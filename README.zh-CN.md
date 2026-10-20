# RoboPaintBench · 机器人绘画基准

**大模型能否把绘画目标变成机械臂的真实落笔动作？**

基于 [AgentArk](https://p90-rushb.github.io/agentark-hub/) 的模拟机械臂绘画评测与实验环境。模型通过相机反馈控制 Panda 机械臂，寻找颜料和画纸，规划三维运动并落笔作画。

[**展示网站**](https://robopaintbench.org/) · [**Colab 在线回放**](https://colab.research.google.com/drive/1szVNzToQ0VadlPTB2BymM-sgYNbnAHD_?usp=sharing) · [**本地运行**](docs/local-setup.md) · [**自定义绘画**](docs/custom-painting.md) · [**English**](README.md)

![Astra 完成金门大桥第三轮绘画时的机械臂三视角画面](site/assets/media/astra-round3-complete.png)

*真实录制帧：Astra 完成第 3 轮 ICL 绘画。模型获得两路固定工作区相机，笔尖跟随近景供观众观看。*

## 三种绘画模式

| 模式 | 给模型的目标 | 可以做什么 |
| --- | --- | --- |
| **参考图绘画 · 金门大桥** | 统一参考照片与复现指令。 | 回放已发布的模型记录，或在相同目标上评测模型。 |
| **纯文字绘画 · 鹈鹕骑自行车** | 文字描述，不附参考画作；模型仍通过相机观察工作区。 | 比较不同模型如何把同一句话转化为画面。 |
| **自定义绘画 · 你的目标** | 自己的 prompt、一张或多张参考图，也可组合使用。 | 选择模型，让机械臂画你指定的内容。 |

两个固定目标各包含 **11 模型 × 3 轮连续 ICL**，共 66 张最终画布。每轮换新画纸，前轮经验通过同一 agent 的上下文与记忆保留，模型参数不更新。两个目标分别默认采用作者给出的个人排名。

[展示网站](https://robopaintbench.org/)负责比较画作和观看视频；本仓库负责安装、回放与运行环境。

## 从这里开始

| 你想做什么 | 入口 |
| --- | --- |
| **在线观看模型回放** | [金门大桥 Colab](https://colab.research.google.com/drive/1szVNzToQ0VadlPTB2BymM-sgYNbnAHD_?usp=sharing) · [鹈鹕 Colab](https://colab.research.google.com/github/P90-RushB/robopaint-bench/blob/main/notebooks/Pelican_Record_Colab.ipynb) |
| **在自己的电脑运行** | [Windows / Linux 安装与首次回放](docs/local-setup.md) |
| **让模型画自己的目标** | [自定义 prompt 与参考图](docs/custom-painting.md) · [自定义绘画 Colab](https://colab.research.google.com/github/P90-RushB/robopaint-bench/blob/main/notebooks/RobotPainting_Colab.ipynb) |
| **了解或修改环境配置** | [环境与配置说明](docs/environment.md) |

### 在线：打开 Colab 观看

1. 打开回放 notebook，在 **Runtime → Change runtime type** 选择 **T4 GPU**。
2. 选择要回放的模型 record，点击 **Runtime → Run all**。
3. **打开第 7 步输出的 viewer 网址**，观看相机画面、动作与交互历史。

回放执行已保存的动作，**不需要模型 API Key**。让模型新画一幅画需要自己的模型服务凭据；自定义绘画 notebook 默认先准备配置，由用户显式启用推理。[Colab 中文说明](docs/colab-record.zh-CN.md) · [自定义绘画](docs/custom-painting.md) · [验证范围](docs/validation.md)。

### 本地：Windows 或 Linux

安装对应平台的 Player 与 RobotPainting task 后，可以选择**回放记录**或**启动模型作画**。图形桌面上可直接观看 Unity 环境窗口；回放还提供浏览器内的相机与历史 viewer。不需要 Unity Editor，也无需下载模型权重。

[本地安装指南](docs/local-setup.md)分别提供 Windows PowerShell 和 Linux 命令。Python 版本为 **3.10.0–3.10.12**；安装器下载锁定运行时，并打印当前终端需要设置的路径。

## 环境配置概览

| 配置 | 固定 benchmark 设置 |
| --- | --- |
| 环境与任务 | AgentArk **Task 107 · RobotPainting**；env **1.0.5**、task **task-v1** |
| 轮次与预算 | **3 轮连续 ICL**，每轮最多 **96 个环境动作**；seed **107** |
| 模型观察 | 两路固定 **960 × 720** 工作区相机、末端位姿与动作反馈 |
| 动作 | 每个动作最多 32 个带时间的末端路径点，笔与纸接触产生笔迹 |
| 绘画机制 | 固定笔、固定画板、无限颜料 |
| 仿真时序 | 120 Hz 控制、480 Hz 物理、time scale 1 |
| Agent harness | 所有模型使用 AgentArk 内置的 **SimpleAgent** |

也支持力夹持画笔、有限颜料与干笔/重新蘸取、随机画板、不同物理频率等设置。[配置文档](docs/environment.md)说明如何创建独立实验条件。Codex SDK、OpenRouter 和火山引擎是同一 SimpleAgent 内的模型接入后端；各模型实际推理设置及差异保留在[协议](benchmarks/protocol.md)与结果资料中。提交 reward 表示保存/提交状态，不评价画作质量。

## AgentArk 中的一个任务

RoboPaintBench 专门研究 AgentArk 的 **RobotPainting 这一个 task**。[**AgentArk Hub**](https://p90-rushb.github.io/agentark-hub/)是更广泛的任务入口，可以理解为**大模型的 Steam**：发现环境、运行任务、观察模型如何行动。[AgentArk 源码与 Python 包](https://github.com/P90-RushB/AgentArk)。

## 结果与开发资料

- [金门大桥结果](benchmarks/results/golden_gate.json) · [鹈鹕结果与设置](docs/pelican-results.md) · [作者排名与可选评分](docs/scoring.md)。
- [评测协议](benchmarks/protocol.md) · [版本锁](benchmarks/versions.json) · [进阶回放](docs/replay.md) · [局限](docs/limitations.md)。
- [提交新结果](docs/submissions.md) · [构建与部署展示网页](docs/hosting.md) · [开发验证](docs/validation.md)。

网站所需 69 张精选 PNG 已随仓库提供，完整视频由 B 站播放。代码与文档采用 Apache-2.0；运行时资产和评测图片保留各自条款。参考照片为 Frank Schulenburg 的 CC BY-SA 4.0 作品；灵感来自 [Thijs Simonian 的机器人绘画演示](https://thijs.net/projects/robot-painter)。[来源与许可](docs/attribution.md) · [引用](CITATION.cff)。
