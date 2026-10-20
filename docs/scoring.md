# Interpreting and rating paintings

The Golden Gate collection can be understood directly through its 33 labeled final
canvases and interaction evidence. Formal visual scoring is optional. No human
quality scores have yet been collected under the plan below, and submission
reward must never be used as a substitute.

The gallery calls the three connected stages **ICL Round 1 → ICL Round 2 →
ICL Round 3**. They form one continuous session with fresh paper and retained
SimpleAgent context, summaries, and archives; model weights stay fixed.
“ICL Round n” maps to runtime `attempt n`, the term retained below for precise
record identification. Round-to-round improvement is not assumed.

Pelican has a separate 33-canvas text-goal collection with its own author's personal ranking, supplied on **2026-10-20**: **Astra → Sol → Argon → Opus → Wonder → MiMo → Qwen → Kimi → DeepSeek → Doubao → Grok**. Its gallery and settings default to that order, retained in [Pelican's ranking metadata](../benchmarks/results/pelican-ranking.json). Neither task has a numerical quality score. The Golden Gate reference-fidelity rubric and ranking below do not automatically apply to Pelican's text-only target. See [Pelican results](pelican-results.md).

## Golden Gate: author-curated recommendations

The benchmark author supplied this **personal qualitative ranking on
2026-10-19**. It is the gallery's default order, labeled **Author recommendation
— qualitative**:

| Order | Model |
| --- | --- |
| 1 | GPT-6 Astra |
| 2 | GPT-6.1 Sol |
| 3 | Gemini 4 Argon |
| 4 | Claude Opus 5.5 |
| 5 | DeepSeek V4.1 Flash1017 |
| 6 | Meta Muse Wonder |
| 7 | Qwen3.8 Max Prime |
| 8 | MiMo V2.6 Pro |
| 9 | Kimi K3 |
| 10 | Grok 4.7 |
| 11 | Doubao Seed2.1 Pro260915 |

This records the author's own assessment, not a numerical metric or a
human-consensus result. Attribution, date, and order are retained in
[`editorial-ranking.json`](../benchmarks/results/editorial-ranking.json).
Future updates should keep that provenance and explain the change.

Use attempt 3 for the main side-by-side comparison, and keep attempts 1–3
available so readers can judge progression. If an earlier attempt informs a
recommendation, state that choice explicitly. A recommendation is subjective
commentary, not a blinded human score, consensus ranking, statistical finding,
or claim about all tasks a model can perform. Ties and broad tiers are acceptable
when fine distinctions are unhelpful. This launch route does not require a
three-rater study.

## Optional study: freeze the rating plan

For a later measured comparison, the primary endpoint is the final saved canvas
of **attempt 3**, even when it is worse than an earlier attempt. Attempt 1 and
the ordered set of all three attempts are diagnostic. Best-of-three must not
replace the primary endpoint.

Before collecting ratings, create a versioned manifest with the protocol
revision, fixed cohort/run IDs, reference and canvas hashes, attempt mapping,
rater instructions, anonymization-map hash, assignment seed, planned rater
count, exclusion rules, and aggregation rule. Timestamp it and record its Git
commit. Preserve changes in a new version with an explanation. This freezes
rating prospectively; the existing model collection remains retrospective.

## Primary study question: pairwise reference fidelity

Show the same reference photograph beside two anonymized attempt-3 canvases.
Use the aspect-corrected saved `canvas.png` for every model; do not mix raw square
textures or camera screenshots into the comparison. Keep image size, complete
boundaries, aspect ratio, and zoom behavior consistent. Do not retouch, crop to
content, remove blank areas, or alter colors.

Give the rater this question:

> Which painting more faithfully reproduces the reference, considering the
> bridge's structure and relative geometry, composition, major scene regions,
> and colors? Judge what is visible on the paper. Allow a simplified brush
> painting; do not prefer an image merely because it has more marks or looks
> more polished.

Responses are **A**, **B**, **tie**, or **cannot judge**. A tie includes two
equally poor reproductions. “Cannot judge” means an unreadable/unavailable image
or another stated obstacle, not a poor painting. A genuinely blank saved canvas
is a valid outcome and may be judged.

For the 11-model cohort there are 55 unordered pairs. Plan at least three human
raters per pair: at least 165 valid judgments for a complete first round. Each
rater judges a pair at most once. Freeze the rater count before collection;
do not keep collecting votes only on close pairs until a preferred order emerges.
Randomize order and A/B position with the frozen seed and approximately balance
each model's left/right exposure.

Raters work independently. Hide model names, providers, filenames, usage, action
counts, earlier attempts, videos, and developer commentary. Recruit people who
have not seen the labeled collection where feasible; record prior exposure and
developer/provider affiliations. The benchmark author can prepare materials but
should not supply one of the independent primary votes. If the actual
arrangement differs, disclose it and label the study as a pilot. A distinct
self-declared rater ID is an identifier, not proof of identity or independence.
Recognizable painting styles can still weaken blinding.

Pairwise human comparison is an established approach, including in
[Chatbot Arena](https://arxiv.org/abs/2403.04132). RoboPaintBench uses a fixed
reference-fidelity question on paintings; it does not inherit Arena's population,
rating scale, or statistical guarantees.

## Aggregation and presentation

Give a win 1 point, tie 0.5, and loss 0. For each opponent compute the model's
mean points over valid votes, then average those opponent means equally:

```text
points(model, opponent) = (wins + 0.5 × ties) / valid votes for that pair
pairwise points (%) = 100 × mean(points(model, opponent)) over all opponents
```

For 11 models, every model has ten opponents; with exactly three valid ratings
per pair, it has 30 judgments. Equal opponent weighting prevents uneven rater
coverage from silently weighting some comparisons more heavily. Publish the
full pairwise counts, wins/ties/losses, abstentions, and valid-vote denominators.
Aggregate individual votes rather than collapsing a pair to a majority winner.
Equal point totals receive equal displayed ranks.

The number is **cohort-relative human comparison points**, not an absolute
percentage of art quality or task success. An added opponent changes the cohort;
it must not silently update the meaning of an old score.

Every pair must reach the frozen valid-vote requirement before the cohort is
called completely scored. Retain “cannot judge” votes and reasons; replace
invalid-image assignments only through the same blinded process. Incomplete
collections may show descriptive vote counts and coverage with score/rank
pending. Do not silently omit an opponent or treat abstention as a tie. A
missing/corrupt canvas is pending, not a synthetic blank or zero. If a smaller
eligible cohort is necessary, name and freeze it before rating.

Report unanimous, majority-agreement, and three-way-disagreement pair counts,
with tie votes explicit. Do not discard disagreement or edit votes after model
identities are revealed. A mapping error receives a versioned correction and
rerating of affected assignments, preserving the earlier release.

Rater votes repeatedly assess the same paintings. They are **not additional
independent robot sessions or target examples**. v0.1 uses descriptive counts;
it does not claim model-generalization confidence intervals, significance stars,
or that nearby positions are meaningfully different. More raters address rating
uncertainty, not rollout variation. A later replicated study needs a frozen
sampling plan and an analysis that respects session dependence.

## Diagnostic rubric

A separate 0–4 ordinal rubric gives context: a pairwise winner can still be a weak
reproduction. Score dimensions separately; do not silently sum them into another
headline metric.

| Dimension | What to inspect |
| --- | --- |
| Target recognizability | Whether marks depict the intended suspension-bridge scene |
| Spatial structure | Tower/deck/cable relationships, perspective, proportions, and placement |
| Scene and color coverage | Arrangement and extent of bridge, water, land, sky, and major colors |
| Mark placement | Whether strokes, boundaries, and regions support rather than obscure the scene |

Apply each dimension's definition using these anchors:

| Rating | Anchor |
| --- | --- |
| 0 | No meaningful evidence: blank or unrelated marks |
| 1 | Isolated relevant marks; major intended content/relationships absent or severely wrong |
| 2 | Partly recognizable/organized content; substantial omissions or distortions |
| 3 | Clearly expressed content/relationships; limited visible errors or omissions |
| 4 | Strong correspondence in this dimension within the brush medium; minor deviations only |

Use separate practice material to explain the rubric and allow questions. Do
not tune anchors on labeled official outcomes or show a named model as the
example of a good painting. Record training instructions. Publish per-dimension
distributions, medians, and ranges plus anonymized raw ratings. Novelty,
photorealism, and personal aesthetic preference are not hidden extra criteria.

Show all three attempts in order. Attempt-1 versus attempt-3 rubric distributions
describe revision within a session; improvement is not assumed and is not causal
proof of a particular learning mechanism. Best-of-three may be displayed only
as explicitly secondary and sensitive to selection.

## Control, resource, and automatic diagnostics

Actions, submitted versus limit-ended attempts, rejected commands, protection
events, and executed waypoint counts may be reported when recoverable. Separate
model calls, summary calls, and archive-tool calls from environment actions.
These are not automatic art-quality penalties. Use records and videos to audit
behavior after primary canvas ratings are locked.

Report tokens and time only when supported by records. Reasoning tokens are
commonly included in output tokens and cache tokens in input tokens; do not add
them twice. Mark missing usage unknown. Subscription access does not provide an
observed per-run API dollar cost. End-to-end latency needs appropriate timing
records: demonstration videos omit model-thinking waits and can use human-only
views.

Pixel similarity, image embeddings, and multimodal judges may be investigated
as secondary metrics with exact versions and implementations. Do not derive a
visual score from reward, use an evaluated model to certify its own result, or
present an unvalidated similarity as calibrated artistic quality.

A measured rating release needs its frozen manifest, anonymized judgments,
rater arrangement and exclusions, source-canvas hashes, full pairwise matrix,
aggregation code/version, and deviations. Release only authorized materials
with required attribution and no credentials or personal rater information.
Until judgments exist, numerical quality scores remain **pending**.
