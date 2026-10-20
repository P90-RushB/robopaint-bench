# v0.1 preview validation

This page retains dated checks below; later follow-ups supersede only the presentation or runtime scope they explicitly cover. Media policies and missing-file reports in earlier checkpoints describe those earlier states. The current integrated checkout tracks **69 selected website PNGs** across Golden Gate and Pelican; it requires no external media ZIP for a normal build. Raw records, trajectories, request logs and full videos remain outside Git.

Checked 2026-10-19. This validates the benchmark presentation and onboarding changes, not a new model evaluation or a new full physical replay.

## Passed

- 85 offline unit/integration checks with an existing Python 3.10.12 environment. Coverage includes runtime ZIP integrity, actual AgentArk config loading/merging, unique outputs, model profiles, notebook launch guards, target changes, renderer selection, recovered records, evidence sanitization, optional human review, archive tampering, recommendation coverage and generated document links.
- JavaScript syntax check with `node --check site/app.js`.
- 11 models and 33 final attempt canvases: actual episode associations, action counts, exact canvas/metadata/record hashes and canvas dimensions verified. Grok uses the final 96 / 96 / 47 collection.
- 36 selected site assets verified by size/SHA-256; 8,888,108 uncompressed bytes. Reviewed PNG ancillary fields contain only the reference color profile and recorder aspect information. No source records or private model context are included.
- Static build from local selected assets; separate build from the exact review ZIP without access to a media source directory. No missing media. Source-only builds identify missing media explicitly; normal builds refuse them.
- Browser inspection at the available desktop sidebar width and a 390-pixel iframe viewport. Native controls exercised attempt switching, Grok search, all-three-attempt detail, model/attempt comparison, and actual video playback with time advancing. Resolved image-height and mobile-navigation defects found during inspection.
- Independent review repaired a missing generated runtime-installation document and persistent per-model/attempt video-link maintenance.
- Independent onboarding review repaired stale custom-target launch, inherited software-renderer conflicts and inherited automatic-Xvfb flags. Tests exercise the pinned display configuration path without starting Unity.
- Release-facing content scan found no local drive/user paths, encoded observation payloads or credential patterns. Generated media and preview outputs remain ignored by Git.

The site-build checks were rerun after adding embedded public metadata for opening an assembled page directly from its output directory. No additional model calls, downloads, Unity runs, or remote publication occurred.

## Local-only review artifacts

- `local_save/benchmark-preview/index.html`: complete assembled static preview, with its adjacent assets/documents.
- `local_save/benchmark_release/site-media-v0.1-preview.zip`: exact 36-asset review selection, archive SHA-256 `ca8fa1e1b9b3b48cbd7b31800fa48c164f3027f6f64aa4787e7673c2ee10b61a`.
- `local_save/benchmark_release/site-media-v0.1-preview.manifest.json`: selected paths, sizes, archive hash and no-publication receipt.
- `local_save/benchmark_release/screenshots/`: rendered inspection images.

These are local evidence, **unavailable in a fresh clone** until separately authorized media is restored. Git contains the source and portable metadata, not the preview imagery.

## Pending or deliberately outside this check

No numerical quality rating, new model inference, new full three-attempt physical replay, fresh hosted Colab run, anonymous runtime-download acceptance, GitHub push, Pages deployment or media upload is claimed. Existing per-model replay and video-decode receipts are reported only within their historical scope in the result metadata.

The optional anonymous review HTML was generated from actual data and tested offline. Browser automation rejected its `file://` opening because that surface permits only HTTP/HTTPS; it was not bypassed, and rendered QA for that optional tool remains unverified. This does not affect the separately verified main project site.

Pelican results, full hosted process videos and the narrated explainer remain pending inputs. The code/documentation license is Apache-2.0; public licensing/release of the selected evaluation media is still an owner decision.

## Presentation follow-up, 2026-10-19

The owner supplied the personal ranking Astra, Sol, Argon, Opus, DeepSeek, Wonder (Meta), Qwen, MiMo, Kimi, Grok, Doubao. The gallery now defaults to that exact order with #1–#11 and explicit author attribution. Browser inspection verified all eleven positions and the selected default. The reference is a full-width image card above the sample output, with an original-size link. The robot recording section now precedes the side-by-side comparison. Five targeted site-build checks and JavaScript syntax validation passed; no new environment/model run was needed. Updated screenshots are local-only under `local_save/benchmark_release/screenshots/home-ranked.png` and `results-ranked.png`.

The subsequent harness clarification identifies all eleven runs as using AgentArk's built-in SimpleAgent. Display labels now read Codex SDK, OpenRouter and Volcengine Ark, with the shared harness separated from model access in both the site and portable metadata. Browser inspection of the expanded model settings confirmed the shared-harness explanation and all eleven rows in the author's ranking order, with an explicit rank column. Ten public-metadata checks and five site-build checks passed. Model/effort/output-limit evidence was preserved; no evaluation or media source was modified. The updated inspection screenshot is local-only at `local_save/benchmark_release/screenshots/settings-simpleagent.png`.

The in-context learning clarification presents the three runtime attempts as sequential ICL rounds within one continuous agent session. The hero, gallery controls, comparison and detail dialog explain fresh canvases, experience carried through context/memory, and fixed model weights. Runtime attempt IDs and evidence paths remain unchanged. Browser inspection verified Round 1/3 switching, the default author ranking, the three-round detail captions, and the explainer/controls at a 390-pixel iframe viewport. Ten public-metadata checks, five site-build checks and JavaScript syntax validation passed. This describes the evaluation protocol; it does not claim measured or guaranteed improvement across rounds. Local-only inspection screenshots are `local_save/benchmark_release/screenshots/icl-rounds.png` and `icl-dialog.png`.

## Hosted Colab follow-up, 2026-10-20

The separate [hosted Colab validation report](colab-validation-20261020.md) records the subsequent real-runtime installation, verified NVIDIA rendering, normal notebook/browser interaction, record replay and optional video checks. Its dated evidence supersedes the earlier Colab exclusions only within the scope stated there. Use the new [recording/replay notebook guide](colab-record.md) for that workflow; this follow-up does not add model inference or artistic-quality ratings.

## Source checkpoint, 2026-10-20

All 117 existing unit/integration checks passed with the existing Python 3.10.12 environment before this source checkpoint. The current site build verifies 37 selected media assets, all 11 model recording links and all 33 round-end canvases. Its GitHub Pages workflow remains manual; pushing this checkpoint does not deploy the page or upload raw evidence.

The current opening hero shows Astra’s final ICL Round 3 three-camera recording frame, with reference and saved canvas below. Desktop and mobile layouts were inspected, including image loading/order and horizontal overflow. The human-only brush-follow view is explicitly distinguished from the two model-facing cameras. All 11 recording choices share one Bilibili player; playback and switching were checked. The public Colab button opens the owner-shared notebook and explains T4 GPU, Run all, and opening the step-7 viewer URL. The [hosted execution report](colab-validation-20261020.md) records actual GPU/replay evidence separately.

The standalone replay notebook has empty execution outputs; its three owner-selected preview illustrations and verified eleven-file source archive are intentional notebook presentation/bootstrap assets. Full raw records, request bodies, videos and machine-local outputs are excluded from Git. The website’s selected media is supplied separately through the size/hash-checked media bundle. Pelican results remain a future integration; this checkpoint includes no new model evaluation, numerical quality scoring or automatic site deployment.

## Initial Pelican local integration checkpoint, 2026-10-20

The separate Pelican collection is now integrated: **11 models, 33 final
canvases and 603 recorded environment actions**. The importer verifies the
published results/trajectory sizes and SHA-256, source canvas and metadata
hashes, episode GUIDs, round order, action counts, exact text goal and fixed
physics settings. Its output is an explicit public metadata allowlist; it does
not copy private reasoning contents, HTTP payloads, logs or local paths.

All 134 offline unit/integration checks pass in the existing Python 3.10.12
environment, and `node --check site/app.js` passes. Coverage includes separate
task evidence and ranking contracts, case/model record selection without model
inference, both replay notebooks' fourteen-file source bundles, unsafe archive
and media-tampering refusal, and Pelican-only media transfer. The source bundle
maintenance command is `python scripts/update_colab_sources.py --check`.

Browser inspection verified 11 loaded images in each of the three Pelican
rounds, three-round details, two-model comparison, independent task switching
and hash links, and preservation of the Golden Gate author ordering. Pelican
remains unranked. Its single recording player switches to the correct model
BVID and displays 4× simulated-time speed; Golden Gate stays 6×. The embedded
Bilibili region was blank in the inspected in-app browser, so stream playback
is not claimed. Each selected recording has a direct Bilibili fallback link.

At this earlier checkpoint, this machine had all 33 verified Pelican PNGs but lacked the other machine's
37 selected Golden Gate media files. Its local two-task preview therefore uses
the explicit source-only build flag and reports those missing Golden Gate
files. Normal and publication builds continue to refuse incomplete media;
Golden Gate metadata and original source media were not replaced. A separate
Pelican-only ZIP contains exactly the 33 reviewed PNGs, with no records, videos
or logs. This earlier ZIP handoff requirement is superseded by the repository-media integration below.

The new [Pelican Colab](pelican-results.md#replay-without-inference) was checked
offline; no fresh hosted GPU execution is claimed. This integration made no
model calls, Unity launches, new physical replays, video re-encodes, external
media uploads or Pages deployment. Existing dated evaluation/replay receipts
retain their original scope. Raw evidence and all historical recovery segments
remain intact.

## Upstream Golden Gate repository-media checkpoint, 2026-10-20

The owner requested that required website illustrations travel with the repository. At upstream commit `5a76b71`, the selected Golden Gate website PNGs were versioned under `site/assets/media/`: 33 round-end canvases, the reference photograph and two robot recording stills, totaling 36 images. The obsolete 12-second MP4 excerpt and its page link have been removed from the active site selection; the original local clip and older review archives remain preserved. The 11 complete model videos continue to play from Bilibili.

That Golden Gate checkpoint allowed a fresh checkout to build its complete site directly with `python scripts/build_site.py --output <new-directory>` after installing `requirements-site.txt`. It needs no local evidence catalog or external media ZIP. Size/SHA-256 verification still applies to every selected image. Raw records, full recordings, local validation output and credentials remain excluded.


## Two-task repository-media integration, 2026-10-20

The upstream `5a76b71` snapshot was imported through the reviewed offline ZIP and merged with the independent Pelican integration. The active selected image set now has **69 tracked PNGs**: 36 Golden Gate images (33 canvases, one reference and two robot recording stills) plus 33 Pelican canvases. The old 12-second MP4 is excluded from the active site; original local recordings and earlier archives remain preserved. All selected images are available in the integrated checkout, superseding the earlier report of missing Golden Gate media.

Normal fresh-clone builds use the checked-in results and images; no private catalog or external media ZIP is required. The manual Pages workflow builds from that checkout and no longer takes a media-archive URL or approval phrase. A merge, source push or local preview is not a Pages deployment. Raw records, trajectories, HTTP logs, complete videos, credentials and machine-local output remain excluded from Git.

<!-- MERGE_VALIDATION_RESULTS: replace after the final merged-source test, asset/build and browser checks. Do not reuse an earlier checkpoint's count as the merged-source result. -->
Final merged-source test counts, size/hash-checked image totals and visual checks are pending at this editing checkpoint. No new model inference, Unity execution, physical replay or hosted Pelican Colab execution is claimed by this merge.
