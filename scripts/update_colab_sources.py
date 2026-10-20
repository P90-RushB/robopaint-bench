"""Refresh or check both replay notebooks' exact embedded source bundles.

Only the bootstrap's source list, archive hash and base64 archive are updated.
All other cells, including Golden Gate's selected preview images, are retained.
This maintenance command performs no network, runtime or model operations.
"""
from __future__ import annotations

import argparse
import ast
import base64
import json
from pathlib import Path
import tempfile
import textwrap

import package_colab_source


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ("GoldenGate_Record_Colab.ipynb", "Pelican_Record_Colab.ipynb")


def refresh(*, write: bool = False) -> dict:
    with tempfile.TemporaryDirectory(prefix="robopaint-notebook-source-") as temporary:
        archive = Path(temporary) / "source.zip"
        receipt = package_colab_source.pack(ROOT, archive)
        encoded = base64.b64encode(archive.read_bytes()).decode("ascii")
    replacements = {
        "SOURCE_FILES": "SOURCE_FILES = " + repr(package_colab_source.ALLOWED_FILES) + "\n",
        "SOURCE_ARCHIVE_SHA256": "SOURCE_ARCHIVE_SHA256 = " + repr(receipt["archive_sha256"]) + "\n",
        "EMBEDDED_SOURCE_ZIP_B64": "EMBEDDED_SOURCE_ZIP_B64 = (\n" + "".join(
            "    " + repr(part) + "\n" for part in textwrap.wrap(encoded, 110)) + ")\n",
    }
    prepared = []
    for name in NOTEBOOKS:
        path = ROOT / "notebooks" / name
        notebook = json.loads(path.read_text("utf-8"))
        bootstrap = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"
                     and "def unpack_source_bundle" in "".join(cell["source"])]
        if len(bootstrap) != 1:
            raise ValueError(f"{name}: expected exactly one source bootstrap")
        cell = bootstrap[0]
        source = "".join(cell["source"])
        lines = source.splitlines(keepends=True)
        assignments = [node for node in ast.parse(source).body if isinstance(node, ast.Assign)
                       and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                       and node.targets[0].id in replacements]
        if (len(assignments) != len(replacements)
                or {node.targets[0].id for node in assignments} != set(replacements)):
            raise ValueError(f"{name}: source bootstrap assignments changed; review before refresh")
        for node in reversed(assignments):
            lines[node.lineno - 1:node.end_lineno] = [replacements[node.targets[0].id]]
        updated = "".join(lines)
        ast.parse(updated)
        cell["source"] = updated.splitlines(keepends=True)
        prepared.append((path, notebook, source != updated))
    changed = [path.name for path, _, different in prepared if different]
    if write:
        for path, notebook, different in prepared:
            if different:
                path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"files": receipt["files"], "archive_sha256": receipt["archive_sha256"],
            "notebooks": list(NOTEBOOKS), "changed": changed, "written": write,
            "current": write or not changed, "model_inference": False, "network_used": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--write", action="store_true", help="Refresh only the embedded bootstrap assignments")
    selection.add_argument("--check", action="store_true", help="Check only (the default); fail if stale")
    args = parser.parse_args()
    result = refresh(write=args.write)
    print(json.dumps(result, indent=2))
    if not result["current"]:
        parser.exit(1, "Embedded source changed; review source files, then run with --write.\n")


if __name__ == "__main__":
    main()
