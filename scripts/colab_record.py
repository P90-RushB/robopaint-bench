"""Prepare, launch and inspect no-inference Colab replay or human sessions.

This is an onboarding adapter around AgentArk's existing installers, preparer,
evaluator, replay and viewer. It does not implement an evaluation loop.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from urllib.parse import unquote, urlsplit

import yaml

import prepare_run
import run_eval

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record_contract(case: str = "golden_gate", model: str = "sol") -> dict:
    """Take an already-public record's immutable identity from its own track."""
    if case not in ("golden_gate", "pelican"):
        raise ValueError("Unknown replay case.")
    release = json.loads((ROOT / f"benchmarks/results/{case}.json").read_text("utf-8"))
    entries = [item for item in release["models"] if item["id"] == model]
    if len(entries) != 1:
        raise ValueError("The public result release must identify exactly one selected model record.")
    entry = deepcopy(entries[0]["record"])
    parsed = urlsplit(entry["url"])
    match = re.fullmatch(r"/datasets/P90-RushB/AgentArk/resolve/([0-9a-f]{40})/(artifacts/records/.+\.jsonl)",
                         unquote(parsed.path))
    if (entry.get("publication_status") != "already_published" or parsed.scheme != "https"
            or parsed.netloc != "huggingface.co" or parsed.query or parsed.fragment or not match
            or type(entry.get("bytes")) is not int or entry["bytes"] <= 0
            or not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("sha256", "")))
            or (match is not None and f"/0107-RobotPainting/{case}/" not in "/" + match[2])):
        raise ValueError("Public record has an invalid immutable download contract.")
    entry.update(repo_id="P90-RushB/AgentArk", repo_type="dataset",
                 revision=match[1], filename=match[2], case=case, model=model)
    return entry


def verify_record(path: Path, contract: dict | None = None) -> dict:
    entry = contract or record_contract()
    if not path.is_file() or path.stat().st_size != entry["bytes"] or sha256(path) != entry["sha256"]:
        raise ValueError("Replay record differs from the selected public record's locked size/SHA-256.")
    return entry


def download_record(destination: Path, *, case: str = "golden_gate", model: str = "sol", downloader=None) -> dict:
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Record destination exists; choose a new path. No data is overwritten.")
    entry = record_contract(case, model)
    if downloader is None:
        from huggingface_hub import hf_hub_download
        downloader = hf_hub_download
    cached = Path(downloader(repo_id=entry["repo_id"], repo_type="dataset", revision=entry["revision"],
                             filename=entry["filename"]))
    verify_record(cached, entry)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with cached.open("rb") as source, destination.open("xb") as target:
        shutil.copyfileobj(source, target)
    verify_record(destination, entry)
    return {"record_path": str(destination.resolve()), "verified": True, "source": entry}


def prepare(args) -> Path:
    record = Path(args.record_path).expanduser().resolve(strict=True) if args.record_path else None
    source = verify_record(record, record_contract(args.case, args.model)) if args.mode == "replay" and record else None
    if args.mode == "replay" and source is None:
        raise ValueError("Replay preparation requires --record-path from download-record.")
    # Sol is only an offline template used by the existing preparer. It is
    # removed below; source-model selection never constructs an API agent.
    command = ["--case", args.case, "--model", "sol", "--runtime-platform", "linux",
               "--render-mode", args.render_mode, "--output-dir", args.run_dir,
               "--base-port", str(args.base_port)]
    for flag, value in (("--env-path", args.env_path), ("--mod-path", args.mod_path),
                        ("--task-store", args.task_store)):
        if value:
            command.extend([flag, value])
    path = prepare_run.prepare(prepare_run.parser().parse_args(command))
    cfg = prepare_run.read_yaml(path)
    if args.graphics_api != "default":
        arguments = cfg["env_cfg"].get("additional_args", [])
        arguments = [item for item in arguments if not str(item).startswith(("-force-glcore", "-force-vulkan", "-force-gles"))]
        cfg["env_cfg"]["additional_args"] = ["-force-" + args.graphics_api, *arguments]
    cfg["hooks"] = {
        "visualization": {"enabled": True, "host": "127.0.0.1", "port": args.viewer_port,
                          "open_browser": False, "event_buffer_size": 1000,
                          "text_max_chars": 16000, "max_images_per_observation": 4,
                          "keep_open_on_end": args.keep_viewer},
        "human_interaction": {"enabled": args.mode == "human", "name": "human-colab", "timeout_s": None},
    }
    if args.mode == "human":
        cfg["models"] = []  # AgentArk selects HumanInteractiveAgent before API model construction.
        cfg["eval"]["cases"][0]["case_id"] = args.case.replace("_", "-") + "-human-record-seed-107"
    else:
        cfg.pop("models", None)
        cfg.pop("eval", None)
        cfg["replay"] = {"records_path": str(record), "record_index": 0,
                         "use_record_max_attempts": True, "step_delay_s": args.step_delay,
                         "require_match": True, "stop_on_error": True,
                         "output_path": str(path.parent / "replay_results.jsonl"), "append": False}
    cfg["robopaint_record"] = {"mode": args.mode, "case": args.case, "source_model": args.model,
                              "model_inference": False,
                              "source_record": source, "graphics_api_request": args.graphics_api}
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    manifest_path = path.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8"))
    manifest.update(mode=args.mode, model_inference=False, eval_config_sha256=sha256(path),
                    model={"provider": "replay" if args.mode == "replay" else "human",
                           "source_record_model": args.model if args.mode == "replay" else None},
                    record_source=source, graphics_api_request=args.graphics_api,
                    validation_status="prepared_only_not_runtime_validated")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def launch(config: Path, *, record_video: bool = False, ffmpeg: str | None = None) -> None:
    cfg = prepare_run.read_yaml(config)
    mode = cfg.get("robopaint_record", {}).get("mode")
    if mode not in ("replay", "human") or cfg["robopaint_record"].get("model_inference") is not False:
        raise ValueError("Use a no-inference configuration created by colab_record.py prepare.")
    if (config.parent / "session_started.json").exists():
        raise FileExistsError("This session already started; prepare a fresh run to preserve its artifacts.")
    if any((config.parent / name).exists() for name in ("results.jsonl", "replay_results.jsonl")) or any(
            folder.is_dir() and any(folder.iterdir()) for folder in (config.parent / "paintings", config.parent / "videos")):
        raise FileExistsError("Run artifacts already exist; prepare a fresh run instead of overwriting them.")
    encoder = None
    if record_video:
        encoder_value = ffmpeg or os.environ.get("AGENTARK_FFMPEG") or shutil.which("ffmpeg")
        encoder = Path(encoder_value).expanduser() if encoder_value else None
        if encoder is None or not encoder.is_absolute() or not encoder.is_file():
            raise ValueError("Video recording requires an existing absolute FFmpeg executable path.")
    if mode == "human" and (cfg.get("models") != [] or not cfg.get("hooks", {}).get("human_interaction", {}).get("enabled")):
        raise ValueError("Human recording requires empty models and the human-interaction hook.")
    if mode == "replay":
        if cfg.get("models") or cfg.get("hooks", {}).get("human_interaction", {}).get("enabled"):
            raise ValueError("Record replay cannot contain an API model or human action producer.")
        identity = cfg["robopaint_record"]
        verify_record(Path(cfg["replay"]["records_path"]),
                      record_contract(identity.get("case", "golden_gate"), identity.get("source_model", "sol")))
    with (config.parent / "session_started.json").open("x", encoding="utf-8") as marker:
        json.dump({"started_utc": datetime.now(timezone.utc).isoformat(), "mode": mode,
                   "record_video": record_video, "model_inference": False}, marker)
    if record_video:
        os.environ.update(AGENTARK_TASK107_VIDEO_DIR=str(config.parent / "videos"), AGENTARK_FFMPEG=str(encoder))
    else:
        os.environ["AGENTARK_TASK107_VIDEO_DIR"] = ""
    if mode == "human":
        run_eval.main(["--config", str(config)])
        return
    for name in run_eval.TASK_PATH_OVERRIDES:
        os.environ[name] = ""
    run_eval.apply_render_profile(cfg)
    from agent_ark.ark_eval.run_replay import main, build_parser
    run_eval.apply_render_profile(cfg)
    main(build_parser().parse_args(["--config", str(config)]))


def inspect_run(directory: Path) -> dict:
    log = directory / "player.log"
    lines = log.read_text("utf-8", errors="replace").splitlines() if log.is_file() else []
    evidence = [line for line in lines if re.search(r"GfxDevice|Renderer:|Vendor:|Device:|Vulkan|OpenGL|NVIDIA|llvmpipe|softpipe", line, re.I)]
    videos = []
    for path in sorted((directory / "videos").glob("**/manifest.json")):
        data = json.loads(path.read_text("utf-8"))
        videos.append({key: data.get(key) for key in ("episode_guid", "frames", "complete", "truncated", "encoder_exit_code", "error")}
                      | {"manifest": str(path), "video_exists": (path.parent / "motion.mp4").is_file(), "decode_verified": False})
    return {"run_dir": str(directory), "renderer_log_exists": log.is_file(),
            "renderer_log_evidence": evidence[:50], "renderer_claim": "unclassified_actual_log_requires_review",
            "saved_canvases": [str(path) for path in sorted((directory / "paintings").glob("**/canvas.png"))],
            "recording_manifests": videos,
            "results_exists": (directory / "results.jsonl").is_file(),
            "replay_results_exists": (directory / "replay_results.jsonl").is_file(),
            "runtime_pass_claimed": False}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    download = commands.add_parser("download-record", help="Download and hash-check an already-public action record.")
    download.add_argument("--destination", required=True, type=Path)
    download.add_argument("--case", choices=("golden_gate", "pelican"), default="golden_gate")
    download.add_argument("--model", default="sol", help="Model ID in the selected track's public result manifest.")
    prep = commands.add_parser("prepare", help="Prepare only; no Unity, model, or viewer starts.")
    prep.add_argument("--mode", choices=("replay", "human"), default="replay")
    prep.add_argument("--case", choices=("golden_gate", "pelican"), default="golden_gate")
    prep.add_argument("--model", default="sol", help="Source-record model only; replay never calls this model.")
    prep.add_argument("--record-path")
    prep.add_argument("--run-dir", required=True, help="A new unique output directory.")
    prep.add_argument("--env-path", default=os.getenv("AGENTARK_ENV_PATH"))
    prep.add_argument("--mod-path", default=os.getenv("AGENTARK_MOD_PATH"))
    prep.add_argument("--task-store", default=os.getenv("AGENTARK_TASK_STORE_PATH"))
    prep.add_argument("--render-mode", choices=("existing-display", "xvfb-software"), default="xvfb-software")
    prep.add_argument("--graphics-api", choices=("default", "glcore33", "vulkan"), default="default",
                      help="Request an API; this does not prove GPU use or configure drivers.")
    prep.add_argument("--viewer-port", type=int, default=18181)
    prep.add_argument("--base-port", type=int, default=5005)
    prep.add_argument("--step-delay", type=float, default=0.1)
    prep.add_argument("--keep-viewer", action=argparse.BooleanOptionalAction, default=True)
    run = commands.add_parser("run", help="Launch an existing AgentArk replay or human session, never an API model.")
    run.add_argument("--config", required=True, type=Path)
    run.add_argument("--record-video", action="store_true", help="Enable the task's existing continuous motion recorder.")
    run.add_argument("--ffmpeg", help="Absolute existing encoder; otherwise AGENTARK_FFMPEG or PATH is used.")
    inspect = commands.add_parser("inspect", help="Report actual local artifacts; makes no runtime-success claim.")
    inspect.add_argument("--run-dir", required=True, type=Path)
    return result


def main():
    args = parser().parse_args()
    if args.command == "download-record":
        print(json.dumps(download_record(args.destination.expanduser().absolute(), case=args.case, model=args.model), indent=2))
    elif args.command == "prepare":
        path = prepare(args)
        print(json.dumps({"prepared_only": True, "config": str(path), "model_inference": False}, indent=2))
    elif args.command == "run":
        launch(args.config.expanduser().resolve(strict=True), record_video=args.record_video, ffmpeg=args.ffmpeg)
    else:
        print(json.dumps(inspect_run(args.run_dir.expanduser().resolve(strict=True)), indent=2))


if __name__ == "__main__":
    main()
