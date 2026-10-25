# @juzi/juzi-win-dsh「电脑控制」

把 Windows 桌面封装成本地 MCP（stdio）服务，让 DSH 里的模型能看到并操作这台电脑。
插件结构参照 `plugins/dsh-deepseek-tools`：`lib/index.js` 把配置交给官方 MCP 客户端，
Python 服务独立运行，`cordis.patch.yml` 负责 bundle 注册。

> **当前进度：第一轮。** 已完成插件骨架与只读/窗口定位能力（`list_windows`、
> `focus_window`、`screenshot`）。点击、滚动、输入、按键在第二轮接入；系统控制、
> 确认门与完整日志在第三轮接入。README 随轮次更新。

## 工具

| 工具 | 完整调用名 | 状态 | 说明 |
|---|---|---|---|
| `list_windows` | `mcp__win__list_windows` | 已实现 | 可见顶层窗口：hwnd、进程名、PID、标题、物理像素矩形、最小化、前台 |
| `focus_window` | `mcp__win__focus_window` | 已实现 | 按 hwnd / 进程名 / 标题关键字切前台；最小化先还原；返回真实前台状态 |
| `screenshot` | `mcp__win__screenshot` | 已实现 | 整屏或窗口客户区截图，PNG 返回；支持 `max_width` 等比缩放 |
| `click` | `mcp__win__click` | 第二轮 | 物理像素左键/右键/双击，可选 hwnd 客户区相对坐标 |
| `scroll` | `mcp__win__scroll` | 第二轮 | 在指定坐标滚动 |
| `type_text` | `mcp__win__type_text` | 第二轮 | SendInput Unicode 输入中文/换行，不占用剪贴板 |
| `press_keys` | `mcp__win__press_keys` | 第二轮 | 组合键，如 `ctrl+v`、`alt+tab`、`win+d` |
| `system` | `mcp__win__system` | 第三轮 | 亮度、音量/静音、锁屏 |

## 安装

```powershell
# 1. Python 依赖（本机 C:\Python314 已装 mcp 1.27 与 Pillow 12）
C:\Python314\python.exe -m pip install -r plugins\juzi-win-dsh\requirements.txt

# 2. 安装到目标 profile（示例为 desktop）
dsh plugin --profile desktop add "file:D:/Tools/AI/Juzi-Skill/Juzi-DSH-Plugins/plugins/juzi-win-dsh"
```

安装后确认 profile 的 `dsh.profile.bundles` 含 `@juzi/juzi-win-dsh`，重启 Desktop 或等待 profile 热重组。
插件默认使用 `C:\Python314\python.exe`；也可在 profile patch 中覆盖：

```yaml
- id: juzi-win-dsh
  config:
    python: 'C:/Python314/python.exe'
```

## 坐标与 DPI

- 服务启动时切到 **Per-Monitor V2** DPI 感知，之后所有坐标都是**物理像素**。
- 本机屏幕 2160×1440、缩放 150%；DPI 不感知的程序只会看到 1440×960，本服务不会。
- `screenshot` 元数据里 `original_width/original_height` 是截图原始物理尺寸，
  `width/height` 是缩放后图像尺寸，`scale = width / original_width`。
- 换算公式：`屏幕坐标 = origin + 截图坐标 / scale`。
- `hwnd` 截图只含**客户区**（不含标题栏），`origin` 是客户区左上角的屏幕坐标；
  第二轮的 `click(hwnd=...)` 会使用同一个原点。
- 整屏截图 `origin` 是虚拟屏幕左上角，覆盖所有显示器。

## 安全

- 禁止操作清单：UAC（`consent.exe`）、Windows 安全中心、锁屏/登录界面、
  1Password / Bitwarden / KeePass / LastPass 等密码管理器；按进程名与标题双重匹配。
- 操作日志写系统临时目录 `juzi-win-dsh-<pid>.jsonl`，进程正常退出即删除，不跨运行保留。
- `confirmMode` / `allowlist` 配置项已在 `lib/config.js` 中预留并传入服务端，
  确认门在第三轮实现；当前轮次只有只读与窗口焦点操作。

## 测试

```powershell
C:\Python314\python.exe plugins\juzi-win-dsh\smoke_test.py
```

第一轮覆盖：

1. MCP 握手后工具清单为 `list_windows` / `focus_window` / `screenshot`。
2. `list_windows` 能列出 `ChatGPT.exe`、`WindowsTerminal.exe`、`Weixin.exe`。
3. 整屏截图原始尺寸与 DPI 感知后的系统物理分辨率一致（本机 2160×1440）。
4. `max_width=1080` 时返回 1080×720、`scale=0.5`，PNG 实际尺寸与元数据一致。
5. Notepad++ 最小化时 `focus_window` 能还原并真正成为前台（`foreground=true`）。

预期最后一行 `SMOKE_OK`。

### 测试约定（必须遵守）

- 输入类测试**禁止往已有标签页/已有文件里打字**。自动化流程必须先让 Notepad++ 执行 `Ctrl+N` 新建空白标签页，确认标题是新的「新文件」后再输入。
- 测试结束用 `Ctrl+W` 关闭该标签页；若弹出保存提示选择「不保存」，不写入任何用户文件。
- 临时截图、脚本、日志一律用 `.tmp-*` 前缀放在仓库根或系统临时目录，测试后立即删除；`.gitignore` 已忽略 `.tmp-*`，但清理仍是硬要求。
- 不把测试产生的文件、截图或日志加入 git。

## 文件

| 文件 | 作用 |
|---|---|
| `lib/index.js` | DSH 插件入口，交给官方 `@deepseek-ai/dsh-mcp-client` |
| `lib/config.js` | 解析 Python、confirmMode、allowlist，生成 MCP stdio 配置 |
| `server.py` | FastMCP 服务；stdout 只走协议 |
| `winapi.py` | DPI、窗口枚举、前台切换、截图（ctypes + Pillow） |
| `security.py` | 禁止操作窗口清单 |
| `runlog.py` | 本次运行内的 JSONL 操作日志 |
| `smoke_test.py` | 真机 MCP 端到端冒烟 |
| `cordis.patch.yml` | bundle 注册与默认配置 |
| `requirements.txt` | `mcp` 与 `Pillow` |

## 已知限制

- 第一轮没有输入注入，`click` / `type_text` 等工具尚不可见。
- `screenshot(hwnd=...)` 依赖窗口可被 `PrintWindow` 捕获；最小化窗口需先 `focus_window`。
- Windows 前台锁可能拒绝后台进程置前；`focus_window` 会返回 `foreground=false` 而不是假装成功。
