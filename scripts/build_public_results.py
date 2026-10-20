#!/usr/bin/env python3
"""Build a small, allowlisted result index from the private resource catalog.

No inference, network, video copying, or raw-record export takes place. The
catalog and source files stay local. Optional PNG copies are byte-identical and
belong in an ignored preview directory until publication is authorized.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import struct
from urllib.parse import parse_qsl, urlsplit


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VIDEO_LINKS = ROOT / "benchmarks/results/video-links.json"
RELEASE_ID = "golden-gate-2026-10-19-preview"
REFERENCE_SHA256 = "54c7a2385db7ab9df4e2be820dfd32ede7576fe66d62c69832784599c7b4feb5"
# These strings are curated public metadata, never copied from free-form audit
# text, catalog notes, model messages, HTTP payloads, or environment variables.
MODEL_INFO = {
    "sol": ("GPT-6.1 Sol", "openai/gpt-6.1-sol", "openrouter", "max"),
    "argon": ("Gemini 4 Argon", "google/gemini-4-argon", "openrouter", "high"),
    "opus": ("Claude Opus 5.5", "anthropic/claude-opus-5.5", "openrouter", "high"),
    "grok": ("Grok 4.7", "x-ai/grok-4.7", "openrouter", "xhigh"),
    "wonder": ("Meta Muse Wonder", "meta/muse-wonder", "openrouter", "max"),
    "deepseek": ("DeepSeek V4.1 Flash1017", "deepseek/deepseek-v4.1-flash-1017", "openrouter", "max"),
    "qwen": ("Qwen3.8 Max Prime", "qwen/qwen3.8-max-prime", "openrouter", "xhigh"),
    "kimi": ("Kimi K3", "moonshotai/kimi-k3", "openrouter", "max"),
    "mimo": ("MiMo V2.6 Pro", "xiaomi/mimo-v2.6-pro", "openrouter", None),
    "astra": ("GPT-6 Astra", "gpt-6-astra", "codex", "ultra"),
    "doubao": ("Doubao Seed2.1 Pro260915", "doubao-seed-2-1-pro-260915", "volcengine", "high"),
}
BACKEND_LABELS = {"openrouter": "OpenRouter", "volcengine": "Volcengine Ark", "codex": "Codex SDK"}
CAVEATS = {
    "sol": [],
    "argon": ["The full action record was reconstructed from retained originals and continuation segments."],
    "opus": ["Mixed profile: attempt 1 actions 1–4 used max reasoning and a 65,536-token output budget; the remaining 39 actions used high reasoning and 20,480 tokens. Later attempts retained the earlier context."],
    "grok": ["Completed continuation: 96 / 96 / 47 environment steps. Tool-budget failures consumed rejected environment steps; these were harness-generated feedback, not model-selected painting motions. Budgets were unchanged.", "Some original request usage is unknown; complete billing totals are unavailable."],
    "wonder": ["The same evaluation continued after harness repairs. Some historical request usage is unknown."],
    "deepseek": ["The same evaluation continued after harness repairs."],
    "qwen": ["The same evaluation continued with the 20,480-token action budget. Two historical requests have unknown usage."],
    "kimi": [],
    "mimo": ["Budget supplement: one earlier action used 20,480 tokens; continuation used a 65,536-token output budget with thinking enabled. This is not a standard 20,480-token completion."],
    "astra": ["SimpleAgent uses the Codex SDK for model access with ultra reasoning. The declared 20,480-token budget was not enforced as an API output cap; it is not equivalent to an HTTP max-token limit. API dollar cost is unavailable."],
    "doubao": ["Continuation restored the same evaluation. Two HTTP requests have unknown usage; known token totals are incomplete.", "Attempt 2 voluntarily submitted after six contact-protection motion results; its seven steps are a completed attempt."],
}
REPLAY_SCOPES = {
    "sol": "Historical official physical replay: 56 actions (attempt 1 plus one action); first-attempt canvas and raw PNG matched. No new full three-attempt replay is claimed.",
    "argon": "Historical official physical replay: all 71 actions; six final PNGs matched and three videos decoded. Not rerun for this preview.",
    "opus": "Offline record verification: all 43 actions. Historical official physical replay: 18 actions (attempt 1 plus one action).",
    "grok": "Offline ReplayAgent reader matched all 239 saved actions. All three final videos decoded. No new full official physical replay was performed.",
    "wonder": "Historical physical verification: attempt 1 plus one action (45 actions). No full three-attempt physical rerun was performed.",
    "deepseek": "Historical physical verification: attempt 1 plus one action (60 actions). No full three-attempt physical rerun was performed.",
    "qwen": "All 154 saved actions matched in ReplayAgent reading; 115 physical reconstruction actions and 116 observation gates were checked. This was not a new full official physical replay.",
    "kimi": "Historical official physical replay: 12 actions (attempt 1 plus one action); not all 62 actions.",
    "mimo": "Historical official physical replay: 20 actions (attempt 1 plus one action); not all 31 actions.",
    "astra": "Historical Linux official physical replay: 40 actions (attempt 1 plus one action), pixel-identical canvas and raw PNG. Three final videos fully decoded; no full three-attempt replay is claimed.",
    "doubao": "Historical Linux official physical replay: 54 actions (attempt 1 plus one action), pixel-identical canvas and raw PNG. Three final videos fully decoded; no full three-attempt replay is claimed.",
}


class EvidenceError(ValueError):
    """Incomplete, inconsistent, or unpublishable source evidence."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_path(value: str) -> Path:
    """Translate only the conventional Windows/WSL mount spelling."""
    if not isinstance(value, str) or not value:
        raise EvidenceError("Source path is missing")
    if os.name == "nt" and re.match(r"^/mnt/[a-z]/", value):
        value = value[5].upper() + ":/" + value[7:]
    elif os.name != "nt" and re.match(r"^[A-Za-z]:[/\\]", value):
        value = "/mnt/" + value[0].lower() + "/" + value[3:].replace("\\", "/")
    return Path(value)


def file_entry(media: dict, kind: str) -> dict:
    """Normalize the catalog's three explicit media shapes."""
    filenames = {"canvas": "canvas.png", "metadata": "metadata.json", "video": "motion.mp4", "video_manifest": "manifest.json"}
    files = media.get("files")
    if isinstance(files, list):
        matches = [item for item in files if Path(item["path"]).name == filenames[kind]]
        if len(matches) != 1:
            raise EvidenceError(f"Expected exactly one {kind} mapping")
        return matches[0]
    if isinstance(files, dict):
        return files.get(filenames[kind], {})
    return media.get(kind, {})


def locate_entry(entry: dict) -> tuple[Path, str | None, int | None]:
    candidates = [entry.get("copy", {}), entry, entry.get("source", {}), entry.get("original", {})]
    for candidate in candidates:
        for key in ("windows_path", "copied_path", "path"):
            value = candidate.get(key)
            if value and source_path(value).is_file():
                expected_hash = entry.get("receipt_sha256") or candidate.get("sha256") or entry.get("sha256")
                expected_size = candidate.get("bytes", entry.get("bytes"))
                return source_path(value), expected_hash, expected_size
    raise EvidenceError("Mapped evidence file is unavailable; source files were not changed")


def verify_file(entry: dict, require_hash: bool = True) -> tuple[Path, dict]:
    path, expected_hash, expected_size = locate_entry(entry)
    actual_hash, actual_size = sha256(path), path.stat().st_size
    if require_hash and not re.fullmatch(r"[0-9a-f]{64}", expected_hash or ""):
        raise EvidenceError("An expected evidence SHA-256 is required")
    if expected_hash and actual_hash != expected_hash:
        raise EvidenceError("Evidence SHA-256 mismatch")
    if expected_size is not None and actual_size != expected_size:
        raise EvidenceError("Evidence byte count mismatch")
    return path, {"sha256": actual_hash, "bytes": actual_size}


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        head = stream.read(24)
    if len(head) != 24 or head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        raise EvidenceError("Canvas must be a PNG with an IHDR")
    return struct.unpack(">II", head[16:24])


def metadata_entry(media: dict, canvas: Path, model_id: str) -> dict:
    entry = file_entry(media, "metadata")
    if entry:
        return entry
    # Astra/Doubao's catalog points into a content-addressed collection. Resolve
    # only its explicit episode mapping, never a latest-file or filename glob.
    collection = canvas.parents[4] / "collection.json"
    if not collection.is_file():
        raise EvidenceError("Canvas metadata mapping is missing")
    content = json.loads(collection.read_text("utf-8"))
    episodes = content["models"][model_id]["media"]["episodes"]
    matches = [ep for ep in episodes if ep.get("episode_guid") == media.get("episode_guid")]
    if len(matches) != 1:
        raise EvidenceError("Episode metadata mapping is ambiguous")
    return matches[0]["final_painting"]["metadata_file"]


def published_record_url(model: dict) -> str | None:
    value = model.get("published_record_url")
    if value is None:
        return None
    parsed = urlsplit(value)
    revision = model.get("published_record_revision", "")
    if (parsed.scheme != "https" or parsed.netloc != "huggingface.co" or
            parsed.query or parsed.fragment or not re.fullmatch(r"[0-9a-f]{40}", revision) or
            not parsed.path.startswith(f"/datasets/P90-RushB/AgentArk/resolve/{revision}/artifacts/records/")):
        raise EvidenceError("Public record URL is outside the approved immutable dataset location")
    return value


def public_video_url(value: object) -> str:
    """Accept an owner-supplied public HTTPS link without fetching its content."""
    if not isinstance(value, str) or not value or len(value) > 2048 or any(char.isspace() or ord(char) < 32 for char in value):
        raise EvidenceError("Video links must be bounded HTTPS URLs without whitespace")
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port
    except ValueError as error:
        raise EvidenceError("Video link has an invalid URL authority") from error
    if (parsed.scheme != "https" or not host or parsed.username is not None or
            parsed.password is not None or port not in (None, 443) or "\\" in value):
        raise EvidenceError("Video links require public HTTPS URLs without credentials or custom ports")
    host = host.rstrip(".").lower()
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if ("." not in host or len(host) > 253 or host.rsplit(".", 1)[-1].isdigit() or
                host.endswith((".localhost", ".local", ".internal", ".test", ".invalid")) or
                not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in host.split("."))):
            raise EvidenceError("Video links require a public hostname")
    else:
        if not address.is_global:
            raise EvidenceError("Video links cannot point to local or private addresses")
    secret_names = {"key", "apikey", "accesskey", "accesstoken", "token", "auth", "authorization", "password", "secret", "signature", "xamzcredential", "xamzsignature", "xgoogcredential", "xgoogsignature"}
    for field in (parsed.query, parsed.fragment):
        for name, _ in parse_qsl(field, keep_blank_values=True):
            if re.sub(r"[^a-z0-9]", "", name.lower()) in secret_names:
                raise EvidenceError("Video links must not contain credential or signed-access parameters")
    assert_portable_public_data(value)
    return value


def load_video_links(path: Path) -> dict[str, dict[str, str]]:
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise EvidenceError("Duplicate key in video-link mapping")
            result[key] = value
        return result
    content = json.loads(path.read_text("utf-8"), object_pairs_hook=unique_keys)
    if (not isinstance(content, dict) or set(content) != {"schema", "case_id", "models"} or
            content.get("schema") != "robopaint.video-links.v1" or content.get("case_id") != "golden_gate" or
            not isinstance(content.get("models"), dict)):
        raise EvidenceError("Video links require the golden_gate robopaint.video-links.v1 mapping")
    validated = {}
    for name, attempts in content["models"].items():
        if name not in MODEL_INFO or not isinstance(attempts, dict) or any(key not in ("1", "2", "3") for key in attempts):
            raise EvidenceError("Video links contain an unknown model or attempt")
        validated[name] = {attempt: public_video_url(url) for attempt, url in attempts.items()}
    return validated


def assert_portable_public_data(value: object) -> None:
    """Final guard against local paths and embedded private payloads."""
    if isinstance(value, dict):
        for key, item in value.items():
            assert_portable_public_data(key)
            assert_portable_public_data(item)
    elif isinstance(value, list):
        for item in value:
            assert_portable_public_data(item)
    elif isinstance(value, str):
        patterns = (r"(?<![A-Za-z])[A-Za-z]:[/\\]", r"^\\\\", r"/mnt/[a-z]/", r"/root/", r"/Users/", r"/home/", r"file://", r"data:image/", r"(?i)bearer\s+", r"sk-[a-zA-Z0-9]{16}")
        if any(re.search(pattern, value) for pattern in patterns):
            raise EvidenceError("Public result data contains a local path or private payload")


def build_results(catalog_path: Path, video_links: Path | None = None) -> tuple[dict, dict, list[tuple[Path, str]]]:
    video_links = DEFAULT_VIDEO_LINKS if video_links is None else video_links
    curated_videos = load_video_links(video_links)
    catalog = json.loads(catalog_path.read_text("utf-8"))
    models = catalog.get("models", [])
    names = [model.get("name") for model in models]
    if len(names) != 11 or len(set(names)) != 11 or set(names) != set(MODEL_INFO):
        raise EvidenceError("This release requires exactly the 11 curated models")
    if catalog.get("completed_three_attempt_models") != 11 or catalog.get("partial_models"):
        raise EvidenceError("This release requires 11 completed three-attempt evaluations")
    public_models, artifacts, copies = [], [], []
    for model in models:
        name = model["name"]
        label, model_id, backend, effort = MODEL_INFO[name]
        if (model.get("model_id"), model.get("backend"), model.get("effort")) != (model_id, backend, effort):
            raise EvidenceError(f"Unreviewed model identity or profile for {name}")
        steps = model.get("attempt_steps")
        if (not isinstance(steps, list) or len(steps) != 3 or
                any(type(step) is not int or not 1 <= step <= 96 for step in steps) or
                sum(steps) != model.get("total_environment_actions") or model.get("completed_attempts") != 3):
            raise EvidenceError(f"Invalid attempt/step coverage for {name}")
        media = model.get("media", [])
        if len(media) != 3 or sorted(item.get("attempt", -1) for item in media) != [1, 2, 3]:
            raise EvidenceError(f"Expected exactly three unambiguous media mappings for {name}")
        attempts = []
        for item in sorted(media, key=lambda m: m["attempt"]):
            attempt = item["attempt"]
            step_count = steps[attempt - 1]
            if item.get("steps", item.get("wrapper_environment_steps", step_count)) != step_count:
                raise EvidenceError("Catalog attempt steps disagree")
            canvas, canvas_info = verify_file(file_entry(item, "canvas"))
            width, height = png_dimensions(canvas)
            if (width, height) != (1024, 725):
                raise EvidenceError("Expected a 1024 × 725 rectified final canvas")
            meta_path, meta_info = verify_file(metadata_entry(item, canvas, name))
            meta = json.loads(meta_path.read_text("utf-8"))
            episode_id = meta.get("episode_guid")
            if not re.fullmatch(r"[0-9a-f]{32}", episode_id or ""):
                raise EvidenceError("Missing episode identity")
            if item.get("episode_guid", episode_id) != episode_id:
                raise EvidenceError("Canvas episode identity disagrees with its catalog mapping")
            if meta.get("action_count") != step_count or meta.get("physical_sha256") != canvas_info["sha256"]:
                raise EvidenceError("Canvas metadata does not match the final action count or PNG")
            if meta.get("reference_images", [{}])[0].get("sha256") != REFERENCE_SHA256:
                raise EvidenceError("Canvas metadata has an unexpected target image")
            saved_at = meta.get("saved_utc")
            if not isinstance(saved_at, str) or not re.fullmatch(r"2026-10-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", saved_at):
                raise EvidenceError("Missing verified canvas save date")
            video_entry = file_entry(item, "video")
            _, video_hash, video_size = locate_entry(video_entry)
            if not re.fullmatch(r"[0-9a-f]{64}", video_hash or "") or type(video_size) is not int:
                raise EvidenceError("Video provenance hash/size is missing")
            video_verified = item.get("video_valid", item.get("video_fully_decoded"))
            if video_verified is False or item.get("partial", False):
                raise EvidenceError("Final video is marked incomplete")
            # Older Sol/Argon catalog entries supply a recorder manifest rather
            # than a decode flag. Keep that distinction explicit.
            video_duration = None
            if video_verified is None:
                manifest_path, _ = verify_file(file_entry(item, "video_manifest"))
                video_manifest = json.loads(manifest_path.read_text("utf-8"))
                if (video_manifest.get("complete") is not True or video_manifest.get("truncated") is not False or
                        video_manifest.get("encoder_exit_code") != 0 or video_manifest.get("episode_guid") != episode_id):
                    raise EvidenceError("Historical recorder manifest is not complete for this episode")
                video_duration = video_manifest.get("video_seconds")
            relative_path = f"assets/media/golden_gate/{name}/attempt-{attempt:02d}.png"
            attempt_data = {
                "attempt": attempt, "steps": step_count, "episode_id": episode_id,
                "recorded_at": saved_at,
                "canvas": {"path": relative_path, **canvas_info, "width": width, "height": height},
                "metadata": meta_info,
                "video_url": curated_videos.get(name, {}).get(str(attempt)),
                "video": {"sha256": video_hash, "bytes": video_size, "duration_s": video_duration,
                          "verified_full_decode": video_verified,
                          "verification": "Historical collection receipt; video bytes are not rehashed or copied by this builder." if video_verified else "Historical recorder manifest confirms completed encoding; the catalog does not supply a full-decode flag."},
            }
            attempts.append(attempt_data)
            copies.append((canvas, relative_path.removeprefix("assets/media/")))
            artifacts.append({"id": f"{name}/attempt-{attempt:02d}/canvas", **attempt_data["canvas"], "publication_status": "pending_approval"})
            artifacts.append({"id": f"{name}/attempt-{attempt:02d}/metadata", **meta_info, "publication_status": "local_only"})
            artifacts.append({"id": f"{name}/attempt-{attempt:02d}/video", "sha256": video_hash, "bytes": video_size,
                              "url": attempt_data["video_url"], "publication_status": "linked_public_video" if attempt_data["video_url"] else "pending_video_host"})
        record_path = source_path(model["recommended_record"])
        if not record_path.is_file():
            raise EvidenceError("Recommended replay record is unavailable")
        record = {"url": published_record_url(model), "sha256": sha256(record_path), "bytes": record_path.stat().st_size}
        record["publication_status"] = "already_published" if record["url"] else "local_only"
        artifacts.append({"id": f"{name}/record", **record})
        group = {"opus": "mixed-profile", "mimo": "budget-supplement", "astra": "sdk-subscription"}.get(name, "http-20480")
        public_models.append({
            "id": name, "label": label, "model_id": model_id, "backend": backend,
            "backend_label": BACKEND_LABELS[backend],
            "effort": effort, "effort_label": {"opus": "max → high", "mimo": "thinking enabled"}.get(name, effort),
            "attempt_steps": steps, "total_environment_actions": sum(steps),
            "comparison_group": group, "caveats": CAVEATS[name], "replay_verification": REPLAY_SCOPES[name],
            "record": record, "attempts": attempts,
        })
    result = {
        "schema": "robopaint.public-results.v1", "case_id": "golden_gate", "release_id": RELEASE_ID,
        "publication_status": "local_preview_pending_media_approval",
        "harness": {
            "name": "AgentArk SimpleAgent", "shared_across_models": True,
            "shared_components": ["Agent implementation", "Task and action interface", "Environment attempt and action budget"],
            "model_access_backends": [{"id": key, "label": label} for key, label in BACKEND_LABELS.items()],
            "backend_role": "These backends supply model access inside the same AgentArk SimpleAgent evaluation loop. The Codex SDK supplies model access for Astra.",
            "configuration_scope": "Actual reasoning effort, output budgets, transport limitations and continuation conditions are reported per model.",
        },
        "target": {"title": "Golden Gate Bridge", "mode": "reference_image", "instruction": "Reproduce the provided reference image as closely as possible.",
                   "reference": {"path": "assets/media/reference.png", "sha256": REFERENCE_SHA256,
                                 "width": 1280, "height": 800, "author": "Frank Schulenburg", "license": "CC BY-SA 4.0",
                                 "source_url": "https://commons.wikimedia.org/wiki/File:Golden_Gate_Bridge_as_seen_from_Battery_East.jpg",
                                 "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
                                 "modification": "Full image proportionally resized to 1280 × 800; no crop."}},
        "protocol": {"attempts": 3, "max_steps_per_attempt": 96, "group_seed": 107, "official_platform": "linux",
                     "environment_version": "1.0.5", "task_version": "task-v1", "brush": "fixed", "paper": "fixed", "pigment": "infinite",
                     "learning_protocol": "in_context_learning", "session_structure": "one_continuous_agent_session",
                     "round_count": 3, "experience_carries_across_rounds": True, "canvas_resets_each_round": True,
                     "model_weight_updates": False, "round_index_field": "attempt",
                     "context_management": "Experience carries across rounds through SimpleAgent's managed context and archives; context compression can summarize earlier interactions. Three rounds belong to one continuing agent session."},
        "quality": {"status": "unscored", "note": "All models share AgentArk SimpleAgent and the task conditions. All three final canvases are retained in attempt order. The author's personal ranking is stored separately; no numerical artistic-quality scores are assigned. Submission reward checks the save/submission process. Actual reasoning settings and model-access details accompany each model."},
        "model_count": 11, "attempt_count": 33, "models": public_models,
    }
    manifest = {
        "schema": "robopaint.public-release-manifest.v1", "release_id": RELEASE_ID,
        "publication_status": "local_preview_pending_media_approval",
        "harness": result["harness"],
        "session_protocol": {key: result["protocol"][key] for key in (
            "learning_protocol", "session_structure", "round_count", "experience_carries_across_rounds",
            "canvas_resets_each_round", "model_weight_updates", "round_index_field", "context_management")},
        "source_catalog_sha256": sha256(catalog_path), "builder": "scripts/build_public_results.py",
        "video_links_sha256": sha256(video_links),
        "video_link_policy": "Owner-curated model/attempt associations. Remote videos are not downloaded or hash-verified; recording hashes identify the retained originals, not re-encoded copies on video hosts.",
        "verification_scope": "Canvas, metadata, and recommended record bytes were hashed locally. Canvas identity, dimensions, action counts, reference hash, and explicit attempt associations were checked. Video hashes and decode states are retained historical receipts; no new video decode or physical replay is claimed.",
        "privacy": "Explicit allowlist only. No local source paths, raw records, native reasoning, API prompts, HTTP payloads, or credentials are included.",
        "media_policy": "PNG copies are local preview assets. This manifest does not authorize publication of new evaluation media or records.",
        "artifacts": artifacts,
    }
    assert_portable_public_data(result)
    assert_portable_public_data(manifest)
    return result, manifest, copies


def write_release(catalog_path: Path, output_dir: Path, media_output: Path | None = None,
                  reference_image: Path | None = None, video_links: Path | None = None) -> dict:
    result, manifest, copies = build_results(catalog_path, video_links)
    if reference_image is not None:
        if sha256(reference_image) != REFERENCE_SHA256 or png_dimensions(reference_image) != (1280, 800):
            raise EvidenceError("Reference PNG does not match the benchmark target")
        copies.append((reference_image, "reference.png"))
    # Complete all validation before writing anything, and preserve existing
    # preview files if their bytes differ from this release.
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
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, value in (("golden_gate.json", result), ("release-manifest.json", manifest)):
        temporary = output_dir / (filename + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(output_dir / filename)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True, help="Explicit local model_catalog.json")
    parser.add_argument("--output", type=Path, default=ROOT / "benchmarks/results")
    parser.add_argument("--media-output", type=Path, help="Optional ignored preview PNG destination (e.g. site/assets/media)")
    parser.add_argument("--reference-image", type=Path, help="Optional exact reference PNG to copy to preview media")
    parser.add_argument("--video-links", type=Path, default=DEFAULT_VIDEO_LINKS,
                        help="Curated model/attempt public-video links; defaults to benchmarks/results/video-links.json")
    args = parser.parse_args()
    try:
        result = write_release(args.catalog, args.output, args.media_output, args.reference_image, args.video_links)
    except (EvidenceError, OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        parser.exit(1, f"Public evidence build failed: {error}\n")
    print(f"Verified {result['model_count']} models and {result['attempt_count']} final canvases; no inference or remote publication performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
