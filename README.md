# RoboPaintBench

**From pixels to physical strokes.** A visual, replayable benchmark of language models controlling a simulated robot arm to paint, built on [AgentArk](https://github.com/P90-RushB/AgentArk).

**v0.1 research preview** · 2 fixed targets · 11 models per target · 3 ICL rounds each · 66 canvases · [中文说明](README.zh-CN.md)

Give a model two workspace cameras, flange-pose feedback, and a paintbrush. It must find the canvas and paint, plan timed 3D movements, inspect the resulting marks, and use feedback across three rounds. It does not receive a ready-made stroke program or paper/paint coordinates.

**In-context learning: ICL Round 1 → ICL Round 2 → ICL Round 3.** Each model runs one continuous session: every round starts with fresh paper while earlier experience remains available through SimpleAgent's context, summaries, and interaction archive. Model weights stay fixed; improvement is observed rather than assumed. “ICL Round n” is the display name for runtime `attempt n` in configs and records.

**All 11 models, including Astra, use AgentArk's built-in SimpleAgent harness.** They share the agent loop, action and observation interface, and task budget. Codex SDK, OpenRouter, and Volcengine Ark are model-access backends within that common harness. This keeps the comparison consistent at the harness and task level; each model's inference settings are recorded below.

This project is inspired by [Thijs Simonian's Bot Ross demonstration](https://thijs.net/projects/robot-painter), in which Astra paints the Golden Gate Bridge with a real robot arm. RoboPaintBench provides an independent, configurable **simulation** with its own robot, mechanics and evaluation protocol.

## Explore, run, or reproduce

| Entry | What it provides |
| --- | --- |
| [Project-site source](site/index.html) · [local preview and deployment](docs/hosting.md) | All-model gallery, ICL round switcher, three-round progression, side-by-side comparison, actual settings and one shared Bilibili player for all 11 models. Public deployment is pending. |
| [Open Golden Gate Colab](https://colab.research.google.com/drive/1szVNzToQ0VadlPTB2BymM-sgYNbnAHD_?usp=sharing) · [guide](docs/colab-record.md) · [notebook source](notebooks/GoldenGate_Record_Colab.ipynb) | Select T4 GPU, Run all, then open the viewer URL printed in step 7 to watch the camera views and action history. Replay recorded model actions and follow the camera views and interaction history; no model API key. [Dated execution evidence](docs/colab-validation-20261020.md). |
| [Pelican replay Colab](https://colab.research.google.com/github/P90-RushB/robopaint-bench/blob/main/notebooks/Pelican_Record_Colab.ipynb) · [guide](docs/pelican-results.md#replay-without-inference) | Select any of the 11 published Pelican records, locked to one HF revision. No model API key. New notebook checked offline; a hosted Pelican Colab run has not been validated. |
| [New model evaluation Colab](notebooks/RobotPainting_Colab.ipynb) | Guided installation, offline preparation and explicit user-started inference. Paid model evaluation is outside the hosted replay/interaction validation. |
| [Quickstart](docs/quickstart.md) | Locked runtime download and first local evaluation. |
| [Custom painting](docs/custom-painting.md) | Text goals, one or multiple reference images, configurable mechanics. |
| [Replay guide](docs/replay.md) | Replay saved actions through the original AgentArk environment. |
| [Protocol](benchmarks/protocol.md) · [result presentation](docs/scoring.md) | Fixed conditions, inference differences, author recommendations and optional human rating. |
| [Portable results](benchmarks/results/golden_gate.json) · [provenance manifest](benchmarks/results/release-manifest.json) | Verified attempt mapping, canvas hashes, steps, backend and evidence scope. |

## The collection

| Track | Target supplied to the model | Status |
| --- | --- | --- |
| **Golden Gate Bridge** | Reference photograph + “Reproduce the provided reference image as closely as possible.” | Initial 11-model / 33-canvas collection assembled. |
| **Pelican riding a bicycle** | `Paint a pelican riding a bicycle.`; workspace camera observations remain visual. | Independent 11-model / 33-canvas collection, 603 actions; author's personal ranking. |
| **Open canvas** | User text, a reference image, or multiple references. | Custom-run entry available; separate from the fixed-target comparisons. |

The standard environment uses seed 107, **3 connected ICL rounds × at most 96 environment actions per round**, two fixed **960 × 720** workspace views, a fixed brush and paper, infinite pigment, 120 Hz control and 480 Hz physics, at time scale 1. The paper resets between rounds; agent experience carries over within the same session. These are dependent rounds rather than independent experimental repeats.

The model submits up to 32 timed flange waypoints per action. Robot motion and brush contact generate marks. A human-only follow camera can record the process; it is not an extra model observation.

The **Golden Gate** table and gallery default to the **author's personal qualitative ranking**, supplied on **2026-10-19**. It is an attributed recommendation, not a numerical metric or human-consensus ranking.

| Author order | Model | Model access / reasoning | Actions, ICL rounds 1 / 2 / 3 |
| --- | --- | --- | --- |
| 1 | GPT-6 Astra | Codex SDK / ultra | 39 / 31 / 33 |
| 2 | GPT-6.1 Sol | OpenRouter / max | 55 / 44 / 56 |
| 3 | Gemini 4 Argon | OpenRouter / high | 26 / 21 / 24 |
| 4 | Claude Opus 5.5 | OpenRouter / mixed max → high | 17 / 13 / 13 |
| 5 | DeepSeek V4.1 Flash1017 | OpenRouter / max | 59 / 56 / 35 |
| 6 | Meta Muse Wonder | OpenRouter / max | 44 / 26 / 21 |
| 7 | Qwen3.8 Max Prime | OpenRouter / xhigh | 67 / 41 / 46 |
| 8 | MiMo V2.6 Pro | OpenRouter / thinking enabled; increased output budget | 19 / 6 / 6 |
| 9 | Kimi K3 | OpenRouter / max | 11 / 23 / 28 |
| 10 | Grok 4.7 | OpenRouter / xhigh | 96 / 96 / 47 |
| 11 | Doubao Seed2.1 Pro260915 | Volcengine Ark / high | 53 / 7 / 17 |

This retrospective collection uses the common SimpleAgent harness with recorded model-specific inference settings. Opus's first four actions use max/65,536, followed by high/20,480; MiMo's continuation uses 65,536; Astra's Codex SDK backend has no equivalent API output cap. These settings are not an equal-compute budget. Grok's final continuation is complete; action 217 is explicitly recorded as a harness-generated rejected no-motion step. Details and exact identifiers accompany the results.

All rounds remain inspectable, with ICL Round 3 selected for the main comparison. Formal human scoring is an optional follow-up; no numerical quality scores have been assigned. Task reward measures submission/save integrity, not fidelity. [Result presentation](docs/scoring.md) · [Scope and limitations](docs/limitations.md).

## Pelican: an independent text-goal collection

All 11 models completed three connected attempts: **33 canvases and 603 environment actions**. The prompt is exactly `Paint a pelican riding a bicycle.`; no reference image is appended. [Results and evidence](benchmarks/results/pelican.json) · [settings, limitations and replay](docs/pelican-results.md).

Pelican defaults to its own **author's personal ranking**, supplied on **2026-10-20**: **Astra → Sol → Argon → Opus → Wonder → MiMo → Qwen → Kimi → DeepSeek → Doubao → Grok**. The gallery and settings follow this order. Attribution and order are retained in [Pelican's ranking metadata](benchmarks/results/pelican-ranking.json); this is a subjective recommendation, not a numerical score or a human-consensus result.

The 11 Pelican process videos show all three attempts at **4× simulated-time speed**, with Chinese/English captions and explicit reading pauses for very short steps. Waiting/inference time is omitted. Videos, original canvases and records are associated by episode GUID. The [Pelican video index](benchmarks/results/pelican-videos.json) preserves the published links.

Public Pelican records and trajectories are pinned to HF commit `b16fb52e866ce6a33c52e287f04bfe4a77964453`. Complete action records support all 603 actions; six models’ first-attempt trajectory exports retain only their final 24 actions. These exports must not be mistaken for complete interaction or context history. Pelican Opus used **high**; MiMo had **two temporary 65,536-token requests**; Astra used **Codex SDK / max** without an API-equivalent hard output cap. These differ from some Golden Gate settings.

## Quickstart

Use an existing compatible Python environment; the pinned AgentArk package requires Python **3.10.0–3.10.12**. Install the locked AgentArk revision and runtime as described in the [quickstart](docs/quickstart.md). Set machine-local `AGENTARK_ENV_PATH`, `AGENTARK_MOD_PATH`, and the relevant API key at runtime.

```sh
# Offline: validates installed inputs and prepares one independent run.
python scripts/prepare_run.py --case golden_gate --model sol

# Explicitly start inference using the generated configuration path.
python scripts/run_eval.py --config '<generated-run>/eval.yaml'
```

The repository reuses AgentArk's evaluator, SimpleAgent, model tools, context management, runtime isolation, recording and replay. It does not introduce a second evaluation harness. Model inference can incur provider charges. Runtime packages and model backends have their own access requirements.

## Contribute a result

Read [submission requirements](docs/submissions.md) and use the [result issue form](https://github.com/P90-RushB/robopaint-bench/issues/new?template=result-submission.yml). Include every attempt, exact versions and settings, sanitized action evidence, artifact hashes, and the replay verification scope. Custom targets and altered mechanics get separate condition labels.

The 11 Golden Gate process videos are [available on Bilibili](https://space.bilibili.com/277451319/channel/collectiondetail?sid=9369723) and switch within one player on the project page. Each combines one model's three sequential ICL rounds, at 6× speed with Chinese/English captions; thinking and network waits are omitted. The [model video index](benchmarks/results/model-videos.json) preserves the exact links. The independent Pelican videos run at 4× rather than Golden Gate’s 6×; a narrated benchmark explainer remains pending.

## Development and release

```sh
python -m unittest discover -s tests -v
python -m pip install -r requirements-site.txt
python scripts/build_site.py --output local_save/site-preview-01
```

These checks do not run models or Unity. All **69 selected website PNGs** are included in the repository: 36 for Golden Gate (33 canvases, its reference and two recording frames), plus 33 Pelican canvases. A fresh clone can build the complete two-task site without a separate media archive or private result catalog. Full videos stream from Bilibili; no local video excerpt is required. The deployment workflow remains manual. Raw audits, reasoning, trajectories, full videos, credentials and machine paths stay outside Git. [Preview and hosting](docs/hosting.md) · [Validation and limits](docs/validation.md) · [Release guide](docs/release.md) · [中文发布方案](docs/launch-plan.zh-CN.md).

## Attribution and citation

The Golden Gate photograph is by **Frank Schulenburg**, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), resized without cropping. [Full source and asset notices](docs/attribution.md). Code/documentation use Apache-2.0; runtime/vendor assets and evaluation media retain separate terms. The owner has approved inclusion of the selected website images in Git; this does not apply the code license to those images or release the raw evaluation data.

Use [CITATION.cff](CITATION.cff) when referencing this software preview. No paper or peer-reviewed acceptance is claimed.
