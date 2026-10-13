"""Fail-closed, read-only path guard for macOS application uninstall plans.

No filesystem deletion or shell execution is performed in this module.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import shlex

_UUID = re.compile(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}\Z")
_BUNDLE = re.compile(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+\Z")
_TEMP_CACHE = re.compile(r"/private/var/folders/[^/]+/[^/]+/C/[^/]+\Z")
_USER_LOCATIONS = {
    "app-data": "Application Support",
    "cache": "Caches",
    "preferences": "Preferences",
    "logs": "Logs",
    "sandbox": "Containers",
    "saved-state": "Saved Application State",
    "http-storage": "HTTPStorages",
    "webkit": "WebKit",
}
_FORBIDDEN_PARTS = {"sharedfilelist", "recent documents", "mobile documents", "cloudstorage"}
# A full shell-quoted name can safely contain spaces and apostrophes, but we
# deliberately refuse active shell syntax/globs rather than trying to interpret it.
_UNSAFE_NAME = re.compile(r"[\x00-\x1f\x7f*?\[\]`$;|&<>\\\"]")


def assert_safe_path(raw: str, category: str, home: Path, bundle_id: str) -> Path:
    """Return an exact candidate or raise before any delete command is produced.

    This is a structural allowlist. The caller must independently verify item
    identity, current metadata, manifest integrity, and human approval.
    """
    if not isinstance(raw, str) or not raw.startswith("/") or raw.startswith("//"):
        raise ValueError("Unsafe deletion path: expected one absolute path")
    if os.path.normpath(raw) != raw or _UNSAFE_NAME.search(raw):
        raise ValueError("Unsafe deletion path: noncanonical or shell-special path")
    if not _BUNDLE.fullmatch(bundle_id) or bundle_id.casefold().startswith("com.apple."):
        raise ValueError("Unsafe application identity")
    path = Path(raw)
    home_text = str(home)
    if not home.is_absolute() or os.path.normpath(home_text) != home_text:
        raise ValueError("Invalid home directory")
    # The actual home is supplied by Path.home() in the CLI. Its location
    # can vary, so check protected roots and enforce exact child locations.
    if home_text in ("/", "/System", "/Library", "/Users", "/Applications",
                     "/Volumes", "/private", "/private/var", "/usr", "/etc"):
        raise ValueError("Protected root cannot be used as a user home")

    if any(part.casefold() in _FORBIDDEN_PARTS for part in path.parts):
        raise ValueError("Sensitive or cloud-synced directory is excluded")
    if raw in ("/", "/Applications", "/Users", "/System", "/Library", "/Volumes",
               "/private", "/private/var", "/usr", "/bin", "/sbin", "/etc",
               home_text, home_text + "/Library", home_text + "/Applications"):
        raise ValueError("Protected root or parent directory")

    if category == "app":
        if path.parent not in (Path("/Applications"), home / "Applications"):
            raise ValueError("App outside permitted Applications location")
        if path.suffix.casefold() != ".app" or not path.stem.strip():
            raise ValueError("Invalid app bundle target")
    elif category == "temp-cache":
        if not _TEMP_CACHE.fullmatch(raw):
            raise ValueError("Cache outside permitted macOS cache directory")
    elif category in _USER_LOCATIONS:
        if path.parent != home / "Library" / _USER_LOCATIONS[category]:
            raise ValueError("Residue outside its exact approved category")
        if category == "sandbox":
            if path.name.casefold() != bundle_id.casefold() and not _UUID.fullmatch(path.name):
                raise ValueError("Sandbox name is neither Bundle ID nor UUID")
    else:
        # Includes Group Containers, system areas, LaunchAgents and review-only
        # resources. No automatic manual-command generation for shared paths.
        raise ValueError("Unapproved or shared resource category")

    # Check every existing path component; never follow a symlink even if
    # it points back into an allowed subtree. Require exact current existence.
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError("Symlink in deletion path")
    if not path.exists():
        raise ValueError("Deletion target no longer exists")
    if os.path.realpath(raw) != raw:
        raise ValueError("Deletion path resolves to another location")
    return path


def format_manual_command(path: Path) -> str:
    """Generate a user-visible command; never run it."""
    return "sudo rm -rf -- " + shlex.quote(str(path))
