# Run locally · Windows and Linux

Install once, then choose **replay a recording** or **let a model paint your own goal**. A graphics desktop shows the Unity environment window. Replay also provides a browser viewer for camera observations and interaction history.

No Unity Editor or local model weights are required. The fixed benchmark uses Linux GPU rendering; Windows is supported for local exploration and custom runs, with the platform recorded separately.

## 1. Get the code and Python package

Use Git and an activated **Python 3.10.0–3.10.12** environment. Run these commands in Windows PowerShell or a Linux terminal:

```sh
git clone https://github.com/P90-RushB/robopaint-bench.git
cd robopaint-bench
python -m pip install "git+https://github.com/P90-RushB/AgentArk.git@54ab7cb0adf6539419611b536811b9850e429520" huggingface_hub
```

## 2. Install the Player and painting task

Choose your operating system. Each command installs env **1.0.5** and RobotPainting **task-v1** into a new directory next to the checkout.

**Windows · PowerShell**

```powershell
python scripts/install_runtime.py --platform windows --destination ../robopaint-runtime-windows
```

**Linux · terminal**

```sh
python scripts/install_runtime.py --platform linux --destination ../robopaint-runtime-linux
```

**Copy and run the three environment-variable assignments printed by the installer in the same terminal.** They set `AGENTARK_ENV_PATH`, `AGENTARK_MOD_PATH` and `AGENTARK_TASK_STORE_PATH`. Keep this terminal open for the following commands.

The installer downloads matching platform files and verifies sizes and SHA-256 hashes. If the destination already exists, choose a new directory. [Advanced installation details](runtime-installation.md).

### Seeing the environment

- **Windows:** use your normal graphical desktop with working graphics drivers. The packaged Unity Player opens in a window.
- **Linux desktop:** use a terminal with a working graphics `DISPLAY` and graphics drivers. The Player opens on that display.
- **Linux without a desktop:** configure a GPU-connected display first, or use the optional [software preview](quickstart.md#graphics-and-colab). Colab configures its own display in the replay notebook.

Rendering stays enabled (`no_graphics: false`). The native window shows the environment; the browser viewer shows agent observations and history.

## 3A. Replay a published model · no API key

Download a complete action record. This example selects Sol's Golden Gate session:

```sh
python scripts/colab_record.py download-record --case golden_gate --model sol --destination runs/replay-inputs/golden-gate-sol.jsonl
```

Prepare a new replay for your platform:

**Windows**

```powershell
python scripts/colab_record.py prepare --mode replay --case golden_gate --model sol --record-path runs/replay-inputs/golden-gate-sol.jsonl --run-dir runs/replay-golden-gate-sol-01 --runtime-platform windows
```

**Linux desktop**

```sh
python scripts/colab_record.py prepare --mode replay --case golden_gate --model sol --record-path runs/replay-inputs/golden-gate-sol.jsonl --run-dir runs/replay-golden-gate-sol-01 --runtime-platform linux --render-mode existing-display
```

Start the prepared replay on either platform:

```sh
python scripts/colab_record.py run --config runs/replay-golden-gate-sol-01/eval.yaml
```

**Open the `[AgentArk viewer]` URL printed in the terminal**, normally `http://127.0.0.1:18181`. Let Unity finish starting; the viewer then shows camera images, actions and results. At the end, the viewer remains available until you press **Ctrl+C** in the terminal.

To choose another recording, use `--case pelican` or change `--model sol` in **both** download and preparation. Available model records are `astra`, `sol`, `argon`, `opus`, `wonder`, `mimo`, `qwen`, `kimi`, `deepseek`, `doubao` and `grok`. Use new input/output paths for each session.

Astra's record replays without Codex login. Public runs were recorded on Linux; a Windows replay does not promise identical pixels across platforms. [Replay details](replay.md).

## 3B. Give a model your own painting goal

Create a UTF-8 file named `my_goal.txt`, for example:

```text
Paint a small red lighthouse on a rocky island at sunset.
Use broad shapes and leave space around the lighthouse.
```

Set your model-provider credential in your terminal using your normal secret-management method. The `sol` profile uses `OPENROUTER_API_KEY`; `doubao` uses `ARK_API_KEY`. Replay does not use these credentials.

For a **text-only goal**, prepare the run:

```sh
python scripts/prepare_run.py --case golden_gate --model sol --runtime-platform windows --goal-file my_goal.txt --text-only
```

On Linux, replace `--runtime-platform windows` with `--runtime-platform linux`.

For a **reference image and prompt**, use:

```sh
python scripts/prepare_run.py --case golden_gate --model sol --runtime-platform windows --goal-file my_goal.txt --reference-image my_reference.png
```

**Run the `scripts/run_eval.py --config …` command printed by the preparer.** This starts the environment and model calls. Follow the painting in the desktop environment window and progress in the terminal. Preparation itself makes no model calls.

Use `--text-only` to remove the Golden Gate reference; a goal file alone retains it. Repeat `--reference-image` for multiple ordered images. Inputs are copied into the new run. [Custom-painting guide and Colab option](custom-painting.md).

Other OpenRouter profiles are `argon`, `opus`, `grok`, `wonder`, `deepseek`, `qwen`, `kimi` and `mimo`. Provider availability depends on your account. Fresh Astra inference is not currently a portable profile; this does not affect replay. [Model access details](quickstart.md#model-access).

## 4. Find your outputs

The preparer prints the exact run path. Inside it:

| File or directory | Contains |
| --- | --- |
| `eval.yaml`, `manifest.json` | Run settings and version/input identities |
| `inputs/` | Copied prompt and reference images |
| `paintings/` | Saved canvases and metadata, written when a round is submitted |
| `results.jsonl`, `trajectories.jsonl` | Model-evaluation records and exported history |
| `replay_results.jsonl` | Checks from a replay run |
| `player.log` | Unity startup and rendering information |

The viewer follows replay from the start; saved final canvases appear after submission. Keep the full run directory to inspect or replay a custom session later.

## If something does not start

- **Python version error:** check `python --version`; the pinned package requires Python 3.10 below 3.10.13.
- **Missing paths:** run the installer's three variable assignments again in the current terminal.
- **Download access denied:** sign in to the required GitHub/Hugging Face account if that repository or dataset requires access. A Colab link does not change repository permissions.
- **No Linux window:** check `DISPLAY` and the graphics driver, or use the software preview. Allocating a GPU alone is insufficient.
- **Viewer initially empty:** wait for Unity startup, then refresh the terminal's viewer URL. Final canvases appear after submission.

[Environment settings](environment.md) · [Advanced installation](runtime-installation.md) · [Replay and video recording](replay.md) · [README](../README.md)
