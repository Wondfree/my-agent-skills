---
name: macos-app-uninstaller
description: Safely discover and uninstall a macOS application by app name or Bundle ID. Scan application bundles, preferences, app data and caches; assess ownership, request approval for an exact deletion list, then move approved files to Trash and verify. Not for general disk cleanup or automatic removal without user consent.
---

# macOS App Uninstaller

Use when the user wants to inspect or uninstall a named macOS application, including without an App Cleaner screenshot. The Skill provides a read-only inventory phase and a separate confirmed Trash phase. Finding files, scanning them, or a previous general preference is **not** authorization to delete them.

## Workflow

1. Resolve the app name or Bundle ID. If several apps match a name, request disambiguation. Do not guess or silently select one.
2. Locate the directory of this SKILL.md as SKILL_DIR at runtime. Script paths are relative to it; no fixed user home.
3. Run the scanner by name or Bundle ID (see commands below). It inventories candidate targets without modifying them. To prepare actual removal, optionally create a **new private manifest** via --output; the command refuses to overwrite existing files.
4. Report **every** candidate and its ID, exact path, category, size, evidence, and confidence (high or review). Flag likely user data (sessions, databases, preferences, account information). Examine folder names if needed, never dump private contents or secrets.
5. Mark uncertain or shared paths as review-only. Exclude macOS Recent Documents / sharedfilelist from deletion **by default**. Never attempt to evade OS privacy controls or permissions.
6. **Ask for explicit user approval of the exact numbered paths** before any deletion. Warn that removing session/history folders can destroy user state. On a preserve-data request, leave those IDs out. Scanning consent is never deletion consent.
7. Only after approval, execute the separate trash command with manifest, matching plan_id, and **only the explicitly approved high-confidence IDs**. The script re-checks path, ownership, device/inode/mtime, nested directory metadata and running-app state before invoking macOS FileManager.trashItem. If anything changed, stop and rescan/re-approve. Do not retry via sudo, rm, permission changes, or other workarounds.
8. Verify which sources vanished and which destinations landed in Trash. Report successes, failures and remaining files distinctly. Never empty Trash automatically.

## Commands

    SKILL_DIR="<absolute directory containing this SKILL.md>"
    python3 "$SKILL_DIR/scripts/app_uninstaller.py" scan --name "Example App"
    python3 "$SKILL_DIR/scripts/app_uninstaller.py" scan --bundle-id "com.example.app" --output "<new private manifest path>"

    # After showing the exact manifest and receiving explicit user approval for IDs 1,2:
    python3 "$SKILL_DIR/scripts/app_uninstaller.py" trash --manifest "<plan.json>" --confirm "<plan_id>" --ids "1,2"

Requirements: macOS and Python 3.9+ (scanner). Trash phase also requires Swift / Apple command line tools; [trash.swift](scripts/trash.swift) is bundled. No network fetches, installation, or privileged execution is necessary. Read [safety and coverage notes](references/safety-and-coverage.md) for missed files, macOS permission errors and mixed-confidence cases.

## Confidence limits

High confidence is **not proof of exclusive ownership**. It means an exact Bundle ID, a sufficiently specific exact normalized app-name in an expected location, or an identified helper cache. macOS apps may leave unknown or shared locations; neither an empty scan nor a successful Trash operation proves complete removal. Always use the human approval gate. Do not recursively delete a parent directory, guess dynamic folder paths, or interpret similar names as sufficient proof.
