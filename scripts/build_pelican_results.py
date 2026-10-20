#!/usr/bin/env python3
"""Build allowlisted Pelican metadata and optional byte-identical PNG previews.

Inputs are explicit local evidence files. No inference, network requests, replay,
video export, or source modification occurs. Native reasoning and request bodies
are never loaded; published records are hashed without parsing their contents.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct

ROOT = Path(__file__).resolve().parents[1]
REVISION = "b16fb52e866ce6a33c52e287f04bfe4a77964453"
RELEASE_ID = "pelican-2026-10-20"
DATASET_PREFIX = "artifacts/records/0100-0199/0107-RobotPainting/pelican/"
TARGET = "Paint a pelican riding a bicycle."
MODEL_INFO = {
    "sol": ("GPT-6.1 Sol", "openai/gpt-6.1-sol", "openrouter", "max", [20, 14, 14]),
    "argon": ("Gemini 4 Argon", "google/gemini-4-argon", "openrouter", "high", [18, 11, 12]),
    "opus": ("Claude Opus 5.5", "anthropic/claude-opus-5.5", "openrouter", "high", [29, 9, 9]),
    "grok": ("Grok 4.7", "x-ai/grok-4.7", "openrouter", "xhigh", [58, 14, 15]),
    "wonder": ("Meta Muse Wonder", "meta/muse-wonder", "openrouter", "max", [49, 17, 16]),
    "deepseek": ("DeepSeek V4.1 Flash 1017", "deepseek/deepseek-v4.1-flash-1017", "openrouter", "max", [50, 15, 23]),
    "qwen": ("Qwen3.8-Max-Prime", "qwen/qwen3.8-max-prime", "openrouter", "xhigh", [32, 10, 10]),
    "kimi": ("Kimi K3", "moonshotai/kimi-k3", "openrouter", "max", [16, 9, 10]),
    "mimo": ("MiMo V2.6 Pro", "xiaomi/mimo-v2.6-pro", "openrouter", None, [21, 10, 6]),
    "doubao": ("Doubao Seed 2.1 Pro 260915", "doubao-seed-2-1-pro-260915", "volcengine", "high", [27, 9, 9]),
    "astra": ("GPT-6 Astra", "gpt-6-astra", "codex", "max", [19, 11, 11]),
}
BACKEND_LABELS = {"openrouter": "OpenRouter", "volcengine": "Volcengine Ark", "codex": "Codex SDK"}
PROTOCOL = {"max_attempts": 3, "max_steps_per_attempt": 96, "width": 960, "height": 720,
            "obs_mode": "decision", "time_scale": 1, "physics_frequency_hz": 480,
            "brush_mode": "fixed", "pigment_mode": "infinite"}
SESSION = {"learning_protocol": "in_context_learning", "session_structure": "one_continuous_agent_session",
           "round_count": 3, "experience_carries_across_rounds": True, "canvas_resets_each_round": True,
           "model_weight_updates": False, "round_index_field": "attempt",
           "context_management": "Experience carries across rounds through SimpleAgent's managed context, summaries, and archives. Model weights remain fixed."}


class EvidenceError(ValueError):
    """Evidence is incomplete, inconsistent, or unsuitable for publication."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_path(value: str) -> Path:
    if not isinstance(value, str) or not value:
        raise EvidenceError("Missing explicit source path")
    if os.name == "nt" and re.match(r"^/mnt/[a-z]/", value):
        value = value[5].upper() + ":/" + value[7:]
    elif os.name != "nt" and re.match(r"^[A-Za-z]:[/\\]", value):
        value = "/mnt/" + value[0].lower() + "/" + value[3:].replace("\\", "/")
    return Path(value)


def read_json(path: Path) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise EvidenceError("Duplicate JSON key")
            result[key] = value
        return result
    value = json.loads(path.read_text("utf-8"), object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise EvidenceError("Evidence must be a JSON object")
    return value


def portable(value: object) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            portable(key)
            portable(item)
    elif isinstance(value, list):
        for item in value:
            portable(item)
    elif isinstance(value, str):
        patterns = (r"(?<![A-Za-z])[A-Za-z]:[/\\]", r"^\\\\", r"/mnt/[a-z]/", r"/root/", r"/Users/", r"/home/", r"file://", r"data:image/", r"(?i)bearer\s+", r"sk-[a-zA-Z0-9]{16}")
        if any(re.search(pattern, value) for pattern in patterns):
            raise EvidenceError("Output contains a local path or private payload")


def receipt(path: Path) -> dict:
    return {"sha256": sha256(path), "bytes": path.stat().st_size}


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        head = stream.read(24)
    if len(head) != 24 or head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        raise EvidenceError("Canvas is not a PNG")
    return struct.unpack(">II", head[16:24])


def record_receipt(entry: dict, payload_root: Path, name: str, kind: str) -> dict:
    path = entry.get("path", "")
    if (entry.get("model_name") != name or entry.get("kind") != "record" or
            entry.get("record_kind") != {"record": "results", "trajectory": "trajectories"}[kind] or
            not path.startswith(DATASET_PREFIX) or ".." in Path(path).parts or
            not re.fullmatch(r"[A-Za-z0-9_./-]+\.jsonl", path)):
        raise EvidenceError("Invalid allowlisted dataset artifact mapping")
    actual = receipt(payload_root / path)
    if actual != {"sha256": entry.get("sha256"), "bytes": entry.get("size_bytes")}:
        raise EvidenceError("Published artifact SHA-256 or byte count mismatch")
    return {"url": f"https://huggingface.co/datasets/P90-RushB/AgentArk/resolve/{REVISION}/{path}",
            **actual, "publication_status": "already_published", "revision": REVISION}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def validate_video_receipt(value: dict, *, film: bool = False) -> None:
    require(re.fullmatch(r"[0-9a-f]{64}", value.get("video_sha256", "")) is not None and
            type(value.get("duration_s")) in (int, float) and value["duration_s"] > 0,
            "Invalid video hash or duration receipt")
    if film:
        require(type(value.get("video_bytes")) is int and value["video_bytes"] > 0, "Invalid film byte count")


def build_release(dataset_manifest: Path, production_models: Path, delivery_manifest: Path,
                  publication_status: Path, payload_root: Path | None = None) -> tuple[dict, list]:
    catalog, source, delivery, publication = map(read_json, (dataset_manifest, production_models, delivery_manifest, publication_status))
    payload_root = payload_root or dataset_manifest.parents[5]
    names = set(MODEL_INFO)
    require(catalog.get("case_id") == "pelican" and catalog.get("target_text") == TARGET and
            catalog.get("reference_image_attached") is False, "Unexpected dataset task target")
    require(catalog.get("repo_id") == "P90-RushB/AgentArk" and catalog.get("sources_modified") is False,
            "Unapproved dataset identity or changed sources")
    require(set(catalog.get("models", {})) == names and set(source) == names, "Expected exactly 11 curated models")
    require(delivery.get("status") == "complete" and delivery.get("models") == 11 and delivery.get("attempts") == 33 and
            delivery.get("retained_actions") == 603 and delivery.get("speed_in_simulated_time") == 4 and
            all(delivery.get(key) is True for key in ("all_full_decodes_pass", "all_steps_present", "all_subtitles_within_step_boundaries")),
            "Delivery is not the verified complete 4x collection")
    deliveries = {item["model"]: item for item in delivery.get("deliveries", [])}
    posts = {item["model"]: item for item in publication.get("items", [])}
    require(len(delivery.get("deliveries", [])) == 11 and set(deliveries) == names and
            len(publication.get("items", [])) == 11 and set(posts) == names and
            publication.get("all_11_published") is True, "Missing or duplicate completed film/publication mappings")
    files = catalog.get("files", [])
    require(len(files) == 22, "Expected 22 published record/trajectory files")
    public_models, copies, artifacts, video_models = [], [], [], {}
    for name, (label, model_id, backend, effort, steps) in MODEL_INFO.items():
        model, mapping, film, post = catalog["models"][name], source[name], deliveries[name], posts[name]
        require((model.get("model"), model.get("provider"), model.get("reasoning_effort")) == (model_id, backend, effort), "Unreviewed model identity or reasoning profile")
        require(model.get("protocol") == PROTOCOL and model.get("group_seed") == 107 and model.get("platform") == "linux" and
                model.get("env_version") == "1.0.5" and model.get("task_version") == "v1", "Changed benchmark protocol")
        require(model.get("attempt_action_counts") == steps == mapping.get("attempt_steps") == film.get("attempt_steps") and
                model.get("action_count") == sum(steps) and model.get("attempt_count") == 3, "Inconsistent attempt/action coverage")
        commit = "299737b6eeddfb50e1f8edc9194b0a15d47049f3" if name in ("sol", "argon") else "54ab7cb0adf6539419611b536811b9850e429520"
        require(model.get("agentark_commit") == commit, "Unexpected AgentArk version")
        simple = model.get("simple_agent_settings", {})
        require(simple.get("output_token_parameter") == "max_tokens" and simple.get("env_message_mode") == "delta" and
                simple.get("tool_choice") == ("auto" if name in ("opus", "wonder") else "required") and
                simple.get("context", {}).get("output_reserve_tokens") == 20480 and
                simple.get("context", {}).get("summary_output_tokens") == 32768,
                "Unreviewed SimpleAgent settings")
        require(film.get("full_decode_pass") is True and film.get("all_three_attempts_present") is True and
                film.get("all_steps_accounted_for") is True and film.get("speed_in_simulated_time") == 4,
                "Film is not fully verified")
        validate_video_receipt(film, film=True)
        url = post.get("url", "")
        bvid_match = re.fullmatch(r"https://www\.bilibili\.com/video/(BV[A-Za-z0-9]{10})/", url)
        require(post.get("review_status") == "published" and bvid_match is not None, "Unverified public video URL")
        video_models[name] = {"bvid": bvid_match.group(1), "url": url, "duration_seconds": film["duration_s"],
                              "source_sha256": film["video_sha256"], "source_bytes": film["video_bytes"]}
        file_receipts = {}
        for kind, field in (("record", "results_path"), ("trajectory", "trajectories_path")):
            entries = [item for item in files if item.get("model_name") == name and item.get("kind") == "record" and
                       item.get("record_kind") == {"record": "results", "trajectory": "trajectories"}[kind]]
            require(len(entries) == 1 and entries[0].get("path") == model.get(field), "Ambiguous published artifact mapping")
            file_receipts[kind] = record_receipt(entries[0], payload_root, name, kind)
            artifacts.append({"id": f"{name}/{kind}", **file_receipts[kind]})
        guids = model.get("source_episode_guids", [])
        require(len(guids) == 3 and len(set(guids)) == 3 and all(re.fullmatch(r"[0-9a-f]{32}", guid) for guid in guids), "Invalid source episode identities")
        media = mapping.get("media", [])
        require(len(media) == 3 and sorted(item.get("attempt", -1) for item in media) == [1, 2, 3], "Expected three unambiguous media mappings")
        attempts = []
        for item in sorted(media, key=lambda entry: entry["attempt"]):
            attempt = item["attempt"]
            episode = item.get("source_episode_guid", item.get("episode_guid"))
            require(episode == guids[attempt - 1] and item.get("steps") == steps[attempt - 1], "Media/record episode or steps disagree")
            canvas_path = source_path(item.get("source_canvas", item.get("canvas")))
            metadata_path = canvas_path.with_name("metadata.json")
            metadata, canvas = read_json(metadata_path), receipt(canvas_path)
            require(metadata.get("episode_guid") == episode and metadata.get("action_count") == steps[attempt - 1] and
                    metadata.get("physical_sha256") == canvas["sha256"], "Canvas metadata identity, steps, or SHA-256 mismatch")
            require(metadata.get("painting_goal", "").strip() == TARGET and metadata.get("reference_images") == [] and
                    metadata.get("reference_mode") == "text" and metadata.get("group_seed") == 107 and
                    metadata.get("physics_frequency_hz") == 480 and metadata.get("brush_mode") == "fixed" and
                    metadata.get("board_mode") == "fixed" and metadata.get("pigment_mode") == "infinite" and
                    metadata.get("submission_integrity") is True and metadata.get("terminal_status") == "submitted", "Canvas has changed task conditions or is not submitted")
            width, height = png_dimensions(canvas_path)
            require((width, height) == (1024, 725), "Expected an uncropped 1024 x 725 physical canvas")
            recorded_at = metadata.get("saved_utc", "")
            require(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", recorded_at) is not None, "Invalid recorded date")
            require(item.get("complete") is True and item.get("truncated") is False and item.get("encoder_exit_code") == 0 and
                    item.get("full_decode_pass") is True, "Episode video receipt is not complete")
            validate_video_receipt(item)
            if name not in ("doubao", "astra"):
                require(item.get("canvas_identical") is True and item.get("canvas_mae_0_255") == 0.0, "Physical replay canvas differs from the recorded source")
            relative = f"assets/media/pelican/{name}/attempt-{attempt:02d}.png"
            attempt_data = {"attempt": attempt, "steps": steps[attempt - 1], "episode_id": episode,
                "recorded_at": recorded_at, "canvas": {"path": relative, **canvas, "width": width, "height": height},
                "metadata": receipt(metadata_path), "video_url": None,
                "video": {"sha256": item["video_sha256"], "duration_s": item["duration_s"], "verified_full_decode": True,
                          "complete": True, "truncated": False, "encoder_exit_code": 0,
                          "scope": "Historical native recorder receipt; public model video combines all three rounds at 4x simulated speed."}}
            attempts.append(attempt_data)
            copies.append((canvas_path, relative.removeprefix("assets/media/")))
            artifacts.append({"id": f"{name}/attempt-{attempt:02d}/canvas", **attempt_data["canvas"]})
        history = model.get("history_coverage", {})
        saved_steps = history.get("saved_steps_per_attempt")
        require(history.get("all_actions_in_results") is True and isinstance(saved_steps, list) and len(saved_steps) == 3 and
                all(saved == min(total, 24) for saved, total in zip(saved_steps, steps)), "Unexpected trajectory coverage")
        full_history = saved_steps == steps
        require(history.get("trajectory_full_history") is full_history, "Trajectory completeness flag disagrees")
        settings = {"reasoning_effort": effort, "thinking": "enabled" if name in ("mimo", "doubao") else None,
                    "action_output_token_budget": 20480, "summary_output_token_budget": 32768,
                    "tool_choice": "auto" if name in ("opus", "wonder") else "required", "env_message_mode": "delta",
                    "context_profile": "Pinned SimpleAgent defaults", "output_token_cap_enforced": name != "astra"}
        caveats = []
        if name == "opus":
            require(model.get("settings_exceptions", {}).get("reasoning_fallback") == "max failed; user-authorized high continuation, full context restored" and
                    model.get("simple_agent_settings", {}).get("tool_choice") == "auto", "Unreviewed Opus fallback")
            caveats.append("Max reasoning failed; the authorized continuation used high reasoning and tool_choice=auto after full context restoration.")
        if name == "mimo":
            caps = [{"purpose": "action", "max_output_tokens": 20480, "requests": 25},
                    {"purpose": "action", "max_output_tokens": 65536, "requests": 2},
                    {"purpose": "summary", "max_output_tokens": 32768, "requests": 1}]
            require(model.get("thinking") == {"type": "enabled"} and model.get("settings_exceptions", {}).get("actual_provider_request_caps_latest_segment") == caps,
                    "Unreviewed MiMo output budget exception")
            settings["actual_provider_request_caps_latest_segment"] = caps
            caveats.append("Two truncated-action retries in the latest segment used a 65,536-token provider cap. Logical records retain the original caps; this is an output-budget exception. No 131,072-token request is claimed.")
        if name == "astra":
            caveats.append("Codex SDK subscription transport did not enforce the logical hard output-token cap. API dollar cost is unavailable.")
        if name == "wonder":
            caveats.append("The recorded SimpleAgent profile used tool_choice=auto.")
        if not full_history:
            caveats.append("The full action record is complete. The native trajectory retains only the last 24 steps of the first round; use the results record for full replay.")
        replay = ("Historical official Linux GPU replay covered all three rounds; the 27 re-recorded canvases in the nine-model group were pixel-identical to source canvases. All episode videos fully decoded."
                  if name not in ("doubao", "astra") else "All three native Linux GPU evaluation recordings fully decoded. No additional physical replay is claimed.")
        public_models.append({"id": name, "label": label, "model_id": model_id, "backend": backend, "backend_label": BACKEND_LABELS[backend],
            "effort": effort, "effort_label": "thinking enabled" if name == "mimo" else effort,
            "attempt_steps": steps, "total_environment_actions": sum(steps), "agentark_commit": commit,
            "comparison_group": {"opus": "reasoning-fallback", "mimo": "budget-supplement", "astra": "sdk-subscription"}.get(name, "http-20480"),
            "settings": settings, "caveats": caveats, "replay_verification": replay,
            "record": {**file_receipts["record"], "all_actions_complete": True},
            "trajectory": {**file_receipts["trajectory"], "full_history": full_history, "saved_steps_per_attempt": saved_steps},
            "token_usage": None, "api_cost_usd": None, "video_url": url, "attempts": attempts})
    results = {"schema": "robopaint.public-results.v1", "case_id": "pelican", "release_id": RELEASE_ID,
        "publication_status": "public_records_and_videos_local_canvas_preview",
        "harness": {"name": "AgentArk SimpleAgent", "shared_across_models": True,
            "shared_components": ["Agent implementation", "Task and action interface", "Environment attempt and action budget"],
            "model_access_backends": [{"id": key, "label": label} for key, label in BACKEND_LABELS.items()],
            "backend_role": "All backends supply model access inside the AgentArk SimpleAgent evaluation loop.",
            "configuration_scope": "Actual reasoning, budget exceptions, harness revisions and trajectory limits are reported per model."},
        "target": {"title": "A Pelican Riding a Bicycle", "mode": "text", "instruction": TARGET, "reference": None},
        "protocol": {"attempts": 3, "max_steps_per_attempt": 96, "group_seed": 107, "official_platform": "linux",
                     "environment_version": "1.0.5", "task_version": "task-v1", "physics_frequency_hz": 480,
                     "width": 960, "height": 720, "obs_mode": "decision", "time_scale": 1,
                     "brush": "fixed", "paper": "fixed", "pigment": "infinite", **SESSION},
        "quality": {"status": "unscored", "note": "No Pelican quality scores or author ordering have been supplied. Submission reward is a save/submission-integrity check, not an artistic-quality metric. The model list is a presentation order, not a ranking."},
        "model_count": 11, "attempt_count": 33, "action_count": 603, "models": public_models}
    ranking = {"schema": "robopaint.author-recommendation.v1", "case_id": "pelican", "status": "awaiting_owner",
               "attributed_to": None, "basis": None, "date": None, "tiers": [],
               "note": "The benchmark author has not supplied a Pelican ranking. Golden Gate recommendations do not apply to this task."}
    videos = {"schema": "robopaint.model-videos.v1", "case_id": "pelican", "playback_speed": 4, "speed_basis": "simulated_time",
              "captions": ["zh", "en"], "scope": "Each model video contains all three sequential ICL rounds. Model waits are removed. Explicit reading pauses are labeled; the brush-follow view is viewer-only and was not model input.", "models": video_models}
    manifest = {"schema": "robopaint.public-release-manifest.v1", "case_id": "pelican", "release_id": RELEASE_ID,
                "dataset_revision": REVISION, "builder": "scripts/build_pelican_results.py",
                "source_evidence": [{"role": role, **receipt(path)} for role, path in zip(
                    ("published_dataset_manifest", "production_episode_map", "film_delivery_manifest", "public_video_receipt"),
                    (dataset_manifest, production_models, delivery_manifest, publication_status))],
                "model_count": 11, "attempt_count": 33, "action_count": 603,
                "session_protocol": SESSION, "harness": results["harness"],
                "verification_scope": "Source canvas/metadata and exported record/trajectory bytes were hashed locally. Episodes, steps, text target and protocol were checked. Historical video decode/replay receipts were retained; no new inference, physical replay or video decode was performed by this builder.",
                "privacy": "Explicit allowlist only. No local source paths, raw payloads, request history, credentials, reasoning contents or private context stores.",
                "media_policy": "Byte-identical source canvas PNG copies are ignored local preview assets, published separately from Git. Raw records, trajectories, logs and videos are not copied into the code repository.",
                "artifacts": artifacts}
    outputs = {"pelican.json": results, "pelican-ranking.json": ranking, "pelican-videos.json": videos,
               "pelican-release-manifest.json": manifest}
    for value in outputs.values():
        portable(value)
    return outputs, copies


def write_release(dataset_manifest: Path, production_models: Path, delivery_manifest: Path,
                  publication_status: Path, output: Path, media_output: Path | None = None,
                  payload_root: Path | None = None) -> dict:
    outputs, copies = build_release(dataset_manifest, production_models, delivery_manifest, publication_status, payload_root)
    if media_output is not None:
        for source, relative in copies:
            destination = media_output / relative
            if destination.exists() and sha256(destination) != sha256(source):
                raise EvidenceError("Refusing to overwrite different existing preview media")
        for source, relative in copies:
            destination = media_output / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                shutil.copyfile(source, destination)
    output.mkdir(parents=True, exist_ok=True)
    for filename, value in outputs.items():
        temporary = output / (filename + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(output / filename)
    return outputs["pelican.json"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--production-models", type=Path, required=True)
    parser.add_argument("--delivery-manifest", type=Path, required=True)
    parser.add_argument("--publication-status", type=Path, required=True)
    parser.add_argument("--payload-root", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "benchmarks/results")
    parser.add_argument("--media-output", type=Path, help="Ignored assets/media root; adds pelican/<model>/attempt-XX.png")
    args = parser.parse_args()
    try:
        write_release(args.dataset_manifest, args.production_models, args.delivery_manifest, args.publication_status,
                      args.output, args.media_output, args.payload_root)
    except (EvidenceError, OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        parser.exit(1, f"Pelican evidence build failed: {error}\n")
    print("Verified 11 models, 33 canvases and 603 actions; no inference, replay, or network publication.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
