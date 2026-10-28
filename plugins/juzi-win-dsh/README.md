# @juzi/juzi-win-dsh「电脑控制」

把 Windows 桌面封装成本地 MCP（stdio）服务，让 DSH 里的模型能看到并操作这台电脑。
插件结构参照 `plugins/dsh-deepseek-tools`：`lib/index.js` 把配置交给官方 MCP 客户端，
Python 服务独立运行，`cordis.patch.yml` 负责 bundle 注册。

## 工具

| 工具 | 完整调用名 | 说明 |
|---|---|---|
| `list_windows` | `mcp__win__list_windows` | 可见顶层窗口：hwnd、进程名、PID、标题、物理像素矩形、最小化、最大化、前台；最小化窗口给出还原矩形 |
| `focus_window` | `mcp__win__focus_window` | 按 hwnd / 进程名 / 标题关键字切前台；最小化先还原；返回真实 `foreground` |
| `screenshot` | `mcp__win__screenshot` | 整屏或窗口客户区 PNG；`max_width` 等比缩放；返回原始尺寸、缩放比例、origin；Chrome/Electron 窗口自动回退屏幕截图 |
| `click` | `mcp__win__click` | 物理像素左键/右键/双击；可选 hwnd 客户区相对坐标 |
| `scroll` | `mcp__win__scroll` | 在指定坐标滚动，正数向上、负数向下 |
| `type_text` | `mcp__win__type_text` | 输入中文/换行/制表符；默认剪贴板粘贴并恢复，`method=unicode` 时用 SendInput |
| `press_keys` | `mcp__win__press_keys` | 组合键：`ctrl+a`、`ctrl+c`、`alt+tab`、`win+d`、`f5` 等 |
| `system` | `mcp__win__system` | 亮度 0~100（WMI 读回）、音量 0~100、静音、锁屏；无参数时只读 |
| `manage_window` | `mcp__win__manage_window` | `get_work_area` / `move` / `resize` / `set_bounds` / `minimize` / `maximize` / `restore` / `close` / `tile`；坐标全部物理像素，`tile` 相对工作区 |
| `hover` | `mcp__win__hover` | 光标移到物理像素坐标并停留 `duration_ms`（默认 500，上限 10000），不按键 |
| `drag` | `mcp__win__drag` | 起点按下、按 `steps` 插值移动、终点松开；支持 left/right/middle；途中命中禁止窗口立即抬键中止 |
| `wait` | `mcp__win__wait` | `timeout` / `window_exists` / `window_gone` / `title_contains` / `foreground_is` / `screenshot_stable`；超时返回 `ok=false` 不抛异常 |
| `clipboard` | `mcp__win__clipboard` | `get` / `set` / `clear` / `restore`，本批只保证 Unicode 文本 |
| `launch_app` | `mcp__win__launch_app` | ShellExecuteEx 启动绝对路径/URI，可等待主窗口出现；拒绝相对路径、提权与脚本宿主 |
| `find_text` | `mcp__win__find_text` | OCR 找字：返回 `confidence`、屏幕物理像素 `cx/cy` 与外接矩形，可直接传给 `click` |

## 安装

Python 服务以系统临时目录作为工作目录，入口及辅助脚本均使用安装包内的绝对路径，避免工作目录占用阻止 Windows 替换插件目录。代码不会搬入临时目录。

从仍使用包内工作目录的旧版升级时，先停用电脑控制插件，等待 MCP 子进程退出，再安装并启用。仅结束进程可能触发宿主自动重连。此改动消除工作目录占用，不保证所有宿主更新均免重启；以 DSH 的应用结果为准。

运行时依赖只有 Pillow（本机 `C:\Python314` 已装 12.1.1；最低 **11.2.1**，因为窗口截图使用
`ImageGrab.grab(window=...)`）：

```powershell
C:\Python314\python.exe -m pip install -r plugins\juzi-win-dsh\requirements.txt
```

OCR 不需要 Python 依赖：

- **首选** Windows.Media.Ocr：使用系统「中文(简体)」OCR 语言组件，本机已可用；
- **回退** Tesseract 5：放在 `C:\Program Files\Tesseract-OCR\tesseract.exe` 或 PATH 中，
  语言数据至少 `eng`，中文找字需要 `chi_sim`。`find_text` 会先试 Windows OCR，
  不可用时再试 Tesseract；两者都没有则返回 `ocr_unavailable` 与安装提示。

本机桌面端 profile 由 Electron 独占管理，CLI 的
`dsh plugin --profile desktop add ...` 会被拒绝（实测：`profile "desktop" is managed
exclusively by the Electron application`）。开发时请用桌面端插件管理器添加本地目录，
或等 Codex 发布后从市场「电脑控制」升级；非 desktop profile 仍可用 `link:`：

```powershell
dsh plugin --profile <profile> add "link:D:/Tools/AI/Juzi-Skill/Juzi-DSH-Plugins/plugins/juzi-win-dsh"
```

发布后从插件市场安装「电脑控制」即可。安装后确认 profile 的 `dsh.profile.bundles` 含
`@juzi/juzi-win-dsh`；未出现工具时重启 Desktop。插件默认使用 `C:\Python314\python.exe`，
可在 profile patch 覆盖：

```yaml
- id: juzi-win-dsh
  config:
    python: 'C:/Python314/python.exe'
    confirmMode: always
    allowlist: []
```

## 确认模式

| 模式 | 行为 |
|---|---|
| `always`（默认） | 所有写操作第一次调用只返回 `confirmation_required` 和一次性 `confirm_token`，**不执行任何操作**。模型必须先在 dsh 里向用户说明目标和参数并取得确认，再用同一个 token 重试。token 绑定 action + 参数 + 目标窗口，180 秒过期、单次有效。 |
| `allowlist` | 目标进程在白名单内时直接执行；否则同上需要确认。进程名可带或不带 `.exe`。 |
| `off` | 不要求确认，直接执行。 |

写操作清单：`click` / `scroll` / `type_text` / `press_keys` / `hover` / `drag` /
`manage_window` 的 `move`、`resize`、`set_bounds`、`minimize`、`maximize`、`restore`、
`close`、`tile` / `clipboard` 的 `set`、`clear`、`restore` / `launch_app` /
`system` 包含 `brightness`、`volume`、`mute`、`lock` 任一写参数时。

只读、不走确认门：`focus_window`、`screenshot`、`list_windows`、`system`（无参数）、
`manage_window` 的 `get_work_area`、`wait`、`clipboard.get`、`find_text`。
受保护窗口（UAC、Windows 安全中心、登录/锁屏、常见密码管理器）在任何模式下都会被拒绝；
`drag` 途中落点进入受保护窗口也会立即抬键中止。

### 确认门的真实边界（R1）

- DSH 宿主提供 `ctx.approval` 与 `tools/pre-execute` 审批 seam。本插件的
  `lib/index.js` 在宿主 approval 策略为 `ask` 时，会对 `mcp__win__*` 的写操作返回
  `ask`，由宿主原生审批链决定是否放行。
- 本机当前 profile 是 `danger-full-access`（approval policy `never`），插件会跳过
  `ask`；此时服务内 `confirm_token` 只是**模型侧两阶段协议**：它保证没有 token 不会执行、
  token 绑定参数且一次性，但**不能证明 token 是由人工批准后使用的**，也不是服务端强制确认。
- 需要硬审批时，请在 DSH 权限预设中启用 `ask` 并确保宿主 approval answerer 可用；不要把
  `confirm_mode=always` 当作独立的安全边界。
- 工具结果统一带 `ok` / `error_code` / `message`。执行失败或安全拒绝时 MCP `isError=true`；
  `confirmation_required` 是明确的非执行状态（`status=confirmation_required`，`isError=false`），
  不会与成功混淆。

## 坐标与 DPI

- 服务启动时切 **Per-Monitor V2** DPI 感知，所有坐标都是**物理像素**。
- 本机屏幕 2160×1440、缩放 150%；DPI 不感知的程序只会看到 1440×960。
- `screenshot` 元数据：`original_width/original_height` 是原始物理尺寸，
  `width/height` 是缩放后图像尺寸，`scale = width / original_width`。
- **唯一推荐换算**：`屏幕坐标 = origin + 截图坐标 / scale`。
- `hwnd` 截图只含**客户区**（不含标题栏），`origin` 为客户区左上角；
  `click(hwnd=..., x, y)` 使用同一个客户区原点。
- 整屏截图 `origin` 是虚拟屏幕左上角，覆盖所有显示器。
- `find_text` 返回的 `cx/cy` 已经是屏幕物理像素，可直接传给 `click`；其
  `origin` 与 `scale` 也一并返回，需要自行换算时用同一公式。
- Chrome / Electron 窗口的 `PrintWindow` 可能返回纯白，服务会自动改用屏幕客户区截图，
  `capture_method` 为 `window-screen`；此时窗口必须可见、未被完全遮挡。

## 窗口管理

- `tile` 相对显示器**工作区**（排除任务栏），支持 `left_half` / `right_half` /
  `top_left` / `top_right` / `bottom_left` / `bottom_right` / `maximize`。
- `set_bounds` / `tile` 按 DWM 可见外框补偿不可见边框，然后回读真实矩形；
  返回 `requested_bounds`、`applied_bounds`、`delta`、`clamped`。被系统最小尺寸或
  DPI 钳制时 `clamped=true`，不会假装成功。
- `minimize` / `maximize` / `restore` 回读 `state` 与 `window.minimized/maximized`。
- `close` 只发送 `WM_CLOSE`（等价点标题栏关闭），**不杀进程、不自动点保存按钮**。
  若窗口仍在并出现同进程对话框（例如 Notepad++ 的 `#32770` 保存框），返回
  `close_pending_dialog=true`、`foreground` 与 `dialogs`，由上层决定。
- 对禁止清单窗口的任何 action（含 `close`）一律拒绝。

## OCR 找字

- `find_text` 默认在整屏找；传 `hwnd` 只搜该窗口客户区；传 `region`
  （屏幕物理像素 `{x,y,width,height}`）只搜该区域。
- 默认 `lang=chi_sim+eng`，`match=contains`；`exact` 按整行/整词精确匹配。
- Windows OCR 没有置信度 API，命中项 `confidence=null`；Tesseract 回退时返回 0~1 的
  平均置信度。两者都会给出 `cx/cy` 与 `rect`。
- Windows OCR 常在中文之间插空格、把中英文拆成多个 OcrLine；服务按词框重建视觉行，
  忽略空白匹配。拉丁字母被文本光标遮挡时（如 `AB` 读不到 `C`），会用 Tesseract `eng`
  补词框，`engine` 显示为 `windows-ocr+tesseract`。
- 已知限制：艺术字、极小字、低对比度、强反光可能失败；此时回退到坐标或后续
  无障碍方案（本批不含 UI Automation）。
- 日志只记录查询与命中框/文案，不保存整张截图。

## 剪贴板

- `clipboard.get` 读取 Unicode 文本，默认截断到 8192 字节（UTF-8），返回 `length`、
  `returned_length` 与 `truncated`；空剪贴板返回 `empty=true`。`get` 不走确认门。
- `clipboard.set` / `clear` 默认把写之前的**文本快照**保存在本进程内存（单槽），
  快照状态区分 `success` / `empty`；**备份失败则不写入**。写入后记录
  `GetClipboardSequenceNumber` 作为所有权序列号，`action=restore` 前若发现序列号变化
  （用户或其他程序复制了新内容），返回 `clipboard_changed` 冲突并保留新内容，不覆盖。
- `type_text` 默认粘贴路径也在 PowerShell helper 中做同样的快照/序列号事务，并分别返回
  `paste_ok`、`restore_ok`、`restore_conflict`、`backup_status`；`type_text` 的文本通过
  stdin 传入，不占 Windows 命令行。
- 本批只支持 `format=text`，其它格式返回 `unsupported_format`。
- 剪贴板是系统级共享资源。即使前台是密码管理器，`get` 仍可读取系统剪贴板；
  不要在不可信环境下把敏感内容留在剪贴板，README 在此明确提示风险。

## 启动应用

- `path` 必须是绝对路径或明确 URI scheme（`ms-settings:`、`shell:` 等）；相对路径拒绝。
- `as_admin` 本批固定 `false`；传 `true` 直接返回 `as_admin_not_supported`。
- 使用 `ShellExecuteExW` 的 `open` 动词，不经过 `cmd /c` 拼接；`args` 原样传给目标程序。
- 本批一律拒绝脚本宿主、提权/注册表工具与卸载器：`powershell.exe`、`pwsh.exe`、
  `cmd.exe`、`wscript.exe`、`cscript.exe`、`mshta.exe`、`reg.exe`、`regedit.exe`、
  `rundll32.exe`、`msiexec.exe`，以及 `unins*` / `uninstall*` 等疑似卸载器；同时拒绝
  `.bat/.cmd/.ps1/.psm1/.vbs/.js/.wsf/.hta/.reg/.lnk/.url` 等脚本或快捷方式文件。
  文件名按 Windows 规则去掉尾部点和空格后再比较，防止 `cmd.exe.` 这类绕过。
- `wait_window_ms>0` 时按启动进程 PID / 进程名匹配新窗口；超时仍返回
  `started=true` 但 `window=null`（例如复用了已有进程）。

## 安全

- 禁止清单：`consent.exe`、Windows 安全中心、`LogonUI`/`LockApp`、1Password /
  Bitwarden / KeePass / LastPass / Proton Pass / Enpass 等；按进程名与标题双重匹配。
  进程身份读取失败时按 fail-closed 拒绝写操作。
- 点击/悬停/拖拽以**屏幕落点实际顶层窗口**为准，传入 hwnd 只作为预期目标；实际窗口不一致
  或派发前发生变化就中止。输入/按键在派发前再次核对前台窗口。
- `screenshot` / `find_text` 会检查截图区域与所有可见禁止窗口的交集，命中即拒绝，
  避免截取密码管理器等受保护内容。
- 操作日志写系统临时目录 `juzi-win-dsh-<pid>.jsonl`，进程正常退出即删除，不跨运行保留；
  确认令牌不写入日志；剪贴板日志只记录长度，不记录内容。
- `type_text` 默认先备份剪贴板所有可读取格式，粘贴后按序列号事务恢复；
  `method=unicode` 完全不碰剪贴板。
- 锁屏（`system(lock=true)`）执行后当前会话会立即锁定，属于预期行为。

## 测试

```powershell
# 首次跑 smoke 前安装测试依赖
C:\Python314\python.exe -m pip install -r plugins\juzi-win-dsh\requirements-dev.txt
C:\Python314\python.exe plugins\juzi-win-dsh\smoke_test.py
C:\Python314\python.exe plugins\juzi-win-dsh\regression_test.py
```

`smoke_test.py` 是安全冒烟：MCP 握手、17 工具清单（含 `get_focused_text`、`input_batch`）、窗口枚举、截图、`get_work_area`、
`clipboard.get`、`wait` 短超时、`find_text` 引擎探测、Notepad++ 置前和系统状态读取；
不点击、不输入、不按键、不修改音量/亮度、不写剪贴板。预期最后一行 `SMOKE_OK`。
`regression_test.py` 是纯标准库 unittest，覆盖 R2/R3/R4/R5/R6/R7/R8/R9/R10/R12/R13 的
可隔离回归（不执行真实键鼠/窗口/剪贴板写），预期 `OK`。

### 测试约定（必须遵守）

- 输入类测试**禁止往已有标签页/已有文件里打字**。自动化流程必须先让 Notepad++ 执行
  `Ctrl+N` 新建空白标签页，确认标题是新的「新文件」后再输入。
- 测试结束用 `Ctrl+W` 关闭该标签页；若弹出保存提示选择「不保存」，不写入任何用户文件。
- 临时截图、脚本、日志一律用 `.tmp-*` 前缀放在仓库根或系统临时目录，测试后立即删除；
  `.gitignore` 已忽略 `.tmp-*`，但清理仍是硬要求。
- 不把测试产生的文件、截图或日志加入 git。

## 文件

| 文件 | 作用 |
|---|---|
| `lib/index.js` | DSH 插件入口，交给官方 `@deepseek-ai/dsh-mcp-client` |
| `lib/config.js` | 解析 Python、confirmMode、allowlist，生成 MCP stdio 配置 |
| `server.py` | 纯标准库 MCP stdio 服务；实现 initialize / tools/list / tools/call |
| `winapi.py` | DPI、窗口枚举/布局/状态、前台切换、截图、SendInput 鼠标/键盘、稳定度差分 |
| `security.py` | 禁止操作窗口清单 |
| `confirm.py` | 一次性确认令牌 |
| `clipboard_win.py` | ctypes 剪贴板文本读写与单槽备份 |
| `launcher.py` | ShellExecuteExW 启动、脚本宿主拦截、新窗口等待 |
| `ocr.py` | OCR 引擎编排、视觉行重建与文字命中计算 |
| `ocr_windows.ps1` | Windows.Media.Ocr WinRT 调用，输出词框 JSON |
| `schema_validate.py` | 工具参数 JSON Schema 严格校验 |
| `paste_text.py` / `paste_text.ps1` | 剪贴板粘贴、序列号事务与恢复 |
| `system_control.py` / `system_control.ps1` | WMI 亮度 + Core Audio 音量/静音 + 锁屏 |
| `runlog.py` | 本次运行内的 JSONL 日志 |
| `smoke_test.py` | 安全冒烟测试 |
| `regression_test.py` | R1-R13 隔离回归测试（unittest） |
| `cordis.patch.yml` | bundle 注册与默认配置 |
| `requirements.txt` | 运行时依赖：Pillow >= 11.2.1 |
| `requirements-dev.txt` | 测试依赖：mcp 客户端 |

## 已知限制

- `server.py` 为绕开 DSH 约 2 秒的插件启动等待，使用纯标准库 MCP 实现；不依赖 `mcp`
  Python 包，`mcp` 只用于 `smoke_test.py`。
- 窗口截图回退为屏幕截图时，窗口必须可见；完全被遮挡时会截到遮挡窗口。
- 以管理员权限运行的窗口（UIPI）可能拒绝 SendInput 或前台切换；`focus_window` 会返回
  `foreground=false`，不会假装成功。
- `type_text` 的 paste 模式依赖目标窗口支持 `Ctrl+V`；极少数只接受按键的应用需显式
  `method=unicode`。
- Windows OCR 的 `confidence` 为 `null`（系统 API 不提供）；需要置信度时确保 Tesseract
  与对应语言数据可用。
- 确认令牌由模型转述给用户。服务端保证没有 token 绝不执行，且 token 绑定参数/目标、
  180 秒过期、单次有效；但**服务端无法验证 token 是否经人工批准**。宿主 approval 策略为
  `ask` 时 `lib/index.js` 会额外走原生审批；本机 `danger-full-access`（policy `never`）
  下该原生审批被禁用，`confirm_mode=always` 不是独立安全边界。
- R11（协议读取与串行执行队列分离）未在本批实现：DSH 的 MCP 客户端按会话串行调用，
  桌面写操作又必须保持单写者；拆队列需要重写协议循环、取消传播和按键释放保证，风险高于
  本批收益，留待后续版本。当前慢操作仍会占用该 MCP 连接，`ping`/取消不能提前插队。


## 输入验证（1.1.1）

`type_text`、`press_keys` 可传 `hwnd` 固定前台目标；不匹配时拒绝派发，调用方先明确聚焦。
`type_text` 使用 UI Automation 读取可编辑焦点控件，并将其标识纳入确认参数。
默认严格验证：不支持回读或文本超过读取上限时拒绝输入。密码控件始终拒绝。派发后以内容插入/选区替换比对验证；
无法验证返回 `paste_unverified` / `input_unverified`，其中 `dispatched=true` 表示可能已经写入，禁止自动重试。
已有相同文本且无法观察变化也返回未验证，而非宣称成功。

新增只读 `get_focused_text(hwnd?, max_chars=10000)`，返回文本、长度、控件类型、焦点标识及截断标记。
UI Automation Pattern 不可用时，对经典 Edit / WindowsForms10.EDIT 文本控件使用有 500ms 超时的 WM_GETTEXT 回读，核对所属窗口并拒绝密码样式；其他控件不使用窗口标题冒充文本。返回 read_method 标明来源。
Unicode 模式换行使用 Shift+Enter，制表符作为 Unicode 字符派发，字符间间隔 10ms；
Shift+Enter 的具体语义仍由目标应用决定，默认粘贴模式适合多行文本。
节流不能保证 Electron 不丢字，最终仍需回读验证。

确认令牌保持一次性、绑定参数与目标。新增 `input_batch(hwnd, actions, confirm_token?)`，一次确认覆盖同一窗口上最多 20 个明确的 type_text/press_keys 动作。两次调用完成整批；任何失败停止，返回已执行结果，授权不复用到批次外。
例如 actions 为 `[{"tool":"press_keys","arguments":{"keys":"ctrl+a"}},{"tool":"type_text","arguments":{"text":"你好"}}]`。
Windows OCR 的 `confidence=null` 表示引擎不提供置信度，不能视为 0 或虚构相似度。


### 未验证输入与延迟回读

`type_text(..., allow_unverified=true)` 显式允许在焦点可绑定但文本无法可靠回读时派发。
返回 `ok=true, dispatched=true, verified=false, status="dispatched_unverified"` 仅表示已派发，
不代表内容正确落地，`paste_ok=false`。默认 `allow_unverified=false` 继续严格验证。
该参数纳入确认令牌，不能使用严格模式令牌偷偷切换；密码控件、目标漂移及无法取得焦点标识仍拒绝。
批次遇到未验证派发即停止，不继续按键或再次输入；应使用 get_focused_text 或截图确认后再规划下一步。

验证最多读取四次，读取之间等待 100/200/400ms（另外计入读取自身耗时），不会重复派发输入。
CRLF、CR、软换行 U+000B 和行分隔 U+2028 统一为 LF 后比对；不删除空格或任意尾部文本。

浏览器 contenteditable 即使能够回读，也可能被 UIA 标记为不可编辑；这种目标每次输入均可能需要显式 `allow_unverified=true`。
