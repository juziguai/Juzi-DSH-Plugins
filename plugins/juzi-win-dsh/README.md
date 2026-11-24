# 电脑控制 · juzi-win-dsh

让 DSH 里的模型读取和操作 Windows 桌面。它可以找到窗口，判断按钮是否可用，读取被遮挡窗口中的文字，也可以在确认后点击或输入。插件通过本地 MCP 服务 `win` 提供工具。要操作另一台已授权的 Windows 电脑，见[远程 SSH 桥接指南](remote/README.md)。

[安装与首次使用](#安装与首次使用) · [选择读屏方式](#选择读屏方式) · [工具速查](#工具速查) · [写操作与确认](#写操作与确认) · [开发与验收](#开发与验收)

## 安装与首次使用

1. **准备 Python。** 插件默认使用 PATH 中的 `python`。在 PowerShell 中为该解释器安装截图依赖。使用虚拟环境或自定义解释器时，在插件配置的 `python` 字段填写同一解释器的完整路径。

   ```powershell
   python -m pip install 'Pillow>=11.2.1'
   ```

2. **在 DSH Desktop 启用「电脑控制」。** 要使用本文的 21 个工具，在桌面端插件管理器添加本仓库的 `plugins/juzi-win-dsh` 目录。市场安装使用市场索引固定的版本，工具清单以已安装版本为准。当前源码声明的 DSH 兼容范围为 `>=0.2.1-rc.2 <0.2.3-0`。

3. **做一次只读验证。** 在 DSH 对话里试试这句话。

   > 列出当前可见窗口，只告诉我哪个窗口在前台，以及它的标题和进程名。

   对应调用为 `mcp__win__list_windows`，参数为 `{}`。返回的 `windows` 列表里，每项都有窗口句柄 `hwnd`，可用于后续定向读屏。若看不到工具，检查当前 profile 的 `dsh.profile.bundles` 是否包含 `@juzi/juzi-win-dsh`，以及配置的解释器能否导入 `PIL`，再重新启用插件。

<details>
<summary>其他 profile、本地配置与升级</summary>

Desktop profile 由桌面应用管理。其他 profile 可以从仓库根目录运行以下命令，链接同一份源码。

```powershell
$pluginPath = (Resolve-Path '.\plugins\juzi-win-dsh').Path.Replace('\', '/')
$profileName = Read-Host '输入目标 DSH profile 名称'
dsh plugin --profile $profileName add "link:$pluginPath"
```

默认配置见 [cordis.patch.yml](cordis.patch.yml)。需要修改解释器或确认模式时，可在 profile patch 中覆盖这些字段。

```yaml
- id: juzi-win-dsh
  config:
    python: 'python'
    confirmMode: always
    allowlist: []
```

升级或回退时，先停用「电脑控制」，等它的 Python 子进程退出，替换完整插件包后再启用。Python 服务和 PowerShell 辅助脚本需要使用同一版本。

</details>

## 选择读屏方式

| 想知道什么 | 选哪个工具 | 能读到什么 |
| --- | --- | --- |
| “保存”按钮能点吗？两个同名按钮分别在哪一行？ | `inspect_ui` | Windows UI Automation（UIA）提供的控件名称、状态、层级和屏幕坐标 |
| 焦点输入框里实际写入了什么？ | `get_focused_text` | 当前焦点控件的原文、焦点标识和截断状态。密码控件拒绝回读 |
| 自绘界面上写了什么？某个词在哪里？ | `read_screen_text` / `find_text` | 前者按块返回 OCR 文字，后者按关键词返回命中框和中心点 |
| 浏览器标签页里有哪些网页控件？ | `chrome_cdp` | Chrome 或 Edge 开放本地调试并允许连接后，可枚举标签页、读取页面文字及控件状态 |
| 需要看实际布局、颜色或图标？ | `screenshot` | 整个桌面或窗口客户区的 PNG/JPEG，附原点、原始尺寸和缩放比例 |

**识别同名按钮。** 假设 `list_windows` 返回的目标 `hwnd` 为 `123456`。向 `inspect_ui` 传入下面的参数，在 `elements` 找到两个“删除”，再沿各自的 `parent_id` 在 `hierarchy` 中找到所属行或分组。节点 ID 仅在这一次结果中有效。

```json
{"hwnd": 123456, "query": "删除", "include_elements": true}
```

读取编辑器时，`include_visible_text=true` 会让支持 `TextPattern` 的控件返回可见原文。仅支持 `ValuePattern` 的控件可返回当前值。每个控件最多读取 2048 个 UTF-16 代码单元和 64 段可见范围，`visible_text_truncated=true` 表示还有内容未返回。日常查看可直接读默认的 `compact` 摘要。

**读取被遮挡的窗口。** `read_screen_text` 默认识别桌面可见像素，即使指定了 `hwnd`，遮挡物上的字也可能被读到。需要目标窗口自己的画面时，可向该工具传入 Windows Graphics Capture（WGC）参数。

```json
{"hwnd": 123456, "capture_mode": "wgc", "include_items": true}
```

WGC 需要支持窗口捕获的 Windows 10 1903 或更高版本，以及已还原的目标窗口。`items` 给出文字和屏幕坐标，`image.capture_method` 标明采集方式。可选 `region` 必须完全位于客户区内。抓帧期间可能闪现系统提示边框。取帧失败会返回错误。

**OCR 找字。** `find_text` 优先使用 Windows OCR。中文识别需安装相应的 Windows OCR 语言组件，也可使用 Tesseract 5 和 `chi_sim`、`eng` 语言数据。Windows OCR 返回的 `confidence=null` 表示引擎未提供置信度。两种引擎均不可用时，查看 `ocr_unavailable` 附带的安装提示。

**从图像换算点击坐标。** 桌面坐标使用物理像素。缩放截图上的点按 `屏幕坐标 = origin + 图中坐标 / scale` 逐轴换算。`find_text` 返回的 `cx/cy` 已是屏幕坐标，可直接用于不带 `hwnd` 的 `click`。带 `hwnd` 的点击使用客户区相对坐标，需要先减去客户区在屏幕上的原点。窗口截图若返回 `capture_method="window-screen"`，画面来自该区域当时可见的桌面。

## 工具速查

在 DSH 中，给下列工具名加上 `mcp__win__` 前缀即可得到完整调用名。MCP 客户端可通过 `tools/list` 获取已加载版本的参数定义。

| 用途 | 工具 | 常用操作 |
| --- | --- | --- |
| 窗口 | `list_windows`、`focus_window`、`manage_window` | 取得句柄、还原并切到前台、查询工作区、移动、调整大小、平铺或关闭 |
| 桌面内容 | `inspect_ui`、`get_focused_text`、`read_screen_text`、`find_text`、`screenshot` | 读取结构或原文、识别自绘文字、定位关键词、查看画面 |
| 网页 | `chrome_cdp` | 用 `list_tabs` 选择标签页，用 `inspect_page` 或 `read_text` 检查内容，也可点击或填写网页控件 |
| 鼠标 | `click`、`scroll`、`hover`、`drag` | 单击、双击、右击、滚动、悬停和拖拽 |
| 键盘与连续操作 | `type_text`、`press_keys`、`input_batch`、`action_batch` | 发送文本或组合键。同一前台窗口的连续输入用 `input_batch`，混合读屏与操作用 `action_batch`。每批最多 20 步 |
| 等待 | `wait` | 等窗口出现、前台切换或画面稳定。`ui_text` 等 UIA 文字出现，`ui_gone` 等其消失，`ocr_text` 等文字出现在画面上 |
| 剪贴板、应用与系统 | `clipboard`、`launch_app`、`system` | 读写及恢复文本、按绝对路径或受支持 URI 启动应用、读取或调整亮度和音量、锁屏 |

`manage_window` 的 `tile` 按显示器工作区布局，避开任务栏。尺寸受系统限制时看 `applied_bounds` 和 `clamped`。关闭窗口发送 `WM_CLOSE`，若返回 `close_pending_dialog=true`，应先处理保存对话框。

## 写操作与确认

`confirmMode` 默认取 `always`。点击、输入等写操作首次调用返回 `confirmation_required` 和一次性 `confirm_token`。模型应向用户说明目标和动作，取得确认后携带令牌、原参数和原目标再次调用。令牌 180 秒内有效。`allowlist` 对列出的目标进程免确认，`off` 关闭服务内确认。

需要人工审批时，在 DSH 宿主启用 `ask` 并配置可用的审批应答方。服务端令牌只校验动作、参数和目标，人工批准由宿主负责。`focus_window` 会改变前台窗口，但不经过写操作确认。UAC、登录界面、Windows 安全中心和常见密码管理器属于受保护窗口。

| 遇到的结果 | 如何继续 |
| --- | --- |
| `target_changed` / `not_foreground` | 重新核对目标窗口和焦点，再决定是否派发。鼠标操作还会核对落点实际所属的窗口 |
| 输入返回 `dispatched=true`、`verified=false` | 文本可能已经写入。先用 `get_focused_text` 或截图查结果，避免重复输入。批次遇到未验证输入会停止 |
| `clipboard_changed` / `restore_conflict=true` | 其他程序或用户已改动剪贴板，保留较新的内容。`clipboard` 工具的备份只覆盖 Unicode 文本 |
| `user_interrupted` | 用户在悬停、拖拽或批次操作期间移动了鼠标。停止后续操作，让用户接管 |
| 远程桥接返回 `remote_outcome_unknown` | 请求可能已送达远端。先检查远端窗口或输入内容，再决定下一步 |

`type_text` 默认粘贴并尝试恢复剪贴板，`method="unicode"` 可直接派发字符。默认会回读焦点控件验证文本。只有明确接受无法验证结果时才用 `allow_unverified=true`，密码控件仍拒绝输入。`clipboard.get` 读取的是系统共享剪贴板，其内容独立于当前前台窗口。

<details>
<summary>输入验证、鼠标接管与受保护窗口</summary>

- `type_text` 和 `press_keys` 可带 `hwnd` 固定前台目标。文本验证最多回读四次，回读之间等待 100、200、400 毫秒，整个过程只派发一次输入。`status="dispatched_unverified"` 表示已派发、内容待核实。
- `hover`、`drag` 以及含物理指针动作的 `action_batch` 会检查用户接管。`JUZI_WIN_DSH_TAKEOVER_PX` 控制位移阈值，默认 60 像素。若只想隐藏 AI 游标，可设置 `JUZI_WIN_DSH_CURSOR=off`。
- 截图或 OCR 区域与可见的受保护窗口相交时，会返回 `forbidden_window`。`launch_app` 支持普通权限下的应用启动，拒绝提权、脚本宿主和卸载器。[窗口保护规则](src/security.py) · [启动规则](src/launcher.py)
- 同一 MCP 连接按顺序执行请求。长时间的 `wait` 会占用该连接，后续调用需等它结束。

</details>

## 开发与验收

宿主从 `lib/` 读取配置，经包根目录的 `server.py` 启动 MCP。工具实现位于 `src/`，Windows 原生辅助脚本位于 `scripts/`。排查工具名或参数先看服务入口。[宿主配置](lib/config.js) · [工具定义与分发](src/core_server.py) · [版本记录](CHANGELOG.md)

以下命令从**仓库根目录**运行，`python` 应指向已安装插件依赖的解释器。

| 验证内容 | 命令 | 通过标志 |
| --- | --- | --- |
| 桌面工具隔离回归 | `python -B plugins/juzi-win-dsh/tests/regression_test.py` | `OK` |
| 桥接鉴权、断线处理与版本切换的本机回归 | `python -B plugins/juzi-win-dsh/tests/remote_test.py` | `OK` |
| 真实 WPF 测试窗口的 UIA 层级、可见原文与密码控件 | `python -B scripts/test-win-uia.py` | `UIA_SMOKE_OK` |
| 本机 MCP 握手、窗口、截图、剪贴板读取与系统状态 | `python -B plugins/juzi-win-dsh/tests/smoke_test.py` | `SMOKE_OK` |

首次运行本机冒烟测试，先执行 `python -m pip install -r plugins/juzi-win-dsh/requirements-dev.txt`。该测试会读取桌面，若 Notepad++ 已打开，还会将其置于前台。手工验证输入时，在 Notepad++ 用 `Ctrl+N` 创建空白标签，确认目标后再输入，结束后关闭并选择“不保存”。临时截图、脚本和日志使用 `.tmp-*` 前缀并在测试后清理。

运行中的服务日志在系统临时目录 `juzi-win-dsh-<pid>.jsonl`，正常退出时删除。远程部署、权限、升级和回退步骤见[远程桥接指南](remote/README.md)。
