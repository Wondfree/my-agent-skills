---
name: git-lifecycle
description: Audit Git branches, worktrees and submodules across individual or registered project repositories; identify unmerged work, stale candidates and unsafe cleanup conditions. Use when reviewing AI-created temporary Git resources or before/after an AI coding task. P0 is read-only; never merge, delete, prune or alter hooks automatically.
---

# Git Lifecycle — P0 inventory

Inspect Git lifecycle resources using the bundled deterministic checker. **P0 only reports**; it does not modify refs, files, hooks, configuration or scheduled tasks. A result of `CLEANUP_READY` is *technical evidence for further review*, not ownership proof or permission to delete.

## Workflow

1. Identify the project root or explicit registry. Check project-local `AGENTS.md` and user authorization before changing anything (although P0 makes no changes).
2. Run the read-only checker. Resolve script paths relative to this `SKILL.md`, never assume a particular home directory or project.
3. Report `CLEAN`, `CLEANUP_READY`, `ACTIVE`, or `NEEDS_DECISION` per repo and branch, including detached HEAD commits in any worktree, unsaved changes and submodules in linked worktrees, staged gitlink changes, submodule gitlink mismatches and incomplete nested scans. Parent status intentionally skips submodule traversal; each initialized child is scanned independently after its filter configuration is checked.
4. Default mode uses **local Git state only**. `--verify-remote` reads the configured origin URL and performs `git ls-remote` outside the repository's Git configuration context; it does not fetch or mutate refs. To prevent execution of configured helper commands, P0 allows only unauthenticated HTTPS or literal absolute local/file URLs. SSH origins and private HTTPS requiring credentials return `UNAVAILABLE`. Lazy fetching and replacement objects are disabled; inherited Askpass commands are stripped, and legacy grafts, configured clean/process filters or ref-enumeration warnings fail closed. A failed or unavailable remote lookup cannot be treated as proof of publication.
5. Do not infer that a checked-out worktree is abandoned, even if clean. Do not infer ownership from a `codex/` prefix or last modification time. Human decisions remain required before merging unrelated commits or removing uncertain resources.
6. If a task needs actual cleanup, stop at the report. The separately gated cleanup workflow is not implemented in P0.

## Commands

Run from this Skill's directory, or use an absolute resolved script path:

```bash
python3 -B scripts/git_lifecycle.py check --repo /absolute/path/to/project
python3 -B scripts/git_lifecycle.py check --repo /path/one --repo /path/two --json
python3 -B scripts/git_lifecycle.py check --repo /path/to/project --verify-remote
python3 -B scripts/git_lifecycle.py check --all --registry /path/to/projects.json
python3 -B scripts/test_git_lifecycle.py
```

Registry format (read-only input, not auto-created):

```json
{"version": 1, "repositories": ["/absolute/path/to/project-one", "/absolute/path/to/project-two"]}
```

Without `--registry`, `--all` reads `~/.config/git-lifecycle/projects.json`. If absent, the check fails clearly; it does **not** scan the entire disk. Explicit `--repo` needs no registry. The checker inspects initialized nested submodules automatically.

The checker exits 0 when scanning completes (even if issues need Human action), 1 on per-repository scan failures, and 2 on invalid input/registry. Use `--json` for machine-readable results. Git metadata may contain private local paths; treat output as local/private evidence.

For P1, the [isolated Hook adapter preview](references/p1-hook-integration.md) and its **inactive** client-specific examples are available for review. This source does not enable any Hooks. Use `python3 -B scripts/test_hook_bridge.py` to test synthetic event delivery without changing live agent configuration.

For follow-on P1–P3, permission gates, future hook integration, and limitations, read [design and safety boundaries](references/design-v1.md).
