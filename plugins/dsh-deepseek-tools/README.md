# @juzi/dsh-deepseek-tools

把 **DeepSeek 官方 Search / Fetch** 两个只读 HTTP 接口封装成本地 MCP（stdio）服务，
供 Claude Code / Codex / DeepSeek Harness 等客户端直接调用，并统计成功次数给 HUD 展示。

## 工具

| 工具 | 完整调用名 | 说明 |
|---|---|---|
| `DeepSeek-Search` | `mcp__deepseek__DeepSeek-Search` | 调 `POST /v1/tools/search`，返回标题 / URL / 摘要 / 发布时间 / `authority` / `rerank_score`；支持 `site:`、`-site:`、`"精确短语"`、`lang:`、`after:` / `before:` |
| `DeepSeek-Fetch` | `mcp__deepseek__DeepSeek-Fetch` | 调 `POST /v1/tools/fetch`，把单个网页转成 Markdown |

两者都只读，不会修改任何远端状态。

## 安装

```powershell
C:\Python314\python.exe -m pip install -r requirements.txt
```

## 鉴权

按以下顺序解析，命中即止，全程不落盘、不打印：

1. 环境变量 `DEEPSEEK_API_KEY`
2. 环境变量 `ANTHROPIC_AUTH_TOKEN`（本机与上面是同一把 Key）
3. Windows 注册表 `HKCU\Environment\DEEPSEEK_API_KEY`
4. Windows 注册表 `HKLM\Environment\DEEPSEEK_API_KEY`
5. Windows 注册表 `HKCU\Environment\ANTHROPIC_AUTH_TOKEN`
6. Windows 注册表 `HKLM\Environment\ANTHROPIC_AUTH_TOKEN`

第 3/4 级是必需的兜底：部分宿主（例如 DSH 的 `dsh-mcp-client`）在 spawn stdio 子进程时会
**删除名字匹配 `/KEY|PASSWORD|SECRET|TOKEN/i` 的环境变量**，只靠环境继承会直接报
`missing_api_key`。

## 注册到客户端

### Claude Code（`~/.claude.json`）

```json
"deepseek": {
  "type": "stdio",
  "command": "C:\\Python314\\python.exe",
  "args": ["D:/Tools/AI/Juzi-Skill/Juzi-DSH-Plugins/plugins/dsh-deepseek-tools/server.py"],
  "env": {}
}
```

### DeepSeek Harness（`~/.dsh/profiles/desktop/cordis.patch.yml`）

`dsh-mcp-client` 每台服务器一条配置项。注意本 loader 的顶层 patch 是
**按 id 覆盖已有条目**，新增必须写在 `insert:` 下，否则会报
`patch: entry "xxx" not found`：

```yaml
- insert:
    - id: mcp-deepseek-tools
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: deepseek
        transport: stdio
        command: 'C:\Python314\python.exe'
        args:
          - 'D:\Tools\AI\Juzi-Skill\Juzi-DSH-Plugins\plugins\dsh-deepseek-tools\server.py'
        cwd: 'D:\Tools\AI\Juzi-Skill\Juzi-DSH-Plugins\plugins\dsh-deepseek-tools'
        toolCallTimeoutMs: 90000
        failOnStartupError: false
```

独立 MCP 配置样例见仓库根目录 `deploy/dsh-mcp-deepseek.patch.yml`；不要与本插件同时启用同名服务。改完保存即会触发 profile 热重组，
工具以 `mcp__deepseek__DeepSeek-Search` 形式出现在工具列表；没出现就重启桌面端。

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `DEEPSEEK_API_BASE` | `https://api.deepseek.com` | 网关地址，测试时可指向本地 mock |
| `DEEPSEEK_TOOLS_TIMEOUT` | `60` | 单次请求超时秒数；非数字会告警并回退 60（不再导致启动失败） |
| `DEEPSEEK_TOOLS_RETRIES` | `1` | 追加重试次数（0~3），只对 408 / 425 / 429 / 5xx 与超时生效 |
| `DEEPSEEK_USAGE_PATH` | `<CLAUDE_CONFIG_DIR 或 ~/.claude>/deepseek-tools-usage.json` | 计数文件位置 |

## 用量统计

`usage_store.py` 用「锁文件 + 同目录临时文件 + `os.replace`」做跨进程原子读改写，
多个客户端同时跑也不会丢计数；锁带 5s 等待超时与 15s 陈旧锁清理。

计费口径与官方一致：**HTTP 200 且 Search 的 `results` 非空 / Fetch 的 `content` 非空**才算一次成功。

```json
{
  "version": 1,
  "search": {"success": 10, "last_success_at": "2026-10-21T11:25:06Z"},
  "fetch":  {"success": 3,  "last_success_at": "2026-10-17T16:10:01Z"},
  "updated_at": "2026-10-21T11:25:06Z"
}
```

`claude-hud` 的 `src/deepseek-usage.ts` 读同一个文件，按 **5 元 / 1000 次**折算展示。

> 官方口径：2026-11-01 00:00（北京时间）前，经 API 调用 Search/Fetch 未计费；
> 之后按 5 元 / 1000 次成功请求收费，HUD 显示的名目金额从那时起才是真实账单。

## 测试

```powershell
C:\Python314\python.exe test_usage.py     # 计数 / 8 进程并发 / 持久化 / 清理
C:\Python314\python.exe smoke_test.py     # 真 MCP 客户端端到端（写临时计数，不污染真实数据）
$env:SMOKE_REAL=1; C:\Python314\python.exe smoke_test.py   # 写真实计数，验收 HUD 全链路
```

`smoke_test.py` 会真的联网调一次 Search 与 Fetch（各计一次费用，若已进入收费期）。

## 文件

| 文件 | 作用 |
|---|---|
| `server.py` | FastMCP 服务；stdout 只走协议，日志全走 stderr |
| `usage_store.py` | 并发安全计数，可单独运行查看当前计数 |
| `test_usage.py` | 计数与并发测试 |
| `smoke_test.py` | 端到端冒烟 |

## 排错

| 现象 | 原因 / 处理 |
|---|---|
| `missing_api_key` | 六级来源都没拿到 Key；先 `setx DEEPSEEK_API_KEY sk-xxx` 再重启客户端 |
| `http_error 401` | Key 无效或已撤销 |
| `http_error 402` | 余额不足 |
| `http_error 403` | Fetch 被目标站安全策略拒绝，换 URL，重试无用 |
| `http_error 404` | Fetch 拿不到可用正文（页面为空 / 非 HTML / 被拦截），重试无用 |
| `http_error 429` | 触发 QPS：Search 100 QPS、Fetch 25 QPS（按账号，非按 Key） |
| 计数文件损坏 | `usage_store` 会自动改名为 `*.corrupt-<ts>` 备份后归零重来 |

## DSH 插件入口

推荐按仓库根目录 `docs/development.md` 安装 `@juzi/dsh-deepseek-tools` 并加入 bundle 列表。插件使用官方 MCP 客户端管理 Python 子进程，服务路径相对于插件自动解析。

配置项：`python`（默认 `python`，可指定虚拟环境解释器绝对路径）。在 profile patch 中以 `id: juzi-deepseek-tools` 覆盖 `config.python`。运行前用该解释器安装本目录的 `requirements.txt`。宿主必须提供兼容的 `@deepseek-ai/dsh-mcp-client`（已核验 0.2.1-rc.2）。

本页 Python 命令均在插件目录执行。独立 MCP 配置与 DSH 插件是两种可选接入方式，不要重复注册 `deepseek`。
