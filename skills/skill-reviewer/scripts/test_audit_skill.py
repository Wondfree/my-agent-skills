#!/usr/bin/env python3
"""Offline regression fixtures for the audit CLI and repository validator."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
AUDIT_SCRIPT = ROOT / "skills/skill-reviewer/scripts/audit_skill.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = load_module("audit_under_test", AUDIT_SCRIPT)
validator = load_module("validator_under_test", ROOT / "scripts/validate_skills.py")


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="skill-audit-test-")
        self.addCleanup(self.temp.cleanup)
        self.target = Path(self.temp.name) / "fixture"
        self.target.mkdir()
        self.write_markdown("")

    def write_markdown(self, body):
        (self.target / "SKILL.md").write_text(
            "---\nname: fixture\ndescription: Safe regression fixture\n---\n" + body,
            encoding="utf-8",
        )

    def cli(self):
        result = subprocess.run(
            [sys.executable, "-B", str(AUDIT_SCRIPT), str(self.target), "--json"],
            capture_output=True, text=True, check=False,
        )
        return result.returncode, json.loads(result.stdout)["observations"]

    def repository_errors(self):
        with mock.patch.object(validator, "ROOT", Path(self.temp.name)):
            return validator.check_skill(self.target)

    def assert_checks_clean(self):
        self.assertEqual(audit.scan_folder(self.target), [])
        self.assertEqual(self.repository_errors(), [])

    def test_code_examples_do_not_fail_ci(self):
        examples = [
            "```markdown\n[example](missing.md)\n```\n",
            "~~~~markdown\n[example](missing.md)\n~~~\n[still code](missing.md)\n~~~~\n",
            "`[example](missing.md)`\n",
            "``a ` [example](missing.md)``\n",
            "`multiline\n[example](missing.md)`\n",
        ]
        for body in examples:
            with self.subTest(body=body):
                self.write_markdown(body)
                self.assert_checks_clean()
                self.assertEqual(self.cli(), (0, []))

    def test_visible_missing_link_still_fails_with_original_line(self):
        self.write_markdown("```md\n[example](ignored.md)\n```\n`code` [real](missing.md)\n")
        observations = audit.scan_folder(self.target)
        self.assertEqual([(x["kind"], x["severity"], x["line"]) for x in observations],
                         [("broken_reference", "P2", 8)])
        self.assertEqual(self.cli()[0], 1)
        self.assertEqual(len(self.repository_errors()), 1)
        self.assertIn("SKILL.md:8", self.repository_errors()[0])

    def test_unmatched_backticks_cannot_hide_links_in_another_paragraph(self):
        self.write_markdown("A lone ` backtick.\n\n[real](missing.md)\n\nAnother ` in prose.\n")
        self.assertEqual([(x["kind"], x["line"]) for x in audit.scan_folder(self.target)],
                         [("broken_reference", 7)])
        self.assertEqual(self.cli()[0], 1)
        self.assertEqual(len(self.repository_errors()), 1)

    def test_code_span_removal_does_not_create_a_link(self):
        self.write_markdown("[text]`code`(missing.md)\n")
        self.assert_checks_clean()

    def test_existing_relative_and_external_links_pass(self):
        (self.target / "references").mkdir()
        (self.target / "references/note.md").write_text("A note\n", encoding="utf-8")
        self.write_markdown("[note](references/note.md#section) [web](https://example.org) [here](#anchor)\n")
        self.assert_checks_clean()

    @unittest.skipUnless(shutil.which("bash") and shutil.which("dash"), "bash and dash required")
    def test_bash_extension_and_shebang_work_when_sh_is_dash(self):
        # Real interpreters, with the Linux /bin/sh behavior reproduced on macOS.
        shell_dir = Path(self.temp.name) / "bin"
        shell_dir.mkdir()
        (shell_dir / "sh").symlink_to(shutil.which("dash"))
        (shell_dir / "bash").symlink_to(shutil.which("bash"))
        cases = [("demo.bash", ""), ("demo.sh", "#!/usr/bin/env bash\n"),
                 ("demo.sh", "#!/usr/bin/env -S bash -eu\n")]
        for filename, shebang in cases:
            with self.subTest(filename=filename, shebang=shebang):
                script = self.target / filename
                script.write_text(shebang + "values=(one two)\n", encoding="utf-8")
                try:
                    with mock.patch.dict(os.environ, {"PATH": str(shell_dir)}):
                        self.assert_checks_clean()
                finally:
                    script.unlink()

    @unittest.skipUnless(shutil.which("zsh"), "zsh not installed")
    def test_valid_zsh_uses_zsh(self):
        (self.target / "demo.zsh").write_text("repeat 2 do\n  :\ndone\n", encoding="utf-8")
        self.assert_checks_clean()

    @unittest.skipUnless(shutil.which("zsh"), "zsh not installed")
    def test_invalid_zsh_is_reported(self):
        (self.target / "demo.zsh").write_text("if then\n", encoding="utf-8")
        self.assertEqual([(x["kind"], x["severity"]) for x in audit.scan_folder(self.target)],
                         [("shell_syntax", "P1")])
        self.assertEqual(len(self.repository_errors()), 1)

    def test_missing_interpreter_is_visible_without_false_syntax_failure(self):
        (self.target / "demo.zsh").write_text(":\n", encoding="utf-8")
        with mock.patch.object(shutil, "which", return_value=None):
            observations = audit.scan_folder(self.target)
            self.assertEqual([(x["kind"], x["severity"]) for x in observations],
                             [("shell_unchecked", "INFO")])
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertEqual(self.repository_errors(), [])
            self.assertIn("demo.zsh", stderr.getvalue())
            self.assertIn("zsh", stderr.getvalue())

    def test_unsupported_shebang_is_not_executed_or_guessed(self):
        marker = self.target / "executed"
        (self.target / "demo.sh").write_text(
            "#!/usr/bin/env python3\nfrom pathlib import Path\n"
            "Path(__file__).with_name('executed').touch()\n", encoding="utf-8")
        observations = audit.scan_folder(self.target)
        self.assertEqual([(x["kind"], x["severity"]) for x in observations],
                         [("shell_unchecked", "INFO")])
        self.assertFalse(marker.exists())

    def test_audit_parses_python_and_shell_without_running_them(self):
        marker = self.target / "executed"
        (self.target / "demo.py").write_text("raise RuntimeError('must not run')\n", encoding="utf-8")
        (self.target / "demo.sh").write_text("#!/bin/sh\ntouch \"" + str(marker) + "\"\n", encoding="utf-8")
        before = {p.name: p.read_bytes() for p in self.target.iterdir()}
        self.assertEqual(self.cli(), (0, []))
        self.assert_checks_clean()
        self.assertEqual({p.name: p.read_bytes() for p in self.target.iterdir()}, before)
        self.assertFalse(marker.exists())

    def test_invalid_python_is_blocking(self):
        (self.target / "demo.py").write_text("if then\n", encoding="utf-8")
        code, observations = self.cli()
        self.assertEqual(code, 1)
        self.assertEqual([(x["kind"], x["severity"]) for x in observations],
                         [("python_syntax", "P1")])

    def test_heuristic_leads_do_not_block(self):
        self.write_markdown("Use $HOME/.codex/skills/demo only as an example.\n")
        code, observations = self.cli()
        self.assertEqual(code, 0)
        self.assertEqual([(x["kind"], x["severity"]) for x in observations],
                         [("fixed_skill_install", "P2?")])

    def test_missing_entrypoint_is_blocking(self):
        (self.target / "SKILL.md").unlink()
        code, observations = self.cli()
        self.assertEqual(code, 1)
        self.assertEqual(observations[0]["kind"], "missing_entrypoint")


if __name__ == "__main__":
    unittest.main()
