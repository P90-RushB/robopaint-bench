# Website and hosting decision

Use **a GitHub repository + a GitHub Pages project site + externally hosted videos + a Colab notebook** for the first release. No server purchase is needed for this architecture.

The repository carries the protocol, installation and evaluation entry points, source code, portable result metadata and issue-based submissions. The project site carries the interactive painting gallery, attempt comparisons, settings, and links into those documents. Bilibili/YouTube carry complete recordings and the later narrated video. Colab supplies user-started compute; a static page does not run Unity or hold model credentials.

This separates the public explanation from the compute bill. A hosted multi-user Unity service would require process isolation, graphics resources, admission control, secrets and ongoing operation; add one only if a later user study demonstrates the need.

## Research behind the choice

[EmbodiedBench](https://embodiedbench.github.io/) and [RoboBench](https://robo-bench.github.io/) both use project sites alongside code and research artifacts. They show why a repository alone is a weak visual introduction: a project site can bring examples, methods and results together. These are presentation references, not claims of equivalent task coverage.

[GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages) serves static HTML/CSS/JavaScript from a repository. [Its limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits) include a 1 GB published site and a soft 100 GB/month bandwidth limit. Keep full videos and raw trajectories off the site. GitHub Free supports Pages from public repositories; private-repository availability depends on plan. Research checked 2026-10-19.

The planned project URL, after actual deployment, is `https://p90-rushb.github.io/robopaint-bench/`. This is a deployment target, **not a claim that the site is already live**. A custom domain is optional and can be added later.

## Local preview

Use an existing Python environment. Install the small static-document renderer, assemble the selected media, then build to a new output directory:

```sh
python -m pip install -r requirements-site.txt
python scripts/build_public_results.py --catalog /path/to/model_catalog.json --media-output site/assets/media
python scripts/build_site.py --output local_save/site-preview-01
python -m http.server 8765 --bind 127.0.0.1 --directory local_save/site-preview-01
```

The catalog path is local input, never a tracked configuration. The canvas builder copies and verifies the 33 selected canvases. The separately curated reference, two recording frames and 12-second clip must also match `benchmarks/results/editorial-media.json`; see [release](release.md). The site builder checks exact sizes and SHA-256 and refuses to publish incomplete media accidentally. `--allow-missing-media` is available only for source-only checks. Use a new output directory on each build; existing nonempty directories are protected.

The assembled page embeds its public result metadata, so its `index.html` can also be opened directly from the complete output directory. Keep its adjacent assets and documents together. HTTP is recommended for browser QA and required for an unassembled source page that still fetches metadata. Local preview keeps model requests, native reasoning, HTTP bodies, raw trajectories and machine paths outside the site.

## GitHub Pages deployment

The manual workflow is `.github/workflows/pages.yml`. It is intentionally not triggered by every push: a code upload is not approval to upload evaluation media. Before invoking it:

1. Review the exact selected media archive, its hash, attribution, and output-media licensing.
2. Authorize public release of those selected assets and the site; decide repository visibility separately.
3. Upload the reviewed archive to an approved immutable HTTPS artifact URL. No new data host upload has occurred during local preparation.
4. In repository Settings → Pages choose **GitHub Actions**. Check the account plan if keeping the repository private.
5. Run **Deploy benchmark site**, supply the media URL and the required approval phrase, and inspect the workflow's returned deployment URL.

The workflow verifies every archive member against the tracked media manifests before assembling the site. It never needs raw audits, model keys, or the local resource catalog. All links and assets are relative so `/robopaint-bench/` subpath deployment works.

## Videos and recommendation updates

The 11 published Golden Gate recordings are indexed in `benchmarks/results/model-videos.json`, keyed by exact model ID. Each Bilibili video combines all three sequential ICL rounds from one continuous session, with 6× motion playback and Chinese/English captions. The site uses one shared player and model buttons in the author's ranking order; switching a model replaces the video in that same player. A direct Bilibili link is available if an embedded player is unavailable. The build checks complete model coverage, unique BVIDs and matching canonical HTTPS links, and embeds the small index so the extracted site also works over `file://`. Remote videos are streamed from Bilibili; they are not downloaded into the site bundle.

`benchmarks/results/video-links.json` remains the mapping for **individual-round** links (for example `models.astra["3"]`). The curated results builder writes these into each round's `video_url`; `--video-links` selects another reviewed mapping. Do not label a whole-session video as one round. Keep the source recordings and their episode associations.

The Replay in Colab button opens the [public shared notebook](https://colab.research.google.com/drive/1szVNzToQ0VadlPTB2BymM-sgYNbnAHD_?usp=sharing). Its visible instructions are: select T4 GPU, Run all, then open the viewer URL printed in step 7 to see camera observations and action history. That runtime-specific viewer link is temporary; the permanent project-page link points to the notebook.

The author's personal qualitative ranking, supplied on **2026-10-19**, lives in `benchmarks/results/editorial-ranking.json` and supplies the default gallery order: **Astra → Sol → Argon → Opus → DeepSeek → Wonder (Meta) → Qwen → MiMo → Kimi → Grok → Doubao**. The site validates coverage and identifiers and displays the attribution as an **author recommendation**, separate from numerical metrics or human-consensus ratings. Keep the attribution and date when updating it; tied tiers are supported. Alphabetical sorting remains an alternative view.
