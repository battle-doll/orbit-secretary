#!/usr/bin/env python3
"""Local release invariants, not an official marketplace approval validator.

Reads only build_release.py's public allowlist. Never reads Codex tasks, credentials
or manager state. Prints a path-free environment summary and relative-file findings.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path, PurePosixPath
import platform
import posixpath
import re
import sys
from urllib.parse import unquote, urlsplit

import yaml

from build_release import PackageError, ROOT, load_public_files, validate_manifest, variant_files


MARKDOWN_LINK = re.compile(r"!?\[[^\]\n]*\]\(([^)\n]+)\)")
HTML_SOURCE = re.compile(r"(?:src|href)=[\"']([^\"']+)[\"']")


def broken_links(files: dict[str, bytes]) -> list[str]:
    findings = []
    for name, payload in files.items():
        if not name.endswith(".md"):
            continue
        text = payload.decode("utf-8")
        # Code fences can demonstrate paths without linking to a shipped file.
        text = re.sub(r"```[\s\S]*?```", "", text)
        for raw in MARKDOWN_LINK.findall(text) + HTML_SOURCE.findall(text):
            target = raw.strip().strip("<>")
            if ' "' in target:
                target = target.split(' "', 1)[0]
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            decoded = unquote(parsed.path)
            resolved = posixpath.normpath(posixpath.join(str(PurePosixPath(name).parent), decoded))
            if decoded.startswith("/") or resolved.startswith("../") or resolved not in files:
                findings.append(f"{name}: unresolved local link {decoded}")
    return findings


def validate(root: Path = ROOT) -> dict:
    files = load_public_files(root)
    manifest = validate_manifest(files)
    findings = []
    for name, payload in files.items():
        if name.endswith(".py"):
            try:
                ast.parse(payload.decode("utf-8"), filename=name)
            except SyntaxError:
                findings.append(f"{name}: Python syntax error")
    skill = files["skills/orbit/SKILL.md"].decode("utf-8")
    if not skill.startswith("---\n") or "\n---\n" not in skill[4:]:
        findings.append("skills/orbit/SKILL.md: missing YAML frontmatter")
    else:
        try:
            frontmatter = yaml.safe_load(skill.split("---\n", 2)[1])
            if (not isinstance(frontmatter, dict) or frontmatter.get("name") != "orbit"
                    or not isinstance(frontmatter.get("description"), str) or not frontmatter["description"].strip()):
                findings.append("skills/orbit/SKILL.md: invalid name or description")
        except yaml.YAMLError:
            findings.append("skills/orbit/SKILL.md: invalid YAML frontmatter")
    for name in ("skills/orbit/agents/openai.yaml", ".github/workflows/ci.yml"):
        try:
            if not isinstance(yaml.safe_load(files[name]), dict):
                findings.append(f"{name}: expected a YAML mapping")
        except yaml.YAMLError:
            findings.append(f"{name}: invalid YAML")
    for name in ("logo", "composerIcon"):
        value = manifest.get("interface", {}).get(name)
        if value is not None:
            if not isinstance(value, str) or value.removeprefix("./") not in files:
                findings.append(f"manifest interface.{name}: missing package asset")
    for variant in ("source", "skills-only"):
        findings.extend(f"{variant}: {item}" for item in broken_links(variant_files(files, variant)))
    if findings:
        raise PackageError("\n".join(findings))
    return {"status": "PASS", "version": manifest["version"], "public_source_files": len(files),
            "checks": ["explicit public allowlist", "no source symlinks", "targeted sensitive-content scan",
                       "manifest scope", "Python syntax", "skill/YAML structure", "source and skills-only local links"],
            "environment": {"os": platform.system(), "python": platform.python_version()},
            "live_codex_tasks_read": False, "other_operating_systems_verified_by_this_run": False,
            "official_marketplace_approval": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--report", type=Path, help="write the local result JSON to this user-selected file")
    args = parser.parse_args()
    try:
        result = validate(args.root)
    except (PackageError, OSError) as exc:
        parser.exit(1, f"Local package validation failed: {exc}\n")
    output = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.report is not None:
        if args.report.is_symlink():
            parser.exit(1, "Validation report cannot overwrite a symlink.\n")
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output, encoding="utf-8", newline="\n")
    print(output, end="")


if __name__ == "__main__":
    main()
