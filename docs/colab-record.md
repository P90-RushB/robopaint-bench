# Golden Gate replay and interaction in Colab

**[Open the public Golden Gate Colab notebook](https://colab.research.google.com/github/P90-RushB/robopaint-bench/blob/main/notebooks/GoldenGate_Record_Colab.ipynb)** to run the native Linux simulator with AgentArk's observation/history viewer. Select any of the **11 published model records** using `RECORD_MODEL` in step 5; the default is **GPT-6.1 Sol**. The alternative `human` mode lets you send actions yourself and save a new record. Neither mode calls a model or needs a model API key. The [notebook source](../notebooks/GoldenGate_Record_Colab.ipynb) is maintained in this repository; saving a copy to Drive is optional.

The separate [evaluation notebook](../notebooks/RobotPainting_Colab.ipynb) prepares new SimpleAgent model evaluations and can incur inference charges after explicit launch. It has a different purpose.

The notebook opens with a complete English quick start. A separate [Chinese guide](colab-record.zh-CN.md) is also available.

Code cells use AgentArk's existing Colab form presentation: instructions and essential controls are visible, while implementation code is hidden behind **Show code**. The opening preview embeds three images in order: the target reference, a three-camera recording frame from Sol's final ICL round, and that round's saved canvas. They are visible before runtime connection and need no external image host.

## Start the notebook

1. Open the [shared Colab notebook](https://colab.research.google.com/github/P90-RushB/robopaint-bench/blob/main/notebooks/GoldenGate_Record_Colab.ipynb). Sign in, select **Runtime → Change runtime type → Python 3 / T4 GPU**, save and connect. GPU allocation depends on your account's available resources. You may save a copy to Drive if you want to keep your changes; alternatively, upload the local `.ipynb` yourself.
2. Keep `SOURCE_MODE="embedded"`, `RENDERER="gpu"`, `MODE="replay"`, `START_SESSION=True` and MP4 recording off. The single-file notebook embeds the reviewed fourteen-file source archive and checks its SHA-256, exact file list and member hashes. No separate source upload, Drive mount or model API key is required.
3. Choose **Runtime → Run all**. Wait for source verification, dependency/runtime installation, GPU setup, record download and automatic launch. The Colab kernel stays unchanged; AgentArk runs in a separate **Python 3.10.12** subprocess environment. The installer verifies pinned env **1.0.5**, RobotPainting **task-v1**, archive sizes and SHA-256 hashes. No Unity Editor is required.
4. **Open the viewer URL printed in step 7, “Open the live viewer.”** This native **`https://…prod.colab.dev/`** link opens the interactive visualization in another tab. Use the same Google account. Wait for **connected**, two workspace camera views, the Golden Gate reference and advancing action history. You can watch the interaction before a round finishes. If startup is still in progress, wait and refresh; inspect startup errors and `session.log` if it does not connect.
5. After camera images appear, rerun **9. Inspect actual evidence and saved canvases** to view the actual Unity NVIDIA renderer. A failed GPU setup stops visibly; choose `cpu` explicitly only if software rendering is acceptable.
6. The published record contains **155 actions across three connected ICL rounds**. You can view its progress before the full replay finishes. One complete T4 replay took about 103 minutes; this is a measured example, not a time guarantee. Save wanted outputs, stop the session and disconnect/delete the runtime when finished. Runtime storage and viewer URLs are temporary.

Advanced source routes remain available: `SOURCE_MODE="upload"` accepts the curated source ZIP plus its trusted hash; `SOURCE_MODE="github"` requires repository access, or an existing authorized checkout can be supplied through `LOCAL_CHECKOUT`. Opening a notebook in Colab does not make a private GitHub repository anonymously cloneable.

You can also pre-upload the source ZIP through Colab's left **Files** sidebar. Copy that file's VM path into `SOURCE_ARCHIVE`, for example `/content/robopaint-colab-source.zip`, keep `SOURCE_MODE="upload"`, and enter the trusted package hash in `SOURCE_ARCHIVE_SHA256` before running cell 1. This uses the same archive verification as the notebook's upload prompt.

Source ZIP packaging, for a maintainer with the reviewed checkout:

```sh
python scripts/package_colab_source.py pack --output '<new-source-archive>.zip'
```

Distribute that archive together with the printed `archive_sha256`. It contains only the fourteen allowlisted source/configuration/metadata files. It does not contain runtime binaries, evaluation records, images, videos, logs or credentials. Runtime and public replay data are downloaded separately from their immutable releases.

## What uses the GPU

| Component | Execution |
| --- | --- |
| Unity camera and scene rendering, `RENDERER="gpu"` | NVIDIA GPU, verified through the actual Player log and rendered camera frames |
| Unity rendering, `RENDERER="cpu"` | Xvfb + Mesa llvmpipe software rendering on the CPU |
| Robot/brush physics and the Python wrapper | CPU |
| Optional MP4 encoder | CPU FFmpeg/libx264, even when Unity renders on the GPU |

Both profiles keep `no_graphics: false` so Unity can create its graphics device and camera observations. GPU mode supplies an **NVIDIA-backed Xorg display with a virtual screen**, selected through `DISPLAY`; a full desktop shell and physical monitor are unnecessary. Unity renders the camera targets on the GPU, and AgentArk captures those images for its viewer. CPU mode supplies its display through Xvfb and uses Mesa software rendering.

`nvidia-smi` proves a GPU was allocated. `glxinfo` proves the tested display's GL renderer. The run's **`player.log`** identifies the renderer actually used by Unity. Look for `Renderer: Tesla T4/PCIe/SSE2`, `Vendor: NVIDIA Corporation` and the OpenGL version; `llvmpipe` or `softpipe` denotes software rendering. The notebook exposes these lines and the saved observations for inspection.

Continuous 1920×1080, 12 fps motion recording is **off by default** to avoid its extra rendering, readback and CPU encoding cost. Set `RECORD_MOTION_VIDEO=True` before preparing/launching if you want it. The AgentArk viewer and action records remain available with MP4 recording off. GPU rendering does not promise faster-than-real-time physics or a fixed completion time.

## Manual interaction and new records

Choose `MODE="human"` before preparation. The same Golden Gate reference, seed and three-round action budget are retained. AgentArk creates its existing `HumanInteractiveAgent`; no API model is constructed. The viewer shows the two workspace cameras, task prompt, action documentation and action/result history. Send a tool call through its action editor, or use the notebook's explicit `SEND_ACTION` cell.

Use the displayed flange pose and tool documentation for `MoveFlange`. `SubmitPainting` saves and ends the current round:

```text
<tool_call>{"name":"SubmitPainting","arguments":{}}</tool_call>
```

Submission reward confirms the mechanical submission/save workflow; it does not assess drawing quality. Human demonstrations are separate from the benchmark's model results.

Inspect the run's `results.jsonl` or `replay_results.jsonl`, `player.log`, `paintings/` and optional `videos/`. Replay executes the saved actions; its contract match checks turn counts, rewards and termination flags. It does not by itself prove a pixel-identical painting. A replay or human record is separate from an MP4.

Use the native viewer from cell 7 to watch drawing. Cell 9 is an optional renderer/submitted-work inspection, not a video recorder or a second live camera viewer. Startup/reset/disable boundaries can save blank paper; these are excluded from the submitted-work gallery using artifact metadata. A legitimately submitted blank canvas remains a submission. A round saves its final canvas when it is submitted or reaches its action limit. Before the first round ends there may be no finished canvas, even though drawing is visible in the viewer. Rerunning cell 9 after a round ends refreshes the gallery without restarting replay. Turning off MP4 recording does not turn off round-end canvas saving.

For MP4s, associate the selected episode with its artwork metadata using `episode_guid`. Startup/reset boundaries can also create recorder directories; directory counts are not the number of benchmark rounds. Check `complete`, `truncated`, encoder exit code and actual decoded frame count. See [replay and recording](replay.md).

Use the notebook's stop cell before preparing another session or switching modes. The viewer deliberately remains available after a completed run and otherwise keeps its port occupied. Download the run directory before disconnecting the Colab runtime; its local storage is temporary.

## CLI validation versus the browser

The official [Colab CLI](https://github.com/googlecolab/google-colab-cli) can allocate a T4 and execute the same helpers. Ordinary notebook use opens the viewer through Colab's `google.colab.kernel.proxyPort` function.

The notebook's **7. Open AgentArk's existing interaction viewer** cell prints that native Colab URL. It is generated for the current runtime and port, remains available with MP4 recording off, and expires when the runtime is released. GPU rendering uses the same URL-generation path.

CLI-to-browser attachment has a reported [upstream issue](https://github.com/googlecolab/google-colab-cli/issues/24): opening a CLI-generated runtime link can allocate a new CPU session instead of attaching to the existing T4. If that happens, do not assume that the webpage and CLI share a VM. Open the notebook through the normal Colab workflow and select its runtime there. This does not change the graphics profile used by the separate CLI session.

The dated [validation report](colab-validation-20261020.md) distinguishes actual GPU execution, notebook/browser checks, action replay and video decoding.

The new [Pelican replay notebook](../notebooks/Pelican_Record_Colab.ipynb) is an independent text-goal entry using the same no-inference helper and source bundle. It supports all 11 locked Pelican records. [Pelican settings, coverage and local replay](pelican-results.md) are separate from the Golden Gate hosted validation above.
