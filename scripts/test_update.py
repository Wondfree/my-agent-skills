#!/usr/bin/env python3
"""Offline update gate regression tests, using only disposable local Git fixtures."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def safe_git_environment(source: dict[str, str], template: Path) -> dict[str, str]:
    """Never inherit caller-controlled Git redirection, config, hook or index settings."""
    clean = {
        key: value for key, value in source.items()
        if not key.startswith("GIT_") and key not in ("SSH_ASKPASS", "SSH_ASKPASS_REQUIRE")
    }
    clean.update({
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ALLOW_PROTOCOL": "file",
        "GIT_LFS_SKIP_SMUDGE": "1",
        "GIT_TEMPLATE_DIR": str(template),
        # A temporary fixture must not execute hooks inherited from its parent.
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "core.hooksPath",
        "GIT_CONFIG_VALUE_0": os.devnull,
    })
    return clean


ENV: dict[str, str] = {}


def run(*args: str, cwd: Path | None = None, expect: int = 0) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        args, cwd=cwd, env=ENV, capture_output=True, text=True, timeout=35, check=False
    )
    if proc.returncode != expect:
        raise AssertionError(
            f"Unexpected exit {proc.returncode} (expected {expect}) for {args}:\n"
            f"stdout={proc.stdout}\nstderr={proc.stderr}"
        )
    return proc


def git(repo: Path, *args: str) -> str:
    return run("git", *args, cwd=repo).stdout.strip()


def commit(repo: Path, title: str) -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-m", title)
    return git(repo, "rev-parse", "HEAD")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="agent instructions update gate ") as folder:
        root = Path(folder)
        template = root / "empty-git-template"
        template.mkdir()
        external_index = root / "do-not-touch-index"
        external_index.write_bytes(b"EXTERNAL INDEX SENTINEL")
        poisoned = dict(os.environ)
        poisoned.update({
            "GIT_INDEX_FILE": str(external_index),
            "GIT_DIR": str(root / "not-a-fixture-repo"),
            "GIT_WORK_TREE": str(root / "not-a-fixture-worktree"),
            "GIT_TEMPLATE_DIR": str(root / "untrusted-template"),
            "GIT_CONFIG_COUNT": "2",
            "GIT_CONFIG_KEY_0": "core.hooksPath",
            "GIT_CONFIG_VALUE_0": str(root / "untrusted-hooks"),
            "GIT_CONFIG_KEY_1": "core.pager",
            "GIT_CONFIG_VALUE_1": "untrusted-command",
        })
        global ENV
        ENV = safe_git_environment(poisoned, template)
        for dangerous in ("GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE"):
            assert dangerous not in ENV
        assert ENV["GIT_CONFIG_COUNT"] == "1"
        assert ENV["GIT_TEMPLATE_DIR"] == str(template)
        assert ENV["GIT_CONFIG_VALUE_0"] == os.devnull
        remote, seed, client = (root / n for n in ("origin.git", "seed", "client"))
        run("git", "init", "--bare", "-b", "main", str(remote))
        run("git", "init", "-b", "main", str(seed))
        git(seed, "config", "user.name", "Isolated Update Test")
        git(seed, "config", "user.email", "fixture@example.invalid")
        scripts = seed / "scripts"
        scripts.mkdir()
        shutil.copy2(ROOT / "scripts" / "update.sh", scripts / "update.sh")
        # The fixture exercises update.sh's validation *gate*, not the validation
        # implementations themselves (those have their own production tests).
        (scripts / "validate_skills.py").write_text("print('fixture validator pass')\n")
        (scripts / "test_install.py").write_text("print('fixture install pass')\n")
        (seed / "rules").mkdir()
        (seed / "rules" / "agent-global.md").write_text("v1 approved global instructions\n")
        (seed / "rules" / "reuse-first.md").write_text("v1 legacy entry\n")
        (seed / "README.md").write_text("baseline\n")
        baseline = commit(seed, "baseline")
        git(seed, "remote", "add", "origin", str(remote))
        git(seed, "push", "-u", "origin", "main")
        run("git", "clone", "--branch", "main", str(remote), str(client))
        assert git(client, "rev-parse", "HEAD") == baseline

        # Status mode has no side effects; a gate flag alone cannot apply.
        status = run("bash", "scripts/update.sh", cwd=client)
        assert "Use --apply" in status.stdout
        misuse = run(
            "bash", "scripts/update.sh", "--approve-global-instructions",
            cwd=client, expect=2
        )
        assert "requires --apply" in misuse.stderr

        # Changes to shared instructions require explicit review.
        (seed / "rules" / "agent-global.md").write_text("v2 new global instructions\n")
        changed_rules = commit(seed, "update global instructions")
        git(seed, "push")
        refused = run("bash", "scripts/update.sh", "--apply", cwd=client, expect=2)
        assert "REFUSED: shared Instructions changed" in refused.stderr
        assert "v2 new global instructions" in refused.stdout
        assert git(client, "rev-parse", "HEAD") == baseline
        assert (client / "rules" / "agent-global.md").read_text() == (
            "v1 approved global instructions\n"
        )
        assert not git(client, "status", "--porcelain")

        # Approval must name a FULL reviewed commit; never just an unbound flag.
        missing_pin = run(
            "bash", "scripts/update.sh", "--apply",
            "--approve-global-instructions", cwd=client, expect=2
        )
        assert "full 40-character commit SHA" in missing_pin.stderr
        assert git(client, "rev-parse", "HEAD") == baseline

        # Simulate the upstream changing after the Human reviewed the first diff.
        (seed / "rules" / "agent-global.md").write_text("v3 different unreviewed global instructions\n")
        changed_since_review = commit(seed, "updated again after review")
        git(seed, "push")
        stale_approval = run(
            "bash", "scripts/update.sh", "--apply",
            "--approve-global-instructions",
            f"--approved-revision={changed_rules}", cwd=client, expect=2
        )
        assert "differs from explicitly reviewed" in stale_approval.stderr
        assert changed_rules in stale_approval.stderr
        assert changed_since_review in stale_approval.stderr
        assert git(client, "rev-parse", "HEAD") == baseline

        approved = run(
            "bash", "scripts/update.sh", "--apply",
            "--approve-global-instructions",
            f"--approved-revision={changed_since_review}", cwd=client
        )
        assert "Updated to" in approved.stdout
        assert git(client, "rev-parse", "HEAD") == changed_since_review
        assert (client / "rules" / "agent-global.md").read_text() == (
            "v3 different unreviewed global instructions\n"
        )

        # Changes to other files may fast-forward without the special rule gate.
        (seed / "README.md").write_text("documentation-only update\n")
        docs_revision = commit(seed, "docs only")
        git(seed, "push")
        run("bash", "scripts/update.sh", "--apply", cwd=client)
        assert git(client, "rev-parse", "HEAD") == docs_revision

        # The currently active legacy global entry must use the same approval gate.
        (seed / "rules" / "reuse-first.md").write_text("v2 legacy entry changed\n")
        legacy_revision = commit(seed, "legacy instructions changed")
        git(seed, "push")
        legacy_block = run("bash", "scripts/update.sh", "--apply", cwd=client, expect=2)
        assert "REFUSED: shared Instructions changed" in legacy_block.stderr
        assert "v2 legacy entry changed" in legacy_block.stdout
        assert git(client, "rev-parse", "HEAD") == docs_revision
        assert (client / "rules" / "reuse-first.md").read_text() == "v1 legacy entry\n"
        run("bash", "scripts/update.sh", "--apply",
            "--approve-global-instructions", f"--approved-revision={legacy_revision}",
            cwd=client)
        assert git(client, "rev-parse", "HEAD") == legacy_revision
        assert (client / "rules" / "reuse-first.md").read_text() == "v2 legacy entry changed\n"

        # Failed candidate validation must not update the current HEAD.
        (scripts / "validate_skills.py").write_text("raise SystemExit(3)\n")
        commit(seed, "invalid candidate")
        git(seed, "push")
        failure = run("bash", "scripts/update.sh", "--apply", cwd=client, expect=3)
        assert git(client, "rev-parse", "HEAD") == legacy_revision
        assert "fixture validator pass" not in failure.stdout
        assert not git(client, "status", "--porcelain")

        # A dirty client must not advance even if the remote is valid.
        (scripts / "validate_skills.py").write_text("print('fixture validator pass')\n")
        valid_revision = commit(seed, "restore valid candidate")
        git(seed, "push")
        (client / "README.md").write_text("UNCOMMITTED LOCAL WORK\n")
        dirty = run("bash", "scripts/update.sh", "--apply", cwd=client, expect=2)
        assert "working tree contains local changes" in dirty.stderr
        assert (client / "README.md").read_text() == "UNCOMMITTED LOCAL WORK\n"
        assert git(client, "rev-parse", "HEAD") == legacy_revision
        git(client, "restore", "--", "README.md")  # temp fixture only
        run("bash", "scripts/update.sh", "--apply", cwd=client)
        assert git(client, "rev-parse", "HEAD") == valid_revision

        # A divergent client must fail, not merge or discard its local commit.
        git(client, "config", "user.name", "Isolated Update Test")
        git(client, "config", "user.email", "fixture@example.invalid")
        (client / "README.md").write_text("client-only commit\n")
        local_revision = commit(client, "local change")
        (seed / "README.md").write_text("remote-only commit\n")
        commit(seed, "remote change")
        git(seed, "push")
        diverged = run("bash", "scripts/update.sh", "--apply", cwd=client, expect=2)
        assert "diverged" in diverged.stderr
        assert git(client, "rev-parse", "HEAD") == local_revision
        assert external_index.read_bytes() == b"EXTERNAL INDEX SENTINEL"

    print(json.dumps({"passed": True, "tested": [
        "read-only status", "flag requires apply", "global change refusal",
        "full SHA required", "stale reviewed SHA rejected", "explicit global approval",
        "legacy rule change refusal", "legacy rule explicit approval",
        "non-global fast-forward", "validation failure", "dirty checkout protection",
        "diverged checkout protection", "Git environment sanitization", "sentinel index unchanged",
        "offline local remote fixture"
    ]}))


if __name__ == "__main__":
    main()
