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
5. Do not infer that a checked-out worktree is abandoned, even if clean. Do not infer ownership from a `codex/` prefix or last modification time. Human decisions remain required before merging unrelated commits or removing uncertain resources. `ACTIVE` can describe a checked-out **unmerged** branch: inspect `merged_into_local_base`, HEAD and other evidence, not just status.
6. P0 never cleans anything. If cleanup is requested, use the **separately Human-gated manual P2 checklist below**; do not treat a P0 label as clearance to execute.

## P2 — Human-gated manual closeout (no cleanup executor)

Reuse the P0 report, the installed `finishing-a-development-branch` Skill's **verify → options → Human choice** structure, and Git's native commands. This section is a **procedure**, not automatic permission or an implemented P2 CLI. Do **not** blindly reuse that Skill's `git pull`, `git worktree prune`, forced-discard steps, or directory-name-only ownership rule. No Task ID/database is mandatory.

1. **Plan only first.** Record the exact repository root and Git common-dir identity; requested linked Worktree's canonical path, branch or Detached HEAD, current HEAD SHA, chosen **retained** base/ref and its SHA, registered Worktree list, lock/prunable indicators and any submodule state. Distinguish evidence from Human's statement that a workspace is no longer needed. A clean tree or a missing process does **not** prove that another Agent will not resume.
2. **Revalidate content, not only the status label.** Run P0 for the exact repo and check per-branch `merged_into_local_base`, per-Worktree `detached_head_contained_in_local_base`, all dirty entries, scan errors and nested submodules. P0's ordinary dirty count excludes ignored files **and may miss index-hidden tracked changes**. Before any Worktree removal, independently check (a) ignored/untracked/tracked entries and (b) index `assume-unchanged` / `skip-worktree` flags. Reuse the **identical sanitized Git invocation context** in `scripts/git_lifecycle.py` (`safe_git_environment()`, `git_command()`, `assert_no_external_filters()`) for the exact Worktree; **never invoke these extra checks as bare Git commands** that re-enable inherited `GIT_*` variables, system/global config, filters or fsmonitor. Within that context inspect `status --porcelain=v1 --untracked-files=all --ignored --ignore-submodules=all` and `ls-files -t -v -z`; any lowercase index tag (`assume-unchanged`) or `S` (`skip-worktree`), any status output (including ignored-only `!!`), incomplete inspection, index parsing error or path/common-dir mismatch **blocks routine removal**. If an equally isolated, reviewed invocation is not available, stop rather than run unsafe ad hoc commands. Use P0's independently scanned submodule results; disposal of blocked content needs a **separate Human decision** outside this routine.
3. **Separate approvals.** Ask Human to approve the **exact Worktree removal** and **exact local branch deletion** separately; push, remote branch deletion, merge and discarded changes always require their own authorization. Confirm the workspace is not needed by another task/Agent; this is a Human responsibility assertion, *not* a property proved by `ps`. Do not remove platform-managed Codex/Claude worktrees without clear permission from their owning lifecycle workflow. A `locked`, `prunable`, missing, changing or uncertain Worktree is **not** routine-removable; never auto-unlock or prune.
4. **Worktree removal only:** the path must be a registered, non-primary, clean, unlocked linked Worktree; verify its HEAD/branch and common-dir against the approved snapshot immediately before acting. For a named branch, keep that branch/ref as a durable local pointer even if its commits are unmerged (warn when unpublished); Worktree removal **does not** authorize branch removal. A Detached HEAD with commits not reachable from a specifically approved *retained* ref must be preserved, despite Git's willingness to remove it. When all conditions and the specific Human approval hold, use only `git worktree remove "<exact-path>"` **without** `--force`; then re-read Git state. Do not call it from inside the Worktree being removed.
5. **Local branch deletion only:** no Worktree may have it checked out; the exact approved branch must still point to the same commit; that commit must be contained in the specifically approved **local base and live verified remote retained ref**. Check ancestry directly; `git branch -d` may consult an upstream other than the approved base. P0's `--verify-remote` does **not** verify authenticated SSH/private remotes: `UNAVAILABLE` is a stop, unless a separately authorized trusted, read-only remote verification was completed. Then, and only with branch-specific Human approval, use `git branch -d -- "<exact-branch>"` and re-read the result. No `-D`, `push --delete`, reset or force.
6. **Race/interruption rule.** A scan or plan is a snapshot, not a lock. Before **each** operation, independently recheck all relevant refs, HEAD, path/common-dir, locks, changes (including ignored/index-hidden content), submodules and allowed remote evidence; if anything differs, stop and ask again. Native Git commands are not a transaction and cannot eliminate time-of-check/time-of-use races. If Worktree removal and branch deletion were **both explicitly approved**, success of the first may be followed by the second **only after its full independent recheck**; success is not a failure. If either command fails, approval is missing, or the sequence is interrupted, **stop, report precisely what completed and what did not, then replan**—never auto-retry, unlock, prune, force or rollback. Preserve audit evidence and actual Human decision in the project's existing record; do not invent a cross-project task registry.

**Observed in 2026-10-21 isolated test conversations on Apple Git 2.39.5 (not independently reproduced from this repository):** a non-forced `git worktree remove` deleted an ignored-only file and could remove a clean Detached HEAD whose commit was not merged. `git branch -d` deleted a locally merged but not remotely published branch. A separate fixture showed that `assume-unchanged` and `skip-worktree` can hide local changes from ordinary `status` while `ls-files -t -v -z` exposes lowercase `h` and `S` tags. Dirty tracked/untracked and locked Worktrees were rejected. These observations justify *independent preflight evidence*; they do **not** authorize cleanup or prove the same behavior on every Git version.

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
