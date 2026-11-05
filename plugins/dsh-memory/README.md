# DSH Memory · 记忆

`@juzi/dsh-memory` **0.1.0**，面向 DSH **0.2.1-rc.3**，通过官方 MCP stdio 连接 LocalMemory 2.0.0 / schema7。新增左侧记忆管理、设置中的独立采集／召回开关及会话右侧本轮记录；候选没有页面批准能力。

## 本地配置

本包源码先在隔离 Home/profile 验证，不能直接替换生产 profile。无需新依赖、外部服务或付费 API；使用 DSH 已提供的 Cordis、Session、ToolRuntime 和 MCP 客户端。

```yaml
- insert:
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

页面使用 DSH 原生同源 `/api/juzi.memory.*` 通道。Host 使用私有 ToolRuntime + 官方 MCP 客户端，每连接启动固定scope；首次描述schema的连接随即释放，最多3个实际范围的按需连接，空闲连接可释放，卸载统一关闭。不会启动Worker或工作队列。

模型工具 `memory_query/get/remember/correct/forget/feedback` 从原MCP schema生成，Host按 `exec.agent.session`及原生回合记录绑定scope，召回、工具与采集使用同一范围。运行中改绑下一回合生效，右侧显示当前及待生效范围；缺失可信回合绑定时拒绝记忆操作。模型没有capture签名密钥或approve工具。MCP进程内写入身份为DSH客户端，非独立Agent凭证，不能视为多用户安全隔离。

每个新实际输入ID召回一次；后续模型请求检查scope revision和Core返回的next_change_at，修订变化、自然到期或未来生效时重选，空缓存同样刷新；未变快照保留一份。首次握手和工具调用均有截止时间与取消；Core错误码原样返回。只注入当前有效且已通过本地审核的事实，预算以字符计，无匹配返回空。原生`surfaceOp.replace`移除本插件拥有的旧活动快照；保留不可变原日志，不使用DOM补丁或自定义回放解释器。

右侧分别显示当前可用快照和本轮最近一次注入。每次模型请求前会重新校验快照。历史记录表示宿主接受了注入。快照替换及卸载后，原始聊天、已发送内容及宿主历史保留。

`turn/end`仅为内存提交通知；必须`ctx.sessions.flush(session)===true`才采集。保存用户／助手角色、工具调用及结果、原生session/seq/时间；PTC子调用保留配对及父调用JSON证据，孤立结果保留为经历。批次按128事件与1MiB UTF-8预算分片。跳过插件注入、记忆工具结果和继承fork事件。回执幂等键从稳定事件内容生成；失败显式显示，可重试本轮，无持久队列和静默自动重写。

证据保存与候选提炼分阶段原子提交。单次提炼最多新增128个候选，复用已有事实不占新建预算，剩余项明确返回partial及pending原因；右侧分别显示证据、候选、复用、待提炼及拒绝数，可续做未完成提炼。同一请求重试不重复保存证据或已完成候选；旧格式回执可补齐漏提炼项。可信批量提炼不消耗模型交互限额，交互写入仍按身份和项目限制10条/分钟、200条/天；候选始终需要本地审核。

纠正／遗忘先预览目标、scope及expected_version；保护对象进入既有本地CLI审核。候选不会因为存在引用就语义已证实；所有采集、证据校验、审核、版本和事务规则留在Core。

## 验证与回退

仓库默认 `npm test` 使用离线用例，其中记忆用例16项。需要真实已安装DSH原生API及stdio时，显式运行：

```powershell
node scripts/memory-native.mjs --core-root "D:/path/to/LocalMemory" --dsh-root "C:/path/to/node_modules/@deepseek-ai/dsh" --work "D:/new-isolated-validation"
```

work须不存在；只复制源码到测试目录并链接只读原生依赖，保留回执证据。该测试包含私有工具域、失效引用错误、提交后丢回执重连、Host密钥轮换、原生Session注入更新、回合改绑、有效期与空缓存、150项提炼续做、超时和取消释放及上下文失效后清理，不调用模型API。实际stdio与原生Web装配在隔离数据和独立DSH_HOME中验证；本轮修复记录在LocalMemory的`doc/process/MEMORY-REVIEW-FIXES-2026-11-04.md`。

卸载前关闭自动召回并等待下一请求清除插件拥有的快照；正常插件dispose也清理仍存活会话的活动快照并释放MCP资源。崩溃／强杀无法保证dispose执行；恢复时需加载插件清理或新建会话。撤销插件源码不回退数据库；schema回退使用匹配旧源码的旧备份，不能旧程序写schema7。
