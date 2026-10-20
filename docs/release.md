# Release and hosting

Use three connected surfaces: **GitHub for the benchmark source and protocol, GitHub Pages for the visual result gallery, and Colab for trying the environment.** Host long videos on Bilibili/YouTube and versioned runtime/data artifacts separately. This static project page needs no application server or new server purchase.

GitHub Pages publishes static HTML/CSS/JavaScript. It cannot host the native Unity Player or keep evaluation sessions running. The [public replay notebook](https://colab.research.google.com/drive/1szVNzToQ0VadlPTB2BymM-sgYNbnAHD_?usp=sharing) starts the Linux Player in a visitor's GPU runtime, replays saved Sol actions and exposes AgentArk's viewer through the link printed in step 7; it needs no model API key. The separate evaluation notebook calls a model provider using the visitor's credentials. Model inference charges and Colab resource policies are independent of the website. [GitHub Pages overview](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)

## Prepare the public release

1. Keep the benchmark protocol, version lock, reproducible inputs and evaluator wrapper in Git. Preserve the distinction between task submission reward, visual quality assessment and observed model behavior.
2. Review the gallery's selected canvases and provenance. Publish only the intended artwork/previews and their attribution. Raw results, request bodies, encoded image dumps, logs, local manifests and credentials remain outside Git.
3. Check the actual access state of the GitHub repository and locked runtime dataset. A notebook link cannot grant private repository or dataset access. The installer supports Hugging Face's normal authentication; run a fresh authorized download check before advertising anonymous access. Its revision/hash lock must stay immutable.
4. Enable GitHub Pages for the repository using the supplied deployment workflow. Check the resulting project URL, relative assets, mobile gallery, notebook link, source links and attribution. A custom domain is optional.
5. Validate one fresh Colab session through installation, rendering, preparation and a small explicitly authorized model evaluation. Archive the exact package freeze and graphics log. The current offline notebook checks are not a substitute for this hosted runtime check.
6. Verify the published links in `benchmarks/results/model-videos.json` and test switching models in the single shared Bilibili player. All 11 Golden Gate recordings are linked. The explanation video and Pelican results are pending on the project page; show their status plainly until integrated.
7. Tag the release and make an archival snapshot if desired. Update the citation with the real release DOI only after an archive exists; do not invent a DOI, paper acceptance or quality ranking.

Public code upload does not authorize evaluation-data/media upload. Review the exact files and destination before changing access or publishing the gallery. A release should preserve the original runs and any recovery segments; staging public copies does not make ignored evidence disposable.

## Keep future results comparable

Accept complete manifests, exact model/provider/effort, case/seed, all attempts, action records, input hashes, runtime versions, output-budget limitations and visual assessment evidence. Separate new standard runs from mechanics variants and arbitrary drawings. Provider model aliases and SDKs can change; record the actual version/date and constraints instead of relying only on a display name.

Keep the 11-model Golden Gate release fixed. Integrate the independent text-goal Pelican evaluation as a second case only after its inputs, settings and complete results are checked. Add a scored leaderboard when an assessment protocol and reviewer evidence are available; a gallery of finished works is useful evidence without pretending that submission reward measures art quality.
