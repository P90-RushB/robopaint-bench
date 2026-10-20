"""Public metadata must be reproducible and fail closed on mixed evidence."""
import importlib.util
import json
from pathlib import Path
import re
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_public_results", ROOT / "scripts/build_public_results.py")
public = importlib.util.module_from_spec(spec)
spec.loader.exec_module(public)


def png(width=1024, height=725):
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff)
    scanlines = (b"\x00" + b"\xff\xff\xff" * width) * height
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(scanlines)) + chunk(b"IEND", b""))


class PublicResultsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="robopaint-public-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.catalog_path = self.root / "model_catalog.json"
        self.video_links = self.root / "video-links.json"
        self.video_links.write_text(json.dumps({"schema": "robopaint.video-links.v1", "case_id": "golden_gate", "models": {}}), "utf-8")
        default_links = patch.object(public, "DEFAULT_VIDEO_LINKS", self.video_links)
        default_links.start()
        self.addCleanup(default_links.stop)
        self.reviewed_artifacts = public.DEFAULT_PUBLIC_ARTIFACTS
        default_artifacts = patch.object(public, "DEFAULT_PUBLIC_ARTIFACTS", None)
        default_artifacts.start()
        self.addCleanup(default_artifacts.stop)
        self.output = self.root / "public"
        self.media = self.root / "preview"
        self.marker = "PRIVATE_NATIVE_REASONING_MUST_NOT_LEAVE_SOURCE"
        self.catalog = {"completed_three_attempt_models": 11, "partial_models": [], "models": []}
        canvas_bytes = png()
        counter = 0
        for name, (_, model_id, backend, effort) in public.MODEL_INFO.items():
            model_root = self.root / name
            model_root.mkdir()
            record = model_root / "results.jsonl"
            record.write_text(json.dumps({"native_reasoning": self.marker, "prompt": "private prompt"}), "utf-8")
            model = {"name": name, "model_id": model_id, "backend": backend, "effort": effort,
                     "attempt_steps": [1, 2, 3], "total_environment_actions": 6, "completed_attempts": 3,
                     "recommended_record": str(record), "notes": [self.marker, "C:/Users/private-user/secrets"], "media": []}
            for attempt in (1, 2, 3):
                counter += 1
                episode = f"{counter:032x}"
                directory = model_root / str(attempt)
                directory.mkdir()
                canvas = directory / "canvas.png"
                canvas.write_bytes(canvas_bytes)
                metadata = directory / "metadata.json"
                metadata.write_text(json.dumps({"episode_guid": episode, "action_count": attempt,
                    "authoritative_attempt_index": -1, "local_episode_counter": 999,
                    "physical_sha256": public.sha256(canvas), "saved_utc": "2026-10-19T10:22:33.1234567Z",
                    "reference_images": [{"sha256": public.REFERENCE_SHA256}], "extra_private": self.marker}), "utf-8")
                video = directory / "motion.mp4"
                video.write_bytes(b"retained video receipt fixture; not decoded by this builder")
                entries = {}
                for key, path in (("canvas", canvas), ("metadata", metadata), ("video", video)):
                    info = {"path": str(path), "sha256": public.sha256(path), "bytes": path.stat().st_size}
                    entries[key] = info
                # Exercise the current catalog's direct, copy/receipt, and list
                # mappings without scanning directories or picking newer files.
                if name == "opus":
                    entries = {key: {"copy": entry, "receipt_sha256": entry["sha256"]} for key, entry in entries.items()}
                item = {"attempt": attempt, "steps": attempt, "episode_guid": episode, "video_valid": True, **entries}
                if name == "sol":
                    item = {"attempt": attempt, "steps": attempt, "episode_guid": episode, "video_valid": True,
                            "files": list(entries.values())}
                model["media"].append(item)
            # Media order is deliberately unrelated to attempt numbering.
            model["media"].reverse()
            self.catalog["models"].append(model)
        self.save_catalog()

    def save_catalog(self):
        self.catalog_path.write_text(json.dumps(self.catalog), "utf-8")

    def fixture_public_artifacts(self):
        """Bind real publication receipts to small, deterministic source fixtures."""
        mapping = json.loads(self.reviewed_artifacts.read_text("utf-8"))
        for source in self.catalog["models"]:
            model = mapping["models"][source["name"]]
            record = Path(source["recommended_record"])
            model["record"].update(source_sha256=public.sha256(record), source_bytes=record.stat().st_size)
            for kind in ("record", "trajectory"):
                model[kind].update(action_count=6, attempt_action_counts=[1, 2, 3])
            model["canvases"] = [{"sha256": public.sha256(self.root / source["name"] / str(attempt) / "canvas.png"),
                                   "bytes": (self.root / source["name"] / str(attempt) / "canvas.png").stat().st_size}
                                  for attempt in (1, 2, 3)]
        path = self.root / "public-artifacts.json"
        path.write_text(json.dumps(mapping), "utf-8")
        return path, mapping

    def test_public_release_has_all_attempts_and_no_private_payload(self):
        result = public.write_release(self.catalog_path, self.output, self.media)
        self.assertEqual((result["model_count"], result["attempt_count"]), (11, 33))
        self.assertEqual(result["quality"]["status"], "unscored")
        self.assertEqual(result["publication_status"], "local_preview_pending_media_approval")
        self.assertEqual(result["harness"]["name"], "AgentArk SimpleAgent")
        self.assertIs(result["harness"]["shared_across_models"], True)
        session_protocol = {
            "learning_protocol": "in_context_learning", "session_structure": "one_continuous_agent_session",
            "round_count": 3, "experience_carries_across_rounds": True, "canvas_resets_each_round": True,
            "model_weight_updates": False, "round_index_field": "attempt",
        }
        for key, expected in session_protocol.items():
            self.assertEqual(result["protocol"][key], expected)
        backend_labels = {"codex": "Codex SDK", "openrouter": "OpenRouter", "volcengine": "Volcengine Ark"}
        self.assertEqual({item["id"]: item["label"] for item in result["harness"]["model_access_backends"]}, backend_labels)
        self.assertEqual(len(list(self.media.rglob("*.png"))), 33)
        for model in result["models"]:
            self.assertEqual(model["backend"], public.MODEL_INFO[model["id"]][2])
            self.assertEqual(model["backend_label"], backend_labels[model["backend"]])
            self.assertEqual([a["attempt"] for a in model["attempts"]], [1, 2, 3])
            self.assertEqual([a["steps"] for a in model["attempts"]], [1, 2, 3])
            self.assertIsNone(model["record"]["url"])
            for attempt in model["attempts"]:
                copied = self.media / attempt["canvas"]["path"].removeprefix("assets/media/")
                self.assertEqual(public.sha256(copied), attempt["canvas"]["sha256"])
                self.assertIsNone(attempt["video_url"])
        text = "".join(path.read_text("utf-8") for path in self.output.glob("*.json"))
        self.assertNotIn(self.marker, text)
        self.assertNotIn(str(self.root), text)
        self.assertNotIn("private-user", text)
        self.assertNotIn("native_reasoning", text)
        self.assertEqual(len(list(self.media.rglob("*.mp4"))), 0)
        manifest = json.loads((self.output / "release-manifest.json").read_text("utf-8"))
        self.assertEqual(manifest["harness"], result["harness"])
        for key, expected in session_protocol.items():
            self.assertEqual(manifest["session_protocol"][key], expected)
        first_hashes = {path.name: public.sha256(path) for path in self.output.glob("*.json")}
        public.write_release(self.catalog_path, self.output, self.media)
        self.assertEqual(first_hashes, {path.name: public.sha256(path) for path in self.output.glob("*.json")})

    def test_tampered_canvas_aborts_before_any_outputs(self):
        canvas = Path(self.catalog["models"][1]["media"][0]["canvas"]["path"])
        canvas.write_bytes(canvas.read_bytes() + b"tampered")
        with self.assertRaisesRegex(public.EvidenceError, "SHA-256 mismatch"):
            public.write_release(self.catalog_path, self.output, self.media)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.media.exists())

    def test_missing_or_duplicate_attempt_is_rejected(self):
        self.catalog["models"][0]["media"][0]["attempt"] = 1
        self.save_catalog()
        with self.assertRaisesRegex(public.EvidenceError, "unambiguous media mappings"):
            public.build_results(self.catalog_path)

    def test_missing_model_and_unreviewed_identity_are_rejected(self):
        original = self.catalog["models"].pop()
        self.save_catalog()
        with self.assertRaisesRegex(public.EvidenceError, "exactly the 11 curated models"):
            public.build_results(self.catalog_path)
        self.catalog["models"].append(original)
        self.catalog["models"][0]["model_id"] = "unreviewed/model"
        self.save_catalog()
        with self.assertRaisesRegex(public.EvidenceError, "Unreviewed model identity"):
            public.build_results(self.catalog_path)

    def test_validly_hashed_but_wrong_episode_metadata_is_rejected(self):
        item = self.catalog["models"][1]["media"][0]
        entry = item["metadata"]
        path = Path(entry["path"])
        value = json.loads(path.read_text("utf-8"))
        value["episode_guid"] = "f" * 32
        path.write_text(json.dumps(value), "utf-8")
        entry.update(sha256=public.sha256(path), bytes=path.stat().st_size)
        self.save_catalog()
        with self.assertRaisesRegex(public.EvidenceError, "episode identity disagrees"):
            public.build_results(self.catalog_path)

    def test_existing_different_preview_is_preserved(self):
        destination = self.media / "golden_gate/sol/attempt-01.png"
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b"do not overwrite another preview")
        with self.assertRaisesRegex(public.EvidenceError, "Refusing to overwrite"):
            public.write_release(self.catalog_path, self.output, self.media)
        self.assertEqual(destination.read_bytes(), b"do not overwrite another preview")
        self.assertFalse(self.output.exists())

    def test_private_paths_and_nonimmutable_record_links_fail_closed(self):
        for value in ("C:/Users/name/private.json", "\\\\host\\share\\local", "/root/private", "data:image/png;base64,xxx", "Bearer token"):
            with self.assertRaises(public.EvidenceError):
                public.assert_portable_public_data({"value": value})
        with self.assertRaisesRegex(public.EvidenceError, "immutable dataset"):
            public.published_record_url({"published_record_url": "https://example.org/record.jsonl"})
        with self.assertRaisesRegex(public.EvidenceError, "immutable dataset"):
            public.published_record_url({"published_record_url": "https://huggingface.co/datasets/P90-RushB/AgentArk/resolve/main/artifacts/records/x", "published_record_revision": "main"})

    def test_owner_video_links_survive_result_regeneration(self):
        mapping = {"schema": "robopaint.video-links.v1", "case_id": "golden_gate", "models": {
            "astra": {"3": "https://www.youtube.com/watch?v=owner-provided&t=12"},
            "sol": {"1": "https://www.bilibili.com/video/BV-owner-provided/"}}}
        explicit = self.root / "approved-video-links.json"
        explicit.write_text(json.dumps(mapping), "utf-8")
        for _ in range(2):
            result = public.write_release(self.catalog_path, self.output, video_links=explicit)
            by_name = {model["id"]: model for model in result["models"]}
            self.assertEqual(by_name["astra"]["attempts"][2]["video_url"], mapping["models"]["astra"]["3"])
            self.assertIsNone(by_name["astra"]["attempts"][0]["video_url"])
            self.assertEqual(by_name["sol"]["attempts"][0]["video_url"], mapping["models"]["sol"]["1"])
            manifest = json.loads((self.output / "release-manifest.json").read_text("utf-8"))
            self.assertEqual(manifest["video_links_sha256"], public.sha256(explicit))
            video = next(item for item in manifest["artifacts"] if item["id"] == "astra/attempt-03/video")
            self.assertEqual(video["publication_status"], "linked_public_video")

    def test_checked_in_public_contracts_preserve_all_reviewed_downloads(self):
        mapping = public.load_public_artifacts(self.reviewed_artifacts)
        current = json.loads((ROOT / "benchmarks/results/golden_gate.json").read_text("utf-8"))
        self.assertEqual(set(mapping), {model["id"] for model in current["models"]})
        for model in current["models"]:
            for kind in ("record", "trajectory"):
                self.assertEqual(mapping[model["id"]][kind], model[kind])
                self.assertEqual(mapping[model["id"]][kind]["attempt_action_counts"], model["attempt_steps"])
        self.assertFalse(mapping["sol"]["trajectory"]["full_history"])
        self.assertIn("72/155", mapping["sol"]["trajectory"]["history_coverage"])

    def test_regeneration_keeps_all_public_records_trajectories_and_media_approvals(self):
        path, mapping = self.fixture_public_artifacts()
        for _ in range(2):
            result = public.write_release(self.catalog_path, self.output, public_artifacts=path)
            self.assertEqual(result["publication_status"], "public_records_videos_and_versioned_site_canvases")
            self.assertEqual(len(result["models"]), 11)
            for model in result["models"]:
                reviewed = mapping["models"][model["id"]]
                self.assertEqual(model["record"], reviewed["record"])
                self.assertEqual(model["trajectory"], reviewed["trajectory"])
                self.assertEqual(model["video_url"], reviewed["video_url"])
            manifest = json.loads((self.output / "release-manifest.json").read_text("utf-8"))
            self.assertEqual(manifest["publication_status"], result["publication_status"])
            self.assertEqual(manifest["public_artifacts_sha256"], public.sha256(path))
            canvas = [item for item in manifest["artifacts"] if item["id"].endswith("/canvas")]
            self.assertEqual(len(canvas), 33)
            self.assertEqual({item["publication_status"] for item in canvas}, {"versioned_site_asset"})
            self.assertEqual(len([item for item in manifest["artifacts"] if item["id"].endswith("/trajectory")]), 11)
            originals = [item for item in manifest["artifacts"] if re.fullmatch(r"[^/]+/attempt-\d+/video", item["id"])]
            self.assertEqual(len(originals), 33)
            self.assertTrue(all(item["url_scope"] == "combined_model_video" for item in originals))

    def test_public_approvals_reject_mismatched_sources_rounds_and_canvases_before_writing(self):
        path, mapping = self.fixture_public_artifacts()
        mutations = (
            ("record", "source_sha256", "0" * 64, "source record identity mismatch"),
            ("record", "source_bytes", 1, "source record identity mismatch"),
            ("record", "attempt_action_counts", [1, 1, 4], "round action counts mismatch"),
            ("trajectory", "attempt_action_counts", [2, 2, 2], "round action counts mismatch"),
        )
        for kind, key, bad, message in mutations:
            with self.subTest(kind=kind, key=key):
                altered = json.loads(json.dumps(mapping))
                altered["models"]["sol"][kind][key] = bad
                path.write_text(json.dumps(altered), "utf-8")
                with self.assertRaisesRegex(public.EvidenceError, message):
                    public.write_release(self.catalog_path, self.output, self.media, public_artifacts=path)
                self.assertFalse(self.output.exists())
                self.assertFalse(self.media.exists())
        mapping["models"]["sol"]["canvases"][0]["sha256"] = "0" * 64
        path.write_text(json.dumps(mapping), "utf-8")
        with self.assertRaisesRegex(public.EvidenceError, "selected-canvas identity mismatch"):
            public.write_release(self.catalog_path, self.output, self.media, public_artifacts=path)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.media.exists())

    def test_exact_reviewed_public_source_is_accepted_without_changing_original_receipt(self):
        path, mapping = self.fixture_public_artifacts()
        receipt = mapping["models"]["sol"]["record"]
        receipt.update(sha256=receipt["source_sha256"], bytes=receipt["source_bytes"],
                       source_sha256="f" * 64, source_bytes=999)
        path.write_text(json.dumps(mapping), "utf-8")
        result, _, _ = public.build_results(self.catalog_path, public_artifacts=path)
        actual = next(model for model in result["models"] if model["id"] == "sol")["record"]
        self.assertEqual(actual, receipt)
        self.assertEqual(actual["source_sha256"], "f" * 64)
        # A public-copy hash alone is insufficient: its byte count also binds.
        receipt["bytes"] += 1
        path.write_text(json.dumps(mapping), "utf-8")
        with self.assertRaisesRegex(public.EvidenceError, "identity mismatch"):
            public.build_results(self.catalog_path, public_artifacts=path)

    def test_unpublished_collection_keeps_pending_controls_and_cannot_use_approvals(self):
        with patch.object(public, "DEFAULT_PUBLIC_ARTIFACTS", self.reviewed_artifacts):
            with self.assertRaisesRegex(public.EvidenceError, "identity mismatch"):
                public.build_results(self.catalog_path)
            result, manifest, _ = public.build_results(self.catalog_path, unpublished=True)
        self.assertEqual(result["publication_status"], "local_preview_pending_media_approval")
        self.assertNotIn("public_artifacts_sha256", manifest)
        self.assertTrue(all(model["record"]["url"] is None and "trajectory" not in model for model in result["models"]))
        with self.assertRaisesRegex(public.EvidenceError, "cannot use public-artifact approvals"):
            public.build_results(self.catalog_path, public_artifacts=self.reviewed_artifacts, unpublished=True)

    def test_public_artifact_mapping_rejects_unreviewed_shapes_and_mutable_downloads(self):
        path, mapping = self.fixture_public_artifacts()
        invalid = []
        altered = json.loads(json.dumps(mapping))
        altered["case_id"] = "another_collection"
        invalid.append(altered)
        altered = json.loads(json.dumps(mapping))
        del altered["models"]["sol"]
        invalid.append(altered)
        altered = json.loads(json.dumps(mapping))
        artifact = altered["models"]["sol"]["record"]
        artifact["url"] = artifact["url"].replace(artifact["revision"], "main")
        invalid.append(altered)
        altered = json.loads(json.dumps(mapping))
        del altered["models"]["sol"]["trajectory"]["history_coverage"]
        invalid.append(altered)
        for index, value in enumerate(invalid):
            with self.subTest(index=index):
                path.write_text(json.dumps(value), "utf-8")
                with self.assertRaises(public.EvidenceError):
                    public.write_release(self.catalog_path, self.output, self.media, public_artifacts=path)
                self.assertFalse(self.output.exists())
                self.assertFalse(self.media.exists())
        path.write_text('{"schema":"first","schema":"duplicate"}', "utf-8")
        with self.assertRaisesRegex(public.EvidenceError, "Duplicate key"):
            public.load_public_artifacts(path)

    def test_video_links_reject_unknown_models_attempts_and_schema(self):
        bad_mappings = [
            {"schema": "robopaint.video-links.v1", "case_id": "pelican", "models": {}},
            {"schema": "robopaint.video-links.v1", "case_id": "golden_gate", "models": {"unknown": {}}},
            {"schema": "robopaint.video-links.v1", "case_id": "golden_gate", "models": {"astra": {"0": "https://youtu.be/example"}}},
            {"schema": "robopaint.video-links.v1", "case_id": "golden_gate", "models": {"astra": {"01": "https://youtu.be/example"}}},
            {"schema": "robopaint.video-links.v1", "case_id": "golden_gate", "models": {"astra": []}},
            {"schema": "robopaint.video-links.v1", "case_id": "golden_gate", "models": {}, "unreviewed": "extra"},
        ]
        for mapping in bad_mappings:
            with self.subTest(mapping=mapping):
                self.video_links.write_text(json.dumps(mapping), "utf-8")
                with self.assertRaises(public.EvidenceError):
                    public.write_release(self.catalog_path, self.output, self.media)
                self.assertFalse(self.output.exists())
                self.assertFalse(self.media.exists())
        self.video_links.write_text('{"schema":"robopaint.video-links.v1","case_id":"golden_gate","models":{"astra":{"1":"https://youtu.be/first","1":"https://youtu.be/second"}}}', "utf-8")
        with self.assertRaisesRegex(public.EvidenceError, "Duplicate key"):
            public.load_video_links(self.video_links)

    def test_video_links_reject_local_non_https_and_credential_urls(self):
        urls = (None, "http://youtu.be/example", "javascript:alert(1)", "https://user:password@youtu.be/example",
                "https://youtu.be/example?api_key=private", "https://youtu.be/example#access_token=private",
                "https://youtu.be/example?X-Amz-Signature=private", "https://localhost/example",
                "https://127.0.0.1/example", "https://127.1/example", "https://10.0.0.1/example",
                "https://[::1]/example", "https://youtu.be:8443/example", "https://youtu.be/example\n",
                "https://youtu.be\\@example.org/example")
        for url in urls:
            with self.subTest(url=url), self.assertRaises(public.EvidenceError):
                public.public_video_url(url)


if __name__ == "__main__":
    unittest.main()
