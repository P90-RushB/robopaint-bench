# Hosted Colab validation, 2026-10-20

This check runs the native Linux Player in actual Google Colab runtimes. It is an onboarding/replay check, not a new model evaluation or an artistic-quality score. No model API calls were made.

## Locked inputs and installation

- AgentArk source: `54ab7cb0adf6539419611b536811b9850e429520`.
- Linux env `1.0.5` and Task107 `task-v1`: immutable runtime revision and archive size/SHA-256 checks from `benchmarks/versions.json` passed on a fresh Colab installation.
- Python: separate `3.10.12` subprocess environment; the Colab `3.13.15` kernel was left in place.
- Public Sol record: revision `90520211bee7327482ed71805473618cdaf2d61c`, 17,574,365 bytes, SHA-256 `3189bf011628a6f87c25f910141a5ab0c456ecc7059bb4e52b1364877acdaaaf`. Downloaded bytes matched before launch.
- Reviewed source ZIP: eleven allowlisted source/configuration/metadata files, SHA-256 `e8448c8e06368ecec8850ccf122d85dfe806285ed6ba539c5abecc2262078d41`. It contains no records or media. Source ZIP and runtime downloads are separate artifacts.

## T4 graphics and human-action smoke

The VM was allocated a Tesla T4 with driver `580.82.07`. The benchmark-local helper started NVIDIA Xorg using the libraries already supplied by Colab. The **Unity Player log**, not just `nvidia-smi`, reported:

```text
Forcing GfxDevice: OpenGL Core
Renderer: Tesla T4/PCIe/SSE2
Vendor:   NVIDIA Corporation
Version:  3.3.0 NVIDIA 580.82.07
```

The running Unity process was also checked directly: `no_graphics=false`, `DISPLAY=:100`, NVIDIA GLX, and `-force-glcore33`; neither `-nographics` nor `-batchmode` was present. The Xorg screen was virtual, 1280×720, without a desktop shell or physical monitor. AgentArk's automatic virtual-display option was off because this external NVIDIA Xorg display was already supplied.

Reset produced two nonempty **960×720** workspace images and the **1280×800** reference. The images were downloaded and visually inspected. A manual `MoveFlange` action advanced 121 control ticks / 484 physics steps / 1.008333 simulated seconds and returned a new pose and two post-action images. Three subsequent submissions ended the three rounds. The saved human record reported `status=ok`, four actions and `done_all=true`. The submitted canvases were deliberately blank; this was a mechanics smoke, not a drawing-quality result.

Optional CPU FFmpeg/libx264 recording was enabled for that smoke. The motion episode's complete, nontruncated **1920×1080 / 12 fps** video contained **27 frames**; both frame counting and a complete decode succeeded, with encoder exit code 0. The two later submitted static episodes each decoded all 14 declared frames. These selected episodes were associated through artwork episode GUIDs. Extra startup/reset recorder directories, including transient invalid-boundary captures, were retained and excluded from the selected evidence.

## Browser notebook path

The official CLI runtime-link attachment reproduced [upstream issue #24](https://github.com/googlecolab/google-colab-cli/issues/24): the browser allocated a separate CPU VM. The two VMs were identified separately. No CPU page was presented as the T4 VM.

In the normal Colab webpage, the actual recording-notebook code cells were executed with reviewed ZIP source, a fresh Python/runtime installation, explicit CPU mode and human interaction selected. The uploaded source ZIP matched SHA-256 `e8448c8e06368ecec8850ccf122d85dfe806285ed6ba539c5abecc2262078d41`; its eleven allowlisted source files totalled 125,371 bytes. The official `proxyPort` link opened the existing AgentArk viewer. It connected and displayed the two workspace cameras, the reference, task/tool documentation and the action editor. A browser-submitted `MoveFlange` action returned a new observation through that viewer. Unity's separate CPU log identified `llvmpipe (LLVM 20.1.2, 256 bits)` / Mesa `25.2.8`.

The completed CPU human record reported `status=ok`, four turns, three attempts, `done_all=true`, and `total_reward=3.0`, with recorded duration **1129.5477 seconds**. One movement followed by three submissions exercised the browser action/observation path and ended all three rounds. The submitted canvases were deliberately blank; the reward confirms the mechanical submission workflow, not drawing quality. The local post-action screenshot is `local_save/colab_validation/20261020-golden-gate/colab-viewer-after-action.png` (local-only evidence, unavailable in a fresh clone).

The CPU reset event arrived **197.9000268 seconds** after run start. The first `MoveFlange` requested one simulated second and its observed browser round trip was **140.576627 seconds**, including viewer polling. The T4 reset observation was about 12.19 seconds. These are individual observations from separate runtime profiles and a manual interaction smoke; they do not establish general CPU performance, controlled throughput, or a general GPU speedup.

## Normal webpage T4 and native viewer URL

After archiving and releasing the completed validation runtimes, a fresh T4 was connected through the normal Colab webpage. The authored notebook was uploaded and executed there, using the reviewed eleven-file source ZIP and its trusted SHA-256. Fresh Python, pinned AgentArk, runtime and record installation completed, the NVIDIA Xorg helper succeeded, and the recorded-action replay started without model credentials.

The notebook called `google.colab.kernel.proxyPort(18181)` through `google.colab.output.eval_js` and returned Colab's native `prod.colab.dev` URL. Opening that exact URL in the browser showed **connected**, two actual workspace camera images, the reference image, task/tool documentation, and successive recorded actions and returned poses. No SSH tunnel or custom forwarding service was used. This URL belongs to the live runtime, requires the appropriate Google session, and expires with that runtime; personal Drive and temporary viewer addresses are not embedded in the public notebook.

This separate webpage run's actual Unity log reported `Tesla T4/PCIe/SSE2`, `NVIDIA Corporation`, and `3.3.0 NVIDIA 580.82.07`. Its effective Unity configuration reported `no_graphics=false` and `virtual_display=false`, with the helper supplying the external NVIDIA virtual screen. Local evidence is `native-colab-gpu-notebook-ax.txt` and `native-colab-gpu-viewer.png` under the validation directory. The new webpage demo was left running for the requested live viewer; a second completed 155-action replay is not claimed. The completed full-record evidence below comes from the earlier archived T4 run.

## Record replay and final receipts

The full published Sol record completed in **6194.4366 seconds (about 103 minutes)** with NVIDIA GPU rendering, the original three-round/96-action conditions, no model inference and MP4 recording off. All **155 saved actions** ran across the three sequential rounds: **55 / 44 / 56**.

All five ReplayAgent checks passed: `turns_match`, `score_reward_match`, `total_reward_match`, `rollout_success_match` and `rollout_truncated_match`. These compare turn counts, rewards and termination flags; they are separate from visual reproduction. The result reported `status=ok`, `done_all=true` and `rollout_truncated=false`. The three submitted canvas PNGs also matched their corresponding public Sol SHA-256 hashes exactly. All three downloaded PNGs were independently decoded, compared to the local public images and visually inspected at native size.

| ICL round | Actions | Submitted canvas SHA-256 |
| --- | --- | --- |
| 1 | 55 | `87d90276ee5630494a6e3adcddb6626a9ba81724213bb7b24c45bc1f05a53df7` |
| 2 | 44 | `42bb9add23ea1e66bd7591f2cfb7d51ea1905ff3fa5d0a4ea255aa95c8fb6e19` |
| 3 | 56 | `253a7539c33fcaf7e355c9652c5a5433baacca08c8b67894cf056643224994f9` |

The completed replay result has SHA-256 `f569cfb3f25ecceb071a78d978ae8b7c36b09d17930debbae302be6fa159d21f`. The verified collection profile is `sol-openrouter-max`, model `openai/gpt-6.1-sol`, case `golden-gate-bridge-seed-107`.

The artifact-only receipt reports `full_scope_gpu_framework_match_and_public_canvas_hash_match`. This establishes one completed replay of this fixed record, not a new model evaluation, artistic-quality rating, or general cross-GPU determinism guarantee.

During the long run, CLI `0.6.0` lost its cached runtime-proxy token while the VM and replay process remained active, consistent with [upstream issue #106](https://github.com/googlecolab/google-colab-cli/issues/106). The exact existing assignment and kernel were verified through the official client, and only that local CLI binding was refreshed. The Unity/replay processes were not restarted. This CLI credential incident is separate from the normal notebook's native viewer URL.

## Local evidence and limits

Local artifacts are retained under `local_save/colab_validation/20261020-golden-gate/` and are unavailable in a fresh clone. Runtime logs, raw viewer payloads, action records and generated media stay out of Git. No new evaluation data or media was published by this check.

The canonical completed GPU evidence archive is `gpu-evidence-final-20261020-02.zip`, 8,005,809 bytes, SHA-256 `f72bbde67b6f36a43732b5b7ca8a5798e9eeb646e08c9862fcdaa23f48b2932f`. Its ZIP CRC, all 156 manifest entries and the replay-result hash were checked after download. Three submitted human-video episodes were selected through their artwork GUIDs; the 32 other video files remain diagnostic evidence. The CPU notebook evidence archive is `cpu-notebook-evidence.zip`, SHA-256 `45b0d125d32b5faf56028b5ef2ed01d98171c99550b375174bb4b4f517e0926a`. Both completed validation VMs were released after their evidence was saved.

The evaluation notebook's paid model path was not executed. GPU rendering does not move robot physics or FFmpeg encoding onto the GPU. The notebook defaults to MP4 off and provides explicit CPU fallback. Thirty targeted Colab checks and five site-build checks passed; coverage includes source integrity, process lifecycle, preparation, graphics selection and generated document links.

## Local single-file handoff

The local handoff notebook now embeds the exact reviewed source ZIP identified above, with default `SOURCE_MODE="embedded"`, GPU rendering and automatic no-inference replay launch on **Run all**. Its archive verification and the eleven runtime-source files are unchanged. Start-to-viewer instructions are included in the notebook; a separate [Chinese guide](colab-record.zh-CN.md) is also available. This packaging change was checked by executing the actual embedded bootstrap against the source files, rejecting a modified archive, and rerunning the record/notebook checks; the full hosted-run evidence above remains the original completed replay, rather than a claimed second full run of the repackaged notebook.

## Inspection presentation follow-up

A fresh user-run Colab instance exposed an ambiguous inspection display: cell 9 initially showed startup/reset/disable boundary canvases before the first round had submitted. Those blank files were normal initialization artifacts, not evidence of a failed painting replay. The notebook now treats cell 7's native viewer as the main visualization and cell 9 as optional GPU/submitted-work inspection. Submitted canvases are selected through artifact metadata and sorted by the writer's full UTC timestamp; directory names are not used as round numbers. Actual blank submissions are retained. No extra live viewer, video recorder or model call is introduced by inspection.

The notebook's visible instructions are now English, arranged with standard Colab Markdown headings and AgentArk's existing form display mode. This changes presentation only; the source archive, rendering profile and replay actions remain unchanged.
