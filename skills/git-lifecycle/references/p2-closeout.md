# P2 — Manual closeout after explicit approval

Read this entire procedure before planning or performing requested cleanup. It provides no automatic permission and no cleanup executor. **Human** means the user responsible for approving consequential actions. Follow project-local rules and platform lifecycle permissions.

Reuse the P0 report and native Git commands. The `finishing-a-development-branch` skill is **optional**: if available, borrow only its **verify → options → human choice** structure. If absent, follow the complete steps below directly; no installation is required. Its `git pull`, `git worktree prune`, forced-discard steps and directory-name-only ownership rule do not override these gates. No task ID or database is mandatory.

## 1. Record the proposed targets

Plan only first. Record:

- Exact repository root and Git common-dir identity.
- Requested linked worktree's canonical path, branch or detached HEAD, and current HEAD SHA.
- Specifically chosen **retained** base/ref and its SHA.
- Registered worktree list, lock/prunable indicators and submodule state.

Separate technical evidence from the human assertion that the workspace is no longer needed. A clean tree or missing process does not prove another agent will not resume.

## 2. Inspect all potentially lost content

Run P0 for the exact repository. Check `merged_into_local_base`, `detached_head_contained_in_local_base`, dirty entries, scan errors and nested submodules. Incomplete or failed inspection blocks routine cleanup.

**P0's ordinary dirty count excludes ignored files and may miss index-hidden tracked changes.** Before removing a worktree, independently inspect tracked, untracked and ignored entries, plus index flags:

1. Reuse the identical sanitized Git context from `../scripts/git_lifecycle.py`: `safe_git_environment()`, `git_command()` and `assert_no_external_filters()` for the exact worktree. **Never run the following as bare Git commands** that restore inherited `GIT_*` variables, system/global configuration, filters or fsmonitor. If an equally isolated, reviewed invocation is unavailable, stop.
2. Within that context, inspect `status --porcelain=v1 --untracked-files=all --ignored --ignore-submodules=all` and `ls-files -t -v -z`.
3. Any status output, including ignored-only `!!`, any lowercase index tag (`assume-unchanged`) or `S` (`skip-worktree`), incomplete inspection, index parsing error or path/common-dir mismatch **blocks routine removal**. Do not clear index flags or exempt generated files, caches or symlinks to make the check pass.
4. Use P0's independently scanned submodule results. Preserving or discarding blocked content requires a separate human decision outside this routine.

## 3. Obtain separate approvals

- Obtain approval for the **exact worktree removal** and **exact local branch deletion** separately. Push, remote branch deletion, merge and discarded changes each require their own authorization.
- Confirm with the human that no other task or agent needs the workspace. This is a responsibility assertion, not something proved by `ps`.
- Do not remove Codex/Claude platform-managed worktrees without clear permission from their owning lifecycle workflow.
- A locked, prunable, missing, changing or uncertain worktree is not routine-removable. Never automatically unlock or prune it.

## 4. Remove only the approved worktree

The target must be a registered, non-primary, clean, unlocked linked worktree. Immediately before acting, verify its HEAD, branch and common-dir against the approved snapshot, and perform the full recheck in step 6.

- For a named branch, **retain the branch/ref** as a durable local pointer even if its commits are unmerged; warn when unpublished. Worktree removal does not authorize branch deletion.
- For detached HEAD, preserve the worktree unless its commits are reachable from a specifically approved **retained ref**. Git accepting removal is insufficient evidence.

Only after all checks and worktree-specific approval, run `git worktree remove "<exact-path>"` **without `--force`**, from outside the worktree being removed. Then re-read Git state.

## 5. Delete only the approved local branch

Independently verify all of the following:

- No worktree has the branch checked out.
- The exact approved branch still points to the approved commit.
- The commit is contained in the specifically approved **local base and live verified remote retained ref**.

Check ancestry directly: `git branch -d` may consult a different upstream. A local `origin/main`, an existing remote branch or a past push is insufficient proof of current remote retention. P0 `--verify-remote` does not verify authenticated SSH/private HTTPS: `UNAVAILABLE` means stop unless separately authorized, trusted read-only verification has completed.

After branch-specific approval and the full recheck in step 6, use only `git branch -d -- "<exact-branch>"` and re-read the result. No `-D`, `push --delete`, reset or force.

## 6. Recheck each action and handle interruptions

A scan is a snapshot, not a lock. **Immediately before each operation**, independently recheck:

- Relevant refs, HEAD and approved retained refs.
- Canonical path, common-dir, registration and locks.
- Tracked, untracked, ignored and index-hidden content, plus submodules.
- Required live remote evidence and target ownership/use assertions.

If anything differs from the approved snapshot, stop and obtain a renewed decision. Native Git commands are not a transaction and cannot eliminate time-of-check/time-of-use races.

When both operations were explicitly approved, successful worktree removal may be followed by branch deletion **only after its full independent recheck**. If either command fails, approval is missing or the sequence is interrupted, stop, report exactly what completed and what did not, then replan. Never automatically retry, unlock, prune, force, reset, clean or roll back.

Save the checks, actual human approvals, outcomes and final Git state in the project's existing agreed record. Do not invent a cross-project registry.

## Historical evidence

The [design record](design-v1.md#历史演练记录与证据局限) preserves observations reported from 2026-10-21 isolated conversations. Raw output was not archived here; those observations are not independently reproducible from this repository and do not establish behavior on every Git version. They do not authorize cleanup or replace the checks above.
