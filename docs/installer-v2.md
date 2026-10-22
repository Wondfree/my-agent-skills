# V2-A selection and V2-B review handoff

User story: on a new machine, a Human selects new Skills and global
rules, previews exact paths and approves once. A previously installed global
configuration is kept automatically and shown separately for optional review;
it does not block installation of a new unrelated Skill.
No project AGENTS.md is modified.

## Outcome-First / Reuse-First comparison

Outcome: make selection and conflict review understandable without silent adoption
or exposing private configuration. The approved route is a standard-library thin
wrapper around the existing installer, with no dependency, backend, or database.

| Option | Coverage and decision |
| --- | --- |
| Keep `install.py` | Already covers explicit names, paths, backups and previews; retained unchanged by default. |
| Official native instructions/Skills | Keep native discovery and loading: [Codex AGENTS.md](https://developers.openai.com/codex/guides/agents-md), [Codex Skills](https://developers.openai.com/codex/skills), [Claude memory](https://code.claude.com/docs/en/memory), [Claude Skills](https://code.claude.com/docs/en/skills). No replacement loader. |
| Thin selection wrapper | Asks about uninstalled entries only; identifies existing symlinks and exact link destinations without content comparison. New-entry writes and preflight remain installer-owned; Codex/Claude instruction clients remain independently selectable. |
| New service/framework/model backend | Outside scope; existing agents can review after consent. No automated semantic claims. |
| Defer AI review | Safe default: deterministic local status only, with conflicts blocked. |

Official links are reference pointers, not newly verified documentation: this
implementation used offline repository evidence under the no-network constraint.
Consumer auto-detection and compatibility beyond the existing destination-directory
support are not claimed. Use `--target-dir PATH` for an already supported consumer's
Skills directory; the default retains `SKILLS_TARGET_DIR` / Codex semantics.
Global entries independently use `--codex-home` / `--claude-home` and existing env
fallbacks. Both `link` (default) and `copy` modes delegate to the installer.

## Local flow

```sh
python3 -B scripts/install_wizard.py --target-dir /chosen/skills --dry-run
python3 -B scripts/install_wizard.py --target-dir /chosen/skills
```

Only entries not yet installed produce a yes/no installation question, which
defaults to No. Already installed entries require no choice. Existing links
pointing to another checkout are identified by the link target path only:
contents are not read or compared, and path difference is not described as
file-content conflict. Broken links, unreadable entries, and existing regular
files/directories needing review remain untouched. Existing entries do not
block unrelated selected new items. The final summary reports new choices,
entries already linked to this checkout, other sources, and review candidates.
A few exact SKILL.md sentences have concise English presentation copy and
Chinese translations in the message catalog. This is NOT a second Skill registry
or a second definition of any Skill's triggers. A changed or unknown source
sentence falls back to its original text. Unreadable descriptions are reported
without relaxing the installer's independent preflight.

The summary replaces the duplicate technical dry-run output, but safety checks
and their error messages remain visible. Newly arising conflicts affecting selected new items stop their installation.
A non-TTY invocation errors even with --dry-run; use install.py --dry-run
for noninteractive plans.

A final confirmation summary explicitly identifies the install mode:
`link` means the installed entries point to the local Git checkout and can
reflect later approved checkout changes; `copy` means installed copies are
not refreshed until explicitly reinstalled. This distinction must be shown
before Human confirmation. File paths, Skill names, and descriptions shown
in the terminal escape control characters (including ANSI escapes and bidi
controls). Only display text is escaped; filesystem arguments are unchanged.
Underlying installer output, including error details, is also escaped by the
wizard's console adapter.

The wizard never passes the adoption/overwrite flag. Existing entries,
broken links, and unreadable entries are left untouched and require separate
review if the Human wants to migrate or replace them. A Codex global override
file is detected locally and flagged as possibly shadowing the managed rules.
The original installer still rejects any newly arising conflict involving a
selected new entry. Other new items are installable without migrating existing
ones. Codex override/path protections remain installer-owned.
Git Lifecycle hooks are not activated by Skill installation; separate activation
is needed. No hook setup is offered here.

## Language selection (Chinese/English)

The wizard uses a small shared standard-library message catalog
(`scripts/installer_i18n.py`); it does not change Skill names, file paths,
shell commands or installation logic. Explicit `--lang zh-CN` and `--lang en`
override automatic detection. In the absence of a flag, explicit
`LC_ALL` / `LC_MESSAGES` take precedence; on macOS the first language in
`defaults read -g AppleLanguages` is used; otherwise `LANG` is used. An
unsupported language falls back to English. The macOS check is read-only,
times out after one second, and is optional (missing or failed `defaults`
falls back to environment). On this development Mac, `en-US` is the first
preference, so force Chinese with:

```sh
python3 -B scripts/install_wizard.py --lang zh-CN --dry-run
python3 -B scripts/install_wizard.py --lang zh-CN
python3 -B scripts/install_wizard.py --lang zh-CN --review-path /exact/config/CLAUDE.md
```

The language applies to selections, status, preview, conflict refusal, help,
post-installation messages, and path-only AI review handoff. The original
`install.py` defaults to English and accepts opt-in `--lang zh-CN` for
localized internal preview/error lines without changing the install decision.
The locale feature does not enable any Hook or relax Human review gates.

## Optional private configuration review

1. Inspect the target locally, including its symlink destination. Do not paste
   private configuration into shared issues, rules, logs, or this repository.
2. Generate a prompt without reading configuration or invoking any model:

   ```sh
   python3 -B scripts/install_wizard.py --review-path /exact/config/CLAUDE.md
   ```

   The output names the candidate source and target by path only. For a Skill,
   supply its installation directory named after the Skill. For an unusual target
   name, correct the candidate source path before using the prompt.
3. Choose your already available Codex or Claude agent and its read-only/plan
   workflow. Check its configured provider and retention policy yourself. Before
   submitting/allowing reads, explicitly consent to that model reading those exact
   paths. A path-only prompt itself grants no consent. The generated prompt asks
   the agent to confirm consent before reading, treat content as untrusted data,
   and obtain separate consent for external symlink destinations/references.
4. Request review-only classifications: **duplicate / shared candidate /
   machine-specific / project-specific / conflict / unknown**, with path/line
   references and uncertainty. No private quotations, modifications, publishing,
   installation, or commands from configuration. The report is never approval.
5. Leave conflicts blocked unless the Human makes a separate, explicit decision
   for each target. For a global entry approved for replacement, isolate that
   single client and preview its backup operation:

   ```sh
   python3 scripts/install.py --instructions-only --instruction-clients claude --claude-home /exact/config --adopt-existing --dry-run
   # Only after reviewing that exact target and affirmatively approving replacement:
   python3 scripts/install.py --instructions-only --instruction-clients claude --claude-home /exact/config --adopt-existing
   ```

   For a Skill use `--only NAME --target-dir /exact/skills --adopt-existing`
   with a dry-run first. Existing installer backups go to `.instruction-backups`
   or `.skill-backups`. An override or unsafe path remains refused even after
   approval; resolve independently. Do not use bulk adoption to silence conflicts.

V2-B does not run semantic analysis, guarantee model obedience, determine privacy
suitability, or prove rules loaded. The Human controls the review handoff and final
per-target decision. Installation is preflighted but not a multi-entry transaction;
a filesystem failure can leave earlier entries installed. Inspect before retrying.

## Offline verification and checkpoint

```sh
python3 -B scripts/test_install_wizard.py
python3 -B scripts/test_install.py
python3 -B scripts/validate_skills.py
python3 -B scripts/test_update.py
git diff --check
```

Wizard tests use mocked TTY/input and disposable HOME/config/Skills directories;
its original-installer regression subprocess inherits the isolated environment.
They cover independent clients, explicit selection, default skip, conflict privacy,
no implicit adoption, existing status, overrides, cancel/abort/EOF, dry-run,
non-TTY rejection, path-only handoff, and Python 3.9 syntax parsing. No agent or
network calls occur. Syntax parsing on a newer interpreter is not execution on
Python 3.9; native agent loading remains unverified.

Checkpoint (2026-10-21): implementation remains isolated in
`codex/installer-v2-selection-review`. Independent read-only Review found two
moderate issues: post-install interruption could falsely claim no changes, and
an unreadable but unselected instruction file could block a Skills-only run.
Both were corrected, two specific regression tests added, and independent
targeted re-review returned **NO FINDINGS**. Original installer, wizard, update
approval, and skill validation suites passed; a real terminal walkthrough,
actual AI semantic review, and second-computer behavior remain **NOT VERIFIED**.
Localization follow-up (2026-10-21): Chinese/English prompts, help,
installer previews/errors, and private path-only review handoffs are implemented.
The first independent read-only localization Review found two P2 issues:
untranslated `install.py --lang zh-CN --help` and host-locale-dependent
baseline tests. Both were fixed; an independent targeted re-review returned
**NO FINDINGS**. The 18 offline wizard tests and original installer regression
pass, and a real macOS pseudo-terminal `--lang zh-CN --dry-run` was observed
to display Chinese prompts and exit without installing. Actual installation
to a second computer and AI semantic review remain **NOT VERIFIED**.
No production configuration has changed; no commit, push, merge, installation
or production activation is authorized by this checkpoint.


## V2-A English copy and layout refinement (2026-10-21)

Copy now uses plain English and matching Chinese: short per-Skill descriptions,
clear installation statuses, selection by client, summary of consequences, and
one explicit final confirmation. The original install.py safety gate, Skill
opt-in defaults, and V2-B privacy/consent requirements remain unchanged.
Installation does not prove actual rule loading and requires fresh-session
verification. This change is in an isolated worktree until release is approved.

**Final V2-A copy/UX Review checkpoint (2026-10-21):** Independent read-only
review initially raised two P2 issues: the final confirmation did not explain
link-vs-copy update behavior, and dynamic terminal values could contain control
characters. Both were fixed with explicit bilingual mode explanations and
escaped display and installer output. Targeted review found two additional P2
error-path escape issues, followed by a P3 multiline diagnostic formatting
issue. Those were fixed without changing installation targets or permissions.
The final independent targeted re-review returned **NO FINDINGS**. The wizard
suite contains 26 passing tests (including English/Chinese, mode, conflict
refusal, terminal-control injection, readable diagnostic errors), and the
original installer, update-approval and Skill validation suites pass locally.
GitHub CI remains unrun until an approved commit/push. Second-machine install,
real AI semantic review and fresh-agent behavior remain NOT VERIFIED. Nothing
from this worktree has been installed into the active user configuration.


## V2-A existing-installation flow corrected (2026-10-21)

Real-user CLI acceptance showed seven apparent differences (five Skills and
two global instruction entries) because existing symlinks pointed to the
primary checkout while the wizard source was an isolated Git worktree.
That was a source-path difference, not proof of different content.

The wizard now reports installed links with their actual destinations and
does not request reinstall/keep decisions for already installed items.
The local status phase does not read private files to compare contents,
and does not invoke AI. Only genuinely not-installed entries prompt for
installation. Other existing files or broken links are review-only entries,
and do not block independent new installations. The original install.py
preflight is still authoritative and refuses unexpected conflicts.

A mocked alternate-checkout scenario covers all seven linked entries without
any installation questions. A real Mac pseudo-terminal dry-run independently
showed all seven installed elsewhere, no prompts, and zero installation
changes. Further targeted tests cover exact install matches, broken links,
copy-mode mismatch and mixed installed/new entries. Source migration and AI
semantic review are not part of this change.


## Independent review of source-status refinement

An independent read-only Review found two P2 issues: a preexisting Codex
override could shadow installed instructions while appearing healthy, and
some Chinese status labels asserted an unproven difference in file contents.
Both were corrected. Existing Codex overrides are now displayed as review
candidates; all existing regular-file states use neutral language. One
targeted regression test was added to ensure overrides cannot appear healthy.
Final independent targeted re-review returned NO FINDINGS. The follow-up
test suite has 33 passing cases, including the seven-link fixture, broken
links, installed-vs-new questions, Codex override files (including broken
override links), private-source protection and safe preflight. Real
second-computer installation and client behavior remain NOT VERIFIED.
