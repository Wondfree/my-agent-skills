#!/usr/bin/env python3
"""Offline, non-mutating tests. The trash subprocess is always mocked."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parent / "app_uninstaller.py"
spec = importlib.util.spec_from_file_location("app_uninstaller", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MatchingTests(unittest.TestCase):
    def test_exact_bundle_and_app_name(self):
        self.assertEqual(module.residue_match("com.example.Editor.plist", "com.example.Editor",
                                              ["Example Editor"], "preferences")[0], "high")
        self.assertEqual(module.residue_match("example-editor", "com.example.Editor",
                                              ["Example Editor"], "app-data")[0], "high")

    def test_substring_not_auto_matched(self):
        self.assertIsNone(module.residue_match("example-editor-backup", "com.example.Editor",
                                               ["Example Editor"], "app-data"))
        self.assertIsNone(module.residue_match("editor", "com.example.Editor",
                                               ["Example Editor"], "app-data"))

    def test_chinese_app_name_and_unicode_identity(self):
        self.assertEqual(module.normalized("微信读书"), "微信读书")
        apps = [{"name": "微信读书", "display_name": "微信读书",
                 "bundle_id": "com.example.reader", "path": "/Applications/微信读书.app"},
                {"name": "每日英语听力", "display_name": "每日英语听力",
                 "bundle_id": "com.example.listen", "path": "/Applications/每日英语听力.app"}]
        self.assertEqual(module.resolve_app(apps, name="微信读书", bundle_id=None)["bundle_id"],
                         "com.example.reader")
        self.assertEqual(module.residue_match("微信读书", "com.example.reader",
                                              ["微信读书"], "app-data")[0], "high")
        self.assertIsNone(module.residue_match("微信读书备份", "com.example.reader",
                                               ["微信读书"], "app-data"))

    def test_owner_check_rejects_other_user(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "candidate"
            target.write_text("x", encoding="utf-8")
            with mock.patch.object(module.os, "getuid", return_value=9999999):
                self.assertFalse(module.allowed_source(target, "preferences", Path(folder)))

    def test_helper_and_shared(self):
        self.assertEqual(module.residue_match("com.example.Editor.helper", "com.example.Editor",
                                              ["Example Editor"], "temp-cache")[0], "high")
        self.assertEqual(module.residue_match("com.example.Editor.helper", "com.example.Editor",
                                              ["Example Editor"], "shared-container")[0], "review")

    def test_large_tree_is_capped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for i in range(3):
                (root / str(i)).write_text("sample", encoding="utf-8")
            with mock.patch.object(module, "MAX_FILES_PER_TARGET", 1):
                summary = module.file_summary(root)
            self.assertTrue(summary["truncated"])
            self.assertLessEqual(summary["files"], 2)

    def test_wrong_area_rejected(self):
        home = Path.home() / "example-home"
        self.assertFalse(module.allowed_source(home / "Library" / "Application Support",
                                               "app-data", home))
        self.assertFalse(module.allowed_source(Path("/Library/LaunchDaemons/com.example.Editor.plist"),
                                               "system-launch-daemon", home))


class TrashSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="app-uninstall-skill-")
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve()
        self.folder = self.home / "Library" / "Preferences"
        self.folder.mkdir(parents=True)
        self.target = self.folder / "com.example.Editor.plist"
        self.target.write_text("pretend preference", encoding="utf-8")
        meta = module.file_summary(self.target)
        self.plan = {
            "schema": module.SCHEMA,
            "app": {"bundle_id": "com.example.Editor", "name": "Example Editor",
                    "display_name": "Example Editor", "path": None},
            "items": [{"id": 1, "path": str(self.target),
                       "category": "preferences", "confidence": "high",
                       "evidence": "exact Bundle ID", **meta}],
            "warnings": [], "scanned_at": "2026-01-01T00:00:00+00:00"
        }
        self.save()
        self.args = mock.Mock(manifest=str(self.manifest), confirm=self.plan["plan_id"], ids="1")

    def save(self):
        self.plan["plan_id"] = module.plan_digest(self.plan)
        self.manifest = self.home / "scan.json"
        self.manifest.write_text(json.dumps(self.plan), encoding="utf-8")

    def call_trash(self):
        with mock.patch.object(module.Path, "home", return_value=self.home):
            return module.trash(self.args)

    def test_valid_plan_only_calls_native_trash_backend(self):
        result = subprocess.CompletedProcess([], 0, "", "")
        with mock.patch.object(module.subprocess, "run", return_value=result) as backend:
            self.assertEqual(self.call_trash(), 0)
            self.assertEqual(backend.call_count, 1)
            self.assertEqual(backend.call_args.args[0][-1], str(self.target))
        self.assertTrue(self.target.exists(), "This test must not delete real or fixture files")

    def test_wrong_plan_id_refused_before_backend(self):
        self.args.confirm = "bad"
        with mock.patch.object(module.subprocess, "run") as backend:
            with self.assertRaisesRegex(ValueError, "Confirmation ID mismatch"):
                self.call_trash()
            backend.assert_not_called()

    def test_changed_file_refused_before_backend(self):
        self.target.write_text("changed", encoding="utf-8")
        with mock.patch.object(module.subprocess, "run") as backend:
            with self.assertRaisesRegex(ValueError, "Target changed"):
                self.call_trash()
            backend.assert_not_called()

    def test_review_only_refused_before_backend(self):
        self.plan["items"][0]["confidence"] = "review"
        self.save()
        self.args.confirm = self.plan["plan_id"]
        with mock.patch.object(module.subprocess, "run") as backend:
            with self.assertRaisesRegex(ValueError, "review-only"):
                self.call_trash()
            backend.assert_not_called()

    def test_apple_system_app_refused_before_backend(self):
        self.plan["app"]["bundle_id"] = "com.apple.Safari"
        self.save()
        self.args.confirm = self.plan["plan_id"]
        with mock.patch.object(module.subprocess, "run") as backend:
            with self.assertRaisesRegex(ValueError, "Apple system bundles"):
                self.call_trash()
            backend.assert_not_called()

    def test_forged_unrelated_filename_refused_before_backend(self):
        unrelated = self.folder / "com.someone.else.plist"
        unrelated.write_text("not this application", encoding="utf-8")
        self.plan["items"][0].update(path=str(unrelated), **module.file_summary(unrelated))
        self.save()
        self.args.confirm = self.plan["plan_id"]
        with mock.patch.object(module.subprocess, "run") as backend:
            with self.assertRaisesRegex(ValueError, "no longer matches application"):
                self.call_trash()
            backend.assert_not_called()

    def test_nested_file_mutation_is_detected_before_backend(self):
        target = self.home / "Library" / "Application Support" / "example-editor"
        target.mkdir(parents=True)
        nested = target / "history.db"
        nested.write_text("AAAA", encoding="utf-8")
        self.plan["items"][0].update(path=str(target), category="app-data",
                                     **module.file_summary(target))
        self.save()
        self.args.confirm = self.plan["plan_id"]
        # Rewrite in place, preserving length and enclosing directory mtime.
        nested.write_text("BBBB", encoding="utf-8")
        with mock.patch.object(module.subprocess, "run") as backend:
            with self.assertRaisesRegex(ValueError, "Directory contents changed"):
                self.call_trash()
            backend.assert_not_called()

    def test_readonly_plan_disallows_symlink_file(self):
        target = self.folder / "com.example.Editor.backup"
        target.symlink_to(self.target)
        self.plan["items"][0].update(path=str(target), **module.file_summary(target))
        self.save()
        self.args.confirm = self.plan["plan_id"]
        with mock.patch.object(module.subprocess, "run") as backend:
            with self.assertRaisesRegex(ValueError, "review-only"):
                self.call_trash()
            backend.assert_not_called()

    def test_manifest_tampering_refused_before_backend(self):
        self.plan["items"][0]["path"] = str(self.home / "wrong")
        self.manifest.write_text(json.dumps(self.plan), encoding="utf-8")
        with mock.patch.object(module.subprocess, "run") as backend:
            with self.assertRaisesRegex(ValueError, "changed manifest"):
                self.call_trash()
            backend.assert_not_called()


if __name__ == "__main__":
    unittest.main()
