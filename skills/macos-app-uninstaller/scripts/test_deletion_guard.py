#!/usr/bin/env python3
"""Read-only regression tests; no destructive commands are executed."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
import os
from pathlib import Path
import plistlib
import shlex
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import app_uninstaller as app
import deletion_guard as guard


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="guard-test-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve()
        self.prefs = self.home / "Library" / "Preferences"
        self.prefs.mkdir(parents=True)
        self.file = self.prefs / "com.example.Reader.plist"
        self.file.write_text("safe", encoding="utf8")

    def check(self, path, category="preferences", bundle="com.example.Reader"):
        return guard.assert_safe_path(str(path), category, self.home, bundle)

    def test_valid_exact_residue_and_quoting(self):
        path = self.check(self.file)
        command = guard.format_manual_command(path)
        self.assertEqual(shlex.split(command),
                         ["rm", "-rf", "--", str(self.file)])
        self.assertEqual(shlex.split(guard.format_manual_command(path, needs_sudo=True)),
                         ["sudo", "rm", "-rf", "--", str(self.file)])
        self.assertTrue(self.file.exists())

    def test_all_protected_roots_and_parent_paths_rejected(self):
        dangerous = ["/", "/System", "/Library", "/Users", "/Applications",
                     "/Volumes", "/private", "/usr", "/etc", "/bin", "/sbin",
                     str(self.home), str(self.home / "Library"),
                     str(self.home / "Applications")]
        for p in dangerous:
            with self.subTest(path=p), self.assertRaises(ValueError):
                self.check(p)

    def test_traversal_shell_syntax_and_incomplete_paths_rejected(self):
        bad = ["", ".", "Library/Preferences/com.example.Reader.plist",
               "//Users", str(self.file) + "/../../..",
               str(self.prefs) + "/./com.example.Reader.plist",
               str(self.prefs) + "/com.example.Reader.plist;whoami",
               str(self.prefs) + "/$(touch unsafe)",
               str(self.prefs) + "/file*", str(self.prefs) + "/file?",
               str(self.prefs) + "/file\ncommand",
               "/Applications/Editor.app/Contents"]
        for p in bad:
            with self.subTest(path=p), self.assertRaises(ValueError):
                self.check(p)

    def test_cross_app_location_shared_and_cloud_rejected(self):
        foreign = self.home / "Library" / "Group Containers" / "group.com.example.Reader"
        foreign.mkdir(parents=True)
        with self.assertRaises(ValueError):
            self.check(foreign, "shared-container")
        with self.assertRaises(ValueError):
            self.check(self.file, "app")
        with self.assertRaises(ValueError):
            self.check(self.file, "sandbox")
        cloud = self.home / "Library" / "Mobile Documents" / "iCloud~com~example~reader"
        cloud.mkdir(parents=True)
        with self.assertRaises(ValueError):
            self.check(cloud, "app-data")
        with self.assertRaises(ValueError):
            self.check("/System/Library/Preferences/com.example.Reader.plist")
        with self.assertRaises(ValueError):
            self.check(self.file, bundle="com.apple.Safari")

    def test_symlink_ancestors_and_target_rejected(self):
        link = self.home / "Library" / "Caches"
        link.symlink_to(self.prefs, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.check(link / self.file.name, "cache")
        other = self.prefs / "com.example.Reader.alias.plist"
        other.symlink_to(self.file)
        with self.assertRaises(ValueError):
            self.check(other)

    def test_missing_path_refused(self):
        with self.assertRaises(ValueError):
            self.check(self.prefs / "com.example.Reader.missing.plist")

    def test_vendor_location_boundaries(self):
        root = self.home / "Applications"
        for relative in ("Vendor", "Vendor/Deep/Reader.app", "Other.app/Reader.app"):
            target = root / relative
            target.mkdir(parents=True, exist_ok=True)
            with self.subTest(path=target), self.assertRaises(ValueError):
                self.check(target, "app")
            self.assertFalse(app.allowed_source(target, "app", self.home))
        outside = self.home / "outside"
        (outside / "Reader.app").mkdir(parents=True)
        (root / "LinkedVendor").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            self.check(root / "LinkedVendor" / "Reader.app", "app")
        self.assertFalse(app.allowed_source(root / "LinkedVendor" / "Reader.app", "app", self.home))

    def test_new_categories_require_exact_parent(self):
        for category in ("cookies", "application-scripts", "byhost-preferences"):
            with self.subTest(category=category), self.assertRaises(ValueError):
                self.check(self.file, category)


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="preview-test-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve()
        self.folder = self.home / "Library" / "Preferences"
        self.folder.mkdir(parents=True)
        self.target = self.folder / "com.example.Reader.plist"
        self.target.write_text("user data", encoding="utf8")
        self.plan = {
            "schema": app.SCHEMA,
            "app": {"bundle_id": "com.example.Reader", "name": "Example Reader",
                    "display_name": "Example Reader", "path": None},
            "items": [{"id": 1, "path": str(self.target),
                       "category": "preferences", "confidence": "high",
                       "evidence": "exact Bundle ID",
                       **app.file_summary(self.target)}],
            "warnings": [], "scanned_at": "2026-01-01T00:00:00+00:00",
        }
        self.manifest = self.home / "plan.json"
        self.save()

    def save(self):
        self.plan["plan_id"] = app.plan_digest(self.plan)
        self.manifest.write_text(json.dumps(self.plan), encoding="utf8")

    def preview(self, ids="1", confirm=None):
        args = mock.Mock(manifest=str(self.manifest),
                         confirm=confirm or self.plan["plan_id"], ids=ids)
        out = io.StringIO()
        err = io.StringIO()
        with mock.patch.object(app.Path, "home", return_value=self.home), \
             redirect_stdout(out), redirect_stderr(err), \
             mock.patch.object(app.subprocess, "run") as backend:
            result = app.manual_preview(args)
            backend.assert_not_called()
        return result, out.getvalue()

    def test_valid_preview_is_read_only(self):
        result, output = self.preview()
        self.assertEqual(result, 0)
        self.assertEqual(shlex.split(output.strip()),
                         ["rm", "-rf", "--", str(self.target)])
        self.assertTrue(self.target.exists())

    def test_manifest_id_and_changed_file_guard(self):
        with self.assertRaisesRegex(ValueError, "Confirmation ID"):
            self.preview(confirm="wrong")
        self.target.write_text("updated", encoding="utf8")
        with self.assertRaisesRegex(ValueError, "changed since scan"):
            self.preview()

    def test_review_and_truncated_items_refused(self):
        self.plan["items"][0]["confidence"] = "review"
        self.save()
        with self.assertRaisesRegex(ValueError, "Review-only"):
            self.preview()
        self.plan["items"][0]["confidence"] = "high"
        self.plan["items"][0]["truncated"] = True
        self.save()
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            self.preview()

    def test_mixed_batch_does_not_print_partial_command(self):
        self.plan["items"].append({
            "id": 2, "path": "/", "category": "preferences",
            "confidence": "high", "evidence": "bogus",
            **app.file_summary(self.target)})
        self.save()
        output = io.StringIO()
        args = mock.Mock(manifest=str(self.manifest),
                         confirm=self.plan["plan_id"], ids="1,2")
        with mock.patch.object(app.Path, "home", return_value=self.home), \
             redirect_stdout(output), \
             self.assertRaisesRegex(ValueError, "Protected|outside"):
            app.manual_preview(args)
        self.assertEqual(output.getvalue(), "")

    def test_review_app_requires_info_plist_identity(self):
        installed = self.home / "Applications" / "Example Reader.app"
        contents = installed / "Contents"
        contents.mkdir(parents=True)
        with (contents / "Info.plist").open("wb") as f:
            plistlib.dump({"CFBundleIdentifier": "com.example.Reader"}, f)
        self.plan["app"]["path"] = str(installed)
        self.plan["items"][0].update(
            path=str(installed), category="app", confidence="review",
            **app.file_summary(installed))
        self.save()
        self.assertEqual(self.preview()[0], 0)
        with (contents / "Info.plist").open("wb") as f:
            plistlib.dump({"CFBundleIdentifier": "com.other.Reader"}, f)
        self.save()
        with self.assertRaisesRegex(ValueError, "changed|identity"):
            self.preview()

    def test_uuid_identity_is_rechecked(self):
        sandbox = self.home / "Library" / "Containers" / "FE841D49-E3B6-4F86-ADE8-0976E13186D8"
        sandbox.mkdir(parents=True)
        self.plan["items"][0].update(
            path=str(sandbox), category="sandbox",
            **app.file_summary(sandbox))
        self.save()
        with mock.patch.object(app, "owned_uuid_container", return_value=False):
            with self.assertRaisesRegex(ValueError, "Sandbox identity mismatch"):
                self.preview()
        with mock.patch.object(app, "owned_uuid_container", return_value=True):
            self.assertEqual(self.preview()[0], 0)

    def test_root_owned_app_preview_uses_sudo(self):
        installed = self.home / "Applications" / "Vendor" / "Example Reader.app"
        contents = installed / "Contents"
        contents.mkdir(parents=True)
        with (contents / "Info.plist").open("wb") as fp:
            plistlib.dump({"CFBundleIdentifier": "com.example.Reader"}, fp)
        original_lstat = Path.lstat

        def root_owned(path, *args, **kwargs):
            stat = original_lstat(path, *args, **kwargs)
            if path == installed:
                values = {name: getattr(stat, name) for name in dir(stat) if name.startswith("st_")}
                values["st_uid"] = 0
                return SimpleNamespace(**values)
            return stat

        with mock.patch.object(Path, "lstat", root_owned), \
             mock.patch.object(app.os, "getuid", return_value=501):
            self.plan["app"]["path"] = str(installed)
            self.plan["items"][0].update(path=str(installed), category="app", confidence="review",
                                         **app.file_summary(installed))
            self.save()
            result, output = self.preview()
        self.assertEqual(result, 0)
        self.assertEqual(shlex.split(output.strip()), ["sudo", "rm", "-rf", "--", str(installed)])


if __name__ == "__main__":
    unittest.main()
