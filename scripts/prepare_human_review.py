#!/usr/bin/env python3
"""Prepare an optional offline, blinded attempt-3 pairwise review. No network."""
from __future__ import annotations

import argparse
import base64
import hashlib
import itertools
import json
from pathlib import Path
import random
import re
import secrets
import struct

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "robopaint.human-review.v1"
KEY_SCHEMA = "robopaint.human-review-key.v1"
PRIMARY_ATTEMPT = 3
CHOICES = {"A", "B", "tie", "cannot_judge"}


class ReviewError(ValueError):
    """Invalid or inconsistent review evidence."""


def read_json(path: Path) -> dict:
    def unique(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ReviewError("Duplicate JSON field")
            value[key] = item
        return value
    result = json.loads(path.read_text("utf-8"), object_pairs_hook=unique)
    if not isinstance(result, dict):
        raise ReviewError("Expected a JSON object")
    return result


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def rater_identity(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", value):
        raise ReviewError("Rater ID must be 1–64 letters, numbers, dots, underscores or hyphens")
    return value.casefold()


def local_output(path: Path) -> Path:
    path = path.resolve()
    if not path.is_relative_to((ROOT / "local_save").resolve()):
        raise ReviewError("Review outputs must be explicitly placed inside this checkout's local_save/")
    return path


def checked_png(site_root: Path, entry: dict) -> tuple[bytes, dict]:
    relative = entry.get("path")
    if not isinstance(relative, str) or "\\" in relative:
        raise ReviewError("Invalid public image path")
    root = site_root.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or Path(relative).is_absolute():
        raise ReviewError("Image path escapes site root")
    data = path.read_bytes()
    if digest(data) != entry.get("sha256") or (entry.get("bytes") is not None and len(data) != entry["bytes"]):
        raise ReviewError("Image hash or byte count mismatch")
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ReviewError("Expected PNG image")
    width, height = struct.unpack(">II", data[16:24])
    if (width, height) != (entry.get("width"), entry.get("height")):
        raise ReviewError("Image dimensions disagree with dataset")
    return data, {"sha256": digest(data), "bytes": len(data), "width": width, "height": height}


def load_dataset(dataset: Path, site_root: Path) -> tuple[dict, dict]:
    source = read_json(dataset)
    if source.get("schema") != "robopaint.public-results.v1" or source.get("case_id") != "golden_gate":
        raise ReviewError("Expected the Golden Gate public-results dataset")
    models = source.get("models", [])
    ids = [model.get("id") for model in models]
    if len(ids) != 11 or len(set(ids)) != 11 or any(not isinstance(i, str) or not i for i in ids):
        raise ReviewError("Review requires exactly 11 unique models")
    reference, reference_info = checked_png(site_root, source["target"]["reference"])
    images, selected = {}, []
    for model in sorted(models, key=lambda item: item["id"]):
        attempts = [item for item in model.get("attempts", []) if item.get("attempt") == PRIMARY_ATTEMPT]
        if len(attempts) != 1:
            raise ReviewError("Each model must have exactly one final attempt-3 canvas")
        image, info = checked_png(site_root, attempts[0]["canvas"])
        selected.append({"model_id": model["id"], "attempt": PRIMARY_ATTEMPT, **info})
        images[model["id"]] = image
    if len({(item["width"], item["height"]) for item in selected}) != 1:
        raise ReviewError("Pairwise canvases must have equal dimensions")
    selection = {"case_id": "golden_gate", "release_id": source["release_id"],
                 "primary_attempt": PRIMARY_ATTEMPT, "reference": reference_info, "canvases": selected}
    manifest = {"dataset_sha256": digest(dataset.read_bytes()), "selection_sha256": digest(canonical(selection)),
                "selection": selection}
    return manifest, {"reference": reference, "canvases": images}


def prepare(dataset: Path, site_root: Path, output: Path, rater_id: str, seed: str) -> dict:
    identity = rater_identity(rater_id)
    output = local_output(output)
    if output.exists():
        raise ReviewError("Refusing to overwrite an existing review directory")
    manifest, images = load_dataset(dataset, site_root)
    # The private random salt keeps model names out of browser source. This is
    # practical blinding, not a security boundary against identifying the art.
    salt = secrets.token_hex(32)
    mapping = {digest((salt + item["model_id"]).encode())[:24]: item for item in manifest["selection"]["canvases"]}
    by_model = {item["model_id"]: opaque for opaque, item in mapping.items()}
    pairs = list(itertools.combinations(sorted(by_model), 2))
    rng = random.Random(digest(canonical([manifest["selection_sha256"], identity, str(seed)])))
    rng.shuffle(pairs)
    presentation = []
    for left, right in pairs:
        if rng.getrandbits(1):
            left, right = right, left
        a, b = by_model[left], by_model[right]
        presentation.append({"pair_id": digest((salt + ":" + ":".join(sorted([a, b]))).encode())[:24], "a": a, "b": b})
    public = {"schema": SCHEMA, "package_id": secrets.token_hex(16), "rater_id": identity,
              "dataset_sha256": manifest["dataset_sha256"], "selection_sha256": manifest["selection_sha256"],
              "reference_sha256": manifest["selection"]["reference"]["sha256"],
              "primary_attempt": PRIMARY_ATTEMPT, "pairs": presentation}
    key = {"schema": KEY_SCHEMA, **{k: v for k, v in public.items() if k != "schema"},
           "selection": manifest["selection"], "attempt_mapping": mapping,
           "seed": str(seed), "identity_limit": "Rater identity and independence are self-declared, not verified."}
    public["reference_image"] = "data:image/png;base64," + base64.b64encode(images["reference"]).decode("ascii")
    public["images"] = {opaque: "data:image/png;base64," + base64.b64encode(images["canvases"][item["model_id"]]).decode("ascii")
                        for opaque, item in mapping.items()}
    payload = json.dumps(public, separators=(",", ":")).replace("<", "\\u003c")
    output.mkdir(parents=True)
    (output / "review.html").write_text(HTML.replace("__PAYLOAD__", payload), "utf-8")
    (output / "administrator-key.json").write_text(json.dumps(key, indent=2) + "\n", "utf-8")
    return {"review": str(output / "review.html"), "key": str(output / "administrator-key.json"),
            "pairs": len(presentation), "package_id": public["package_id"]}


HTML = r'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RoboPaintBench · blinded review</title><style>
body{font:17px system-ui,sans-serif;margin:0;background:#f4f1eb;color:#18241f}main{max-width:1200px;margin:auto;padding:24px}h1{font-size:28px}p{line-height:1.5}.top{display:flex;gap:20px;flex-wrap:wrap;align-items:center}.reference{width:320px;max-width:100%;height:auto}.pair{display:grid;grid-template-columns:1fr 1fr;gap:20px}figure{margin:0}figure img{display:block;width:100%;height:auto;background:white}figcaption{font-weight:700;padding:10px}button{font:inherit;padding:12px 22px;margin:5px;border:1px solid #69776b;border-radius:8px;background:white;cursor:pointer}button[aria-pressed=true]{background:#1f4d3c;color:white}button:disabled{opacity:.45;cursor:default}.controls{text-align:center;padding:18px}#status{font-weight:600}label{display:block;margin:20px 0}#error{color:#a12e21}@media(max-width:650px){main{padding:12px}.pair{gap:8px}button{padding:10px 14px}}</style>
<main><h1>Golden Gate Bridge · blinded canvas review</h1><div class="top"><img class="reference" id="reference" alt="Reference photograph"><div><p>Rater ID: <strong id="rater"></strong> · final attempt 3 only</p><p>Compare each painting with the photograph. Prefer the one that better reproduces<br>the bridge's structure, composition and colors. Use Tie for similar quality;<br>Cannot judge when you cannot assess the pair. Judge all 55 pairs.</p><p>This optional study uses self-declared independent human judgments.<br>Do not consult model identities or another rater's answers during review.</p></div></div>
<p id="status" aria-live="polite"></p><section class="pair"><figure><figcaption>A</figcaption><img id="a" alt="Anonymous painting A"></figure><figure><figcaption>B</figcaption><img id="b" alt="Anonymous painting B"></figure></section>
<div class="controls"><div id="choices"><button data-v="A">Prefer A</button><button data-v="B">Prefer B</button><button data-v="tie">Tie</button><button data-v="cannot_judge">Cannot judge</button></div><button id="prev">Previous</button><button id="next">Next</button></div>
<label><input type="checkbox" id="attest"> I made these judgments independently, without consulting model identities or other raters' answers.</label>
<button id="export">Export completed review JSON</button><p id="error" role="status"></p><p>Everything stays in this HTML file and this browser's local storage; nothing is uploaded. Export JSON and send it to the study administrator separately. Keep the exported file: browser storage may be unavailable or cleared. The administrator key is separate. Image recognition can reveal authorship; this is practical blinding, not a security guarantee.</p></main>
<script>"use strict";const data=__PAYLOAD__;let pos=0,answers={},storageOkay=true;const storageKey="robopaint-review:"+data.package_id;
const el=id=>document.getElementById(id);try{const saved=JSON.parse(localStorage.getItem(storageKey)||"null");if(saved){answers=saved.answers||{};pos=Math.max(0,Math.min(data.pairs.length-1,saved.pos||0));el("attest").checked=saved.attestation===true;}}catch(e){storageOkay=false;}
el("reference").src=data.reference_image;el("rater").textContent=data.rater_id;
function persist(){try{localStorage.setItem(storageKey,JSON.stringify({answers,pos,attestation:el("attest").checked}));}catch(e){storageOkay=false;}}
function render(){const pair=data.pairs[pos];el("a").src=data.images[pair.a];el("b").src=data.images[pair.b];const complete=data.pairs.filter(p=>["A","B","tie","cannot_judge"].includes(answers[p.pair_id])).length;el("status").textContent=`Pair ${pos+1} of ${data.pairs.length} · ${complete} answered`;document.querySelectorAll("[data-v]").forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.v===answers[pair.pair_id])));el("prev").disabled=pos===0;el("next").disabled=pos===data.pairs.length-1;el("export").disabled=complete!==data.pairs.length||!el("attest").checked;el("error").textContent=storageOkay?"":"Browser progress storage is unavailable. Keep this tab open and export your completed review.";}
document.querySelectorAll("[data-v]").forEach(button=>button.onclick=()=>{answers[data.pairs[pos].pair_id]=button.dataset.v;persist();render();});el("prev").onclick=()=>{pos--;persist();render();};el("next").onclick=()=>{pos++;persist();render();};el("attest").onchange=()=>{persist();render();};
el("export").onclick=()=>{if(el("export").disabled)return;const output={schema:data.schema,package_id:data.package_id,rater_id:data.rater_id,dataset_sha256:data.dataset_sha256,selection_sha256:data.selection_sha256,reference_sha256:data.reference_sha256,primary_attempt:data.primary_attempt,independence_attestation:el("attest").checked,exported_at:new Date().toISOString(),answers:data.pairs.map(p=>({...p,choice:answers[p.pair_id]}))};const url=URL.createObjectURL(new Blob([JSON.stringify(output,null,2)+"\n"],{type:"application/json"}));const link=document.createElement("a");link.href=url;link.download="review-"+data.rater_id+"-"+data.package_id+".json";link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};render();</script></html>'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "benchmarks/results/golden_gate.json")
    parser.add_argument("--site-root", type=Path, default=ROOT / "site")
    parser.add_argument("--output", type=Path, required=True, help="New directory under local_save/")
    parser.add_argument("--rater-id", required=True, help="Distinct self-declared pseudonym; do not use personal information")
    parser.add_argument("--seed", default="robopaint-attempt3-v1")
    args = parser.parse_args()
    try:
        result = prepare(args.dataset, args.site_root, args.output, args.rater_id, args.seed)
    except (ReviewError, OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        parser.exit(2, f"Review preparation failed: {error}\n")
    print(json.dumps(result, indent=2))
    print("Give the rater review.html only. Keep administrator-key.json separate and private. No score was generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
