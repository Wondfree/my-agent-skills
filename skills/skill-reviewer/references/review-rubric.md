# Skill review rubric

## Defect priorities
- **P0**: a broadly reachable irreversible destructive/security error or a skill unusable for any intended invocation.
- **P1**: a central promised workflow fails, or a serious permission/secret/privacy boundary is violated.
- **P2**: a realistic normal invocation fails, writes into the wrong place, relies on a machine-specific assumption, or documents a command that will not work as described.
- **P3**: minor but actionable friction or ambiguity with a real user impact.
- `P2?` is an unconfirmed heuristic lead, not a confirmed P2. Verify its context and impact before assigning a finding priority. `INFO` denotes an observation or an unperformed check; neither blocks the audit by itself.

## Minimum examination
- **Routing**: name, description, actual trigger conditions, unwanted capture, overlaps with installed skills; distinguish creator/reviewer/ordinary code-review responsibilities.
- **Layout**: frontmatter, useful instructions, valid relative links, complete scripts/templates and optional metadata.
- **Portability**: hard-coded user names, absolute paths to tools or files, fixed local project roots, implicit working directories, Linux vs macOS assumptions, virtualenv and `PATH` handling. Do not flag `/usr/bin/env` or `/bin/sh` automatically; some platform-specific paths are legitimate with stated preconditions.
- **Execution**: inspect argument parsing, imports and startup behavior before running any target code, including `--help`. Run it only after establishing that the invocation is safe, using an isolated test environment with appropriate filesystem/network restrictions. A temporary working directory alone is not a sandbox. If safety cannot be established, inspect statically and report the untested behavior. Trace documented flags, shell escaping, input/output naming, side effects and repeatability; don't trust a shell example solely because it is formatted as code.
- **Safety**: destructive writes, unexpected network operations, secrets/cookies, consent boundaries, error handling, repeat attempts and data leakage.
- **Evidence**: creator format check if present; static inspection; genuine behavior demonstration in isolated, non-production sandbox if safe; report any untested path.

## Output
Start with numbered, severity-ranked confirmed findings:

`[P2] Make interpreter detection portable — SKILL.md:24`

Then a short paragraph: realistic failing scenario, direct evidence, and minimal correction.

Finish with:
- `Scope`: complete skill or specified diff and whether a repository exists.
- `Tests`: commands actually run; success/failure. Do not pretend a static check is a smoke test.
- `Heuristic leads`: unconfirmed, only if consequential.
- `Residual risks`: unavailable dependencies, no safe live run, or unexamined platforms.
- `Verdict`: NEEDS FIXES for confirmed P0–P2 findings; PASS WITH WARNINGS for P3 findings or consequential validation gaps; PASS when no actionable findings or consequential gaps remain. Unconfirmed leads require triage, not automatic promotion to findings. All verdicts are review judgments, not automatic deployment permission.

The static audit exits 1 on P1/P2 observations and 0 otherwise; argparse invocation errors exit 2. These codes are CI signals, not the semantic review verdict. A zero exit with an unavailable interpreter or unverified leads still requires review.

## Distinguish harmless examples
Generic placeholder paths (`<input>`, `/path/to/file`) and explicit example URLs are not production hardcodes unless instructions mistakenly demand running them literally. A fixed absolute Python path may be valid when a skill is specifically for the system Python on one controlled image, but should be reviewed when marketed as cross-platform. A dynamic home-directory variable is preferable to a literal username, but a fixed path under the home directory may still incorrectly assume the installation location.

## Create–review–repair cycle
The creator implements; reviewer audits read-only; creator/executor applies corrections and revalidates. Running the same reviewer again after repairs tests closure; an independent agent pass is useful for complex or risky skills when available but is not assumed to have occurred merely because this skill is separate.
