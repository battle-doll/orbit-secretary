#!/usr/bin/env python3
"""Build local, deterministic review archives. No install, upload, or publication.

Only explicitly named public files are read. The allowlist intentionally excludes
manager state, private audit reports, environment files, raw sessions, credentials,
Git internals, and release-submission drafts. Adding a public file requires review
of this allowlist. Text is normalized to LF; ZIP timestamps and modes are fixed.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile


ROOT = Path(__file__).resolve().parents[1]
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
MAX_PUBLIC_FILE_BYTES = 1_000_000
PUBLIC_FILES = frozenset({
    ".codex-plugin/plugin.json", "README.md", "LICENSE", "requirements-dev.txt",
    ".github/workflows/ci.yml",
    "docs/PUBLIC_SCOPE.md", "docs/PUBLIC_RELEASE_GATES.md", "docs/VALIDATION.md",
    "docs/PLATFORM_SUPPORT.md", "docs/PRIVACY.md", "docs/TERMS.md", "docs/SUPPORT.md",
    "examples/offline-fixtures.md",
    "skills/orbit/SKILL.md", "skills/orbit/agents/openai.yaml",
    "skills/orbit/references/reporting.md", "skills/orbit/references/mandate.md",
    "skills/orbit/references/acting.md", "skills/orbit/references/delegation.md",
    "scripts/offline_core.py", "scripts/delegation_policy.py", "scripts/build_release.py", "scripts/validate_package.py",
    "tests/test_offline_core.py", "tests/test_delegation_policy.py", "tests/test_packaging.py",
    "assets/orbit-logo.svg", "assets/orbit-logo.png", "assets/social-card.svg", "assets/social-card.png",
})
OPTIONAL_PUBLIC_FILES = frozenset({
    "CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md",
    "README.ko.md", "README.en.md", "README.ja.md", "README.zh-CN.md", "README.ru.md",
    "docs/GETTING_STARTED.md", "docs/MANUAL_MVP.md", "docs/ACCEPTANCE_TESTS.md",
    "docs/PUBLISHING_CHECKLIST.md", "docs/RELEASE_CANDIDATE.md",
    "examples/synthetic-briefing.md", "examples/synthetic-mandate.md",
})
SKILLS_ONLY_FILES = frozenset({
    ".codex-plugin/plugin.json", "LICENSE",
    "docs/PUBLIC_SCOPE.md", "docs/PUBLIC_RELEASE_GATES.md", "docs/VALIDATION.md",
    "docs/PLATFORM_SUPPORT.md", "docs/PRIVACY.md", "docs/TERMS.md", "docs/SUPPORT.md",
    "skills/orbit/SKILL.md", "skills/orbit/agents/openai.yaml",
    "skills/orbit/references/reporting.md", "skills/orbit/references/mandate.md",
    "skills/orbit/references/acting.md", "skills/orbit/references/delegation.md",
    "assets/orbit-logo.svg", "assets/orbit-logo.png", "assets/social-card.svg", "assets/social-card.png",
})
SKILLS_ONLY_README = """# Orbit Secretary (궤도 조정자)

Your Codex tasks. One conversation. Your direction.

Orbit brings task progress into one conversation, helps you choose priorities,
and carries agreed follow-up instructions to the tasks you select. Reports start
with the essentials: progress, meaningful blockers and decisions for you.
Ask for details when you need them; important problems and uncertainty stay visible.

After installing Orbit, open the conversation where you want your briefings
and call `$orbit`. Ask for a progress report, discuss what deserves attention,
then choose whether to delegate a follow-up.

Finite interventions follow the time and action limits you choose and run in
the current conversation. Orbit normally delegates benchmarks and work estimated
at a minute or more; work estimated at ten minutes or more goes to an authorized
worker. Without an available route, Orbit prepares the handoff instead of taking
on long work in the manager conversation. An unavoidable shorter direct action
needs a brief explanation, and you can explicitly request a direct exception for
a specific task. After sending, Orbit briefly reports the known state and returns
to you rather than waiting for completion. These are estimated-work routing rules.
Unattended recurring management is not included.
Turning the plugin off does not automatically retract delivered instructions
or cancel running tasks. Reading and coordinating other tasks requires those
features to be available in your Codex environment.

- [Feature details](docs/PUBLIC_SCOPE.md)
- [Privacy](docs/PRIVACY.md)
- [Support](docs/SUPPORT.md)
- [Terms](docs/TERMS.md)
- [MIT license](LICENSE)
"""

SENSITIVE_PATTERNS = (
    ("absolute-user-path", re.compile(r"(?:/Users/|/home/)[A-Za-z0-9_.-]+/|/var/folders/[A-Za-z0-9_/.-]+|[A-Za-z]:\\Users\\[^\\\s]+\\")),
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("provider-key", re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}")),
    ("access-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}")),
    ("credential-assignment", re.compile(r"(?i)(?:api[_-]?key|access[_-]?token|password|client[_-]?secret)\s*[:=]\s*[\"']?[A-Za-z0-9_/-]{16,}")),
)


class PackageError(ValueError):
    pass


def _safe_member_name(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts and "\\" not in name and ":" not in name


def sensitive_findings(text: str) -> tuple[str, ...]:
    """Return rule names only, never matching credential or private path contents."""
    return tuple(rule for rule, pattern in SENSITIVE_PATTERNS if pattern.search(text))


def _read_public_file(root: Path, name: str) -> bytes:
    if not _safe_member_name(name):
        raise PackageError("unsafe archive member name")
    path = root / name
    # Reject both file symlinks and parent symlinks before reading their contents.
    cursor = path
    while cursor != root:
        if cursor.is_symlink():
            raise PackageError(f"symlink not allowed in public package: {name}")
        cursor = cursor.parent
    if not path.is_file():
        raise PackageError(f"required public file is missing: {name}")
    if path.stat().st_size > MAX_PUBLIC_FILE_BYTES:
        raise PackageError(f"public text file exceeds size limit: {name}")
    payload = path.read_bytes()
    if name.endswith(".png"):
        if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
            raise PackageError(f"public PNG has an invalid signature: {name}")
        return payload
    try:
        text = payload.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeDecodeError as exc:
        raise PackageError(f"public file is not UTF-8 text: {name}") from exc
    if "\x00" in text:
        raise PackageError(f"binary content is not allowed: {name}")
    findings = sensitive_findings(text)
    if findings:
        raise PackageError(f"sensitive-content rule {','.join(findings)} matched in {name}; contents withheld")
    return text.encode("utf-8")


def load_public_files(root: Path = ROOT) -> dict[str, bytes]:
    root = root.resolve()
    names = PUBLIC_FILES | frozenset(name for name in OPTIONAL_PUBLIC_FILES if (root / name).exists())
    return {name: _read_public_file(root, name) for name in sorted(names)}


def validate_manifest(files: dict[str, bytes]) -> dict:
    try:
        manifest = json.loads(files[".codex-plugin/plugin.json"])
    except (ValueError, KeyError) as exc:
        raise PackageError("plugin manifest must be valid JSON") from exc
    if not isinstance(manifest, dict):
        raise PackageError("plugin manifest must be an object")
    if manifest.get("name") != "orbit-secretary":
        raise PackageError("unexpected plugin name")
    version = manifest.get("version", "")
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+(?:-[A-Za-z0-9][A-Za-z0-9.-]*)?", version):
        raise PackageError("version must be a safe semantic version, optionally with a prerelease")
    if manifest.get("skills") != "./skills/":
        raise PackageError("skills path must stay inside the package at ./skills/")
    if any(key in manifest for key in ("mcpServers", "mcp", "hooks", "apps", "commands", "agents")):
        raise PackageError("manual skills-only release cannot declare an executable integration")
    interface = manifest.get("interface", {})
    if not isinstance(interface, dict) or interface.get("capabilities", []) not in ([], ["Write"]):
        raise PackageError("release cannot claim capabilities beyond its finite authorized Write scope")
    return manifest


def variant_files(files: dict[str, bytes], variant: str) -> dict[str, bytes]:
    if variant == "source":
        return dict(files)
    if variant != "skills-only":
        raise PackageError("unknown package variant")
    result = {name: files[name] for name in sorted(SKILLS_ONLY_FILES)}
    result["README.md"] = SKILLS_ONLY_README.encode("utf-8")
    return result


def archive_bytes(files: dict[str, bytes]) -> bytes:
    """ZIP_STORED avoids compressor-version differences across OS/Python versions."""
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED, strict_timestamps=True) as archive:
        for name, payload in sorted(files.items()):
            if not _safe_member_name(name):
                raise PackageError("unsafe archive member name")
            item = zipfile.ZipInfo(name, date_time=FIXED_ZIP_TIME)
            item.create_system = 3
            item.external_attr = (stat.S_IFREG | 0o644) << 16
            item.compress_type = zipfile.ZIP_STORED
            archive.writestr(item, payload)
    return stream.getvalue()


def build(root: Path = ROOT, output_dir: Path | None = None) -> dict:
    root = root.resolve()
    files = load_public_files(root)
    manifest = validate_manifest(files)
    destination = output_dir if output_dir is not None else root / "dist"
    destination = destination.absolute()
    if destination.is_symlink():
        raise PackageError("output directory cannot be a symlink")
    destination.mkdir(parents=True, exist_ok=True)
    artifacts = []
    for variant in ("source", "skills-only"):
        selected = variant_files(files, variant)
        payload = archive_bytes(selected)
        filename = f"{manifest['name']}-{manifest['version']}-{variant}.zip"
        target = destination / filename
        if target.is_symlink():
            raise PackageError("output archive cannot be a symlink")
        target.write_bytes(payload)
        artifacts.append({"filename": filename, "sha256": hashlib.sha256(payload).hexdigest(),
                          "bytes": len(payload), "files": sorted(selected), "variant": variant})
    checksums = "".join(f"{item['sha256']}  {item['filename']}\n" for item in sorted(artifacts, key=lambda a: a["filename"]))
    report = {"schema_version": 1, "plugin": manifest["name"], "version": manifest["version"],
              "reproducible_format": "UTF-8 LF, sorted ZIP_STORED, fixed 1980 timestamp and 0644 modes",
              "publication_performed": False, "artifacts": artifacts}
    for filename, payload in (("SHA256SUMS", checksums), ("build-info.json", json.dumps(report, indent=2, ensure_ascii=False) + "\n")):
        target = destination / filename
        if target.is_symlink():
            raise PackageError("output metadata cannot be a symlink")
        target.write_bytes(payload.encode("utf-8"))
    return report


def verify(root: Path = ROOT, output_dir: Path | None = None) -> dict:
    """Verify checksums, exact members/content, and deterministic archive metadata."""
    root = root.resolve()
    destination = output_dir if output_dir is not None else root / "dist"
    files = load_public_files(root)
    manifest = validate_manifest(files)
    try:
        checksum_lines = (destination / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise PackageError("SHA256SUMS is missing") from exc
    expected = {}
    for variant in ("source", "skills-only"):
        filename = f"{manifest['name']}-{manifest['version']}-{variant}.zip"
        expected[filename] = archive_bytes(variant_files(files, variant))
    actual = {}
    for line in checksum_lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+\.zip)", line)
        if not match or match[2] in actual:
            raise PackageError("malformed or duplicate SHA256SUMS entry")
        actual[match[2]] = match[1]
    if set(actual) != set(expected):
        raise PackageError("checksum inventory does not match the current release")
    for name, wanted in expected.items():
        try:
            payload = (destination / name).read_bytes()
        except OSError as exc:
            raise PackageError(f"release archive missing: {name}") from exc
        if hashlib.sha256(payload).hexdigest() != actual[name]:
            raise PackageError(f"checksum mismatch: {name}")
        if payload != wanted:
            raise PackageError(f"archive differs from the current allowlisted source: {name}")
    return {"status": "PASS", "version": manifest["version"], "archives_verified": len(expected),
            "publication_performed": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="package source directory")
    parser.add_argument("--output-dir", type=Path, help="local output directory; default: package dist/")
    parser.add_argument("--verify", action="store_true", help="verify existing artifacts instead of building")
    args = parser.parse_args()
    try:
        result = verify(args.root, args.output_dir) if args.verify else build(args.root, args.output_dir)
    except (PackageError, OSError) as exc:
        parser.exit(1, f"Package validation failed: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
