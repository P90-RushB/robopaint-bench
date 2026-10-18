"""Offline validation gates and lossless-copy checks for recovered records."""
from __future__ import annotations

import argparse
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from agent_ark.ark_eval import run_api_agent, run_replay, trajectory_io

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("prepare_recovered_record", ROOT / "scripts/prepare_recovered_record.py")
preparation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preparation)


class ValidatedRecoveredRecordTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="robopaint-validated-copy-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.export = self.root / "immutable_export"
        self.export.mkdir()
        self.result_path = self.export / (preparation.STEM + "_results.jsonl")
        self.trajectory_path = self.export / (preparation.STEM + "_trajectories.jsonl")
        self.provenance_path = self.export / "recovery_provenance.json"
        self.replay_path, self.canvas_path = self.root / "replay.json", self.root / "canvas.json"
        self.result, self.trajectory = self.make_records()
        self.write_export()
        self.replay_report = {
            "phase": "complete", "source_record_sha256": preparation.sha256_file(self.result_path),
            "model_requests": 0, "blocked_http_attempts": [], "turns_completed": 71,
            "summary": {"status": "ok", "turns": 71, "score_reward": 1.0, "total_reward": 3.0,
                        "rollout_success": True, "rollout_truncated": False,
                        "replay": {"match": True, "checks": {key: True for key in preparation.REPLAY_CHECKS}}},
        }
        self.canvas_report = {
            "schema_version": 1, "phase": "complete",
            "source_record_sha256": preparation.sha256_file(self.result_path),
            "all_pixel_identical": True, "attempt_steps": [26, 21, 24],
            "attempts": [{"attempt": index + 1, "action_count": count,
                          "canvas": {"pixel_identical": True, "changed_pixels": 0},
                          "canvas_raw": {"pixel_identical": True, "changed_pixels": 0}}
                         for index, count in enumerate((26, 21, 24))],
        }
        self.write_reports()
        for guard in (patch("subprocess.Popen", side_effect=AssertionError("Preparation must not start processes")),
                      patch.object(socket.socket, "connect", side_effect=AssertionError("Preparation must not use the network")),
                      patch.object(run_api_agent, "build_model_runtimes", side_effect=AssertionError("Preparation must not create a model"))):
            guard.start()
            self.addCleanup(guard.stop)

    def make_records(self):
        steps, history, turn = [], {0: []}, 0
        for attempt_index, count in enumerate((26, 21, 24), start=1):
            attempt = []
            for offset in range(count):
                argument = ("long full action " * 50) if turn == 0 else str(turn)
                action = '<tool_call>' + json.dumps({"name": "FixtureAction", "arguments": {"value": argument}}) + '</tool_call>'
                assistant = "Preserved explanation " + str(turn)
                observation = {"messages": [{"role": "user", "content": "Original model-visible observation " + str(turn)}]}
                reward = 1.0 if offset == count - 1 else 0.0
                trace = {"action_extracted": action, "assistant_raw": assistant,
                         "model_requests": [{"request_messages": [observation], "reasoning": "Repeated trace"}],
                         "agent_events": [{"kind": "original public tool trace"}], "agent_usage": {"action_calls": 1}}
                steps.append({"turn_index": turn, "action_preview": action[:400], "assistant_preview": assistant,
                              "raw_request_by_agent": {"0": {"request_messages": [observation]}},
                              "raw_response_by_agent": {"0": trace}, "reward_total": reward,
                              "reward_by_agent": {"0": reward}, "done": {"0": turn == 70},
                              "info": {"attempt": {"index": attempt_index}},
                              "request_messages": [observation], "step_messages": [observation]})
                attempt.append({"obs": observation, "next_obs": observation, "action": action,
                                "assistant": assistant, "reward": reward, "done": offset == count - 1})
                turn += 1
            history[0].append(attempt)
        result = {"status": "reconstructed", "record_reconstruction": True, "reconstructed_record": True,
                  "source_run_finalized": False, "original_generator_finalized": False, "original_exit": None,
                  "source_http_error": {"status_code": 413, "error": "Original exact HTTP error"},
                  "turns": 71, "steps": steps, "score_reward": 1.0, "total_reward": 3.0,
                  "rollout_success": True, "rollout_truncated": False, "max_attempts": 3,
                  "requested_task_name": "RobotPainting", "requested_group_seed": 107, "unity_id": 0}
        native = trajectory_io.build_eval_trajectory_record(
            result=result, case={"task_name": "RobotPainting", "group_seed": 107},
            model_runtime={"name": "fixture"}, history_snapshot=history, prefix_attempts=None, include_images=True)
        native["reconstruction"] = {"reconstructed_record": True, "source_run_finalized": False,
                                    "original_exit": None, "source_http_error": result["source_http_error"]}
        return result, native

    def write_export(self):
        self.result_path.write_text(json.dumps(self.result) + "\n", encoding="utf-8")
        self.trajectory_path.write_text(json.dumps(self.trajectory) + "\n", encoding="utf-8")
        self.provenance_path.write_text(json.dumps({"logical_steps": 71, "attempt_steps": [26, 21, 24],
                                                  "artifacts": [preparation.file_identity(path)
                                                                for path in (self.result_path, self.trajectory_path)]}), encoding="utf-8")

    def write_reports(self):
        self.replay_path.write_text(json.dumps(self.replay_report), encoding="utf-8")
        self.canvas_path.write_text(json.dumps(self.canvas_report), encoding="utf-8")

    def args(self, name="prepared"):
        return argparse.Namespace(export_dir=self.export, replay_validation=self.replay_path,
                                  canvas_validation=self.canvas_path, output_dir=self.root / name,
                                  agentark_root=None)

    def inputs(self):
        return {path: path.read_bytes() for path in (self.result_path, self.trajectory_path,
                                                    self.provenance_path, self.replay_path, self.canvas_path)}

    def test_prepares_default_replay_candidate_without_altering_any_input(self):
        before = self.inputs()
        manifest_path = preparation.prepare(self.args())
        self.assertEqual(before, self.inputs())
        manifest = preparation.read_object(manifest_path)
        candidate = preparation.read_object(manifest_path.parent / self.result_path.name)
        expected = deepcopy(self.result)
        for step in expected["steps"]:
            step["raw_response_by_agent"]["0"].pop("model_requests")
            step["action_preview"] = step["raw_response_by_agent"]["0"]["action_extracted"]
        expected["status"] = "ok"
        candidate.pop("record_validation")
        self.assertEqual(expected, candidate)
        native = preparation.read_object(manifest_path.parent / self.trajectory_path.name)
        native["reconstruction"].pop("validation")
        self.assertEqual(self.trajectory, native)
        self.assertEqual(71, manifest["compaction"]["removed_field_count"])
        self.assertEqual(1, manifest["action_preview_alignment"]["changed_count"])
        self.assertEqual(71, manifest["offline_validation"]["replay_agent_actions_consumed"])
        self.assertEqual([26, 21, 24], manifest["offline_validation"]["trajectory_attempt_steps"])
        self.assertIn("original runner did not finalize", manifest["status_meaning"])
        self.assertFalse(candidate["source_run_finalized"])
        self.assertIsNone(candidate["original_exit"])

    def test_over_400_character_action_is_kept_full_and_aligns_for_human_review(self):
        original = self.result["steps"][0]
        self.assertEqual(400, len(original["action_preview"]))
        action = original["raw_response_by_agent"]["0"]["action_extracted"]
        self.assertGreater(len(action), 400)
        path = preparation.prepare(self.args())
        candidate = preparation.read_object(path.parent / self.result_path.name)
        manifest = preparation.read_object(path)
        change = manifest["action_preview_alignment"]["changes"][0]
        self.assertEqual(action, candidate["steps"][0]["action_preview"])
        self.assertEqual(action, candidate["steps"][0]["raw_response_by_agent"]["0"]["action_extracted"])
        self.assertEqual(400, change["original_chars"])
        self.assertEqual(len(action), change["derived_chars"])
        self.assertNotEqual(change["original_sha256"], change["derived_sha256"])

    def test_refuses_pending_or_mismatched_reports_before_creating_output(self):
        cases = [
            ("replay phase", lambda: self.replay_report.update(phase="replaying")),
            ("canvas phase", lambda: self.canvas_report.update(phase="pending")),
            ("replay SHA", lambda: self.replay_report.update(source_record_sha256="wrong")),
            ("canvas SHA", lambda: self.canvas_report.update(source_record_sha256="wrong")),
            ("missing check", lambda: self.replay_report["summary"]["replay"]["checks"].pop("turns_match")),
            ("failed check", lambda: self.replay_report["summary"]["replay"]["checks"].update(total_reward_match=False)),
            ("overall mismatch", lambda: self.replay_report["summary"]["replay"].update(match=False)),
            ("wrong turns", lambda: self.replay_report["summary"].update(turns=70)),
            ("wrong reward", lambda: self.replay_report["summary"].update(total_reward=0)),
            ("model calls", lambda: self.replay_report.update(model_requests=1)),
            ("unexpected HTTP", lambda: self.replay_report.update(blocked_http_attempts=["call"])),
            ("pixel mismatch", lambda: self.canvas_report["attempts"][1]["canvas_raw"].update(pixel_identical=False)),
            ("pixel contradiction", lambda: self.canvas_report["attempts"][1]["canvas"].update(changed_pixels=1)),
            ("missing attempt", lambda: self.canvas_report["attempts"].pop()),
            ("wrong count", lambda: self.canvas_report["attempts"][0].update(action_count=25)),
        ]
        original_replay, original_canvas = deepcopy(self.replay_report), deepcopy(self.canvas_report)
        for index, (name, mutate) in enumerate(cases):
            with self.subTest(name=name):
                self.replay_report, self.canvas_report = deepcopy(original_replay), deepcopy(original_canvas)
                mutate()
                self.write_reports()
                before = self.inputs()
                args = self.args("reject-" + str(index))
                with self.assertRaises(ValueError):
                    preparation.prepare(args)
                self.assertFalse(args.output_dir.exists())
                self.assertEqual(before, self.inputs())

    def test_refuses_changed_export_before_creating_output(self):
        self.result_path.write_text(self.result_path.read_text("utf-8") + " ", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "export artifact SHA"):
            preparation.prepare(self.args())
        self.assertFalse(self.args().output_dir.exists())

    def test_refuses_false_original_finalization_or_invented_exit(self):
        for key, value in (("source_run_finalized", True), ("original_generator_finalized", True),
                           ("original_exit", 0), ("record_reconstruction", False)):
            with self.subTest(key=key):
                result = deepcopy(self.result)
                result[key] = value
                with self.assertRaises(ValueError):
                    preparation.validate_source_records(result, self.trajectory, run_replay)

    def test_refuses_missing_actions_or_truncated_trajectory(self):
        result = deepcopy(self.result)
        result["steps"].pop()
        with self.assertRaisesRegex(ValueError, "71 actions"):
            preparation.validate_source_records(result, self.trajectory, run_replay)
        native = deepcopy(self.trajectory)
        native["history_snapshot"]["0"][0] = native["history_snapshot"]["0"][0][-24:]
        with self.assertRaisesRegex(ValueError, "26/21/24"):
            preparation.validate_source_records(self.result, native, run_replay)

    def test_refuses_reusing_output_or_writing_inside_export(self):
        output = self.root / "existing"
        output.mkdir()
        sentinel = output / "keep.jsonl"
        sentinel.write_text("retained", encoding="utf-8")
        args = self.args()
        args.output_dir = output
        with self.assertRaises(FileExistsError):
            preparation.prepare(args)
        self.assertEqual("retained", sentinel.read_text("utf-8"))
        args.output_dir = self.export / "new"
        with self.assertRaisesRegex(ValueError, "separate"):
            preparation.prepare(args)
        self.assertFalse(args.output_dir.exists())


if __name__ == "__main__":
    unittest.main()
