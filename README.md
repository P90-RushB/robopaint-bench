# RoboPaintBench

基于 [AgentArk](https://github.com/P90-RushB/AgentArk) Task107 RobotPainting 的
机器人作画 benchmark，同时支持用户提供参考图片或文字，让大模型操作机械臂作画。
建议公开仓库名为 `robopaint-bench`；当前本地目录名保留 `RobotPainting`。

环境运行、模型调用、工具、上下文压缩、记录和回放均使用 AgentArk。本仓库提供评测
配置、目标文件、运行时下载安装和离线准备脚本，不实现另一套 harness。
Unity Player 与 Task107 runtime mod 单独托管在 Hugging Face，不放进代码仓库。
Colab、结果展示、画质评分与解说视频留待后续补充。

## 两个 benchmark

| 子任务 | 模型得到的目标 | 配置 |
| --- | --- | --- |
| Golden Gate Bridge | 参考照片，每个 attempt 开始附加一次 | [eval.yaml](benchmarks/golden_gate/eval.yaml) |
| Pelican riding a bicycle | `Paint a pelican riding a bicycle.`，不附参考图 | [eval.yaml](benchmarks/pelican/eval.yaml) |

两者始终提供两个固定工作区相机。共同设置为固定笔、固定画板、无限颜料、480 Hz 物理、
120 Hz 控制、time scale 1、3 个同种子 attempt，每次最多 96 个环境动作。
每轮最终画布均保存，内部 reward 只代表提交保存，不是画质得分。
详见[协议](benchmarks/protocol.md)和[版本及默认值快照](benchmarks/versions.json)。

两个 case 均预置以下 OpenRouter 模型条目，用 `--model` 选择名称：

| 名称 | 模型 | effort | tool_choice |
| --- | --- | --- | --- |
| `sol` | `openai/gpt-6.1-sol` | `max` | `required` |
| `argon` | `google/gemini-4-argon` | `high` | `required` |
| `opus` | `anthropic/claude-opus-5.5` | `high` | `auto` |
| `grok` | `x-ai/grok-4.7` | `xhigh` | `required` |
| `wonder` | `meta/muse-wonder` | `max` | `auto` |
| `deepseek` | `deepseek/deepseek-v4.1-flash-1017` | `max` | `required` |
| `qwen` | `qwen/qwen3.8-max-prime` | `xhigh` | `auto` |
| `kimi` | `moonshotai/kimi-k3` | `max` | `required` |
| `mimo` | `xiaomi/mimo-v2.6-pro` | 开启 thinking，无 effort 档位 | `auto` |

Opus 的 adaptive thinking 与强制工具选择不兼容，会返回 HTTP 400，因此使用 `auto`。
Wonder 实测也返回 HTTP 400：Meta provider 只接受 `auto`，不支持 `none`、`required` 或指定工具名。
2026-10-19 核对 [OpenRouter 模型元数据](https://openrouter.ai/api/v1/models)：
Qwen 最高可选 effort 为 `xhigh`，Kimi 为 `max`；MiMo 只公布 reasoning 开关，
因此显式设置 `thinking.type: enabled`、不发送虚构的 effort 档位。
[Qwen endpoint](https://openrouter.ai/api/v1/models/qwen/qwen3.8-max-prime/endpoints)
支持 `auto`、不支持 `required`；
[Kimi](https://openrouter.ai/api/v1/models/moonshotai/kimi-k3/endpoints) 有支持 `required` 的路由；
[MiMo](https://openrouter.ai/api/v1/models/xiaomi/mimo-v2.6-pro/endpoints) 的各 provider
对强制工具支持不同，使用共同支持的 `auto`。未固定 provider，实际路由须保存在运行记录中。
三者均接受图像、支持工具，公布的输出上限足以容纳下面的动作及摘要预算。
轻量能力快照和来源 SHA 见 [模型能力快照](benchmarks/openrouter-model-capabilities-20261019.json)；
这只证明公开参数兼容性，没有执行模型推理探测。
所有条目继承同一版 SimpleAgent 默认：262,144-token 上下文、256 张图的阈值、
20,480-token 动作输出预留、32,768-token 独立摘要输出预算；摘要推理设置继承动作。
上下文的其他大小限制也可提前触发压缩，256 张图并非保证全部保留。
工具默认保留最多 512 条可读取记录，支持压缩后重看历史图片。

## 安装与机器设置

使用已有 Python **3.10.0–3.10.12** 环境。先将本机 `AGENTARK_SOURCE` 设置为要存放
AgentArk Python 源码的新目录，再安装锁定版本：

```sh
git clone https://github.com/P90-RushB/AgentArk.git "$AGENTARK_SOURCE"
git -C "$AGENTARK_SOURCE" checkout 54ab7cb0adf6539419611b536811b9850e429520
python -m pip install -e "$AGENTARK_SOURCE"
```

已有安装的更新步骤见[运行时安装说明](docs/runtime-installation.md#更新已有安装)。

在 RoboPaintBench 根目录运行以下可选安装器，把 `ROBOTPAINTING_INSTALL` 设置为本机
**尚不存在**的安装目录。它下载 env **1.0.5** 和同平台 **Task107 RobotPainting runtime
mod**，核对版本锁中的不可变提交、字节数和 SHA-256，并打印本机环境变量设置命令：

```sh
python -m pip install huggingface_hub
python scripts/install_runtime.py --platform linux --destination "$ROBOTPAINTING_INSTALL"
```

Windows PowerShell 对应命令为：

```powershell
python -m pip install huggingface_hub
python scripts/install_runtime.py --platform windows --destination $env:ROBOTPAINTING_INSTALL
```

安装器沿用本机 Hugging Face 认证/缓存，不创建 Python 环境，不启动 Unity 或模型，
不会覆盖已有安装目录或运行记录。需要仓库权限时先运行 `hf auth login`。
详细目录结构、手动下载、已有 Player 接入和两平台运行步骤见
[运行时安装说明](docs/runtime-installation.md)。Task107 的 ModelScope Editor 源码包
用于 Unity 编辑开发，不能当作这里的 runtime mod。

每台机器分别设置以下环境变量，或把路径传给准备脚本的对应参数：

| 环境变量 | 内容 |
| --- | --- |
| `AGENTARK_ENV_PATH` | 本机 Player 可执行文件的绝对路径 |
| `AGENTARK_MOD_PATH` | Player 目录内的 Mods 模板绝对路径 |
| `AGENTARK_TASK_STORE_PATH` | 可选，包含 `RobotPainting` 的任务存储目录；默认 Mods 下 `all_tasks` |
| `OPENROUTER_API_KEY` | 运行模型时读取的密钥；离线准备不需要 |

不要把密钥写进 YAML 或提交到 Git。正式 benchmark 使用 Linux GPU 渲染；无显示器的
机器仍需配置可渲染的 display，例如本机已有的 Xvfb。DISPLAY、显卡驱动和环境变量
由机器配置决定；`no_graphics: false` 保留相机渲染。Windows 预览可使用对应 Player/mod
并传 `--runtime-platform windows`，不与 Linux 官方结果混报。

## 离线准备，再使用 AgentArk 运行

以下命令只读取配置、检查版本/输入并生成独立运行目录，**不启动 Unity 或模型**：

```sh
python scripts/prepare_run.py --case golden_gate --model sol
python scripts/prepare_run.py --case pelican --model argon
```

每次会生成新的 `runs/<case>/<时间>-<模型>-<随机ID>/`，包括 `eval.yaml`、目标输入副本、
manifest 和有效任务配置预览。模型选择只取这次指定的一项，防止意外把所有条目都运行。
金门大桥原图从已安装 mod 的 `References` 读取并核对哈希，不联网、不修改共享任务包。
文字目标也复制进运行目录，Unity 与 wrapper 读取同一份输入。目标文件在评测期间保持不变。

真正开始评测时，另行执行准备脚本打印的启动命令，将 `<生成的eval.yaml>` 换成实际路径：

```sh
python scripts/run_eval.py --config '<生成的eval.yaml>'
```

这个薄启动脚本清空当前子进程中可能指向模板或 Editor 的 task 路径环境变量，然后
直接调用 AgentArk 原有 `agent_ark.ark_eval.run_api_agent` 入口；评测循环、模型调用和
状态管理均未改写。这样 Unity 会读取自己的私有 Mods 配置。API key、DISPLAY 和
GPU 环境变量保留，父进程/终端的环境变量不变。

运行使用 AgentArk 官方 runtime sandbox，为这次生成独立的可写 Player/Mods，
task store 通过现有机制复用。两台机器分别运行即可；同机并行时可传不同 `--base-port`。
所有生成的输出路径均为绝对路径，正式入口无需依赖当前工作目录。
每个子任务和每次运行使用独立结果文件，避免两个目标在续跑检查时被当成同一项。

预期输出是 `results.jsonl`、包含观测和 SimpleAgent trace 的 `trajectories.jsonl`、
`paintings/` 下各 attempt 的画布与元数据。当前配置不自动录制连续视频。
`manifest.json` 记录准备时的模型、实际默认预算、输入、Player 可执行文件、Mods baseline
及完整 task 文件哈希；两平台 task 包还须匹配各自锁定的运行文件清单。
`effective_task.preview.yaml` 是只读合并预览，实际 Unity 配置仍由
AgentArk 在启动时生成。准备完成不代表评测已执行或画作已保存。
这些运行文件都被 Git 忽略。

## 自定义绘画

用 UTF-8 文本文件说明要画什么，可以选纯文字或一张、多张有顺序的参考图：

```sh
python scripts/prepare_run.py --case pelican --model sol --goal-file my_goal.txt --text-only
python scripts/prepare_run.py --case golden_gate --model sol --goal-file my_goal.txt --reference-image person.png --reference-image background.jpg
```

目标文本遵循 Task107 的 32 KiB / 8192 UTF-16 单位限制，参考图支持 PNG/JPG/JPEG，
最多 16 张，每张最多 16 MiB、边长最多 8192、像素最多 16×1024×1024。
准备脚本将输入复制到独立目录，自动将目标模式设为文字或图像，标记
`custom_target: true` 并更改 case ID。这些画作可以自由查看、记录和回放，作为官方
benchmark 结果发布时需要另行定义目标条件。

更换模型时，在两个 case 的原生 YAML 中增添一致的 `models` 条目，再用 `--model`
选择其 `name`。上下文与工具预算仍继承 SimpleAgent 默认；更新官方协议或默认值时，
同步更新版本快照。`--allow-version-mismatch` 只用于明确标记的非标准 harness 试验。

## 离线检查

```sh
python -m unittest discover -s tests -v
```

检查覆盖两个目标的真实 AgentArk 配置加载与合并、参考图附件、自定义输入、运行隔离和
拒绝覆盖旧输出，以及安装器的 ZIP 校验、安全解包与已有目录保护。
测试不下载运行时、不调用模型、不启动 Unity。已完成的配置离线检查见
[配置验收记录](docs/config-validation.md)。

## 已有结果与视频素材

金门大桥的已完成 Sol / Argon 原始记录与六轮剪辑素材见
[保留结果索引](docs/retained-runs.md)。原始数据保留在本机，不随本代码仓库上传或克隆。
