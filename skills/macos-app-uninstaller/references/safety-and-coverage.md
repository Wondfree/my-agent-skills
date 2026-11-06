# Evaluation and recovery notes

## Discoverability and coverage

The scanner inspects /Applications and ~/Applications (direct apps and apps in one non-app vendor folder; only the app itself is eligible for removal) and immediate children of common per-user Library subdirectories, selected system Library folders (review only) and /private/var/folders/*/*/C cache directories. Paths beneath the app-data directories are measured recursively, but the tool never searches or deletes unconnected parent directories.

Matching uses native or wrapped iOS-on-Mac Info.plist identity, exact Bundle ID, exact Unicode-aware normalized application-name aliases and recognized helper-cache suffixes. UUID sandbox containers use `com.apple.containermanager.identifier` extended attributes to prove app/extension identity rather than guessing from UUID directory names. Cookies (`*.binarycookies`) and Application Scripts are included. Preferences/ByHost matches only an exact Bundle ID followed by a host UUID and `.plist`; other host naming schemes require manual review. No fuzzy substring deletion. Data using an unexpected name is not discovered automatically. System-wide installer receipts, services outside known paths, network drives, deeply nested apps, other users' data and unknown aliases may require additional manual review. Never promise exhaustive removal.

A Bundle ID may still be scanned after the .app is gone, but the app display name might no longer be available. If an independently verified data directory is missing from the automated plan, report it separately; never insert it manually into an approved plan just to bypass eligibility rules.

## Deletion guardrails

- A review result is **manual investigation**, not permission to delete. Shared Group Containers, system LaunchAgents/Daemons, privileged helpers and system-level Application Support are always review-only, and this CLI refuses to move them.
- Recent Documents / sharedfilelist is excluded. The automated Trash operation uses no elevated privileges and never forces deletion. No bypasses for macOS TCC/SIP.
- The manifest fingerprint detects accidental changes; it is **not** evidence of user authorization. The agent must separately obtain consent for exact item IDs.
- The scanner can create a new manifest at an explicitly chosen output location, but does not modify target files; protect manifest privacy.
- Directory counts/sizes and metadata fingerprints are time- and count-bounded; truncated results are marked review-only. A complete directory is rechecked before Trash, including child metadata changes, and ownership must match the current user. Apple (com.apple.*) bundles are excluded from automated scanning and removal.
- If source metadata changes after scanning, stop and rescan. If only some items were moved, report the partial result and do not quietly retry another technique.
- App data can contain sessions, keys, browser state, local projects and secrets. Examine directory names and sizes to inform the user without opening or sharing their contents.
- Trash is reversible until emptied. Do not empty it automatically.

## User-run manual fallback

Only when the user requests manual terminal fallback after safe Trash fails:

1. Obtain approval for the exact paths and manual commands using a fresh manifest. If metadata changes, rescan and obtain updated approval.
2. Use `manual-preview --manifest ... --confirm ... --ids ...`. Never hand-write, interpolate or infer deletion commands from scanner text or screenshots. Copy only complete output lines into one copyable shell block, one exact absolute path per line.
3. The independent `scripts/deletion_guard.py` enforces strict path/category allowlists, canonical paths, no symlinks and protected-directory exclusions. The preview rechecks the manifest, ownership, identity and metadata; if any selected item fails, no commands are printed. Verified root-owned installed apps may be accepted, but ordinary review-only resources and incomplete scans are refused.
4. Warn that user execution permanently deletes data outside Trash. Commands use `sudo` only for verified root-owned apps; permissions may still block them. The agent must **never execute** these commands or bypass the guard, TCC or SIP.

Never generate commands for guessed UUIDs, broad parent directories, another app's data, shared components, unapproved iCloud data or macOS Recent Documents. Shared Group Containers and excluded resources need further investigation, not a guard bypass.

## Incomplete scans and permissions

Targets exceeding 20,000 files or the 3-second metadata budget, or containing unreadable entries, are marked truncated and review-only. Neither Trash nor manual-preview can act on them. Report the incomplete coverage and exact path, and hand inspection and removal back to the user in Finder; do not raise the limits or switch deletion methods to bypass verification.

On `PermissionError`, “Operation not permitted”, or an access-denied Trash failure, report the affected path and the limitation. Do not use sudo, change permissions or retry permanent deletion automatically. macOS privacy controls can require Full Disk Access for the terminal or host app; if the user chooses to grant it in System Settings → Privacy & Security → Full Disk Access, rescan afterward and obtain approval for the new exact plan. Full Disk Access does not override SIP or filesystem ownership, and it does not guarantee removal. Keep inaccessible locations explicitly unverified; absence from the report is not proof they are empty.

## Typical disposition

| Category | Default |
|---|---|
| Installed app bundle with exact Info.plist identity | High-confidence candidate |
| Exact Bundle ID preferences, caches, sandbox | High-confidence candidate |
| Exact sufficiently specific app-name Application Support data | High confidence; highlight user data |
| Bundle-prefix helpers outside known cache naming | Review |
| Group Containers or shared resources | Review and not eligible for Trash CLI |
| Global helper, system daemon or global startup item | Review and not eligible for Trash CLI |
| Recent Documents / macOS sharedfilelist | Excluded |
| Weak abbreviated or substring name matching | Excluded |

No source file can be removed merely because a report suggests it: the user makes the final decision.
