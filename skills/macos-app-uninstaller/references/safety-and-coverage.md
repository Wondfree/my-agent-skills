# Evaluation and recovery notes

## Discoverability and coverage

The scanner inspects /Applications and ~/Applications (one nested level) and immediate children of common per-user Library subdirectories, selected system Library folders (review only) and /private/var/folders/*/*/C cache directories. Paths beneath the app-data directories are measured recursively, but the tool never searches or deletes unconnected parent directories.

Matching uses Info.plist identity, exact Bundle ID, exact Unicode-aware normalized application-name aliases and recognized helper-cache suffixes. No fuzzy substring deletion. Data using an unexpected name is not discovered automatically. System-wide installer receipts, services outside known paths, network drives, deeply nested apps, other users' data and unknown aliases may require additional manual review. Never promise exhaustive removal.

A Bundle ID may still be scanned after the .app is gone, but the app display name might no longer be available. If an independently verified data directory is missing from the automated plan, report it separately; never insert it manually into an approved plan just to bypass eligibility rules.

## Deletion guardrails

- A review result is **manual investigation**, not permission to delete. Shared Group Containers, system LaunchAgents/Daemons, privileged helpers and system-level Application Support are always review-only, and this CLI refuses to move them.
- Recent Documents / sharedfilelist is excluded. No bypasses for macOS TCC/SIP, no elevated privileges and no forced deletion.
- The manifest fingerprint detects accidental changes; it is **not** evidence of user authorization. The agent must separately obtain consent for exact item IDs.
- The scanner can create a new manifest at an explicitly chosen output location, but does not modify target files; protect manifest privacy.
- Directory counts/sizes and metadata fingerprints are time- and count-bounded; truncated results are marked review-only. A complete directory is rechecked before Trash, including child metadata changes, and ownership must match the current user. Apple (com.apple.*) bundles are excluded from automated scanning and removal.
- If source metadata changes after scanning, stop and rescan. If only some items were moved, report the partial result and do not quietly retry another technique.
- App data can contain sessions, keys, browser state, local projects and secrets. Examine directory names and sizes to inform the user without opening or sharing their contents.
- Trash is reversible until emptied. Do not empty it automatically.

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
