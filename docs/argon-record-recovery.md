# Argon 三轮 record 恢复

此次恢复只读取留存 audit，不请求模型，不改变原始运行目录。生成文件在
`local_save/record_recovery/argon_20261018/`，不随 Git 仓库上传。

下文记录首次恢复及验收时的状态。之后用户于 2026-10-18 批准精简重复带图审计快照，
保留完整 HTTP 请求/回复、所有 record 和媒体。精简范围及当前完整性基线见
[保留资料说明](retained-runs.md#已授权的审计快照精简)。已有 export/replay_ready JSONL
包含自足的动作和观测，不依赖被精简的原 audit 文件；从审计重新恢复时应先使用
`audit/compaction/` 映射还原相应 JSON，不能直接用精简前的文件清单核验当前目录。

## 为什么原来没有完整 JSONL

原始运行在第二轮的下一次模型请求遇到 HTTP 413：请求体为 20,105,329 字节，
超过服务商的 20,000,000 字节限制。因此原段 `results.jsonl` 仅有一条错误记录。

续跑 audit 最后一个事件确认第三轮提交成功，但之后没有标准 record 写出、
正常 teardown 或已知的 runner 退出码。审计证据只能将缺口定位到最后一次
`env.step` 返回之后、trajectory 文件打开之前，不能进一步确定具体失败函数。
三个 attempt 画完与完整 record 落盘是不同的验收项，此前漏查了后者。

## 恢复边界

| 来源 | 全局 turn（从 0 开始） | 动作归属 |
| --- | --- | --- |
| `linux/argon/audit` | 0–25 | attempt 1：26 步 |
| 同上 | 26–31 | attempt 2：前 6 步 |
| `recovery/argon_resume_02/audit` 的新推理部分 | 32–46 | attempt 2：后 15 步 |
| 同上 | 47–70 | attempt 3：24 步 |

续跑中的六次物理状态重建不是新决策，已排除。恢复从真实输入、完整动作、
公开解释与环境返回重建，不使用事后动作摘要替代原始动作。两段全部 1,367 个
来源文件与事先留存的 SHA-256 清单一致，全部索引引用及 blob 完整性通过。

原始 API `messages`（包含图像）原样保留。为兼容 AgentArk 人审界面，额外将
明确标记为 Camera 的工作区图像解码成原生 `vis`，参考图片不会成为第三个工作区
相机。自动重置返回包中的前轮 terminal 图不会冒充下一轮初始工作区画面。
未宣称恢复内部原始 observation 字典或原 runner 未保存的内存状态。

## 文件与复核

- `export/RobotPainting_argon_recovered_results.jsonl`：完整恢复结果，保留全部公开 trace。
- `export/RobotPainting_argon_recovered_trajectories.jsonl`：原生 trajectory，完整保留 26 / 21 / 24 步历史。
- `export/recovery_provenance.json`、`verified_source_payloads.json`：来源、变换、逐步对应关系和哈希。
- `validation/source_integrity_after.json`：两棵原始目录全部 7,725 文件、13,750,003,842 字节的只读复核；无新增、缺失或内容变化。
- `replay_ready/RobotPainting_argon_recovered_results.jsonl`：7,164,054 字节，供标准 ReplayAgent 回放。
- `replay_ready/RobotPainting_argon_recovered_trajectories.jsonl`：146,255,771 字节，包含完整三轮历史及图像。
- `replay_ready/validated_record_manifest.json`：上述副本的来源、字段精简清单、文件大小与 SHA-256。

`export` 的结果状态为 `reconstructed`，需用 `replay.status: null` 选取。
这避免把恢复工作当成原始程序正常收尾。

离线复核使用 AgentArk 官方 results/trajectory 加载器及 `ReplayAgent`，
逐一消费 71 个完整动作，检查三轮 terminal 和 280 个工作区图像投影。
恢复工具及测试分别在 `scripts/recover_audit_record.py`、
`tests/test_recover_audit_record.py`；命令拒绝覆盖已有输出：

```sh
python -B scripts/recover_audit_record.py \
  --source-root "$RETAINED_ARGON_RUN" \
  --source-manifest "$RETAINED_SOURCE_MANIFEST" \
  --agentark-root "$AGENTARK_SOURCE" \
  --output-dir "$NEW_RECOVERY_DIR"
```

`prepare_recovered_record.py` 只接受完整 Linux 回放和三轮最终画布验证均通过的报告，
再生成独立回放副本；不会修改 `export`。它保留动作、公开解释、观测及结果，
去掉各步重复嵌入的 `model_requests`，并将显示用 `action_preview` 补全，
使人审能与长动作准确配对。原完整 trace 仍在 `export` 和原始 audit 中。

派生副本使用默认回放筛选所需的 `status: ok`，同时明确保留
`record_reconstruction: true`、`source_run_finalized: false`、`original_exit: null`。
`ok` 仅表示恢复后的 record 已验证，不表示原 runner 正常收尾。使用已配置本机
Player/Mods 的 AgentArk replay YAML 即可，不需要模型 API：

```sh
python -m agent_ark.ark_eval.run_replay \
  --config "$REPLAY_CONFIG" --records "$RECOVERED_RESULTS" --index 0
```

## Linux 实际验收

在 env 1.0.5、相同 Linux Task107 包、seed 107、480 Hz 物理、固定笔、固定画板、
无限颜料、3 × 96 步配置下，通过官方 `run_replay` 完整执行 71 个动作。
使用 GPU 渲染；模型/外部 HTTP 调用被阻断，实际模型调用为 0。

- 官方五项汇总比较全部通过；额外逐步核对 71 步的轮次、reward、done、rollout 状态。
- 三轮在总第 26、47、71 步终止，动作数为 26 / 21 / 24。
- 三轮 `canvas.png` 与 `canvas_raw.png` 共六份图像，均与原评测逐像素一致，PNG 文件 SHA-256 也完全一致。
- 重新录制的三段视频完整解码通过，帧数 3366 / 3165 / 3332 与原录像一致。
- 官方人审构建器成功对齐 71 个动作，读取 280 帧工作区图像。
- 29 项离线测试通过；仅在 RoboPaintBench 添加恢复工具、测试和说明，AgentArk 运行代码与 Task107 资源未改。

对应本地证据为 `validation/run_01/replay_validation.json`、
`validation/canvas_validation.json`、`validation/video_validation.json` 和
`validation/human_review_02/validation.json`。第一次人审校验脚本误传已解码的 PIL
对象，界面实际读取原始 JSON 图像标记；修正校验脚本后完整通过，record 本身未改。
新回放录像在 `validation/run_01/videos/`，通过 manifest 的 `episode_guid` 与
`validation/run_01/canvases/` 中的提交元数据关联；忽略启动时产生的空白片段。

回放副本的 SHA-256：

- results：`818bcb587645551438299f48ecd8ece9e7d49ff14572a789cfc53d2b356354dc`
- trajectories：`a7845817f7dd679cc207161bcf89f82297d38b40ce3bb37db75cb65b58132598`

这些是本地恢复材料，尚未作为远程 record 发布。后续发布仍需检查隐私、
许可及运行版本；代码仓库中的恢复报告不代表原始 audit 已上传。
