#!/usr/bin/env python3
"""Isolated offline smoke tests; never mutates real installed Skills."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "scripts" / "install.py"


def execute(*args: str, expect: int = 0) -> subprocess.CompletedProcess:
    call = subprocess.run([sys.executable, str(INSTALL), *args],
                          text=True, capture_output=True)
    if call.returncode != expect:
        raise AssertionError(f"Expected exit {expect} got {call.returncode}: {call.stdout} {call.stderr}")
    return call


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="agent skills test ") as folder:
        root = Path(folder)
        # Git Lifecycle is opt-in, including when the new global rules are requested.
        default_dir = root / "default skills"
        default_preview = execute("--target-dir", str(default_dir), "--dry-run")
        assert "git-lifecycle:" not in default_preview.stdout
        assert not default_dir.exists()
        execute("--target-dir", str(default_dir))
        assert not (default_dir / "git-lifecycle").exists()
        assert (default_dir / "reuse-first").is_symlink()

        combined_skills = root / "combined skills"
        combined_codex = root / "combined codex"
        combined_claude = root / "combined claude"
        combined_options = ("--with-instructions", "--target-dir", str(combined_skills),
                            "--codex-home", str(combined_codex),
                            "--claude-home", str(combined_claude))
        combined_preview = execute(*combined_options, "--dry-run")
        assert "git-lifecycle:" not in combined_preview.stdout
        assert "codex-global:" in combined_preview.stdout
        assert "claude-global:" in combined_preview.stdout
        execute(*combined_options)
        assert not (combined_skills / "git-lifecycle").exists()
        assert (combined_skills / "reuse-first").is_symlink()
        assert (combined_codex / "AGENTS.md").is_symlink()
        assert (combined_claude / "CLAUDE.md").is_symlink()

        explicit_dir = root / "explicit skills"
        explicit_preview = execute("--target-dir", str(explicit_dir),
                                   "--only", "git-lifecycle", "--dry-run")
        assert "git-lifecycle: install" in explicit_preview.stdout
        assert not explicit_dir.exists()
        execute("--target-dir", str(explicit_dir), "--only", "git-lifecycle")
        assert (explicit_dir / "git-lifecycle").is_symlink()
        assert (explicit_dir / "git-lifecycle").resolve() == (
            ROOT / "skills" / "git-lifecycle").resolve()
        # A subsequent default install must not touch this explicitly installed Skill.
        # Verify both the plan and the actual entry identity (not just its target).
        opt_in_entry = explicit_dir / "git-lifecycle"
        before = opt_in_entry.lstat()
        later_default = execute("--target-dir", str(explicit_dir), "--dry-run")
        assert "git-lifecycle:" not in later_default.stdout
        execute("--target-dir", str(explicit_dir))
        after = opt_in_entry.lstat()
        assert opt_in_entry.is_symlink()
        assert opt_in_entry.resolve() == (ROOT / "skills" / "git-lifecycle").resolve()
        assert (before.st_ino, before.st_mtime_ns) == (after.st_ino, after.st_mtime_ns)
        local = root / "user skills"
        source = ROOT / "skills" / "video-to-knowledge"
        execute("--target-dir", str(local), "--only", "video-to-knowledge",
                "--dry-run")
        assert not local.exists(), "dry-run modified disk"
        execute("--target-dir", str(local), "--only", "video-to-knowledge")
        linked = local / "video-to-knowledge"
        assert linked.is_symlink() and linked.resolve() == source.resolve()
        execute("--target-dir", str(local), "--only", "video-to-knowledge")
        other = local / "skill-reviewer"
        other.mkdir()
        (other / "SKILL.md").write_text("USER MODIFIED - preserve me")
        execute("--target-dir", str(local), "--only", "skill-reviewer", expect=2)
        assert (other / "SKILL.md").read_text() == "USER MODIFIED - preserve me"
        execute("--target-dir", str(local), "--only", "skill-reviewer",
                "--adopt-existing")
        assert other.is_symlink()
        backup = list((local / ".skill-backups").glob("skill-reviewer-*"))
        assert len(backup) == 1
        assert (backup[0] / "SKILL.md").read_text() == "USER MODIFIED - preserve me"
        copied_dir = root / "copied skills"
        execute("--target-dir", str(copied_dir), "--mode", "copy",
                "--only", "video-to-knowledge")
        copy = copied_dir / "video-to-knowledge"
        assert copy.is_dir() and not copy.is_symlink()
        assert (copy / "SKILL.md").read_bytes() == (source / "SKILL.md").read_bytes()
        with (copy / "SKILL.md").open("a") as f:
            f.write("\nlocal customization\n")
        execute("--target-dir", str(copied_dir), "--mode", "copy",
                "--only", "video-to-knowledge", expect=2)
        assert "local customization" in (copy / "SKILL.md").read_text()
        execute("--target-dir", str(copied_dir), "--mode", "copy",
                "--only", "video-to-knowledge", "--adopt-existing")
        assert "local customization" not in (copy / "SKILL.md").read_text()
        assert len(list((copied_dir / ".skill-backups").glob("video-to-knowledge-*"))) == 1

        # Instructions opt-in: do not touch Skills unless explicitly requested.
        codex_home = root / "codex home"
        claude_home = root / "claude home"
        options = ("--instructions-only", "--codex-home", str(codex_home),
                   "--claude-home", str(claude_home))
        execute(*options, "--dry-run")
        assert not codex_home.exists() and not claude_home.exists()
        # A symlinked config home must not redirect installation into source Git.
        alias_to_rules = root / "repo rules alias"
        alias_to_rules.symlink_to(ROOT / "rules", target_is_directory=True)
        bad_home = ("--instructions-only", "--codex-home", str(alias_to_rules),
                    "--claude-home", str(claude_home))
        execute(*bad_home, "--dry-run", expect=2)
        assert not (ROOT / "rules" / "AGENTS.md").exists()
        # A future Skill symlink must not redirect a subsequent global write
        # into the Skill *source* during a combined installation.
        future_skills = root / "future skills"
        nested_home = future_skills / "reuse-first"
        combined = ("--with-instructions", "--only", "reuse-first",
                    "--target-dir", str(future_skills),
                    "--codex-home", str(nested_home),
                    "--claude-home", str(claude_home))
        execute(*combined, "--dry-run", expect=2)
        execute(*combined, expect=2)
        execute(*combined, "--adopt-existing", expect=2)
        for escaped_home in (nested_home / "..", nested_home / ".." / "other"):
            escaped = ("--with-instructions", "--only", "reuse-first",
                       "--target-dir", str(future_skills),
                       "--codex-home", str(escaped_home),
                       "--claude-home", str(claude_home))
            execute(*escaped, "--dry-run", expect=2)
            execute(*escaped, expect=2)
            execute(*escaped, "--adopt-existing", expect=2)
        assert not future_skills.exists()
        assert not (ROOT / "skills" / "reuse-first" / "AGENTS.md").exists()
        # Codex override takes priority over AGENTS.md: refuse misleading installs.
        codex_home.mkdir(parents=True)
        override = codex_home / "AGENTS.override.md"
        override.write_text("USER global override")
        execute(*options, "--dry-run", expect=2)
        execute(*options, "--adopt-existing", "--dry-run", expect=2)
        execute(*options, expect=2)
        execute(*options, "--adopt-existing", expect=2)
        blocked_combined = ("--with-instructions", "--only", "reuse-first",
                            "--target-dir", str(future_skills),
                            "--codex-home", str(codex_home),
                            "--claude-home", str(claude_home))
        execute(*blocked_combined, expect=2)
        execute(*blocked_combined, "--adopt-existing", expect=2)
        assert not future_skills.exists()
        assert not (codex_home / "AGENTS.md").exists()
        assert not claude_home.exists()
        assert override.read_text() == "USER global override"
        override.unlink()
        execute(*options)
        instruction_source = ROOT / "rules" / "agent-global.md"
        for target in (codex_home / "AGENTS.md", claude_home / "CLAUDE.md"):
            assert target.is_symlink() and target.resolve() == instruction_source.resolve()
        execute(*options)  # idempotent
        assert not (codex_home / "skills").exists()

        # Legacy links are protected; only explicitly adopted replacements are backed up.
        codex_target = codex_home / "AGENTS.md"
        codex_target.unlink()
        old_rule = ROOT / "rules" / "reuse-first.md"
        codex_target.symlink_to(old_rule)
        claude_target = claude_home / "CLAUDE.md"
        claude_target.unlink()
        claude_target.write_text("PRIVATE user rule - preserve")
        execute(*options, expect=2)
        assert codex_target.resolve() == old_rule.resolve()
        assert claude_target.read_text() == "PRIVATE user rule - preserve"
        execute(*options, "--adopt-existing", "--dry-run")
        assert codex_target.resolve() == old_rule.resolve()
        execute(*options, "--adopt-existing")
        assert codex_target.resolve() == instruction_source.resolve()
        assert claude_target.resolve() == instruction_source.resolve()
        assert len(list((codex_home / ".instruction-backups").glob("AGENTS.md-*"))) == 1
        assert len(list((claude_home / ".instruction-backups").glob("CLAUDE.md-*"))) == 1
        saved_claude = next((claude_home / ".instruction-backups").glob("CLAUDE.md-*"))
        assert saved_claude.read_text() == "PRIVATE user rule - preserve"

        # Copy mode is a snapshot: refresh must be explicit and local edits get backed up.
        copied_codex = root / "copied codex"
        copied_claude = root / "copied claude"
        copied_options = ("--instructions-only", "--mode", "copy",
                          "--codex-home", str(copied_codex),
                          "--claude-home", str(copied_claude))
        execute(*copied_options)
        copied_target = copied_codex / "AGENTS.md"
        assert copied_target.is_file() and not copied_target.is_symlink()
        assert copied_target.read_bytes() == instruction_source.read_bytes()
        execute(*copied_options)  # Identical copies are idempotent, no backups created.
        assert not (copied_codex / ".instruction-backups").exists()
        copied_target.write_text("machine-only change")
        execute(*copied_options, expect=2)
        assert copied_target.read_text() == "machine-only change"
        execute(*copied_options, "--adopt-existing")
        assert copied_target.read_bytes() == instruction_source.read_bytes()
        assert any(p.read_text() == "machine-only change"
                   for p in (copied_codex / ".instruction-backups").glob("AGENTS.md-*"))
    print(json.dumps({"passed": True, "tested": ["dry-run", "symlink", "idempotency",
          "refuse overwrite", "backup on adoption", "copy mode", "local changes preserved",
          "global instructions opt-in", "legacy migration", "instruction backups",
          "instruction copy refresh", "git-lifecycle opt-in default",
          "combined default excludes git-lifecycle", "explicit opt-in installs"]}))


if __name__ == "__main__":
    main()
