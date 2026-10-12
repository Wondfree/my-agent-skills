#!/usr/bin/env python3
"""Read-only, heuristic audit for installable Skill packages (Python 3.9+)."""
from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


TARGET_EXTENSIONS = {".md", ".yaml", ".yml", ".py", ".sh", ".zsh", ".bash"}
NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
USER_PATHS = [
    ("user_home", re.compile(r"(?<![\w])/(?:Users|home)/[a-zA-Z][\w.-]+/(?:[^\s`'\"<>)]*)")),
    ("host_python", re.compile(r"(?<![\w])/usr/bin/python(?:3(?:\.\d+)?)?(?![\w./])")),
    ("homebrew_prefix", re.compile(r"(?<![\w])/(?:opt/homebrew|usr/local/Cellar|Applications/Xcode\.app)(?:/[^\s`'\"<>)]*)?")),
    ("fixed_skill_install", re.compile(r"\$(?:\{HOME\}|HOME)/\.codex/skills/[\w-]+")),
]
MD_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def finding(path: str, line: int, severity: str, kind: str, detail: str) -> dict:
    return {"severity": severity, "kind": kind, "path": path, "line": line, "detail": detail}


def scan_folder(target: Path) -> list[dict]:
    findings: list[dict] = []
    skill = target / "SKILL.md"
    if not target.is_dir():
        return [finding(str(target), 0, "P1", "no_target", "Skill directory does not exist")]
    if not skill.is_file():
        return [finding("SKILL.md", 0, "P1", "missing_entrypoint", "Missing SKILL.md")]
    text = skill.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\s*\n", text, re.S)
    if not match:
        findings.append(finding("SKILL.md", 1, "P1", "frontmatter", "Missing or malformed YAML frontmatter delimiters"))
    else:
        hdr = match.group(1)
        name = re.search(r"(?m)^name:\s*(.*?)\s*$", hdr)
        descr = re.search(r"(?m)^description:\s*(.*?)\s*$", hdr)
        if not name or not name.group(1).strip():
            findings.append(finding("SKILL.md", 1, "P1", "name", "Missing name (verify with official validator)"))
        else:
            value = name.group(1).strip().strip("\"'")
            if not NAME_PATTERN.fullmatch(value) or value != target.name:
                findings.append(finding("SKILL.md", 2, "P2", "name", f"Name {value!r} differs from directory or uses invalid casing"))
        if not descr or not descr.group(1).strip():
            findings.append(finding("SKILL.md", 1, "P1", "description", "Missing triggering description"))
    for f in target.rglob("*"):
        if not f.is_file() or f.suffix.lower() not in TARGET_EXTENSIONS:
            continue
        if any(seg in {".git", "__pycache__", "node_modules"} for seg in f.parts):
            continue
        rel = str(f.relative_to(target))
        try:
            content = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(finding(rel, 1, "INFO", "unreadable", "Text file is not UTF-8; review manually"))
            continue
        for num, line in enumerate(content.splitlines(), start=1):
            # A regex definition describing a bad example isn't itself an actual path
            # usage. Skip that false positive, but still inspect the rest of the file.
            defining_pattern = f.suffix == ".py" and "re.compile(" in line
            if not defining_pattern:
                for label, pat in USER_PATHS:
                    for m in pat.finditer(line):
                        findings.append(finding(rel, num, "P2?", label,
                                                f"Potential runtime-specific path {m.group(0)!r}; verify whether it is a harmless example"))
            if not (f.suffix == ".py" and "re.search(" in line) and re.search(r"\[TODO:[^\]]*\]", line):
                findings.append(finding(rel, num, "P2?", "todo", "Unresolved TODO marker"))
            if f.suffix == ".md":
                for m in MD_LINK.finditer(line):
                    ref = m.group(1).split("#", 1)[0].strip()
                    if not ref or ref.startswith(("http:", "https:", "mailto:", "//")):
                        continue
                    if "<" in ref or ">" in ref:
                        continue
                    if not (f.parent / ref).exists():
                        findings.append(finding(rel, num, "P2", "broken_reference", f"Markdown link missing: {ref}"))
        if f.suffix == ".py":
            try:
                ast.parse(content, filename=rel)
            except SyntaxError as e:
                findings.append(finding(rel, e.lineno or 1, "P1", "python_syntax", f"Python syntax error: {e.msg}"))
        elif f.suffix in {".sh", ".bash"} and shutil.which("sh"):
            result = subprocess.run(["sh", "-n", str(f)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode:
                findings.append(finding(rel, 1, "P1", "shell_syntax",
                                        f"Shell syntax check failed: {result.stderr.strip()[:300]}"))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_dir", type=Path, help="Skill folder to review, never mutated")
    parser.add_argument("--json", action="store_true", help="Machine-readable leads")
    args = parser.parse_args()
    target = args.skill_dir.expanduser().resolve()
    findings = scan_folder(target)
    if args.json:
        print(json.dumps({"target": str(target), "observations": findings,
                          "requires_manual_review": True}, ensure_ascii=False, indent=2))
    else:
        print(f"Skill: {target}")
        print(f"Static audit: {len(findings)} leads (heuristic, not an approval)")
        for f in findings:
            print(f"[{f['severity']}] {f['kind']} — {f['path']}:{f['line']}: {f['detail']}")
        if not findings:
            print("No static leads. Continue semantic/routing, safety and functional review.")
    return 1 if any(x["severity"] in {"P1", "P2"} for x in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
