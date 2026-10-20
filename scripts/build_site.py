"""Assemble a portable static site from allowlisted metadata and verified media.

No model calls, environment launches, deployment or source-data uploads occur.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def asset_path(value: str) -> str:
    path = PurePosixPath(value)
    if not value.startswith("assets/media/") or path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ValueError(f"Unsafe media path: {value!r}")
    if any(part in ("", ".") for part in value.split("/")):
        raise ValueError(f"Non-canonical media path: {value!r}")
    return path.as_posix()


def expected_media(results: dict, editorial: dict) -> dict:
    expected = {}
    for model in results["models"]:
        for attempt in model["attempts"]:
            canvas = attempt["canvas"]
            key = asset_path(canvas["path"])
            if key in expected:
                raise ValueError(f"Duplicate media path: {key}")
            expected[key] = {"sha256": canvas["sha256"], "bytes": canvas["bytes"]}
    for item in editorial.get("assets", []):
        key = asset_path(item["path"])
        if key in expected:
            raise ValueError(f"Duplicate editorial media: {key}")
        expected[key] = {"sha256": item["sha256"], "bytes": item["bytes"]}
    reference = results["target"]["reference"]
    if expected.get(asset_path(reference["path"]), {}).get("sha256") != reference["sha256"]:
        raise ValueError("Editorial reference must match the benchmark input hash")
    return expected


def validate_recommendation(recommendation: dict, results: dict) -> None:
    if recommendation.get("case_id") != results["case_id"]:
        raise ValueError("Recommendation case mismatch")
    if recommendation.get("status") == "awaiting_owner":
        if recommendation.get("tiers"):
            raise ValueError("Pending recommendation must not contain a ranking")
        return
    if recommendation.get("status") != "provided" or not recommendation.get("attributed_to") or not recommendation.get("date"):
        raise ValueError("A recommendation requires status, attribution and date")
    ids = [model_id for tier in recommendation["tiers"] for model_id in tier["model_ids"]]
    if len(ids) != len(set(ids)) or set(ids) != {m["id"] for m in results["models"]}:
        raise ValueError("Recommendation must cover each known model exactly once; use tied tiers")
    if any(not tier.get("label") for tier in recommendation["tiers"]):
        raise ValueError("Each recommendation tier requires a label")


def verify_media(data: bytes, expected: dict, key: str) -> None:
    if len(data) != expected["bytes"] or sha256(data) != expected["sha256"]:
        raise ValueError(f"Media size/SHA-256 mismatch: {key}")


def validate_model_videos(videos: dict, results: dict) -> None:
    """Keep whole-session video links separate from per-round evidence."""
    if videos.get("schema") != "robopaint.model-videos.v1" or videos.get("case_id") != results["case_id"]:
        raise ValueError("Model video schema/case mismatch")
    models = videos.get("models")
    if not isinstance(models, dict) or set(models) != {m["id"] for m in results["models"]}:
        raise ValueError("Model videos must cover each known model exactly once")
    bvids = set()
    for item in models.values():
        if not isinstance(item, dict):
            raise ValueError("Invalid model video entry")
        bvid = item.get("bvid", "")
        if not isinstance(bvid, str) or not re.fullmatch(r"BV[0-9A-Za-z]{10}", bvid) or bvid in bvids:
            raise ValueError("Invalid or duplicate Bilibili video ID")
        bvids.add(bvid)
        if item.get("url") != f"https://www.bilibili.com/video/{bvid}/":
            raise ValueError("Model video URL must match its canonical Bilibili ID")
        duration = item.get("duration_seconds")
        if type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0:
            raise ValueError("Model video duration must be positive and finite")


def read_archive(path_or_url: str, expected: dict) -> dict[str, bytes]:
    if path_or_url.startswith("https://"):
        with urllib.request.urlopen(path_or_url, timeout=45) as response:
            if urllib.parse.urlparse(response.geturl()).scheme != "https":
                raise ValueError("Media redirect must remain HTTPS")
            data = response.read(MAX_ARCHIVE_BYTES + 1)
    elif "://" in path_or_url:
        raise ValueError("Only HTTPS media archive URLs are supported")
    else:
        source = Path(path_or_url)
        if source.stat().st_size > MAX_ARCHIVE_BYTES:
            raise ValueError("Media archive exceeds size limit")
        data = source.read_bytes()
    if len(data) > MAX_ARCHIVE_BYTES:
        raise ValueError("Media archive exceeds size limit")
    verified = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            key = asset_path(entry.filename)
            if key not in expected or key in verified:
                raise ValueError(f"Unexpected or duplicate archive member: {key}")
            if entry.file_size != expected[key]["bytes"]:
                raise ValueError(f"Unexpected uncompressed size: {key}")
            payload = archive.read(entry)
            verify_media(payload, expected[key], key)
            verified[key] = payload
    return verified


def render_doc(source: Path, destination: Path, title: str) -> None:
    import markdown
    import html
    import re

    text = source.read_text(encoding="utf-8")
    # Source repository links remain repository links; sibling Markdown becomes HTML.
    text = re.sub(r"(?<=\]\()([a-z0-9_-]+)\.md(?=[#)])", r"\1.html", text, flags=re.I)
    content = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists", "toc"])
    def rewrite_link(match):
        href = html.unescape(match.group(1))
        if urllib.parse.urlparse(href).scheme or href.startswith(("#", "//")):
            return match.group(0)
        url = urllib.parse.urlsplit(href)
        target = (source.parent / url.path).resolve()
        try:
            relative = target.relative_to(ROOT).as_posix()
        except ValueError:
            return match.group(0)
        name = target.name
        if (relative.startswith("docs/") and name.endswith(".md")) or relative == "benchmarks/protocol.md":
            href = name.replace(".md", ".html")
        elif relative.endswith(".html") and not (ROOT / relative).exists():
            href = relative.rsplit("/", 1)[-1]
        else:
            href = "https://github.com/P90-RushB/robopaint-bench/blob/main/" + urllib.parse.quote(relative)
        if url.fragment:
            href += "#" + url.fragment
        return 'href="' + html.escape(href, quote=True) + '"'
    content = re.sub(r'href="([^"]+)"', rewrite_link, content)
    document = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} · RoboPaintBench</title>
<link rel="stylesheet" href="../styles.css"><style>main.article{{max-width:860px;margin:55px auto;padding:0 24px}}.article h1{{font-size:46px;letter-spacing:-2px}}.article h2{{font-size:30px;letter-spacing:-1px;line-height:1.2;margin-top:38px}}.article h3{{margin-top:28px}}.article p,.article li{{font-size:15px}}.article pre{{overflow:auto;background:#e7ece7;padding:20px;font-size:12px}}.article code{{overflow-wrap:anywhere}}.article table{{display:block;overflow-x:auto}}.article img{{max-width:100%}}</style></head><body><main class="article"><a class="text-link" href="../index.html">← RoboPaintBench</a><article style="margin-top:30px">{content}</article></main></body></html>'''
    destination.write_text(document, encoding="utf-8")


def build(output: Path, media_root: Path | None, archive: str | None, allow_missing: bool, publication_approved: bool = False) -> dict:
    results_path = ROOT / "benchmarks/results/golden_gate.json"
    editorial_path = ROOT / "benchmarks/results/editorial-media.json"
    results = json.loads(results_path.read_text(encoding="utf-8"))
    editorial = json.loads(editorial_path.read_text(encoding="utf-8"))
    recommendation_path = ROOT / "benchmarks/results/editorial-ranking.json"
    validate_recommendation(json.loads(recommendation_path.read_text(encoding="utf-8")), results)
    videos_path = ROOT / "benchmarks/results/model-videos.json"
    videos = json.loads(videos_path.read_text(encoding="utf-8"))
    validate_model_videos(videos, results)
    expected = expected_media(results, editorial)
    media = read_archive(archive, expected) if archive else {}
    missing = []
    if media_root:
        for key, spec in expected.items():
            file = media_root / PurePosixPath(key).relative_to("assets/media")
            if not file.is_file():
                continue
            payload = file.read_bytes()
            verify_media(payload, spec, key)
            media[key] = payload
    missing = sorted(set(expected) - set(media))
    if missing and not allow_missing:
        raise ValueError(f"Missing {len(missing)} verified assets; assemble the media bundle first. First missing: {missing[0]}")
    if publication_approved and missing:
        raise ValueError("A publication build requires all verified media")
    output = output.resolve()
    if output == ROOT or ROOT.is_relative_to(output) or (ROOT / "site").resolve() == output:
        raise ValueError("Output must not replace the repository or source site")
    # Never remove or overwrite a directory containing unrelated files.
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory must be empty; use a new preview directory")
    output.mkdir(parents=True, exist_ok=True)
    for filename in ("index.html", "styles.css", "app.js", ".nojekyll"):
        text = (ROOT / "site" / filename).read_text(encoding="utf-8")
        if filename == "index.html":
            text = text.replace('.md"', '.html"')
        (output / filename).write_text(text, encoding="utf-8")
    (output / "assets").mkdir()
    shutil.copyfile(ROOT / "site/assets/mark.svg", output / "assets/mark.svg")
    for filename in ("LICENSE", "NOTICE", "CITATION.cff"):
        shutil.copyfile(ROOT / filename, output / filename)
    (output / "data").mkdir()
    for path in (results_path, ROOT / "benchmarks/results/release-manifest.json", editorial_path, recommendation_path, videos_path):
        value = json.loads(path.read_text(encoding="utf-8"))
        if publication_approved and path != recommendation_path:
            value["publication_status"] = "approved_for_publication"
            for artifact in value.get("artifacts", []):
                if artifact.get("publication_status") == "pending_approval" and artifact.get("path") in expected:
                    artifact["publication_status"] = "approved_for_publication"
        (output / "data" / path.name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Built pages also work when opened directly from their extracted directory.
    # Keep the downloadable JSON alongside them for provenance and reuse.
    inline = []
    for element_id, filename in (("benchmark-data", "golden_gate.json"), ("recommendation-data", "editorial-ranking.json"), ("model-video-data", "model-videos.json")):
        payload = (output / "data" / filename).read_text(encoding="utf-8").replace("<", "\\u003c")
        inline.append(f'<script type="application/json" id="{element_id}">{payload}</script>')
    index = output / "index.html"
    index.write_text(index.read_text(encoding="utf-8").replace("</head>", "\n".join(inline) + "\n</head>"), encoding="utf-8")
    for key, payload in media.items():
        destination = output / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
    (output / "docs").mkdir()
    docs = {"protocol.md": ROOT / "benchmarks/protocol.md"}
    for filename in ("scoring.md", "submissions.md", "limitations.md", "quickstart.md", "custom-painting.md", "replay.md", "hosting.md", "attribution.md", "release.md", "runtime-installation.md", "colab-record.md", "colab-record.zh-CN.md", "colab-validation-20261020.md"):
        docs[filename] = ROOT / "docs" / filename
    for filename, source in docs.items():
        render_doc(source, output / "docs" / filename.replace(".md", ".html"), filename.removesuffix(".md").replace("-", " ").title())
    report = {"schema": "robopaint.site-build.v1", "models": len(results["models"]), "model_videos": len(videos["models"]), "verified_media": len(media), "missing_media": missing, "publication_approved": publication_approved, "publication_performed": False}
    (output / "build-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--media-root", type=Path, default=ROOT / "site/assets/media")
    parser.add_argument("--media-archive", help="Approved local ZIP path or HTTPS URL; exact members are hash checked")
    parser.add_argument("--allow-missing-media", action="store_true", help="Source-only QA; not suitable for public launch")
    parser.add_argument("--publication-approved", action="store_true", help="Record an existing owner approval in the build metadata; does not deploy")
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.media_root, args.media_archive, args.allow_missing_media, args.publication_approved), indent=2))


if __name__ == "__main__":
    main()
