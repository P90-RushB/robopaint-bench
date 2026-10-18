# 保留的金门大桥结果与视频素材

用户于 2026-10-18 要求保留，后续增加模型评测并制作视频。
下列原始目录、续跑段和素材不得作为临时验证文件清理；新增评测使用新的输出目录。
这些是本机数据，GitHub 私有代码仓库不包含原始记录、图像和录像。

## 原始评测目录

以下路径相对于本机 AgentArk-Env checkout 根目录：

| 模型 | 原始目录 | 三轮动作数 |
| --- | --- | --- |
| 最新 GPT-6.1 Sol | `local_save/task_validation/Task107_RobotPainting/20261018_sol_summary_fix_rerun/` | 55 / 44 / 56 |
| Gemini 4 Argon | `local_save/task_validation/Task107_RobotPainting/20261018_openrouter_formal/` | 26 / 21 / 24 |

Sol 的完整标准结果与轨迹为 `linux/sol/results.jsonl` 和 `linux/sol/trajectories.jsonl`；
实际 HTTP 请求/回复、trace 与 blobs 在 `linux/sol/audit/`。摘要和用量报告在
`analysis/final_summary_zh.md`，动作与公开理由保存在 `analysis/sol_audit_analysis.json`。

Argon 必须同时保留 `linux/argon/audit/` 和 `recovery/argon_resume_02/audit/`，
以及恢复校验的相关目录。三轮结果与全部 71 个动作由 `analysis/argon_audit_analysis.json`、
`analysis/argon_actions.md`、`analysis/argon_segment_ledger.json` 和原始 audit 共同保存。
Argon 没有正常终结的完整标准 results/trajectories JSONL；原段 results 仅是一条 error 记录，
不要将它误当成完整推理结果。A2 由原段 6 动作和恢复后的 15 动作组成；恢复视频中的
物理重建不能重复计为新模型动作。

`20261018_openrouter_formal` 中的旧 Sol 已作废，仅作历史证据保留。
当前 Sol 应取另一行的新目录。Argon 摘要预算为旧版 10,000，当前 Sol 为 32,768，
制作对比时保留 harness 差异说明。

## 集中剪辑素材与校验索引

以下路径相对于本机 RobotPainting / RoboPaintBench checkout 根目录：

`local_save/retained_results/golden_gate_20261018/`

- `index.html`：两模型六轮画布和完整三视图录像。
- `editing_assets/<sol|argon>/attempt_<01|02|03>/`：原字节复制的 PNG、MP4、frames、metadata、manifest 和编码验收日志。
- `index.json`：原始目录和六轮素材副本的位置、大小及 SHA-256。
- `source_file_manifest.json`：两个完整原始目录的逐文件大小与 SHA-256。

已核验 42 个媒体/sidecar 文件，副本均与源文件哈希一致；六段视频之前的完整解码验收均通过。
原始目录与集中素材目录均放置 `KEEP_FOR_VIDEO_PRODUCTION.md` 保留标记。
这里只为媒体制作了另一份本地副本，原始推理数据仍原位保留；未做云端或异地备份。
