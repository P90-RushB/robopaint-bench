"""Prepare a validated, compact copy of the retained Argon recovery, offline.

The full recovery export is immutable input. Status becomes ``ok`` only after
matching completed physical-replay and three-attempt pixel-comparison reports.
It describes this derived record's validation, never original runner completion.
Only per-agent ``model_requests`` is removed from the result's repeated traces.
The display/alignment ``action_preview`` is expanded to the saved full action.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True

STEM = "RobotPainting_argon_recovered"
ATTEMPT_STEPS = [26, 21, 24]
REPLAY_CHECKS = {
    "turns_match", "score_reward_match", "total_reward_match",
    "rollout_success_match", "rollout_truncated_match",
}
STATUS_MEANING = (
    "ok means this reconstructed record passed official replay and all three "
    "canvas/canvas_raw pixel comparisons; the original runner did not finalize "
    "normally and its exit code remains unknown"
)


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path):
    # Each native file in this retained export contains exactly one JSON object.
    # json.load rejects an additional JSONL record instead of selecting silently.
    with Path(path).open("r", encoding="utf-8") as stream:
        result = json.load(stream)
    if not isinstance(result, dict):
        raise ValueError(f"Expected one JSON object: {Path(path).name}")
    return result


def file_identity(path):
    return {"path": Path(path).name, "bytes": Path(path).stat().st_size, "sha256": sha256_file(path)}


def official_modules(agentark_root=None):
    if agentark_root:
        source = Path(agentark_root).expanduser().resolve(strict=True) / "src"
        if not (source / "agent_ark/ark_eval/trajectory_io.py").is_file():
            raise ValueError("--agentark-root must contain src/agent_ark")
        sys.path.insert(0, str(source))
    modules = {name: importlib.import_module("agent_ark.ark_eval." + name)
               for name in ("run_api_agent", "run_replay", "trajectory_io")}
    if agentark_root and any(not Path(module.__file__).resolve().is_relative_to(source)
                             for module in modules.values()):
        raise ValueError("Imported AgentArk differs from --agentark-root")
    return modules


def require_source_flags(record):
    if record.get("record_reconstruction") is not True or record.get("reconstructed_record") is not True:
        raise ValueError("Input must explicitly identify itself as a reconstructed record")
    if record.get("source_run_finalized") is not False or record.get("original_generator_finalized") is not False:
        raise ValueError("Source runner finalization must remain explicitly false")
    if "original_exit" not in record or record["original_exit"] is not None:
        raise ValueError("Original exit must remain explicitly unknown")
    if record.get("source_http_error", {}).get("status_code") != 413:
        raise ValueError("Retained original HTTP 413 evidence is missing")


def validate_reports(replay_report, canvas_report, source_sha256, source_result):
    for name, report in (("replay", replay_report), ("canvas", canvas_report)):
        if report.get("phase") != "complete":
            raise ValueError(f"{name} validation is not complete")
        if report.get("source_record_sha256") != source_sha256:
            raise ValueError(f"{name} validation source result SHA-256 mismatch")
    if type(replay_report.get("model_requests")) is not int or replay_report["model_requests"] != 0:
        raise ValueError("Replay report must prove zero model requests")
    if replay_report.get("blocked_http_attempts", []) != []:
        raise ValueError("Replay reported unexpected HTTP attempts")
    summary = replay_report.get("summary", {})
    if summary.get("status") != "ok" or summary.get("turns") != 71:
        raise ValueError("Replay must complete all 71 actions with status ok")
    if "turns_completed" in replay_report and replay_report["turns_completed"] != 71:
        raise ValueError("Replay receipt does not contain 71 completed actions")
    comparison = summary.get("replay", {})
    checks = comparison.get("checks", {})
    if (comparison.get("match") is not True or not REPLAY_CHECKS.issubset(checks)
            or not checks or any(value is not True for value in checks.values())):
        raise ValueError("Every official replay comparison must match")
    for field in ("turns", "score_reward", "total_reward", "rollout_success", "rollout_truncated"):
        if field not in summary or summary[field] != source_result.get(field):
            raise ValueError(f"Replay reported {field} differs from source result")
    if canvas_report.get("schema_version") != 1 or canvas_report.get("all_pixel_identical") is not True:
        raise ValueError("Canvas validation must prove exact pixel equality")
    if canvas_report.get("attempt_steps") != ATTEMPT_STEPS:
        raise ValueError("Canvas report attempt action counts differ from 26/21/24")
    attempts = canvas_report.get("attempts", [])
    if not isinstance(attempts, list) or [item.get("attempt") for item in attempts] != [1, 2, 3]:
        raise ValueError("Canvas report must contain exactly three ordered attempts")
    for index, item in enumerate(attempts):
        if item.get("action_count") != ATTEMPT_STEPS[index]:
            raise ValueError("Canvas report contains an incorrect action count")
        for kind in ("canvas", "canvas_raw"):
            comparison = item.get(kind, {})
            if comparison.get("pixel_identical") is not True:
                raise ValueError(f"Attempt {index + 1} {kind} pixels differ or are unverified")
            if "changed_pixels" in comparison and comparison["changed_pixels"] != 0:
                raise ValueError("Canvas report contradicts its exact-pixel equality flag")


def validate_source_records(result, trajectory, replay):
    require_source_flags(result)
    steps = result.get("steps", [])
    if result.get("turns") != 71 or len(steps) != 71:
        raise ValueError("Recovered result must contain all 71 actions")
    if [step.get("turn_index") for step in steps] != list(range(71)):
        raise ValueError("Recovered actions have gaps, duplicates, or reordered turns")
    if (trajectory.get("format") != "agentark_trajectory" or trajectory.get("version") != 1
            or trajectory.get("reconstruction", {}).get("reconstructed_record") is not True
            or trajectory.get("reconstruction", {}).get("source_run_finalized") is not False
            or "original_exit" not in trajectory.get("reconstruction", {})
            or trajectory["reconstruction"]["original_exit"] is not None):
        raise ValueError("Input is not the native reconstructed trajectory")
    history = trajectory.get("history_snapshot", {})
    if set(history) != {"0"} or [len(attempt) for attempt in history["0"]] != ATTEMPT_STEPS:
        raise ValueError("Native trajectory must retain all 26/21/24 actions for agent 0")
    source_actions = [replay.extract_replay_action(step, 0) for step in steps]
    if any(not isinstance(action, str) or not action for action in source_actions):
        raise ValueError("Recovered result is missing a full action")
    if source_actions != [step.get("action") for attempt in history["0"] for step in attempt]:
        raise ValueError("Recovered result and trajectory actions do not match")
    counts = Counter(step.get("info", {}).get("attempt", {}).get("index") for step in steps)
    if [counts[index] for index in (1, 2, 3)] != ATTEMPT_STEPS or set(counts) != {1, 2, 3}:
        raise ValueError("Recovered result attempt counts differ from trajectory")
    for attempt in history["0"]:
        if [step.get("done") for step in attempt] != [False] * (len(attempt) - 1) + [True]:
            raise ValueError("Native trajectory attempt terminal boundaries are inconsistent")


def compact_trace_requests(result):
    removed = []
    for step in result["steps"]:
        responses = step.get("raw_response_by_agent", {})
        if not isinstance(responses, dict):
            raise ValueError("raw_response_by_agent must be a mapping")
        for uid, trace in responses.items():
            if not isinstance(trace, dict):
                raise ValueError("Per-agent response trace must be a mapping")
            if "model_requests" in trace:
                value = trace.pop("model_requests")
                removed.append({"path": f"steps[{step['turn_index']}].raw_response_by_agent[{uid!r}].model_requests",
                                "field": "model_requests", "original_type": type(value).__name__,
                                "original_items": len(value) if isinstance(value, (list, dict)) else None})
    return removed


def expand_action_previews(result, replay):
    changed = []
    for step in result["steps"]:
        full_action = replay.extract_replay_action(step, 0)
        original = step.get("action_preview")
        if original != full_action:
            if not isinstance(original, str) or not isinstance(full_action, str):
                raise ValueError("Action preview and saved full action must be text")
            changed.append({"path": f"steps[{step['turn_index']}].action_preview",
                            "original_chars": len(original), "original_bytes": len(original.encode("utf-8")),
                            "original_sha256": hashlib.sha256(original.encode("utf-8")).hexdigest(),
                            "derived_chars": len(full_action), "derived_bytes": len(full_action.encode("utf-8")),
                            "derived_sha256": hashlib.sha256(full_action.encode("utf-8")).hexdigest()})
            step["action_preview"] = full_action
    return changed


def validate_candidate(results_path, trajectories_path, official):
    replay = official["run_replay"]
    selected = replay.select_replay_records(replay._jsonl_records(str(results_path)), {})
    if len(selected) != 1 or selected[0].get("status") != "ok" or selected[0].get("turns") != 71:
        raise ValueError("Official default status filter did not select one complete validated record")
    case = replay.replay_case_from_record(selected[0])
    agent = replay.ReplayAgent(selected[0])
    actions = []
    for _ in range(71):
        actions.append(agent.forward_with_trace({0: {"skip_infer": False}})[0][0]["action"])
    records = official["trajectory_io"].load_trajectory_records(str(trajectories_path))
    if len(records) != 1:
        raise ValueError("Official loader must read exactly one native trajectory")
    history = official["trajectory_io"].history_snapshot_from_record(records[0])
    if set(history) != {0} or [len(attempt) for attempt in history[0]] != ATTEMPT_STEPS:
        raise ValueError("Official trajectory loader did not retain all three complete attempts")
    if actions != [step.get("action") for attempt in history[0] for step in attempt]:
        raise ValueError("Official ReplayAgent and trajectory actions differ")
    return {"official_default_status_filter_selected": 1, "replay_agent_actions_consumed": len(actions),
            "trajectory_attempt_steps": [len(attempt) for attempt in history[0]], "case": case,
            "model_requests": 0, "environments_started": 0}


def prepare(args):
    export_dir = Path(args.export_dir).expanduser().resolve(strict=True)
    replay_path = Path(args.replay_validation).expanduser().resolve(strict=True)
    canvas_path = Path(args.canvas_validation).expanduser().resolve(strict=True)
    output_dir = Path(args.output_dir).expanduser().resolve()
    if output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {output_dir}")
    if output_dir.is_relative_to(export_dir) or export_dir.is_relative_to(output_dir):
        raise ValueError("Output directory must be separate from the immutable export")
    if any(path.is_relative_to(output_dir) for path in (replay_path, canvas_path)):
        raise ValueError("Output directory must not contain validation input reports")
    source_result = export_dir / (STEM + "_results.jsonl")
    source_trajectory = export_dir / (STEM + "_trajectories.jsonl")
    provenance_path = export_dir / "recovery_provenance.json"
    sources = [file_identity(path) for path in (source_result, source_trajectory, provenance_path)]
    provenance = read_object(provenance_path)
    expected = {item["path"]: item for item in provenance.get("artifacts", [])}
    for identity in sources[:2]:
        pinned = expected.get(identity["path"], {})
        if identity["sha256"] != pinned.get("sha256") or identity["bytes"] != pinned.get("bytes"):
            raise ValueError("Recovery export artifact SHA-256/size differs from recovery provenance")
    if provenance.get("logical_steps") != 71 or provenance.get("attempt_steps") != ATTEMPT_STEPS:
        raise ValueError("Recovery provenance does not describe all 71 actions")
    replay_report, canvas_report = read_object(replay_path), read_object(canvas_path)
    result, trajectory = read_object(source_result), read_object(source_trajectory)
    validate_reports(replay_report, canvas_report, sources[0]["sha256"], result)
    official = official_modules(getattr(args, "agentark_root", None))
    validate_source_records(result, trajectory, official["run_replay"])
    validation = {
        "source_result_sha256": sources[0]["sha256"],
        "source_trajectory_sha256": sources[1]["sha256"],
        "replay_validation": file_identity(replay_path), "canvas_validation": file_identity(canvas_path),
        "replayed_actions": 71, "attempt_steps": ATTEMPT_STEPS,
        "all_official_replay_fields_match": True, "all_canvas_and_canvas_raw_pixels_identical": True,
        "status_meaning": STATUS_MEANING, "derived_result_status": "ok",
        "source_run_finalized": False, "original_exit": None,
    }
    removed = compact_trace_requests(result)
    expanded = expand_action_previews(result, official["run_replay"])
    result["status"] = "ok"
    result["record_validation"] = validation
    trajectory["reconstruction"]["validation"] = validation
    output_dir.mkdir(parents=True, exist_ok=False)
    results_path, trajectories_path = output_dir / source_result.name, output_dir / source_trajectory.name
    official["run_api_agent"].JsonlWriter(str(results_path)).write(result)
    official["trajectory_io"].TrajectoryJsonlWriter(str(trajectories_path)).write(trajectory)
    del result, trajectory
    offline = validate_candidate(results_path, trajectories_path, official)
    # Recheck immutable inputs after serialization and all official loader checks.
    for path, identity in zip((source_result, source_trajectory, provenance_path), sources):
        if sha256_file(path) != identity["sha256"]:
            raise ValueError("Immutable export input changed while preparing the copy")
    for path, identity in ((replay_path, validation["replay_validation"]), (canvas_path, validation["canvas_validation"])):
        if sha256_file(path) != identity["sha256"]:
            raise ValueError("Validation input changed while preparing the copy")
    manifest = {
        "schema_version": 1, "generated_utc": datetime.now(timezone.utc).isoformat(),
        "kind": "validated_reconstructed_record_copy", "record_reconstruction": True,
        "source_run_finalized": False, "original_generator_finalized": False, "original_exit": None,
        "status_meaning": STATUS_MEANING, "sources": sources,
        "validation": validation, "offline_validation": offline,
        "compaction": {"only_removed_field": "steps[*].raw_response_by_agent[uid].model_requests",
                       "removed_field_count": len(removed), "removed_fields": removed,
                       "preserved": "All other source result fields, full actions/assistant text, raw_request_by_agent, step results, and the entire native trajectory remain intact; status, action_preview, and validation metadata are the declared changes."},
        "action_preview_alignment": {"changed_count": len(expanded), "changes": expanded,
                                     "meaning": "Display/alignment field expanded to the full saved action; action_extracted and trajectory actions are unchanged."},
        "artifacts": [file_identity(path) for path in (results_path, trajectories_path)],
        "preparation_tool_sha256": sha256_file(__file__),
        "official_source_sha256": {name: sha256_file(module.__file__) for name, module in official.items()},
        "models_called": 0, "environments_started": 0, "input_files_written": 0,
    }
    manifest_path = output_dir / "validated_record_manifest.json"
    with manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return manifest_path


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--export-dir", required=True)
    result.add_argument("--replay-validation", required=True)
    result.add_argument("--canvas-validation", required=True)
    result.add_argument("--output-dir", required=True, help="New directory; existing output is never overwritten")
    result.add_argument("--agentark-root", help="Optional existing AgentArk checkout containing src/agent_ark")
    return result


def main(argv=None):
    print(prepare(parser().parse_args(argv)))


if __name__ == "__main__":
    main()
