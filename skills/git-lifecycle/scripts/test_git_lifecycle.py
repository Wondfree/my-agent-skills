#!/usr/bin/env python3
"""Offline integration tests using disposable repositories only."""
from __future__ import annotations

import json
import importlib.util
import io
import os
from contextlib import redirect_stdout
from unittest.mock import patch
from pathlib import Path
import subprocess
import sys
import tempfile

SCRIPT = Path(__file__).with_name("git_lifecycle.py")


def fixture_env() -> dict[str, str]:
    """Isolate Git fixture creation from the caller's repos, hooks, and config."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GIT_") and k not in
           {"SSH_ASKPASS", "SSH_ASKPASS_REQUIRE", "GCM_INTERACTIVE"}}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_SYSTEM=os.devnull,
               GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0")
    return env


def run(*args: str, cwd: Path | None = None, expect: int = 0) -> str:
    command = list(args)
    if command and command[0] == "git":
        command[1:1] = ["-c", "core.hooksPath=/dev/null",
                         "-c", "commit.gpgSign=false", "-c", "tag.gpgSign=false",
                         "-c", "core.fsmonitor=false"]
    result = subprocess.run(command, cwd=cwd, env=fixture_env(),
                            capture_output=True, text=True, timeout=20)
    if result.returncode != expect:
        raise AssertionError(f"Expected {expect}, got {result.returncode}: {args}\n{result.stdout}\n{result.stderr}")
    return result.stdout


def check(repo: Path, *options: str) -> dict:
    return json.loads(run(sys.executable, "-B", str(SCRIPT), "check", "--repo", str(repo),
                          "--json", *options))


def init_repo(path: Path) -> None:
    run("git", "init", "-b", "main", str(path))
    run("git", "config", "user.name", "Fixture Agent", cwd=path)
    run("git", "config", "user.email", "fixture@example.invalid", cwd=path)
    (path / "README.md").write_text("initial\n")
    run("git", "add", "README.md", cwd=path)
    run("git", "commit", "-m", "initial", cwd=path)


def commit(path: Path, filename: str) -> None:
    (path / filename).write_text(filename + "\n")
    run("git", "add", filename, cwd=path)
    run("git", "commit", "-m", "fixture " + filename, cwd=path)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="git-lifecycle-p0-") as tmp:
        root = Path(tmp)
        repo = root / "repo with spaces"
        init_repo(repo)

        baseline = check(repo)["repositories"][0]
        assert baseline["status"] == "CLEAN"
        assert baseline["remote_base"]["status"] == "NOT_REQUESTED"

        # Test clean and process individually: either configured executable
        # filter must block scanning before invoking Git status.
        marker = root / "filter-executed"
        for config_key, command in (
            ("filter.audit.clean", f"sh -c 'touch {marker}; cat'"),
            ("filter.audit.process", "sh -c 'exit 1'"),
        ):
            run("git", "config", config_key, command, cwd=repo)
            failed = json.loads(run(sys.executable, "-B", str(SCRIPT), "check",
                                    "--repo", str(repo), "--json", expect=1))
            assert failed["errors"] and not marker.exists()
            run("git", "config", "--unset", config_key, cwd=repo)
        assert check(repo)["repositories"][0]["status"] == "CLEAN"

        # Fixture commands must ignore inherited Git redirection/config,
        # not merely the production scan subprocess.
        with patch.dict(os.environ, {
            "GIT_DIR": str(repo / ".git"),
            "GIT_WORK_TREE": str(repo),
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "commit.gpgsign",
            "GIT_CONFIG_VALUE_0": "true",
        }):
            assert Path(run("git", "-C", str(repo), "rev-parse",
                            "--show-toplevel").strip()).resolve() == repo.resolve()
            assert "GIT_DIR" not in fixture_env()
            assert "GIT_CONFIG_COUNT" not in fixture_env()

        # A colliding tag must not cause branch names to be shortened as "heads/main".
        run("git", "tag", "main", cwd=repo)
        assert check(repo)["repositories"][0]["status"] == "CLEAN"
        assert check(repo)["repositories"][0]["current_branch"] == "main"
        run("git", "tag", "-d", "main", cwd=repo)

        # Detached HEAD with unreferenced commits must never report CLEAN.
        run("git", "switch", "--detach", "main", cwd=repo)
        assert check(repo)["repositories"][0]["status"] == "CLEAN"
        commit(repo, "detached-only.txt")
        detached = check(repo)["repositories"][0]
        assert detached["status"] == "NEEDS_DECISION"
        assert detached["detached_head_unmerged"] is True
        assert detached["head_sha"] == run("git", "rev-parse", "HEAD", cwd=repo).strip()
        run("git", "switch", "main", cwd=repo)

        # A merged, inactive temporary branch is NOT cleanup-ready on an unverified remote.
        run("git", "switch", "-c", "codex/finished", cwd=repo)
        commit(repo, "finished.txt")
        run("git", "switch", "main", cwd=repo)
        run("git", "merge", "--ff-only", "codex/finished", cwd=repo)
        offline = check(repo)["repositories"][0]
        assert offline["branches"][0]["status"] == "NEEDS_DECISION"
        assert not offline["branches"][0]["published_to_remote_base"]

        remote = root / "remote.git"
        run("git", "init", "--bare", str(remote))
        run("git", "remote", "add", "origin", str(remote), cwd=repo)
        run("git", "push", "-u", "origin", "main", cwd=repo)
        verified = check(repo, "--verify-remote")["repositories"][0]
        assert verified["branches"][0]["status"] == "CLEANUP_READY"
        assert verified["remote_base"]["status"] == "VERIFIED"

        # Configured upload-pack helpers must never execute during verification,
        # even for a file:// or absolute local bare repository.
        upload_marker = root / "unsafe-uploadpack-ran"
        run("git", "config", "remote.origin.uploadpack",
            f"sh -c 'touch {upload_marker}'", cwd=repo)
        protected = check(repo, "--verify-remote")["repositories"][0]
        assert protected["remote_base"]["status"] == "VERIFIED"
        assert protected["branches"][0]["status"] == "CLEANUP_READY"
        assert not upload_marker.exists()

        # Do not interpret configured remote URL rewrites / external helpers.
        run("git", "remote", "set-url", "origin", "ext::sh -c 'exit 0'", cwd=repo)
        refused = check(repo, "--verify-remote")["repositories"][0]
        assert refused["remote_base"]["status"] == "UNAVAILABLE"
        assert refused["branches"][0]["status"] == "NEEDS_DECISION"
        run("git", "remote", "set-url", "origin", str(remote), cwd=repo)

        # Unmerged branch must not become a cleanup candidate even with live remote verification.
        run("git", "switch", "-c", "codex/unmerged", cwd=repo)
        commit(repo, "unmerged.txt")
        run("git", "switch", "main", cwd=repo)
        unmerged = check(repo, "--verify-remote")["repositories"][0]
        assert next(b for b in unmerged["branches"] if b["name"] == "codex/unmerged")["status"] == "NEEDS_DECISION"

        # A checked-out worktree is active, not eligible for automatic deletion.
        extra = root / "running worktree"
        run("git", "worktree", "add", str(extra), "codex/unmerged", cwd=repo)
        active = check(repo, "--verify-remote")["repositories"][0]
        assert next(b for b in active["branches"] if b["name"] == "codex/unmerged")["status"] == "ACTIVE"
        assert active["extra_worktrees"][0]["status"] == "ACTIVE"

        # An additional worktree's untracked data requires a human decision;
        # the primary checkout's status alone is not sufficient.
        (extra / "valuable-unsaved.txt").write_text("preserve me")
        extra_dirty = check(repo)["repositories"][0]
        x = next(w for w in extra_dirty["extra_worktrees"] if w["path"] == str(extra.resolve()))
        assert x["status"] == "NEEDS_DECISION"
        assert x["dirty_entries"] > 0
        (extra / "valuable-unsaved.txt").unlink()

        # Additional detached worktree can carry unique unmerged commits.
        detached_extra = root / "detached running worktree"
        run("git", "worktree", "add", "--detach", str(detached_extra), "main", cwd=repo)
        run("git", "config", "user.name", "Fixture Agent", cwd=detached_extra)
        run("git", "config", "user.email", "fixture@example.invalid", cwd=detached_extra)
        commit(detached_extra, "detached-extra.txt")
        detached_status = check(repo)["repositories"][0]
        w = next(x for x in detached_status["extra_worktrees"]
                 if x["path"] == str(detached_extra.resolve()))
        assert w["status"] == "NEEDS_DECISION"
        assert w["head_sha"] == run("git", "rev-parse", "HEAD", cwd=detached_extra).strip()
        assert w["detached_head_contained_in_local_base"] is False

        # Untracked files are preserved and reported.
        (repo / "not-yet-saved.txt").write_text("keep")
        assert check(repo)["repositories"][0]["dirty_entries"] >= 1
        (repo / "not-yet-saved.txt").unlink()

        # A submodule's gitlink is checked independently of the child's working-tree state.
        child = root / "child source"
        init_repo(child)
        run("git", "branch", "-m", "master", cwd=child)
        run("git", "-c", "protocol.file.allow=always", "submodule", "add",
            str(child), "components/child", cwd=repo)
        run("git", "commit", "-m", "add submodule", cwd=repo)
        run("git", "push", "origin", "main", cwd=repo)
        proper = check(repo)["repositories"][0]
        assert proper["submodules"][0]["status"] == "MATCH"
        nested = check(repo)["repositories"]
        assert len(nested) == 2
        assert nested[1]["base"] == "master"
        assert nested[1]["extra_worktrees"] == []
        assert nested[1]["branches"] == []

        # Child clean filter is dangerous even if the parent has no filters.
        # Verify the attribute conversion actually invokes the configured
        # command, then prove the parent audit never invokes that filter.
        child_checkout = repo / "components/child"
        child_marker = root / "submodule-filter-executed"
        (child_checkout / ".gitattributes").write_text("README.md filter=childhook\n")
        (child_checkout / "README.md").write_text("changed to invoke clean filter\n")
        run("git", "config", "filter.childhook.clean",
            f"sh -c 'touch {child_marker}; cat'", cwd=child_checkout)
        run("git", "hash-object", "--path=README.md", "README.md", cwd=child_checkout)
        assert child_marker.exists(), "Regression fixture failed to activate child clean filter"
        child_marker.unlink()
        rejected = json.loads(run(sys.executable, "-B", str(SCRIPT), "check",
                                  "--repo", str(repo), "--json", expect=1))
        assert rejected["errors"], "Configured submodule filter did not fail closed"
        assert not child_marker.exists(), "Parent audit invoked child filter"
        run("git", "config", "--unset", "filter.childhook.clean", cwd=child_checkout)
        run("git", "restore", "README.md", cwd=child_checkout)
        (child_checkout / ".gitattributes").unlink()

        # Staged submodule gitlink updates must be detected even though status
        # skips child recursion. Parent HEAD still points at the older gitlink.
        original_child_sha = run("git", "rev-parse", "HEAD", cwd=child_checkout).strip()
        run("git", "config", "user.name", "Fixture Agent", cwd=child_checkout)
        run("git", "config", "user.email", "fixture@example.invalid", cwd=child_checkout)
        commit(child_checkout, "staged-child.txt")
        run("git", "add", "components/child", cwd=repo)
        staged_result = check(repo)["repositories"][0]
        assert staged_result["dirty_entries"] > 0
        assert staged_result["status"] == "NEEDS_DECISION"
        run("git", "reset", "-q", "HEAD", "--", "components/child", cwd=repo)
        run("git", "reset", "--hard", original_child_sha, cwd=child_checkout)
        assert check(repo)["repositories"][0]["submodules"][0]["status"] == "MATCH"

        # A linked worktree created before the submodule was added has a
        # different tree; create a linked checkout at the new main to prove
        # nested gitlink mismatches and submodule changes are also inspected.
        sub_wt = root / "worktree with submodule"
        run("git", "worktree", "add", "--detach", str(sub_wt), "main", cwd=repo)
        uninit = check(repo)["repositories"][0]
        record = next(w for w in uninit["extra_worktrees"]
                      if w["path"] == str(sub_wt.resolve()))
        assert record["status"] == "NEEDS_DECISION"
        assert record["submodules"][0]["status"] == "UNINITIALIZED"
        # Initialize solely in the disposable fixture, not any real project.
        run("git", "-c", "protocol.file.allow=always",
            "submodule", "update", "--init", cwd=sub_wt)
        (sub_wt / "components/child" / "unsaved-child.txt").write_text("important")
        linked_child = check(repo)["repositories"][0]
        record = next(w for w in linked_child["extra_worktrees"]
                      if w["path"] == str(sub_wt.resolve()))
        assert record["status"] == "NEEDS_DECISION"
        assert record["submodules"][0]["status"] == "MATCH"
        assert any(n["path"] == str((sub_wt / "components/child").resolve())
                   and n["dirty_entries"] > 0 for n in check(repo)["repositories"])

        child_checkout = repo / "components/child"
        run("git", "config", "user.name", "Fixture Agent", cwd=child_checkout)
        run("git", "config", "user.email", "fixture@example.invalid", cwd=child_checkout)
        commit(child_checkout, "later.txt")
        mismatched = check(repo)["repositories"][0]
        assert mismatched["submodules"][0]["status"] == "MISMATCH"
        assert mismatched["status"] == "NEEDS_DECISION"

        # Explicit registry, no disk discovery, no writes to default global configuration.
        registry = root / "projects.json"
        registry.write_text(json.dumps({"version": 1, "repositories": [str(repo), str(child)]}))
        all_result = json.loads(run(sys.executable, "-B", str(SCRIPT), "check",
                                    "--all", "--registry", str(registry), "--json"))
        scanned_paths = {n["path"] for n in all_result["repositories"]}
        assert scanned_paths == {str(repo.resolve()), str(child_checkout.resolve()),
                                 str((sub_wt / "components/child").resolve()), str(child.resolve())}, scanned_paths
        absent = run(sys.executable, "-B", str(SCRIPT), "check", "--all",
                     "--registry", str(root / "absent.json"), expect=2)
        assert not absent
        assert registry.exists()
        assert (extra / "unmerged.txt").exists()

        # Exception translation and report isolation for ancestry command timeouts.
        spec = importlib.util.spec_from_file_location("gl_p0_test", SCRIPT)
        assert spec and spec.loader
        gl = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gl)
        with patch.object(gl.subprocess, "run", side_effect=subprocess.TimeoutExpired("git", 12)):
            try:
                gl.is_ancestor(repo, "main", "HEAD")
                raise AssertionError("Timeout was not raised as ScanError")
            except gl.ScanError:
                pass
        # No implicit Git blob hydration even when object probes are made.
        orig_run = subprocess.run
        seen = []
        def inspect_env(args, **kwargs):
            seen.append(kwargs.get("env", {}).get("GIT_NO_LAZY_FETCH"))
            return orig_run(args, **kwargs)
        with patch.object(gl.subprocess, "run", side_effect=inspect_env):
            gl.git(repo, "cat-file", "-e", "HEAD^{commit}")
        assert seen == ["1"], seen

        # Inherited Git env must not redirect an explicit path to another repo.
        with patch.dict(os.environ, {
            "GIT_DIR": str(repo / ".git"),
            "GIT_WORK_TREE": str(repo),
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "remote.origin.url",
            "GIT_CONFIG_VALUE_0": "ext::malicious",
            "GIT_NO_REPLACE_OBJECTS": "0",
            "SSH_ASKPASS": "/usr/bin/printf",
            "SSH_ASKPASS_REQUIRE": "force",
        }):
            assert Path(gl.git(child, "rev-parse", "--show-toplevel")).resolve() == child.resolve()
            assert gl.safe_git_environment()["GIT_NO_REPLACE_OBJECTS"] == "1"
            assert "GIT_DIR" not in gl.safe_git_environment()
            assert "GIT_CONFIG_COUNT" not in gl.safe_git_environment()
            assert "SSH_ASKPASS" not in gl.safe_git_environment()
            assert "SSH_ASKPASS_REQUIRE" not in gl.safe_git_environment()
        assert gl.safe_remote_url("file://user:secret@localhost/repo.git") is None

        # Even a successful branch enumeration must not hide broken-ref warnings.
        valid = gl.git(repo, "for-each-ref",
                       "--format=%(refname)%09%(objectname)", "refs/heads")
        def warn_ref_call(path, *args, **kwargs):
            if args[0] == "for-each-ref":
                return subprocess.CompletedProcess(["git"], 0, valid,
                                                   "warning: ignoring broken ref refs/heads/codex/lost")
            return gl.git_command(path, *args, **kwargs)
        with patch.object(gl, "git_command", side_effect=warn_ref_call):
            try:
                gl.local_branches(repo)
                raise AssertionError("Broken-ref warning was silently accepted")
            except gl.ScanError:
                pass

        # Fsmonitor hooks can execute arbitrary commands inside git status.
        # Inject a harmless hook through a temporary environment override;
        # the checker must explicitly disable it before all Git probes.
        marker = root / "fsmonitor-executed.txt"
        hook = f"touch '{marker}'"
        with patch.dict(__import__("os").environ, {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.fsmonitor",
            "GIT_CONFIG_VALUE_0": hook,
        }):
            scanned = gl.scan_one(repo, "main", False, set())
        assert scanned
        assert not marker.exists(), "Checker executed core.fsmonitor hook"

        second = root / "second repo"
        init_repo(second)
        first_sha = run("git", "rev-parse", "HEAD", cwd=second).strip()
        commit(second, "successor.txt")
        successor_sha = run("git", "rev-parse", "HEAD", cwd=second).strip()
        # Replacement makes successor look unrelated to the original root.
        run("git", "replace", successor_sha, first_sha, cwd=second)
        run("git", "merge-base", "--is-ancestor", first_sha, successor_sha,
            cwd=second, expect=1)
        assert gl.is_ancestor(second, first_sha, successor_sha), "Replace objects affected ancestry"

        # Legacy info/grafts can still alter ancestry even without replacements.
        graft = second / ".git" / "info" / "grafts"
        graft.write_text(successor_sha + "\n")
        try:
            gl.scan_one(second, "main", False, set())
        except gl.ScanError:
            pass
        else:
            raise AssertionError("Legacy grafts were silently accepted")
        finally:
            graft.unlink()

        bare = root / "bare admin.git"
        run("git", "init", "--bare", str(bare))
        bare_checkout = root / "bare linked worktree"
        # Need a commit for the bare-backed worktree.
        run("git", "remote", "add", "bare-origin", str(bare), cwd=second)
        run("git", "push", "bare-origin", "main", cwd=second)
        run("git", "--git-dir", str(bare), "worktree", "add",
            "-b", "view", str(bare_checkout), "main")
        bare_item = check(bare_checkout)["repositories"][0]
        assert bare_item["extra_worktrees"] == []

        def fail_one(path, ancestor, descendant):
            if path.resolve() == repo.resolve():
                raise gl.ScanError("Synthetic ancestry timeout")
            return True
        argv = ["git_lifecycle.py", "check", "--repo", str(second),
                "--repo", str(repo), "--json"]
        capture = io.StringIO()
        with patch.object(gl, "is_ancestor", side_effect=fail_one), patch.object(sys, "argv", argv):
            with redirect_stdout(capture):
                code = gl.main()
        assert code == 1
        report = json.loads(capture.getvalue())
        assert len(report["repositories"]) == 1
        assert len(report["errors"]) == 1 and report["errors"][0]["path"] == str(repo)

        original_scan = gl.scan_one
        def nested_failure(path, base, verify_remote, visited):
            if path.resolve() == child_checkout.resolve():
                raise gl.ScanError("Synthetic nested scan failure")
            return original_scan(path, base, verify_remote, visited)
        capture = io.StringIO()
        with patch.object(gl, "scan_one", side_effect=nested_failure):
            with patch.object(sys, "argv", ["git_lifecycle.py", "check", "--repo", str(repo), "--json"]):
                with redirect_stdout(capture):
                    code = gl.main()
        result = json.loads(capture.getvalue())
        assert code == 1
        assert any(x["path"] == str(child_checkout.resolve()) for x in result["errors"])
        assert result["repositories"][0]["submodules"][0]["status"] == "UNKNOWN"

    print(json.dumps({"passed": True, "scenarios": [
        "clean", "offline no false publication", "verified merged candidate",
        "unmerged branch", "active worktree", "dirty worktree", "submodule mismatch",
        "multi-repo registry", "missing registry fails closed",
        "colliding tag and branch", "detached HEAD unmerged commits",
        "ancestry subprocess timeout", "batch error isolation", "disable lazy fetch",
        "detached linked worktree commits", "nested submodule failure propagation",
        "linked worktree dirty", "linked worktree submodule",
        "fsmonitor hook disabled", "bare storage excluded",
        "env path/config injection blocked", "remote uploadpack not invoked",
        "unsafe remote scheme rejected", "replace objects ignored",
        "askpass inheritance blocked", "credentialed file remote refused",
        "broken ref warning fails closed", "legacy grafts fail closed",
        "external filters fail closed", "fixture Git environment isolation",
        "child filter never executes from parent status",
        "staged gitlink not hidden by submodule skipping"]}))


if __name__ == "__main__":
    main()
