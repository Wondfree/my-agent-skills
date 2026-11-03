---
name: git-lifecycle
description: Use when auditing Git branches, worktrees or submodules, planning their cleanup or closeout, or reviewing stale or AI-created Git resources before or after a coding task.
---

# Git Lifecycle

Inspect one repository or an explicit project registry with the bundled read-only checker.

**Phases:** P0 = read-only audit; P1 = optional read-only hooks; P2 = manually approved cleanup; P3 = future scheduled audits (not implemented). **Human** means the user responsible for approving consequential actions.

## Hard rules

- **P0 only reports.** Never automatically merge, delete, prune, or change refs, files, hooks, configuration or scheduled tasks.
- `CLEANUP_READY` is technical evidence for review, not ownership proof or deletion permission. A clean worktree, `codex/` prefix, modification time or missing process does not prove abandonment.
- If cleanup is requested, **read the complete [P2 closeout procedure](references/p2-closeout.md) before planning or acting**. Exact worktree removal and local branch deletion require separate approvals and fresh checks; P0 labels never authorize them.
- Treat reports as snapshots, not locks. Preserve project-local rules and platform-managed worktree ownership boundaries.

## P0 workflow

1. Identify the project root or explicit registry and read project-local `AGENTS.md`. Resolve scripts relative to this `SKILL.md`; never assume an installation directory.
2. Run the checker using the commands below. Default mode reads **local Git state only**.
3. Report `CLEAN`, `CLEANUP_READY`, `ACTIVE` or `NEEDS_DECISION` per repository and branch. Include detached HEAD commits, dirty linked worktrees, submodule gitlink mismatches, staged gitlink changes and incomplete scans. `ACTIVE` can include an **unmerged** checked-out branch: inspect `merged_into_local_base`, HEAD and other evidence.
4. For requested remote verification, use `--verify-remote`. It runs isolated `git ls-remote` without fetching or changing refs. Only unauthenticated HTTPS and literal absolute local/file URLs are supported; SSH/private authenticated HTTPS return `UNAVAILABLE`. Failed or unavailable lookup never proves publication.

The checker isolates Git configuration/environment, disables lazy fetching and replacement objects, and fails closed on unsafe filters, legacy grafts or ref-enumeration warnings. Initialized nested submodules are scanned independently after their filters are checked. See [design and safety boundaries](references/design-v1.md) for details and historical evidence.

## Commands

Requires **Git and Python 3.9+**. Run from this skill's directory, or use an absolute resolved script path. `-B` prevents Python bytecode cache writes.

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

**Exit 0 means the scan completed, not that cleanup is safe or no action is needed.** Exit 1 means per-repository scan failures; exit 2 means invalid input/registry. Automation must inspect `--json` statuses and errors. Reports may contain private local paths; keep them local/private.

## Optional P1 hooks

For hook setup or diagnosis, read [P1 integration and activation gates](references/p1-hook-integration.md). The adapter is included in this source; reference JSON files are inactive examples. Installing the skill does not enable hooks. Deployment and runtime verification are client-specific and require separate authorization. Ordinary P0 audits need no hook setup.

Use `python3 -B scripts/test_hook_bridge.py` for offline synthetic event tests; these do not establish live integration.
