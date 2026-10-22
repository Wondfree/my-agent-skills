#!/usr/bin/env python3
"""Offline wizard tests: mocked terminal, disposable HOME, no agents."""
from __future__ import annotations

import ast
from contextlib import redirect_stdout, redirect_stderr
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import install
import install_wizard as wizard
import installer_i18n as i18n


class WizardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {
            "HOME": str(self.root), "CODEX_HOME": str(self.root / "codex"),
            "CLAUDE_CONFIG_DIR": str(self.root / "claude"),
            "SKILLS_TARGET_DIR": str(self.root / "skills"),
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        # Baseline tests are language-independent even on a Chinese macOS host.
        self.default_lang = patch.object(wizard, "detect_language", return_value="en")
        self.default_lang.start()
        self.addCleanup(self.default_lang.stop)

    def run_wizard(self, names=(), clients=(), final="y", flags=(), tty=True):
        # The revised wizard asks only for entries that are not installed.
        mode = flags[flags.index("--mode") + 1] if "--mode" in flags else "link"
        custom_target = flags[flags.index("--target-dir") + 1] if "--target-dir" in flags else None
        target_dir = install.destination_dir(custom_target)
        answers = []
        for name, source in install.available_skills().items():
            state, _ = wizard.inspect_entry(target_dir / name, source, mode)
            if state == "new":
                answers.append("y" if name in names else "")
        for name, target in install.instructions_targets(None, None):
            state, _ = wizard.inspect_entry(target, install.GLOBAL_RULE, mode)
            if state == "new":
                answers.append("y" if name.split("-")[0] in clients else "")
        answers.append(final)
        output = io.StringIO()
        with redirect_stdout(output), patch("sys.stdin.isatty", return_value=tty), patch("sys.stdout.isatty", return_value=tty), patch("builtins.input", side_effect=answers), redirect_stderr(output):
            result = wizard.main(list(flags))
        return result, output.getvalue()

    def test_select_and_independent_clients(self):
        code, out = self.run_wizard(["reuse-first"], ["claude"])
        self.assertEqual(code, 0)
        self.assertIn("Installation summary", out)
        self.assertTrue((self.root / "skills/reuse-first").is_symlink())
        self.assertFalse((self.root / "skills/git-lifecycle").exists())
        self.assertTrue((self.root / "claude/CLAUDE.md").is_symlink())
        self.assertFalse((self.root / "codex").exists())
        code, _ = self.run_wizard(clients=["codex"])
        self.assertEqual(code, 0)
        self.assertTrue((self.root / "codex/AGENTS.md").is_symlink())

    def test_skip_cancel_abort_and_dry_run(self):
        for final, flags in (("", ()), ("q", ()), ("y", ("--dry-run",))):
            code, _ = self.run_wizard(["git-lifecycle"], final=final, flags=flags)
            self.assertEqual(code, 0)
            self.assertEqual(list(self.root.iterdir()), [])
        self.assertEqual(self.run_wizard()[0], 0)
        with redirect_stdout(io.StringIO()), patch("sys.stdin.isatty", return_value=True), patch("sys.stdout.isatty", return_value=True), patch("builtins.input", side_effect=EOFError):
            self.assertEqual(wizard.main([]), 0)

    def test_conflict_private_content_never_printed(self):
        target = self.root / "claude/CLAUDE.md"
        target.parent.mkdir()
        target.write_text("PRIVATE_SENTINEL")
        code, out = self.run_wizard(["reuse-first"], ["claude"])
        self.assertEqual(code, 0)
        self.assertNotIn("PRIVATE_SENTINEL", out)
        self.assertIn("Existing configuration needs review", out)
        self.assertIn("Other entries needing review: 1", out)
        self.assertEqual(target.read_text(), "PRIVATE_SENTINEL")
        self.assertTrue((self.root / "skills/reuse-first").is_symlink())
        self.assertFalse((target.parent / ".instruction-backups").exists())
        output = io.StringIO()
        with patch.object(Path, "read_text", side_effect=AssertionError("must not read")), redirect_stdout(output):
            self.assertEqual(wizard.main(["--review-path", str(target)]), 0)
        self.assertIn(str(target), output.getvalue())
        self.assertIn("explicit consent", output.getvalue())
        self.assertNotIn("PRIVATE_SENTINEL", output.getvalue())

    def test_non_tty(self):
        with self.assertRaises(SystemExit) as error:
            self.run_wizard(["reuse-first"], tty=False)
        self.assertEqual(error.exception.code, 2)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_override_and_status(self):
        codex = self.root / "codex"
        codex.mkdir()
        (codex / "AGENTS.override.md").write_text("private override")
        code, out = self.run_wizard(clients=["codex"])
        self.assertEqual(code, 0)
        self.assertIn("Existing Codex override may shadow these rules", out)
        self.assertIn("AGENTS.override.md", out)
        self.assertFalse((codex / "AGENTS.md").exists())
        self.run_wizard(["reuse-first"])
        code, out = self.run_wizard(["reuse-first"])
        self.assertEqual(code, 0)
        self.assertIn("Already installed", out)

    def test_custom_consumer_copy_and_preview(self):
        target = self.root / "consumer skills"
        flags = ("--target-dir", str(target), "--mode", "copy")
        self.assertEqual(self.run_wizard(["git-lifecycle"], flags=(*flags, "--dry-run"))[0], 0)
        self.assertFalse(target.exists())
        code, out = self.run_wizard(["git-lifecycle"], flags=flags)
        self.assertEqual(code, 0)
        self.assertIn("does not activate automatic Git checks", out)
        self.assertTrue((target / "git-lifecycle/SKILL.md").is_file())
        self.assertFalse((target / "git-lifecycle").is_symlink())
        self.assertFalse((self.root / "skills").exists())

    def test_client_option_requires_instructions(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            install.main(["--instruction-clients", "codex"])
        self.assertEqual(error.exception.code, 2)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_interruption_after_install_begins_reports_partial_state(self):
        marker = self.root / "partial-change"

        def interrupted_install(argv):
            if "--dry-run" in argv:
                return 0
            marker.write_text("installed first entry")
            raise KeyboardInterrupt

        with patch.object(install, "main", side_effect=interrupted_install):
            code, out = self.run_wizard(["reuse-first"])
        self.assertEqual(code, 130)
        self.assertIn("some entries may already have changed", out)
        self.assertNotIn("no installation requested", out)
        self.assertEqual(marker.read_text(), "installed first entry")

    def test_unreadable_unselected_global_does_not_block_skills(self):
        original = install.describe_target

        def unreadable_claude(target, source, mode):
            if target.name == "CLAUDE.md":
                raise PermissionError("private simulated config")
            return original(target, source, mode)

        with patch.object(install, "describe_target", side_effect=unreadable_claude):
            code, out = self.run_wizard(["reuse-first"])
        self.assertEqual(code, 0)
        self.assertIn("Unable to inspect; review required", out)
        self.assertTrue((self.root / "skills/reuse-first").is_symlink())

        with patch.object(install, "describe_target", side_effect=unreadable_claude):
            code, out = self.run_wizard(clients=["claude"])
        self.assertEqual(code, 0)
        self.assertIn("Unable to inspect; review required", out)
        self.assertFalse((self.root / "claude/CLAUDE.md").exists())

    def test_original_regression_isolated(self):
        call = subprocess.run([sys.executable, "-B", str(install.ROOT / "scripts/test_install.py")], capture_output=True, text=True)
        self.assertEqual(call.returncode, 0, call.stderr)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_chinese_wizard_preview_and_default_skip(self):
        code, out = self.run_wizard(["reuse-first"], ["claude"], flags=("--lang", "zh-CN", "--dry-run"))
        self.assertEqual(code, 0)
        for expected in ("Skills 安装目录", "安装摘要", "仅为预览", "将安装"):
            self.assertIn(expected, out)
        self.assertNotIn("Local deterministic preview", out)
        self.assertNotIn("Select this Skill?", out)
        self.assertFalse((self.root / "skills").exists())
        self.assertFalse((self.root / "claude").exists())

    def test_chinese_wizard_install_with_explicit_selection(self):
        code, out = self.run_wizard(["reuse-first"], ["codex"], flags=("--lang", "zh-CN"))
        self.assertEqual(code, 0)
        self.assertIn("已安装", out)
        self.assertTrue((self.root / "skills/reuse-first").is_symlink())
        self.assertTrue((self.root / "codex/AGENTS.md").is_symlink())
        self.assertFalse((self.root / "claude").exists())
        self.assertFalse((self.root / "skills/git-lifecycle").exists())

    def test_chinese_conflict_is_blocked_and_private_data_not_leaked(self):
        target = self.root / "claude/CLAUDE.md"
        target.parent.mkdir()
        target.write_text("PRIVATE_SENTINEL")
        code, out = self.run_wizard(["reuse-first"], ["claude"], flags=("--lang", "zh-CN"))
        self.assertEqual(code, 0)
        self.assertIn("已有全局规则，切换前需要审查", out)
        self.assertNotIn("REFUSED:", out)
        self.assertNotIn("PRIVATE_SENTINEL", out)
        self.assertEqual(target.read_text(), "PRIVATE_SENTINEL")
        self.assertTrue((self.root / "skills/reuse-first").is_symlink())

    def test_review_handoff_is_localized_and_path_only(self):
        target = self.root / "claude/CLAUDE.md"
        for language, phrase, missing in (
            ("zh-CN", "明确同意", "Human-invoked AI review"),
            ("en", "explicitly consent", "候选源路径"),
        ):
            output = io.StringIO()
            with patch.object(Path, "read_text", side_effect=AssertionError("must not read")):
                with redirect_stdout(output):
                    self.assertEqual(wizard.main(["--lang", language, "--review-path", str(target)]), 0)
            self.assertIn(phrase, output.getvalue())
            self.assertNotIn(missing, output.getvalue())
            self.assertIn(str(target), output.getvalue())

    def test_chinese_help_and_language_detection(self):
        with redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(SystemExit) as result:
                wizard.main(["--lang", "zh-CN", "--help"])
        self.assertEqual(result.exception.code, 0)
        self.assertIn("显示此帮助信息", output.getvalue())
        self.assertIn("--lang", output.getvalue())

        class Completed:
            returncode = 0
            stdout = '(\n    "zh-Hans-CN",\n    "en-US"\n)'
        with patch.dict(os.environ, {"LC_ALL": "", "LC_MESSAGES": "", "LANG": "en_US.UTF-8"}):
            with patch.object(i18n.sys, "platform", "darwin"):
                with patch.object(i18n.subprocess, "run", return_value=Completed()) as run:
                    self.assertEqual(i18n.detect_language(), "zh-CN")
                    self.assertEqual(wizard.language_from_args([], default=i18n.detect_language), "zh-CN")
                    self.assertEqual(run.call_count, 2)
                with patch.dict(os.environ, {"LC_MESSAGES": "en_US.UTF-8"}):
                    self.assertEqual(i18n.detect_language(), "en")
                    self.assertEqual(wizard.language_from_args(["--lang", "zh-CN"], default=i18n.detect_language), "zh-CN")
        with patch.object(i18n.sys, "platform", "linux"):
            with patch.dict(os.environ, {"LC_ALL": "", "LC_MESSAGES": "", "LANG": "zh_CN.UTF-8"}):
                self.assertEqual(i18n.detect_language(), "zh-CN")
            with patch.dict(os.environ, {"LC_ALL": "", "LC_MESSAGES": "", "LANG": "ja_JP.UTF-8"}):
                self.assertEqual(i18n.detect_language(), "en")

    def test_installer_chinese_help_and_errors(self):
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as result:
            install.main(["--lang", "zh-CN", "--help"])
        self.assertEqual(result.exception.code, 0)
        self.assertIn("用法：", output.getvalue())
        self.assertIn("默认只处理 Skills", output.getvalue())
        self.assertIn("只安装全局规则", output.getvalue())
        self.assertNotIn("Output language", output.getvalue())
        output = io.StringIO()
        with redirect_stderr(output), self.assertRaises(SystemExit) as result:
            install.main(["--lang", "zh-CN", "--not-a-real-flag"])
        self.assertEqual(result.exception.code, 2)
        self.assertIn("用法：", output.getvalue())
        self.assertIn("无法识别的参数", output.getvalue())

    def test_installer_chinese_and_legacy_english(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(install.main(["--lang", "zh-CN", "--only", "reuse-first",
                                           "--dry-run"]), 0)
        self.assertIn("[试运行]", output.getvalue())
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(install.main(["--only", "reuse-first", "--dry-run"]), 0)
        self.assertIn("[dry-run]", output.getvalue())

    def test_plain_language_summaries_come_from_skill_source(self):
        base = install.available_skills()["reuse-first"]
        description = wizard.skill_description(base, "en")
        chinese = wizard.skill_description(base, "zh-CN")
        self.assertIn("existing solutions", description)
        self.assertIn("现有方案", chinese)
        self.assertNotIn("Apply this before", description)
        self.assertIn("Description unavailable", wizard.skill_description(self.root / "missing", "en"))
        code, out = self.run_wizard(["reuse-first"], flags=("--dry-run",))
        self.assertEqual(code, 0)
        self.assertIn("Install", out)
        self.assertIn("New Skills selected: 1", out)
        self.assertIn("New global settings selected: 0", out)
        self.assertIn("Preview only: no files will be installed.", out)
        self.assertNotIn("[dry-run] reuse-first:", out)
        self.assertNotIn("Local deterministic preview", out)
        self.assertFalse((self.root / "skills").exists())

    def test_plain_language_summary_with_existing_and_conflict(self):
        self.run_wizard(["reuse-first"])
        code, out = self.run_wizard(["reuse-first"], flags=("--dry-run",))
        self.assertEqual(code, 0)
        self.assertIn("Already installed from this checkout: 1", out)
        self.assertIn("New Skills selected: 0", out)
        self.assertIn("No new items selected", out)
        target = self.root / "claude/CLAUDE.md"
        target.parent.mkdir()
        target.write_text("PRIVATE_SENTINEL")
        code, out = self.run_wizard(clients=["claude"], flags=("--lang", "zh-CN", "--dry-run"))
        self.assertEqual(code, 0)
        self.assertIn("待审查的其他项目：1", out)
        self.assertIn("已有全局规则，切换前需要审查", out)
        self.assertIn("没有选择新安装项", out)
        self.assertNotIn("PRIVATE_SENTINEL", out)
        self.assertEqual(target.read_text(), "PRIVATE_SENTINEL")

    def test_presentation_copy_is_english_and_chinese(self):
        for lang, expected, absent in (
            ("en", "Help your AI assistant check existing solutions", "帮助 AI 优先"),
            ("zh-CN", "帮助 AI 优先检查现有方案", "Help your AI assistant check"),
        ):
            code, out = self.run_wizard(["reuse-first"], flags=("--lang", lang, "--dry-run"))
            self.assertEqual(code, 0)
            self.assertIn(expected, out)
            self.assertNotIn(absent, out)
            self.assertIn("reuse-first", out)
            self.assertNotIn("PRIVATE_SENTINEL", out)

    def test_install_method_is_explained_in_both_languages(self):
        for lang, mode, expected, side_effect in (
            ("en", "link", "Installation method: Links to this local repository",
             "Global rule updates still require separate approval"),
            ("en", "copy", "Installation method: Independent copies",
             "reinstall explicitly"),
            ("zh-CN", "link", "安装方式：链接到本地仓库文件",
             "全局规则的仓库更新仍需单独审批"),
            ("zh-CN", "copy", "安装方式：独立复制",
             "复制后的文件不会随仓库更新而变化"),
        ):
            flags = ("--lang", lang, "--mode", mode, "--dry-run")
            code, out = self.run_wizard(["reuse-first"], flags=flags)
            self.assertEqual(code, 0)
            self.assertIn(expected, out)
            self.assertIn(side_effect, out)
            self.assertFalse((self.root / "skills").exists())

    def test_dynamic_terminal_controls_are_escaped_without_mutating_paths(self):
        self.assertEqual(wizard.safe_display("name\x1b[2J\nnext\u202e"),
                         "name\\x1b[2J\\nnext\\u202e")
        raw_target = self.root / ("target\x1b[2J\nFake approval")
        flags = ("--target-dir", str(raw_target), "--dry-run")
        code, out = self.run_wizard(["reuse-first"], flags=flags)
        self.assertEqual(code, 0)
        self.assertNotIn("\x1b", out)
        self.assertIn("\\x1b", out)
        self.assertNotIn("\nFake approval", out)
        self.assertIn("\\nFake approval", out)
        self.assertFalse(raw_target.exists())

        # Installer refusal contains the same untrusted target: its stderr must
        # also be safe, not only wizard labels and plan summaries.
        conflicted = raw_target / "reuse-first"
        conflicted.mkdir(parents=True)
        code, out = self.run_wizard(["reuse-first"], flags=flags)
        self.assertEqual(code, 0)
        self.assertNotIn("\x1b", out)
        self.assertIn("\\x1b", out)
        self.assertIn("Existing installation needs review", out)
        self.assertFalse((conflicted / ".skill-backups").exists())

        # A third-party Skill description that contains escape sequences must
        # never be able to overwrite the visible confirmation screen.
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            (source / "SKILL.md").write_text(
                "---\nname: malicious\n---\n# Malicious\n"
                "Harmless words \x1b[2J\rFAKE APPROVED.\n")
            original = wizard.skill_description(source, "en")
            self.assertIn("\x1b", original)
            rendered = wizard.safe_display(original)
            self.assertNotIn("\x1b", rendered)
            self.assertIn("\\x1b", rendered)

    def test_unrecognized_argument_controls_are_escaped_both_languages(self):
        for lang in ("en", "zh-CN"):
            err = io.StringIO()
            token = "--bad-arg\\x1b[2J\\nFAKE APPROVED".encode("utf-8").decode("unicode_escape")
            with redirect_stderr(err), self.assertRaises(SystemExit) as result:
                wizard.main(["--lang", lang, token])
            self.assertEqual(result.exception.code, 2)
            output = err.getvalue()
            self.assertNotIn("\\x1b".encode().decode("unicode_escape"), output)
            self.assertNotIn("\nFAKE APPROVED", output)
            self.assertIn("\\x1b", output)
            self.assertIn("\\nFAKE APPROVED", output)

    def test_real_installer_output_escapes_embedded_newlines(self):
        target = self.root / ("path\\x1b[2J\\nFAKE APPROVED".encode().decode("unicode_escape"))
        code, out = self.run_wizard(["reuse-first"], flags=("--target-dir", str(target)))
        self.assertEqual(code, 0)
        self.assertTrue((target / "reuse-first").is_symlink())
        self.assertNotIn("\nFAKE APPROVED", out)
        self.assertNotIn("\\x1b".encode().decode("unicode_escape"), out)
        self.assertIn("\\x1b", out)
        self.assertIn("\\nFAKE APPROVED", out)

    def test_installer_argument_error_keeps_readable_lines(self):
        codex = self.root / "codex"
        codex.mkdir()
        (codex / "AGENTS.override.md").write_text("private override")
        for lang in ("en", "zh-CN"):
            err = io.StringIO()
            with redirect_stderr(err), self.assertRaises(SystemExit) as result:
                install.main(["--lang", lang, "--instructions-only",
                              "--instruction-clients", "codex"])
            self.assertEqual(result.exception.code, 2)
            message = err.getvalue()
            self.assertGreaterEqual(len(message.splitlines()), 2)
            self.assertIn("AGENTS.override.md", message)
            self.assertIn("用法：" if lang == "zh-CN" else "usage:", message)
            self.assertNotIn("\\n", message)

    def test_broken_codex_override_is_review_only(self):
        codex = self.root / "codex"
        codex.mkdir()
        (codex / "AGENTS.md").symlink_to(install.GLOBAL_RULE)
        override = codex / "AGENTS.override.md"
        override.symlink_to(self.root / "not-present")
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output), (
            patch("sys.stdin.isatty", return_value=True)
        ), patch("sys.stdout.isatty", return_value=True), (
            patch("builtins.input", side_effect=lambda prompt: "")
        ):
            result = wizard.main(["--lang", "en", "--dry-run"])
        self.assertEqual(result, 0)
        self.assertIn("Existing Codex override may shadow these rules", output.getvalue())
        self.assertIn("Other entries needing review: 1", output.getvalue())
        self.assertEqual(override.readlink(), self.root / "not-present")

    def test_other_checkout_codex_link_with_override_stays_untouched(self):
        codex = self.root / "codex"
        codex.mkdir()
        old_rule = self.root / "other-checkout" / "rules" / "agent-global.md"
        old_rule.parent.mkdir(parents=True)
        old_rule.write_text("SENSITIVE_PRIVATE_RULES")
        global_entry = codex / "AGENTS.md"
        global_entry.symlink_to(old_rule)
        override = codex / "AGENTS.override.md"
        override.write_text("OVERRIDE_PRIVATE")
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output), (
            patch("sys.stdin.isatty", return_value=True)
        ), patch("sys.stdout.isatty", return_value=True), (
            patch("builtins.input", side_effect=lambda prompt: "")
        ):
            result = wizard.main(["--lang", "zh-CN", "--dry-run"])
        self.assertEqual(result, 0)
        self.assertIn("发现 Codex 覆盖规则文件", output.getvalue())
        self.assertIn("待审查的其他项目：1", output.getvalue())
        self.assertIn(str(old_rule), output.getvalue())
        self.assertNotIn("SENSITIVE_PRIVATE_RULES", output.getvalue())
        self.assertNotIn("OVERRIDE_PRIVATE", output.getvalue())
        self.assertEqual(global_entry.readlink(), old_rule)
        self.assertEqual(override.read_text(), "OVERRIDE_PRIVATE")

    def test_existing_global_link_shadowed_by_override_is_not_reported_healthy(self):
        codex = self.root / "codex"
        codex.mkdir()
        global_entry = codex / "AGENTS.md"
        global_entry.symlink_to(install.GLOBAL_RULE)
        (codex / "AGENTS.override.md").write_text("LOCAL_OVERRIDE_PRIVATE")
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output), (
            patch("sys.stdin.isatty", return_value=True)
        ), patch("sys.stdout.isatty", return_value=True), (
            patch("builtins.input", side_effect=lambda prompt: "")
        ):
            code = wizard.main(["--lang", "zh-CN", "--dry-run"])
        self.assertEqual(code, 0)
        shown = output.getvalue()
        self.assertIn("发现 Codex 覆盖规则文件", shown)
        self.assertIn("AGENTS.override.md", shown)
        self.assertIn("待审查的其他项目：1", shown)
        self.assertNotIn("LOCAL_OVERRIDE_PRIVATE", shown)
        self.assertEqual(global_entry.readlink(), install.GLOBAL_RULE)
        self.assertEqual((codex / "AGENTS.override.md").read_text(), "LOCAL_OVERRIDE_PRIVATE")

    def test_another_checkout_links_are_retained_without_any_questions(self):
        # Reproduces an installed main checkout inspected from a second worktree.
        old_checkout = self.root / "main-checkout"
        target_dir = self.root / "skills"
        target_dir.mkdir()
        for name in install.available_skills():
            original = old_checkout / "skills" / name
            original.mkdir(parents=True)
            (original / "SKILL.md").write_text("PREEXISTING PRIVATE DATA")
            (target_dir / name).symlink_to(original, target_is_directory=True)
        old_global = old_checkout / "rules" / "agent-global.md"
        old_global.parent.mkdir(parents=True)
        old_global.write_text("PRIVATE_GLOBAL_RULES")
        for _, target in install.instructions_targets(None, None):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(old_global)
        rendered = io.StringIO()
        with patch.object(Path, "read_bytes", side_effect=AssertionError("no content comparison")), (
            redirect_stdout(rendered)
        ), patch("sys.stdin.isatty", return_value=True), (
            patch("sys.stdout.isatty", return_value=True)
        ), patch("builtins.input", side_effect=AssertionError("already installed items must not ask")):
            result = wizard.main(["--lang", "zh-CN", "--dry-run"])
        self.assertEqual(result, 0)
        output = rendered.getvalue()
        self.assertIn("其他来源的已安装项：7", output)
        self.assertIn("没有选择新安装项", output)
        self.assertIn("当前链接目标", output)
        self.assertIn(str(old_checkout), output)
        self.assertNotIn("PRIVATE_GLOBAL_RULES", output)
        for name in install.available_skills():
            self.assertEqual((target_dir / name).readlink(),
                             old_checkout / "skills" / name)
        for _, target in install.instructions_targets(None, None):
            self.assertEqual(target.readlink(), old_global)

    def test_existing_link_different_mode_is_not_silently_switched(self):
        src = install.available_skills()["reuse-first"]
        target = self.root / "skills/reuse-first"
        target.parent.mkdir()
        target.symlink_to(src, target_is_directory=True)
        state, linked_to = wizard.inspect_entry(target, src, "copy")
        self.assertEqual(state, "linked_other_mode")
        self.assertEqual(linked_to, src)
        result, output = self.run_wizard(["reuse-first"], flags=("--mode", "copy", "--dry-run"))
        self.assertEqual(result, 0)
        self.assertIn("Already linked — requested install method differs", output)
        self.assertTrue(target.is_symlink())
        self.assertEqual(target.readlink(), src)

    def test_broken_link_is_kept_for_review_and_fresh_skill_is_installable(self):
        target = self.root / "skills/reuse-first"
        target.parent.mkdir()
        target.symlink_to(self.root / "missing-source")
        result, output = self.run_wizard(["skill-reviewer"], ["claude"])
        self.assertEqual(result, 0)
        self.assertIn("Broken link needs review", output)
        self.assertTrue(target.is_symlink())
        self.assertEqual(target.readlink(), self.root / "missing-source")
        self.assertTrue((self.root / "skills/skill-reviewer").is_symlink())
        self.assertTrue((self.root / "claude/CLAUDE.md").is_symlink())

    def test_installation_prompts_only_for_fresh_items(self):
        # An exact install, a preexisting arbitrary file, and a fresh Skill
        # must not share a single ambiguous yes/no question.
        target_dir = self.root / "skills"
        target_dir.mkdir()
        (target_dir / "git-lifecycle").mkdir()
        (target_dir / "reuse-first").symlink_to(install.available_skills()["reuse-first"],
                                                target_is_directory=True)
        answers = []
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output), (
            patch("sys.stdin.isatty", return_value=True)
        ), patch("sys.stdout.isatty", return_value=True), (
            patch("builtins.input", side_effect=lambda prompt: answers.append(prompt) or "")
        ):
            result = wizard.main(["--lang", "en", "--dry-run"])
        self.assertEqual(result, 0)
        questions = " ".join(answers)
        self.assertNotIn("Install git-lifecycle?", questions)
        self.assertNotIn("Install reuse-first?", questions)
        self.assertIn("Install skill-reviewer?", questions)
        self.assertIn("Already installed from this checkout", output.getvalue())
        self.assertIn("Existing installation needs review", output.getvalue())

    def test_python39_syntax(self):
        for name in ("install.py", "installer_i18n.py", "install_wizard.py", "test_install_wizard.py"):
            ast.parse((install.ROOT / "scripts" / name).read_text(), feature_version=(3, 9))


if __name__ == "__main__":
    unittest.main()
