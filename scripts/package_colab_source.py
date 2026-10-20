"""Package or safely unpack the minimal, no-inference Colab source closure.

The source archive contains no runtime, records, media, logs or credentials.
An independently supplied SHA-256 is required before trusting an uploaded ZIP;
the internal manifest checks consistency, not the identity of its publisher.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "robopaint.colab-source.v1"
MANIFEST_NAME = "SOURCE_MANIFEST.json"
ALLOWED_FILES = (
    "scripts/colab_record.py",
    "scripts/colab_graphics.py",
    "scripts/install_runtime.py",
    "scripts/prepare_run.py",
    "scripts/run_eval.py",
    "scripts/package_colab_source.py",
    "benchmarks/versions.json",
    "benchmarks/task107_linux.task-v1.files.json",
    "benchmarks/golden_gate/eval.yaml",
    "benchmarks/golden_gate/painting_goal.txt",
    "benchmarks/results/golden_gate.json",
    "benchmarks/pelican/eval.yaml",
    "benchmarks/pelican/painting_goal.txt",
    "benchmarks/results/pelican.json",
)
MAX_ARCHIVE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 1024 * 1024
MAX_FILE_BYTES = 512 * 1024
MAX_MANIFEST_BYTES = 16 * 1024


class BundleError(ValueError):
    """The archive does not satisfy the fixed source-bundle contract."""


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def safe_name(value: str) -> str:
    if (not isinstance(value, str) or not value or "\\" in value or ":" in value or
            PurePosixPath(value).is_absolute() or any(ord(char) < 32 for char in value) or
            any(part in ("", ".", "..") for part in value.split("/"))):
        raise BundleError("Archive names must be canonical relative POSIX paths")
    return value


def reject_link(path: Path) -> None:
    if path.is_symlink():
        raise BundleError("Source and destination paths must not contain links")
    if path.exists() and getattr(path.lstat(), "st_file_attributes", 0) & 0x400:
        raise BundleError("Source and destination paths must not contain reparse points")


def check_existing_parents(path: Path) -> None:
    for part in (path, *path.parents):
        reject_link(part)


def source_file(root: Path, relative: str) -> bytes:
    path = root.joinpath(*safe_name(relative).split("/"))
    check_existing_parents(path)
    if not path.exists() or not stat.S_ISREG(path.lstat().st_mode):
        raise BundleError("A required source file is missing or is not a regular file")
    with path.open("rb") as stream:
        payload = stream.read(MAX_FILE_BYTES + 1)
    if not 0 < len(payload) <= MAX_FILE_BYTES:
        raise BundleError("A source file is empty or exceeds the size limit")
    return payload


def new_destination(path: Path) -> Path:
    path = path.expanduser().absolute()
    check_existing_parents(path)
    if path.exists() or path.is_symlink():
        raise FileExistsError("Destination exists; select a new path. Existing files are preserved.")
    return path


def pack(source_root: Path, destination: Path) -> dict:
    destination = new_destination(destination)
    source_root = source_root.expanduser().absolute()
    check_existing_parents(source_root)
    if not source_root.is_dir():
        raise BundleError("Source root must be an existing directory")
    payloads = {name: source_file(source_root, name) for name in sorted(ALLOWED_FILES)}
    total = sum(map(len, payloads.values()))
    if total > MAX_TOTAL_BYTES:
        raise BundleError("Source payload exceeds the total size limit")
    manifest = {"schema": SCHEMA, "files": [
        {"path": name, "bytes": len(payload), "sha256": digest(payload)}
        for name, payload in payloads.items()
    ]}
    payloads[MANIFEST_NAME] = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    if len(payloads[MANIFEST_NAME]) > MAX_MANIFEST_BYTES:
        raise BundleError("Source manifest exceeds the size limit")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, payload in sorted(payloads.items()):
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, payload)
    data = buffer.getvalue()
    if len(data) > MAX_ARCHIVE_BYTES:
        raise BundleError("Source archive exceeds the size limit")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as stream:
        stream.write(data)
    return {"schema": "robopaint.colab-source-package.v1", "source_schema": SCHEMA,
            "files": len(ALLOWED_FILES), "source_bytes": total,
            "archive_bytes": len(data), "archive_sha256": digest(data),
            "publication_performed": False}


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BundleError("Duplicate key in source manifest")
        result[key] = value
    return result


def verify_archive(archive_path: Path, expected_sha256: str) -> tuple[dict, dict[str, bytes]]:
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise BundleError("An independently supplied 64-digit archive SHA-256 is required")
    archive_path = archive_path.expanduser().absolute()
    check_existing_parents(archive_path)
    if not archive_path.is_file() or not stat.S_ISREG(archive_path.lstat().st_mode):
        raise BundleError("Source archive must be a regular file")
    with archive_path.open("rb") as stream:
        data = stream.read(MAX_ARCHIVE_BYTES + 1)
    if len(data) > MAX_ARCHIVE_BYTES:
        raise BundleError("Source archive exceeds the size limit")
    if digest(data) != expected_sha256.lower():
        raise BundleError("Uploaded source archive SHA-256 mismatch")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            names, folded = set(), set()
            allowed = {*ALLOWED_FILES, MANIFEST_NAME}
            for entry in entries:
                name = safe_name(entry.orig_filename)
                if entry.filename != name or name not in allowed:
                    raise BundleError("Unknown source archive member")
                if name in names or name.casefold() in folded:
                    raise BundleError("Duplicate or case-ambiguous source archive member")
                names.add(name)
                folded.add(name.casefold())
                mode = entry.external_attr >> 16
                if (entry.is_dir() or stat.S_IFMT(mode) not in (0, stat.S_IFREG) or
                        entry.external_attr & 0x400 or entry.flag_bits & 1 or
                        entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                    raise BundleError("Source archive members must be unencrypted regular files")
                limit = MAX_MANIFEST_BYTES if name == MANIFEST_NAME else MAX_FILE_BYTES
                if not 0 < entry.file_size <= limit:
                    raise BundleError("Source archive member exceeds its size limit")
            if names != allowed:
                raise BundleError("Source archive is missing required files")
            manifest = json.loads(archive.read(MANIFEST_NAME).decode("utf-8"), object_pairs_hook=unique_keys)
            if (not isinstance(manifest, dict) or set(manifest) != {"schema", "files"} or
                    manifest.get("schema") != SCHEMA or not isinstance(manifest.get("files"), list)):
                raise BundleError("Source manifest schema is invalid")
            expected = {}
            for item in manifest["files"]:
                if (not isinstance(item, dict) or set(item) != {"path", "bytes", "sha256"} or
                        item.get("path") not in ALLOWED_FILES or item["path"] in expected or
                        type(item.get("bytes")) is not int or not 0 < item["bytes"] <= MAX_FILE_BYTES or
                        not isinstance(item.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])):
                    raise BundleError("Source manifest entry is invalid or duplicated")
                expected[item["path"]] = item
            if set(expected) != set(ALLOWED_FILES):
                raise BundleError("Source manifest is missing required files")
            if sum(item["bytes"] for item in expected.values()) > MAX_TOTAL_BYTES:
                raise BundleError("Source payload exceeds the total size limit")
            payloads = {}
            for name, item in expected.items():
                if archive.getinfo(name).file_size != item["bytes"]:
                    raise BundleError("Source member size differs from its manifest")
                payload = archive.read(name)
                if len(payload) != item["bytes"] or digest(payload) != item["sha256"]:
                    raise BundleError("Source member SHA-256 differs from its manifest")
                payloads[name] = payload
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, UnicodeError, json.JSONDecodeError) as error:
        raise BundleError("Invalid source ZIP or manifest encoding") from error
    return manifest, payloads


def unpack(archive: Path, destination: Path, expected_sha256: str) -> dict:
    destination = new_destination(destination)
    manifest, payloads = verify_archive(archive, expected_sha256)
    # All archive checks precede destination creation. Exclusive writes preserve
    # any destination that appears concurrently; IO failures keep partial output.
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir(exist_ok=False)
    for name, payload in payloads.items():
        path = destination.joinpath(*name.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(payload)
    with (destination / MANIFEST_NAME).open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2)
        stream.write("\n")
    return {"schema": "robopaint.colab-source-unpack.v1", "source_schema": SCHEMA,
            "files": len(payloads), "archive_sha256": expected_sha256.lower(),
            "verified": True, "model_inference": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    pack_parser = commands.add_parser("pack", help="Create a reviewable minimal source ZIP; never upload")
    pack_parser.add_argument("--source-root", type=Path, default=ROOT)
    pack_parser.add_argument("--output", type=Path, required=True)
    unpack_parser = commands.add_parser("unpack", help="Verify a trusted archive SHA and safely unpack")
    unpack_parser.add_argument("--archive", type=Path, required=True)
    unpack_parser.add_argument("--destination", type=Path, required=True)
    unpack_parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    try:
        result = (pack(args.source_root, args.output) if args.command == "pack" else
                  unpack(args.archive, args.destination, args.expected_sha256))
    except (OSError, ValueError) as error:
        parser.exit(1, f"Source bundle failed: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
