# My Agent Skills

A private-first, portable repository for **self-maintained** Agent Skills. The files in `skills/` are the canonical source (SSOT). Local agent directories are runtime installations, not independent sources of truth.

## Included

| Skill | Purpose |
|---|---|
| [video-to-knowledge](skills/video-to-knowledge/SKILL.md) | Download/source videos, local Whisper transcription, evidence-checked tutorial/knowledge notes |
| [skill-reviewer](skills/skill-reviewer/SKILL.md) | Read-only Skill review: boundaries, portability, safety, syntax, documented behavior |
| [macos-app-uninstaller](skills/macos-app-uninstaller/SKILL.md) | Identify macOS app residues by name or Bundle ID; confirmed Trash-only removal |

Not included: Codex built-in `.system` Skills, third-party skills (e.g. media/sprite forge and Lark skills), or personal workspace/logs. These must undergo ownership, license, data, and dependency review before any future import.

## Install on a new computer

Requirements: Git, Python 3.9+, and Codex or another consumer that supports Agent Skills. Media extraction skills separately require the tools stated in their own `SKILL.md`.

```bash
git clone git@github.com:Wondfree/my-agent-skills.git
cd my-agent-skills

# Preview changes (no files written)
python3 scripts/install.py --dry-run

# Link the installed Skills to this checkout (recommended on macOS/Linux).
python3 scripts/install.py
```

The default destination is `${CODEX_HOME:-$HOME/.codex}/skills`. Override with `--target-dir PATH` or `SKILLS_TARGET_DIR`. On computers where symbolic links are restricted (commonly Windows), use `python3 scripts/install.py --mode copy` and rerun the installer to update copies.

**Existing Skills are never overwritten silently.** If a target name already exists, the installer refuses to replace it. After comparing your existing files against the repo, explicitly run:

```bash
python3 scripts/install.py --adopt-existing --dry-run
python3 scripts/install.py --adopt-existing
```

Old local directories are preserved in the target's `.skill-backups/` directory, never deleted. Inspect those backups before removing anything yourself. A linked installation points to the local repo; if you move the repo, reinstall links from its new location. `--mode copy` creates independently editable copies, but those copies need explicit refreshes after Git updates.

## Update and synchronize

```bash
./scripts/update.sh          # Check local/upstream settings without changing files
./scripts/update.sh --apply  # Fetch, verify the incoming revision, fast-forward
```

Link-mode installations reflect the updated checkout. The update refuses dirty or diverged Git working trees and validates the incoming revision before applying. If you edit a linked Skill on your Mac, that is a Git working tree change: **review, commit and push it**; other machines then update. A remote update never auto-commits your unreviewed changes.

To contribute a change, modify files **in this checkout**, run validation, commit and push. Avoid editing `.system` Skills or vendoring external code without a license check.

## Review and CI

```bash
python3 scripts/validate_skills.py
python3 scripts/test_install.py
python3 skills/skill-reviewer/scripts/audit_skill.py skills/video-to-knowledge
python3 skills/skill-reviewer/scripts/audit_skill.py skills/skill-reviewer
python3 -B skills/macos-app-uninstaller/scripts/test_uninstaller.py
# On macOS with Xcode Command Line Tools:
swiftc -typecheck skills/macos-app-uninstaller/scripts/trash.swift
```

GitHub Actions runs these offline checks on pushes and pull requests. CI covers basic structure, path/secret heuristics, script syntax and installation safety—not AI-generated content quality, browser permission flows, paid services or long-running Whisper inference. A substantive Skill change still warrants scenario-based manual/agent review, and execution tests when safe.

## Privacy, ownership and publishing

The GitHub repository is intended to be **Private at first**. Its contents should contain no cookies, credentials, real customer data, video/source media, or private personal logs. Never blindly copy the whole installed Skills tree into this repo. Check ownership/licensing before adding any external Skill. Before publishing publicly, perform a separate privacy/license/security review and deliberately choose a license; a private repository by itself is not a safety boundary for secrets.

## First-time remote setup

If the remote does not exist yet, create a **blank private GitHub repository** named `my-agent-skills` under your own account, **without** auto-generating a README/license/.gitignore. Then configure and push this local checkout:

```bash
cd my-agent-skills
git remote -v
git push -u origin main
```

If SSH isn't configured on a new computer, authenticate with GitHub first or use GitHub's recommended HTTPS authentication; avoid embedding access tokens in remote URLs.

The initial migration does **not** change your already installed Skills until you explicitly run the installer/adoption procedure. This lets you inspect backups and switch runtime installations safely.
