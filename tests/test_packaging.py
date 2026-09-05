"""Public bundle invariants. All injected paths and credentials are synthetic."""

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_release as release
import validate_package as validation


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="orbit-package-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "source"
        self.root.mkdir()
        # Copy only the public allowlist; do not traverse any private state.
        names = release.PUBLIC_FILES | frozenset(name for name in release.OPTIONAL_PUBLIC_FILES if (ROOT / name).exists())
        for name in names:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)

    def test_builds_are_byte_identical_across_mtime_and_line_ending_changes(self):
        first_dir = Path(self.temporary.name) / "first"
        second_dir = Path(self.temporary.name) / "second"
        release.build(self.root, first_dir)
        readme = self.root / "README.md"
        text = readme.read_text(encoding="utf-8")
        readme.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
        os.utime(readme, (1_600_000_000, 1_600_000_000))
        release.build(self.root, second_dir)
        self.assertEqual({p.name: p.read_bytes() for p in first_dir.iterdir()},
                         {p.name: p.read_bytes() for p in second_dir.iterdir()})

    def test_private_unlisted_state_is_not_packaged(self):
        excluded = (".env", ".orbit/manager.json", "docs/private-audit.md", ".git/config", "release/submission.json")
        private_marker = hashlib.sha256(b"invented excluded payload").hexdigest()
        for name in excluded:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(private_marker, encoding="utf-8")
        result = release.build(self.root)
        for artifact in result["artifacts"]:
            self.assertTrue(set(excluded).isdisjoint(artifact["files"]))
            with zipfile.ZipFile(self.root / "dist" / artifact["filename"]) as archive:
                self.assertFalse(any(private_marker.encode() in archive.read(name) for name in archive.namelist()))

    def test_included_private_paths_and_credential_values_block_build_without_echoing(self):
        original = (self.root / "README.md").read_text(encoding="utf-8")
        examples = ("/" + "Users/fictional/private/report.md", "C:" + "\\Users\\fictional\\private.txt",
                    "sk-" + "proj-" + "x" * 40, "ghp" + "_" + "x" * 40)
        for value in examples:
            with self.subTest(kind=value[:3]):
                (self.root / "README.md").write_text(original + "\n" + value, encoding="utf-8")
                with self.assertRaises(release.PackageError) as caught:
                    release.build(self.root)
                self.assertNotIn(value, str(caught.exception))
                self.assertIn("contents withheld", str(caught.exception))

    def test_required_missing_files_fail_instead_of_silently_shipping_partial_package(self):
        (self.root / "LICENSE").unlink()
        with self.assertRaisesRegex(release.PackageError, "required public file is missing"):
            release.build(self.root)

    def test_symlinked_public_member_is_rejected_before_it_is_read(self):
        original = Path.is_symlink
        with patch.object(Path, "is_symlink", lambda path: path.name == "README.md" or original(path)):
            with self.assertRaisesRegex(release.PackageError, "symlink not allowed"):
                release.load_public_files(self.root)

    def test_skill_only_archive_is_self_contained_and_has_no_executable_runtime(self):
        result = release.build(self.root)
        artifact = next(item for item in result["artifacts"] if item["variant"] == "skills-only")
        with zipfile.ZipFile(self.root / "dist" / artifact["filename"]) as archive:
            files = {name: archive.read(name) for name in archive.namelist()}
        self.assertIn(".codex-plugin/plugin.json", files)
        self.assertIn("skills/orbit/references/acting.md", files)
        self.assertIn("skills/orbit/references/delegation.md", files)
        self.assertFalse(any(name.endswith(".py") or name.startswith(("scripts/", "tests/", ".github/")) for name in files))
        self.assertEqual(validation.broken_links(files), [])
        self.assertIn(b"Finite interventions", files["README.md"])

    def test_checksums_and_fixed_zip_metadata_match_written_archives(self):
        result = release.build(self.root)
        self.assertEqual(release.verify(self.root)["status"], "PASS")
        for artifact in result["artifacts"]:
            payload = (self.root / "dist" / artifact["filename"]).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), artifact["sha256"])
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                self.assertEqual(archive.namelist(), sorted(archive.namelist()))
                for member in archive.infolist():
                    self.assertEqual(member.date_time, release.FIXED_ZIP_TIME)
                    self.assertEqual(member.compress_type, zipfile.ZIP_STORED)
                    self.assertEqual(member.external_attr >> 16, 0o100644)
                    self.assertTrue(release._safe_member_name(member.filename))

    def test_tampered_archive_or_stale_source_is_detected(self):
        result = release.build(self.root)
        target = self.root / "dist" / result["artifacts"][0]["filename"]
        target.write_bytes(target.read_bytes() + b"tampered")
        with self.assertRaisesRegex(release.PackageError, "checksum mismatch"):
            release.verify(self.root)
        release.build(self.root)
        readme = self.root / "README.md"
        readme.write_text(readme.read_text(encoding="utf-8") + "\nChanged public content.\n", encoding="utf-8")
        with self.assertRaisesRegex(release.PackageError, "differs from the current"):
            release.verify(self.root)

    def test_manifest_path_escape_and_executable_integration_are_rejected(self):
        files = release.load_public_files(self.root)
        original = json.loads(files[".codex-plugin/plugin.json"])
        for changes in ({"skills": "../external/"}, {"hooks": {}}, {"version": "../../unsafe"}):
            with self.subTest(changes=changes):
                files[".codex-plugin/plugin.json"] = json.dumps({**original, **changes}).encode()
                with self.assertRaises(release.PackageError):
                    release.validate_manifest(files)

    def test_validation_detects_broken_local_links(self):
        self.assertEqual(validation.validate(self.root)["status"], "PASS")
        readme = self.root / "README.md"
        readme.write_text(readme.read_text(encoding="utf-8") + "\n[missing](docs/not-shipped.md)\n", encoding="utf-8")
        with self.assertRaisesRegex(release.PackageError, "unresolved local link"):
            validation.validate(self.root)

    def test_ci_covers_three_os_minimum_and_current_python_without_publication(self):
        workflow = yaml.safe_load((self.root / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertEqual(set(workflow["on"]), {"push", "pull_request", "workflow_dispatch"})
        job = workflow["jobs"]["offline-validation"]
        self.assertEqual(set(job["strategy"]["matrix"]["os"]), {"ubuntu-latest", "macos-latest", "windows-latest"})
        self.assertEqual(set(job["strategy"]["matrix"]["python-version"]), {"3.10", "3.14"})
        self.assertEqual(job["env"]["PYTHONTZPATH"], "")
        runs = [step["run"] for step in job["steps"] if "run" in step]
        self.assertIn("python -m pip install -r requirements-dev.txt", runs)
        self.assertIn("python scripts/build_release.py --verify", runs)
        self.assertFalse(any("release create" in command or "git push" in command for command in runs))
        for step in job["steps"]:
            if "uses" in step:
                self.assertRegex(step["uses"], r"@[a-f0-9]{40}$")


if __name__ == "__main__":
    unittest.main()
