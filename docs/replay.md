# Replay and record a painting

Replay uses AgentArk's existing `ReplayAgent` and `run_replay` entry point. It executes saved environment actions without calling a model API. A compatible Unity Player, matching task/configuration, original goal/reference inputs and a complete action record are required.

For the guided Golden Gate example, use [the recording Colab notebook](../notebooks/GoldenGate_Record_Colab.ipynb) and [its guide](colab-record.md). It downloads and verifies the public Sol record, prepares the locked runtime, selects GPU or explicit CPU rendering, and exposes the observation/history viewer. Its human mode saves new manually chosen actions.

## Choose the right record

Use the complete `results.jsonl` or the validated compact replay record. A trajectory export can contain only a recent-history window; its existence does not establish that all actions were retained. Preserve recovery order and the manifest identifying the final record. Do not concatenate arbitrary resumed files: overlapping prefixes can duplicate actions.

For your own prepared run, create a **new external output directory** and generate a replay configuration from its actual `eval.yaml`. The following is a local Python example; replace both input paths and use the same installed AgentArk environment:

```python
from copy import deepcopy
from pathlib import Path
import yaml

run = Path('<original-run-directory>').resolve(strict=True)
out = Path('<new-replay-directory>').resolve()
out.mkdir(parents=True, exist_ok=False)
cfg = yaml.safe_load((run / 'eval.yaml').read_text('utf-8'))
env = deepcopy(cfg['env_cfg'])
env['runtime_sandbox']['pool_root'] = str(out / 'runtime')
env['env_config_overrides']['task_params']['canvas_output_directory'] = str(out / 'paintings')
args = env.setdefault('additional_args', [])
if '-logFile' in args:
    args[args.index('-logFile') + 1] = str(out / 'player.log')
else:
    args.extend(['-logFile', str(out / 'player.log')])
replay = {
    'env_cfg': env,
    'replay': {
        'records_path': str(run / 'results.jsonl'),
        'record_index': 0,
        'use_record_max_attempts': True,
        'step_delay_s': 0,
        'require_match': True,
        'stop_on_error': True,
        'output_path': str(out / 'verification.jsonl'),
        'append': False,
    },
}
(out / 'replay.yaml').write_text(yaml.safe_dump(replay, sort_keys=False), encoding='utf-8')
print(out / 'replay.yaml')
```

This keeps original target inputs intact and writes new runtime/canvas/verification artifacts elsewhere. `record_index` is zero-based; it selects a JSONL record, not an individual environment action. Select the intended model/case if the record file includes multiple evaluations. For moved runs, update input/reference paths to the restored input copies and verify their hashes against the original manifest.

Before launching, clear `AGENTARK_TASK107_CONFIG`, `AGENTARK_TASK107_REFERENCE_DIRECTORY`, `AGENTARK_TASK107_CANVAS_OUTPUT`, `AGENTARK_CANVAS_OUTPUT_DIRECTORY`, `AGENTARK_MOD_PATH` and `AGENT_ARK_MOD_PATH` from the replay process environment after materializing absolute paths in YAML; inherited task path overrides can bypass sandbox-local config/output. Keep `DISPLAY` and required graphics variables. Set `AGENTARK_AUTO_LOAD_DOTENV=0` and `AUTO_LOAD_DOTENV=0` to prevent local `.env` files from restoring stale overrides. Then run:

```sh
python -m agent_ark.ark_eval.run_replay --config '<new-replay-directory>/replay.yaml'
```

AgentArk's [replay example](https://github.com/P90-RushB/AgentArk/blob/54ab7cb0adf6539419611b536811b9850e429520/config/ark_env/replay.example.yaml) documents record filters and optional browser visualization hooks. That viewer displays agent observations and interaction history; it is separate from the Unity desktop and continuous motion recorder.

`require_match` checks the task's replay contract. It does not certify artistic similarity or a byte-identical canvas on another operating system/GPU. Official results use Linux. Any claim of full replay must report all attempts/actions checked; a one-attempt smoke must remain labeled partial.

## Continuous motion video

Task107 includes a recorder for human viewing. Before evaluation or replay, set two process variables:

```sh
export AGENTARK_TASK107_VIDEO_DIR='<new-absolute-video-directory>'
export AGENTARK_FFMPEG='<absolute-path-to-an-existing-ffmpeg>'
```

The video is 1920×1080 at 12 fps, combining overhead, side and pen-follow cameras. Capture occurs during simulated control ticks and omits model-thinking waits. These human cameras are not additional model observations. Video timing therefore must not be used as end-to-end API latency.

Associate video attempts with canvas/record episodes using episode GUIDs, not just directory counters. Check the recorder manifest, `complete`/`truncated` status, encoder exit code and decoded frame count before publishing. Keep the record, inputs and versions for a reproducible motion replay; an MP4 alone is presentation evidence.

The owner has published all 11 Golden Gate process videos on Bilibili. Exact model links are in [model-videos.json](../benchmarks/results/model-videos.json); each video combines that model’s three sequential ICL rounds, at 6× speed with Chinese/English captions. The project page switches them within one player. These whole-session links are distinct from per-round video links. Preserve the local originals; code publication does not authorize automatic upload of raw records or recordings.
