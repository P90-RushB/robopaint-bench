# Website and hosting decision

The public website is **[robopaintbench.org](https://robopaintbench.org/)**. The first release uses **a GitHub repository + GitHub Pages + Cloudflare-managed domain and DNS + externally hosted videos + Colab notebooks**. No server purchase is needed for this architecture.

The repository carries the protocol, installation and evaluation entry points, source code, portable result metadata, curated website PNGs and issue-based submissions. The project site carries the interactive painting gallery, attempt comparisons, settings, and links into those documents. Bilibili/YouTube carry complete recordings and the later narrated video. Colab supplies user-started compute; a static page does not run Unity or hold model credentials.

This separates the public explanation from the compute bill. A hosted multi-user Unity service would require process isolation, graphics resources, admission control, secrets and ongoing operation; add one only if a later user study demonstrates the need.

## Research behind the choice

[EmbodiedBench](https://embodiedbench.github.io/) and [RoboBench](https://robo-bench.github.io/) both use project sites alongside code and research artifacts. They show why a repository alone is a weak visual introduction: a project site can bring examples, methods and results together. These are presentation references, not claims of equivalent task coverage.

[GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages) serves static HTML/CSS/JavaScript from a repository. [Its limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits) include a 1 GB published site and a soft 100 GB/month bandwidth limit. Keep full videos and raw trajectories off the site. GitHub Free supports Pages from public repositories; private-repository availability depends on plan. Research checked 2026-10-19.

`https://robopaintbench.org/` is the primary address used in repository links and sharing metadata. Cloudflare manages registration and DNS; GitHub Pages serves the built site. The default Pages address is `https://p90-rushb.github.io/robopaint-bench/`, which redirects to the configured custom domain after deployment.

## Local preview

Use an existing Python environment. A fresh clone already contains the selected website images. Install the small static-document renderer, then build to a new output directory:

```sh
python -m pip install -r requirements-site.txt
python scripts/build_site.py --output local_save/site-preview-01
python -m http.server 8765 --bind 127.0.0.1 --directory local_save/site-preview-01
```

No private result catalog or separate media ZIP is needed for this build. The selected image set is **69 checked-in PNGs**: Golden Gate's 36 images (33 canvases, one reference photograph and two robot recording frames) plus Pelican's 33 canvases. The site builder checks exact sizes and SHA-256 against the tracked case and editorial manifests and refuses an incomplete build. The obsolete 12-second local MP4 is excluded; complete recordings play through the shared Bilibili player. Use a new output directory on each build; existing nonempty directories are protected. `--allow-missing-media` remains available for source-only checks, and `--media-archive` remains an optional archival input rather than a fresh-clone prerequisite.

Maintainers regenerating Golden Gate metadata can use `build_public_results.py` with their private catalog. Pelican metadata and selected PNGs can be regenerated from four explicit local evidence inputs:

```sh
python scripts/build_pelican_results.py \
  --dataset-manifest '<reviewed-dataset-manifest.json>' \
  --production-models '<reviewed-production-models.json>' \
  --delivery-manifest '<reviewed-delivery-manifest.json>' \
  --publication-status '<reviewed-publication-status.json>' \
  --media-output site/assets/media
```

These are maintainer regeneration steps, not normal build prerequisites. The Pelican builder hashes the published records/trajectories and original canvases, checks episode/attempt mapping and copies only the selected PNGs. It performs no inference, replay, network upload or video export. Keep private evidence and catalog paths out of tracked configuration.

The assembled page embeds its public result metadata, so its `index.html` can also be opened directly from the complete output directory. Keep its adjacent assets and documents together. HTTP is recommended for browser QA and required for an unassembled source page that still fetches metadata. Local preview keeps model requests, native reasoning, HTTP bodies, raw trajectories and machine paths outside the site.

## GitHub Pages deployment

The manual workflow is `.github/workflows/pages.yml`. Pushing a commit does not deploy the site. To publish:

1. Review the selected website images, attribution and repository visibility. The owner has approved including the current selected images in Git; this does not license other evaluation data for publication.
2. In repository Settings → Pages choose **GitHub Actions**. The public repository supports Pages on GitHub Free.
3. Configure **robopaintbench.org** as the Pages custom domain and point its Cloudflare DNS records to GitHub Pages, as described below.
4. Run **Deploy benchmark site** from the Actions tab. It has no media archive or approval-phrase input.
5. Inspect the workflow's returned deployment URL, HTTPS, relative links, shared video player and mobile layout.

The workflow builds directly from the checked-in media and verifies each selected file against the tracked manifests before assembling the site. It never needs raw audits, model keys, a media-archive host or the local resource catalog. Content links and asset paths are relative, so both the custom-domain root and `/robopaint-bench/` subpath previews work. Canonical and social-preview metadata use the primary domain.

### Custom domain and HTTPS

Domain configuration is separate from the repository build:

1. Verify domain ownership in the GitHub account's Pages settings using the supplied DNS TXT record. Add the custom domain to this repository's Pages settings before pointing public DNS at GitHub.
2. In **Cloudflare → robopaintbench.org → DNS → Records**, configure the apex (`@`) with GitHub Pages' published `A` records and, if desired, `AAAA` records. Configure `www` as a `CNAME` to `p90-rushb.github.io`, without the repository name. Set these records to **DNS only** (unproxied), so GitHub validates and serves HTTPS directly. The primary address remains the apex domain.
3. Wait for GitHub's DNS check and TLS certificate, then enable **Enforce HTTPS**. Confirm both the primary URL and `www` resolve correctly and the latter redirects to the primary address. DNS and certificate provisioning can take up to 24 hours.

This site uses a custom GitHub Actions workflow. The custom domain is stored in **Pages settings**; no repository `CNAME` file is required, and Actions-based Pages ignores such a file. Re-running the manual deployment workflow updates the site without changing the domain or DNS settings.

Use the current [GitHub custom-domain instructions and DNS values](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site) and [Cloudflare DNS record guide](https://developers.cloudflare.com/dns/manage-dns-records/how-to/create-dns-records/) when changing hosting. Domain renewal is managed in Cloudflare; it does not deploy new website content.

## Videos and recommendation updates

The two fixed-target choices sit below the opening hero and select independent results, video indexes and replay entrances. Pelican uses `benchmarks/results/pelican-videos.json`, with 11 full three-attempt videos at **4× simulated-time speed** and its own author's personal ranking. Golden Gate remains 6× and retains its separate author recommendation. The checked-in image set covers both case manifests, and the build verifies all 69 selected PNGs.

The 11 published Golden Gate recordings are indexed in `benchmarks/results/model-videos.json`, keyed by exact model ID. Each Bilibili video combines all three sequential ICL rounds from one continuous session, with 6× motion playback and Chinese/English captions. The site uses one shared player and model buttons in the author's ranking order; switching a model replaces the video in that same player. A direct Bilibili link is available if an embedded player is unavailable. The build checks complete model coverage, unique BVIDs and matching canonical HTTPS links, and embeds the small index so the extracted site also works over `file://`. Remote videos are streamed from Bilibili; they are not downloaded into the site bundle.

`benchmarks/results/video-links.json` remains the mapping for **individual-round** links (for example `models.astra["3"]`). The curated results builder writes these into each round's `video_url`; `--video-links` selects another reviewed mapping. Do not label a whole-session video as one round. Keep the source recordings and their episode associations.

The Golden Gate Replay in Colab button opens the [public shared notebook](https://colab.research.google.com/github/P90-RushB/robopaint-bench/blob/main/notebooks/GoldenGate_Record_Colab.ipynb). Its visible instructions are: select T4 GPU, Run all, then open the viewer URL printed in step 7 to see camera observations and action history. That runtime-specific viewer link is temporary; the permanent project-page link points to the notebook.

The author's personal qualitative ranking, supplied on **2026-10-19**, lives in `benchmarks/results/editorial-ranking.json` and supplies the default gallery order: **Astra → Sol → Argon → Opus → DeepSeek → Wonder (Meta) → Qwen → MiMo → Kimi → Grok → Doubao**. The site validates coverage and identifiers and displays the attribution as an **author recommendation**, separate from numerical metrics or human-consensus ratings. Keep the attribution and date when updating it; tied tiers are supported. Alphabetical sorting remains an alternative view.

The Pelican Replay in Colab button opens [Pelican_Record_Colab.ipynb](https://colab.research.google.com/github/P90-RushB/robopaint-bench/blob/main/notebooks/Pelican_Record_Colab.ipynb), which selects one of the 11 Pelican records and the text-only task. It never redirects to the Golden Gate record. This new extension has offline checks; the existing Golden Gate hosted execution report is not a hosted Pelican validation.

## Sync selected images between machines

The selected 69 website PNGs are tracked with the source. A normal Git pull carries both tasks' canvases, the Golden Gate reference and the two recording stills; a separate media ZIP is not required. Build from the checkout and require 69 verified images with no missing media before a complete two-task preview is considered ready.

Optional media-archive commands remain useful for archival or reviewed offline transfer. They do not replace the tracked manifests and are not deployment inputs. Original records, trajectories, HTTP logs, complete videos and machine-local outputs remain outside Git; tracking the curated website PNGs does not authorize adding those other artifacts. A local build or a Git push does not deploy the site.
