"""Download the locked Player and Task107 runtime into a new installation directory.

This optional installer uses Hugging Face's normal cache/authentication and never
starts Unity, a model, or creates a Python environment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import ntpath
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import stat
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXECUTABLES = {"linux": "AgentArk.x86_64", "windows": "AgentArk.exe"}


def windows_long_path(path: str) -> str:
    """Use Windows extended absolute paths for cache and installation file I/O."""
    absolute = ntpath.abspath(ntpath.expanduser(path))
    if absolute.startswith("\\\\?\\"):
        return absolute
    if absolute.startswith("\\\\"):
        return "\\\\?\\UNC\\" + absolute[2:]
    return "\\\\?\\" + absolute


def filesystem_path(path: str | Path) -> Path:
    return Path(windows_long_path(str(path)) if os.name == "nt" else path)


def display_path(path: Path) -> Path:
    """Keep the internal long-path prefix out of printed deployment variables."""
    value = str(path)
    if os.name == "nt":
        if value[:8].upper() == "\\\\?\\UNC\\":
            value = "\\\\" + value[8:]
        elif value.startswith("\\\\?\\"):
            value = value[4:]
    return Path(value)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with filesystem_path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_parts(name: str) -> tuple[str, ...]:
    """Use the same unambiguous, portable path interpretation on both platforms."""
    parts = tuple(name.removesuffix("/").split("/"))
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10))}
    if (not name or "\\" in name or PurePosixPath(name).is_absolute()
            or any(not part or part in (".", "..") or ":" in part
                   or part.endswith((".", " "))
                   or part.split(".")[0].upper() in reserved
                   or any(ord(char) < 32 for char in part) for part in parts)):
        raise ValueError(f"Unsafe archive/file path: {name!r}")
    return parts


def download_contract(lock: dict, platform: str) -> tuple[dict, dict, dict]:
    if not isinstance(lock, dict):
        raise ValueError("versions.json must contain an object.")
    downloads = lock.get("runtime_downloads", {})
    if (not isinstance(downloads, dict) or downloads.get("repo_type") != "dataset"
            or not isinstance(downloads.get("repo_id"), str)
            or not re.fullmatch(r"[\w.-]+/[\w.-]+", downloads["repo_id"])
            or not re.fullmatch(r"[0-9a-fA-F]{40}", str(downloads.get("revision", "")))):
        raise ValueError("runtime_downloads needs a dataset repo_id and an immutable 40-digit commit revision.")
    artifacts = []
    for kind in ("envs", "tasks"):
        platforms = downloads.get(kind)
        entry = platforms.get(platform) if isinstance(platforms, dict) else None
        if (not isinstance(entry, dict) or not isinstance(entry.get("path"), str)
                or not entry["path"].endswith(".zip")
                or type(entry.get("bytes")) is not int or entry["bytes"] <= 0
                or not re.fullmatch(r"[0-9a-fA-F]{64}", str(entry.get("sha256", "")))):
            raise ValueError(f"Missing or invalid locked {kind}/{platform} ZIP, bytes or SHA-256.")
        safe_parts(entry["path"])
        artifacts.append(entry)
    return downloads, *artifacts


def checked_download(downloads: dict, entry: dict, cache_dir: str | None, downloader) -> Path:
    path = filesystem_path(downloader(repo_id=downloads["repo_id"], repo_type=downloads["repo_type"],
                                     revision=downloads["revision"], filename=entry["path"],
                                     cache_dir=cache_dir))
    if (not path.is_file() or path.stat().st_size != entry["bytes"]
            or sha256(path) != entry["sha256"].lower()):
        raise ValueError(f"Downloaded ZIP does not match locked bytes/SHA-256: {entry['path']}")
    return path


def extract_zip(archive: Path, destination: Path) -> None:
    """Validate every entry before extracting, without extractall or link support."""
    destination = filesystem_path(destination)
    with zipfile.ZipFile(filesystem_path(archive)) as source:
        entries = []
        seen = {}
        for info in source.infolist():
            parts = safe_parts(info.orig_filename)
            key = "/".join(parts).casefold()
            mode = info.external_attr >> 16
            file_type = stat.S_IFMT(mode)
            if (file_type not in (0, stat.S_IFREG, stat.S_IFDIR)
                    or info.external_attr & 0x400):  # Windows reparse-point attribute.
                raise ValueError(f"Archive links/special files are not supported: {info.filename}")
            if key in seen:
                raise ValueError(f"Duplicate/ambiguous archive path: {info.filename}")
            seen[key] = info.is_dir()
            entries.append((info, parts, mode))
        for key in seen:
            parents = key.split("/")[:-1]
            for index in range(1, len(parents) + 1):
                parent = "/".join(parents[:index])
                if parent in seen and not seen[parent]:
                    raise ValueError(f"Archive file is also used as a directory: {parent}")
        destination.mkdir()
        for info, parts, mode in entries:
            output = destination.joinpath(*parts)
            if info.is_dir():
                output.mkdir(parents=True, exist_ok=True)
            else:
                output.parent.mkdir(parents=True, exist_ok=True)
                with source.open(info) as incoming, output.open("xb") as outgoing:
                    shutil.copyfileobj(incoming, outgoing, length=1024 * 1024)
                # Retain executable bits only, never setuid/setgid or world write.
                output.chmod(0o755 if mode & 0o111 else 0o644)


def player_root(extracted: Path, platform: str) -> Path:
    extracted = filesystem_path(extracted)
    candidates = [path.parent for path in extracted.rglob(EXECUTABLES[platform])
                  if path.is_file() and (path.parent / "AgentArk_Data/Resources/Mods").is_dir()]
    if len(candidates) != 1:
        raise ValueError("Environment ZIP must contain exactly one Player with AgentArk_Data/Resources/Mods.")
    root = candidates[0]
    mods = root / "AgentArk_Data/Resources/Mods"
    if not (mods / "config.yaml.bak").is_file() or not any(
            (mods / name).is_file() for name in ("config.yaml", "config.json")):
        raise ValueError("Environment ZIP needs its original config.yaml.bak and active Mods configuration.")
    return root


def task_root(extracted: Path) -> Path:
    # Published packages are flat; also accept one RobotPainting wrapper.
    extracted = filesystem_path(extracted)
    candidates = [path for path in (extracted, extracted / "RobotPainting")
                  if (path / "cfg/task_config.yaml").is_file()]
    if len(candidates) != 1:
        raise ValueError("Task ZIP needs a flat root or one RobotPainting/ wrapper containing cfg/task_config.yaml.")
    root = candidates[0]
    if (len(list(root.glob("*.json"))) != 1 or not any(root.glob("*.bundle"))
            or not any((root / "dll").glob("*.dll"))
            or not (root / "References/GoldenGateBridge_reference.png").is_file()):
        raise ValueError("Task ZIP needs its catalog, Addressables bundle, DLL and Golden Gate reference.")
    return root


def install(args: argparse.Namespace, *, downloader=None) -> dict[str, Path]:
    requested = filesystem_path(Path(args.destination).expanduser())
    # Check before resolve(), so even a dangling destination symlink is refused.
    if requested.exists() or requested.is_symlink():
        raise FileExistsError("Destination already exists; choose a new directory. Existing installations/runs are never overwritten.")
    destination = filesystem_path(requested.resolve())
    lock = json.loads(filesystem_path(ROOT / "benchmarks/versions.json").read_text(encoding="utf-8"))
    downloads, env_entry, task_entry = download_contract(lock, args.platform)
    cache_dir = args.cache_dir
    if downloader is None:
        try:
            from huggingface_hub import constants, hf_hub_download
        except ImportError as error:
            raise ImportError("Optional installer dependency missing: python -m pip install huggingface_hub") from error
        downloader = hf_hub_download
        if os.name == "nt" and cache_dir is None:
            # Let HF resolve HF_HUB_CACHE/HF_HOME and its normal default first.
            cache_dir = constants.HF_HUB_CACHE
    if os.name == "nt" and cache_dir is not None:
        cache_dir = windows_long_path(cache_dir)
    env_zip = checked_download(downloads, env_entry, cache_dir, downloader)
    task_zip = checked_download(downloads, task_entry, cache_dir, downloader)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{destination.name}.install-", dir=destination.parent) as temporary:
        staging = filesystem_path(temporary)
        extract_zip(env_zip, staging / "environment")
        extract_zip(task_zip, staging / "task")
        player = player_root(staging / "environment", args.platform)
        task = task_root(staging / "task")
        installed_task = player / "AgentArk_Data/Resources/Mods/all_tasks/RobotPainting"
        shutil.copytree(task, installed_task)  # Refuse a pre-existing bundled task.
        if args.platform == "linux":
            for name in (EXECUTABLES["linux"], "UnityCrashHandler64"):
                path = player / name
                if path.is_file():
                    path.chmod(0o755)
        # Exclusive mkdir protects an installation that appeared during download.
        # All validation is complete before creating the final directory.
        destination.mkdir(exist_ok=False)
        for child in player.iterdir():
            child.rename(destination / child.name)
    destination = display_path(destination)
    mods = destination / "AgentArk_Data/Resources/Mods"
    return {"AGENTARK_ENV_PATH": destination / EXECUTABLES[args.platform],
            "AGENTARK_MOD_PATH": mods, "AGENTARK_TASK_STORE_PATH": mods / "all_tasks"}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--platform", required=True, choices=tuple(EXECUTABLES))
    result.add_argument("--destination", required=True, help="A new, nonexistent installation directory.")
    result.add_argument("--cache-dir", help="Optional Hugging Face cache directory; normal HF auth/cache defaults apply.")
    return result


def main() -> None:
    try:
        paths = install(parser().parse_args())
    except (OSError, ValueError, ImportError, zipfile.BadZipFile, RuntimeError) as error:
        raise SystemExit(f"Installation failed: {error}") from error
    print("Runtime installed. Unity and the model have not been started.\nSet these in your current terminal:")
    for name, path in paths.items():
        if os.name == "nt":
            quoted = "'" + str(path).replace("'", "''") + "'"
            print(f"$env:{name} = {quoted}")
        else:
            print(f"export {name}={shlex.quote(str(path))}")


if __name__ == "__main__":
    main()
