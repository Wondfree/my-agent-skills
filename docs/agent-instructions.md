# Agent Instructions — Bootstrap, Update and Verification (P1)

## Ownership and scope

- `rules/agent-global.md` is the versioned SSOT for short **L0+L1** global instructions used by both Codex and Claude Code. It contains portable rules, not secrets, user profiles, or a directory-specific project state.
- `skills/reuse-first/SKILL.md` and other Skills keep detailed on-demand workflows. Skills do not supersede Human approval or project rules.
- Project `AGENTS.md` (and optional Claude `CLAUDE.md` bridge) remains independently owned by that project's Git repository. **P1 does not rewrite any project rules.**
- `rules/reuse-first.md` is temporarily retained as a **legacy global entry** while existing symlinks on older installations still point to it. Do not maintain new shared policy in this file. Remove or replace this compatibility path only after every affected installation has explicitly migrated and passed behavioral checks.

## First-time setup (macOS / Linux)

Prerequisites: Git, Python 3.9+, installed Codex / Claude Code as needed.

1. Clone your private `my-agent-skills` repository to **any** directory. Do not use an assumed Mac-specific path.
2. Inspect the source rules and installed/local entries.
3. Preview, then explicitly install both Skills and the global rules:

```sh
python3 scripts/validate_skills.py
python3 scripts/install.py --with-instructions --dry-run
python3 scripts/install.py --with-instructions
```

To install **only** the global entries, without changing Skills:

```sh
python3 scripts/install.py --instructions-only --dry-run
python3 scripts/install.py --instructions-only
```

The installer uses `CODEX_HOME` or the current user's `~/.codex`, and `CLAUDE_CONFIG_DIR` or `~/.claude`; explicit `--codex-home` and `--claude-home` overrides are available for isolated tests and nonstandard installations.

The two managed entries are:

- Codex: `AGENTS.md` inside Codex home.
- Claude Code: `CLAUDE.md` inside Claude config home.

Each points to the *same file* `rules/agent-global.md` in the local checkout. Do not copy the rule body into two independently maintained files.

**Important:** If Codex has an `AGENTS.override.md` in its global config directory, Codex may load it instead of `AGENTS.md`. The installer intentionally refuses an Instructions installation when that override exists, even with `--adopt-existing`; the user must inspect and resolve the existing override independently. Also, combined Skills + Instructions installation rejects a global target nested under a managed Skill destination, and any Instructions home containing `..` path traversal, to prevent a newly installed symlink redirecting writes into this repository.

## Safe migration from an old installation

A current entry can already point to `rules/reuse-first.md` or contain locally customized content. The installer **must refuse** to overwrite it without explicit adoption. Follow this sequence:

1. Read the existing entry and decide whether any machine-local content needs to remain separate. Keep credentials and private data outside the shared repo.
2. Preview migration with `python3 scripts/install.py --instructions-only --adopt-existing --dry-run`.
3. Only after Human approval, run `python3 scripts/install.py --instructions-only --adopt-existing`.
4. Inspect original entry backups at `~/.codex/.instruction-backups/` and `~/.claude/.instruction-backups/` (or the corresponding override homes).
5. Verify saved paths/content **and** start fresh Codex and Claude Code sessions to verify load and actual triggered behavior.

The existing source file remains available until the migration and verification are complete. Nothing automatically rewrites the old global path. **Never use the installer's adoption flag solely to silence an unexpected conflict.**

## Update safety

The existing `scripts/update.sh` checks Git state; it refuses dirty or diverged branches and validates incoming content before a fast-forward. If the incoming revision changes `rules/agent-global.md` **or the still-active legacy** `rules/reuse-first.md`, `--apply` shows the diff and its **full commit SHA**, then refuses to update unless explicit approval is bound to that exact SHA. The offline `python3 -B scripts/test_update.py` regression test (also run in CI) covers both rule paths, stale approval, environment isolation and safe failures.

```sh
./scripts/update.sh                 # Local status; no fetch
./scripts/update.sh --apply         # Fetch and show candidate; refuse unapproved rule changes
# After independently reviewing the FULL commit SHA and exact changes:
./scripts/update.sh --apply --approve-global-instructions --approved-revision=FULL_40_CHARACTER_SHA
```

If the upstream changes between review and approval, the expected SHA no longer matches and the update is refused. The fast-forward applies the exact validated commit rather than a mutable upstream branch reference. Do not approve merely because an install/update script suggested a SHA; the Human must review it. This additional flag is not permission to overwrite local project rules, commit, push, or run unrelated tasks. Link-mode entry content follows the checkout revision after an approved Git update; copy-mode entries require an explicit reinstall with `--mode copy --adopt-existing` after inspecting local modifications.

A checkout with multiple Git worktrees must be updated carefully: the new revision only affects the checkout that moved. **Do not point a production global entry to an unreviewed development worktree.**

## Rollback

- Before changing an active entry, identify and preserve its old target and backed-up file/symlink.
- If installation failed partway through, inspect **both** agents' entries and per-target backups; do not assume all-or-nothing success.
- To undo an entry migration, first verify the replacement is still the expected managed entry, then restore the original saved entry from `.instruction-backups` through an explicitly authorized operation. Do not overwrite a subsequently modified user file.
- To revert the global *content*, return the shared checkout to an approved Git revision using a non-destructive, reviewed Git operation. Do not use `git reset --hard` to discard user work.
- After rollback, repeat Saved → Loaded → Triggered → Behavior validation in new sessions.

## Verification matrix

| Check | Evidence |
| --- | --- |
| Saved | source file exists, Git revision recorded, target links/copies match expected bytes |
| Loaded | new Codex and Claude sessions demonstrate their own global and project rule discovery |
| Triggered | representative Reuse-First and Human Gate prompts trigger appropriate rules |
| Behavior PASS | AI actually performs proportional comparison, protects dirty trees, and honors project gates |
| Negative | ordinary bug fix does not trigger broad survey; unknown local config is not overwritten |
| Migration | legacy link and custom file are refused by default and backed up when explicitly adopted |
| Portability | installer works under an alternate simulated HOME/config paths; an actual second computer remains a separate acceptance test |
| Failure | missing source, dirty update, incompatible entry, and offline/permission errors are reported, not silently ignored |

Static installer tests use disposable directories. They do **not** prove that a live Agent loaded the rules, and P1 must never report behavioral PASS without new-session evidence.

## Notes for P2

Only after a separate Human decision, identify redundant paragraphs in Personal System/GameChat `AGENTS.md` and preserve all project-specific architecture, Review gates, and recovery rules. Cross-project Toolbox links must remain optional; do not create a runtime or repository dependency between those projects.
