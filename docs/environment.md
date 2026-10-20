# Environment and configuration

RoboPaintBench uses **AgentArk Task 107 · RobotPainting**, a Panda-arm painting simulation. The same task supports reference-image painting, text-only targets and custom paintings.

## Where to run

| Platform | Runtime | How you watch |
| --- | --- | --- |
| **Colab** | Linux native Unity Player in the notebook runtime | Open the printed viewer link for camera images, actions and history |
| **Windows desktop** | Windows Player and RobotPainting mod | Unity environment window; replay also provides a browser viewer |
| **Linux desktop** | Linux Player and RobotPainting mod, using the existing graphics display | Unity environment window; replay also provides a browser viewer |

[Local setup](local-setup.md) uses Python **3.10.0–3.10.12** and the pinned AgentArk package. The installer obtains matching env **1.0.5** and **task-v1** packages. Unity Editor and local model weights are unnecessary.

## Fixed benchmark settings

| Setting | Value | Meaning |
| --- | --- | --- |
| `max_attempts` | `3` | Three sequential ICL rounds in one agent session |
| `max_steps_per_attempt` | `96` | Maximum environment actions per round |
| `group_seed` | `107` | Fixed task seed |
| Observations | Two fixed cameras, `960 × 720` each | Both painting modes retain visual workspace feedback |
| `obs_mode` | `decision` | Observe after an environment action |
| `brush_mode` | `fixed` | Brush attached to the robot flange |
| `pigment_mode` | `infinite` | Paint supply does not deplete |
| `board_mode` | `fixed` | Fixed board placement |
| Control / physics | `120 Hz` / `480 Hz` | Timed robot control and physics stepping |
| `time_scale` | `1` | Normal simulation time |
| `no_graphics` | `false` | Rendering is enabled |

A fresh canvas starts each round. The same SimpleAgent carries experience through its context, summaries and archive; rounds are not independent sessions. A human-only brush-follow camera can be recorded, but is not an extra model observation.

Templates: [Golden Gate](../benchmarks/golden_gate/eval.yaml) · [Pelican](../benchmarks/pelican/eval.yaml). Each prepared run saves its configuration and manifest. See the [full protocol](../benchmarks/protocol.md) for benchmark conditions and model-setting differences.

## Change the painting goal

Use `scripts/prepare_run.py`:

| Goal | Flags |
| --- | --- |
| Text only | `--goal-file my_goal.txt --text-only` |
| One reference and instructions | `--goal-file my_goal.txt --reference-image my_reference.png` |
| Several references | Repeat `--reference-image` in the intended order |

The helper copies inputs, records hashes and marks the custom target. A goal file without `--text-only` retains the selected case's default references. [Examples and input limits](custom-painting.md).

## Explore other mechanics

| Parameter | Choices | Effect |
| --- | --- | --- |
| `brush_mode` | `fixed`, `force_grip` | Fixed attachment or force-based brush gripping |
| `pigment_mode` | `infinite`, `finite` | Unlimited pigment or finite brush loading, drying and redipping |
| `board_mode` | `fixed`, `randomized` | Fixed or randomized board placement |
| `physics_frequency_hz` | `120`, `240`, `480`, `960` | Physics stepping rate |

Finite pigment affects the brush's carried load and later strokes; it does not mean deposited paint on paper dries. Follow [the variant workflow](custom-painting.md#mechanics-variants), use a distinct condition name and record the changed settings.

### Example: force-gripped brush with finite pigment

In a separate experiment checkout, open the chosen `benchmarks/<case>/eval.yaml` and change its existing `env_cfg.env_config_overrides.task_params` entries:

```yaml
brush_mode: force_grip
pigment_mode: finite
board_mode: fixed
physics_frequency_hz: 480
```

Keep the rest of the file. Give `eval.cases[0].case_id` a distinct name, such as `custom-force-grip-finite-seed-107`. Prepare the run normally, inspect the generated `effective_task.preview.yaml`, then execute the printed launch command. Each mechanics variant starts a fresh environment process and is reported separately from the fixed benchmark. The installed Player and task files stay unchanged.

## Rendering and model access

The fixed benchmark uses **Linux GPU rendering**. Desktop runs use the matching platform and `existing-display`; Windows does not need Xvfb. A headless Linux GPU machine needs a configured GPU-connected display. Linux also offers an explicitly labeled `xvfb-software` preview. [Graphics details](quickstart.md#graphics-and-colab).

Every model uses AgentArk's built-in **SimpleAgent**. OpenRouter, Volcengine Ark and Codex SDK supply model access within that harness. Replay uses saved actions and needs no model API key. New paintings use your provider credentials; [model access](quickstart.md#model-access) explains portable profiles and the historical Astra limitation.

[Local setup](local-setup.md) · [Custom painting](custom-painting.md) · [Replay](replay.md)
