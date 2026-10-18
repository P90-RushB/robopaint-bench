"""Recover the retained Argon rollout from frozen audit evidence, entirely offline.

This writes AgentArk's existing result and trajectory formats using its own
writers. It never instantiates an environment or model. Input files are opened
read-only, and the explicitly selected output directory must not already exist.
Run with an existing AgentArk Python environment; no API key is needed.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import importlib
import io
import json
from pathlib import Path
import re
import sys

# Importing the retained harness could alter its directory through __pycache__.
# We do not import it, and suppress bytecode for all other offline imports too.
sys.dont_write_bytecode = True

STEM = "RobotPainting_argon_recovered"
SEGMENTS = (
    {"name": "argon_original", "relative": "linux/argon/audit",
     "identity": "5c5ccb786384281056cc",
     "index_sha256": "8771f9b08959da680fffdce785abfb8d3cb762ba83f064a482187a4620e49d71"},
    {"name": "argon_resume_02", "relative": "recovery/argon_resume_02/audit",
     "identity": "413440e88d6f1b5f2c3f",
     "index_sha256": "90f175ddf10ee9144de68c264f8d09e8b09842ce301f16965bc48bc7954da52d"},
)
EXPECTED_ATTEMPT_COUNTS = [26, 21, 24]
CAMERA_LABEL = re.compile(r"Image: \[([^\]]*?)Camera (\d+)\s*[·|]\s*Frame (\d+)/(\d+)\]")


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_identity(events):
    start = next(event for event in events if event.get("kind") == "audit_start")
    fields = {key: start.get(key) for key in ("time_utc", "time_unix", "monotonic_ns")}
    return sha256_bytes(json.dumps(fields, sort_keys=True).encode("utf-8"))[:20]


def contained_path(root, relative):
    """Reject traversal and symlink escapes in untrusted audit descriptors."""
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Audit reference must be a contained relative path")
    resolved = (root / relative).resolve(strict=True)
    if not resolved.is_relative_to(root.resolve(strict=True)):
        raise ValueError("Audit reference escapes source directory")
    return resolved


def artifact_descriptors(value):
    if isinstance(value, dict):
        if {"path", "sha256", "bytes", "gzip"}.issubset(value):
            yield value
        else:
            for item in value.values():
                yield from artifact_descriptors(item)
    elif isinstance(value, list):
        for item in value:
            yield from artifact_descriptors(item)


def blob_descriptors(value):
    """Only audit markers are local blobs; embedded provenance has other scopes."""
    if isinstance(value, dict):
        if "__audit_blob__" in value:
            yield value["__audit_blob__"]
        else:
            for item in value.values():
                yield from blob_descriptors(item)
    elif isinstance(value, list):
        for item in value:
            yield from blob_descriptors(item)


class AuditSource:
    def __init__(self, directory, *, name, expected_identity, expected_index_sha256):
        self.directory = Path(directory).resolve(strict=True)
        self.name = name
        raw = (self.directory / "index.jsonl").read_bytes()
        self.index_sha256 = sha256_bytes(raw)
        if self.index_sha256 != expected_index_sha256:
            raise ValueError(f"{name}: source index SHA-256 mismatch")
        self.events = [json.loads(line) for line in raw.splitlines() if line.strip()]
        self.identity = audit_identity(self.events)
        if self.identity != expected_identity:
            raise ValueError(f"{name}: audit identity mismatch")
        if [event["audit_seq"] for event in self.events] != list(range(1, len(self.events) + 1)):
            raise ValueError(f"{name}: missing or duplicated audit sequence")
        self.verified = {}

    def read_reference(self, descriptor):
        if descriptor.get("complete") is False or descriptor.get("credential_payload_suppressed"):
            raise ValueError(f"{self.name}: incomplete or suppressed audit payload")
        if not descriptor.get("path"):
            raise ValueError(f"{self.name}: absent audit payload path")
        path = contained_path(self.directory, descriptor["path"])
        wire = path.read_bytes()
        raw = gzip.decompress(wire) if descriptor.get("gzip") else wire
        digest = sha256_bytes(raw)
        if digest != descriptor["sha256"] or len(raw) != descriptor["bytes"]:
            raise ValueError(f"{self.name}: payload SHA-256/size mismatch: {descriptor['path']}")
        metadata = {"path": descriptor["path"], "bytes": len(raw), "sha256": digest,
                    "stored_bytes": len(wire), "stored_sha256": sha256_bytes(wire)}
        old = self.verified.get(descriptor["path"])
        if old is not None and old != metadata:
            raise ValueError(f"{self.name}: conflicting reference or changed source file")
        self.verified[descriptor["path"]] = metadata
        return raw

    def restore(self, value):
        if isinstance(value, list):
            return [self.restore(item) for item in value]
        if not isinstance(value, dict):
            return value
        if "__audit_image__" in value:
            from PIL import Image
            image = Image.open(io.BytesIO(self.restore(value["__audit_image__"])))
            image.load()
            if list(image.size) != value["size"] or image.mode != value["mode"]:
                raise ValueError(f"{self.name}: audit image metadata mismatch")
            return image
        if "__audit_ndarray__" in value:
            import numpy as np
            array = np.load(io.BytesIO(self.restore(value["__audit_ndarray__"])), allow_pickle=False)
            if list(array.shape) != value["shape"] or str(array.dtype) != value["dtype"]:
                raise ValueError(f"{self.name}: audit ndarray metadata mismatch")
            return array
        if "__audit_blob__" in value:
            return self.read_reference(value["__audit_blob__"])
        if "__audit_unsupported_type__" in value:
            raise ValueError(f"{self.name}: unsupported original value cannot be reconstructed")
        return {key: self.restore(item) for key, item in value.items()}

    def record(self, event):
        return self.restore(json.loads(self.read_reference(event["record"])))

    def verify_all_references(self):
        """Verify every indexed record, HTTP body and recursively linked blob."""
        for event in self.events:
            for descriptor in artifact_descriptors(event):
                if descriptor["path"] not in self.verified:
                    self.read_reference(descriptor)
            if "record" in event:
                value = json.loads(self.read_reference(event["record"]))
                for descriptor in blob_descriptors(value):
                    if descriptor["path"] not in self.verified:
                        self.read_reference(descriptor)

    def event_for(self, kind, turn_index=None, *, phase=None):
        matches = [event for event in self.events if event["kind"] == kind
                   and (turn_index is None or event.get("turn_index") == turn_index)
                   and (phase is None or event.get("recovery_phase") == phase)]
        if len(matches) != 1:
            raise ValueError(f"{self.name}: expected one {kind} for turn {turn_index}, found {len(matches)}")
        return matches[0]


def verify_source_manifest(path, source_root, audits):
    """Check stored bytes against the pre-existing, independent retention manifest."""
    manifest = json.loads(Path(path).read_text("utf-8"))
    prefixes = [audit.directory.relative_to(source_root).as_posix() + "/" for audit in audits]
    candidates = []
    for entry in manifest.get("roots", {}).values():
        files = {item["path"]: item for item in entry.get("files", [])}
        if all(prefix + "index.jsonl" in files for prefix in prefixes):
            candidates.append(files)
    if len(candidates) != 1:
        raise ValueError("Retention manifest must contain one matching source tree")
    files = candidates[0]
    checked = []
    for prefix, audit in zip(prefixes, audits):
        expected = {key: value for key, value in files.items() if key.startswith(prefix)}
        actual = {item.relative_to(source_root).as_posix(): item for item in audit.directory.rglob("*") if item.is_file()}
        if set(actual) != set(expected):
            raise ValueError(f"{audit.name}: audit file inventory differs from retention manifest")
        for key, file_path in actual.items():
            item = expected[key]
            if file_path.stat().st_size != item["bytes"] or sha256_file(file_path) != item["sha256"]:
                raise ValueError(f"Retention SHA-256 mismatch: {key}")
        checked.append({"segment": audit.name, "files": len(actual),
                        "bytes": sum(item["bytes"] for item in expected.values())})
    return {"manifest_sha256": sha256_file(path), "audits": checked}


def project_observation(observation, *, before_action=False):
    """Retain exact API messages and add a declared viewer projection.

    Only explicitly labeled workspace cameras become vis. Additional/reference
    images remain exclusively in the original messages. An auto-reset message
    carries the preceding terminal images, so they must not be shown as the next
    attempt's initial workspace. For post-action observations those same images
    are the genuine terminal camera evidence.
    """
    from PIL import Image
    if not isinstance(observation, dict) or not isinstance(observation.get("messages"), list):
        raise ValueError("Expected the original model-visible messages observation")
    projected = dict(observation)
    text_chunks = []
    cameras = {}
    all_text = []
    for message in observation["messages"]:
        content = message.get("content", "")
        parts = content if isinstance(content, list) else [{"type": "text", "text": content}]
        label = None
        for part in parts:
            if part.get("type") == "text":
                text = part.get("text", "")
                text_chunks.append(text)
                all_text.append(text)
                matches = list(CAMERA_LABEL.finditer(text))
                label = matches[-1] if matches else None
            elif part.get("type") == "image_url" and label is not None:
                description, camera, frame, frame_count = label.groups()
                if not ("Initial view" in description or "Current attempt" in description):
                    raise ValueError("Unrecognized workspace image label")
                payload = part.get("image_url", {})
                url = payload.get("url") if isinstance(payload, dict) else payload
                if not isinstance(url, str) or not url.startswith("data:image/") or ";base64," not in url:
                    raise ValueError("Expected an exact embedded workspace image")
                encoded = url.split(",", 1)[1]
                image = Image.open(io.BytesIO(base64.b64decode(encoded, validate=True)))
                image.load()
                position = (int(camera), int(frame))
                if position in cameras:
                    raise ValueError("Ambiguous repeated workspace camera label")
                cameras[position] = (image, int(frame_count))
                label = None
    joined_text = "\n\n".join(text_chunks)
    reset_package = any("Auto-reset started attempt" in text for text in all_text)
    if before_action and reset_package:
        cameras = {}
    if cameras:
        camera_ids = sorted({camera for camera, _ in cameras})
        if camera_ids != list(range(1, max(camera_ids) + 1)):
            raise ValueError("Workspace camera numbering is not contiguous")
        vis = []
        for camera in camera_ids:
            frames = sorted(frame for cam, frame in cameras if cam == camera)
            expected_count = cameras[(camera, frames[0])][1]
            if frames != list(range(1, expected_count + 1)):
                raise ValueError("Workspace frame sequence is incomplete")
            vis.append([cameras[(camera, frame)][0] for frame in frames])
        projected["vis"] = vis
    projected["step_msg"] = joined_text
    projected["audit_observation_projection"] = {
        "source_surface": "exact model-visible API messages",
        "raw_internal_observation_recovered": False,
        "text_projection": "all original message text in order, separated by two newlines",
        "image_projection": "explicitly labeled workspace cameras only",
        "auto_reset_message_package": reset_package,
        "prior_terminal_images_omitted_from_new_attempt_pre_observation": bool(before_action and reset_package),
    }
    return projected


def collect_decisions(audits):
    decisions, excluded = [], []
    for audit in audits:
        for event in audit.events:
            if event["kind"] != "env_step_return":
                continue
            if event.get("recovery_phase") == "physical_rehydration":
                excluded.append({"segment": audit.name, "audit_seq": event["audit_seq"],
                                 "turn_index": event.get("turn_index"), "reason": "physical prefix replay"})
                continue
            turn = event.get("turn_index")
            phase = event.get("recovery_phase")
            start = audit.event_for("env_step_start", turn, phase=phase)
            request = audit.event_for("agent_forward_with_trace_start", turn, phase=phase)
            response = audit.event_for("agent_forward_with_trace_return", turn, phase=phase)
            hook_request = audit.event_for("hook_agent_request", turn, phase=phase)
            action_args = audit.record(start)
            actions = action_args["args"][0]
            before = audit.record(request)["args"][0]
            returned_actions, trace = audit.record(response)
            after, reward, done, info = audit.record(event)
            if actions != returned_actions or set(actions) != {"0"} or set(before) != {"0"} or set(after) != {"0"}:
                raise ValueError(f"{audit.name}: mismatched actions or agent IDs at turn {turn}")
            if trace["0"].get("action_extracted") != actions["0"].get("action"):
                raise ValueError(f"{audit.name}: response/action mismatch at turn {turn}")
            if info["sub_env"]["step"].get("turn_index") != turn:
                raise ValueError(f"{audit.name}: environment turn mismatch")
            hook = audit.record(hook_request)["payload"]
            decisions.append({"turn_index": turn, "before": before, "after": after,
                              "actions": actions, "trace": trace, "reward": reward,
                              "done": done, "info": info, "hook_request": hook,
                              "source": {"segment": audit.name, "audit_identity": audit.identity,
                                         "events": {kind: {"audit_seq": row["audit_seq"], **row["record"]}
                                                    for kind, row in [("request", request), ("response", response),
                                                                      ("step_start", start), ("step_return", event)]}}})
    if [item["turn_index"] for item in decisions] != list(range(len(decisions))):
        raise ValueError("Logical decisions have a gap, duplicate, or reordered turn")
    return decisions, excluded


def load_official(agentark_root):
    source = Path(agentark_root).resolve(strict=True) / "src"
    if not (source / "agent_ark/ark_eval/trajectory_io.py").is_file():
        raise ValueError("--agentark-root must contain src/agent_ark")
    sys.path.insert(0, str(source))
    modules = {name: importlib.import_module("agent_ark.ark_eval." + name)
               for name in ("run_api_agent", "trajectory_io", "run_replay")}
    for module in modules.values():
        if not Path(module.__file__).resolve().is_relative_to(source):
            raise ValueError("An already imported AgentArk installation differs from --agentark-root")
    return modules


def build_records(audits, official):
    decisions, excluded = collect_decisions(audits)
    counts = Counter(item["info"]["attempt"]["index"] for item in decisions)
    if [counts[index] for index in sorted(counts)] != EXPECTED_ATTEMPT_COUNTS or len(excluded) != 6:
        raise ValueError(f"Unexpected retained rollout or hydration counts: {dict(counts)}, {len(excluded)}")
    api = official["run_api_agent"]
    steps, history = [], {0: [[], [], []]}
    for item in decisions:
        actions = item["actions"]
        info = item["info"]
        attempt = info["attempt"]["index"]
        step = {
            "turn_index": item["turn_index"],
            "action_preview": api.preview_action(actions),
            "assistant_preview": api.preview_assistant(actions),
            "reward_total": sum(float(value) for value in item["reward"].values()),
            "reward_by_agent": item["reward"], "done": item["done"], "info": info,
            "request_messages": item["hook_request"]["request_messages"],
            "raw_request_by_agent": item["hook_request"]["raw_trace_by_agent"],
            "raw_response_by_agent": item["trace"],
            "step_messages": api.collect_step_messages(item["after"]),
            "audit_reconstruction_source": item["source"],
        }
        steps.append(step)
        history[0][attempt - 1].append({
            "obs": project_observation(item["before"]["0"], before_action=True),
            "next_obs": project_observation(item["after"]["0"]),
            "action": actions["0"]["action"], "assistant": actions["0"].get("assistant"),
            "reward": item["reward"]["0"],
            "done": bool(info["sub_env"]["attempt_done"]["0"]),
        })
    original = audits[0]
    reset_obs, reset_info = original.record(original.event_for("env_reset_return"))
    config = original.record(original.event_for("launcher_config"))
    model = config["models"][0]
    case = config["eval"]["cases"][0]
    final = decisions[-1]["info"]["rollout"]
    errors = [{"segment": original.name, "kind": event["kind"], "audit_seq": event["audit_seq"],
               "payload": original.record(event)} for event in original.events
              if event["kind"] in ("sdk_error", "launcher_error")]
    source_http_error = next(item["payload"] for item in errors if item["kind"] == "sdk_error")
    if source_http_error.get("status_code") != 413:
        raise ValueError("Original source failure is not the pinned HTTP 413 event")
    summary = api.summarize_attempt_rewards(steps, reset_info)
    result = {
        "status": "reconstructed", "record_reconstruction": True, "reconstructed_record": True,
        "source_run_finalized": False, "original_generator_finalized": False,
        "original_exit": None, "source_http_error": source_http_error,
        "case_id": case["case_id"], "model_name": model["name"], "model": model["model"],
        "provider": model["provider"], "agent_type": model["agent_type"],
        "base_url": model["base_url"], "api_key_env": model.get("api_key_env"),
        "reasoning_effort": model.get("reasoning_effort"),
        "max_completion_tokens": model.get("max_completion_tokens"),
        "requested_task_name": case["task_name"], "actual_task_name": final["task_name"],
        "requested_group_seed": case["group_seed"], "actual_group_seed": final["group_seed"],
        "actual_rollout_group_seed": final["rollout_group_seed"],
        "initial_attempt_group_seed": reset_info["attempt"]["attempt_group_seed"],
        "final_attempt_group_seed": final["current_attempt_group_seed"],
        "attempt_group_seed_history": final["attempt_group_seed_history"],
        "reroll_group_seed_on_same_task": final["reroll_group_seed_on_same_task"],
        "requested_env_id": final["env_id"], "actual_env_id": final["env_id"],
        "unity_id": 0, "start_attempt_index": 1, "loaded_history_attempt_count": 0,
        "turns": len(steps), "max_attempts": final["max_attempts"],
        "max_steps_per_attempt": final["max_steps_per_attempt"],
        "rollout_step_budget": final["max_rollout_steps"], "rollout_budget_exhausted": False,
        "attempt_count": summary["attempt_count"], "score_reward": summary["last_attempt_reward"],
        "last_attempt_index": summary["last_attempt_index"], "last_attempt_reward": summary["last_attempt_reward"],
        "best_attempt_reward": summary["best_attempt_reward"],
        "final_attempt_success": summary["final_attempt_success"],
        "ever_attempt_success": summary["ever_attempt_success"],
        "first_success_attempt_index": summary["first_success_attempt_index"],
        "success_attempt_count": summary["success_attempt_count"], "attempt_rewards": summary["attempts"],
        "done_all": bool(final["success"] or final["truncated"]), "truncated_all": final["truncated"],
        "rollout_success": final["success"], "rollout_truncated": final["truncated"],
        "rollout_terminal": bool(final["success"] or final["truncated"]),
        "total_reward": sum(step["reward_total"] for step in steps), "reset_info": reset_info,
        "initial_obs_summary": api.summarize_obs(0, reset_obs["0"]), "duration_s": None, "steps": steps,
    }
    trajectory = official["trajectory_io"].build_eval_trajectory_record(
        result=result, case=case, model_runtime=model, history_snapshot=history,
        prefix_attempts=None, include_images=True)
    trajectory["reconstruction"] = {
        "reconstructed_record": True, "source_run_finalized": False, "original_exit": None,
        "source_http_error": source_http_error,
        "observation_surface": "model-visible API messages plus explicitly labeled viewer projections",
        "raw_internal_history_snapshot_recovered": False,
        "full_logical_history_instead_of_retained_24_step_cache": True,
        "result_status": "reconstructed",
    }
    provenance = {
        "schema_version": 1, "generated_utc": datetime.now(timezone.utc).isoformat(),
        "reconstructed_record": True, "source_run_finalized": False, "original_generator_finalized": False,
        "original_exit": None, "source_http_error": source_http_error, "original_errors": errors,
        "models_called": 0, "environments_started": 0, "source_files_written": 0,
        "logical_steps": len(steps), "attempt_steps": [len(attempt) for attempt in history[0]],
        "excluded_physical_rehydration_steps": excluded,
        "excluded_resume_01": "not read; failed recovery contains no new model decisions",
        "sources": [{"segment": audit.name, "audit_identity": audit.identity,
                     "index_sha256": audit.index_sha256, "events": len(audit.events),
                     "verified_payloads": len(audit.verified)} for audit in audits],
        "source_priority": {
            "complete_get_records_or_export_snapshots_found": False,
            "resume_reset_history_snapshot_attempt_steps": [24],
            "reason_snapshot_not_used": "retained history is shorter than the 26-action first attempt",
            "selected": "full agent_forward_with_trace inputs/returns and env_step inputs/returns",
            "analysis_briefs_used_as_record_source": False,
        },
        "fidelity": {
            "messages": "Original API messages, image data URLs, actions, assistant text and traces are retained.",
            "vis": "PIL pixels decoded only from explicit Camera N / Frame N labels; official serializer writes PNG.",
            "references": "Additional/reference images remain in messages and never become extra workspace cameras.",
            "auto_reset": "Terminal+reset API messages remain intact. Their camera projection is terminal evidence; the next attempt pre-observation omits these prior-terminal vis frames.",
            "limits": "Internal raw vis/step_msg/history state was not fully audited and is not claimed recovered. Original exit code and post-rollout process outcome are unknown. This is not an original successful finalization.",
        },
        "official_format": {"result_writer": "agent_ark.ark_eval.run_api_agent.JsonlWriter",
                            "trajectory_builder": "agent_ark.ark_eval.trajectory_io.build_eval_trajectory_record",
                            "trajectory_writer": "agent_ark.ark_eval.trajectory_io.TrajectoryJsonlWriter",
                            "result_loader": "agent_ark.ark_eval.run_replay._jsonl_records",
                            "trajectory_loader": "agent_ark.ark_eval.trajectory_io.load_trajectory_records",
                            "replay_selection": {"status": None, "index": 0}},
        "step_sources": [item["source"] for item in decisions],
    }
    return result, trajectory, provenance


def validate_offline(results_path, trajectories_path, official):
    replay = official["run_replay"]
    records = replay.select_replay_records(replay._jsonl_records(str(results_path)), {"status": None, "index": 0})
    if len(records) != 1 or records[0]["turns"] != 71:
        raise ValueError("Official result loader did not recover exactly one 71-action rollout")
    result = records[0]
    case = replay.replay_case_from_record(result)
    agent = replay.ReplayAgent(result)
    for step in result["steps"]:
        action = agent.forward_with_trace({0: {"skip_infer": False}})[0][0]["action"]
        if action != step["raw_response_by_agent"]["0"]["action_extracted"]:
            raise ValueError("Official ReplayAgent changed a recovered action")
    trajectory_io = official["trajectory_io"]
    records = trajectory_io.load_trajectory_records(str(trajectories_path))
    if len(records) != 1:
        raise ValueError("Official trajectory loader did not recover exactly one record")
    history = trajectory_io.history_snapshot_from_record(records[0])
    if set(history) != {0} or [len(attempt) for attempt in history[0]] != EXPECTED_ATTEMPT_COUNTS:
        raise ValueError("Official trajectory history has wrong IDs or attempt lengths")
    projected_frames = sum(len(camera) for attempt in history[0] for step in attempt
                           for field in ("obs", "next_obs") for camera in step[field].get("vis", []))
    for attempt in history[0]:
        if [step["done"] for step in attempt] != [False] * (len(attempt) - 1) + [True]:
            raise ValueError("Recovered attempt terminal boundaries are inconsistent")
    flattened = [step["action"] for attempt in history[0] for step in attempt]
    if flattened != [replay.extract_replay_action(step) for step in result["steps"]]:
        raise ValueError("Result and trajectory actions diverged")
    return {"official_loaders_passed": True, "replay_agent_actions_consumed": agent.turn_index,
            "attempt_steps": [len(attempt) for attempt in history[0]], "projected_workspace_frames": projected_frames,
            "case": case, "unity_or_model_started": False,
            "physical_replay_performed": False}


def recover(args):
    source_root = Path(args.source_root).expanduser().resolve(strict=True)
    output_dir = Path(args.output_dir).expanduser().resolve()
    if output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {output_dir}")
    if output_dir.is_relative_to(source_root) or source_root.is_relative_to(output_dir):
        raise ValueError("Output directory must be separate from the retained source tree")
    audits = [AuditSource(source_root / spec["relative"], name=spec["name"],
                          expected_identity=spec["identity"], expected_index_sha256=spec["index_sha256"])
              for spec in SEGMENTS]
    manifest_check = verify_source_manifest(args.source_manifest, source_root, audits) if args.source_manifest else None
    for audit in audits:
        audit.verify_all_references()
    official = load_official(args.agentark_root)
    result, trajectory, provenance = build_records(audits, official)
    provenance["source_manifest_check"] = manifest_check
    provenance["official_source_sha256"] = {name: sha256_file(module.__file__) for name, module in official.items()}
    provenance["recovery_tool_sha256"] = sha256_file(__file__)
    output_dir.mkdir(parents=True, exist_ok=False)
    results_path = output_dir / (STEM + "_results.jsonl")
    trajectories_path = output_dir / (STEM + "_trajectories.jsonl")
    official["run_api_agent"].JsonlWriter(str(results_path)).write(result)
    official["trajectory_io"].TrajectoryJsonlWriter(str(trajectories_path)).write(trajectory)
    # Drop the construction objects before the official loaders decode all images.
    del result, trajectory
    provenance["offline_validation"] = validate_offline(results_path, trajectories_path, official)
    provenance["artifacts"] = [{"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
                               for path in (results_path, trajectories_path)]
    report_path = output_dir / "recovery_provenance.json"
    with report_path.open("x", encoding="utf-8") as stream:
        json.dump(provenance, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    with (output_dir / "verified_source_payloads.json").open("x", encoding="utf-8") as stream:
        json.dump({audit.name: sorted(audit.verified.values(), key=lambda item: item["path"])
                   for audit in audits}, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return report_path


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--source-root", required=True, help="Retained 20261018_openrouter_formal directory (read-only)")
    result.add_argument("--output-dir", required=True, help="New directory outside the source tree; refuses an existing path")
    result.add_argument("--agentark-root", required=True, help="Existing AgentArk checkout containing src/agent_ark")
    result.add_argument("--source-manifest", help="Optional pre-existing independent file SHA-256 manifest")
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    print(recover(args))


if __name__ == "__main__":
    main()
