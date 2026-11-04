---
name: reuse-first
description: Use when evaluating consequential design or technology choices, new shared infrastructure or automation, significant migrations, or build-versus-reuse decisions. Excludes routine bug fixes, narrow patches, and implementation within an approved technical route.
---

# Outcome-first → Reuse-first → Build-last

Establish the outcome, consider smaller fixes, then compare reuse with building. Match effort to impact, reversibility and uncertainty. This package stands alone; project rules and existing user approvals remain authoritative. An **approval gate** is a point where the user or project policy requires a decision before proceeding. This skill grants no additional permissions.

## When to apply

A choice is **consequential** when it materially changes one or more of:

- Shared capabilities, architecture or operating responsibility;
- Data location, migration, security, privacy or access boundaries;
- Recurring cost, external service reliance or maintenance burden;
- Recovery effort or the ability to reverse the change.

A new dependency or service is a signal to assess impact, not an automatic full survey. Handle ordinary bugs, small adapters and approved implementation directly. Reopen an approved route only when material new evidence challenges it. For unclear cases, read [calibration examples](references/calibration.md).

## 1. Frame the decision

Separate the observed problem, verifiable outcome, fixed constraints and suggested solution. Honor explicitly mandated approaches; alternatives are advisory within scope. Use available context, asking one decisive question only when missing information blocks progress.

For recurring workflows, trace trigger → work → usable result, including persistence and notification when required. Distinguish necessary user decisions from execution already delegated to the agent.

## 2. Compare proportionately

Consider keep/configure, local repair, reuse, adapt/combine, replace/build and defer. Eliminate implausible options briefly. Investigate existing project capabilities first, then relevant official features or standards, maintained open source, and suitable managed services.

An accessible knowledge catalog is optional. Its absence or an empty result does not establish an ecosystem gap. Mark unavailable evidence `NOT VERIFIED`; do not infer that custom development is necessary.

Compare viable options against the same outcome: functional fit, maintenance and compatibility, license/security/privacy, integration effort, ownership and ongoing cost. Cite evidence and explain material rejections. Until comparison and any required route approval are complete, keep proposals at comparison level; defer new interfaces, component topology and detailed build plans.

## 3. Validate only the gap

Reuse applicable documentation, inspected implementations, logs and earlier tests. Record sources and conditions; distinguish **A** supported facts, **B** evidence whose applicability is unconfirmed, **C** decision-critical assumptions, and **D** irrelevant unknowns. Missing evidence in this chat does not prove a check never ran.

Before another experiment, identify the remaining uncertainty, what existing evidence establishes, how failure could change the decision, the smallest safe check, and a sufficient stop condition. A brief paragraph is enough; no mandatory matrix.

Stop when evidence is sufficient. If tests or prerequisites keep multiplying without progress, reassess the original outcome and whether the next step changes the decision; simplify or defer unnecessary work. Preserve environment-specific permission, backup/restore, migration and irreversible-action checks: general documentation cannot establish current account access or data safety.

## 4. Handoff and review

Present the problem/outcome/constraints, viable alternatives and sources, recommendation and evidence gaps, acceptance or reversal conditions, and the decision needed or existing authorization. Save the comparison in the project's established decision record. If none exists, provide it in the response; creating a new repository or external catalog needs separate authorization.

For consequential proposals, use an authorized human reviewer or a separate agent/session acting as reviewer. Before performing or requesting that review, read [independent design review](references/design-review.md). The reviewer must examine the actual proposal, rules and evidence. Self-checks and script results are not independent review. If no reviewer is available, record review as pending and continue authorized preparation without crossing a required review or approval gate.

After implementation, verify the defined outcome and resulting maintenance burden. Continue already authorized low-risk steps without repeated approval; installations, external writes, scope changes and other gated actions still require their applicable authorization.
