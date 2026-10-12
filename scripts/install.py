#!/usr/bin/env python3
"""Install skills from this checked-out repository without overwriting local work.

Default: symlink each skill into the Codex skill directory. The repository is SSOT.
Existing installations are preserved unless --adopt-existing is explicitly given.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import sys
import uuid


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "skills"
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store", ".git")


def available_skills() -> dict[str, Path]:
    return {
        path.name: path for path in sorted(SOURCE.iterdir())
        if path.is_dir() and (path / "SKILL.md").is_file() and not path.is_symlink()
    }


def destination_dir(option: str | None) -> Path:
    if option:
        return Path(option).expanduser().resolve()
    env_target = os.environ.get("SKILLS_TARGET_DIR")
    if env_target:
        return Path(env_target).expanduser().resolve()
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
    return (codex_home / "skills").resolve()


def describe_target(path: Path, source: Path, mode: str) -> str:
    if path.is_symlink():
        if path.resolve() == source.resolve() and mode == "link":
            return "current"
        return "different"
    if not path.exists():
        return "new"
    # Never adopt a user-owned directory silently, even if it appears identical.
    return "different"


def atomic_install(source: Path, target: Path, mode: str, adopt: bool) -> str:
    temp = target.parent / f".{target.name}.install-{uuid.uuid4().hex[:10]}"
    backup = None
    if temp.exists() or temp.is_symlink():
        raise RuntimeError(f"Unexpected temporary path already exists: {temp}")
    if mode == "link":
        temp.symlink_to(source.resolve(), target_is_directory=True)
    else:
        shutil.copytree(source, temp, symlinks=False, ignore=IGNORE)
    try:
        if target.exists() or target.is_symlink():
            if not adopt:
                raise RuntimeError(f"Existing installation requires --adopt-existing: {target}")
            backups = target.parent / ".skill-backups"
            backups.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = backups / f"{target.name}-{stamp}-{uuid.uuid4().hex[:6]}"
            target.rename(backup)
        try:
            temp.rename(target)
        except Exception:
            if backup is not None and backup.exists():
                backup.rename(target)
            raise
    finally:
        if temp.is_symlink():
            temp.unlink()
        elif temp.exists():
            shutil.rmtree(temp)
    return f"installed {target} ({mode})" + (f"; previous copy: {backup}" if backup else "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-dir", help="Default: SKILLS_TARGET_DIR or CODEX_HOME/skills")
    parser.add_argument("--mode", choices=("link", "copy"), default="link",
                        help="link: changes follow repository updates; copy: independent snapshot")
    parser.add_argument("--only", nargs="+", metavar="NAME", help="One or more skill names, default all")
    parser.add_argument("--dry-run", action="store_true", help="Inspect changes, do not write")
    parser.add_argument("--adopt-existing", action="store_true",
                        help="Back up pre-existing installations before replacing them")
    args = parser.parse_args()

    skills = available_skills()
    requested = list(dict.fromkeys(args.only or skills.keys()))
    bad = [n for n in requested if n not in skills]
    if bad:
        parser.error(f"Unknown skills {bad}; available: {sorted(skills)}")
    target_dir = destination_dir(args.target_dir)
    if target_dir == SOURCE.resolve() or SOURCE.resolve() in target_dir.parents:
        parser.error("Target must not be inside this repository's skills source directory.")

    plans = []
    conflicts = []
    for name in requested:
        src = skills[name]
        dst = target_dir / name
        state = describe_target(dst, src, args.mode)
        if state == "different" and not args.adopt_existing:
            conflicts.append(str(dst))
        plans.append((name, src, dst, state))
    if conflicts:
        print("REFUSED: existing installations will not be overwritten:", file=sys.stderr)
        for x in conflicts:
            print(f"  - {x}", file=sys.stderr)
        print("Use --adopt-existing to back up originals explicitly, or choose --target-dir.", file=sys.stderr)
        return 2
    for name, _src, dst, state in plans:
        action = "skip" if state == "current" else ("back up + install" if state == "different" else "install")
        print(f"{'[dry-run] ' if args.dry_run else ''}{name}: {action} -> {dst}")
    if args.dry_run:
        return 0
    target_dir.mkdir(parents=True, exist_ok=True)
    for name, src, dst, state in plans:
        if state != "current":
            print(atomic_install(src, dst, args.mode, args.adopt_existing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
