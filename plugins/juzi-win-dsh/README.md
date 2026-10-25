# @juzi/juzi-win-dsh「电脑控制」

把 Windows 桌面封装成本地 MCP（stdio）服务，让 DSH 里的模型能看到并操作这台电脑。
插件结构参照 `plugins/dsh-deepseek-tools`：`lib/index.js` 把配置交给官方 MCP 客户端，
Python 服务独立运行，`cordis.patch.yml` 负责 bundle 注册。

## 工具

| 工具 | 完整调用名 | 说明 |
|---|---|---|
| `list_windows` | `mcp__win__list_windows` | 可见顶层窗口：hwnd、进程名、PID、标题、物理像素矩形、最小化、前台；最小化窗口给出还原矩形 |
| `focus_window` | `mcp__win__focus_window` | 按 hwnd / 进程名 / 标题关键字切前台；最小化先还原；返回真实 `foreground` |
| `screenshot` | `mcp__win__screenshot` | 整屏或窗口客户区 PNG；`max_width` 等比缩放；返回原始尺寸、缩放比例、origin；Chrome/Electron 窗口自动回退屏幕截图 |
| `click` | `mcp__win__click` | 物理像素左键/右键/双击；可选 hwnd 客户区相对坐标 |
| `scroll` | `mcp__win__scroll` | 在指定坐标滚动，正数向上、负数向下 |
| `type_text` | `mcp__win__type_text` | 输入中文/换行/制表符；默认剪贴板粘贴并恢复，`method=unicode` 时用 SendInput |
| `press_keys` | `mcp__win__press_keys` | 组合键：`ctrl+a`、`ctrl+c`、`alt+tab`、`win+d`、`f5` 等 |
| `system` | `mcp__win__system` | 亮度 0~100（WMI 读回）、音量 0~100、静音、锁屏；无参数时只读 |

## 安装

运行时依赖只有 Pillow（本机 `C:\Python314` 已装 12.1.1）：

```powershell
C:\Python314\python.exe -m pip install -r plugins\juzi-win-dsh\requirements.txt
```

本机开发用 `link:` 安装（会写入 profile 并自动加入 bundles）：

```powershell
dsh plugin --profile desktop add "link:D:/Tools/AI/Juzi-Skill/Juzi-DSH-Plugins/plugins/juzi-win-dsh"
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
| `always`（默认） | `click` / `scroll` / `type_text` / `press_keys` 第一次调用只返回 `confirmation_required` 和一次性 `confirm_token`，**不执行任何操作**。模型必须先在 dsh 里向用户说明目标和参数并取得确认，再用同一个 token 重试。token 绑定 action + 参数 + 目标窗口，180 秒过期、单次有效。 |
| `allowlist` | 目标进程在白名单内时直接执行；否则同上需要确认。进程名可带或不带 `.exe`。 |
| `off` | 不要求确认，直接执行。 |

`focus_window`、`screenshot`、`list_windows`、`system` 不走确认门。受保护窗口
（UAC、Windows 安全中心、登录/锁屏、常见密码管理器）在任何模式下都会被拒绝。

## 坐标与 DPI

- 服务启动时切 **Per-Monitor V2** DPI 感知，所有坐标都是**物理像素**。
- 本机屏幕 2160×1440、缩放 150%；DPI 不感知的程序只会看到 1440×960。
- `screenshot` 元数据：`original_width/original_height` 是原始物理尺寸，
  `width/height` 是缩放后图像尺寸，`scale = width / original_width`。
- 换算：`屏幕坐标 = origin + 截图坐标 / scale`。
- `hwnd` 截图只含**客户区**（不含标题栏），`origin` 为客户区左上角；
  `click(hwnd=..., x, y)` 使用同一个客户区原点。
- 整屏截图 `origin` 是虚拟屏幕左上角，覆盖所有显示器。
- Chrome / Electron 窗口的 `PrintWindow` 可能返回纯白，服务会自动改用屏幕客户区截图，
  `capture_method` 为 `window-screen`；此时窗口必须可见、未被完全遮挡。

## 安全

- 禁止清单：`consent.exe`、Windows 安全中心、`LogonUI`/`LockApp`、1Password /
  Bitwarden / KeePass / LastPass 等；按进程名与标题双重匹配。
- 点击会检查落点窗口；输入/按键会检查当前前台窗口；命中禁止清单直接拒绝。
- 操作日志写系统临时目录 `juzi-win-dsh-<pid>.jsonl`，进程正常退出即删除，不跨运行保留；
  确认令牌不写入日志。
- `type_text` 默认先备份剪贴板所有可读取格式，粘贴后恢复；`method=unicode` 完全不碰剪贴板。
- 锁屏（`system(lock=true)`）执行后当前会话会立即锁定，属于预期行为。

## 测试

```powershell
# 首次跑 smoke 前安装测试依赖
C:\Python314\python.exe -m pip install -r plugins\juzi-win-dsh\requirements-dev.txt
C:\Python314\python.exe plugins\juzi-win-dsh\smoke_test.py
```

`smoke_test.py` 是安全冒烟：只做 MCP 握手、工具清单、窗口枚举、截图、Notepad++ 置前
和系统状态读取；不点击、不输入、不按键、不修改音量/亮度。预期最后一行 `SMOKE_OK`。

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
| `winapi.py` | DPI、窗口枚举、前台切换、截图、SendInput 鼠标/键盘 |
| `security.py` | 禁止操作窗口清单 |
| `confirm.py` | 一次性确认令牌 |
| `paste_text.py` / `paste_text.ps1` | 剪贴板粘贴与恢复 |
| `system_control.py` / `system_control.ps1` | WMI 亮度 + Core Audio 音量/静音 + 锁屏 |
| `runlog.py` | 本次运行内的 JSONL 日志 |
| `smoke_test.py` | 安全冒烟测试 |
| `cordis.patch.yml` | bundle 注册与默认配置 |
| `requirements.txt` | 运行时依赖：Pillow |
| `requirements-dev.txt` | 测试依赖：mcp 客户端 |

## 已知限制

- `server.py` 为绕开 DSH 约 2 秒的插件启动等待，使用纯标准库 MCP 实现；不依赖 `mcp`
  Python 包，`mcp` 只用于 `smoke_test.py`。
- 窗口截图回退为屏幕截图时，窗口必须可见；完全被遮挡时会截到遮挡窗口。
- 以管理员权限运行的窗口（UIPI）可能拒绝 SendInput 或前台切换；`focus_window` 会返回
  `foreground=false`，不会假装成功。
- `type_text` 的 paste 模式依赖目标窗口支持 `Ctrl+V`；极少数只接受按键的应用需显式
  `method=unicode`。
- 确认令牌由模型转述给用户，真正的人工确认依赖 dsh 会话中的 ask_user_question；服务端
  保证没有 token 绝不执行，但无法验证 token 是由谁确认后使用的。
