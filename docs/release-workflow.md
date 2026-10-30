# 发布与部署工具

`npm run release -- <阶段>` 串联现有构建、测试、官方市场校验和逐包部署。工具不提交、推送、打标签、创建 GitHub Release 或重启 DSH。根版本、组件版本和变更范围仍由维护者审核。

需要 Node.js 22 或更新版本、Git、npm、tar，以及明确指定的 Python。所有回执、日志和制包目录放在仓库内已被 Git 忽略的 `--run` 目录，默认 `.codex/release`；不要公开其中的 profile 备份和差异导出。

## 1. 构建与验证

```powershell
npm run release -- prepare --python C:/Python314/python.exe
```

默认构建全部插件的生成入口，执行完整 `npm test` 和 `git diff --check`。可用 `--plugins dsh-changes,dsh-ultra-effort` 限定构建范围，测试仍覆盖全仓库。官方 Host、插槽、预设和 React 集成测试的环境变量沿用 [开发指南](development.md#验证分层) 和 [CI 配置](../.github/workflows/verify.yml)，没有配置时对应测试仍可能跳过；复用一次有跳过项的结果不代表完成全部集成验收。

成功测试的回执位于 `<run>/gates/npm-test.json`。指纹包含插件及脚本内容（含未跟踪源码）、根包清单、CI 配置、市场目录、Node 版本、显式 Python 的版本和发行包清单，以及已配置官方运行时的入口、清单和锁文件。相同输入且日志校验通过才复用；源码或这些环境输入变化、日志丢失、前次失败均重新测试。文档和市场生成索引不影响测试指纹，`git diff --check` 每次执行。

缓存不递归校验外部 `node_modules` 全部内容；手工修改依赖内部文件等未纳入指纹的环境变化后，使用 `--refresh` 强制验证。缓存只减少本机重复工作，不能替代远程 CI。

各耗时阶段输出带 `phase`、`status` 和 `elapsedMs` 的 JSON 进度，等待期间每十秒提示一次；复用结果标记 `reused: true`。命令日志从进程启动时持续写入，失败前输出也会保留，无需等待整轮结束才能排查。例如另开终端查看：

```powershell
Get-Content .codex/release/gates/npm-test.log -Tail 20 -Wait
```

每次命令和内部阶段的起止边界同时追加到 `<run>/timing.jsonl`，包含独立运行标识、时间戳、耗时和复用状态。查询历史无需连接 DSH：

```powershell
npm run release -- report --run .codex/release
```

报告分别列出命令耗时、内部阶段及命令之间的空档。`measuredCommandMs` 只累计已结束命令，不重复累加其内部阶段；`betweenCommandsMs` 仅表示相邻命令间的墙钟间隔，不能当作下载或安装耗时。只有开始记录的命令标为 `incomplete`，不猜测其结束或重发任何操作；损坏日志会明确报错。命令计时从取得运行锁后开始，不包含 npm/Node 启动；外部 CI、GitHub 预检和网络下载若没有独立记录，仍应列为历史数据或未知。

## 2. 从固定提交制包

按授权审核、提交源码并推送，确认 CI 通过后，记录完整 40 位源码 SHA。后续阶段始终使用该提交，不将工作区修改标成已发布内容。

```powershell
$sourceCommit = '<完整源码SHA>'
$pluginDirs = 'dsh-changes,dsh-ultra-effort,dsh-quote-annotate,dsh-deepseek-tools,juzi-win-dsh'
$env:DSH_MARKET_INDEX_MODULE = '<已安装官方 dsh-plugin-market-index 包目录>/lib/index.js'
npm run release -- pack --plugins $pluginDirs --commit $sourceCommit --repository https://github.com/juziguai/Juzi-DSH-Plugins.git
```

仅接受正式组件版本。选定插件共用一次 Git 树读取和一次二进制 blob 批量读取，并在一次离线 `npm pack --ignore-scripts` 调用中制包；逐包核对身份、成员清单及解包后的逐文件 SHA-256。输出 `<run>/<SHA>/plan.json`、`archives/` 和 `SHA256SUMS.txt`，npm 日志为 `<run>/<SHA>/npm-pack.log`。相同提交及选择可以复用已核验的制包结果；目录选择、包体或保存的源码改变时停止。

安装来源使用官方校验器返回的固定 Git 地址；tgz 用于离线核验和交付。全新目标的首次制包若在生成 plan 前中断，请检查保留的日志并另选 `--run`，工具不自动清理不完整现场。

## 3. 生成市场预览

```powershell
npm run release -- market --plugins $pluginDirs --commit $sourceCommit --repository https://github.com/juziguai/Juzi-DSH-Plugins.git
```

默认只写 `<run>/<SHA>/market-index.json`，保留未选插件的版本、来源和展示信息，并验证全部条目的固定源码及官方格式。审核预览后以相同参数加 `--write-market`，才替换工作区 `marketplace/index.json`。源码与索引按 [市场指南](marketplace.md#生成和校验) 分别提交；提交、推送及外部发布仍各自需要用户授权。

清单和入口按固定源码提交批量读取；同一索引中共享提交的插件共用一次快照，不逐文件启动 Git。快照仅在本次调用内使用，下一次调用重新解析引用；工作区修改不改变固定提交结果。市场生成与制包复用同一套二进制 Git 读取器，入口必须是提交中的普通文件。

最终须核对 CI、公开索引 HTTP 200 和固定源码可访问，再进行真实界面或工具验收。工具不会根据一次本地通过回执宣告发布成功。

## 4. 逐包部署

先预览，不连接 DSH，也不修改 profile：

```powershell
$planPath = ".codex/release/$sourceCommit/plan.json"
npm run release -- deploy --plan $planPath
```

真实部署需要已授权的目标 profile、其 Host Inspector 的明确本机端口、已有 `js-yaml` 模块和绝对 Python 路径。每次宿主请求都核对实际 profile 目录，避免端口选错后操作另一个实例。端口不能沿用旧日志猜测；适配器使用当前已核验 DSH 0.2.1-rc.5 的 Inspector/插件管理器契约，结构不匹配会停止。此工具的新部署链路先通过隔离模拟验证；实际应用更新仍需真实验收。

```powershell
npm run release -- deploy --plan $planPath --apply --profile '<目标profile绝对路径>' --inspector 'http://127.0.0.1:<当前Host端口>/' --yaml '<已有js-yaml入口绝对路径>' --python C:/Python314/python.exe --changes-export '<新鲜差异导出JSON绝对路径>'
```

仅替换已经安装的选定插件。若包含需要替换的 Changes，先通过现有差异导出入口保存当前记录，传入 `--changes-export`：JSON 必须包含 `createdAt`、`sessions`、空 `errors` 和 `cappedTurns: 0`，生成时间不超过十分钟。停用 Changes 会清空原临时记录，备份导出供人工查阅，不能恢复成 Host 原有轮次；不更新 Changes 时无需此参数。

工具先检查无运行中的任务，使用指定 Python 的 `shutil.copy2` 备份 profile 四个配置文件并校验格式，再保留需要替换的原包。随后按包执行“停用 → 官方管理器安装固定 Git 来源 → 恢复原开关 → 核验”。原来停用的插件保持停用，已满足版本和来源的插件只核验；不批量停用其他插件。每个动作前重新检查任务，每个动作后保存管理器结果并核对宿主状态，最后核对文件、来源、原开关及无关配置。

单次连接复用同一 Inspector WebSocket，不重复启动外部检查进程。配置备份与原包位于 `<run>/rollback`，阶段状态在 `<run>/deployment.json`；确认完成的动作保留起止时间，备份、停用、安装和启用分别计时。安装阶段包含官方管理器的整体调用，不能据此拆分下载、pnpm 和宿主重载。

## 5. 失败与续接

```powershell
npm run release -- status
```

`status` 只读取本地回执，不查询 Host、不清除待定请求。使用自定义目录时，各阶段及 `status` 带同一个 `--run`。同一目录同时只允许一个工具进程。

确认完成的阶段可以续接，重复调用不会再次安装。出现任务运行、管理器失败、文件不符、配置漂移、连接断开或超时便停止；请求结果未知时保留 `pending` 和日志位置，后续调用拒绝重发。先核对实际安装状态和管理器日志，再人工决定恢复或创建新部署计划，不能通过删除回执盲目重试。

本工具不自动回滚、重启或强杀进程。回退时确认无任务后，通过官方管理器安装 `<run>/rollback` 中的原包并恢复原开关，再核对文件、配置和实际功能。仅配置确实损坏时才在退出 DSH 后用备份恢复；保留当前现场，避免覆盖后续正常配置或其他插件。回退真实系统仍须具备相应操作授权。
