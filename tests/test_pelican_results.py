"""Pelican public metadata is task-specific, reproducible, and fail-closed."""
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_pelican_results", ROOT / "scripts/build_pelican_results.py")
pelican = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pelican)


def png():
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1024, 725, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress((b"\0" + b"\xff\xff\xff" * 1024) * 725)) + chunk(b"IEND", b""))


class PelicanResultsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pelican-evidence-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.payload = self.root / "payload"
        self.dataset = self.payload / pelican.DATASET_PREFIX / "records_manifest.json"
        self.dataset.parent.mkdir(parents=True)
        self.sources_path, self.delivery_path, self.publication_path = [self.root / name for name in ("models.json", "delivery.json", "publication.json")]
        self.output, self.media_output = self.root / "public", self.root / "media"
        self.marker = "PRIVATE_REQUEST_OR_REASONING_MUST_NOT_BE_EXPORTED"
        self.catalog = {"case_id": "pelican", "target_text": pelican.TARGET, "reference_image_attached": False,
                        "repo_id": "P90-RushB/AgentArk", "sources_modified": False, "models": {}, "files": [],
                        "private_unknown_field": self.marker}
        self.sources = {}
        self.delivery = {"status": "complete", "models": 11, "attempts": 33, "retained_actions": 603,
                         "speed_in_simulated_time": 4, "all_full_decodes_pass": True, "all_steps_present": True,
                         "all_subtitles_within_step_boundaries": True, "deliveries": []}
        self.publication = {"all_11_published": True, "items": []}
        canvas_bytes, counter = png(), 0
        for name, (label, model_id, backend, effort, steps) in pelican.MODEL_INFO.items():
            model = {"model": model_id, "provider": backend, "reasoning_effort": effort, "protocol": pelican.PROTOCOL,
                     "group_seed": 107, "platform": "linux", "env_version": "1.0.5", "task_version": "v1",
                     "attempt_action_counts": steps, "action_count": sum(steps), "attempt_count": 3,
                     "agentark_commit": "299737b6eeddfb50e1f8edc9194b0a15d47049f3" if name in ("sol", "argon") else "54ab7cb0adf6539419611b536811b9850e429520",
                     "simple_agent_settings": {"tool_choice": "auto" if name in ("opus", "wonder") else "required", "output_token_parameter": "max_tokens",
                         "env_message_mode": "delta", "context": {"output_reserve_tokens": 20480, "summary_output_tokens": 32768}},
                     "source_episode_guids": [], "settings_exceptions": {}, "untrusted_notes": self.marker}
            saved_steps = [min(24, step) for step in steps]
            model["history_coverage"] = {"saved_steps_per_attempt": saved_steps, "all_actions_in_results": True,
                                         "trajectory_full_history": saved_steps == steps}
            if name == "opus":
                model["settings_exceptions"] = {"reasoning_fallback": "max failed; user-authorized high continuation, full context restored"}
            if name == "mimo":
                model["thinking"] = {"type": "enabled"}
                model["settings_exceptions"] = {"actual_provider_request_caps_latest_segment": [
                    {"purpose": "action", "max_output_tokens": 20480, "requests": 25},
                    {"purpose": "action", "max_output_tokens": 65536, "requests": 2},
                    {"purpose": "summary", "max_output_tokens": 32768, "requests": 1}]}
            for kind, field in (("results", "results_path"), ("trajectories", "trajectories_path")):
                relative = pelican.DATASET_PREFIX + name + "/" + kind + ".jsonl"
                path = self.payload / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"private_raw_payload": self.marker}), "utf-8")
                model[field] = relative
                self.catalog["files"].append({"model_name": name, "kind": "record", "record_kind": kind,
                    "path": relative, "sha256": pelican.sha256(path), "size_bytes": path.stat().st_size})
            mapping = {"attempt_steps": steps, "media": [], "private_note": self.marker}
            for attempt, count in enumerate(steps, 1):
                counter += 1
                guid = f"{counter:032x}"
                model["source_episode_guids"].append(guid)
                directory = self.root / "sources" / name / str(attempt)
                directory.mkdir(parents=True)
                canvas = directory / "canvas.png"
                canvas.write_bytes(canvas_bytes)
                metadata = {"episode_guid": guid, "action_count": count, "physical_sha256": pelican.sha256(canvas),
                    "painting_goal": pelican.TARGET + "\n", "reference_images": [], "reference_mode": "text", "group_seed": 107,
                    "physics_frequency_hz": 480, "brush_mode": "fixed", "board_mode": "fixed", "pigment_mode": "infinite",
                    "submission_integrity": True, "terminal_status": "submitted", "saved_utc": "2026-10-19T01:02:03.456Z",
                    "private_payload": self.marker, "source_path": "C:/Users/private/secrets"}
                (directory / "metadata.json").write_text(json.dumps(metadata), "utf-8")
                item = {"attempt": attempt, "steps": count, "episode_guid": guid, "canvas": str(canvas),
                    "complete": True, "truncated": False, "encoder_exit_code": 0, "full_decode_pass": True,
                    "video_sha256": "1" * 64, "duration_s": 15.5}
                if name not in ("doubao", "astra"):
                    item.update(source_episode_guid=guid, source_canvas=str(canvas), canvas_identical=True, canvas_mae_0_255=0.0)
                mapping["media"].append(item)
            mapping["media"].reverse()
            self.catalog["models"][name] = model
            self.sources[name] = mapping
            self.delivery["deliveries"].append({"model": name, "attempt_steps": steps, "full_decode_pass": True,
                "all_three_attempts_present": True, "all_steps_accounted_for": True, "speed_in_simulated_time": 4,
                "duration_s": 123.4, "video_sha256": "2" * 64, "video_bytes": 1000, "film": "C:/private/video.mp4"})
            self.publication["items"].append({"model": name, "review_status": "published", "url": "https://www.bilibili.com/video/BV1234567890/",
                                             "title": self.marker})
        self.save()

    def save(self):
        for path, value in ((self.dataset, self.catalog), (self.sources_path, self.sources),
                            (self.delivery_path, self.delivery), (self.publication_path, self.publication)):
            path.write_text(json.dumps(value), "utf-8")

    def build(self):
        return pelican.write_release(self.dataset, self.sources_path, self.delivery_path, self.publication_path,
                                     self.output, self.media_output)

    def test_complete_release_is_allowlisted_reproducible_and_unranked(self):
        result = self.build()
        self.assertEqual((result["model_count"], result["attempt_count"], result["action_count"]), (11, 33, 603))
        self.assertEqual(result["quality"]["status"], "unscored")
        self.assertIsNone(result["target"]["reference"])
        self.assertEqual(result["target"]["instruction"], pelican.TARGET)
        self.assertEqual(len(list(self.media_output.rglob("*.png"))), 33)
        self.assertEqual(len(list(self.media_output.rglob("*.mp4"))), 0)
        for model in result["models"]:
            self.assertEqual([entry["attempt"] for entry in model["attempts"]], [1, 2, 3])
            self.assertIsNone(model["token_usage"])
            self.assertIsNone(model["api_cost_usd"])
            self.assertIn(pelican.REVISION, model["record"]["url"])
            self.assertTrue(model["record"]["all_actions_complete"])
            for attempt in model["attempts"]:
                self.assertIsNone(attempt["video_url"], "Whole-session video must not be labeled as an individual round")
                copied = self.media_output / attempt["canvas"]["path"].removeprefix("assets/media/")
                self.assertEqual(pelican.sha256(copied), attempt["canvas"]["sha256"])
        rank = json.loads((self.output / "pelican-ranking.json").read_text("utf-8"))
        self.assertEqual((rank["status"], rank["tiers"]), ("awaiting_owner", []))
        videos = json.loads((self.output / "pelican-videos.json").read_text("utf-8"))
        self.assertEqual(videos["playback_speed"], 4)
        exported = "".join(path.read_text("utf-8") for path in self.output.glob("*.json"))
        for private in (self.marker, str(self.root), "C:/private", "private_payload", "untrusted_notes"):
            self.assertNotIn(private, exported)
        hashes = {path.name: pelican.sha256(path) for path in self.output.glob("*.json")}
        self.build()
        self.assertEqual(hashes, {path.name: pelican.sha256(path) for path in self.output.glob("*.json")})

    def test_actual_exceptions_and_truncated_history_are_explicit(self):
        models = {model["id"]: model for model in self.build()["models"]}
        self.assertEqual(models["opus"]["settings"]["tool_choice"], "auto")
        self.assertEqual(models["opus"]["effort"], "high")
        self.assertEqual(models["opus"]["effort_label"], "high")
        self.assertFalse(models["opus"]["trajectory"]["full_history"])
        self.assertEqual(models["opus"]["trajectory"]["saved_steps_per_attempt"], [24, 9, 9])
        self.assertTrue(models["sol"]["trajectory"]["full_history"])
        self.assertEqual(models["mimo"]["settings"]["actual_provider_request_caps_latest_segment"][1]["max_output_tokens"], 65536)
        self.assertEqual(models["astra"]["effort"], "max")
        self.assertFalse(models["astra"]["settings"]["output_token_cap_enforced"])

    def provided_ranking(self):
        order = ["astra", "sol", "argon", "opus", "wonder", "mimo", "qwen", "kimi", "deepseek", "doubao", "grok"]
        return {"schema": "robopaint.author-recommendation.v1", "case_id": "pelican", "status": "provided",
                "attributed_to": "the benchmark author", "basis": "Personal assessment of the Pelican paintings.",
                "date": "2026-10-20", "tiers": [{"label": str(index), "model_ids": [name]}
                                               for index, name in enumerate(order, 1)],
                "note": "A personal recommendation, not a numerical quality score."}

    def test_refresh_preserves_the_independent_author_ranking(self):
        self.build()
        ranking = self.provided_ranking()
        path = self.output / "pelican-ranking.json"
        path.write_text(json.dumps(ranking, indent=2) + "\n", "utf-8")
        self.build()
        self.assertEqual(json.loads(path.read_text("utf-8")), ranking)
        hashes = {item.name: pelican.sha256(item) for item in self.output.glob("*.json")}
        self.build()
        self.assertEqual(hashes, {item.name: pelican.sha256(item) for item in self.output.glob("*.json")})

    def test_invalid_existing_author_ranking_aborts_before_any_output_change(self):
        self.output.mkdir()
        path = self.output / "pelican-ranking.json"
        for field, value in (("case_id", "golden_gate"), ("schema", "unknown"),
                             ("attributed_to", " "), ("basis", None), ("date", "2026-02-30"),
                             ("status", "awaiting_owner"), ("tiers", []), ("tiers", ["invalid"])):
            with self.subTest(field=field, value=value):
                ranking = self.provided_ranking()
                ranking[field] = value
                original = json.dumps(ranking)
                path.write_text(original, "utf-8")
                with self.assertRaises(pelican.EvidenceError):
                    self.build()
                self.assertEqual(path.read_text("utf-8"), original)
                self.assertEqual(list(self.output.iterdir()), [path])
                self.assertFalse(self.media_output.exists())
        for model_id in ("astra", "unknown_model"):
            with self.subTest(model_id=model_id):
                ranking = self.provided_ranking()
                ranking["tiers"][-1]["model_ids"] = [model_id]
                original = json.dumps(ranking)
                path.write_text(original, "utf-8")
                with self.assertRaisesRegex(pelican.EvidenceError, "each known model exactly once"):
                    self.build()
                self.assertEqual(path.read_text("utf-8"), original)
                self.assertEqual(list(self.output.iterdir()), [path])
                self.assertFalse(self.media_output.exists())

    def test_tampered_exported_record_aborts_before_output(self):
        (self.payload / self.catalog["models"]["sol"]["results_path"]).write_text("tampered", "utf-8")
        with self.assertRaisesRegex(pelican.EvidenceError, "SHA-256 or byte count mismatch"):
            self.build()
        self.assertFalse(self.output.exists())
        self.assertFalse(self.media_output.exists())

    def test_wrong_episode_or_goal_is_rejected(self):
        canvas = Path(self.sources["sol"]["media"][0]["source_canvas"])
        metadata_path = canvas.with_name("metadata.json")
        metadata = json.loads(metadata_path.read_text("utf-8"))
        metadata["episode_guid"] = "f" * 32
        metadata_path.write_text(json.dumps(metadata), "utf-8")
        with self.assertRaisesRegex(pelican.EvidenceError, "identity"):
            self.build()
        metadata["episode_guid"] = self.sources["sol"]["media"][0]["source_episode_guid"]
        metadata["painting_goal"] = "Draw a bridge"
        metadata_path.write_text(json.dumps(metadata), "utf-8")
        with self.assertRaisesRegex(pelican.EvidenceError, "task conditions"):
            self.build()

    def test_duplicate_attempt_or_missing_model_is_rejected(self):
        self.sources["sol"]["media"][0]["attempt"] = 1
        self.save()
        with self.assertRaisesRegex(pelican.EvidenceError, "unambiguous"):
            self.build()
        del self.sources["sol"]
        self.save()
        with self.assertRaisesRegex(pelican.EvidenceError, "11 curated"):
            self.build()

    def test_unapproved_video_or_changed_protocol_is_rejected(self):
        self.publication["items"][0]["url"] = "https://127.0.0.1/video/BV1234567890/"
        self.save()
        with self.assertRaisesRegex(pelican.EvidenceError, "public video URL"):
            self.build()
        self.publication["items"][0]["url"] = "https://www.bilibili.com/video/BV1234567890/"
        self.catalog["models"]["sol"]["protocol"] = {**pelican.PROTOCOL, "physics_frequency_hz": 240}
        self.save()
        with self.assertRaisesRegex(pelican.EvidenceError, "benchmark protocol"):
            self.build()

    def test_existing_different_media_is_preserved(self):
        destination = self.media_output / "pelican/sol/attempt-01.png"
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b"existing owner media")
        with self.assertRaisesRegex(pelican.EvidenceError, "Refusing to overwrite"):
            self.build()
        self.assertEqual(destination.read_bytes(), b"existing owner media")
        self.assertFalse(self.output.exists())

    def test_incomplete_or_changed_speed_receipt_is_rejected(self):
        self.delivery["speed_in_simulated_time"] = 6
        self.save()
        with self.assertRaisesRegex(pelican.EvidenceError, "4x collection"):
            self.build()


if __name__ == "__main__":
    unittest.main()
