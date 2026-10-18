# 配置验收：2026-10-18

本次只准备和检查配置，没有模型请求、Unity Player 启动、runtime pool 创建或远程发布。

- Windows 与 Linux 分别通过 11 个离线测试。测试禁止网络连接与新进程，启动入口只以 mock 验证委托。
- 使用已安装 Linux env 1.0.5 和真实 RobotPainting mod，为两个 case 完成离线 prepare。
- AgentArk commit 与版本锁一致，当前 SimpleAgent 默认快照一致；摘要输出为 32768，effort 继承。
- 真实 Linux mod 的 10 个已锁定文件通过大小和 SHA-256 检查，包含 DLL、Addressables、cfg 与 References。
- 金门大桥解析出一张参考附件，字节哈希匹配；鹈鹕解析出零张参考附件，两路工作区相机配置保留。
- 两者有效预算均为 3 attempts × 96 actions，固定笔、无限颜料、480 Hz、960×720、time scale 1。
- 模板与共享任务包没有被准备脚本修改，生成文件均位于 Git 忽略的 `runs/`。

测试还覆盖自定义双图顺序、纯文本覆盖、目标 UTF-16 长度、图片格式和尺寸、任务二进制变化、
prefab 模板拒绝、旧运行覆盖拒绝，以及启动时清除旧 task 路径但保留密钥和 DISPLAY。
这证明配置与准备路径通过离线检查，不代表在新入口下完成了一次 Unity 或模型评测。

原始离线准备输出位于本地 `runs/offline-validation/`，不随 Git 克隆提供。
重新验证使用 README 的离线命令和本机路径；不要用调用模型的方式代替配置检查。
