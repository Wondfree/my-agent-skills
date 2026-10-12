#!/usr/bin/env python3
"""Portable offline validation for all self-maintained skills in this repository."""
from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "skills"
SKIP = {"__pycache__", ".git", ".DS_Store"}
EXT = {".md", ".py", ".yaml", ".yml", ".sh", ".bash", ".zsh", ".txt", ".json"}
FRONT = re.compile(r"\A---\n(.*?)\n---(?:\n|$)", re.S)
NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
SENSITIVE_FILENAME = re.compile(r"(?:^|/)(?:\.env(?:\..*)?|id_(?:rsa|ed25519)|.*\.(?:pem|p12|pfx|key))$", re.I)
CREDENTIAL = re.compile(r"gh(?:p|o|s|u|r)_[A-Za-z0-9]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")


def check_skill(path: Path) -> list[str]:
    errors = []
    name = path.name
    entry = path / "SKILL.md"
    if not entry.exists():
        return [f"{name}: missing SKILL.md"]
    raw = entry.read_text(encoding="utf-8")
    header = FRONT.match(raw)
    if not header:
        return [f"{name}: invalid YAML frontmatter boundaries"]
    if not NAME.fullmatch(name):
        errors.append(f"{name}: invalid skill directory name")
    fields = {}
    for line in header.group(1).splitlines():
        m = re.match(r"^([a-z][-a-z]*):\s*(.*?)\s*$", line)
        if m:
            fields[m.group(1)] = m.group(2).strip().strip("'\"")
    if fields.get("name") != name:
        errors.append(f"{name}: frontmatter name differs from directory")
    if not fields.get("description") or fields["description"].startswith("[TODO"):
        errors.append(f"{name}: missing or unfinished description")
    for file in path.rglob("*"):
        if any(p in SKIP for p in file.parts):
            continue
        if file.is_symlink():
            # All source files should be physically present within the checked-out repo.
            errors.append(f"{name}: unexpected symlink {file.relative_to(ROOT)}")
            continue
        if not file.is_file():
            continue
        rel = str(file.relative_to(ROOT))
        if SENSITIVE_FILENAME.search(rel):
            errors.append(f"{rel}: potential secret file; never commit it")
            continue
        if file.suffix not in EXT:
            continue
        try:
            content = file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"{rel}: non-UTF8 content")
            continue
        if CREDENTIAL.search(content):
            errors.append(f"{rel}: possible credential material")
        if file.suffix == ".py":
            try:
                ast.parse(content, filename=rel)
            except SyntaxError as ex:
                errors.append(f"{rel}:{ex.lineno} invalid Python syntax: {ex.msg}")
        if file.suffix in {".sh", ".bash", ".zsh"}:
            shell = "sh" if file.suffix == ".sh" else "bash"
            if shutil.which(shell):
                check = subprocess.run([shell, "-n", str(file)], capture_output=True, text=True)
                if check.returncode:
                    errors.append(f"{rel}: invalid {shell} syntax {check.stderr[:150]}")
        if file.suffix == ".md":
            for lineno, line in enumerate(content.splitlines(), 1):
                for match in LINK.finditer(line):
                    reference = match.group(1).split("#", 1)[0].strip()
                    if not reference or reference.startswith(("https:", "http:", "mailto:", "#", "//")) or "<" in reference or ">" in reference:
                        continue
                    if not (file.parent / reference).exists():
                        errors.append(f"{rel}:{lineno} broken relative markdown link {reference}")
    return errors


def main() -> int:
    if not SOURCE.is_dir():
        print("Missing skills/ directory", file=sys.stderr)
        return 1
    targets = sorted(p for p in SOURCE.iterdir() if p.is_dir() and not p.name.startswith("."))
    if not targets:
        print("No skills discovered", file=sys.stderr)
        return 1
    errors = []
    for target in targets:
        errors.extend(check_skill(target))
    results = {"skills": [p.name for p in targets], "errors": errors, "passed": not errors}
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
