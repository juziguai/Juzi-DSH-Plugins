# 更新日志

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
