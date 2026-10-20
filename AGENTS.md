# RoboPaintBench development safeguards

- Reuse AgentArk's evaluator, SimpleAgent, task loading, recording and replay.
- Preserve completed and historical evaluation artifacts for comparison and
  video production. Do not delete, move, overwrite or treat ignored runs as
  disposable without explicit user authorization. New evaluations need unique
  output directories. Retained Golden Gate runs are indexed in
  `docs/retained-runs.md`; keep recovery segments and referenced audit blobs.
- Version the curated website PNGs under `site/assets/media/` together with their
  hash/provenance manifests so a fresh clone can build the complete site. The
  current Golden Gate selection is 36 PNGs: 33 canvases, the reference and two
  robot recording frames. Pelican adds 33 selected round-end canvas PNGs, for
  69 versioned website images across the two cases. Full videos are hosted externally; the obsolete local
  12-second excerpt is not part of the website.
- Keep raw records, HTTP payloads, unselected media, full recordings, logs,
  credentials and machine-local configurations out of Git. The owner's approval
  to include selected website images does not authorize publishing other
  evaluation data. Lightweight provenance/location notes may be tracked.
- Clearly distinguish standard benchmark runs, custom drawings, superseded runs
  and runs made with different harness versions. Submission reward is not an
  artistic-quality score.
