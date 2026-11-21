# `juzi-win-dsh` 远程 SSH 桌面桥接（`remote/`）

通过 SSH 转发已授权 Windows 主机的活动交互桌面。本机 MCP 客户端可复用全部 21 个桌面工具。桥接按 Windows 实际分配的登录会话 ID 选择目标。

## 架构与组件

```text
[本机 MCP 宿主]
   │ stdio (initialize / tools/list 本地零延迟秒回)
   ▼
remote/local_proxy.py ──(首次 tools/call 懒连接: ssh -N -L 127.0.0.1:LPORT:127.0.0.1:RPORT)──┐
                                                                                              │
┌─────────────────────────── 远端 Windows 主机 (OpenSSH Server) ──────────────────────────────┘
│  remote/ensure_daemon.ps1  ──► 确保交互式桌面会话已启动回环桥并返回 {port, token}
│  remote/session1_daemon.py ──► 仅绑定 127.0.0.1:RPORT，校验 256-bit Token 后派生 server.py
│  app/server.py             ──► 原生 21 个桌面工具 + Per-Monitor V2 物理像素感知
└─────────────────────────────────────────────────────────────────────────────────────────────
```

| 文件 | 运行位置 | 作用 |
|---|---|---|
| `local_proxy.py` | 本机 | MCP `stdio` 懒连接代理；离线时毫秒级返回本地工具元数据，不阻塞宿主启动；调用时复用单条 SSH 转发长连接 |
| `session1_daemon.py` | 远端交互会话 | 回环守护进程按连接校验本进程的随机令牌，转发每个请求前检查桌面仍处于活动状态 |
| `ensure_daemon.ps1` | 远端 | 检查 `daemon_state.json` 存活状态，按需在当前交互式桌面会话拉起 `session1_daemon.py` |
| `build_bundle.py` | 本机（构建期） | 从本机 Python 环境离线提取免安装绿色包（`pythonXY.zip` + `_pth` 严格隔离 + `Pillow` + 插件源码）并做纯净环境自检 |
| `sync_release.py` | 本机（运维期） | 打包 `remote/bundle/` 并通过 `scp` + Windows 内置 `tar` 同步至远端目录，可选执行只读桥接健康检查 |

## 安全与工程边界

1. **零公网/局域网端口暴露**：`session1_daemon.py` 硬编码绑定 `127.0.0.1`，不监听局域网或虚拟网卡接口；跨机流量全程走 SSH 加密隧道。
2. **桌面身份与状态文件**。优先选择活动控制台，只有一个活动桌面时也可选择 RDP 会话。复用守护前核对进程的用户 SID、会话 ID、程序路径和监听端口的所有者。令牌写入目标用户配置文件下受保护的目录，访问权限限于该用户、SYSTEM 和本机管理员。新任务使用交互用户的普通运行级别。
3. **路径与仓库洁净**：构建产物 `remote/bundle/`（约 25~35 MB）与临时归档 `.tmp-*.zip` 均已被仓库 `.gitignore` 忽略，不会污染 Git 历史。
4. **生命周期可回收**：客户端断开即向对应 `server.py` 发送 EOF 回收全部辅助进程；无活跃连接超过 `--idle-timeout`（默认 900 秒）后守护进程自动退出并清理 `daemon_state.json`。
5. **写操作确认**。远端从机器级环境变量 `JUZI_WIN_DSH_CONFIRM_MODE` 和 `JUZI_WIN_DSH_ALLOWLIST` 读取策略，默认 `always`。代理省略参数时继承远端策略。客户端可提高确认级别，双方均设允许清单时按进程名取交集。修改机器策略后应关闭已有桥接连接，再重新连接。
6. **断线处理**。连接尚未发送请求时可重连，已发送的只读查询可重试一次。点击、输入、批处理及未知工具在发送后失去响应时返回 `remote_outcome_unknown`，调用方应先核对桌面状态。

## 快速上手

### 1. 构建并同步远端绿色便携包

本机需配置到远端 Windows OpenSSH Server 的公钥登录。远端 Windows PowerShell 5.1 的执行策略须允许项目随包提供的本地脚本，SSH 账户须有权注册目标用户的交互计划任务。可在 SSH 配置中给主机设置别名，例如 `friend-pc`。

```powershell
# 仅在本机离线构建并做隔离环境自检（不连远端）
C:\Python314\python.exe plugins\juzi-win-dsh\remote\build_bundle.py

# 构建并同步至远端主机 C:\ProgramData\RemoteWinMCP，同时执行只读桥接校验
C:\Python314\python.exe plugins\juzi-win-dsh\remote\sync_release.py --ssh-target friend-pc --verify-bridge
```

### 2. 在本机注册 MCP 服务

同步会把新包解压到安装根目录下独立的 `releases/<编号>/`，核对 SHA-256 并实际启动候选 MCP。指定 `--verify-bridge` 时还会通过该候选版本读取工作区大小。全部通过后才原子更新 `releases/active-release`。验收失败返回非零退出码，原活动版本和已有连接继续使用原文件。需要回滚时，用上一份已验证的协议 2 构建包重新执行同步验收；已连接的客户端在重连后进入新活动版本。

从平铺目录旧版迁移时，先关闭旧代理并等旧守护退出，再用新版构建和同步一次，随后启动新版代理。新版代理要求协议 2。同步不会覆盖旧平铺目录，旧版的公共状态文件也不会用于新版鉴权。

在 MCP 客户端配置中指向本机 `remote/local_proxy.py`：

```json
{
  "mcpServers": {
    "friend_win": {
      "command": "C:\\Python314\\python.exe",
      "args": [
        "D:\\Tools\\AI\\Juzi-Skill\\Juzi-DSH-Plugins\\plugins\\juzi-win-dsh\\remote\\local_proxy.py",
        "--ssh-target",
        "friend-pc",
        "--remote-root",
        "C:\\ProgramData\\RemoteWinMCP",
        "--server-name",
        "friend_win",
        "--confirm-mode",
        "always"
      ]
    }
  }
}
```

也支持通过环境变量配置：`JUZI_WIN_REMOTE_SSH_TARGET`、`JUZI_WIN_REMOTE_ROOT`、`JUZI_WIN_REMOTE_SERVER_NAME`、`JUZI_WIN_DSH_CONFIRM_MODE`、`JUZI_WIN_DSH_ALLOWLIST`。

## 测试验收

```powershell
# 运行远程桥本地回环与协议回归测试（无需真实远端机器，不移动鼠标/不写剪贴板）
C:\Python314\python.exe plugins\juzi-win-dsh\tests\remote_test.py
```
