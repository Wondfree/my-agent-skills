#!/usr/bin/env python3
"""P1 preview: isolated, non-blocking, read-only lifecycle Hook adapter.

No configuration is installed or modified by this script. The parent process
enforces a total timeout over an isolated worker, with no persistent state.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
from pathlib import Path
import re
import subprocess
import sys

from git_lifecycle import ScanError, git, scan_one

EVENTS = frozenset({"SessionStart", "Stop", "SessionEnd"})
MAX_INPUT = 262_144
INPUT_TOO_LARGE = object()
WORKER_TIMEOUT_SECONDS = 9
INCOMPLETE = "Git Lifecycle inspection incomplete; check Git state manually. No cleanup authorized."


def load_event() -> dict | object | None:
    data = sys.stdin.buffer.read(MAX_INPUT + 1)
    if len(data) > MAX_INPUT:
        return INPUT_TOO_LARGE
    if not data:
        return None
    try:
        obj = json.loads(data)
    except (ValueError, UnicodeError):
        return None
    return obj if isinstance(obj, dict) else None


def safe_label(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._/-]", "_", text)[:80]


def has_checkout_marker(path: Path) -> bool:
    """Distinguish an ordinary non-Git directory from an inaccessible checkout."""
    for item in (path, *path.parents):
        marker = item / ".git"
        if marker.exists() or marker.is_symlink():
            return True
        if (item / "HEAD").is_file() and (item / "objects").is_dir():
            return True
    return False


def get_snapshot(payload: dict) -> str | None:
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd or not Path(cwd).is_absolute():
        return None
    target = Path(cwd)
    if not target.is_dir():
        # Moved/deleted/inaccessible checkout during a session must not
        # masquerade as a clean Stop or an ignorable non-Git session.
        return INCOMPLETE
    try:
        root = Path(git(target, "rev-parse", "--show-toplevel")).resolve()
    except ScanError as exc:
        if "failed or timed out" in str(exc) or has_checkout_marker(target):
            return INCOMPLETE
        return None
    try:
        nodes = scan_one(root, "main", False, set())
    except ScanError:
        return INCOMPLETE
    if not nodes or any(node["scan_errors"] for node in nodes):
        return INCOMPLETE

    problems = sum(node["status"] == "NEEDS_DECISION" for node in nodes)
    dirty = sum(node["dirty_entries"] > 0 for node in nodes)
    dirty += sum((wt.get("dirty_entries") or 0) > 0
                 for node in nodes for wt in node["extra_worktrees"])
    branches = sum(len(node["branches"]) for node in nodes)
    extra = sum(len(node["extra_worktrees"]) for node in nodes)

    main = nodes[0]
    branch = safe_label(main["current_branch"] or "detached")
    summary = (f"Git Lifecycle P1 read-only snapshot: {safe_label(root.name)} "
               f"HEAD={main['head_sha'][:10]}, branch={branch}; "
               f"{len(nodes)} checkout(s), {dirty} dirty worktree(s), "
               f"{branches} other branch(es), {extra} linked worktree(s), "
               f"{problems} checkout(s) NEEDS_DECISION.")
    if problems or extra or branches:
        summary += " Review unmerged/active resources before closing the task."
    else:
        summary += " No resources requiring follow-up were identified in this snapshot."
    return summary + " Never merge, prune or delete without Human approval."


def kill_worker_tree(process: subprocess.Popen) -> None:
    # The Python worker and Git descendants share a fresh process group on
    # POSIX. Killing only the Python process can orphan a blocked Git command.
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        pass
    except OSError:
        process.kill()
    try:
        process.communicate(timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        process.kill()
        try:
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            pass


def read_snapshot_with_budget(event: dict) -> str | None:
    # Never forward session id, transcript, or assistant-message fields.
    # ASCII JSON protects the parent from lone Unicode surrogates.
    payload = json.dumps({"cwd": event.get("cwd")}, ensure_ascii=True).encode("ascii")
    process = None
    try:
        process = subprocess.Popen(
            [sys.executable, "-B", str(Path(__file__).resolve()), "--worker"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=(os.name == "posix"),
        )
        output, _stderr = process.communicate(input=payload, timeout=WORKER_TIMEOUT_SECONDS)
        if process.returncode != 0 or len(output) > 8192:
            return INCOMPLETE
        response = json.loads(output)
        if not isinstance(response, dict):
            return INCOMPLETE
        message = response.get("snapshot")
        if message is not None and (not isinstance(message, str) or len(message) > 2048):
            return INCOMPLETE
        return message
    except (OSError, subprocess.TimeoutExpired, ValueError, UnicodeError, TypeError, AttributeError):
        if process is not None:
            kill_worker_tree(process)
        return INCOMPLETE


def render(client: str, event: str, snapshot: str | None) -> dict:
    if snapshot is None:
        return {}
    if event == "SessionStart":
        return {"hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": snapshot +
            " This is an initial context snapshot, not a persistent task baseline."}}
    if event == "Stop":
        # Stop marks the end of a turn, not the completion of a task.
        if "No resources requiring follow-up" in snapshot:
            return {}
        # An advisory systemMessage never requests blocking or continuation.
        return {"systemMessage": snapshot}
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", choices=("codex", "claude"))
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.worker and not args.client:
        parser.error("--client is required for Hook mode")
    event = load_event()

    if args.worker:
        try:
            snapshot = get_snapshot(event) if isinstance(event, dict) else INCOMPLETE
        except (OSError, RuntimeError, ValueError, KeyError, TypeError, RecursionError):
            snapshot = INCOMPLETE
        print(json.dumps({"snapshot": snapshot}, ensure_ascii=False))
        return 0

    if event is INPUT_TOO_LARGE:
        # Legitimate Stop payloads may contain a huge last_assistant_message.
        # Fail closed without reading or echoing its contents.
        print(json.dumps({"systemMessage": INCOMPLETE}))
        return 0
    name = event.get("hook_event_name") if isinstance(event, dict) else None
    if not isinstance(name, str) or name not in EVENTS or name == "SessionEnd":
        print("{}")
        return 0
    snapshot = read_snapshot_with_budget(event)
    print(json.dumps(render(args.client, name, snapshot),
                     ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
