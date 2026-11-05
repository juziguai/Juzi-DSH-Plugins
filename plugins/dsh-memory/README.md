# DSH Memory · 记忆

`@juzi/dsh-memory` **0.2.0**，面向 DSH **0.2.2-rc.1**（`engines.dsh` 与宿主 peer 均为 `>=0.2.2-rc.1 <0.2.3`），通过官方 MCP stdio 连接 LocalMemory 2.0.0 / schema7。0.1.0 只适用于 DSH 0.2.1，不能在 0.2.2 上继续使用；不要降级桌面端。新增左侧记忆管理、设置中的独立采集／召回开关及会话右侧本轮记录；候选没有页面批准能力。

## 本地配置

先在独立 `DSH_HOME`、profile 和空库验证，勿直接替换生产 profile。在 DSH「插件 → 添加插件 → 安装第三方插件」中安装本地目录或打包后的 `.tgz`；包中声明的宿主 peer 依赖需由官方安装器解析。目录与 tarball 相互切换后若仍报旧来源路径，保存错误并正常重启该测试 Web 后复验。

安装后，备份当前 profile 的 `cordis.patch.yml`，在其中合并以下按组件 ID 更新的可信配置；已有同 ID 配置时更新原项。随后从 UI 启用插件。这里不使用 `insert`，也不覆盖 `disabled`：组件由包自带的 bundle 注册，避免外加组件绕过 UI 停用。

```yaml
- id: juzi-memory
  name: '@juzi/dsh-memory'
  config:
    coreEntry: 'D:/path/to/LocalMemory/src/interfaces/cli/index.js'
    memoryRoot: 'D:/isolated-memory'
    coreConfig: 'D:/isolated-memory/config.json'
    timeoutMs: 2500
```

三条路径仅由可信本地 Host 配置给出；页面不能设置可执行文件、数据路径或任意工作目录。未配置连接时页面仍可打开并显示配置提示。旧库须先在副本显式迁移，不自动升级。

设置保存在当前 `DSH_HOME/plugins/juzi-memory.json`。自动采集、自动召回默认各自关闭；UI从宿主已知会话获取工作目录，用户指定稳定项目ID后绑定；同名目录不自动共享。可显式选择global；项目读取全局偏好与写全局权限分开。

## 通讯与生命周期

页面使用 DSH 原生同源 `/api/juzi.memory.*` 通道。Host 在隔离上下文挂载 SystemPrompt、不带配置的 ToolRuntime，以及 `@deepseek-ai/dsh-tool-executor-native`，再接官方 MCP 客户端。每连接启动固定scope；首次描述schema的连接随即释放，最多3个实际范围的按需连接，满额时淘汰最久未用连接（暂无空闲定时释放），卸载统一关闭。不会启动Worker或工作队列。

0.2.2 起 `ToolRuntime` 的 `mode` 为 never，`{ mode: 'native' }` 会被配置校验拒绝；原生执行改由独立 executor 调用 `tools.setExecutor`。`tools.execute` 只接受完整批次：`calls` 的每一项为 `{ type: 'tool-call', id, name, arguments }`，`arguments` 必须是 `JSON.stringify` 后的原始 JSON 字符串，取消信号放在批次上。成功或失败都取 `results[0].result`（仍看 `isError`、`error.message`、`content` 与 `value.structuredContent`）。沿用 0.2.1 的单次 `{ callId, name, arguments, signal }` 会得到 `Tool batch execution failed`。采集签名仍由 Host 密钥在字符串化之前计算，页面不能设置路径。

模型工具 `memory_query/get/remember/correct/forget/feedback` 从原MCP schema生成，Host按 `exec.agent.session`及原生回合记录绑定scope，召回、工具与采集使用同一范围。运行中改绑下一回合生效，右侧显示当前及待生效范围；缺失可信回合绑定时拒绝记忆操作。模型没有capture签名密钥或approve工具。MCP进程内写入身份为DSH客户端，非独立Agent凭证，不能视为多用户安全隔离。

每个新实际输入ID召回一次；后续模型请求检查scope revision和Core返回的next_change_at，修订变化、自然到期或未来生效时重选，空缓存同样刷新；未变快照保留一份。首次握手和工具调用均有截止时间与取消；Core错误码原样返回。只注入当前有效且已通过本地审核的事实，预算以字符计，无匹配返回空。原生`surfaceOp.replace`移除本插件拥有的旧活动快照；保留不可变原日志，不使用DOM补丁或自定义回放解释器。

右侧分别显示当前可用快照和本轮最近一次注入。每次模型请求前会重新校验快照。历史记录表示宿主接受了注入。快照替换及卸载后，原始聊天、已发送内容及宿主历史保留。

`turn/end`仅为内存提交通知；必须`ctx.sessions.flush(session)===true`才采集。保存用户／助手角色、工具调用及结果、原生session/seq/时间；PTC子调用保留配对及父调用JSON证据，孤立结果保留为经历。批次按128事件与1MiB UTF-8预算分片。跳过插件注入、记忆工具结果和继承fork事件。回执幂等键从稳定事件内容生成；失败显式显示，可重试本轮，无持久队列和静默自动重写。

证据保存与候选提炼分阶段原子提交。单次提炼最多新增128个候选，复用已有事实不占新建预算，剩余项明确返回partial及pending原因；右侧分别显示证据、候选、复用、待提炼及拒绝数，可续做未完成提炼。同一请求重试不重复保存证据或已完成候选；旧格式回执可补齐漏提炼项。可信批量提炼不消耗模型交互限额，交互写入仍按身份和项目限制10条/分钟、200条/天；候选始终需要本地审核。

纠正／遗忘建议先dry_run预览目标、scope及expected_version（当前实现不强制预览，可直接执行）；保护对象进入既有本地CLI审核。候选不会因为存在引用就语义已证实；所有采集、证据校验、审核、版本和事务规则留在Core。

## 验证与回退

仓库默认 `npm test` 使用离线用例，其中记忆用例16项，不加载真实 DSH。`scripts/memory-native.mjs` 仍按 0.2.1 安装 `ToolRuntime { mode: 'native' }`，不能用来验收 0.2.2。

MateBook 桌面端已是 DSH 0.2.2-rc.1 时，合并后做隔离冒烟，不要降级宿主：

1. 使用独立 `DSH_HOME`、独立 profile 和空库，不要覆盖生产 profile。先停用已安装的旧 `@juzi/dsh-memory`。目录与 tarball 互相切换后若仍报旧来源路径，保存错误并正常重启该测试 Web 后再装。
2. 二选一安装本版本 0.2.0：
   - 目录：DSH「插件 → 添加插件 → 安装第三方插件」，选择仓库中的 `plugins/dsh-memory`。
   - tarball：在仓库根目录执行 `npm pack ./plugins/dsh-memory`，再安装生成的 `juzi-dsh-memory-0.2.0.tgz`。
3. 宿主安装器需解析 peer。0.2.2-rc.1 已随桌面端提供 `@deepseek-ai/dsh-tool-executor-native` 以及其余 `@deepseek-ai/dsh-*` 包，不要单独降级这些包。
4. 按上文把绝对路径写入 profile 的 `cordis.patch.yml` 后从 UI 启用。冒烟只确认插件能加载（不再因 `mode: 'native'` 被拒绝），一次记忆调用不再报 `Tool batch execution failed`，未配置连接时页面仍只显示配置提示。通过后再考虑生产 profile。

实际 stdio 与原生 Web 装配仍应在隔离数据和独立 `DSH_HOME` 中验证。0.1.0 的修复记录在 LocalMemory 的 `doc/process/MEMORY-REVIEW-FIXES-2026-11-04.md`。

卸载前关闭自动召回并等待下一请求清除插件拥有的快照；正常插件dispose也清理仍存活会话的活动快照并释放MCP资源。崩溃／强杀无法保证dispose执行；恢复时需加载插件清理或新建会话。撤销插件源码不回退数据库；schema回退使用匹配旧源码的旧备份，不能旧程序写schema7。
