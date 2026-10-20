import hashlib
import copy
from html.parser import HTMLParser
import importlib.util
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlparse, unquote
import zipfile
import warnings

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("site_builder", ROOT / "scripts/build_site.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name == "href":
                self.links.append(value)


class SiteBuildTests(unittest.TestCase):
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
            self.assertEqual(len(report["missing_media"]), 36)
            self.assertFalse(report["publication_performed"])
            self.assertIn('id="benchmark-data"', (output / "index.html").read_text(encoding="utf-8"))
            self.assertIn('id="model-video-data"', (output / "index.html").read_text(encoding="utf-8"))
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

    def test_repository_images_build_a_complete_site_without_an_external_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "site"
            report = builder.build(output, ROOT / "site/assets/media", None, False)
            self.assertEqual(report["verified_media"], 36)
            self.assertEqual(report["missing_media"], [])
            self.assertEqual(len(list((output / "assets/media").rglob("*.png"))), 36)
            self.assertEqual(list((output / "assets/media").rglob("*.mp4")), [])

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
