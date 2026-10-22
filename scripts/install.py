#!/usr/bin/env python3
"""Install self-maintained Skills and, when explicitly requested, global Agent Instructions.

Default behavior remains Skills-only. Never silently replace existing user files.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import sys
import uuid

from installer_i18n import Translator, Parser, language_from_args, escape_controls


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "skills"
# A separate Human decision is needed before installing these Skills.
OPT_IN_SKILLS = frozenset({"git-lifecycle"})
GLOBAL_RULE = ROOT / "rules" / "agent-global.md"
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


def instructions_targets(codex_home: str | None, claude_home: str | None) -> list[tuple[str, Path]]:
    codex = Path(codex_home or os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
    claude = Path(claude_home or os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude").expanduser()
    return [
        ("codex-global", (codex / "AGENTS.md").absolute()),
        ("claude-global", (claude / "CLAUDE.md").absolute()),
    ]


def describe_target(path: Path, source: Path, mode: str) -> str:
    if path.is_symlink():
        if path.resolve() == source.resolve() and mode == "link":
            return "current"
        return "different"
    if not path.exists():
        return "new"
    # For global instruction *files*, an identical copy is already installed.
    # Preserve original Skills behavior: do not silently adopt pre-existing directories.
    if mode == "copy" and source.is_file() and path.is_file():
        if path.read_bytes() == source.read_bytes():
            return "current"
    return "different"


def atomic_install(source: Path, target: Path, mode: str, adopt: bool, *, kind: str = "skill", lang: str = "en") -> str:
    t = Translator(lang)
    temp = target.parent / f".{target.name}.install-{uuid.uuid4().hex[:10]}"
    backup = None
    if temp.exists() or temp.is_symlink():
        raise RuntimeError(t("Unexpected temporary path already exists: {temp}", temp=temp))
    if mode == "link":
        temp.symlink_to(source.resolve(), target_is_directory=source.is_dir())
    elif source.is_dir():
        shutil.copytree(source, temp, symlinks=False, ignore=IGNORE)
    else:
        shutil.copy2(source, temp)
    try:
        if target.exists() or target.is_symlink():
            if not adopt:
                raise RuntimeError(t("Existing installation requires --adopt-existing: {target}", target=target))
            backup_dir = ".skill-backups" if kind == "skill" else ".instruction-backups"
            backups = target.parent / backup_dir
            backups.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = backups / f"{target.name}-{stamp}-{uuid.uuid4().hex[:6]}"
            target.rename(backup)
        try:
            temp.rename(target)
        except Exception:
            if backup is not None and (backup.exists() or backup.is_symlink()):
                backup.rename(target)
            raise
    finally:
        if temp.is_symlink() or temp.is_file():
            temp.unlink()
        elif temp.exists():
            shutil.rmtree(temp)
    return t("installed {target} ({mode})", target=target, mode=mode) + (t("; previous entry: {backup}", backup=backup) if backup else "")


def main(argv: list[str] | None = None) -> int:
    lang = language_from_args(argv, default=lambda: "en")
    t = Translator(lang)
    parser = Parser(lang=lang, description=t(__doc__))
    parser.add_argument("--lang", choices=("zh-CN", "en"), help=t("Output language (default: en)"))
    parser.add_argument("--target-dir", help=t("Skills destination: SKILLS_TARGET_DIR or CODEX_HOME/skills"))
    parser.add_argument("--mode", choices=("link", "copy"), default="link",
                        help=t("link: follows checkout updates; copy: requires explicit refresh"))
    parser.add_argument("--only", nargs="+", metavar="NAME",
                        help=t("Explicitly select Skills (including opt-in); default excludes opt-in"))
    parser.add_argument("--with-instructions", action="store_true",
                        help=t("Install Skills and both global instruction entries"))
    parser.add_argument("--instructions-only", action="store_true",
                        help=t("Install only global instruction entries; leave Skills unchanged"))
    parser.add_argument("--codex-home", help=t("Override Codex home for global instructions"))
    parser.add_argument("--claude-home", help=t("Override Claude config home for global instructions"))
    parser.add_argument("--dry-run", action="store_true", help=t("Preview without writing"))
    parser.add_argument("--adopt-existing", action="store_true",
                        help=t("Explicitly back up and replace existing entries"))
    parser.add_argument("--instruction-clients", nargs="+", choices=("codex", "claude"),
                        help=t("Select global instruction clients; default remains both"))
    args = parser.parse_args(argv)
    if args.instruction_clients and not (args.with_instructions or args.instructions_only):
        parser.error(t('--instruction-clients requires Instructions installation'))

    if args.instructions_only and (args.only or args.target_dir):
        parser.error(t('--only and --target-dir configure Skills; neither applies to --instructions-only'))
    if (args.codex_home or args.claude_home) and not (args.with_instructions or args.instructions_only):
        parser.error(t('--codex-home/--claude-home require Instructions installation'))

    plans: list[tuple[str, Path, Path, str, str]] = []
    if not args.instructions_only:
        skills = available_skills()
        requested = list(dict.fromkeys(args.only or (
            name for name in skills if name not in OPT_IN_SKILLS
        )))
        bad = [n for n in requested if n not in skills]
        if bad:
            parser.error(t("Unknown skills {bad}; available: {available}", bad=bad, available=sorted(skills)))
        target_dir = destination_dir(args.target_dir)
        if target_dir == SOURCE.resolve() or SOURCE.resolve() in target_dir.parents:
            parser.error(t("Skills target must not be inside this repository's skills source directory."))
        for name in requested:
            src = skills[name]
            dst = target_dir / name
            plans.append((name, src, dst, describe_target(dst, src, args.mode), "skill"))

    if args.with_instructions or args.instructions_only:
        if not GLOBAL_RULE.is_file():
            parser.error(t("Global rules source is missing: {path}", path=GLOBAL_RULE))
        for name, dst in instructions_targets(args.codex_home, args.claude_home):
            if args.instruction_clients and name.split("-")[0] not in args.instruction_clients:
                continue
            src = GLOBAL_RULE
            # Reject parent traversal before any symlinks are created. A path
            # containing ".." may escape a future Skill link only after the link
            # is installed, even if its normalized path appears harmless now.
            if ".." in dst.parts:
                parser.error(t("{name}: instruction home must not contain '..': {dst}", name=name, dst=dst))
            if name == "codex-global":
                override = dst.parent / "AGENTS.override.md"
                if override.exists() or override.is_symlink():
                    parser.error(
                        t("Codex AGENTS.override.md shadows the managed AGENTS.md: {override}. Inspect and resolve the local override explicitly; it will not be overwritten.", override=override)
                    )
            # Resolve the *parent*, not the entry: an existing global entry can
            # itself be a legacy symlink into this repository and must be migratable.
            canonical_parent = dst.parent.resolve()
            if canonical_parent == ROOT.resolve() or ROOT.resolve() in canonical_parent.parents:
                parser.error(t("Instruction target cannot be inside source repository: {dst}", dst=dst))
            plans.append((name, src, dst, describe_target(dst, src, args.mode), "instruction"))

    # Reject targets nested under a Skill that will be installed as a link.
    # Otherwise that newly created link can redirect the subsequent global
    # Instructions write *into this repository*, after initial path preflight.
    skill_destinations = [
        Path(os.path.normpath(str(dst))) for _name, _src, dst, _state, kind in plans
        if kind == "skill"
    ]
    for name, _src, dst, _state, kind in plans:
        if kind != "instruction":
            continue
        lexical_parent = Path(os.path.normpath(str(dst.parent)))
        canonical_parent = dst.parent.resolve()
        for skill_dst in skill_destinations:
            canonical_skill_dst = skill_dst.parent.resolve() / skill_dst.name
            if (lexical_parent == skill_dst or skill_dst in lexical_parent.parents
                    or canonical_parent == canonical_skill_dst
                    or canonical_skill_dst in canonical_parent.parents):
                parser.error(t("{name}: instruction target is nested in a managed Skill destination: {dst}", name=name, dst=dst))

    # Preflight all targets before any modification. Detect duplicate target paths.
    targets = [dst for _name, _src, dst, _state, _kind in plans]
    if len(set(targets)) != len(targets):
        parser.error(t('Two install entries resolve to the same destination'))
    conflicts = [str(dst) for _name, _src, dst, state, _kind in plans
                 if state == "different" and not args.adopt_existing]
    if conflicts:
        print(t('REFUSED: existing installations will not be overwritten:'), file=sys.stderr)
        for item in conflicts:
            print(f"  - {escape_controls(item)}", file=sys.stderr)
        print(t('Inspect existing entries; use --adopt-existing to back up and replace explicitly.'),
              file=sys.stderr)
        return 2
    for name, _src, dst, state, _kind in plans:
        action = "skip" if state == "current" else ("back up + install" if state == "different" else "install")
        print(f"{t('[dry-run] ') if args.dry_run else ''}{name}: {t(action)} -> {dst}")
    if args.dry_run:
        return 0

    for name, src, dst, state, kind in plans:
        if state != "current":
            dst.parent.mkdir(parents=True, exist_ok=True)
            print(atomic_install(src, dst, args.mode, args.adopt_existing, kind=kind, lang=lang))
    return 0


if __name__ == "__main__":
    sys.exit(main())
