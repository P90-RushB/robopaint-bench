# RoboPaintBench

基于 [AgentArk](https://github.com/P90-RushB/AgentArk) Task107 RobotPainting 的
机器人作画 benchmark，同时支持用户提供参考图片或文字，让大模型操作机械臂作画。
建议公开仓库名为 `robopaint-bench`；当前本地目录名保留 `RobotPainting`。

环境运行、模型调用、工具、上下文压缩、记录和回放均使用 AgentArk。本仓库提供评测
配置、目标文件和离线准备脚本，不实现另一套 harness，不包含 Unity 环境和任务资源包。
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

配置预置 OpenRouter 的 `sol` 与 `argon` 两个模型条目，分别为
`openai/gpt-6.1-sol` / effort `max` 和 `google/gemini-4-argon` / effort `high`。
两者继承同一版 SimpleAgent 默认：262,144-token 上下文、256 张图的阈值、
20,480-token 动作输出预留、32,768-token 独立摘要输出预算；摘要 effort 继承动作。
上下文的其他大小限制也可提前触发压缩，256 张图并非保证全部保留。
工具默认保留最多 512 条可读取记录，支持压缩后重看历史图片。

## 安装与机器设置

使用现有 Python 环境安装 `benchmarks/versions.json` 锁定的 AgentArk 源码，
例如在设置本机 `AGENTARK_SOURCE` 后运行：

```sh
python -m pip install -e "$AGENTARK_SOURCE"
```

AgentArk 提供 Python 依赖。锁定提交现已推送到 AgentArk 远端；另一台机器可拉取
仓库，切换到 `benchmarks/versions.json` 指定的提交后安装。准备脚本会检查版本和默认值。
安装 Linux env **1.0.5**，以及对应平台的 **RobotPainting runtime mod**；
Editor 源码包不等于 runtime mod。Mods 需有原始 `config.yaml.bak`，task store 需有
`RobotPainting/cfg`、`dll`、Addressables 和 `References`。

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
及完整 task 文件哈希；Linux task 包还须匹配仓库锁定的运行文件清单。
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
拒绝覆盖旧输出。测试不调用模型、不启动 Unity。已完成的离线检查见
[配置验收记录](docs/config-validation.md)。

## 已有结果与视频素材

金门大桥的已完成 Sol / Argon 原始记录与六轮剪辑素材见
[保留结果索引](docs/retained-runs.md)。原始数据保留在本机，不随本代码仓库上传或克隆。
