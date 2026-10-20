"""Offline evidence and aggregation tests. Never runs a model or Unity."""
import copy
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import prepare_human_review as prepare
import score_human_review as scoring


def png_bytes(color):
    def chunk(kind, value):
        return struct.pack(">I", len(value)) + kind + value + struct.pack(">I", zlib.crc32(kind + value))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 1, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(b"\x00" + bytes(color) * 2)) + chunk(b"IEND", b"")


class HumanReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.site = self.root / "site"
        self.site.mkdir()
        self.patch = patch.object(prepare, "ROOT", self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        models = []
        for i in range(11):
            entry = self.image(f"model-{i}.png", (i, 80, 140))
            models.append({"id": f"model-{i:02d}", "label": f"Secret Model {i}", "attempts": [{"attempt": 3, "canvas": entry}]})
        self.dataset = self.root / "dataset.json"
        self.data = {"schema": "robopaint.public-results.v1", "case_id": "golden_gate", "release_id": "fixture",
                     "target": {"reference": self.image("reference.png", (1, 2, 3))}, "models": models}
        self.write(self.dataset, self.data)

    def image(self, name, color):
        data = png_bytes(color)
        (self.site / name).write_bytes(data)
        return {"path": name, "sha256": prepare.digest(data), "bytes": len(data), "width": 2, "height": 1}

    def write(self, path, value):
        path.write_text(json.dumps(value), "utf-8")
        return path

    def package(self, rater="rater-1", seed="123"):
        output = self.root / "local_save" / rater
        prepare.prepare(self.dataset, self.site, output, rater, seed)
        key_path = output / "administrator-key.json"
        return key_path, prepare.read_json(key_path)

    def review(self, key, choice="tie"):
        result = {field: key[field] for field in ("package_id", "rater_id", "dataset_sha256", "selection_sha256", "reference_sha256", "primary_attempt")}
        result.update(schema=prepare.SCHEMA, independence_attestation=True,
                      answers=[{**pair, "choice": choice} for pair in key["pairs"]])
        return result

    def test_all_pairs_equal_size_blind_payload(self):
        path, key = self.package()
        prepare_manifest, _ = prepare.load_dataset(self.dataset, self.site)
        scoring.validate_key(key, prepare_manifest)
        self.assertEqual(55, len(key["pairs"]))
        html = (path.parent / "review.html").read_text("utf-8")
        self.assertIn("data:image/png;base64,", html)
        for model in self.data["models"]:
            self.assertNotIn(model["id"], html)
            self.assertNotIn(model["label"], html)
            self.assertNotIn(model["attempts"][0]["canvas"]["path"], html)
        self.assertNotIn(str(self.root), html)
        self.assertNotIn("fetch(", html)
        self.assertNotIn("XMLHttpRequest", html)

    def test_order_deterministic_for_rater_and_seed(self):
        _, first = self.package()
        second_output = self.root / "local_save/second"
        prepare.prepare(self.dataset, self.site, second_output, "rater-1", "123")
        second = prepare.read_json(second_output / "administrator-key.json")
        def model_order(key):
            return [(key["attempt_mapping"][p["a"]]["model_id"], key["attempt_mapping"][p["b"]]["model_id"]) for p in key["pairs"]]
        self.assertEqual(model_order(first), model_order(second))
        _, third = self.package("rater-2")
        self.assertNotEqual(model_order(first), model_order(third))

    def test_no_overwrite_or_output_outside_local_save(self):
        self.package()
        with self.assertRaises(prepare.ReviewError):
            self.package()
        with self.assertRaises(prepare.ReviewError):
            prepare.prepare(self.dataset, self.site, self.root / "public", "rater", "1")

    def test_refuses_tampered_canvas_reference_or_dataset(self):
        path, key = self.package()
        review = self.write(path.parent / "answers.json", self.review(key))
        image = self.site / self.data["target"]["reference"]["path"]
        image.write_bytes(b"altered")
        with self.assertRaisesRegex(prepare.ReviewError, "hash"):
            scoring.score(self.dataset, self.site, [path], [review])
        image.write_bytes(png_bytes((1, 2, 3)))
        self.dataset.write_text(self.dataset.read_text("utf-8") + "\n", "utf-8")
        with self.assertRaisesRegex(prepare.ReviewError, "identity"):
            scoring.score(self.dataset, self.site, [path], [review])

    def test_requires_exact_pairs_and_unchanged_sides(self):
        _, key = self.package()
        for mutation in ("missing", "duplicate", "flipped", "unknown_choice", "no_attestation"):
            with self.subTest(mutation=mutation):
                review = self.review(key)
                if mutation == "missing": review["answers"].pop()
                if mutation == "duplicate": review["answers"][-1] = copy.deepcopy(review["answers"][0])
                if mutation == "flipped": review["answers"][0]["a"], review["answers"][0]["b"] = review["answers"][0]["b"], review["answers"][0]["a"]
                if mutation == "unknown_choice": review["answers"][0]["choice"] = "unknown"
                if mutation == "no_attestation": review["independence_attestation"] = False
                with self.assertRaises(prepare.ReviewError):
                    scoring.validate_review(review, key)

    def test_three_complete_raters_allow_descriptive_ranking(self):
        keys, reviews = [], []
        for i in range(3):
            path, key = self.package(f"rater-{i}")
            keys.append(path)
            content = self.review(key)
            reviews.append(self.write(path.parent / "answers.json", content))
            report = scoring.score(self.dataset, self.site, keys, reviews)
            self.assertEqual("withheld" if i < 2 else "eligible_descriptive", report["ranking_status"])
        self.assertTrue(all(row["tie_adjusted_win_rate"] == .5 for row in report["scores"]))
        self.assertTrue(all(row["presented_comparisons"] == 30 for row in report["scores"]))
        self.assertTrue(all(row["rank"] == 1 for row in report["ranking"]))

    def test_cannot_judge_counts_and_incomplete_pair_coverage(self):
        keys, reviews = [], []
        for i in range(3):
            path, key = self.package(f"rater-{i}")
            keys.append(path)
            content = self.review(key)
            content["answers"][0]["choice"] = "cannot_judge"
            reviews.append(self.write(path.parent / "answers.json", content))
        report = scoring.score(self.dataset, self.site, keys, reviews)
        self.assertEqual(6, sum(row["cannot_judge"] for row in report["scores"]))
        self.assertEqual("withheld", report["ranking_status"])
        self.assertTrue(report["pending_pairs"])
        self.assertTrue(all(row["tie_adjusted_win_rate"] == .5 for row in report["scores"]))

    def test_opponents_are_weighted_equally_when_valid_vote_counts_differ(self):
        keys, reviews = [], []
        focal, other = "model-00", "model-01"
        for i in range(4):
            path, key = self.package(f"rater-{i}")
            keys.append(path)
            content = self.review(key)
            for answer in content["answers"]:
                a = key["attempt_mapping"][answer["a"]]["model_id"]
                b = key["attempt_mapping"][answer["b"]]["model_id"]
                if {a, b} == {focal, other}:
                    answer["choice"] = "A" if a == focal else "B"
                elif focal in (a, b) and i == 3:
                    answer["choice"] = "cannot_judge"
                elif focal in (a, b):
                    answer["choice"] = "B" if a == focal else "A"
            reviews.append(self.write(path.parent / "answers.json", content))
        result = scoring.score(self.dataset, self.site, keys, reviews)
        row = next(row for row in result["scores"] if row["model_id"] == focal)
        self.assertAlmostEqual(.1, row["tie_adjusted_win_rate"])
        self.assertNotAlmostEqual(4 / 31, row["tie_adjusted_win_rate"])
        self.assertEqual("eligible_descriptive", result["ranking_status"])

    def test_duplicate_rater_rejected(self):
        path, key = self.package()
        review = self.write(path.parent / "answers.json", self.review(key))
        with self.assertRaisesRegex(prepare.ReviewError, "Duplicate rater"):
            scoring.score(self.dataset, self.site, [path], [review, review])

    def test_no_judgment_cannot_create_ranking(self):
        keys, reviews = [], []
        for i in range(3):
            path, key = self.package(f"rater-{i}")
            keys.append(path)
            reviews.append(self.write(path.parent / "answers.json", self.review(key, "cannot_judge")))
        result = scoring.score(self.dataset, self.site, keys, reviews)
        self.assertIsNone(result["ranking"])
        self.assertTrue(all(row["tie_adjusted_win_rate"] is None for row in result["scores"]))

    def test_prefer_a_aggregates_actual_anonymous_mapping(self):
        path, key = self.package()
        review = self.write(path.parent / "answers.json", self.review(key, "A"))
        result = scoring.score(self.dataset, self.site, [path], [review])
        expected = {model["id"]: 0 for model in self.data["models"]}
        for pair in key["pairs"]:
            expected[key["attempt_mapping"][pair["a"]]["model_id"]] += 1
        self.assertEqual(expected, {row["model_id"]: row["wins"] for row in result["scores"]})
        self.assertIsNone(result["ranking"])


if __name__ == "__main__":
    unittest.main()
