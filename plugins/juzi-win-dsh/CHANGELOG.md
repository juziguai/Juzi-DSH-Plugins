# 更新日志

## [1.1.3] - 2026-10-30

### 变更

- 焦点文本读取复用独立 STA 子进程，每次请求仍重新核验目标、焦点与密码控件；不缓存文本。

### 修复

- 读取超时或故障后回收旧子进程，下一次调用重新创建；传输失败不再作为延迟输入重复等待。
- 私有工作进程的工作目录位于安装包外，插件退出时关闭该进程；升级需先停用本插件并更新完整包，再启用。

## [1.1.2] - 2026-10-29

### 修复

- Python 工作目录移至系统临时目录，避免占用插件安装目录而阻止 Windows 更新时替换目录；脚本仍从安装包绝对路径加载。


## [1.1.1] - 2026-10-28

### 新增

- 新增焦点文本回读与同窗输入批次，共17个工具；批次一次确认，失败或未验证时停止。
- 新增显式 `allow_unverified` 派发选项，保持目标、焦点、密码保护与一次性确认。

### 修复

- 输入绑定目标窗口与焦点控件，粘贴前再次核对，避免确认期间目标漂移。
- 通过内容回读验证落地，有界重试异步结果并统一软换行；无法验证时明确报告派发状态，避免重复输入。
- 经典 Edit / WinForms Edit 在 UIA Pattern 不可用时采用有超时的 WM_GETTEXT 回读。
- Unicode 换行改为 Shift+Enter，制表符按 Unicode 派发，中文输入按字符节流。
- 冒烟入口同步17个工具清单，并明确报告缺失项和意外项。

## [1.1.0] - 2026-10-28

### 新增

- `manage_window`：`get_work_area`（只读）、`move` / `resize` / `set_bounds`、`minimize` / `maximize` / `restore`、`close`（只发 `WM_CLOSE`）、`tile`（`left_half` / `right_half` / 四象限 / `maximize`）。按 DWM 可见外框补偿不可见边框，回读 `applied_bounds`，被系统钳制时 `clamped=true`；`close` 检测到同进程保存对话框时返回 `close_pending_dialog=true`，不自动点击按钮。
- `hover`：移动到物理像素坐标并停留 0~10000ms，不按键。
- `drag`：按下起点 → 按 `steps` 插值移动 → 松开，支持 left/right/middle、按下/松开前停留；途中落点命中禁止窗口时立即抬键中止并返回 `aborted_blocked_window`。
- `wait`：`timeout` / `window_exists` / `window_gone` / `title_contains` / `foreground_is` / `screenshot_stable`；超时返回 `ok=false` + `timed_out=true`；稳定度只用缩略图差分，不回传截图。
- `clipboard`：`get`（默认 8KB 截断）、`set`（默认备份）、`clear`、`restore`；纯 ctypes 实现，不依赖 PowerShell。
- `launch_app`：`ShellExecuteExW` 启动绝对路径/URI，等待新窗口并返回 hwnd；拒绝相对路径、`as_admin=true`、脚本宿主（powershell/cmd/wscript/cscript/mshta/reg 等）与脚本文件。
- `find_text`：Windows.Media.Ocr 优先、Tesseract 回退；返回 `confidence`（Windows OCR 无置信度时为 `null`）、屏幕物理像素 `cx/cy` 与外接矩形；中文 OCR 字间空格与同一视觉行拆分可正确拼接；拉丁字母被光标遮挡时用 Tesseract 补词框。引擎不可用返回 `ocr_unavailable` 与安装提示。
- 新增 `clipboard_win.py`、`launcher.py`、`ocr.py`、`ocr_windows.ps1`。
- `smoke_test.py` 扩展：15 工具清单、`get_work_area`、`clipboard.get`、`wait` 短超时、`find_text` 引擎探测（只读）。
- README 补充新工具、坐标换算、OCR 依赖、脚本宿主拒绝策略与最小化/关闭语义。

### 变更

- MCP `serverInfo.version` 升到 1.1.0；1.0.0 的 8 个工具签名与行为保持不变。
- `window_info` 增加 `maximized` 字段，供 `list_windows`/状态机回读。

### 修复

- `type_text` 默认粘贴路径继续按格式快照并恢复剪贴板（1.0.0 回归测试通过）。
- `manage_window.close` 对 Notepad++ `#32770` 保存对话框的检测：返回 `dialogs` 与 `close_pending_dialog`，不自动按「是/否」。
- `launch_app` 脚本宿主黑名单按去掉 `.exe` 的进程名比较，修正 `cmd.exe` 未被拦截的问题。

### 安全与协议修复（Codex 审查 R1-R13）

- R1：`lib/index.js` 接入 DSH `tools/pre-execute` 审批 seam；宿主 approval 策略为 `ask` 时对写操作发原生 `ask`，策略为 `never` 时保留服务内 token 协议。README 明确 token 不能证明人工批准。
- R2：click/hover/drag/scroll 以屏幕落点真实顶层窗口为准，hwnd 只作预期目标；派发前再次核对，变化即中止。type_text/press_keys 在派发前及 helper 内核对实际前台窗口。`screenshot`/`find_text` 拒绝与禁止窗口相交的区域。
- R3：新增纯标准库 `schema_validate.py`，所有工具入口按声明 schema 严格校验类型/范围/未知字段；布尔只接受 true/false，整数拒绝 bool/float/NaN。
- R4：剪贴板改为事务：备份失败不写入；用 `GetClipboardSequenceNumber` 记录所有权，restore 遇到外部新内容返回 `clipboard_changed` 冲突；`paste_text.ps1` 分别报告 `paste_ok`/`restore_ok`/`restore_conflict`。
- R5：stdin 读取限制单帧 1 MiB、整数 1000 位、嵌套 200 层；解析错误返回 JSON-RPC `-32700` 后继续处理后续帧。
- R6：`system` 的 brightness/volume/mute/lock 写请求在 `always` 下走确认；无参只读免确认。
- R7：禁止清单补 Proton Pass/Enpass/浏览器密码管理标题；目标进程身份读取失败 fail-closed；launcher 规范化尾部点/空格并拒绝 `.lnk/.url`、`unins*`/`uninstall*`、`msiexec`。
- R8：窗口截图裁剪后严格核对客户区尺寸，失败改走带 `all_screens=True` 的屏幕客户区；副屏负坐标回退可用。
- R9：校验 JSON-RPC 版本、id、params 类型和初始化状态；未知协议版本返回实际支持的 `2025-06-18`。
- R10：失败/拒绝设置 MCP `isError=true`；`confirmation_required` 用 `status` 明确表示未执行；新增 `error_code` 并保留 `error` 兼容。
- R12：`type_text` 文本改由 stdin 传给 PowerShell helper，不再放 Base64 命令行参数。
- R13：Pillow 最低版本提升到 11.2.1，匹配 `ImageGrab.grab(window=...)` 的实际要求。
- `regression_test.py`：新增 14 项隔离回归（R2/R3/R4/R5/R6/R7/R8/R9/R10/R12/R13）。

## [1.0.0] - 2026-10-26

### 新增

- 新建 `@juzi/juzi-win-dsh`「电脑控制」DSH 插件：`lib/index.js` + `lib/config.js` + `cordis.patch.yml`，复用官方 `@deepseek-ai/dsh-mcp-client`。
- 完整 8 个 MCP 工具：
  - `list_windows`：hwnd、进程名、PID、标题、物理像素矩形、最小化、前台；最小化窗口给出还原矩形。
  - `focus_window`：按 hwnd / 进程名 / 标题关键字切前台，最小化先还原，返回真实 `foreground`。
  - `screenshot`：整屏或窗口客户区 PNG，支持 `max_width` 缩放；Chrome/Electron 窗口自动回退屏幕截图。
  - `click`：左键/右键/双击，支持 hwnd 客户区相对坐标。
  - `scroll`：指定坐标滚动，正数向上、负数向下。
  - `type_text`：默认剪贴板粘贴并恢复原剪贴板，支持中文/换行/制表符；`method=unicode` 时用 SendInput。
  - `press_keys`：组合键 `ctrl+a`、`ctrl+c`、`alt+tab`、`win+d`、`f5` 等。
  - `system`：WMI 亮度 0~100 读写回、Core Audio 音量/静音、锁屏。
- Per-Monitor V2 DPI 感知与物理像素坐标；本机 150% 缩放下截图仍为 2160×1440，点击误差实测 0 物理像素。
- `confirm_mode` 三档：`always`（默认，一次性令牌）/ `allowlist` / `off`；未确认绝不执行点击或输入。
- 禁止操作窗口清单（UAC / Windows 安全中心 / 登录锁屏 / 常见密码管理器）与本次运行内的 JSONL 日志。
- 纯标准库 MCP stdio 实现：避开 `mcp` 包 3.4 秒冷启动导致 DSH 约 2 秒启动窗口超时的问题。
- `smoke_test.py`：MCP 握手、8 工具清单、窗口枚举、截图尺寸/缩放、Notepad++ 置前、系统状态读取、确认令牌单元测试。

### 修复

- 窗口截图对 Chrome/Electron 纯白结果自动回退到屏幕客户区截图。
- 输入中文改为剪贴板粘贴优先，解决 Chromium/Electron 内容输入框对 SendInput Unicode 不生效的问题。
- 剪贴板恢复从单一 IDataObject 改为按格式快照后重建，文本剪贴板可原样恢复。

## [0.1.0] - 2026-10-26

### 新增

- 新建 `@juzi/juzi-win-dsh`「电脑控制」DSH 插件骨架：`lib/index.js` + `lib/config.js` + `cordis.patch.yml`，复用官方 `@deepseek-ai/dsh-mcp-client`。
- 第一轮只读与窗口定位工具：
  - `list_windows`：hwnd、进程名、PID、标题、物理像素矩形、最小化、前台。
  - `focus_window`：按 hwnd / 进程名 / 标题关键字切前台，最小化先还原，返回真实前台状态。
  - `screenshot`：整屏或窗口客户区 PNG，支持 `max_width` 缩放，返回原始尺寸与缩放比例。
- Per-Monitor V2 DPI 感知与物理像素坐标；本机 150% 缩放下截图仍为 2160×1440。
- 禁止操作窗口清单（UAC / Windows 安全中心 / 登录锁屏 / 常见密码管理器）与本次运行内的 JSONL 日志。
- `smoke_test.py`：MCP 握手、窗口清单、截图尺寸/缩放、Notepad++ 最小化还原、非法参数路径。
- 测试约定：输入类测试只用 `Ctrl+N` 新建空白标签页，禁止写入已有文件；测完关闭不保存；`.tmp-*` 临时文件测后清理。

### 说明

- 点击、滚动、中文输入、组合键、系统控制、confirm_mode 确认门分别在第二、三轮实现。
- 第一轮不修改用户 profile；安装与重启由验收方按 README 执行。
