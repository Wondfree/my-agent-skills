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
    print(json.dumps({"passed": True, "tested": ["dry-run", "symlink", "idempotency",
          "refuse overwrite", "backup on adoption", "copy mode", "local changes preserved"]}))


if __name__ == "__main__":
    main()
