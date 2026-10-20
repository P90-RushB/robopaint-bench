# Run RoboPaintBench

Start with the [Golden Gate replay / interaction notebook](../notebooks/GoldenGate_Record_Colab.ipynb) to use the simulator without a model API key. It defaults to NVIDIA GPU rendering and replays public saved actions, with an alternative manual interaction mode. See the [Colab guide](colab-record.md) and [dated execution report](colab-validation-20261020.md).

For a new SimpleAgent evaluation, use the separate [evaluation notebook](../notebooks/RobotPainting_Colab.ipynb), or a Linux graphics machine. Its default is **prepare only**, with a software-rendering preview profile; paid model evaluation is outside the hosted replay/interaction check. Installing dependencies and downloading the runtime do not make paid model calls. No Unity Editor or local model weights are required.

## Local installation

Use an existing Python **3.10.0–3.10.12** environment, matching the pinned package constraint. The historical Linux runs used 3.10.20; this is a recorded execution detail, not the installation requirement. Follow [runtime installation](runtime-installation.md) to install the pinned AgentArk commit and Linux env **1.0.5** + RobotPainting **task-v1**. The immutable revision, archive sizes, SHA-256 checks and reference attribution live in [versions.json](../benchmarks/versions.json).

Set `AGENTARK_ENV_PATH`, `AGENTARK_MOD_PATH` and, optionally, `AGENTARK_TASK_STORE_PATH` using the installer output. The Mods template must be inside the Player directory. Do not modify its `config.yaml.bak`; AgentArk materializes a private runtime sandbox for each run.

```sh
python scripts/install_runtime.py --platform linux --destination "$ROBOTPAINTING_INSTALL"
# Apply the three path assignments printed by the installer, then:
python scripts/prepare_run.py --case golden_gate --model sol
```

Preparation checks source/defaults, platform task files, inputs and effective configuration, then creates a unique run directory with `eval.yaml`, `manifest.json`, an effective-config preview and input copies. It starts neither Unity nor the model. Inspect those files before starting the separate launch command printed by the preparer:

```sh
python scripts/run_eval.py --config '<new-run-directory>/eval.yaml'
```

## Model access

Set credentials in the process environment, a secret manager, or the notebook's hidden runtime prompt. Never place keys in YAML, notebook cells, saved output, URLs or commits.

| Profile name | Transport | Runtime credential |
| --- | --- | --- |
| `sol`, `argon`, `opus`, `grok`, `wonder`, `deepseek`, `qwen`, `kimi`, `mimo` | OpenRouter | `OPENROUTER_API_KEY` |
| `doubao` | Volcengine Ark | `ARK_API_KEY` |
| Historical `astra` | Codex subscription SDK | See limitation below |

Use `--model <profile-name>` to select one entry from the case's `eval.yaml`. These are launch profiles; consult the results provenance for historical mixed settings and resumptions. Preparing a profile is not a claim that the provider currently grants your account model access or that a new result reproduces the published drawing.

**Astra:** the historical `gpt-6-astra` / `ultra` run used a verified CLI plus process-local SDK compatibility adapters. The plain pinned AgentArk entry point does not reproduce that complete transport; consequently `--model astra` is not advertised as a portable launch profile. An OpenRouter GPT profile is not a substitute reproduction of the subscription run. A future portable Astra release must publish/review the adapters, pin both `openai-codex` and its CLI, verify subscription login and the actual model/effort, and retain the SDK's lack of an equivalent hard output-token cap. Do not silently map `ultra` to another effort.

## Graphics and Colab

The benchmark runs use Linux GPU rendering with `no_graphics: false` and two 960×720 observation cameras. A configured, working graphics `DISPLAY` is needed; verify the renderer with `glxinfo -B` and retain the Unity Player graphics log. A GPU listed by `nvidia-smi` does not prove that Unity uses it.

The new [record notebook](colab-record.md) configures an NVIDIA Xorg display on a Colab GPU VM and verifies its GL renderer before launch. Inspect Unity's `player.log` as well. For an explicit CPU fallback or the older evaluation notebook:

```sh
python scripts/prepare_run.py --case golden_gate --model sol --render-mode xvfb-software
```

This uses AgentArk's existing Xvfb manager and explicitly requests Mesa software rendering. It is a **preview rendering profile**, recorded as such in the manifest. Install `xvfb`, Mesa/OpenGL runtime libraries and `mesa-utils`. The thin launch wrapper enforces its bounded software-renderer variables in the evaluation process, replacing inherited conflicts while leaving the parent shell unchanged. Existing-display preparation explicitly disables automatic virtual-display startup. Neither preparation nor a preview is evidence of matching benchmark GPU rendering or speed. The notebook also offers an existing-display mode for a machine you have already configured and checks for a non-software GL renderer before paid launch.

Colab runs a native Linux Unity Player behind the notebook. AgentArk's browser viewer displays observations/history and accepts manual actions; it does not expose the Unity Editor. The [record notebook](colab-record.md) opens this viewer through Colab's authenticated port proxy. Colab availability and session lifetimes vary, so save your run directory before a session ends. [Colab resource policy](https://research.google.com/colaboratory/faq.html)

## What a run means

Golden Gate is the reference-image case: seed 107, three attempts, at most 96 environment actions per attempt. Text-only goals still use the same workspace camera observations. Pelican is the planned second case; its independent result set has not yet been integrated. Custom targets and mechanics variants belong in separate tracks. Reward records the task's submission workflow, not painting quality.

Each run is local and may be large. Keep its manifest, inputs, complete records, canvases and logs together. A saved recent-history trajectory can be shorter than the complete action record. Preparation does not upload any data or credentials.
