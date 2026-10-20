# Pelican: text-only painting results and replay

The fixed target is exactly:

> Paint a pelican riding a bicycle.

No reference image is supplied. The model still receives the same two fixed 960 × 720 workspace cameras and flange feedback. All 11 models use AgentArk SimpleAgent, with seed 107, three connected attempts of at most 96 environment actions each, fixed brush/paper, infinite pigment, 120 Hz control, 480 Hz physics and time scale 1. A fresh canvas starts each attempt while the existing managed context, summaries and archives carry experience forward. Model weights do not change.

The completed independent collection contains **11 models, 33 attempts and 603 actions**. Golden Gate's author ranking is not applied here. Display order and action counts are not quality scores. Submission reward checks the saving/submission workflow, not whether the pelican or bicycle is recognizable.

## Actual historical settings

| Model | Access / reasoning | Actions, attempts 1 / 2 / 3 |
| --- | --- | --- |
| GPT-6.1 Sol | OpenRouter / max | 20 / 14 / 14 |
| Gemini 4 Argon | OpenRouter / high | 18 / 11 / 12 |
| Claude Opus 5.5 | OpenRouter / high | 29 / 9 / 9 |
| Grok 4.7 | OpenRouter / xhigh | 58 / 14 / 15 |
| Meta Muse Wonder | OpenRouter / max | 49 / 17 / 16 |
| DeepSeek V4.1 Flash 1017 | OpenRouter / max | 50 / 15 / 23 |
| Qwen3.8-Max-Prime | OpenRouter / xhigh | 32 / 10 / 10 |
| Kimi K3 | OpenRouter / max | 16 / 9 / 10 |
| MiMo V2.6 Pro | OpenRouter / thinking enabled | 21 / 10 / 6 |
| Doubao Seed 2.1 Pro 260915 | Volcengine Ark / high | 27 / 9 / 9 |
| GPT-6 Astra | Codex SDK / max | 19 / 11 / 11 |

The [portable results](../benchmarks/results/pelican.json) retain exact model IDs, source AgentArk commits, canvases, episode GUIDs, artifact hashes and limitations. These are historical settings, not an equal-compute comparison:

- **Opus:** retained successful execution used **high**, with `tool_choice=auto`, after max-mode failures and context-preserving recovery. Golden Gate's mixed max/high action history must not be substituted for this run.
- **MiMo:** thinking enabled, without an effort selector. The normal 20,480 output budget was temporarily raised to **65,536 for two provider requests** after truncation. This exception is retained in the evidence; it does not silently change the standard template.
- **Doubao:** direct Volcengine Ark, `doubao-seed-2-1-pro-260915`, thinking enabled / high; no OpenRouter substitution.
- **Astra:** SimpleAgent's Codex subscription SDK backend, `gpt-6-astra` / **max**, without an API-equivalent hard output-token cap. Golden Gate used ultra, a different historical setting. The local SDK compatibility adapters are absent from the locked upstream package, so this repository does not advertise an unverified portable `--model astra` evaluation profile. Record replay does not require that transport, subscription login or a model API key.

## Public evidence and coverage

The 11 complete records and 11 trajectories are pinned to dataset `P90-RushB/AgentArk` revision **`b16fb52e866ce6a33c52e287f04bfe4a77964453`**. Each file has a locked size and SHA-256 in the result manifest. No video, HTTP audit log, repeated request history, credentials or machine paths are embedded in this source release.

**Use the results record for replay.** All 603 executed actions are present there. The first-attempt trajectory exports for Claude Opus 5.5, Grok 4.7, Meta Muse Wonder, DeepSeek V4.1 Flash 1017, Qwen3.8-Max-Prime, Doubao Seed 2.1 Pro 260915 retain only their final 24 steps. Later attempts are retained; the result manifest reports each export's actual coverage. A trajectory window is not a complete request history or proof of how much context the agent retained. Public sanitized evidence preserves readable thoughts, actions and execution outcomes; it does not expose or guess encrypted reasoning.

The first nine models were re-recorded through the official Linux GPU replay entry point: all 27 round-end canvases matched their source pixels. Doubao and Astra retain their six native Linux GPU evaluation recordings; no additional physical replay is claimed for those two. All 33 selected native episode videos passed complete MP4 decoding, with frame counts checked against `frames.jsonl` and recorder manifests showing `complete=true`, `truncated=false`, `encoder_exit_code=0`. Episode GUIDs associate records, canvases and selected recordings; folder counters alone do not identify attempts.

These are historical local checks. A new machine or hosted Colab replay is a separate verification. Pixel equality across GPUs, operating systems or differing harness revisions is not promised.

## Videos

The [11 published videos](../benchmarks/results/pelican-videos.json) each contain one model's three attempts, in order, including calibration, failures, recovery and submission actions. They use native overhead, fixed side and pen-follow views. The follow camera is for the audience and was not an extra model observation.

**播放速度：4× / Speed: 4×** means four simulated seconds per playback second, independent of model/network waiting. Captions summarize and translate readable source statements in the first person. Plans are not presented as successful outcomes. Captions remain within their source step; brief explicitly labeled “字幕暂停 / Reading pause” segments support exceptionally short steps. The film is not an end-to-end latency measurement or the model's exact image stream. Golden Gate's published films use 6× and remain a separate collection.

## Replay without inference

[Open the Pelican Colab](https://colab.research.google.com/github/P90-RushB/robopaint-bench/blob/main/notebooks/Pelican_Record_Colab.ipynb), select a T4 GPU, select a source model in step 5 and Run all. Keep `MODE="replay"`. Step 7 prints AgentArk's existing viewer URL. The notebook embeds the same reviewed no-inference source bundle as the Golden Gate notebook and selects **Pelican** records and the text-goal configuration. Its extension was checked offline; it has not been claimed to pass a fresh hosted Pelican GPU execution. The existing [Golden Gate hosted report](colab-validation-20261020.md) retains only its stated scope.

For an installed local Linux GPU runtime, the same helper prepares a new isolated output directory without starting Unity or calling any model:

```sh
# Use the existing compatible environment and paths from install_runtime.py.
python scripts/colab_record.py download-record \
  --case pelican --model sol --destination '<new-input-directory>/sol-results.jsonl'

python scripts/colab_record.py prepare --case pelican --model sol --mode replay \
  --record-path '<new-input-directory>/sol-results.jsonl' \
  --run-dir '<new-pelican-replay-directory>' \
  --env-path "$AGENTARK_ENV_PATH" --mod-path "$AGENTARK_MOD_PATH" \
  --task-store "$AGENTARK_TASK_STORE_PATH" --render-mode existing-display \
  --graphics-api glcore33 --step-delay 0 --no-keep-viewer

python scripts/colab_record.py run --config '<new-pelican-replay-directory>/eval.yaml'
```

Replace `sol` with `argon`, `opus`, `grok`, `wonder`, `deepseek`, `qwen`, `kimi`, `mimo`, `doubao` or `astra` in **both** download and preparation. The helper verifies the selected record's immutable hash again before launching AgentArk's official `agent_ark.ark_eval.run_replay`; there is no second replay or evaluation harness. Fresh destinations preserve all original files. GPU mode keeps `no_graphics: false`; verify the actual Unity `player.log` renderer rather than inferring GPU use from hardware availability.

For optional native motion recording, pass `--record-video --ffmpeg '<existing-absolute-ffmpeg-path>'` to the helper's `run` command. Close the environment normally and perform the [recorder integrity checks](replay.md#continuous-motion-video). `inspect` reports observed evidence but does not claim that MP4s were decoded or a runtime passed.

To prepare a **new model evaluation**, use `python scripts/prepare_run.py --case pelican --model sol` followed by the separately printed `scripts/run_eval.py` command only when inference is intended. Preparation alone is offline. Portable launch profiles and historical actual settings are distinct; recovery must retain the complete original context and physics boundary and must not be simulated by replaying a short trajectory window.
