---
name: reuse-first
description: Before building general-purpose infrastructure or choosing a significant technical approach, search for existing in-project, official, open-source and managed solutions, compare Build vs Reuse, and present evidence for a human decision. Use for new data collectors, monitoring, schedulers, queues, RAG/memory, auth, notifications, observability or testing infrastructure; not for routine bug fixes, narrow patches or preapproved minor implementation details.
---

# Reuse-First — Stop, Discover, Compare

Apply this workflow **before** designing or implementing an applicable new generic capability. It is a decision aid, not permission to install, experiment, rewrite scope or execute consequential changes.

## 1. Scope and trigger

- Identify the precise capability, actual constraints, acceptance criteria, whether a technical decision has already been approved, and the cost of a wrong choice.
- Trigger when proposing new generic modules, common workflow automation or significant tool/infrastructure decisions.
- Skip extensive external discovery for ordinary bug fixes, scoped changes and routine implementation inside an already approved technical choice. Reuse existing source and tests as usual.
- For a small reversible decision, use a short search and short comparison. For important, expensive or security-sensitive design, investigate substantive alternatives.

## 2. Discovery (proportional)

Use existing sources before inventing a replacement:

1. Current repository implementation, dependencies and approved architecture.
2. Personal System Toolbox Problem Index / Radar **if reachable and relevant**; report inaccessible, absent or stale evidence accurately.
3. Official platform features, APIs, SDKs, existing standards or maintained libraries.
4. Relevant, demonstrably maintained GitHub/open-source projects; verify the primary repository, not just popularity.
5. Managed/commercial solutions when realistically suitable.

A Toolbox miss does not mean the ecosystem has no candidate. If tools, network or trustworthy evidence are unavailable, mark `NOT VERIFIED` and stop short of an unsupported self-build recommendation. Do not browse without a meaningful reason or expand research indefinitely.

## 3. Build vs Reuse

Compare viable **reuse**, **adapt/combine**, **build**, and **defer** options against the same real problem. Record concise, source-backed evidence for:

- Functional coverage and required adaptation;
- Maintenance maturity, recent activity and relevant compatibility;
- License, security, privacy, permission and supply-chain risks;
- Integration complexity, ownership, ongoing maintenance and deployment/operating cost;
- Actual constraints that might justify custom development.

Prefer a concrete shortlist with disqualifiers over a rigid scorecard. Do not claim a library is safe, maintained or compatible without checking it. When a candidate is rejected, explain why; when no viable options can be confirmed, preserve unknowns.

## 4. Decision handoff

Provide: (a) the decision question and trigger, (b) candidates and links/sources, (c) concise comparison and evidence gaps, (d) the recommended reuse / combination / build / defer option and why, (e) validation or reversal conditions, and (f) the **Human decision required when consequential**, or the existing approval authorizing a small reversible choice. Stop at the existing approval boundary when the choice is consequential.

Save project-specific comparison in its established decision/design record; refer useful general learnings to Personal System Toolbox per its Handoffs, respecting access and separate approval. Do not create a second candidate database or automatically upgrade Toolbox levels.

## 5. Independent design review

Reviewers should independently check the actual design and evidence: Did the trigger apply? Were relevant existing and external options considered? Was the selected approach justified by evidence and constraints rather than habit? For any applicable general-capability design, missing investigation material to its scale or unsupported dismissal is a blocking design-review finding; higher-impact decisions require deeper evidence. For excluded ordinary fixes or narrow changes, demanding a full external survey is itself disproportionate.

## Calibration examples

- New local stock-price collector/monitor: **trigger**; compare existing project capability, official sources, maintained OSS and managed feeds before inventing scrapers.
- Routine Android bug fix: **do not trigger** an ecosystem-wide survey.
- Toolbox no match: **continue** with official and OSS discovery, or report access gaps.
- Proposed custom task queue or RAG store: **trigger**; a reviewer must examine Build vs Reuse evidence.
- Existing approved dependency, small adapter fix: normally **no full discovery** unless important new evidence invalidates that decision.
