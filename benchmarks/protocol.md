# RoboPaintBench protocol v0.1

**Status: initial Golden Gate collection; numerical quality ratings pending.**
RoboPaintBench evaluates simulated robot painting through
[AgentArk](https://github.com/P90-RushB/AgentArk). Its initial collection contains
11 model configurations, each completing one continuous session of three
**in-context learning (ICL) rounds**. The public gallery documents observable
outcomes. An explicitly labeled
author recommendation supplies the default gallery order; a measured quality
score requires actual ratings under the optional
[human evaluation plan](../docs/scoring.md).

## What the benchmark tests

A multimodal model turns a visual or written goal into physical brush motion.
It observes the workspace, issues timed robot commands, inspects their effects,
and can use experience from earlier attempts. This jointly exercises visual
grounding, spatial planning, contact control, and revision. All 11 models use
**the same AgentArk built-in SimpleAgent harness**, including Astra. Results
describe each model and its inference settings within that shared harness and
task; they do not isolate a single cognitive capability.

| Track | Goal supplied to the model | Release status |
| --- | --- | --- |
| Golden Gate | Fixed reference photograph plus `Reproduce the provided reference image as closely as possible.` | Initial 11-model collection |
| Pelican | `Paint a pelican riding a bicycle.`; no target image | Configuration available; results pending from a separate evaluation |
| Custom studio | User-provided text and/or ordered reference images | Interactive use; excluded from benchmark comparisons |

The Pelican track still supplies rendered workspace observations. “Text goal”
describes its target specification, not a text-only observation interface. Its
release needs its own frozen evaluation criteria and data acceptance checks.
No Pelican results are implied by the configuration's availability.

## In-context learning across three rounds

**ICL Round 1 → ICL Round 2 → ICL Round 3** is one continuous session per model.
Each round resets the paper and seed-dependent physical setup while preserving
the model's preceding experience through SimpleAgent's normal working context,
summaries, and interaction archive. Later rounds can reuse observations and
lessons from earlier rounds. Model parameters are unchanged, and improvement is
an outcome to inspect rather than a guarantee.

The presentation label **ICL Round n** maps directly to runtime **attempt n**.
Configuration fields, original action records, episode mappings, and provenance
retain their existing `attempt` identifiers. The three connected rounds are
dependent observations, not three independent experimental trials.

## Reference environment and interaction

| Property | Golden Gate reference condition |
| --- | --- |
| Task | AgentArk Task107 `RobotPainting`, runtime `task-v1` |
| Runtime | Linux env `1.0.5`, GPU-rendered; `no_graphics: false` |
| Setup | Group seed `107`; fixed brush, fixed board, infinite pigment |
| Timing | 120 Hz control; 480 Hz physics; time scale 1 |
| Session budget | 3 connected ICL rounds; at most 96 environment actions per round |
| Reset | Clean paper and the same seed-dependent setup at each round |
| Memory | Earlier experience retained through normal SimpleAgent context, summaries, and archives |
| Observation | Two fixed workspace camera views, each 960 × 720; public flange pose, action status, and simulation timing |
| Reference | 1280 × 800 photograph attached at the first decision of each round |
| Primary comparison canvas | Final saved canvas of ICL Round 3 (runtime attempt 3) |

The model receives the flange pose in robot-base coordinates, not privileged
paper, pigment, or brush-mount coordinates. It infers useful relationships from
observations and interactions. The human-facing brush-follow camera is for
presentation and is not an additional model observation.

`MoveFlange` accepts 1–32 timed waypoints: position in robot-base metres (`x`
right, `y` forward, `z` up), orientation as quaternion `xyzw`, and `duration_s`.
Each waypoint lasts at least 0.08 seconds and a batch totals at most 20 seconds.
Task-owned robot control executes the command through the simulated robot and
soft brush. This is a high-level pose-command interface rather than direct torque
control. `SubmitPainting` ends the attempt and saves its canvas; reaching the
action limit also saves the final canvas.

An environment action can contain many waypoints. A model decision can contain
multiple model requests and archive/note tool calls. **96 actions is neither a
token budget nor a 96-request limit.** An early submission is a valid outcome;
fewer actions do not establish better quality. The three rounds share experience
within the same continuous session.

The reference condition retains the existing AgentArk task and SimpleAgent. It
does not supply target stroke trajectories, an oracle plan, object coordinates,
or a separate image-generation route. Changing brush attachment, grip-force
constraints, pigment depletion, board behavior, observations, budgets, or goal
inputs creates a distinct experimental condition. These are supported avenues
for extending the environment, not conditions covered by the initial results.

## Agent and inference contract

Every model uses the same SimpleAgent loop, action/observation interface,
interaction archives, notes, and shared task budget. **Codex SDK, OpenRouter, and
Volcengine Ark are model-access backends inside this harness**. Astra's access
through Codex SDK keeps SimpleAgent in charge of the painting interaction, just
as the API backends do for the other models. The common harness and task provide
consistent evaluation conditions across the collection.

SimpleAgent uses native `submit_action` calls for environment actions, read-only
interaction archives, and writable notes. Context compression can
remove older images from the current request; archived observations can be
revisited through file/image tools. A nominal image threshold does not guarantee
that all earlier images remain in the live request.

[versions.json](versions.json) locks the current preparation baseline, inputs,
downloads, and defaults. Its working-context token threshold is 262,144; action
output reserve is 20,480 tokens; summary input limit is 48,000 tokens and summary
generation budget is 32,768 tokens. Other character, byte, image, request, and
tool limits also apply. The actual run manifest and effective configuration take
precedence over a template when describing a historical run.

Declare model identifier, provider/route where available, evaluation date,
reasoning/thinking settings, output limits, tool policy, and any mid-session
changes. The common harness adapts requests to each model-access backend.
Labels such as `high`, `max`, and `ultra` are provider-specific; native tool
support and output-limit enforcement also differ. These recorded inference
differences do not change the shared agent loop or task interface, and the
collection is not a matched-compute comparison.

## Initial Golden Gate collection

These retained completed sessions follow the author's personal ranking, supplied
on 2026-10-19. Counts include submissions and the documented Grok failed step.
All use SimpleAgent; model-access and inference settings are shown separately.

| Author order | Model | Model access | Recorded reasoning setting | Actions: ICL rounds 1 / 2 / 3 |
| --- | --- | --- | --- | --- |
| 1 | GPT-6 Astra | Codex SDK | `ultra` | 39 / 31 / 33 |
| 2 | GPT-6.1 Sol | OpenRouter | `max` | 55 / 44 / 56 |
| 3 | Gemini 4 Argon | OpenRouter | `high` | 26 / 21 / 24 |
| 4 | Claude Opus 5.5 | OpenRouter | Initially `max`, then `high` | 17 / 13 / 13 |
| 5 | DeepSeek V4.1 Flash1017 | OpenRouter | `max` | 59 / 56 / 35 |
| 6 | Meta Muse Wonder | OpenRouter | `max` | 44 / 26 / 21 |
| 7 | Qwen3.8 Max Prime | OpenRouter | `xhigh` | 67 / 41 / 46 |
| 8 | MiMo V2.6 Pro | OpenRouter | Thinking enabled; output budget increased during continuation | 19 / 6 / 6 |
| 9 | Kimi K3 | OpenRouter | `max` | 11 / 23 / 28 |
| 10 | Grok 4.7 | OpenRouter | `xhigh` | 96 / 96 / 47 |
| 11 | Doubao Seed2.1 Pro260915 | Volcengine Ark | `high` | 53 / 7 / 17 |

Material run notes:

- **Opus:** the first four actions of attempt 1 used `max` with a 65,536-token
  output budget; the remaining actions used `high` with 20,480. Later attempts
  inherited that history. This is a mixed-setting session.
- **MiMo:** the retained session continued with a 65,536-token output budget
  after earlier output-budget problems. It was not restarted from a clean first
  attempt with the larger budget.
- **Astra:** the Codex SDK did not enforce an API-equivalent hard output cap.
  A declared 20,480-token setting is not proof of enforcement.
- **Grok:** all three attempts are complete. Global step 217 is a documented
  harness-generated rejected/no-movement action after tool-budget exhaustion.
  It consumed a step and is not presented as a model-authored command. Final
  counts are 96 / 96 / 47.
- **Doubao:** attempt 2 ended by active submission after six motion commands
  with contact-protection events. Seven steps is not evidence of an incomplete
  attempt. Two HTTP requests have unknown usage, so known tokens are not a
  complete billing total.

This is a **retrospective initial collection**. Development runs and failed
launches exist; continued runs retain their recovery provenance. It is not a
preregistered or randomly sampled study. Freezing a rating plan before human
ratings does not retrospectively preregister collection. All 33 final canvases
should remain accessible with their real attempt labels. A visually preferred
earlier attempt must not silently replace attempt 3 in the primary comparison.

## Quality, recommendations, and evidence

Task reward measures submission/saving integrity. It is **not a fidelity or
artistic-quality score**: a poor painting may receive successful submission
reward. The author supplied a personal qualitative ranking on **2026-10-19**,
used as the default gallery order:

**Astra → Sol → Argon → Opus → DeepSeek → Wonder (Meta) → Qwen → MiMo → Kimi →
Grok → Doubao.**

It is attributed as an author recommendation, not a numerical metric or
human-consensus ranking. Exact model names and the optional rating plan are in
[scoring.md](../docs/scoring.md).

Optional blinded human comparison of the attempt-3 canvases follows
[scoring.md](../docs/scoring.md). Attempt 1 and all three attempts provide
diagnostics, alongside action counts, contact events, and measured resource
usage. Neither a subjective recommendation nor future human ratings require
discarding difficult or unsuccessful-looking outcomes.

A result should connect exact inputs, effective config, runtime/agent revisions,
ordered actions/results, recovery ledger, and canvas hashes. A trajectory export
can contain a limited history window: a 24-step export establishes neither a
24-step agent memory nor a complete action chain. Complete action records take
priority for replay.

| Evidence claim | What must support it |
| --- | --- |
| Three attempts completed | Runner/end-state evidence and mapped final canvases |
| Action chain reconstructed | Ordered action/result reconciliation, including continuation segments |
| Video complete | Episode mapping, encoder status, and successful frame decoding |
| Physical replay passed | Same-runtime replay report stating precisely which steps/attempts were checked |
| Quality scored | Frozen rating manifest and actual judgments |

A readable record or decoded video does not establish full physical replay.
Some existing replay checks cover only attempt 1 and a boundary into attempt 2;
there is no universal full-three-attempt physical replay certification for the
initial collection. Official results use Linux; cross-platform pixel equality
is not promised.

Continuous demonstration videos sample simulation activity, omit model-thinking
waits, and may use human-only cameras. They are not end-to-end latency
measurements or exact reproductions of the model's input images.

## Versions and attribution

Runtime packages and input hashes are pinned in [versions.json](versions.json).
New runs use prepared manifests and actual effective configs. Historical runs
retain their recorded source revisions and recovery segments; never rewrite an
old manifest to match current defaults. Preparation, execution, recording, and
replay use AgentArk's existing tools. See
[runtime installation](../docs/runtime-installation.md),
[submissions](../docs/submissions.md), and [limitations](../docs/limitations.md).

The Golden Gate input is Frank Schulenburg's 2017-06-24 photograph,
[Golden Gate Bridge as seen from Battery East](https://commons.wikimedia.org/wiki/File:Golden_Gate_Bridge_as_seen_from_Battery_East.jpg),
used under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
The complete photograph is resized to 1280 × 800 without cropping. Input SHA-256:
`54c7a2385db7ab9df4e2be820dfd32ede7576fe66d62c69832784599c7b4feb5`.
Visual similarity to an external demonstration's reference does not establish
identical file bytes or experimental conditions.

The transparency approach is informed by [HELM](https://arxiv.org/abs/2211.09110):
document scenarios, adaptations, and multiple outcomes together. The concrete
task and evaluation decisions here are RoboPaintBench's own.
