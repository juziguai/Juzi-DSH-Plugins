# 开发与接入

## 源码与构建

- 变更：`lib/index.js` 维护 Host 事件与路由，`lib/recorder.js` 管理每轮私有 Git 快照，`lib/git.js` 适配公开 subprocess，`lib/client.js` 维护右侧界面。无需构建和 npm 运行依赖；需要本机 Git，不能写用户仓库的 index/ref。
- Ultra：交互、样式、标签组件、版本数据位于 `plugins/dsh-ultra-effort/src/`；在仓库根运行 `npm run client:build` 生成 `lib/client.js`。构建无第三方依赖，默认验证会检查生成漂移。`archive/legacy-patches/` 不能重放。
- Ultra 快速执行：`lib/index.js` 声明 `fastSessions` 活设置；`lib/fast-*.js` 维护会话快照与稳定提示，`src/fast-control.mjs` 通过正式 Settings RPC 保存。Host 新增官方 schemastery 运行依赖，源码 `link:` 前先运行 `npm install --prefix plugins/dsh-ultra-effort --ignore-scripts --package-lock=false`。最低宿主为 0.2.1-rc.3；后台服务通过可释放的可选注入接入。
- 更新模型版本：从 Ultra 目录运行 `powershell -NoProfile -File build/update-versions.ps1`，联网读取官方价格页后写 JSON 并构建。独立角标包冻结为旧版回退用途；新数据只维护 Ultra 一处。
- 搜索：`lib/index.js` 将 MCP 配置交给官方客户端；`lib/config.js` 按模块位置定位 Python。Python 文件保持同目录，独立 stdio 入口不依赖 DSH。
- 不自动安装、启动或重启真实 profile。静态检查通过不等于 DSH 界面或生产工具验收通过。

## 安装到 DSH

先选择目标 profile，并按宿主要求退出正在使用的实例。以下以 web 为例，在仓库根目录执行；只安装需要的插件。

```powershell
$repo = (Get-Location).Path.Replace('\', '/')
dsh plugin --profile web add "link:$repo/plugins/dsh-changes"
dsh plugin --profile web add "link:$repo/plugins/dsh-ultra-effort"
dsh plugin --profile web add "file:$repo/plugins/dsh-deepseek-tools"
```

核对目标 profile `package.json` 的 `dsh.profile.bundles` 包含需要加载的包名。
搜索插件复用宿主 `@deepseek-ai/dsh-mcp-client`（peer `>=0.2.1-rc.2 <0.2.2`，已核验 0.2.1-rc.2 与 0.2.1-rc.3），不捆绑另一套 DSH 服务。升级宿主时重新核验 peer 版本与契约。
搜索插件推荐 `file:` 安装，由包管理器解析 peer；更新源码后需重新安装。UI 插件可使用 `link:`。搜索插件若改用 `link:`，必须先在插件目录解析好匹配 peer；仅链接包不能保证 ESM 依赖可解析。

搜索插件先安装 Python 依赖，再按需覆盖解释器：

```powershell
python -m pip install -r plugins/dsh-deepseek-tools/requirements.txt
```

```yaml
- id: juzi-deepseek-tools
  config:
    python: 'C:/Python314/python.exe'
```

如已有 `mcp-deepseek-tools` 条目，切换时停用旧条目，避免两个 `deepseek` 命名空间同时注册。Ultra 内置角标无需独立包或官方标签插槽注册；旧角标包的迁移见 [迁移指南](ultra-migration.md)。

## 从旧仓库迁移

旧目录 `Juzi-DeepSeek-Tools` 保持原样。新源码在本仓库 `plugins/`；原安装引用不会自动切换。
切换前备份 profile 清单与 patch，记录旧路径；逐个更新包路径和 bundle 配置，重启后验证插件界面/工具发现。
失败时恢复备份和旧路径，停止继续切换。不要删除旧目录，直到新路径完整验收。

## 验证分层

Python MCP启动配置由`lib/config.js`提供`createConfig`，统一启动契约测试自动发现使用官方MCP客户端的包：工作目录必须在可替换安装包之外，脚本使用包内绝对路径，并保留显式指定的项目解释器。Python依赖应装入独立解释器或项目虚拟环境，避免将其它应用的私有Python目录加入用户全局PATH。

1. `npm test`：构建一致性、离线结构、语法、变更快照与 Host 生命周期、Ultra 单包标签与交互、预设生成及失败路径、插件参数和计数并发。设置 `PYTHON` 后只使用该解释器，导入失败直接报错；未设置时尝试 `C:\Python314\python.exe` 和 PATH 中的 `python`，仅接受能 `import mcp` 的解释器。
   设置 `DSH_SLOT_CORE_MODULE` 指向官方 `dsh-client-ui-slots/lib/index.js` 时执行真实插槽注册测试；设置 `DSH_CORDIS_MODULE` 指向官方 `cordis/lib/index.js` 时执行 Host 激活与释放测试；CI 必须执行两者。
   设置 `DSH_PRESET_MODULE` 指向官方 `dsh-agent-preset/lib/index.js` 时使用其 YAML schema 与 Cordis 验证新预设的配置、工具一致性、注册与释放；CI 使用 0.2.1-rc.3，仅验证声明契约，不启动真实 Agent 或调用工具。
   设置 `DSH_FAST_RUNTIME_ANCHOR` 指向隔离测试运行时的 `package.json` 时，执行真实 Loader、Settings、ConfigEditor、Sessions、SystemPrompt 和 SettingsController 集成；仅 HTTP 传输为测试替身。该运行时安装 `@deepseek-ai/dsh-config-editor`、`dsh-settings`、`dsh-system-prompt`、`dsh-api-settings-controller` 的 0.2.1-rc.3 及其 peer（`--legacy-peer-deps=false --include=peer`）。`DSH_ULTRA_UI_RUNTIME_ANCHOR` 指向含 `react@18.3.1`、`react-dom@18.3.1`、`jsdom@26.1.0` 的运行时清单，执行真实 React 交互与提前返回清理回归。CI 必须执行两项；jsdom 不覆盖现代 CSS，布局与动效另用浏览器验收。
2. 安装环境：验证官方 peer 可解析、MCP 握手及工具发现。
3. 真实 profile：变更实时刷新、历史固定、会话隔离与释放清理，以及模型切换、强度交互、版本角标、Search/Fetch；真实 API 测试主动执行，可能产生费用。

快速执行的性能对照必须固定模型、推理强度、任务与验收标准，在隔离副本中交错配对比较开/关，记录总耗时、正确性、步骤、token 与重试。离线契约通过只能证明开关与策略行为，不能证明提速。执行真实 API 对照前取得单独授权；不把计时写入默认测试或用户目录。开关和边界见 [插件说明](../plugins/dsh-ultra-effort/README.md)。

「解锁模式」的维护真源为 `plugins/dsh-preset-unlock/prompts/persona.md` 与官方标准预设快照；运行根命令 `npm run preset:build` / `npm run preset:check`。安装包不包含构建工具或 vendor 快照，安装时不会构建或改默认预设。人格文本不是操作系统沙箱，权限继续由宿主提供。

## Git 工作流

`git status --short` → 检查完整 diff 和新增文件 → `npm test` → `git diff --check`。
可使用 [发布工具](release-workflow.md) 的 `prepare` 统一构建与检查，并在输入相同时复用完整测试回执；`pack` 从固定提交制包，`market` 默认生成局部更新预览，`deploy` 默认只展示计划。
审核范围后再按用户授权暂存/提交；不直接 `git add .`。保留依赖锁文件，忽略运行时锁而非所有 `*.lock`。
根仓库版本与组件版本独立，不为目录搬迁机械升级所有插件。新组件必须包含清单、README、加载入口及可验证路径。
