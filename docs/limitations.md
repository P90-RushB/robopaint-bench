# Scope and limitations

RoboPaintBench makes simulated robot-painting behavior visible and replayable.
The release contains separate Golden Gate and Pelican case studies: 11 model configurations per target,
one three-attempt session per configuration and target. It supports inspecting those
outcomes under their recorded conditions. It does not yet establish a general
ranking of embodied intelligence.

## Two goals, dependent attempts

Golden Gate uses one reference image; Pelican uses one fixed text prompt. Each collection uses one seed-dependent setup.
Attempts share experience and support revision; they are not independent trials.
There are no repeated independent sessions per model to estimate run-to-run
reliability. More raters cannot fill that gap. Generalization needs more targets,
setups, and repeated sessions under a prospectively fixed sampling plan.

Pelican is a separate completed collection (33 attempts, 603 actions), with its own author's personal ranking supplied on 2026-10-20. Each task's subjective recommendation applies only to that collection; neither is a numerical score or a human-consensus result.
Custom studio drawings are demonstrations or separate experimental conditions.
Neither silently increases the sample count for the Golden Gate comparison.

## Simulation and interface

The environment simulates a robot, contact, and soft brush while exposing timed
Cartesian flange commands. A task-owned controller supplies lower-level
execution. This probes painting through that interface; it is not a direct
joint-torque policy test, a physical-robot experiment, or a validated estimate of
real-world deployment performance.

Control and visual differences between simulation and hardware can matter.
[SIMPLER](https://arxiv.org/abs/2405.05941) studies the issue using paired
simulation/real-world evaluations. RoboPaintBench has not performed comparable
transfer validation and cannot inherit another simulator's sim-to-real evidence.

The initial condition fixes brush and paper and provides unlimited pigment.
Grip constraints, pigment depletion, and other supported variants may probe
different behavior but are not covered by these results. A poor painting may
reflect perception, planning, contact dynamics, protection behavior, tooling, or
their interaction; the final canvas alone cannot identify the cause.

## Inference settings and collection history

All 11 models, including Astra, use AgentArk's built-in SimpleAgent harness.
The agent loop, action/observation interface, and task budget are common across
models. Codex SDK, OpenRouter, and Volcengine Ark provide model access within
that shared harness. This establishes consistency at the harness and task level.

The collection also retains model-specific inference settings and recovery
history. Opus used mixed reasoning/output settings; MiMo's output budget
increased during continuation; Astra's Codex SDK backend did not enforce an
API-equivalent hard output cap; Grok includes one recorded harness-generated failed action.
These Golden Gate material conditions are described in the [protocol](../benchmarks/protocol.md). Pelican used Opus high, two temporary MiMo 65,536-token requests and Astra Codex SDK max without an equivalent hard output cap. Its exact conditions and trajectory coverage are in the [Pelican notes](pelican-results.md).

Results are not compute-matched or dollar-matched. Provider reasoning labels
are not common units of computation. Model names can identify changing API
services; dates, endpoint settings, and returned version identifiers matter.
Results describe model and inference configurations evaluated through the common
SimpleAgent loop, tools, memory, and context-management mechanism.

Development experiments and superseded launches exist. Choosing the retained
completed sessions was not blinded or preregistered. A prospective rating plan
cannot retroactively remove collection-time choices. New repeated-run studies
should declare run counts and selection rules before inference and retain the
complete run ledger.

## Quality and interpretation

Reward checks submission/saving, not fidelity, artistry, or semantic success. A
saved canvas can be nearly blank. Action count is an interaction measure, not
an art score; fewer actions do not imply an efficient solution without acceptable
quality and comparable timing.

An author recommendation is attributed subjective commentary. Optional human
ratings assess reference fidelity and retain subjectivity; recognizable styles
can weaken blinding. Pairwise points depend on the opponent cohort and are not
absolute art quality. The rubric, underlying votes, and disagreement provide
context. Until votes exist, numerical quality scores are pending. Model judges
or automatic visual metrics need separate validation.

## Evidence coverage

Trajectories vary in history coverage. A short image export does not establish
a short agent memory. Reconstructed records retain their derivation. Readable
actions, decoded videos, and physical replay are separate claims. Some existing
Golden Gate physical replay checks cover only attempt 1 and a boundary into attempt 2; full
three-attempt replay is not universally certified for that collection. Pelican’s nine later replay recordings and the two direct-model native recordings retain their distinct provenance; decoded videos alone do not certify pixel-identical physics.

Some usage records are incomplete. Reasoning/cache fields can overlap
output/input totals, and subscriptions do not expose a measured per-run API
dollar price. Missing data stays unknown. Demonstration videos omit thinking
waits and include human-only cameras, so they do not measure end-to-end latency
or reproduce the model's exact observation stream. Platforms can differ slightly
in physics/rendering; cross-platform pixel equality is not promised.

## Public inputs and broader claims

The photograph and Pelican prompt are public. Training contamination, prior
familiarity, and future benchmark-specific optimization have not been measured.
The model does not receive hidden environment state, but a familiar goal is not
a held-out distribution by itself.

Public robot-painting demonstrations motivated the work. This is an independent
evaluation with its own input lock, task, and interface. It does not establish
an exact reproduction of another demonstration's setup, provider endorsement,
or a causal explanation of model-family performance. Large visible differences
in these sessions motivate further study; they do not alone prove that a
provider is generally capable or incapable of embodied reasoning.
