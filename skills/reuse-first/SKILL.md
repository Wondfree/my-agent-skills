---
name: reuse-first
description: Before consequential design, migration or infrastructure/technology decisions, distinguish the real problem and outcome from a proposed solution, check minimal fixes, then compare in-project, official, open-source, managed and custom options for Human decision. Use for monitoring, data collectors, schedulers, auth, RAG/memory, notifications and significant migrations; not for routine bug fixes, narrow patches or implementation under approved constraints.
---

# Outcome-First → Reuse-First → Build-Last

Apply this **before** committing to a consequential design, migration, reusable capability or technical route. This is a proportional decision aid, not permission to install, run experiments, alter project scope or override Human choices. Reuse the current project's established design/decision record.

## 1. Trigger and Outcome Framing

- **Trigger:** New generic infrastructure, data/monitoring/automation systems, environment migration or consequential technology decisions with plausible alternatives. Match research depth to impact, reversibility and uncertainty.
- **Problem:** What is actually failing, and what evidence supports that diagnosis? Label observations separately from assumptions.
- **Outcome:** What result does Human want, and how will it be demonstrated or accepted? Do not confuse a proposed technical action with the goal it is supposed to achieve.
- **Constraints vs proposed solution:** Distinguish explicit must-use/must-not-use instructions and approved decisions from a suggested method. Honor genuinely fixed constraints; do not repeatedly reopen approval. Use existing context to resolve assumptions. If a single unresolved fact materially changes the decision, ask one decisive question; otherwise state provisional assumptions and proceed with a bounded comparison. Do not require multi-question intake, a form, or repeated approval.
- **Exclusions:** For routine bugs, scoped patches, approved minor implementation and routine tests, solve the task directly. Do not require a formal questionnaire, full ecosystem survey or new Human approval.

## 2. Minimal-change alternatives

Before proposing a replacement, consider in order: **keep/use differently** (including configuration), **repair a local gap**, **reuse existing platform/service**, **replace or migrate a component**, and only then **migrate or build a whole system**. Eliminate implausible options succinctly. If a smaller route can deliver the same outcome within the hard constraints, do not default to the user's tentative architecture. Until the relevant existing solutions have been investigated and Human has made any required route decision, keep proposals at comparison level: do not prescribe new interfaces, event contracts, queues, dispatchers, storage topology, custom stacks or detailed build plans as the default. Calling an architecture a 'candidate' is not a substitute for first establishing the outcome and comparison evidence. Use only the minimum implementation detail needed to distinguish viable alternatives. If an approach was explicitly mandated, treat alternatives as advisory only within authorized scope.

## 3. Discovery (proportional)

Use existing sources before inventing a replacement:

1. Current repository implementation, dependencies and approved architecture.
2. Personal System Toolbox Problem Index / Radar **if reachable and relevant**; report inaccessible, absent or stale evidence accurately.
3. Official platform features, APIs, SDKs, existing standards or maintained libraries.
4. Relevant, demonstrably maintained GitHub/open-source projects; verify the primary repository, not just popularity.
5. Managed/commercial solutions when realistically suitable.

A Toolbox miss does not mean the ecosystem has no candidate. If tools, network or trustworthy evidence are unavailable, mark `NOT VERIFIED` and stop short of an unsupported self-build recommendation. Do not browse without a meaningful reason or expand research indefinitely.

**Reuse evidence, not just components.** Before designing a fresh investigation or test, look for applicable official documentation, already inspected implementations, project test results, run logs, and historical incident findings. Record the source and conditions of each useful result, then distinguish (A) supported facts, (B) evidence with unconfirmed applicability to this environment, (C) decision-critical assumptions lacking evidence, and (D) unknowns irrelevant to the current decision. Do not treat a missing test in this conversation as proof it was never run; equally, a product capability described in documentation is not proof it succeeded under this account and permission set.

## 4. Build vs Reuse

Compare viable **keep/minimal fix**, **reuse**, **adapt/combine**, **build**, and **defer** options against the same original outcome and fixed constraints. Record concise, source-backed evidence for:

- Functional coverage and required adaptation;
- Maintenance maturity, recent activity and relevant compatibility;
- License, security, privacy, permission and supply-chain risks;
- Integration complexity, ownership, ongoing maintenance and deployment/operating cost;
- Actual constraints that might justify custom development.

Prefer a concrete shortlist with disqualifiers over a rigid scorecard. Do not claim a library is safe, maintained or compatible without checking it. When a candidate is rejected, explain why; when no viable options can be confirmed, preserve unknowns.

### Validate only the decision gap (proportional)

Before proposing a new experiment, answer briefly (in prose for simple decisions; no mandatory matrix):

1. **Unknown:** Which precise condition remains uncertain?
2. **Existing evidence:** What do official sources, project logs and previous tests already establish, and under which conditions?
3. **Decision impact:** Would failure of the proposed check change the current choice or safety assessment? If not, normally defer it.
4. **Smallest safe check:** Can existing evidence, a permission inspection, a read-back, or a bounded test settle only that gap?
5. **Stop condition:** What observable result is sufficient to choose, proceed, defer or stop?

When the evidence meets the defined decision threshold, stop adding tests. A new hypothetical failure mode is not automatically a new prerequisite: apply the existing Direction Drift Check against the original outcome. Conversely, require relevant environment-specific verification for permissions, external writes, data safety, migrations or irreversible/high-risk changes; documentation of general support cannot waive those checks.

## 5. Decision handoff

Provide: (a) the observed problem, desired outcome, fixed constraints and proposed solution as distinct items, (b) smaller alternatives and candidates with sources, (c) concise comparison and evidence gaps, (d) keep/fix/reuse/combine/build/defer recommendation and why, (e) outcome validation or reversal conditions, and (f) the **Human decision required when consequential**, or the existing approval for a small reversible choice. Stop at the existing authorization boundary.

Save project-specific comparison in its established decision/design record; refer useful general learnings to Personal System Toolbox per its Handoffs, respecting access and separate approval. Do not create a second candidate database or automatically upgrade Toolbox levels.

## 6. Independent design review

The independent reviewer examines the actual proposal, project rules and supporting evidence, not just internal consistency. Check:

- **R1 Problem Alignment:** Does the proposal solve the evidenced original problem and specify an observable outcome?
- **R2 Assumption Validity:** Are facts separated from assumptions, and suggested solutions from hard constraints or existing Human approvals?
- **R3 Minimal Change:** Were keep/configuration/local-repair alternatives considered before migration or system creation?
- **R4 Reuse Evidence:** Were applicable project/Toolbox, official, maintained OSS and managed candidates investigated proportionately? Are key rejections justified rather than inferred from a Toolbox miss?
- **R5 Scope and Authority:** Does the plan honor Human decisions, repository boundaries, dirty worktrees and existing project Review gates?
- **R6 Evidence Sufficiency and Validation Stop:** Did the team reuse applicable prior evidence, distinguish conditional evidence from unknowns, require each new experiment to affect the decision, choose the smallest safe check, and stop when sufficient? Were essential safety checks preserved?

For consequential design, unresolved R1, material R2–R4 or R6 gaps affecting the decision, or substantive R5 violations **block design Review**. Minor improvements do not expand scope indefinitely. For routine fixes and already approved scoped execution, imposing a full design survey is itself a review error. Self-check or script output is not independent Review. After implementation, verify not only technical correctness but whether the defined Outcome was achieved without unnecessary maintenance burden.

## Calibration examples

- "Move the cloud risk radar to my Mac": **trigger**; determine whether the real outcome is reliable research persistence, then consider keeping cloud monitoring and fixing output sync before local migration.
- New local stock-price collector/monitor: **trigger**; compare existing project capability, official sources, maintained OSS and managed feeds before inventing scrapers.
- Routine Android null-pointer fix: **do not trigger** an ecosystem-wide survey; use the existing code and tests.
- "Use only the existing Android SDK; no new dependencies": **fixed constraint**; do not reopen the technology decision.
- Toolbox no match: **continue** with official and OSS discovery, or report access gaps.
- Proposed custom task queue or RAG store: **trigger**; a reviewer must examine Build vs Reuse evidence.
- Existing approved dependency, small adapter fix: normally **no full discovery** unless important new evidence invalidates that decision.
- Official GitHub API supports JSON writes: **do not** create a test repository merely to re-prove that capability; check real account authorization only when it changes the decision.
- A first Scheduled write has succeeded: reuse the recorded write/read-back evidence; test cross-run state recovery only if required by the outcome, then stop if sufficient.
- Production database migration: official upgrade support does **not** replace necessary environment-specific backups, restore and migration checks.
- A new shared infrastructure request in GameChat or a new project: **trigger**, but also respect local project-specific selection gates; do not assume Toolbox availability or installation means the agent actually loaded this rule.
