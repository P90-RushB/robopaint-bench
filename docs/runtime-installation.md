# 另一台机器安装与运行

RoboPaintBench 使用 AgentArk 原有的评测、SimpleAgent、任务加载、记录和回放流程。
运行时资源位于 [Hugging Face AgentArk dataset](https://huggingface.co/datasets/P90-RushB/AgentArk)，
下载定位及完整文件 SHA-256 由 [benchmarks/versions.json](../benchmarks/versions.json)
的 `runtime_downloads` 锁定。代码仓库不包含 Player、模型权重或原始评测结果。

当前 Task107 发布为 `task-v1`，最低兼容 env **1.0.5**，下载锁指向 HF 提交
[`86a260c`](https://huggingface.co/datasets/P90-RushB/AgentArk/commit/86a260c904f0bd4010f24a6c471d5b66553ece7d)。
env ZIP 仍只内置原来的前 51 个任务；Task107 作为独立 mod 安装。
mod 仅含运行配置、DLL、Addressables、默认目标文本、参考图及许可证，
不包含任何模型评测结果、record、日志、录像或开发中间文件。

两平台发布文件清单为 `benchmarks/task107_<platform>.task-v1.files.json`。
旧 `benchmarks/task107_linux.files.json` 保留用于辨认历史评测输入，不再作为新运行的
校验清单。发布包补充了许可证和显式回放一致性等级，并去除了 DLL 内的本机构建路径；
DLL 的执行代码、Addressables 与任务机制没有变化。

## 1. 安装锁定的 Python 依赖

使用已经准备好的 Python **3.10.0–3.10.12** 环境；这是锁定 AgentArk 的版本约束。
本流程不创建新 Python 环境。下载 RoboPaintBench 后，在其根目录执行命令。
先在本机设置 `AGENTARK_SOURCE` 为存放 AgentArk Python 源码的目录；新机器的示例为：

```sh
git clone https://github.com/P90-RushB/AgentArk.git "$AGENTARK_SOURCE"
git -C "$AGENTARK_SOURCE" checkout 368eaa4a6018c6c178f3a073ab4b88cbff85c79d
python -m pip install -e "$AGENTARK_SOURCE"
```

PowerShell 使用 `$env:AGENTARK_SOURCE` 替代上面的 `"$AGENTARK_SOURCE"`。
已有源码可以复用，但需要匹配该提交且没有已修改的包源码。`prepare_run.py` 会验证
AgentArk 提交、SimpleAgent 默认值、目标和平台任务文件。Python 依赖来自 AgentArk；
这里不维护另一份评测依赖或 harness。

## 2. 下载并安装 env 1.0.5 + Task107

先将 `ROBOTPAINTING_INSTALL` 设置为本机一个**尚不存在**的绝对目录，放在代码仓库
和评测输出目录之外。以下命令会下载所选平台的两个 ZIP：Player env 1.0.5 和
Task107 RobotPainting runtime mod。无需 Unity Editor，也无需下载模型权重。

Linux：

```sh
python -m pip install huggingface_hub
python scripts/install_runtime.py --platform linux --destination "$ROBOTPAINTING_INSTALL"
```

Windows PowerShell：

```powershell
python -m pip install huggingface_hub
python scripts/install_runtime.py --platform windows --destination $env:ROBOTPAINTING_INSTALL
```

`huggingface_hub` 仅是可选下载工具的依赖。安装器调用标准 `hf_hub_download`，使用
Hugging Face 的缓存和本机认证；需要访问权限时先执行 `hf auth login`，或通过安全的
本机方式配置 `HF_TOKEN`。不要把 token 放进命令参数、YAML 或 Git。可用 `--cache-dir`
指定缓存目录，默认遵循 HF 配置。[Hugging Face 下载接口](https://huggingface.co/docs/huggingface_hub/package_reference/file_download)
Windows 安装器为缓存、临时解包目录和安装目录的内部文件操作使用标准长路径前缀，
支持较深路径并保持同一缓存位置及认证方式；打印的部署变量保留普通可读路径。

安装器只取 `runtime_downloads` 中该平台的 env/task 条目，并要求 revision 为完整提交
哈希。两个 ZIP 都通过完整字节数及 SHA-256 检查后，在临时目录预检、解包；拒绝路径
穿越、绝对路径、符号链接、特殊文件和重复/歧义路径。结构检查通过后才创建目标目录。
已有目录会直接拒绝，重试时请选另一个新目录；不会清理旧安装、records 或 HF 缓存。
安装过程不启动 Unity、不调用模型、不创建 Python 环境。

安装后的目录为：

```text
<安装目录>/
  AgentArk.x86_64                  # Linux；Windows 为 AgentArk.exe
  AgentArk_Data/Resources/Mods/
    config.yaml.bak               # env 原始、不可变的合并基线
    config.yaml 或 config.json
    all_tasks/RobotPainting/
      cfg/task_config.yaml
      dll/
      <Addressables catalog>.json
      <Addressables bundles>.bundle
      References/GoldenGateBridge_reference.png
```

安装器识别 env ZIP 中唯一的 Player 根目录，因此兼容外层包装目录；Task107 发布 ZIP
采用 `cfg/`、`dll/` 等直接位于压缩包根目录的布局，也兼容一个 `RobotPainting/` 包装层。
Linux 的 Player 与 Unity crash handler 会设置可执行权限。Windows Player 和 mod
必须配对，Linux Player 和 mod 必须配对，不能混用平台文件。

成功后会打印当前终端可复制执行的设置命令，分别指向本机的 Player 可执行文件、
Mods 模板和 task store：

| 环境变量 | 安装器打印的路径 |
| --- | --- |
| `AGENTARK_ENV_PATH` | `<安装目录>/AgentArk.x86_64` 或 `AgentArk.exe` |
| `AGENTARK_MOD_PATH` | `<安装目录>/AgentArk_Data/Resources/Mods` |
| `AGENTARK_TASK_STORE_PATH` | `<安装目录>/AgentArk_Data/Resources/Mods/all_tasks` |

路径由本机选择，代码及 benchmark YAML 不写死任何盘符、用户名或 API key。
Task107 的 ModelScope Editor 源码包供 Unity 编辑开发使用；这里下载的是打包 Player
加载的 Addressables + DLL runtime mod，两者用途和格式不同。

## 手动下载，或复用已有 Player

不使用安装器时，从 `runtime_downloads` 读取 `repo_id`、完整 `revision` 和同一平台
的 `envs.<platform>.path`、`tasks.<platform>.path`。用其原值替换下面的占位符：

```sh
hf download P90-RushB/AgentArk '<env ZIP 路径>' '<task ZIP 路径>' --repo-type dataset --revision '<完整锁定提交>' --local-dir '<本机下载目录>'
```

CLI 下载同样支持本机认证和缓存。不要用 `main` 替换锁定提交。
[Hugging Face CLI 下载说明](https://huggingface.co/docs/huggingface_hub/guides/cli)

解包前用 `sha256sum`（Linux）或 `Get-FileHash -Algorithm SHA256`（PowerShell）
核对两个 ZIP 的完整 SHA-256，同时核对文件字节数与版本锁一致。解包到全新的临时
目录并确认没有越界路径或链接，然后把 env 的 Player 根目录放到本机安装位置。
将**平铺的 Task107 ZIP 内容**放进
`AgentArk_Data/Resources/Mods/all_tasks/RobotPainting/`，避免多出一层同名目录。
Linux 还需给 `AgentArk.x86_64` 和存在的 `UnityCrashHandler64` 加执行权限。

已有同平台 env **1.0.5** 可以复用：保留其原始 `Mods/config.yaml.bak`，将 task 放到
一个**新建、空的** `RobotPainting` 目录，或把独立 task store 设为
`AGENTARK_TASK_STORE_PATH`；它必须是包含 `RobotPainting/` 的父目录。
`AGENTARK_MOD_PATH` 仍需指向 Player 内部的 Mods 模板。不要覆盖正在使用的任务目录、
已有记录或之前的有效配置；保持原始 baseline，后续评测由 AgentArk sandbox 复制
并生成各运行自己的配置。安装器本身只支持完整安装到新目录。

## 3. 配置本机渲染和模型访问

正式 benchmark 使用 **Linux GPU 渲染**。机器必须有可用的图形驱动和可渲染的
`DISPLAY`；无物理显示器时可以使用本机已配置的 X server/Xvfb。先确认该 display
能供 Unity 渲染，再运行评测。不要把 display 值照抄其他机器；保持原生配置中的
`no_graphics: false`，保证两个工作区相机产生观测。安装器不配置驱动或 display。

Windows 可在图形桌面启动对应的 Windows Player/mod 做可视化运行，准备时明确传
`--runtime-platform windows`。这些运行记录与 Linux 正式 benchmark 分开标记。
`--runtime-platform` 选择验证与 sandbox 平台，不会把一种平台的二进制转换成另一种。

在运行模型前，通过本机安全方式设置 `OPENROUTER_API_KEY`。离线安装及准备阶段不
需要该 API key。模型调用使用 YAML 指定的 OpenRouter 模型，本地不加载模型权重。
密钥、机器路径和 display 配置都不要写进提交的配置文件。

## 4. 先准备，再显式启动

设置安装器打印的三个路径变量后，先离线准备；这一阶段不会启动 Player 或模型：

```sh
python scripts/prepare_run.py --case golden_gate --model sol --runtime-platform linux
python scripts/prepare_run.py --case pelican --model argon --runtime-platform linux
```

Windows 将 `linux` 改为 `windows`。也可用 `--env-path`、`--mod-path` 和 `--task-store`
直接传本机路径，用 `--output-dir` 选择全新的外部评测输出目录。默认写入 checkout
的 `runs/` 下，每次生成唯一运行目录。路径、版本或 mod 不匹配时先解决检查错误，
正式结果不要使用 `--allow-version-mismatch` 绕过锁定。

准备完成后，检查打印的配置位置，再单独执行：

```sh
python scripts/run_eval.py --config '<准备输出的 eval.yaml 绝对路径>'
```

该入口启动原有 AgentArk evaluator 和独立 runtime sandbox，保留 API key、DISPLAY
及 GPU 环境变量。运行结果、观测轨迹、画布、日志和可能另行生成的视频留在本机各自
运行目录；下载安装脚本没有上传功能，也不会上传这些数据。准备成功表示离线配置
通过检查；模型与 Player 的实际运行结果需等评测完成后确认。
