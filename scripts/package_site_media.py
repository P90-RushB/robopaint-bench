"""Prepare a small, exact media ZIP for owner review. This never uploads files."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from build_site import ROOT, load_cases, verify_media


def package(media_root: Path, destination: Path, case_ids: list[str] | None = None) -> dict:
    _, cases, _ = load_cases()
    known = {case["spec"]["id"] for case in cases}
    selected = set(case_ids) if case_ids else known
    if not selected <= known:
        raise ValueError("Unknown benchmark case in media selection")
    expected = {key: value for case in cases if case["spec"]["id"] in selected for key, value in case["expected_media"].items()}
    if destination.exists():
        raise ValueError("Refusing to overwrite an existing review archive")
    payloads = {}
    for key, spec in sorted(expected.items()):
        path = media_root / key.removeprefix("assets/media/")
        payload = path.read_bytes()
        verify_media(payload, spec, key)
        payloads[key] = payload
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for key, payload in payloads.items():
            info = zipfile.ZipInfo(key, date_time=(2026, 10, 19, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, payload)
    report = {"schema": "robopaint.site-media-review.v1", "case_ids": sorted(selected), "complete_site_media": selected == known, "files": len(payloads), "uncompressed_bytes": sum(map(len, payloads.values())), "archive_bytes": destination.stat().st_size, "archive_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(), "publication_performed": False, "selection": list(payloads)}
    destination.with_suffix(".manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--media-root", type=Path, default=ROOT / "site/assets/media")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", action="append", dest="case_ids", help="Package one task for cross-machine transfer; omit for the complete site")
    args = parser.parse_args()
    print(json.dumps(package(args.media_root, args.output, args.case_ids), indent=2))


if __name__ == "__main__":
    main()
