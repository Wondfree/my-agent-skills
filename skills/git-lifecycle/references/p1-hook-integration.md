# Git Lifecycle P1 — Isolated Hook Adapter / Activation Gate

Status: **implementation preview in isolated Worktree only; NOT ENABLED**. This document does not approve edits to user-level Codex or Claude configuration, project rules, remote repositories, or installed Skills links.

## Reuse-First and authority

Continue reusing P0 `scripts/git_lifecycle.py` (Git-native read-only inventory). Both Codex and Claude Code support `SessionStart`, `Stop`, and `SessionEnd` command hooks; the inactive P1 examples deliberately configure **only SessionStart and Stop** because SessionEnd cannot deliver any actionable output. Use one adapter instead of two independent hook implementations. Codex and Claude use slightly different hook policies and trust behavior; do not assume their configurations can be overwritten or shared wholesale.

Authoritative documentation:
- https://developers.openai.com/codex/hooks
- https://code.claude.com/docs/en/hooks

## Scope implemented here

`../scripts/hook_bridge.py` consumes bounded hook JSON on stdin. It reads `cwd`, `hook_event_name`, and nothing from the transcript or latest assistant message. It resolves the checkout via the existing sanitized P0 Git interface and scans **offline** in a separate Python worker with a 9-second total deadline (hook examples use a 15-second budget). On POSIX the worker starts in its own process group and the Hook kills that entire group on timeout, preventing orphan Git commands. A worker timeout or failed discovery produces a conservative incomplete-check message rather than a silent success. It does not fetch, write a state file, record task ownership, change refs or worktrees, make external calls, or send notifications. All outputs are bounded summaries without absolute paths or session IDs. Example Hook commands use `python3 -B` so the linked Skill source does not receive bytecode cache writes.

| Event | Behavior | Limitation |
|---|---|---|
| `SessionStart` (`startup` / `resume`) | Emit read-only HEAD/branch/count snapshot to the agent's context | Context snapshot, **not** a durable session baseline; no cross-session comparison |
| `Stop` | Rescan. Emit advisory `systemMessage` only for risks/incomplete inspection; empty JSON if no action required | Runs when a turn stops; **does not mean the task is complete**, never blocks or forces continuation |
| `SessionEnd` | No Hook registered in either example; direct adapter invocation returns `{}` | No actionable context or durable report can be delivered by this no-op; Codex also limits this event to 3 seconds |

Non-Git directories, malformed events, and unrelated hook events produce `{}`. Oversized input events and absolute working directories that have become unavailable emit a conservative incomplete warning. An identified repository that cannot be fully scanned yields a conservative warning. Errors never approve cleanup.

## Inactive examples

- `codex-hooks.example.json` — **illustrative**, not installed; do not overwrite current `~/.codex/config.toml` or hooks source. Codex user-level hooks may require explicit trust/review.
- `claude-hooks.fragment.example.json` — **additive fragment**, never a replacement for `~/.claude/settings.json`. Existing `cc-status` event handlers must remain intact.

Both examples run commands from currently installed Git Lifecycle Skills symlinks, **which still point to P0 until a separately approved merge/update**. They are deliberately stored under `references/`, where no runtime discovers them as active Hook definitions. The current production configuration should be inspected again immediately before any activation.

Tests (offline, temporary fixture):

```sh
python3 -B skills/git-lifecycle/scripts/test_hook_bridge.py
python3 -B skills/git-lifecycle/scripts/test_git_lifecycle.py
python3 -B scripts/validate_skills.py
```

## Required separate activation gate

1. Obtain independent Review of adapter, test behavior, event contracts and JSON examples; resolve findings. Recheck source and current Git/worktree statuses.
2. Approve merging the isolated P1 branch and updating the installed Skill source. Approval to implement **does not authorize merging, committing or pushing**.
3. Compare existing Codex hook configuration (including existing `hooks.state`/other TOML data) and Claude Code `cc-status` handlers before any additive install. Back up original bytes and record checksums under a separately approved plan; never overwrite or remove other handlers.
4. Review exact per-client Hook diffs, Hook trust, timeouts and the absence of hooks in cloud/runtime modes that do not support them.
5. Validate Saved → Loaded → Triggered → Behavior in fresh Codex and Claude sessions, including a non-Git session, a clean fixture, and a dirty/linked-worktree fixture. Runtime Hook coverage cannot be inferred from standalone CLI testing.
6. Rollback means reverting **only the exact newly added Hook handlers** after checking configuration has not changed concurrently. Preserve existing configuration, backups, links, and project data.

**Deferred**: durable baseline persistence, task identity / ownership metadata, conflict-safe session registry, retrospective sessions/abrupt termination audits, human notifications, and all merge/remove/cleanup actions. These need a new design/review and explicit Human approval. Existing project-specific AGENTS/CLAUDE rules remain authoritative for scope and decision gates.

## Acceptance criteria (this stage only)

- New P1 code remains isolated in `codex/git-lifecycle-p1`; main, all live Agent configs and other projects unchanged.
- Both clients' simulated JSON events parse correctly and do not block or disclose private transcript/session fields.
- Existing P0 behavior is unchanged and the temporary Git fixtures remain disposable.
- No claim of actual Hook runtime integration or persistent task tracking before separately approved live activation.
