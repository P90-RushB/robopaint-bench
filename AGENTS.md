# RoboPaintBench development safeguards

- Reuse AgentArk's evaluator, SimpleAgent, task loading, recording and replay.
- Preserve completed and historical evaluation artifacts for comparison and
  video production. Do not delete, move, overwrite or treat ignored runs as
  disposable without explicit user authorization. New evaluations need unique
  output directories. Retained Golden Gate runs are indexed in
  `docs/retained-runs.md`; keep recovery segments and referenced audit blobs.
- Keep raw records, HTTP payloads, media, logs, credentials and machine-local
  configurations out of Git. Uploading the code repository does not authorize
  uploading evaluation data. Lightweight provenance/location notes may be tracked.
- Clearly distinguish standard benchmark runs, custom drawings, superseded runs
  and runs made with different harness versions. Submission reward is not an
  artistic-quality score.
