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
实际 HTTP 请求/回复、trace 与 blobs 在 `linux/sol/audit/`；其中重复带图快照已按下述
授权精简映射保存在 `audit/compaction/`。摘要和用量报告在
`analysis/final_summary_zh.md`，动作与公开理由保存在 `analysis/sol_audit_analysis.json`。

Argon 必须同时保留 `linux/argon/audit/` 和 `recovery/argon_resume_02/audit/`，
以及恢复校验的相关目录。三轮结果与全部 71 个动作由 `analysis/argon_audit_analysis.json`、
`analysis/argon_actions.md`、`analysis/argon_segment_ledger.json` 和原始 audit 共同保存。
Argon 原运行没有正常终结的完整标准 results/trajectories JSONL；原段 results 仅是一条 error
记录，不要将它误当成完整推理结果。已从 audit 另存完整 71 步的原生 JSONL，来源与验证
见[Argon record 恢复](argon-record-recovery.md)。恢复阶段未改动原目录；后续授权精简见下文。
A2 由原段 6 动作和
恢复后的 15 动作组成；恢复视频中的物理重建不能重复计为新模型动作。

`20261018_openrouter_formal` 中的旧 Sol 已作废，仅作历史证据保留。
当前 Sol 应取另一行的新目录。Argon 摘要预算为旧版 10,000，当前 Sol 为 32,768，
制作对比时保留 harness 差异说明。

## 集中剪辑素材与校验索引

以下路径相对于本机 RobotPainting / RoboPaintBench checkout 根目录：

`local_save/retained_results/golden_gate_20261018/`

- `index.html`：两模型六轮画布和完整三视图录像。
- `editing_assets/<sol|argon>/attempt_<01|02|03>/`：原字节复制的 PNG、MP4、frames、metadata、manifest 和编码验收日志。
- `index.json`：原始目录和六轮素材副本的位置、大小及 SHA-256。
- `source_file_manifest.json`：精简前两个完整原始目录的逐文件大小与 SHA-256 历史基线。

已核验 42 个媒体/sidecar 文件，副本均与源文件哈希一致；六段视频之前的完整解码验收均通过。
原始目录与集中素材目录均放置 `KEEP_FOR_VIDEO_PRODUCTION.md` 保留标记。
这里只为媒体制作了另一份本地副本。HTTP 原件、record 与媒体仍原位保留；重复带图快照
按下述授权范围精简。未做云端或异地备份。

## 已授权的审计快照精简

2026-10-18 用户批准保留一份完整 HTTP 请求和回复，精简重复带图快照。此次仅涉及
有效 Sol、Argon 原段和 Argon `resume_02` 的三处 audit；旧失败评测不在清理范围内。

共 749 个 `sdk_create_inputs`、`model_completion`、`agent_forward_with_trace_return`
原 gzip 快照被精简。29,706 处图片字面值改为同一 audit 内、经 SHA 和字节相等验证的
完整 HTTP 请求引用；全部非图片内容保留。各 audit 的 `compaction/` 保存精简快照、
逐记录映射、HTTP 索引和验证证据，旁边的 `COMPACTION_APPLIED.json` 说明当前状态。

清理前及删除原快照后，均已验证全部 749 个快照可仅用精简文件及保留的 HTTP
逐字节重建原 JSON；清理后验证没有读取已删除的原快照。
HTTP、原 `index.jsonl`、status、blobs、标准 results/trajectories、所有录像和画布未改，
7,261 个保留文件的 SHA-256 复核通过。原 gzip 包装字节不再另存；旧完整目录清单和
原 index 中被精简文件的路径属于历史基线，不能直接当作当前目录完整性的声明。

清理后的 Linux 回放按用户要求只验证到跨过第一轮：Sol 回放 56 步（55 + 1），
Argon 回放 33 步（26 + 7）。已返回步骤的 attempt、reward、done 和 rollout 均与
原 record 对齐；两个模型首轮的 canvas 和 canvas_raw 均逐像素、逐字节一致。
本次没有重新调用模型，也没有完整复放后两轮。扣除保留的精简文件及本次验证资料，
C 盘相关文件净减少约 6.08 GiB；详细计数和校验结果见下述本地证据目录。

本地清理计划、逐文件操作记录、空间统计和清理后验证位于 AgentArk-Env 的
`local_save/storage_compaction/20261018/`，不随 Git 克隆提供。恢复旧 audit JSON 时需
保留 `compaction/`、对应 HTTP 文件，以及 AgentArk-Env 的
`local_save/storage_compaction/20261018/audit_snapshot_compaction.py` 精简/还原 helper。
