"""Offline integrity and preservation checks for the minimal Colab source ZIP."""
import importlib.util
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("package_colab_source", ROOT / "scripts/package_colab_source.py")
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


class ColabSourceBundleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="robopaint-source-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "checkout"
        self.archive = self.root / "source.zip"
        self.destination = self.root / "unpacked"
        for name in bundle.ALLOWED_FILES:
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("safe fixture for " + name + "\n").encode())
        # They must never enter the package even though present in the checkout.
        for name in (".env", "runs/raw.jsonl", "site/assets/media/private.png", "local_save/log.txt"):
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"PRIVATE_FIXTURE_DO_NOT_PACKAGE")
        self.report = bundle.pack(self.source, self.archive)

    def rewritten(self, transform):
        with zipfile.ZipFile(self.archive) as original:
            entries = [(entry.filename, original.read(entry), entry.external_attr) for entry in original.infolist()]
        entries = transform(entries)
        buffer = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for name, payload, attributes in entries:
                    info = zipfile.ZipInfo(name)
                    info.create_system = 3
                    info.external_attr = attributes
                    info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, payload)
        path = self.root / "modified.zip"
        path.write_bytes(buffer.getvalue())
        return path, bundle.digest(buffer.getvalue())

    def rejected(self, path, expected_sha):
        with self.assertRaises(bundle.BundleError):
            bundle.unpack(path, self.destination, expected_sha)
        self.assertFalse(self.destination.exists())

    def test_fixed_closure_roundtrips_without_private_checkout_content(self):
        self.assertEqual(self.report["files"], 11)
        with zipfile.ZipFile(self.archive) as archive:
            self.assertEqual(set(archive.namelist()), {*bundle.ALLOWED_FILES, bundle.MANIFEST_NAME})
            self.assertNotIn(b"PRIVATE_FIXTURE_DO_NOT_PACKAGE", b"".join(archive.read(name) for name in archive.namelist()))
            manifest = json.loads(archive.read(bundle.MANIFEST_NAME))
            self.assertEqual(manifest["schema"], "robopaint.colab-source.v1")
            self.assertEqual([entry["path"] for entry in manifest["files"]], sorted(bundle.ALLOWED_FILES))
        result = bundle.unpack(self.archive, self.destination, self.report["archive_sha256"].upper())
        self.assertTrue(result["verified"])
        self.assertIs(result["model_inference"], False)
        for name in bundle.ALLOWED_FILES:
            self.assertEqual((self.source / name).read_bytes(), (self.destination / name).read_bytes())
        again = self.root / "same-source.zip"
        self.assertEqual(self.report["archive_sha256"], bundle.pack(self.source, again)["archive_sha256"])

    def test_missing_source_or_existing_destinations_preserve_files(self):
        self.archive.write_bytes(b"preserve existing archive")
        with self.assertRaises(FileExistsError):
            bundle.pack(self.source, self.archive)
        self.assertEqual(self.archive.read_bytes(), b"preserve existing archive")
        required = self.source / bundle.ALLOWED_FILES[0]
        required.unlink()
        missing_output = self.root / "missing.zip"
        with self.assertRaises(bundle.BundleError):
            bundle.pack(self.source, missing_output)
        self.assertFalse(missing_output.exists())
        self.destination.mkdir()
        keep = self.destination / "keep.txt"
        keep.write_text("preserve", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            bundle.unpack(self.archive, self.destination, self.report["archive_sha256"])
        self.assertEqual(keep.read_text("utf-8"), "preserve")

    def test_archive_digest_required_before_any_extraction(self):
        for value in (None, "", "invalid", "0" * 64):
            with self.subTest(value=value):
                self.rejected(self.archive, value)

    def test_manifest_digest_and_size_must_match_even_for_trusted_zip(self):
        target = bundle.ALLOWED_FILES[0]
        for change in (lambda payload: payload + b"tampered", lambda payload: b"x" * len(payload)):
            with self.subTest(change=change):
                path, sha = self.rewritten(lambda entries: [(name, change(data) if name == target else data, mode) for name, data, mode in entries])
                self.rejected(path, sha)

    def test_unknown_missing_duplicate_casefold_and_traversal_members_are_rejected(self):
        target = bundle.ALLOWED_FILES[0]
        transforms = [
            lambda entries: entries + [(".env", b"private", 0o100644 << 16)],
            lambda entries: [entry for entry in entries if entry[0] != target],
            lambda entries: entries + [entries[0]],
            lambda entries: entries + [(target.upper(), b"case collision", 0o100644 << 16)],
            lambda entries: entries + [("../escape.py", b"escape", 0o100644 << 16)],
            lambda entries: entries + [("/absolute.py", b"escape", 0o100644 << 16)],
            lambda entries: entries + [("scripts/./extra.py", b"alias", 0o100644 << 16)],
            lambda entries: entries + [("scripts\\extra.py", b"alias", 0o100644 << 16)],
        ]
        for index, change in enumerate(transforms):
            with self.subTest(index=index):
                self.rejected(*self.rewritten(change))
        self.assertFalse((self.root / "escape.py").exists())

    def test_archive_symlinks_special_files_and_reparse_points_are_rejected(self):
        target = bundle.ALLOWED_FILES[0]
        for mode in ((stat.S_IFLNK | 0o777) << 16, (stat.S_IFIFO | 0o644) << 16, (0o100644 << 16) | 0x400):
            with self.subTest(mode=mode):
                self.rejected(*self.rewritten(lambda entries: [(name, payload, mode if name == target else attrs) for name, payload, attrs in entries]))

    def test_manifest_schema_duplicate_entries_and_unknown_fields_are_rejected(self):
        def changed_manifest(entries, change):
            result = []
            for name, payload, mode in entries:
                if name == bundle.MANIFEST_NAME:
                    content = json.loads(payload)
                    change(content)
                    payload = json.dumps(content).encode()
                result.append((name, payload, mode))
            return result
        transforms = [
            lambda value: value.update(schema="unreviewed-schema"),
            lambda value: value["files"].append(value["files"][0]),
            lambda value: value["files"].pop(),
            lambda value: value.update(private="extra field"),
            lambda value: value["files"][0].update(sha256="f" * 64),
        ]
        for index, change in enumerate(transforms):
            with self.subTest(index=index):
                self.rejected(*self.rewritten(lambda entries: changed_manifest(entries, change)))

    def test_size_bounds_fail_before_output_creation(self):
        with patch.object(bundle, "MAX_ARCHIVE_BYTES", 8):
            self.rejected(self.archive, self.report["archive_sha256"])
        with patch.object(bundle, "MAX_FILE_BYTES", 8):
            self.rejected(self.archive, self.report["archive_sha256"])


if __name__ == "__main__":
    unittest.main()
