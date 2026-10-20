import hashlib
import copy
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import tempfile
import sys
import unittest
from urllib.parse import urlparse, unquote
from unittest.mock import patch
import zipfile
import warnings

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("site_builder", ROOT / "scripts/build_site.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)
with patch.dict(sys.modules, {"build_site": builder}):
    PACKAGE_SPEC = importlib.util.spec_from_file_location("site_media_package", ROOT / "scripts/package_site_media.py")
    packager = importlib.util.module_from_spec(PACKAGE_SPEC)
    PACKAGE_SPEC.loader.exec_module(packager)


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name == "href":
                self.links.append(value)


class SiteBuildTests(unittest.TestCase):
    def test_single_case_media_transfer_excludes_the_other_task(self):
        golden, pelican = b"Golden canvas", b"Pelican canvas"
        golden_key = "assets/media/golden_gate/test/attempt-03.png"
        pelican_key = "assets/media/pelican/test/attempt-03.png"
        expected = {key: {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)} for key, data in ((golden_key, golden), (pelican_key, pelican))}
        cases = [{"spec": {"id": "golden_gate"}, "expected_media": {golden_key: expected[golden_key]}}, {"spec": {"id": "pelican"}, "expected_media": {pelican_key: expected[pelican_key]}}]
        with tempfile.TemporaryDirectory() as tmp, patch.object(packager, "load_cases", return_value=({}, cases, expected)):
            root = Path(tmp)
            # Only this task's canvas exists: a transfer must not require Golden.
            path = root / "media/pelican/test/attempt-03.png"
            path.parent.mkdir(parents=True)
            path.write_bytes(pelican)
            archive = root / "pelican.zip"
            report = packager.package(root / "media", archive, ["pelican"])
            self.assertEqual(report["files"], 1)
            self.assertFalse(report["complete_site_media"])
            self.assertFalse(report["publication_performed"])
            with zipfile.ZipFile(archive) as source:
                self.assertEqual(source.namelist(), [pelican_key])
                self.assertEqual(source.read(pelican_key), pelican)
            with self.assertRaises(ValueError):
                packager.package(root / "media", root / "bad.zip", ["unknown"])
            self.assertFalse((root / "bad.zip").exists())

    def test_archive_tampering_duplicates_and_unselected_data_are_refused(self):
        payload = b"selected public canvas bytes"
        key = "assets/media/golden_gate/test/attempt-03.png"
        expected = {key: {"sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}}
        with tempfile.TemporaryDirectory() as tmp:
            archive_path = Path(tmp) / "selected.zip"
            for members in ([(key, b"wrong")], [(key, payload), (key, payload)], [("assets/media/private-record.json", b"secret")], [("../private-record.json", b"secret")]):
                with zipfile.ZipFile(archive_path, "w") as archive:
                    for name, value in members:
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore", UserWarning)
                            archive.writestr(name, value)
                with self.assertRaises(ValueError):
                    builder.read_archive(str(archive_path), expected)
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr(key, payload)
            self.assertEqual(builder.read_archive(str(archive_path), expected), {key: payload})

    def test_unsafe_asset_paths_and_insecure_download_are_refused(self):
        for path in ("../secret", "assets/media/../../secret", "assets\\media\\x.png", "assets/media//x.png", "/assets/media/x.png"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                builder.asset_path(path)
        with self.assertRaises(ValueError):
            builder.read_archive("http://example.com/private.zip", {})

    def test_author_recommendations_require_full_attributed_unique_coverage(self):
        results = {"case_id": "golden_gate", "models": [{"id": "a"}, {"id": "b"}]}
        base = {"case_id": "golden_gate", "status": "provided", "attributed_to": "Owner", "date": "2026-10-19", "tiers": [{"label": "Joint first", "model_ids": ["a", "b"]}]}
        builder.validate_recommendation(base, results)
        for ids in (["a"], ["a", "a"], ["a", "unknown"]):
            bad = dict(base, tiers=[{"label": "test", "model_ids": ids}])
            with self.assertRaises(ValueError):
                builder.validate_recommendation(bad, results)
        with self.assertRaises(ValueError):
            builder.validate_recommendation(dict(base, attributed_to=None), results)
        with self.assertRaises(ValueError):
            builder.validate_recommendation(dict(base, status="awaiting_owner"), results)

    def test_source_only_build_has_no_broken_internal_document_links(self):
        try:
            import markdown
        except ImportError:
            self.skipTest("Install requirements-site.txt for static-site build tests")
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "site"
            report = builder.build(output, None, None, True)
            self.assertEqual(report["models"], 11)
            self.assertEqual(len(report["missing_media"]), 70)
            self.assertEqual(set(report["cases"]), {"golden_gate", "pelican"})
            self.assertEqual(report["cases"]["pelican"]["attempts"], 33)
            self.assertFalse(report["publication_performed"])
            self.assertIn('id="benchmark-data"', (output / "index.html").read_text(encoding="utf-8"))
            self.assertIn('id="model-video-data"', (output / "index.html").read_text(encoding="utf-8"))
            self.assertIn('id="benchmark-cases-data"', (output / "index.html").read_text(encoding="utf-8"))
            self.assertIn('id="pelican-benchmark-data"', (output / "index.html").read_text(encoding="utf-8"))
            self.assertEqual(json.loads((output / "data/pelican.json").read_text("utf-8"))["target"]["mode"], "text")
            self.assertEqual(report["model_videos"], 11)
            broken = []
            for page in output.rglob("*.html"):
                parser = LinkParser()
                parser.feed(page.read_text(encoding="utf-8"))
                for link in parser.links:
                    url = urlparse(link)
                    if url.scheme or url.netloc or not url.path:
                        continue
                    target = (page.parent / unquote(url.path)).resolve()
                    if url.path in report["missing_media"]:
                        continue
                    if not target.exists():
                        broken.append((page.relative_to(output).as_posix(), link))
            self.assertEqual(broken, [])
            with self.assertRaises(ValueError):
                builder.build(output, None, None, True)

    def test_cases_keep_rankings_targets_and_media_separate(self):
        catalog, cases, expected = builder.load_cases()
        self.assertEqual(catalog["default_case_id"], "golden_gate")
        by_id = {case["spec"]["id"]: case for case in cases}
        self.assertEqual(by_id["golden_gate"]["recommendation"]["status"], "provided")
        self.assertEqual(by_id["pelican"]["recommendation"]["status"], "awaiting_owner")
        self.assertEqual(by_id["pelican"]["recommendation"]["tiers"], [])
        self.assertEqual(by_id["pelican"]["results"]["target"]["instruction"], "Paint a pelican riding a bicycle.")
        self.assertIsNone(by_id["pelican"]["results"]["target"].get("reference"))
        self.assertEqual(by_id["golden_gate"]["videos"]["playback_speed"], 6)
        self.assertEqual(by_id["pelican"]["videos"]["playback_speed"], 4)
        self.assertEqual(len(expected), 70)
        self.assertFalse(set(by_id["pelican"]["expected_media"]) & set(by_id["golden_gate"]["expected_media"]))

    def test_text_case_cannot_smuggle_a_reference_image(self):
        result = {"models": [], "target": {"mode": "text", "instruction": "Draw", "reference": {"path": "assets/media/reference.png"}}}
        with self.assertRaisesRegex(ValueError, "no reference"):
            builder.expected_media(result, {"assets": []})

    def test_catalog_rejects_foreign_rankings_and_unsafe_metadata_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = root / "benchmarks/results"
            directory.mkdir(parents=True)
            real = ROOT / "benchmarks/results"
            catalog = json.loads((real / "cases.json").read_text("utf-8"))
            for path in real.glob("*.json"):
                (directory / path.name).write_bytes(path.read_bytes())
            catalog["cases"][1]["recommendation"] = "editorial-ranking.json"
            (directory / "cases.json").write_text(json.dumps(catalog), "utf-8")
            with patch.object(builder, "ROOT", root), self.assertRaisesRegex(ValueError, "case mismatch"):
                builder.load_cases()
            catalog["cases"][1]["recommendation"] = "../../private.json"
            (directory / "cases.json").write_text(json.dumps(catalog), "utf-8")
            with patch.object(builder, "ROOT", root), self.assertRaisesRegex(ValueError, "Unsafe"):
                builder.load_cases()

    def test_public_build_refuses_missing_media_before_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "site"
            with self.assertRaises(ValueError):
                builder.build(output, None, None, False)
            self.assertFalse(output.exists())

    def test_whole_session_video_mapping_requires_complete_unique_canonical_links(self):
        results = {"case_id": "golden_gate", "models": [{"id": "a"}, {"id": "b"}]}
        base = {"schema": "robopaint.model-videos.v1", "case_id": "golden_gate", "models": {
            "a": {"bvid": "BV1NTnF6cEhU", "url": "https://www.bilibili.com/video/BV1NTnF6cEhU/", "duration_seconds": 300},
            "b": {"bvid": "BV1S6nF6qEN3", "url": "https://www.bilibili.com/video/BV1S6nF6qEN3/", "duration_seconds": 415},
        }}
        builder.validate_model_videos(base, results)
        bad_cases = []
        bad = copy.deepcopy(base); del bad["models"]["b"]; bad_cases.append(bad)
        bad = copy.deepcopy(base); bad["models"]["b"] = dict(bad["models"]["a"]); bad_cases.append(bad)
        for url in ("http://www.bilibili.com/video/BV1NTnF6cEhU/", "https://www.bilibili.com/video/BV1S6nF6qEN3/", "https://www.bilibili.com@private.example/video/BV1NTnF6cEhU/", "https://www.bilibili.com/video/BV1NTnF6cEhU/?secret=token"):
            bad = copy.deepcopy(base); bad["models"]["a"]["url"] = url; bad_cases.append(bad)
        for value in (0, -1, float("nan"), float("inf"), True):
            bad = copy.deepcopy(base); bad["models"]["a"]["duration_seconds"] = value; bad_cases.append(bad)
        for bad in bad_cases:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                builder.validate_model_videos(bad, results)


if __name__ == "__main__":
    unittest.main()
