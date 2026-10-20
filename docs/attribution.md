# Attribution and asset status

## Inspiration

RoboPaintBench was inspired by [Thijs Simonian's Bot Ross project](https://thijs.net/projects/robot-painter), in which Astra controls an SO-101 arm to paint the Golden Gate Bridge. The creator describes camera feedback and feedback between attempts. RoboPaintBench uses a simulated Panda arm, different mechanics, the AgentArk harness, and its own protocol. The initial collection does not establish equivalence with that real-robot setup.

The reference photograph was visually identified from the demonstration. The creator has not confirmed byte identity of the original attached reference; we therefore do not claim to use the exact same input file.

## Golden Gate photograph

- **Title:** Golden Gate Bridge as seen from Battery East.
- **Photographer:** Frank Schulenburg.
- **Date:** 2017-06-24.
- **Source:** [Wikimedia Commons file page](https://commons.wikimedia.org/wiki/File:Golden_Gate_Bridge_as_seen_from_Battery_East.jpg).
- **License:** [Creative Commons Attribution-ShareAlike 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- **Change:** Full photograph proportionally resized to 1280 × 800, without cropping, and encoded as PNG.
- **Input SHA-256:** `54c7a2385db7ab9df4e2be820dfd32ede7576fe66d62c69832784599c7b4feb5`.

The public page places this attribution beside the reference and links here. Preserve it in redistributed input packages. The photograph's license is independent of the code license.

## Runtime and robot

Runtime downloads retain their own AgentArk and Panda asset notices. The installer retrieves the locked platform-specific package with its bundled notices; this repository is not a replacement for those license files. Editable Unity source is provisioned separately from runtime evaluation.

## Recordings and model-generated paintings

The owner has approved inclusion of the **36 selected website PNGs** in the repository: 33 canvas PNGs, the reference PNG and two robot recording frames. Hash manifests describe the exact selected files. The website streams complete recordings from Bilibili; the obsolete 12-second local excerpt is no longer a site asset. Raw interaction records, unselected media and original full recordings remain outside Git.

The shared player's poster is the unaltered source frame at second 240 of the Astra ICL Round 3 recording. Recordings omit model thinking waits and use a human-only brush-follow camera in addition to workspace views.

The opening hero uses the unaltered original Astra ICL Round 3 completion frame (source frame 6938 at 578.1667 seconds, episode `5905234c869e4bcab0ed9ddb5747aba1`). The page masks only the unused bottom 120-pixel black strip; all three camera views remain unchanged. Its two smaller images are the reference photograph and the saved final canvas from the same round. The brush-follow view is for human viewing, in addition to the two model-facing workspace cameras.

The source replay notebook retains the three owner-selected preview illustrations (reference, Sol final-round camera frame, saved canvas) embedded in Markdown so they can be seen before starting a runtime. Its execution outputs are empty. These presentation illustrations are separate from raw interaction records.

The code's Apache-2.0 license does not assign a license to these evaluation media. Permission to include the selected images in Git does not extend to the complete raw evaluation dataset. The evaluation media have no additional reuse license specified here; the reference photograph retains its separately stated CC BY-SA 4.0 license. Preserve asset notices and provenance when redistributing the site.
