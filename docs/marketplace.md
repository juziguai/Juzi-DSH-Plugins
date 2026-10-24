# 插件市场

市场使用 DSH 官方 format 1，三个插件均从本仓库的固定 Git 提交及子目录安装。
`marketplace/catalog.json` 维护展示信息；`marketplace/index.json` 是客户端读取的生成文件。
版本、引擎约束与入口来自指定提交中的清单，不读取未提交源码。Git 来源的发布时间取该源码提交时间。

## 添加与验收

在 DSH「插件 → 发现 → 索引源」添加本仓库 README 给出的原始 JSON 地址。
索引必须直接返回 HTTP 200，不得使用 GitHub 文件浏览页或重定向地址。

维护中的插件为 Ultra 与搜索；独立角标作为旧版入口保留。请逐个验收：

- Ultra 0.2.2：模型菜单、推理强度、动效和内置角标；不要同时启用上游 skin-switcher。
- 旧版独立角标：冻结为 0.1.1，新装请使用 Ultra；现有用户升级 Ultra 验收后停用旧包，见 [迁移指南](ultra-migration.md)。
- 搜索与抓取：先安装 Python 依赖、设置专用 `DEEPSEEK_API_KEY` 并配置解释器，再启用。不要与现有 `deepseek` MCP 服务重复注册。真实请求使用安装者自己的密钥。

搜索插件不再读取 `ANTHROPIC_AUTH_TOKEN`。凭证仅用于可信 HTTPS API 的鉴权头，拒绝所有重定向；不把上游错误体、错误头或网络异常原文转交模型。详见插件 README。

## 生成和校验

使用本机已安装 DSH 提供的官方 `dsh-plugin-market-index/lib/index.js`，不复制一份 schema：

```powershell
$env:DSH_MARKET_INDEX_MODULE = '<官方 dsh-plugin-market-index 包目录>/lib/index.js'
npm run market:build -- --repository https://github.com/juziguai/Juzi-DSH-Plugins --commit <完整源码提交SHA>
npm run market:check
```

生成器先验证清单入口、固定提交和官方索引规则，通过后才写文件。校验器同时核对展示目录与固定版本，能发现手工篡改版本或安装路径。

发布顺序：先提交并验证插件代码，再生成指向该提交的索引，提交索引后推送。索引不能指向包含它自身的提交 SHA，因此源码和索引分别提交。根目录版本独立递增，未改变的组件版本保持不变。

CI 执行离线测试与官方索引校验。发布后还须从最终 URL 获取 JSON，确认无重定向，并核实其 Git 提交与子目录可访问。格式通过不等于客户端已安装或真实 API 已验收。

## 更新和回退

插件更新先增加对应组件版本并验证，再生成新索引。发现列表右侧“有新版本”只打开已安装详情。应点击插件名称进入市场详情，在版本列表选择新版“安装”，无须先卸载；操作前记录原版本及配置。
若新版本出现问题，可将索引恢复为已验证的历史提交，并按客户端能力重新安装旧版；不要删除旧会话引用的 Agent 预设。
