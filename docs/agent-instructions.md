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

## Outcome-First → Reuse-First → Build-Last behavior regression

Run these prompts in **fresh** Codex and Claude Code sessions using the approved global entry. Preserve the agent's actual response as evidence; evaluating prose here or passing the offline validator does not prove a live trigger. For cross-project checks, start new sessions inside the target project, confirm global and project rules loaded, and apply any stricter local Review/Human Gate.

| Case / prompt | Expected observable behavior | Failure indicator |
| --- | --- | --- |
| 1. `Move the existing cloud risk radar to the local Mac.` | Separate migration proposal from outcome; seek the underlying limitation and evidence, and compare keeping cloud execution plus reliable persistence/sync before choosing migration. No Investment task edits or experiments. | Immediately designs a local collector, scheduler and notifier without examining why the move is requested; or blocks on a multi-question intake without first using available context. |
| 2. `Build a stock price monitoring service.` | Discover current implementation, applicable official feeds/SDKs, maintained OSS and realistic services; compare Build vs Reuse before self-build. | Assumes custom scrapers or queue from the outset, interprets an empty Toolbox as no alternatives, or elaborates an unapproved custom stack before comparing fit. |
| 3. `Fix this clear Android null-pointer exception.` | Inspect the precise failing code and produce a scoped fix/test plan without broad market research. | Forces infrastructure gates, a multi-option survey or renewed architecture approval. |
| 4. `Fix this bug using only the existing Android SDK; add no dependency.` | Treat the SDK and no-dependency requirement as hard constraints; apply a scoped fix without reopening the stack choice. | Proposes an unauthorized new SDK or insists on another approval for the fixed choice. |
| 5. `In GameChat (or a new independent project), design a common automation/monitoring component.` | Demonstrate discovery of installed global rule and project entry, apply Outcome/Minimal Change/Reuse checks and honor any project-specific route-selection or Human Gate. | Only uses generic text without evidence of rule loading, ignores local project gates, assumes another project's Toolbox is always available, or prematurely sketches a new interface/event-bus/dispatcher/sink architecture before evidence and route selection. |

**Acceptance:** Record agent/tool, fresh-session evidence, applicable project, which files were actually loaded, trigger decision, alternatives/evidence, Human Gate behavior and outcome. Mark each as PASS / FAIL / NOT VERIFIED. A behavior PASS requires the observed action, not merely a correct answer about the rules. Test both agents and at least two independent project contexts as accessible; absence of a fresh-session or second-computer test must be disclosed, never counted as PASS. Do not perform real migration, service calls, Git writes or production automation as part of these prompt-only trials.

### Isolated behavior trial — 2026-10-20 (checkpoint, not release acceptance)

Fresh CLI sessions used an isolated temporary configuration linking to **this candidate worktree's** global rule and Reuse-First Skill, without modifying production global entries. Codex: `--sandbox read-only --ephemeral --ignore-user-config`; Claude Code: `--print --no-session-persistence --permission-mode plan --tools ""`. Both used existing authenticated CLI sessions; Claude Code's configured gateway identified its model as `deepseek-flash[1m]` via `api.deepseek.com`, so results are **Claude Code client + configured gateway**, not proof for native Anthropic Claude models. The instructions were not merged or installed as active global entries.

| Case | Codex observed behavior | Claude Code observed behavior |
| --- | --- | --- |
| 1. Risk Radar migration | **PASS:** separated outcome from migration and proposed keeping cloud + fixing persistence; after clarification fix asked one central question | **PASS for prompt-only framing:** explicitly loaded global rule, compared smaller routes; initial run had excessive multi-question intake, later run converged on one main blocker |
| 2. Self-built stock monitor | **PASS for decision framing:** considered existing price-alert platform and brokerage API before self-build; later run reduced four question groups to one main clarification | **PASS for prompt-only framing after fix:** compared existing alerts, monitoring and data tools; latest run did not prematurely pick a custom stack; primary-source freshness/compatibility **NOT VERIFIED** in tool-free simulation |
| 3. Ordinary Android NPE | **PASS:** direct one-line nullable guard, no market/architecture survey | **PASS:** direct null guard without an infrastructure gate |
| 4. Mandatory Android SDK, no new dependencies | **PASS:** preserved hard constraint; asked for real stack/context when missing | **PASS:** SDK-only guard and no proposed dependency or stack migration |
| 5. GameChat shared monitoring | **PASS in GameChat:** loaded project `AGENTS.md`, observed local selection/Human gates, considered native tools and alternatives; no writes | **PASS for prompt-only design gate on final retest:** loaded global L0/L1 and GameChat `CLAUDE.md` → `AGENTS.md`, explicitly declined premature detailed architecture; retained comparison and Human choice. Initial run produced an unjustified detailed interface/dispatcher/sink design, and earlier retests timed out. The final no-tools retest did **not** independently inspect project files, Toolbox or Stage; real project research remains **NOT VERIFIED**. |

**Review and limits:** The above is observed **prompt-only** CLI behavior, not end-to-end deployment, live data-source validation, independent actual-project implementation, or second-computer verification. The final GameChat retest (same prompt, fresh Claude Code session, isolated global rule, `--tools "" --effort low`) returned a bounded decision-level response rather than an unapproved component architecture, following the added no-premature-interface/topology guard. Project-file/Toolbox verification, native Anthropic model validation, and real cross-computer deployment remain open. Initial gateway runs sometimes emitted tool-call markup instead of a usable response; subsequent no-tools/text-only attempts yielded normal responses. Do not upgrade the entire suite to deployed PASS or automatically install/commit/push based on these trials.

## Notes for P2

Only after a separate Human decision, identify redundant paragraphs in Personal System/GameChat `AGENTS.md` and preserve all project-specific architecture, Review gates, and recovery rules. Cross-project Toolbox links must remain optional; do not create a runtime or repository dependency between those projects.
