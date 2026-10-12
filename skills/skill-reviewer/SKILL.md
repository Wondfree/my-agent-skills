---
name: skill-reviewer
description: Read-only, defect-first review of a Codex/Agent Skill directory before adoption or after changes. Check skill routing, overlap, portability, external dependencies, safety, documentation-to-script consistency and realistic validation. Use for auditing an existing SKILL.md or reviewing newly created skills; not for creating or editing skills, general PR review, or auditing unrelated applications.
---

# Skill Reviewer

Review a skill as an **installable, reusable operating procedure**, not merely a valid YAML file. Read the target and all supporting files needed to validate its instructions. This skill is read-only with respect to the reviewed skill: report problems, do not edit, commit or install anything.

## Review procedure

1. **Establish target & scope.** Locate the exact `SKILL.md` and all directly referenced `scripts/`, `references/`, `agents/`. Respect `AGENTS.md` and any project policy. For a changed skill, get the actual diff if available; for a newly-created/untracked skill review the whole skill. Do not assume a Git repository exists.
2. **Compare boundaries.** Inspect names/descriptions of nearby installed skills relevant to the same tasks, to decide whether this one overlaps, misroutes, or should extend another. A similarity is not automatically a defect. Check `name` and `description` for clear triggers and exclusions.
3. **Run static checks** via `scripts/audit_skill.py` (from *this reviewer skill*, not the target) and the bundled Skill Creator's `quick_validate.py` if available. The audit is heuristic, so inspect each reported location before presenting it as a finding. Do not mislabel valid examples, user-requested platform dependencies, or placeholders as defects.
4. **Review execution and portability:** no machine/user/project-specific paths encoded as required runtime locations; sensible dynamic dependency discovery and transparent prerequisite checks; relative internal resources; working examples; reasonable defaults with configurable I/O; repeat-run behavior; failures/retries; output integrity; source preservation and privacy. Hard requirements depend on the skill's declared scope (a macOS-only skill may legitimately require macOS).
5. **Cross-check docs vs actual behavior:** trace commands from `SKILL.md` through flags and helpers. Confirm referenced scripts/files exist, expected environment variables are read, example invocations resolve and promises of non-destructive behavior are justified. Examine dangerous shell commands, network side effects and missing permission boundaries.
6. **Validate proportionately:** for scripted skills, run syntax checks and a small representative smoke test in an isolated temp directory only when safe and available. Do not run a production side effect, install packages, access private data without authorization, or trigger paid APIs merely to pass review. Report missing tests clearly; do not call a syntax check functional validation.
7. **Report defect-first** using `P0`–`P3` with precise `path:line`, affected scenario, and actionable correction. Separate **confirmed findings**, **heuristic leads requiring verification**, and **untested risks**. Use [review rubric](references/review-rubric.md) for priorities and exit criteria. If no actionable findings, say `No findings.`; no made-up issues.

## Reviewer checks

Resolve the skill directory containing this reviewer `SKILL.md` at runtime as `REVIEWER_DIR`; never assume the reviewer is installed under a specific user's home or a fixed global skills folder.

```bash
REVIEWER_DIR="<directory containing this SKILL.md>"
TARGET_SKILL="<target skill directory>"
python3 "$REVIEWER_DIR/scripts/audit_skill.py" "$TARGET_SKILL"
# Optional: use Skill Creator's official validator only if installed and accessible
python3 "<skill creator directory>/scripts/quick_validate.py" "$TARGET_SKILL"
```

The audit uses Python 3.9+ standard library and has `--json` for machine-readable observations. It is **non-mutating**: it does not `compileall`, modify caches, download dependencies, or invoke target code. Results are leads, not a replacement for human/agent review.

## Boundaries and handoff

- Review of regular code diffs belongs to `review-agent`; review of skill-specific contracts belongs here. When a skill includes code changes, both perspectives may be useful but neither automatically delegates to the other.
- Creation, repair and refactoring belong to `skill-creator` or the main execution agent. The reviewer proposes focused corrections only.
- Avoid modifying built-in `.system` skills; they may be replaced by upgrades. Never embed one specific workspace or one user's home as a universal standard.
- Completion means you inspected the real files and recorded results, not merely that `quick_validate.py` returned success.
