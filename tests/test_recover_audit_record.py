"""Offline recovery checks. No model, Unity process, or network is permitted."""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

# Import dependencies before the process guard (NumPy may probe Windows).
from agent_ark.ark_eval import run_api_agent, run_replay, trajectory_io

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("recover_audit_record", ROOT / "scripts/recover_audit_record.py")
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)
OFFICIAL = {"run_api_agent": run_api_agent, "run_replay": run_replay, "trajectory_io": trajectory_io}


def image_url(color):
    stream = io.BytesIO()
    Image.new("RGB", (4, 3), color).save(stream, format="PNG")
    return "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode("ascii")


def observation(*, auto_reset=False):
    initial = "Terminal observation (step_msg):\n" if auto_reset else "Environment response (step_msg):\n"
    parts = [{"type": "text", "text": initial + "Actual position is visible.\nImage: [Current attempt · After action · Camera 1 · Frame 1/1]"},
             {"type": "image_url", "image_url": {"url": image_url("red")}},
             {"type": "text", "text": "Image: [Current attempt · After action · Camera 2 · Frame 1/1]"},
             {"type": "image_url", "image_url": {"url": image_url("blue")}},
             {"type": "text", "text": ("Attempt 1 ended. Auto-reset started attempt 2.\n" if auto_reset else "") + "Additional image 1"},
             {"type": "image_url", "image_url": {"url": image_url("green")}}]
    return {"messages": [{"role": "assistant", "content": "Original public explanation."},
                         {"role": "user", "content": parts}], "skip_infer": False}


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="robopaint-audit-recovery-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        for guard in (patch("subprocess.Popen", side_effect=AssertionError("Recovery must not start processes")),
                      patch.object(socket.socket, "connect", side_effect=AssertionError("Recovery must not use the network")),
                      patch.object(run_api_agent, "build_model_runtimes", side_effect=AssertionError("Recovery must not create models"))):
            guard.start()
            self.addCleanup(guard.stop)

    def audit(self, extra_events=()):
        directory = self.root / ("audit-" + str(len(list(self.root.iterdir()))))
        directory.mkdir()
        events = [{"audit_seq": 1, "kind": "audit_start", "time_utc": "2026-10-18T00:00:00Z",
                   "time_unix": 1792281600, "monotonic_ns": 123456789}]
        for event in extra_events:
            event = dict(event)
            event["audit_seq"] = len(events) + 1
            if "payload" in event:
                raw = json.dumps(event.pop("payload"), ensure_ascii=False).encode("utf-8")
                name = "records/" + str(event["audit_seq"]) + ".json.gz"
                (directory / "records").mkdir(exist_ok=True)
                (directory / name).write_bytes(gzip.compress(raw))
                event["record"] = {"path": name, "sha256": hashlib.sha256(raw).hexdigest(),
                                   "bytes": len(raw), "gzip": True}
            events.append(event)
        raw = b"".join((json.dumps(event) + "\n").encode("utf-8") for event in events)
        (directory / "index.jsonl").write_bytes(raw)
        return recovery.AuditSource(directory, name="fixture", expected_identity=recovery.audit_identity(events),
                                    expected_index_sha256=hashlib.sha256(raw).hexdigest())

    def test_source_identity_and_index_sha_are_required(self):
        audit = self.audit()
        for identity, digest, message in (("wrong", audit.index_sha256, "identity"),
                                          (audit.identity, "wrong", "index SHA")):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                recovery.AuditSource(audit.directory, name="bad", expected_identity=identity,
                                     expected_index_sha256=digest)

    def test_record_integrity_rejects_modified_payload_and_keeps_source_read_only(self):
        audit = self.audit([{"kind": "example", "payload": {"action": "full action, not a brief"}}])
        before = {path: path.read_bytes() for path in audit.directory.rglob("*") if path.is_file()}
        audit.verify_all_references()
        self.assertEqual({"action": "full action, not a brief"}, audit.record(audit.events[1]))
        self.assertEqual(before, {path: path.read_bytes() for path in audit.directory.rglob("*") if path.is_file()})
        payload = audit.directory / audit.events[1]["record"]["path"]
        payload.write_bytes(gzip.compress(b'{"action":"changed"}'))
        with self.assertRaisesRegex(ValueError, "SHA-256/size mismatch"):
            audit.record(audit.events[1])

    def test_references_cannot_escape_or_omit_content(self):
        audit = self.audit()
        with self.assertRaisesRegex(ValueError, "contained relative"):
            recovery.contained_path(audit.directory, "../outside.txt")
        for descriptor in ({"complete": False}, {"credential_payload_suppressed": True}, {}):
            with self.subTest(descriptor=descriptor), self.assertRaises(ValueError):
                audit.read_reference(descriptor)

    def test_embedded_original_audit_provenance_is_not_resolved_in_resume_scope(self):
        audit = self.audit([{"kind": "physical_prefix_replay_action", "payload": {
            "original_event": {"record": {"path": "records/original-only.json.gz", "bytes": 12,
                                           "sha256": "preserved-original-reference", "gzip": True}}}}])
        audit.verify_all_references()
        self.assertEqual(1, len(audit.verified))
        self.assertEqual("records/original-only.json.gz", audit.record(audit.events[1])["original_event"]["record"]["path"])

    def test_projection_preserves_messages_and_excludes_reference_camera(self):
        original = observation()
        encoded = json.dumps(original)
        projected = recovery.project_observation(original)
        self.assertEqual(encoded, json.dumps(original))
        self.assertEqual(original["messages"], projected["messages"])
        self.assertEqual([1, 1], [len(camera) for camera in projected["vis"]])
        self.assertEqual((255, 0, 0), projected["vis"][0][0].getpixel((0, 0)))
        self.assertEqual((0, 0, 255), projected["vis"][1][0].getpixel((0, 0)))
        self.assertIn("Original public explanation.", projected["step_msg"])
        self.assertFalse(projected["audit_observation_projection"]["raw_internal_observation_recovered"])

    def test_auto_reset_terminal_is_not_falsely_used_as_new_attempt_view(self):
        original = observation(auto_reset=True)
        post = recovery.project_observation(original)
        pre = recovery.project_observation(original, before_action=True)
        self.assertEqual(2, len(post["vis"]))
        self.assertNotIn("vis", pre)
        self.assertEqual(original["messages"], pre["messages"])
        self.assertTrue(pre["audit_observation_projection"]["prior_terminal_images_omitted_from_new_attempt_pre_observation"])

    def test_ambiguous_workspace_label_fails_instead_of_inventing_projection(self):
        original = observation()
        original["messages"][1]["content"].extend(original["messages"][1]["content"][:2])
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            recovery.project_observation(original)

    def test_source_manifest_checks_compressed_bytes_and_inventory(self):
        audit = self.audit([{"kind": "example", "payload": {"reward": 1}}])
        manifest = self.root / "manifest.json"
        files = [{"path": path.relative_to(self.root).as_posix(), "bytes": path.stat().st_size,
                  "sha256": recovery.sha256_file(path)} for path in audit.directory.rglob("*") if path.is_file()]
        manifest.write_text(json.dumps({"roots": {"fixture": {"files": files}}}), encoding="utf-8")
        checked = recovery.verify_source_manifest(manifest, self.root, [audit])
        self.assertEqual(2, checked["audits"][0]["files"])
        (audit.directory / "unexpected-file").write_text("bad", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "inventory"):
            recovery.verify_source_manifest(manifest, self.root, [audit])

    def test_collection_excludes_physical_replay_and_preserves_full_action_trace(self):
        obs = {"0": observation()}
        action = "<tool_call>{\"name\":\"FullUntruncatedAction\",\"arguments\":{}}</tool_call>"
        actions = {"0": {"action": action, "assistant": "Original explanation"}}
        trace = {"0": {"action_extracted": action, "assistant_raw": "Original explanation",
                       "public_trace": ["tool output", "provider reasoning"]}}
        events = [
            {"kind": "env_step_return", "turn_index": 0, "recovery_phase": "physical_rehydration", "payload": []},
            {"kind": "agent_forward_with_trace_start", "turn_index": 0, "recovery_phase": "new_inference", "payload": {"args": [obs], "kwargs": {}}},
            {"kind": "agent_forward_with_trace_return", "turn_index": 0, "recovery_phase": "new_inference", "payload": [actions, trace]},
            {"kind": "hook_agent_request", "turn_index": 0, "recovery_phase": "new_inference", "payload": {"payload": {"request_messages": [], "raw_trace_by_agent": {}}}},
            {"kind": "env_step_start", "turn_index": 0, "recovery_phase": "new_inference", "payload": {"args": [actions], "kwargs": {}}},
            {"kind": "env_step_return", "turn_index": 0, "recovery_phase": "new_inference", "payload": [obs, {"0": 1}, {"0": True}, {"sub_env": {"step": {"turn_index": 0}}}]},
        ]
        audit = self.audit(events)
        decisions, excluded = recovery.collect_decisions([audit])
        self.assertEqual((1, 1), (len(decisions), len(excluded)))
        self.assertEqual(actions, decisions[0]["actions"])
        self.assertEqual(trace, decisions[0]["trace"])
        self.assertEqual(obs, decisions[0]["before"])
        audit.events[-1]["turn_index"] = 1
        with self.assertRaises(ValueError):
            recovery.collect_decisions([audit])

    def test_existing_or_source_tree_output_is_refused_before_imports(self):
        source = self.root / "source"
        source.mkdir()
        output = self.root / "existing"
        output.mkdir()
        args = argparse.Namespace(source_root=source, output_dir=output, source_manifest=None, agentark_root="not-needed")
        with self.assertRaises(FileExistsError):
            recovery.recover(args)
        args.output_dir = source / "new-output"
        with self.assertRaisesRegex(ValueError, "separate"):
            recovery.recover(args)
        self.assertFalse(args.output_dir.exists())

    def test_official_formats_and_replay_agent_load_all_three_complete_attempts(self):
        steps, history = [], {0: []}
        turn = 0
        for count in (26, 21, 24):
            attempt = []
            for index in range(count):
                action = f'<tool_call>{{"name":"FixtureAction","arguments":{{"turn":{turn}}}}}</tool_call>'
                steps.append({"turn_index": turn, "raw_response_by_agent": {"0": {"action_extracted": action,
                              "assistant_raw": "Preserved public explanation"}}})
                obs = recovery.project_observation(observation())
                attempt.append({"obs": obs, "next_obs": obs, "action": action, "assistant": "Preserved public explanation",
                                "reward": 1 if index == count - 1 else 0, "done": index == count - 1})
                turn += 1
            history[0].append(attempt)
        record = {"status": "reconstructed", "turns": 71, "steps": steps, "max_attempts": 3,
                  "requested_task_name": "RobotPainting", "requested_group_seed": 107, "unity_id": 0}
        results = self.root / "RobotPainting_fixture_results.jsonl"
        trajectories = self.root / "RobotPainting_fixture_trajectories.jsonl"
        run_api_agent.JsonlWriter(str(results)).write(record)
        native = trajectory_io.build_eval_trajectory_record(result=record, case={"task_name": "RobotPainting", "group_seed": 107},
                                                           model_runtime={"name": "fixture"}, history_snapshot=history,
                                                           prefix_attempts=None, include_images=True)
        trajectory_io.TrajectoryJsonlWriter(str(trajectories)).write(native)
        report = recovery.validate_offline(results, trajectories, OFFICIAL)
        self.assertTrue(report["official_loaders_passed"])
        self.assertEqual(71, report["replay_agent_actions_consumed"])
        self.assertEqual([26, 21, 24], report["attempt_steps"])
        self.assertGreater(report["projected_workspace_frames"], 0)
        self.assertFalse(report["unity_or_model_started"])


if __name__ == "__main__":
    unittest.main()
