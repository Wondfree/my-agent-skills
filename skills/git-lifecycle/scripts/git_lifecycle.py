#!/usr/bin/env python3
"""P0 read-only Git branch/worktree/submodule inventory; never modifies repositories."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit

DEFAULT_REGISTRY = Path.home() / ".config/git-lifecycle/projects.json"
TEMP_PREFIXES = ("codex/", "agent/", "feature/", "fix/", "task/", "tmp/", "temp/", "experiment/")
STATUS_PRIORITY = {"CLEAN": 0, "CLEANUP_READY": 1, "ACTIVE": 2, "NEEDS_DECISION": 3}


class ScanError(Exception):
    pass


def safe_git_environment() -> dict[str, str]:
    """Never inherit Git's repository, config, tracing or hook injection variables."""
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("GIT_") and key not in {
               "GCM_INTERACTIVE", "SSH_ASKPASS", "SSH_ASKPASS_REQUIRE",
               "SSH_ASKPASS_PROMPT",
           }}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0",
               GCM_INTERACTIVE="Never", GIT_ALLOW_PROTOCOL="https:file",
               GIT_NO_LAZY_FETCH="1", GIT_NO_REPLACE_OBJECTS="1",
               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
               GIT_CONFIG_NOSYSTEM="1")
    return env


def git_command(path: Path, *args: str, timeout: int = 12,
                repository_config: bool = True) -> subprocess.CompletedProcess[str]:
    argv = ["git", "-c", "core.fsmonitor=false",
            "-c", "core.hooksPath=/dev/null"]
    if not repository_config:
        argv.extend(["-c", "credential.helper="])
    argv.extend(["-C", str(path), *args])
    try:
        return subprocess.run(argv, env=safe_git_environment(), capture_output=True,
                              text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ScanError("Git invocation failed or timed out") from exc


def git(path: Path, *args: str, timeout: int = 12) -> str:
    p = git_command(path, *args, timeout=timeout)
    if p.returncode != 0:
        # Don't surface unchecked stderr: it may contain access tokens/URLs.
        raise ScanError(f"Git command failed (exit {p.returncode})")
    return p.stdout.strip()


def assert_no_external_filters(path: Path) -> None:
    """Fail closed when the repository defines executable conversion filters.

    Git status/diff may run filter.<driver>.clean or .process. Git configuration
    is queried without reading values so sensitive filter command contents do
    not enter reports. Global/system configuration is already isolated.
    """
    p = git_command(path, "config", "--null", "--name-only", "--list")
    if p.returncode != 0 or p.stderr.strip():
        raise ScanError("Cannot safely inspect Git filter configuration")
    config_names = p.stdout.split("\0")
    if any(re.fullmatch(r"filter\..+\.(clean|process)", name, re.IGNORECASE)
           for name in config_names):
        raise ScanError("External Git conversion filters configured; refusing status scan")


def worktree_list(path: Path) -> list[dict]:
    raw = git(path, "worktree", "list", "--porcelain")
    result: list[dict] = []
    entry: dict = {}
    for line in (raw + "\n\n").splitlines():
        if not line:
            if entry:
                result.append(entry)
                entry = {}
            continue
        key, _, value = line.partition(" ")
        if key in ("worktree", "branch", "HEAD"):
            entry[key] = value
        elif key in ("locked", "prunable", "detached", "bare"):
            entry[key] = value or True
    # Submodule Git versions may list the administrative .git/modules/<name>
    # as their primary worktree. It is not an additional checkout.
    git_dir = Path(git(path, "rev-parse", "--absolute-git-dir")).resolve()
    for wt in result:
        if Path(wt.get("worktree", "")).resolve() == git_dir:
            wt["worktree"] = str(path.resolve())
    return result


def local_branches(path: Path) -> list[dict]:
    p = git_command(path, "for-each-ref", "--format=%(refname)%09%(objectname)",
                    "refs/heads")
    # Git may exit zero while warning that it skipped a broken ref. Never
    # report CLEAN or CLEANUP_READY from an incomplete enumeration.
    if p.returncode != 0 or p.stderr.strip():
        raise ScanError("Branch enumeration failed or emitted warnings")
    raw = p.stdout.strip()
    branches = []
    for line in raw.splitlines():
        full_name, sep, sha = line.partition("\t")
        if (not sep or not full_name.startswith("refs/heads/")
                or not re.fullmatch(r"[0-9a-f]{40,64}", sha)):
            raise ScanError("Unexpected branch reference format")
        branches.append({"name": full_name.removeprefix("refs/heads/"), "sha": sha})
    return branches


def is_ancestor(path: Path, ancestor: str, descendant: str) -> bool:
    # 1 means not an ancestor; other errors must not masquerade as unmerged.
    try:
        p = git_command(path, "merge-base", "--is-ancestor", ancestor, descendant)
    except ScanError as exc:
        raise ScanError("Git ancestry comparison failed or timed out") from exc
    if p.returncode not in (0, 1):
        raise ScanError("Could not compare Git ancestry")
    return p.returncode == 0


def safe_remote_url(value: str) -> str | None:
    """Only bare absolute local paths or non-credentialed HTTPS/file URLs."""
    if not value or any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        return None
    if value.startswith("/") and not value.startswith("//"):
        return value
    try:
        parsed = urlsplit(value)
        if (parsed.scheme == "https" and parsed.hostname and parsed.username is None
                and parsed.password is None and parsed.path and not parsed.fragment):
            return value
        if (parsed.scheme == "file" and parsed.hostname in (None, "", "localhost")
                and parsed.username is None and parsed.password is None
                and parsed.path.startswith("/") and not parsed.query and not parsed.fragment):
            return value
    except ValueError:
        return None
    return None


def remote_target(path: Path, base: str, verify_remote: bool) -> dict:
    info = {"status": "NOT_REQUESTED", "sha": None}
    if not verify_remote:
        return info
    try:
        # A remote name is not safe: remote.<name>.uploadpack can be any shell
        # command. Resolve an explicit URL and query it outside the Git checkout,
        # with all per-repository and user Git configuration excluded.
        original_url = git(path, "config", "--local", "--get", "remote.origin.url")
        url = safe_remote_url(original_url)
        if url is None:
            info["status"] = "UNAVAILABLE"
            return info
        p = git_command(Path("/"), "ls-remote", "--heads", url, base,
                        timeout=12, repository_config=False)
        if p.returncode:
            info["status"] = "UNAVAILABLE"
            return info
        lines = p.stdout.splitlines()
        matching = [line.split()[0] for line in lines
                    if line.endswith("\trefs/heads/" + base)]
        if len(matching) != 1 or not re.fullmatch(r"[0-9a-f]{40,64}", matching[0]):
            info["status"] = "UNAVAILABLE"
            return info
        sha = matching[0]
        info["sha"] = sha
        git(path, "cat-file", "-e", sha + "^{commit}")
        info["status"] = "VERIFIED"
    except ScanError:
        info["status"] = "UNAVAILABLE"
    return info


def submodule_links(path: Path) -> list[tuple[str, str]]:
    raw = git(path, "ls-files", "--stage", "-z")
    links: list[tuple[str, str]] = []
    for record in raw.split("\0"):
        if not record:
            continue
        header, sep, name = record.partition("\t")
        parts = header.split()
        if sep and len(parts) == 3 and parts[0] == "160000":
            if parts[2] != "0":
                raise ScanError("Unmerged submodule gitlink: " + name)
            links.append((name, parts[1]))
    return links


def git_common_dir(path: Path) -> Path:
    common = Path(git(path, "rev-parse", "--git-common-dir"))
    # git rev-parse may return .git relative to the checkout's directory.
    return (common if common.is_absolute() else path / common).resolve()


def scan_gitlinks(path: Path, base: str, verify_remote: bool,
                  visited: set[Path]) -> tuple[list[dict], list[dict], list[dict]]:
    """Scan gitlinks from one checkout, preserving partial evidence and errors."""
    items: list[dict] = []
    reports: list[dict] = []
    errors: list[dict] = []
    for relpath, expected in submodule_links(path):
        subdir = (path / relpath).resolve()
        item = {"path": relpath, "expected_gitlink": expected,
                "actual_head": None, "status": "UNINITIALIZED"}
        try:
            if subdir.is_dir():
                root = Path(git(subdir, "rev-parse", "--show-toplevel")).resolve()
                if root == subdir:
                    actual = git(subdir, "rev-parse", "HEAD")
                    item["actual_head"] = actual
                    item["status"] = "MATCH" if actual == expected else "MISMATCH"
                    reports.extend(scan_one(subdir, base, verify_remote, visited))
        except ScanError as exc:
            item["status"] = "UNKNOWN"
            errors.append({"path": str(subdir), "error": str(exc)})
        items.append(item)
    return items, reports, errors


def scan_one(path: Path, base: str, verify_remote: bool, visited: set[Path]) -> list[dict]:
    resolved = path.expanduser().resolve()
    actual_root = Path(git(resolved, "rev-parse", "--show-toplevel")).resolve()
    if actual_root != resolved:
        # Submodules must be initialized; a directory inheriting parent Git is not a submodule.
        if resolved.is_relative_to(actual_root):
            raise ScanError("Not an independent Git checkout: " + str(resolved))
        resolved = actual_root
    if resolved in visited:
        return []
    visited.add(resolved)

    # Git's deprecated info/grafts can rewrite ancestor relationships even
    # when replace objects are disabled. Refuse ancestry classification.
    graft_location = Path(git(resolved, "rev-parse", "--git-path", "info/grafts"))
    graft_path = (graft_location if graft_location.is_absolute()
                  else resolved / graft_location)
    try:
        if graft_path.stat().st_size > 0:
            raise ScanError("Legacy Git grafts present; ancestry cannot be trusted")
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise ScanError("Cannot inspect legacy Git grafts") from exc

    branch_items = local_branches(resolved)
    worktrees = worktree_list(resolved)
    # Use unambiguous full refs from the worktree listing, not --short
    # (a same-named tag can force Git to print "heads/main").
    current = next((w["branch"].removeprefix("refs/heads/")
                    for w in worktrees if Path(w.get("worktree", "")).resolve() == resolved
                    and w.get("branch", "").startswith("refs/heads/")), None)
    head_sha = git(resolved, "rev-parse", "HEAD")
    assert_no_external_filters(resolved)
    # Never let status traverse child repositories before their filters have
    # been independently inspected. The staged gitlink check separately keeps
    # index-vs-HEAD submodule updates visible despite --ignore-submodules=all.
    state = git(resolved, "status", "--porcelain=v1", "--untracked-files=normal",
                "--ignore-submodules=all")
    staged = git(resolved, "diff", "--cached", "--name-only", "--no-ext-diff",
                 "--no-textconv", "--ignore-submodules=none", "HEAD", "--")
    dirty = len(state.splitlines()) if state else 0
    if staged and not dirty:
        dirty = 1
    branch_names = {b["name"] for b in branch_items}
    # Upstream/third-party submodules frequently use master, not main.
    # An explicit non-main base is never silently substituted.
    effective_base = ("master" if base == "main" and base not in branch_names
                      and "master" in branch_names else base)
    remote = remote_target(resolved, effective_base, verify_remote)
    base_sha = next((b["sha"] for b in branch_items if b["name"] == effective_base), None)

    branches: list[dict] = []
    severity = "CLEAN"
    def upgrade(value: str) -> None:
        nonlocal severity
        if STATUS_PRIORITY[value] > STATUS_PRIORITY[severity]:
            severity = value

    if dirty:
        upgrade("NEEDS_DECISION")
    if base_sha is None:
        upgrade("NEEDS_DECISION")
    # Detached HEADs can contain commits reachable from no local branch.
    # HEAD <= base is safe from this particular omission; ahead/divergent is not.
    detached_head_unmerged = (current is None and
                              (base_sha is None or not is_ancestor(resolved, head_sha, base_sha)))
    if detached_head_unmerged:
        upgrade("NEEDS_DECISION")

    for b in branch_items:
        if b["name"] == effective_base:
            continue
        checked_out = [w["worktree"] for w in worktrees
                       if w.get("branch") == "refs/heads/" + b["name"]]
        merged = bool(base_sha and is_ancestor(resolved, b["sha"], base_sha))
        published = (merged and remote["status"] == "VERIFIED"
                     and is_ancestor(resolved, b["sha"], remote["sha"]))
        if checked_out:
            code = "ACTIVE"
            reason = "Checked out in a worktree; ownership/activity not determined"
        elif not merged:
            code = "NEEDS_DECISION"
            reason = "Branch has commits not contained in local base"
        elif not published:
            code = "NEEDS_DECISION"
            reason = "Locally merged but target's remote containment is unverified"
        elif not b["name"].startswith(TEMP_PREFIXES):
            code = "NEEDS_DECISION"
            reason = "Non-temporary naming; do not infer branch ownership"
        else:
            code = "CLEANUP_READY"
            reason = "Technical cleanup candidate only; no ownership or deletion authorization inferred"
        branches.append({"name": b["name"], "sha": b["sha"], "status": code,
                         "merged_into_local_base": merged, "published_to_remote_base": published,
                         "checked_out_at": checked_out, "reason": reason})
        upgrade(code)

    extras: list[dict] = []
    linked_reports: list[dict] = []
    linked_errors: list[dict] = []
    # git worktree list includes the bare common repository (storage only).
    # It is not an active checkout and must not count as an extra worktree.
    common_dir = git_common_dir(resolved)
    for w in worktrees:
        if w.get("bare"):
            continue
        wt = Path(w.get("worktree", "")).resolve()
        if wt == resolved:
            continue
        detached_contained = None
        if w.get("detached") and not w.get("prunable") and base_sha and w.get("HEAD"):
            detached_contained = is_ancestor(resolved, w["HEAD"], base_sha)

        linked_dirty = None
        linked_submodules: list[dict] = []
        inspection_error = None
        linked_children: list[dict] = []
        if not w.get("prunable"):
            try:
                if not wt.is_dir():
                    raise ScanError("Registered worktree directory is missing")
                actual_root = Path(git(wt, "rev-parse", "--show-toplevel")).resolve()
                wt_common = git_common_dir(wt)
                if actual_root != wt or wt_common != common_dir:
                    raise ScanError("Registered worktree points to an unexpected repository")
                assert_no_external_filters(wt)
                state = git(wt, "status", "--porcelain=v1", "--untracked-files=normal",
                            "--ignore-submodules=all")
                staged = git(wt, "diff", "--cached", "--name-only", "--no-ext-diff",
                             "--no-textconv", "--ignore-submodules=none", "HEAD", "--")
                linked_dirty = len(state.splitlines()) if state else 0
                if staged and not linked_dirty:
                    linked_dirty = 1
                linked_submodules, linked_children, child_errors = scan_gitlinks(
                    wt, base, verify_remote, visited)
                linked_reports.extend(linked_children)
                linked_errors.extend(child_errors)
            except ScanError as exc:
                inspection_error = str(exc)
                linked_errors.append({"path": str(wt), "error": inspection_error})

        if w.get("prunable"):
            code, detail = "NEEDS_DECISION", "Git marks worktree prunable; do not prune automatically"
        elif inspection_error:
            code, detail = "NEEDS_DECISION", "Linked worktree inspection failed"
        elif linked_dirty or any(m["status"] != "MATCH" for m in linked_submodules):
            code, detail = "NEEDS_DECISION", "Linked worktree contains unsaved or inconsistent data"
        elif any(r["status"] == "NEEDS_DECISION" for r in linked_children):
            code, detail = "NEEDS_DECISION", "Linked worktree has a child repository requiring review"
        elif detached_contained is False:
            code, detail = ("NEEDS_DECISION",
                            "Detached worktree has commits not contained in local base; preserve and investigate")
        else:
            code, detail = "ACTIVE", "Additional worktree may belong to an active task"
        extras.append({"path": str(wt), "branch": w.get("branch"),
                       "head_sha": w.get("HEAD"), "detached_head_contained_in_local_base": detached_contained,
                       "dirty_entries": linked_dirty, "submodules": linked_submodules,
                       "inspection_error": inspection_error, "status": code, "reason": detail,
                       "locked": bool(w.get("locked")), "prunable": bool(w.get("prunable"))})
        upgrade(code)

    submodules, children, errors = scan_gitlinks(resolved, base, verify_remote, visited)
    if any(m["status"] != "MATCH" for m in submodules):
        upgrade("NEEDS_DECISION")
    if any(r["status"] == "NEEDS_DECISION" for r in children):
        upgrade("NEEDS_DECISION")
    node = {"path": str(resolved), "base": effective_base, "current_branch": current,
            "head_sha": head_sha, "detached_head_unmerged": detached_head_unmerged,
            "dirty_entries": dirty, "remote_base": remote, "branches": branches,
            "extra_worktrees": extras, "submodules": submodules,
            "scan_errors": errors + linked_errors, "status": severity}
    return [node] + children + linked_reports


def registry_paths(registry: Path) -> list[Path]:
    try:
        doc = json.loads(registry.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScanError("Missing or invalid registry file: " + str(registry)) from exc
    if not isinstance(doc, dict) or doc.get("version") != 1 or not isinstance(doc.get("repositories"), list):
        raise ScanError("Expected registry object with version=1 and repositories=[absolute paths]")
    paths = doc["repositories"]
    if not all(isinstance(p, str) and p and Path(p).is_absolute() for p in paths):
        raise ScanError("Registry entries must be absolute path strings")
    return [Path(p) for p in dict.fromkeys(paths)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check",))
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument("--repo", action="append", metavar="PATH",
                         help="One or more explicit checkouts; default: current working directory")
    sources.add_argument("--all", action="store_true", help="Use explicit read-only project registry")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--base", default="main", help="Comparison branch, default main")
    parser.add_argument("--verify-remote", action="store_true",
                        help="Read remote origin/base via ls-remote; no fetch or local ref changes")
    parser.add_argument("--json", action="store_true", help="Machine-readable report")
    args = parser.parse_args()
    try:
        if args.all:
            paths = registry_paths(args.registry)
            if not paths:
                raise ScanError("Registry contains no projects")
        else:
            paths = [Path(p) for p in (args.repo or [os.getcwd()])]
        visited: set[Path] = set()
        reports = []
        errors = []
        for path in paths:
            try:
                scanned = scan_one(path, args.base, args.verify_remote, visited)
                reports.extend(scanned)
                for item in scanned:
                    errors.extend(item["scan_errors"])
            except ScanError as exc:
                errors.append({"path": str(path), "error": str(exc)})
        data = {"schema_version": 1, "mode": "READ_ONLY_P0",
                "remote_verification_requested": args.verify_remote,
                "repositories": reports, "errors": errors}
    except ScanError as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        for item in reports:
            print(f"{item['status']} | {item['path']} | branch={item['current_branch'] or '(detached)'} | dirty={item['dirty_entries']}")
            print(f"  remote base: {item['remote_base']['status']}")
            if item["detached_head_unmerged"]:
                print(f"  NEEDS_DECISION detached HEAD {item['head_sha']}: commits not contained in local base")
            for b in item["branches"]:
                print(f"  {b['status']} branch {b['name']}: {b['reason']}")
            for w in item["extra_worktrees"]:
                print(f"  {w['status']} worktree {w['path']}: {w['reason']}" +
                      (f" (HEAD {w['head_sha']})" if w["detached_head_contained_in_local_base"] is False else "") +
                      (f" (dirty={w['dirty_entries']})" if w["dirty_entries"] else ""))
                for m in w["submodules"]:
                    if m["status"] != "MATCH":
                        print(f"    NEEDS_DECISION linked submodule {m['path']}: {m['status']}")
            for m in item["submodules"]:
                if m["status"] != "MATCH":
                    print(f"  NEEDS_DECISION submodule {m['path']}: {m['status']}")
        for error in errors:
            print(f"ERROR | {error['path']}: {error['error']}")
        print(f"Scanned {len(reports)} checkouts, {len(errors)} errors. No files or Git refs changed by this tool.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
