"""Prepare an isolated AgentArk evaluation config; never launch Unity or a model."""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import re
import subprocess
import unicodedata
import uuid

import yaml

ROOT = Path(__file__).resolve().parents[1]
CASES = ("golden_gate", "pelican")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a YAML mapping: {path}")
    return value


def substitute(value, variables: dict[str, str]):
    """Resolve only deployment variables; retain AgentArk's ${task_params.*}."""
    if isinstance(value, str):
        for key, replacement in variables.items():
            value = value.replace("${" + key + "}", replacement)
        return value
    if isinstance(value, list):
        return [substitute(item, variables) for item in value]
    if isinstance(value, dict):
        return {key: substitute(item, variables) for key, item in value.items()}
    return value


def agentark_identity(lock: dict, allow_mismatch: bool) -> dict:
    import agent_ark
    from agent_ark.agent.simple_agent.runtime import SimpleRuntimeConfig
    from agent_ark.agent.simple_agent.tools import ToolLimits

    package = Path(agent_ark.__file__).resolve().parent
    commit, dirty = None, None
    for parent in package.parents:
        if (parent / ".git").exists():
            relative = package.relative_to(parent).as_posix()
            # An installed .venv can sit inside an unrelated Git checkout.
            # Only a tracked AgentArk source package belongs to this repo.
            try:
                subprocess.check_output(
                    ["git", "-C", str(parent), "ls-files", "--error-unmatch", "--", relative + "/__init__.py"],
                    text=True, stderr=subprocess.DEVNULL,
                )
            except subprocess.CalledProcessError as error:
                if error.returncode != 1:
                    raise
                continue
            commit = subprocess.check_output(
                ["git", "-C", str(parent), "rev-parse", "HEAD"], text=True
            ).strip()
            dirty = bool(subprocess.check_output(
                ["git", "-C", str(parent), "status", "--porcelain", "--", relative], text=True
            ).strip())
            break
    if commit is None:
        try:
            direct_url = metadata.distribution("agent-ark").read_text("direct_url.json")
        except metadata.PackageNotFoundError:
            direct_url = None
        provenance = json.loads(direct_url) if direct_url else {}
        if not provenance.get("dir_info", {}).get("editable"):
            commit = provenance.get("vcs_info", {}).get("commit_id")
    context = asdict(SimpleRuntimeConfig())
    limits = asdict(ToolLimits(max_records=512))
    matches = (commit == lock["agentark"]["commit"] and dirty is not True
               and context == lock["simple_agent_context_defaults"]
               and limits == lock["simple_agent_tool_limits_defaults"])
    if not matches and not allow_mismatch:
        raise ValueError(
            "Installed AgentArk does not match benchmarks/versions.json "
            f"(commit={commit}, source_dirty={dirty}). Install the pinned source, "
            "or use --allow-version-mismatch for an explicitly nonstandard run."
        )
    return {"commit": commit, "source_dirty": dirty, "matches_version_lock": matches,
            "context_defaults": context, "tool_limits_defaults": limits}


def validate_goal(data: bytes) -> None:
    text = data.decode("utf-8-sig", errors="strict")
    if (not text.strip() or len(data) > 32768
            or len(text.encode("utf-16-le")) // 2 > 8192
            or any(unicodedata.category(c) == "Cc" and c not in "\t\r\n" for c in text)):
        raise ValueError("Goal must be nonempty UTF-8, <=32 KiB / 8192 UTF-16 units, without control characters.")


def validate_reference(path: Path) -> tuple[int, int]:
    from PIL import Image

    size = path.stat().st_size
    if not 16 <= size <= 16 * 1024 * 1024:
        raise ValueError("Each reference must be at most 16 MiB.")
    with Image.open(path) as image:
        expected_format = "PNG" if path.suffix.lower() == ".png" else "JPEG"
        if image.format != expected_format or getattr(image, "n_frames", 1) != 1:
            raise ValueError("Reference format must match its PNG/JPG/JPEG extension and be static.")
        pixels = image.width * image.height
        if max(image.size) > 8192 or pixels > 16 * 1024 * 1024:
            raise ValueError("Task107 references require each side <=8192 and at most 16*1024*1024 pixels.")
        image.verify()
    return size, pixels


def tree_manifest(directory: Path) -> list[dict]:
    return [{"path": path.relative_to(directory).as_posix(), "bytes": path.stat().st_size,
             "sha256": sha256(path)} for path in sorted(directory.rglob("*")) if path.is_file()]


def check_task_files(lock: dict, platform: str, task: Path, allow_mismatch: bool) -> bool:
    entry = lock["task"].get("runtime_file_manifests", {}).get(platform)
    if entry is None:
        return False
    expected = json.loads((ROOT / "benchmarks" / entry["filename"]).read_text("utf-8"))
    mismatches = []
    for item in expected["files"]:
        path = task / item["path"]
        if (not path.is_file() or path.stat().st_size != item["bytes"]
                or sha256(path) != item["sha256"]):
            mismatches.append(item["path"])
    if mismatches and not allow_mismatch:
        raise ValueError("Installed task differs from the locked runtime: " + ", ".join(mismatches))
    return not mismatches


def offline_contract(config_path: Path, base_path: Path, task_path: Path) -> tuple[dict, list[str]]:
    # These are AgentArk's read-only loader and pure merge functions. No ArkEnv,
    # model runtime, sandbox preparation or Unity process is constructed here.
    from agent_ark.ark_eval.run_api_agent import load_eval_config
    from agent_ark.ark_env.attempt_initial_images import load_attempt_initial_images
    from agent_ark.ark_env.direct_env import EnvInfoManager

    cfg = load_eval_config(str(config_path))
    env = EnvInfoManager._overlay_env_with_task_config(read_yaml(base_path), read_yaml(task_path))
    env = EnvInfoManager._merge_python_only_task_config(env, read_yaml(task_path))
    env = EnvInfoManager._apply_env_config_overrides(env, cfg["env_cfg"]["env_config_overrides"])
    records = load_attempt_initial_images(env, cfg["env_cfg"]["mod_path"])
    try:
        hashes = [record["sha256"] for record in records]
    finally:
        for record in records:
            record["image"].close()
    return env, hashes


def prepare(args: argparse.Namespace) -> Path:
    if args.render_mode == "xvfb-software" and args.runtime_platform != "linux":
        raise ValueError("xvfb-software rendering is Linux-only.")
    lock = json.loads((ROOT / "benchmarks/versions.json").read_text(encoding="utf-8"))
    identity = agentark_identity(lock, args.allow_version_mismatch)
    # AgentArk's import may have loaded the operator's .env after argparse.
    env_path = args.env_path or os.getenv("AGENTARK_ENV_PATH")
    mod_path = args.mod_path or os.getenv("AGENTARK_MOD_PATH")
    if not env_path or not mod_path:
        raise ValueError("Set AGENTARK_ENV_PATH and AGENTARK_MOD_PATH, or pass --env-path and --mod-path.")
    executable = Path(env_path).expanduser().resolve(strict=True)
    mods = Path(mod_path).expanduser().resolve(strict=True)
    if not executable.is_file() or not mods.is_dir():
        raise ValueError("env_path must be a Player executable; mod_path must be a Mods directory.")
    # The official sandbox clones the Player layout; its Mods template must be
    # inside that layout. A separate task store is supported independently.
    if not mods.is_relative_to(executable.parent):
        raise ValueError("The Mods template must be inside the Player directory; use --task-store for external tasks.")
    store_value = args.task_store or os.getenv("AGENTARK_TASK_STORE_PATH")
    store = Path(store_value).expanduser().resolve(strict=True) if store_value else mods / "all_tasks"
    task = store / "RobotPainting"
    base_path, task_path = mods / "config.yaml.bak", task / "cfg/task_config.yaml"
    if not base_path.is_file() or not task_path.is_file() or not (task / "dll").is_dir():
        raise ValueError("Install env 1.0.5 with immutable config.yaml.bak and the RobotPainting runtime mod.")
    from agent_ark.ark_env.direct_env import EnvInfoManager
    active = mods / "config.yaml"
    active_config = read_yaml(active) if active.exists() else json.loads((mods / "config.json").read_text("utf-8"))
    if not EnvInfoManager._uses_task_store(active_config):
        raise ValueError("The Player template is in prefab mode; use a packaged task-store Mods template.")
    if (len(list(task.glob("*.json"))) != 1 or not any(task.glob("*.bundle"))
            or not any((task / "dll").glob("*.dll"))):
        raise ValueError("RobotPainting runtime mod needs one Addressables catalog, a bundle and its DLL.")
    task_matches = check_task_files(lock, args.runtime_platform, task, args.allow_version_mismatch)
    case_root = ROOT / "benchmarks" / args.case
    template_path = case_root / "eval.yaml"
    config = read_yaml(template_path)
    models = [item for item in config["models"] if item["name"] == args.model]
    if len(models) != 1:
        raise ValueError(f"Choose one model name from {', '.join(item['name'] for item in config['models'])}.")
    config["models"] = deepcopy(models)
    custom = args.goal_file is not None or args.reference_image is not None or args.text_only
    goal_source = Path(args.goal_file).expanduser().resolve(strict=True) if args.goal_file else case_root / "painting_goal.txt"
    goal_bytes = goal_source.read_bytes()
    validate_goal(goal_bytes)
    goal_hash = hashlib.sha256(goal_bytes).hexdigest()
    if not custom and goal_hash != lock["goals"][args.case]["sha256"]:
        raise ValueError("The official goal differs from versions.json; use --goal-file for a custom drawing.")
    params = config["env_cfg"]["env_config_overrides"]["task_params"]
    if args.text_only:
        references = []
    elif args.reference_image is not None:
        references = [Path(path).expanduser().resolve(strict=True) for path in args.reference_image]
    else:
        references = [task / "References" / name for name in params["reference_filenames"]]
    if len(references) > 16:
        raise ValueError("Task107 supports at most 16 reference images.")
    names = [path.name for path in references]
    if len(set(name.casefold() for name in names)) != len(names):
        raise ValueError("Reference images must have distinct basenames.")
    total_bytes = total_pixels = 0
    for path in references:
        if (not re.fullmatch(r"[A-Za-z0-9_.-]{1,160}", path.name)
                or path.suffix.lower() not in (".png", ".jpg", ".jpeg")):
            raise ValueError("Use safe PNG/JPG/JPEG reference basenames (letters, numbers, dot, dash, underscore).")
        if not custom and sha256(path) != lock["reference_images"][path.name]["sha256"]:
            raise ValueError(f"Official reference hash mismatch: {path.name}")
        image_bytes, pixels = validate_reference(path)
        total_bytes += image_bytes
        total_pixels += pixels
    if total_bytes > 64 * 1024 * 1024 or total_pixels > 128_000_000:
        raise ValueError("Task107 references exceed the 64 MiB / 128 million total pixel limit.")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = (Path(args.output_dir).expanduser().resolve() if args.output_dir else
              ROOT / "runs" / args.case / f"{stamp}-{args.model}-{uuid.uuid4().hex[:8]}")
    if output.is_relative_to(executable.parent):
        raise ValueError("The run directory must be outside the Player template directory.")
    if output.is_relative_to(ROOT) and not output.is_relative_to(ROOT / "runs"):
        raise ValueError("Inside this checkout, put generated runs under runs/; an external output directory is also allowed.")
    variables = {"AGENTARK_ENV_PATH": str(executable), "AGENTARK_MOD_PATH": str(mods),
                 "AGENTARK_TASK_STORE_PATH": str(store), "ROBOTPAINTING_RUN_DIR": str(output)}
    config = substitute(config, variables)
    env_cfg = config["env_cfg"]
    env_cfg.setdefault("additional_args", []).extend(["-logFile", str(output / "player.log")])
    env_cfg["base_port"], env_cfg["auto_port_scan"] = args.base_port, True
    env_cfg["runtime_sandbox"]["runtime_platform"] = args.runtime_platform
    # Runtime preserves display flags from the active Mods config before task
    # overlay. Explicitly select this run's display policy over those flags.
    env_cfg["env_config_overrides"].update(virtual_display=False, virtual_display_force=False)
    if args.render_mode == "xvfb-software":
        # Use AgentArk's existing display manager; never edit the immutable
        # Player baseline, create a second runner, or launch Xvfb at prepare time.
        env_cfg["env_config_overrides"].update(
            virtual_display=True, virtual_display_force=True,
            virtual_display_width=1920, virtual_display_height=1080,
            virtual_display_render_env={"LIBGL_ALWAYS_SOFTWARE": "1", "GALLIUM_DRIVER": "llvmpipe",
                                        "GALLIUM_NUM_THREADS": "2", "LP_NUM_THREADS": "2"})
        env_cfg["additional_args"] = ["-force-glcore33", *env_cfg.get("additional_args", [])]
    params = env_cfg["env_config_overrides"]["task_params"]
    params.update(reference_mode="image" if references else "text", reference_filenames=names)
    wrapper = env_cfg["env_config_overrides"].setdefault("env_wrapper_cfg", {})
    wrapper["attempt_initial_images"] = ([str(output / "inputs") + "/${task_params.reference_filenames}"]
                                         if references else [])
    if custom:
        config["eval"]["cases"][0]["case_id"] = "custom-" + config["eval"]["cases"][0]["case_id"]
    config["eval"]["output_path"] = str(output / "results.jsonl")
    config["eval"]["trajectory_save"]["output_path"] = str(output / "trajectories.jsonl")
    config["models"][0]["simple_agent"]["tools"]["workspace_parent"] = str(output / "workspaces")
    # No existing run can be overwritten, including its input copies or records.
    output.mkdir(parents=True, exist_ok=False)
    inputs = output / "inputs"
    inputs.mkdir()
    (inputs / "painting_goal.txt").write_bytes(goal_bytes)
    for path in references:
        (inputs / path.name).write_bytes(path.read_bytes())
    if not custom and references:
        (inputs / "attribution.json").write_text(
            json.dumps(lock["reference_images"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    config_path = output / "eval.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8")
    effective, image_hashes = offline_contract(config_path, base_path, task_path)
    protocol = {"max_attempts": effective["max_attempts"], "max_steps_per_attempt": effective["max_steps_per_attempt"],
                "width": effective["width"], "height": effective["height"], "obs_mode": effective["obs_mode"],
                "time_scale": effective["engine_para"]["time_scale"],
                "physics_frequency_hz": effective["task_params"]["physics_frequency_hz"],
                "brush_mode": effective["task_params"]["brush_mode"], "pigment_mode": effective["task_params"]["pigment_mode"]}
    manifest = {"schema_version": 1, "created_utc": stamp, "preparation_only": True,
                "case": args.case, "custom_target": custom,
                "standard_harness": identity["matches_version_lock"],
                "task_matches_version_lock": task_matches,
                "runtime_platform": args.runtime_platform, "agentark": identity,
                "rendering": {"requested_mode": args.render_mode, "runtime_verified": False,
                              "benchmark_gpu_rendering": "not_applicable_preview" if args.render_mode == "xvfb-software" else "unverified"},
                "declared_versions": lock, "protocol": protocol,
                "model": config["models"][0], "goal_sha256": goal_hash,
                "reference_sha256": image_hashes, "template_sha256": sha256(template_path),
                "eval_config_sha256": sha256(config_path), "base_config_sha256": sha256(base_path),
                "player_executable_sha256": sha256(executable), "task_files": tree_manifest(task)}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "effective_task.preview.yaml").write_text(
        yaml.safe_dump(effective, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return config_path


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--case", choices=CASES, required=True)
    result.add_argument("--model", required=True, help="One models[].name from the case YAML; see docs/quickstart.md.")
    result.add_argument("--env-path", default=os.getenv("AGENTARK_ENV_PATH"))
    result.add_argument("--mod-path", default=os.getenv("AGENTARK_MOD_PATH"))
    result.add_argument("--task-store", default=os.getenv("AGENTARK_TASK_STORE_PATH"))
    result.add_argument("--output-dir", help="A new directory; defaults to a unique runs/<case>/ directory.")
    result.add_argument("--base-port", type=int, default=5005)
    result.add_argument("--runtime-platform", choices=("linux", "windows"), default="linux")
    result.add_argument("--render-mode", choices=("existing-display", "xvfb-software"), default="existing-display",
                        help="Use a configured display, or Linux Xvfb software preview (not the benchmark GPU profile).")
    result.add_argument("--goal-file", help="Custom UTF-8 painting instructions; marks the target as custom.")
    images = result.add_mutually_exclusive_group()
    images.add_argument("--reference-image", action="append", help="Custom image; repeat for multiple ordered images.")
    images.add_argument("--text-only", action="store_true", help="Provide only the goal text; keep both workspace cameras.")
    result.add_argument("--allow-version-mismatch", action="store_true", help="Prepare a nonstandard harness run.")
    return result


def main() -> None:
    try:
        path = prepare(parser().parse_args())
    except (OSError, ValueError, ImportError, metadata.PackageNotFoundError, subprocess.SubprocessError) as error:
        raise SystemExit(f"Preparation failed: {error}") from error
    print(f"Prepared only; Unity and the model have not been started.\nConfig: {path}")
    quoted = "'" + str(path).replace("'", "'\"'\"'") + "'" if os.name != "nt" else '"' + str(path) + '"'
    launcher = ROOT / "scripts/run_eval.py"
    launcher_quoted = "'" + str(launcher).replace("'", "'\"'\"'") + "'" if os.name != "nt" else '"' + str(launcher) + '"'
    print(f"Run separately with: python {launcher_quoted} --config {quoted}")


if __name__ == "__main__":
    main()
