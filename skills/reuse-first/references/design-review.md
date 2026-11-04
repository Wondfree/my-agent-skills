# Independent design review

Read this when performing or handing off review of a consequential proposal. Routine patches and execution within an approved route do not need a new design survey.

## Arrange the review

Use the project's existing reviewer and approval process. The reviewer may be a human or a separate agent/session assigned to assess the proposal rather than author it. A fresh session counts only when it actually examines the proposal and evidence; changing sessions or running a validator alone proves no review occurred. Review does not grant implementation authority.

Provide the reviewer with:

- The actual proposal or diff, original request and applicable project rules;
- Existing approvals, fixed constraints and the authorized scope;
- Candidate comparison, source evidence, assumptions and unresolved gaps;
- Outcome checks, reversal conditions and known implementation risks.

Use available, authorized delegation; this skill requires no particular tool or reviewer service. If none is available, label independent review **pending**, identify the missing reviewer, and continue permitted evidence gathering or drafting. Stop before any required review/approval gate. Do not claim that self-check cleared it.

## Review criteria

| Check | Question |
| --- | --- |
| R1 — Problem alignment | Does the proposal address the evidenced problem and specify an observable outcome? |
| R2 — Assumptions | Are supported facts, conditional evidence and assumptions separated? Are suggested solutions distinct from fixed constraints and approvals? |
| R3 — Minimal change | Were configuration and local repair considered before replacement or a new system? |
| R4 — Reuse evidence | Were project capabilities, relevant official, maintained open-source and managed options investigated proportionately? Are material rejections supported? |
| R5 — Scope and authority | Are user decisions, repository boundaries, unrelated work and project approval gates respected? |
| R6 — Sufficient validation | Was prior evidence reused? Does each proposed experiment affect the decision or necessary safety assessment, with a small scope and stop condition? |
| R7 — Complete outcome | Does the workflow reach a useful result? Are manual steps justified by decisions or permissions rather than imposed on already delegated execution? |

## Record the result

Record reviewer identity, proposal version, evidence examined, findings and unresolved gaps. Use the project's verdict format; otherwise report **ready for user decision**, **needs changes**, or **pending independent review**, with reasons.

For consequential design, unresolved R1, material R2–R4/R6 gaps affecting the decision, material R7 gaps leaving the outcome incomplete, and substantive R5 violations block a passing design review. Minor improvements do not justify endless investigation. Preserve stricter project gates and distinguish review readiness from user approval or production validation.
