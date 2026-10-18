# RoboPaintBench protocol

两个基准复用 AgentArk Task107 RobotPainting：`golden_gate` 根据参考照片绘画，
`pelican` 仅根据一句文本目标绘画。目标文件不提供物体坐标、笔画轨迹或具体构图答案。
同一任务也可用于自由绘画；自定义目标及配置属于新的运行条件，不能直接并入这两个基准。

每个模型使用种子 107、3 次同种子尝试，每次最多 96 个环境动作，合计至多 288 个环境动作。
这不是 HTTP 请求上限：一次决策可包含多次模型调用、工作区工具调用及上下文压缩。
跨尝试历史遵循已锁定 Task107 与 AgentArk 的原生语义；最终尝试决定 rollout 结果。

模型在每个决策接收两路固定工作区相机图像，每路 960×720。Golden Gate 参考图作为附件，
只在每次尝试的首步提供；文本案例不附参考图，两路工作区图像仍然提供。
消息为 append-only delta，轨迹保留图片。SimpleAgent 使用原生 assistant content 给出简短解释，
通过 `submit_action` 提交环境动作。压缩可能移出旧图，已发布记录仍可通过工作区工具重新查看。
非法 `submit_action` 会整批拒绝，不执行其中的工具或环境动作；模型收到原生工具错误反馈，
在原有工具轮数、调用数和超时预算内重新提交。持续格式错误或预算耗尽仍作为运行错误记录。
历史图片工具每个决策最多返回 4 张图片。工具结果超过文本或图片传送预算时，会省略整个结果，
在剩余文本预算允许时返回有界错误反馈。调用仍计数；工具操作可能已经执行，不能盲目重试。
调用数、时限、模型轮数和上下文硬上限，以及放不下最小反馈的情况，仍会终止运行。
原生工具模式会在新决策开始时，对超过字符或编码字节硬上限 75% 的工作上下文提前尝试压缩，
为后续工具交换留出空间。硬预算保持不变；受保护输入和摘要预算可能使其只能满足硬上限。
原生工具续轮仍保留其签名前缀，不在续轮中途压缩。该预留不保证任意工具批次都能容纳。
中断后可从最后成功动作继续；保留原始分段记录、实际源码哈希和调用账本，合并为同一次评测。

两个 YAML 均为原生 AgentArk `env_cfg` / `eval` / `models` 配置。
六个模型条目统一采用当前 SimpleAgent 默认上下文与工具预算，省略 `context`、`tools.limits` 及摘要 effort 覆盖；
全字段默认快照和输入 SHA-256 位于 `versions.json`。动作输出预算均为 20,480 tokens，
`temperature: null`、`max_retries: 0`、超时 1800 秒，输出 token 参数为 `max_tokens`。
Sol、Wonder、DeepSeek effort 为 `max`，Argon 和 Opus 为 `high`，Grok 为 `xhigh`；
摘要继承对应动作 effort。各名称对应的模型 ID 见根目录 README。
Sol、Argon、Grok、DeepSeek 的工具选择为 `required`；Opus 因 adaptive thinking 不接受强制工具选择
（HTTP 400）而使用 `auto`。Wonder 实测返回 HTTP 400，Meta provider 只支持 `auto`，
不支持 `none`、`required` 或指定工具名，因此同样使用 `auto`。
旧 Argon 10,000-token 运行属于历史条件，不能作为这一统一协议的结果。
本仓库当前不提供新协议下的模型结果。

`prepare_run.py` 从用户安装的 AgentArk 与任务包准备独立运行目录，解析配置中的路径占位符，
复制目标文件并校验输入图、代码版本和默认预算。运行记录应保存具体任务包哈希、有效配置与模型标识。
本仓库不分发 Unity 环境、任务包、参考图、API key 或机器专属路径。

Golden Gate 输入 `GoldenGateBridge_reference.png` 为 Frank Schulenburg 于 2017-06-24 拍摄的
[Golden Gate Bridge as seen from Battery East](https://commons.wikimedia.org/wiki/File:Golden_Gate_Bridge_as_seen_from_Battery_East.jpg)，
按 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) 使用。
任务提供的 PNG 是全图等比缩小、未裁剪的 1280×800 输入；其精确字节哈希在 `versions.json` 锁定，
不声称其与照片来源页或其他作者发布的文件字节一致。图片当前从已安装任务的 `References` 目录复制到忽略的运行目录，本次不把图片重复放入 Git。

Task107 reward 衡量提交和保存画作的完整性，不是艺术质量分数。
比较应查看保存画布及包含图像的完整轨迹，并另行说明艺术质量评估方法。
