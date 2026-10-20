# RoboPaintBench：机器人绘画基准

**从视觉到落笔。** 基于开源 [AgentArk](https://github.com/P90-RushB/AgentArk) 的模拟机械臂绘画评测，观察大模型如何利用视觉反馈规划三维运动、蘸颜料、画笔画，并利用前轮经验继续作画。

当前为 **v0.1 研究预览**：金门大桥11模型，每个模型3轮上下文学习，共33张最终画布。页面展示所有ICL轮次，支持轮次切换、模型并排比较、完整三轮进程与实际推理设置。鹈鹕骑自行车的纯文字目标结果由另一台机器整理，暂未纳入；自定义绘画入口已有。

**上下文学习（In-context learning）：ICL Round 1 → ICL Round 2 → ICL Round 3。** 每个模型进行一段连续会话：换轮清空画纸，前轮经验通过SimpleAgent的正常上下文、摘要和交互档案保留，供后轮参考。模型参数不更新，是否进步由实际画作体现。“ICL Round n”是展示名称，对应配置和原始记录中的`attempt n`。

**所有11个模型，包括Astra，都使用AgentArk内置的同一套SimpleAgent harness。** 代理循环、动作与观察接口、任务步数和轮次预算保持一致，在harness和任务层面提供统一比较条件。Codex SDK、OpenRouter和Volcengine Ark只负责接入模型；Astra同样由SimpleAgent驱动画画。各模型的实际推理设置单独记录。

页面默认采用作者于 **2026-10-19** 提供的**个人主观排名**：**Astra → Sol → Argon → Opus → DeepSeek → Wonder（Meta）→ Qwen → MiMo → Kimi → Grok → Doubao**。这是署名推荐，不是数值指标或多人共识排名。所有33张画布保留可查看，主比较默认第3轮；后续人工盲评为可选补充。环境的提交reward只代表保存/提交流程，不是画画好坏。

## 入口

- [英文项目说明](README.md)：结果表、协议、版本和全部文档。
- [展示页本地预览与GitHub Pages](docs/hosting.md)：首版不需要购买服务器。
- [打开金门大桥 Colab 回放](https://colab.research.google.com/drive/1szVNzToQ0VadlPTB2BymM-sgYNbnAHD_?usp=sharing)与[中文使用说明](docs/colab-record.zh-CN.md)：默认 GPU 渲染，不需要模型 API Key；全部运行后打开第 7 步输出的 viewer 链接，查看相机画面及动作历史。[Notebook 源文件](notebooks/GoldenGate_Record_Colab.ipynb)也保存在仓库中。
- [首次评测](docs/quickstart.md)与[新模型评测 Colab](notebooks/RobotPainting_Colab.ipynb)：复用 AgentArk 原有评测器，显式启动后才调用模型。
- [任意图片/文字绘画](docs/custom-painting.md)与[回放](docs/replay.md)。
- [基准协议](benchmarks/protocol.md)、[结果呈现和可选人工评分](docs/scoring.md)、[局限](docs/limitations.md)。
- [中文发布与传播方案](docs/launch-plan.zh-CN.md)。

标准条件是同一会话中的3轮连续ICL、每轮最多96环境动作、种子107、两路960×720固定相机、固定笔/纸、无限颜料、120Hz控制/480Hz物理。换轮保留经验，三轮具有依赖关系。金门大桥参考图只在每轮首步附加，后续可从历史档案回看。

录像用的人类笔尖跟随镜头不提供给模型。模型推理等待不会计入录像，所以录像时长不是端到端推理耗时。

Grok最新资料已补完第三轮：96/96/47步；其中一个预算失败是明确记录的harness无移动拒绝步。共同SimpleAgent harness下，Opus混合推理设置、MiMo提高输出预算、Astra的Codex SDK后端输出限制差异已保留。统一任务和代理机制并不代表相同推理消耗，首版不宣称等算力对照。

发布结构为GitHub仓库、GitHub Pages网页、B站/YouTube视频、Colab计算入口。网页源码、元数据及精选网站PNG图片随Git版本管理：当前金门大桥共36张，包括33张画布、1张参考图和2张机械臂录制帧。新克隆仓库安装`requirements-site.txt`后，执行`python scripts/build_site.py --output local_save/site-preview-01`即可构建完整网页，无需另传媒体包或私有结果索引。完整视频由B站播放，旧的12秒本地片段不再纳入网站。原始记录、请求/推理、完整录像、日志和本机输出继续留在Git之外。Notebook 保留用户指定的三张内嵌预览图，供启动前阅读；不包含执行输出或原始 record。图片入库不代表适用代码的Apache-2.0许可，也不授权发布其他评测数据。GitHub Pages仍需手动部署。Colab 回放／交互示例的实际 GPU、网页、动作和录像验证范围见[运行报告](docs/colab-validation-20261020.md)；新模型付费推理另行启动。

参考照片：Frank Schulenburg，CC BY-SA 4.0；完整[来源与许可说明](docs/attribution.md)。灵感来自 [Thijs Simonian 的现实机器人画桥演示](https://thijs.net/projects/robot-painter)，本项目使用自己的模拟Panda机器人与协议。
