#!/usr/bin/env python3
"""Plan-only macOS application residue discovery; deletion is a separate, confirmed action."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys
import time

SCHEMA = 1
USER_AREAS = {
    "Application Support": "app-data",
    "Caches": "cache",
    "Preferences": "preferences",
    "Logs": "logs",
    "Containers": "sandbox",
    "Saved Application State": "saved-state",
    "HTTPStorages": "http-storage",
    "WebKit": "webkit",
    "Group Containers": "shared-container",
    "LaunchAgents": "launch-agent",
}
SYSTEM_AREAS = {
    "/Library/LaunchAgents": "system-launch-agent",
    "/Library/LaunchDaemons": "system-launch-daemon",
    "/Library/PrivilegedHelperTools": "privileged-helper",
    "/Library/Application Support": "system-app-data",
}
REVIEW_ONLY = {"shared-container", "launch-agent", "system-launch-agent",
               "system-launch-daemon", "privileged-helper", "system-app-data"}
TRAILING = (".plist", ".savedState")
MAX_FILES_PER_TARGET = 20_000
MAX_SECONDS_PER_TARGET = 3.0


def normalized(text: str) -> str:
    return "".join(c for c in text.casefold() if c.isalnum())


def identity(path: Path) -> dict | None:
    info = path / "Contents" / "Info.plist"
    try:
        with info.open("rb") as fp:
            data = plistlib.load(fp)
        bundle = data.get("CFBundleIdentifier")
        if not isinstance(bundle, str) or not bundle:
            return None
        return {"path": str(path), "bundle_id": bundle,
                "name": path.stem, "display_name": data.get("CFBundleDisplayName")
                or data.get("CFBundleName") or path.stem}
    except (OSError, ValueError, TypeError, plistlib.InvalidFileException):
        return None


def installed_apps(roots: list[Path]) -> list[dict]:
    found = []
    seen = set()
    for root in roots:
        if not root.is_dir():
            continue
        # Apps directly below each root and apps inside a single nested folder.
        try:
            first = list(root.iterdir())
        except OSError:
            continue
        for item in first:
            entries = [item]
            if item.is_dir() and not item.name.endswith(".app"):
                try:
                    entries = list(item.iterdir())
                except OSError:
                    continue
            for app in entries:
                if app.suffix.lower() != ".app" or app.is_symlink() or not app.is_dir():
                    continue
                real = os.path.realpath(app)
                if real in seen:
                    continue
                seen.add(real)
                info = identity(app)
                if info:
                    found.append(info)
    return found


def resolve_app(apps: list[dict], *, name: str | None, bundle_id: str | None) -> dict:
    if name:
        n = normalized(name.removesuffix(".app"))
        matches = [a for a in apps if n in {normalized(a["name"]),
                                             normalized(a["display_name"])}]
    else:
        matches = [a for a in apps if a["bundle_id"].casefold() == bundle_id.casefold()]
    if len(matches) > 1:
        raise ValueError("Multiple apps match; use --bundle-id if unique, or inspect manually: "
                         + ", ".join(a["path"] for a in matches))
    if len(matches) == 1:
        return matches[0]
    if bundle_id:
        if not re.fullmatch(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+", bundle_id):
            raise ValueError("Invalid Bundle ID")
        return {"path": None, "bundle_id": bundle_id, "name": None,
                "display_name": None}
    raise ValueError("App name not found in usual Applications locations; retry with --bundle-id")


def residue_match(basename: str, bundle: str, aliases: list[str], category: str) -> tuple[str, str] | None:
    base = basename
    for ending in TRAILING:
        if base.casefold().endswith(ending.casefold()):
            base = base[:-len(ending)]
            break
    if base.casefold() == bundle.casefold():
        return ("high", "exact Bundle ID")
    if category == "temp-cache" and base.casefold() in {
        bundle.casefold() + ".helper", bundle.casefold() + ".renderer"
    }:
        return ("high", "Bundle ID auxiliary cache")
    # A prefix is only evidence, not proof: do not auto-approve shared components.
    if base.casefold().startswith(bundle.casefold() + "."):
        return ("review", "Bundle ID prefix; verify component ownership")
    norm = normalized(base)
    # A short non-ASCII name (e.g. Chinese app titles) can be distinctive;
    # still require an exact whole-name match, never substring matching.
    min_length = 3 if any(ord(c) > 127 for c in norm) else 8
    if len(norm) >= min_length and norm in {normalized(a) for a in aliases if a}:
        return ("high", "exact normalized application name")
    return None


def file_summary(path: Path) -> dict:
    """Bounded metadata snapshot; never follow symlinks or open user file contents."""
    stats = path.lstat()
    result = {"device": stats.st_dev, "inode": stats.st_ino,
              "mtime_ns": stats.st_mtime_ns, "owner_uid": stats.st_uid,
              "kind": "directory" if path.is_dir() else "file"}
    if not path.is_dir():
        result.update(files=1, directories=0, bytes=stats.st_size, truncated=False)
        return result

    files, folders, size, clipped = 0, 0, 0, False
    deadline = time.monotonic() + MAX_SECONDS_PER_TARGET
    digest = hashlib.sha256()
    walk_errors = []

    def record(entry: Path, info: os.stat_result) -> None:
        # Include file names + metadata to detect child changes even when the
        # enclosing directory mtime stays constant. No file contents are read.
        relative = entry.relative_to(path).as_posix()
        digest.update(json.dumps([relative, info.st_dev, info.st_ino, info.st_mode,
                                  info.st_uid, info.st_size, info.st_mtime_ns,
                                  info.st_ctime_ns], ensure_ascii=False).encode("utf-8"))
        digest.update(b"\n")

    def onerror(error: OSError) -> None:
        walk_errors.append(str(error))

    record(path, stats)
    for root, dirs, names in os.walk(path, followlinks=False, onerror=onerror):
        if time.monotonic() >= deadline:
            clipped = True
            break
        dirs.sort()
        names.sort()
        for dirname in dirs:
            try:
                record(Path(root) / dirname, (Path(root) / dirname).lstat())
                folders += 1
            except OSError:
                clipped = True
            if time.monotonic() >= deadline:
                clipped = True
                break
        if clipped:
            break
        for name in names:
            if files >= MAX_FILES_PER_TARGET or time.monotonic() >= deadline:
                clipped = True
                break
            try:
                entry = Path(root) / name
                entry_stats = entry.lstat()
                record(entry, entry_stats)
                size += entry_stats.st_size
                files += 1
            except OSError:
                clipped = True
        if clipped:
            break
    if walk_errors:
        clipped = True
    result.update(files=files, directories=folders, bytes=size, truncated=clipped,
                  fingerprint=digest.hexdigest())
    return result


def allowed_source(path: Path, category: str, home: Path) -> bool:
    """Restrict a deletion candidate to a shallow, exact application-owned location."""
    if path.is_symlink() or not path.is_absolute():
        return False
    try:
        if path.lstat().st_uid != os.getuid():
            return False
    except OSError:
        return False
    # No symlink ancestors: a planned path must stay in its apparent subtree.
    if os.path.realpath(path) != str(path):
        return False
    if category == "app":
        return (path.suffix.lower() == ".app"
                and (path.parent == Path("/Applications") or path.parent == home / "Applications")
                and path != Path("/Applications"))
    if category == "temp-cache":
        parts = path.parts
        return (len(parts) == 8 and parts[:4] == ("/", "private", "var", "folders")
                and parts[6] == "C")
    if category in REVIEW_ONLY:
        return False
    for dirname, value in USER_AREAS.items():
        if value == category and path.parent == home / "Library" / dirname:
            return True
    return False


def plan_digest(data: dict) -> str:
    unsigned = {key: value for key, value in data.items() if key != "plan_id"}
    raw = json.dumps(unsigned, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def scan(args: argparse.Namespace) -> int:
    home = Path.home()
    apps = installed_apps([Path("/Applications"), home / "Applications"])
    app = resolve_app(apps, name=args.name, bundle_id=args.bundle_id)
    bundle = app["bundle_id"]
    if bundle.casefold().startswith("com.apple."):
        raise ValueError("Apple system/vendor bundles are excluded from automated uninstallation")
    aliases = [app.get("name") or "", app.get("display_name") or ""]
    if args.name:
        aliases.append(args.name)
    candidates = []
    warnings = []

    def add(path: Path, category: str, confidence: str, evidence: str):
        if path.is_symlink() or not path.exists():
            return
        try:
            detail = file_summary(path)
        except OSError as ex:
            warnings.append("Cannot inspect " + str(path) + ": " + str(ex))
            return
        if detail["owner_uid"] != os.getuid():
            confidence = "review"
            evidence += "; not owned by current user"
        if detail["truncated"]:
            confidence = "review"
            evidence += "; size scan truncated"
            warnings.append("Incomplete size/count; requires manual inspection: " + str(path))
        if bundle.casefold().startswith("com.apple."):
            confidence = "review"
            evidence += "; Apple/system-owned bundle"
        if category in REVIEW_ONLY or not allowed_source(path, category, home):
            confidence = "review"
        candidates.append({"id": len(candidates) + 1, "path": str(path),
                           "category": category, "confidence": confidence,
                           "evidence": evidence, **detail})

    if app["path"]:
        add(Path(app["path"]), "app", "high", "installed bundle Info.plist: " + bundle)
    for dirname, category in USER_AREAS.items():
        root = home / "Library" / dirname
        if not root.is_dir():
            continue
        try:
            entries = sorted(root.iterdir(), key=lambda p: p.name.casefold())
        except OSError as ex:
            warnings.append("Cannot list " + str(root) + ": " + str(ex))
            continue
        for entry in entries:
            match = residue_match(entry.name, bundle, aliases, category)
            if match:
                add(entry, category, *match)

    for dirname, category in SYSTEM_AREAS.items():
        root = Path(dirname)
        if not root.is_dir():
            continue
        try:
            entries = root.iterdir()
            for entry in entries:
                match = residue_match(entry.name, bundle, aliases, category)
                if match:
                    add(entry, category, "review", "system-level; " + match[1])
        except OSError as ex:
            warnings.append("Cannot list " + str(root) + ": " + str(ex))

    # macOS transient cache roots; never scan or modify their parent directories.
    try:
        roots = Path("/private/var/folders").glob("*/*/C")
        for cache_root in roots:
            try:
                if not cache_root.is_dir():
                    continue
                for entry in cache_root.iterdir():
                    match = residue_match(entry.name, bundle, aliases, "temp-cache")
                    if match:
                        add(entry, "temp-cache", *match)
            except PermissionError:
                # Other users' caches are expected to be inaccessible.
                continue
            except OSError as ex:
                warnings.append("Cannot inspect cache " + str(cache_root) + ": " + str(ex))
    except OSError as ex:
        warnings.append("Cannot list temporary cache roots: " + str(ex))

    # Avoid duplicate exact path entries and make numbering deterministic.
    candidates = sorted({c["path"]: c for c in candidates}.values(), key=lambda c: c["path"])
    for index, item in enumerate(candidates, 1):
        item["id"] = index
    plan = {"schema": SCHEMA, "scanned_at": datetime.now(timezone.utc).isoformat(),
            "app": app, "items": candidates, "warnings": warnings,
            "excluded_by_policy": ["macOS Recent Documents / sharedfilelist",
                                   "unmatched, shared, or uncertain resources"]}
    plan["plan_id"] = plan_digest(plan)
    if args.output:
        dest = Path(args.output).expanduser()
        dest.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fp:
            json.dump(plan, fp, indent=2, ensure_ascii=False)
            fp.write("\n")
    print(json.dumps(plan, indent=2, ensure_ascii=False))
    return 0


def trash(args: argparse.Namespace) -> int:
    home = Path.home()
    plan = json.loads(Path(args.manifest).expanduser().read_text(encoding="utf-8"))
    if plan.get("schema") != SCHEMA or plan_digest(plan) != plan.get("plan_id"):
        raise ValueError("Invalid or changed manifest; rescan")
    if args.confirm != plan["plan_id"]:
        raise ValueError("Confirmation ID mismatch; obtain approval for this exact plan")
    if plan["app"]["bundle_id"].casefold().startswith("com.apple."):
        raise ValueError("Apple system bundles are review-only; refusing automated removal")
    selected = [int(x) for x in args.ids.split(",")]
    if len(selected) != len(set(selected)) or not selected:
        raise ValueError("IDs must be a nonempty, unique comma-separated list")
    items = {i["id"]: i for i in plan["items"]}
    paths = []
    for ident in selected:
        if ident not in items:
            raise ValueError("Unknown selected ID: " + str(ident))
        item = items[ident]
        path = Path(item["path"])
        if item["confidence"] != "high" or not allowed_source(path, item["category"], home):
            raise ValueError("Refusing review-only or unapproved location: " + str(path))
        if not path.exists():
            raise ValueError("Path no longer exists, rescan: " + str(path))
        stat = path.lstat()
        if (stat.st_dev, stat.st_ino, stat.st_mtime_ns) != (
            item["device"], item["inode"], item["mtime_ns"]
        ):
            raise ValueError("Target changed since scan, rescan: " + str(path))
        if item["kind"] == "directory":
            current = file_summary(path)
            if current["truncated"] or any(current.get(key) != item.get(key)
                   for key in ("fingerprint", "bytes", "files", "directories")):
                raise ValueError("Directory contents changed since scan, rescan: " + str(path))
        if stat.st_uid != os.getuid() or item.get("owner_uid") != stat.st_uid:
            raise ValueError("Source not owned by current user, rescan: " + str(path))
        if item["category"] != "app":
            aliases = [plan["app"].get("name") or "", plan["app"].get("display_name") or ""]
            evidence = residue_match(path.name, plan["app"]["bundle_id"], aliases,
                                     item["category"])
            if evidence is None or evidence[0] != "high":
                raise ValueError("Target name no longer matches application identity: " + str(path))
        if item["category"] == "app":
            found = identity(path)
            if not found or found["bundle_id"] != plan["app"]["bundle_id"]:
                raise ValueError("Application identity changed: " + str(path))
        paths.append(str(path))
    script = Path(__file__).with_name("trash.swift")
    result = subprocess.run(["swift", str(script), plan["app"]["bundle_id"], *paths],
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    discovery = commands.add_parser("scan", help="Read-only inventory; optionally write a plan file")
    entry = discovery.add_mutually_exclusive_group(required=True)
    entry.add_argument("--name", help="Exact installed application name")
    entry.add_argument("--bundle-id", help="Bundle ID (supports already-removed apps)")
    discovery.add_argument("--output", help="Create new manifest JSON; refuses overwrite")
    removal = commands.add_parser("trash", help="Move selected high-confidence IDs to Trash")
    removal.add_argument("--manifest", required=True)
    removal.add_argument("--confirm", required=True, help="Exact plan ID, only after human approval")
    removal.add_argument("--ids", required=True, help="Comma-separated IDs explicitly approved by user")
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("macOS only")
    try:
        return scan(args) if args.command == "scan" else trash(args)
    except (ValueError, OSError, KeyError, RuntimeError) as ex:
        print("REFUSED: " + str(ex), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
