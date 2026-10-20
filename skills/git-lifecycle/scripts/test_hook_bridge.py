#!/usr/bin/env python3
"""Disposable-repository tests for the uninstalled P1 hook bridge."""
from __future__ import annotations

import json
import os
import importlib
import time
from unittest.mock import patch
from pathlib import Path
import subprocess
import sys
import tempfile

BRIDGE = Path(__file__).with_name("hook_bridge.py")


def environment() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GIT_") and k not in
           {"SSH_ASKPASS", "SSH_ASKPASS_REQUIRE", "GCM_INTERACTIVE"}}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_SYSTEM=os.devnull,
               GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0")
    return env


def git(repo: Path, *arguments: str) -> str:
    cmd = ["git", "-c", "core.hooksPath=/dev/null",
           "-c", "commit.gpgSign=false", "-C", str(repo), *arguments]
    p = subprocess.run(cmd, capture_output=True, text=True, env=environment(), timeout=15)
    if p.returncode:
        raise AssertionError(f"Fixture Git failure: {arguments} ({p.returncode})")
    return p.stdout.strip()


def invoke(client: str, payload, expected_rc: int = 0):
    data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    p = subprocess.run([sys.executable, "-B", str(BRIDGE), "--client", client],
                       input=data, capture_output=True, timeout=25, env=environment())
    assert p.returncode == expected_rc, p.stderr.decode(errors="replace")
    assert not p.stderr, p.stderr
    return json.loads(p.stdout)


def main():
    with tempfile.TemporaryDirectory(prefix="git-lifecycle-hook-p1-") as folder:
        repo = Path(folder) / "project with spaces"
        repo.mkdir()
        git(repo, "init", "-b", "main")
        git(repo, "config", "user.name", "Lifecycle Fixture")
        git(repo, "config", "user.email", "fixture@example.invalid")
        (repo / "README.md").write_text("base\n")
        git(repo, "add", "README.md")
        git(repo, "commit", "-m", "base")
        original_head = git(repo, "rev-parse", "HEAD")
        original_state = git(repo, "status", "--porcelain=v1")
        original_worktrees = git(repo, "worktree", "list", "--porcelain")

        for client in ("codex", "claude"):
            event = {"hook_event_name": "SessionStart", "source": "startup",
                     "cwd": str(repo), "session_id": "private-secret",
                     "transcript_path": "/do/not/read/secret.jsonl"}
            start = invoke(client, event)
            assert start["hookSpecificOutput"]["hookEventName"] == "SessionStart"
            message = start["hookSpecificOutput"]["additionalContext"]
            assert repo.name.replace(" ", "_") in message and original_head[:10] in message
            assert "initial context snapshot" in message and "No cleanup authorized" not in message
            assert str(repo) not in message and "private-secret" not in message
            assert "secret.jsonl" not in message
            stop = invoke(client, {**event, "hook_event_name": "Stop",
                                   "last_assistant_message": "do not echo this"})
            assert stop == {}, "Clean workspaces should not generate a Stop warning"
            assert invoke(client, {**event, "hook_event_name": "SessionEnd",
                                   "reason": "other"}) == {}
            assert invoke(client, {**event, "hook_event_name": "PreToolUse"}) == {}
            assert invoke(client, {"hook_event_name": "SessionStart",
                                   "cwd": "relative"}) == {}
            assert "incomplete" in invoke(client, {"hook_event_name": "SessionStart",
                                   "cwd": str(Path(folder) / "missing")})["hookSpecificOutput"]["additionalContext"]

        assert invoke("codex", b"invalid json") == {}
        assert invoke("codex", b"\x00") == {}
        assert "incomplete" in invoke("codex", b" " * 262145)["systemMessage"]
        big_stop = invoke("claude", {"hook_event_name":"Stop", "cwd":str(repo),
                                      "last_assistant_message": "text" * 70000})
        assert "incomplete" in big_stop["systemMessage"]
        assert invoke("codex", ["not", "object"]) == {}
        assert invoke("codex", {"hook_event_name": []}) == {}
        assert invoke("claude", {"hook_event_name": {}}) == {}
        # A valid JSON string may contain an unpaired UTF-16 surrogate.
        # Such input must never crash the hook before it emits valid JSON.
        surrogate = invoke("codex", {"hook_event_name": "Stop",
                                      "cwd": "/tmp/\ud800"})
        assert isinstance(surrogate, dict)

        # Regression probes for bounded worker execution and accurate counts.
        sys.path.insert(0, str(BRIDGE.parent))
        bridge = importlib.import_module("hook_bridge")
        # The parent enforces one deadline over the worker AND its spawned Git.
        # A temporary fake Git binary simulates a stuck descendant in the same
        # process group. On macOS/Linux timeout must kill that descendant.
        stub_dir = Path(folder) / "fake-bin"
        stub_dir.mkdir()
        pidfile = Path(folder) / "stuck-git.pid"
        stub = stub_dir / "git"
        stub.write_text('#!/bin/sh\necho "$$" > "$HOOK_TEST_PIDFILE"\nexec /bin/sleep 30\n')
        stub.chmod(0o755)
        start_time = time.monotonic()
        with patch.object(bridge, "WORKER_TIMEOUT_SECONDS", 2.0):
            with patch.dict(os.environ, {
                "PATH": str(stub_dir) + os.pathsep + os.environ.get("PATH", ""),
                "HOOK_TEST_PIDFILE": str(pidfile),
            }):
                assert bridge.read_snapshot_with_budget({"cwd": str(repo)}) == bridge.INCOMPLETE
        assert time.monotonic() - start_time < 7
        assert pidfile.exists(), "Fixture Git descendant did not start"
        if os.name == "posix":
            ps = subprocess.run(["/bin/ps", "-p", pidfile.read_text().strip(),
                                 "-o", "stat="], capture_output=True, text=True)
            assert not ps.stdout.strip() or ps.stdout.lstrip().startswith("Z"), (
                "Timed-out Git descendant was still running: " + ps.stdout)
        with patch.object(bridge, "git",
                          side_effect=bridge.ScanError("Git invocation failed or timed out")):
            assert bridge.get_snapshot({"cwd": str(repo)}) == bridge.INCOMPLETE
        fake = {
            "path": str(repo), "status": "NEEDS_DECISION", "dirty_entries": 0,
            "branches": [], "extra_worktrees": [
                {"dirty_entries": 1, "status": "NEEDS_DECISION"}],
            "scan_errors": [], "current_branch": "main", "head_sha": "a" * 40}
        with patch.object(bridge, "git", return_value=str(repo)):
            with patch.object(bridge, "scan_one", return_value=[fake]):
                summary = bridge.get_snapshot({"cwd": str(repo)})
        assert "1 dirty worktree(s)" in summary

        # Reference configs must remain inactive, valid, additive examples.
        for client, filename in (
            ("codex", "codex-hooks.example.json"),
            ("claude", "claude-hooks.fragment.example.json"),
        ):
            template = json.loads((BRIDGE.parent.parent / "references" / filename).read_text())
            assert set(template["hooks"]) == {"SessionStart", "Stop"}
            for event_name, groups in template["hooks"].items():
                assert groups and len(groups) == 1
                handler = groups[0]["hooks"][0]
                assert f"--client {client}" in handler["command"]
                assert handler["timeout"] <= 15
                assert "hook_bridge.py" in handler["command"]
                assert handler["command"].startswith("python3 -B ")

        # Danger is reported, never acted on or classified as task completion.
        git(repo, "switch", "-c", "codex/not-merged")
        (repo / "new.txt").write_text("unsaved")
        git(repo, "add", "new.txt")
        git(repo, "commit", "-m", "unmerged")
        git(repo, "switch", "main")
        (repo / "precious.txt").write_text("preserve me")
        risk = invoke("claude", {"hook_event_name": "Stop", "cwd": str(repo)})
        assert risk.get("decision") is None
        assert "NEEDS_DECISION" in risk["systemMessage"]
        assert "Review unmerged/active resources" in risk["systemMessage"]
        assert (repo / "precious.txt").read_text() == "preserve me"

        # Not a repository is a safe observation, not a hook failure.
        other = invoke("codex", {"hook_event_name": "Stop", "cwd": folder})
        assert other == {}, "Non-Git directories should be ignored"

        # The bridge has not changed any repository metadata.
        assert git(repo, "rev-parse", "main") == original_head
        assert git(repo, "worktree", "list", "--porcelain") == original_worktrees
        assert original_state == ""
        assert git(repo, "status", "--porcelain=v1") == "?? precious.txt"

    print(json.dumps({"passed": True, "cases": [
        "both clients start/stop/end", "session fields not leaked",
        "non-blocking outputs", "unsupported event", "missing/relative cwd",
        "malformed/large input", "unmerged branch and dirty files protected",
        "non-repo failure isolation", "no repository mutation",
        "inactive configuration examples validated",
        "malformed event names", "bounded worker timeouts",
        "discovery error warning", "linked worktree dirty count",
        "hook commands disable bytecode writes",
        "surrogate-safe worker serialization",
        "oversized valid Stop warning", "missing absolute cwd warning",
        "worker timeout terminates Git descendants",
        "no-op SessionEnd hooks excluded"]}))


if __name__ == "__main__":
    main()
