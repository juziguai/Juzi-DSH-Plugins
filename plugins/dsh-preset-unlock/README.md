# 解锁模式 · @juzi/dsh-preset-unlock

一个**纯声明型** DSH 插件包：入口不注册工具、路由或客户端，只通过 `cordis.patch.yml` 声明 `@deepseek-ai/dsh-agent-preset`，让 DSH 的预设选择器里出现「解锁模式」。选中后由官方预设服务装配标准工具组。

该预设的人格来自 [`prompts/persona.md`](prompts/persona.md)，工具清单与官方 `standard` 预设同构。要求 DSH 0.2.1-rc.3 或更新版本，当前工具快照已与官方 rc.3 包逐字核对。

## 它到底改了什么

```yaml
- insert:
    - id: juzi-preset-unlock        # 自引用行：仓库检查器要求
      name: '@juzi/dsh-preset-unlock'
    - id: preset-unlock             # 真正的预设声明
      name: '@deepseek-ai/dsh-agent-preset'
      config:
        id: unlock
        name: 解锁模式
        order: 2
        plugins: [ ... 与 standard 一致的 22 行 ... ]
```

- 只新增一个预设条目，**不修改** `standard` 或其它既有预设。
- 只有手动选中「解锁模式」的会话才受影响；已有会话保持原装配。
- `order: 2` 决定它在选择器里的排序（`standard` 是 1）。

## 安装

在 DSH「插件 → 发现 → 索引源」添加本仓库索引后安装，或在本仓库根目录：

```powershell
dsh plugin --profile desktop add "github:juziguai/Juzi-DSH-Plugins#<commit>&path:/plugins/dsh-preset-unlock"
```

> ⚠️ **id 冲突**：如果你此前手写过同 id（`unlock`）的 `@deepseek-ai/dsh-agent-preset` 行，必须先删掉手写块再装本插件，否则同一个预设 id 会出现两份声明。
> 手写块位于 `$env:USERPROFILE\.dsh\profiles\desktop\cordis.patch.yml`，改前请先备份。

安装后重启 DSH 生效；在会话的预设选择器里选「解锁模式」。

安装只注册预设，不自动修改默认预设、会话权限或网络隔离。人格文本里的“离线”“沙箱”等措辞只是提示词，不会创建真实隔离环境；文件、命令与联网能力继续由 DSH 的工具和权限配置决定。

## 停用与回退

已有会话会记录预设 ID。停用或卸载本包后，引用 `unlock` 的会话再次恢复可能报 `Unknown agent preset: unlock`。需要继续这些会话时保留本包；不要同时删除其预设声明。发生该错误时先重新启用或安装本包，恢复相同 ID，再处理迁移。

回退可重新安装本包的旧版固定提交。仅修改人格不会更改预设 ID；不要通过改 ID 来覆盖已有会话的选择。

## 维护

### 改人格

唯一真源是 `prompts/persona.md`。以下维护命令在本仓库根目录执行；安装包不包含构建工具和官方源快照。改完重新生成补丁：

```powershell
npm run preset:build
npm run preset:check   # 校验生成物与源一致
```

**不要直接改 `cordis.patch.yml`** —— 它是生成物，下次构建会被覆盖。

### 跟进官方工具变化

`vendor/standard.patch.yml` 是官方 `standard` 预设的逐字快照（来自 DSH 安装包的 `@deepseek-ai/dsh-web-app/presets/standard.patch.yml`）。官方新增工具后，替换该文件再重新构建即可让「解锁模式」跟上：

```powershell
# 1. 从新版安装包取出官方标准预设（覆盖 vendor/standard.patch.yml）
#    路径示例：resources/app.asar → dsh/node_modules/@deepseek-ai/dsh-web-app/presets/standard.patch.yml
# 2. 重新生成
npm run preset:build
```

构建脚本会对三个结构锚点做校验（`- id: preset-standard`、`plugins:`、`persona` 的 `prefix:`），官方文件结构一变就直接报错，不会静默产出坏补丁。

## 边界

- 不包含任何 `.js` 业务逻辑：`lib/index.js` 是空实现的占位插件，仅为满足 bundle 自引用与加载契约。
- 不读网络、不读用户目录、不执行命令。
- 不修改 profile 的 `package.json`、`pnpm-lock.yaml` 或其它预设。
- 升级 DSH 桌面端不会覆盖本包所在仓库；升级后若官方插件包改名/删除，需同步更新 `vendor/standard.patch.yml`。

## 验证

```powershell
npm run preset:check
npm test           # 仓库级检查（含本包的清单、语法与生成漂移）
git diff --check
```

真实验收：装包 → 重启 DSH → 新会话选「解锁模式」→ 检查该会话的 `system/message` 是否以 `prompts/persona.md` 的正文开头。
