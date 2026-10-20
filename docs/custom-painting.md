# Give the robot your own painting goal

Custom drawing reuses the same Panda simulation, SimpleAgent, records and replay. Write a UTF-8 goal file, choose a model, then prepare and launch a fresh run. This creates a `custom-…` case ID and records `custom_target: true`; it is separate from the fixed Golden Gate and Pelican benchmarks.

**Start online:** [open the custom-painting Colab](https://colab.research.google.com/github/P90-RushB/robopaint-bench/blob/main/notebooks/RobotPainting_Colab.ipynb), supply your prompt/images and provider credentials, then explicitly enable the prepared run.

**Start locally:** follow [Windows / Linux setup](local-setup.md), then use the commands below. Add `--runtime-platform windows` on Windows; Linux is the default. On a graphics desktop, the Unity environment window lets you watch the model paint. [Environment settings](environment.md).

## Text only

```sh
python scripts/prepare_run.py --case golden_gate --model sol --goal-file my_goal.txt --text-only
```

Example `my_goal.txt`:

```text
Paint a small red lighthouse on a rocky island at sunset.
Use broad shapes and leave space around the lighthouse.
```

The model receives the goal and robot workspace cameras; no reference artwork is attached. A text-only target is still a multimodal interaction task. The fixed Pelican template and its [independent completed results](pelican-results.md) are also available. Replacing that prompt creates a custom condition, not another official Pelican attempt.

## One or several reference images

```sh
python scripts/prepare_run.py --case golden_gate --model doubao --goal-file my_goal.txt --reference-image person.png --reference-image landscape.jpg
```

Images retain their supplied order. Explain it in the goal, for example: “Paint the person in image 1 within the landscape in image 2.” References are attached at the start of each attempt; SimpleAgent's normal context/archive tools handle later access. The script copies inputs and stores their hashes. Use images you may share; third-party image rights also matter when publishing the resulting input bundle.

Use `--text-only` explicitly when removing the default Golden Gate reference. Supplying only `--goal-file` changes the instructions while retaining the selected case's default references. Supplying only `--reference-image` retains that case's default goal.

Accepted inputs:

- Nonempty UTF-8 goal: at most 32 KiB and 8,192 UTF-16 code units, without unsupported control characters.
- Up to 16 static PNG/JPEG images with distinct safe basenames: letters, numbers, dot, dash or underscore, at most 160 characters.
- Each image: at most 16 MiB, 8,192 pixels on either side and 16×1,024×1,024 total pixels.
- All images together: at most 64 MiB and 128 million pixels.

Preparation stays offline; it rejects invalid inputs before launching the environment. Use the printed `run_eval.py` command when ready. The [notebook](../notebooks/RobotPainting_Colab.ipynb) accepts custom text and image uploads with the same checks.

## Mechanics variants

The released task can support other experiments, which must be labeled separately from the fixed benchmark:

| Task parameter | Choices | Meaning |
| --- | --- | --- |
| `brush_mode` | `fixed`, `force_grip` | Fixed pen attachment or a force-based grip |
| `pigment_mode` | `infinite`, `finite` | Infinite supply or finite paint/water loading with brush drying and redipping |
| `board_mode` | `fixed`, `randomized` | Fixed or randomized painting board |
| `physics_frequency_hz` | `120`, `240`, `480`, `960` | Physics stepping frequency |

Finite pigment dries/depletes the brush's carried load and can fade later strokes; this is not a claim that paint already deposited on the paper dries. The benchmark uses `fixed` / `infinite` / `fixed` / `480`.

For a variant, use a separate local checkout and edit the selected `benchmarks/<case>/eval.yaml` template's `env_config_overrides.task_params` before preparation so the manifest/config hash records the change. Give its `eval.cases[0].case_id` a distinct variant name and report the changed configuration. Changes to these mechanics require a fresh environment process. Do not overwrite a historical run, silently edit the locked runtime task, or present variant results as standard benchmark results. Keep attempt limits, image resolution and observation settings explicit when changing them.
