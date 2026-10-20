# Reproduce and submit a result

RoboPaintBench reuses AgentArk's evaluator, SimpleAgent, recording, and replay.
Start with [installation](runtime-installation.md), the
[version lock](../benchmarks/versions.json), and the
[protocol](../benchmarks/protocol.md). The initial 11-model collection is a
retrospective release; new runs must describe their actual settings.

## Declare the condition before starting

| Label | Requirements |
| --- | --- |
| Reference-condition run | Unchanged Golden Gate inputs, seed 107, 3 × 96 action budget, observations, action interface, physics, and baseline task settings |
| Inference/agent variant | Reference environment with changed agent, prompts, memory, tools, inference policy, or model-side assistance; disclose differences |
| Environment/input variant | Changed seed, target, observations, physics, brush/grip/pigment/board settings, or attempt/action budget |
| Custom studio | User-selected text/reference collection; excluded from standard Golden Gate comparisons |

Reference-condition runs still need model settings disclosed. They are not
automatically compute-matched. Such a claim requires a shared enforceable budget
and a separate study design. Community entries begin as **submitted, unverified**;
completion, replay verification, author recommendation, and formal quality
scoring are separate statuses.

Declare model settings and the planned session count before running. Freeze
agent/input hashes and retain every session in the declared set. Do not present
only a visually preferred rerun as an ordinary single-run result. Development,
superseded, and repeated runs are welcome when labeled and connected to a full
run ledger.

## Prepare and run

From the repository root, with an existing compatible Python installation and
the machine variables in the installation guide:

```sh
python scripts/prepare_run.py --case golden_gate --model sol
python scripts/run_eval.py --config '<prepared run directory>/eval.yaml'
```

The first step prepares a unique run directory and prints its config path; it
does not run a model. Use that generated config in the second command.
Credentials stay in environment variables. The example alias does not restrict
submissions; select an explicit supported model configuration. Do not overwrite
retained outputs or change a shared installation to prepare an experiment.

Custom targets use existing options:

```sh
python scripts/prepare_run.py --case pelican --model sol --goal-file my_goal.txt --text-only
python scripts/prepare_run.py --case golden_gate --model sol --goal-file my_goal.txt --reference-image reference.png
```

These targets are different conditions even when their starting template is
named `golden_gate` or `pelican`. Repeat `--reference-image` for multiple ordered
images; explain their intended use in the goal text. The completed [official Pelican collection](pelican-results.md) uses exactly
`Paint a pelican riding a bicycle.` without a reference attachment; modified goals
are separate custom submissions.

## Evidence checklist

Preserve these files and their relationships. A final-painting screenshot alone
is insufficient for a verified interactive run.

- Prepared manifest and actual effective task/evaluator/model configs;
  runtime/mod/agent revisions and hashes; date and platform. Include provider
  route/version where exposed, and whether limits were enforced or requested.
- Exact goal/reference hashes and ordered input names; agent/prompt changes;
  declared session count and complete run ledger.
- Complete ordered environment actions/results, session/attempt IDs, end
  reasons, and canvas hashes. Retain the attempt-to-episode mapping rather than
  inferring it from directory counters.
- All three aspect-corrected canvases and original metadata; retain raw textures
  where available without confusing them with display canvases.
- For interruptions, original segments and a recovery ledger describing reason,
  restored state, reconstructed prefix, step/call accounting, and synthesized
  feedback. Prefix reconstruction is not new model action or new inference.
- Measured usage and known/unknown coverage. Optional videos need episode
  mapping, recorder settings, and exact decoding/verification coverage.

A limited-window trajectory is not a complete action record. Physically
rebuilding an action prefix does not restore model context unless native agent
state is also recovered. Preserve output/tool-budget errors rather than silently
skipping them. Changing inference policy during continuation makes a
mixed-setting run.

## Replay and review

Use AgentArk's official `ReplayAgent`:

```sh
python -m agent_ark.ark_eval.run_replay --config replay.yaml
```

Point it to the complete record and matching runtime, inputs, and effective task
config. A pure action record need not package all reference inputs. Write fresh
replay outputs and preserve the original.

State exactly which checks passed: record parsing, ordered-action reconciliation,
first-attempt physical replay, full-session physical replay, canvas comparison,
or video decoding. Give steps/attempts covered and mismatch criteria. Do not
label a partial replay as fully reproduced. Official reference results use Linux;
cross-platform pixel equality is not assumed.

After evidence acceptance, a result can enter the gallery or an attributed author
recommendation. A future formal rating cohort uses [scoring.md](scoring.md).
Successful execution, positive reward, and video completion do not establish a
quality rank.

## Submission packet and publication

The v0.1 submission route is a GitHub issue or pull request with a lightweight
summary and immutable artifact links. There is no hosted automatic submission
service. Supply:

```text
Protocol / condition: version, track, seed, deviations
Run identity: unique session ID, date, model ID, backend, agent revision
Inference: reasoning/thinking settings, limits, tool policy, mid-run changes
Attempts: action counts, end reasons, canvas hashes, episode mapping
Artifacts: immutable manifest/record/canvas links and checksums
Recovery: none, or segment/reconstruction ledger
Verification: exact checks completed and remaining unknowns
Usage: measured totals and coverage; unavailable fields explicit
Rights: permission to publish supplied material and required attribution
```

This is a documented packet format, not a claim of automatic validation.
Maintainers may request missing evidence before marking a submission verified.
Corrections get a new version while retaining earlier records. Adding a model
changes a human-rating cohort rather than silently updating an old score.

Do not commit raw HTTP payloads, credentials, machine-specific configs, or large
image-bearing records to the code repository. Check exports for secrets and
personal information. Release model responses only under applicable terms and
disclose what is public versus available for authorized review. Returned readable
reasoning and encrypted reasoning are different; neither permits a claim of
complete private thought. Publishing code does not itself authorize publishing
evaluation records or media.
