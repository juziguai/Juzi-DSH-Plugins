# 更新日志

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
