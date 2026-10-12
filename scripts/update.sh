#!/usr/bin/env bash
# Synchronize this Git checkout with its configured upstream. Default is read-only.
set -euo pipefail
repo="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
apply=0
if [[ "${1:-}" == "--apply" && "$#" == 1 ]]; then
  apply=1
elif [[ "$#" != 0 ]]; then
  echo "Usage: $0 [--apply] (default: show status only)" >&2
  exit 2
fi
if ! git -C "$repo" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: repository is not initialized as a Git checkout." >&2; exit 2
fi
branch="$(git -C "$repo" symbolic-ref --quiet --short HEAD)" || {
  echo "ERROR: detached HEAD; update manually." >&2; exit 2;
}
upstream="$(git -C "$repo" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null)" || {
  echo "ERROR: no tracking upstream. Set up GitHub first, then git push -u origin $branch." >&2; exit 2;
}
if [[ -n "$(git -C "$repo" status --porcelain --untracked-files=normal)" ]]; then
  echo "ERROR: working tree contains local changes. Commit or stash them first." >&2; exit 2
fi
if [[ "$apply" == 0 ]]; then
  echo "Local: $(git -C "$repo" rev-parse --short HEAD), upstream: $upstream"
  echo "Use --apply to fetch, fast-forward and validate; installed link-mode skills will follow the checkout."
  exit 0
fi
echo "Fetching $upstream..."
git -C "$repo" fetch --prune
if ! git -C "$repo" merge-base --is-ancestor HEAD "$upstream"; then
  echo "ERROR: local and upstream diverged; refusing non-fast-forward merge." >&2; exit 2
fi
current="$(git -C "$repo" rev-parse HEAD)"
new="$(git -C "$repo" rev-parse "$upstream")"
if [[ "$current" == "$new" ]]; then
  echo "Already current."
  exit 0
fi
# Fail before changing the checked-out source if prospective new tree fails basic checks.
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
git -C "$repo" archive "$new" | tar -xf - -C "$tmp"
python3 "$tmp/scripts/validate_skills.py"
python3 "$tmp/scripts/test_install.py"
git -C "$repo" merge --ff-only "$upstream"
echo "Updated to $(git -C "$repo" rev-parse --short HEAD). Symlink installations now use the new revision."
echo "Copied installations must be explicitly reinstalled with scripts/install.py --mode copy --adopt-existing."
