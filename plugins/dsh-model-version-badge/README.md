# @juzi/dsh-model-version-badge

把 DeepSeek Harness 输入框里的模型角标换成**结构化版本角标**：显示官方文档公布的快照日期（MMDD），鼠标悬停显示完整官方模型名。

官方原本的 `1017` 角标是 `@deepseek-ai/dsh-client-ui-deepseek-model-label-1017` 里硬编码的固定字符串，只覆盖 Flash 一个模型。本插件复刻它的 slot 机制，但数据来自官方文档表格，并覆盖所有已公布版本的模型。

## 数据来源

```
https://api-docs.deepseek.com/zh-cn/quick_start/pricing
  表格「模型」行     → 调用名（如 deepseek-flash、deepseek-v4-pro）
  表格「模型版本」行 → 官方完整快照名（如 DeepSeek-V4.1-Flash-1017）
  脚注 (1)           → 旧模型名别名（deepseek-v4-flash 等仍由同一快照提供服务）
```

当前解析结果：

| 调用名 | 官方模型版本 | 角标 |
|---|---|---|
| `deepseek-flash` | DeepSeek-V4.1-Flash-1017 | `1017` |
| `deepseek-v4-pro` | DeepSeek-V4-Pro-0813 | `0813` |
| `deepseek-v4-flash`（旧名） | DeepSeek-V4.1-Flash-1017 | `1017` |
| `deepseek-v4-flash-vision-exp`（旧名） | DeepSeek-V4.1-Flash-1017 | `1017` |

角标直接取官方版本名末尾的 4 位 MMDD 原文（`1017` / `0813`），不插入分隔符。悬停显示完整官方名。

## 机制

0.1.1 版标签集成：

1. 浏览器侧向官方 `conversation.input.model.label` 和 Ultra `juzi.ultra.model.label` 分别注册纯展示组件
2. 使用优先级 -1 覆盖官方默认角标，无须停用官方插件；禁用本插件后官方显示恢复
3. 组件拿到 `provider` / `model` 两个 props，只做查表，不发请求、不缓存、不改模型选择
4. 在对应控件内同时作用于三处：输入框触发按钮、菜单当前值行、模型选项行
5. 查不到映射时原样返回 `model.name`（无角标）

与官方的差异：

- 官方是 `if (provider in [...] && model.id === 'deepseek-flash' && model.name === 'DeepSeek-V4.1-Flash')` 的三重硬编码判断；本插件按 `model.id` 查表，天然支持多模型
- 官方角标文案来自 locale 字典；本插件直接用数据里的日期
- 官方使用 `Tag` 原语；本插件用内联样式复刻同款蓝色胶囊（避免依赖内部原语包）

## 安装

```powershell
# 1. 生成版本表 + 写 lib/client.js
powershell -NoProfile -ExecutionPolicy Bypass -File .\build\update-versions.ps1

# 2. 装进 web profile
dsh plugin --profile web add "link:D:/Tools/AI/Juzi-Skill/Juzi-DSH-Plugins/plugins/dsh-model-version-badge"

# 3. 与 Ultra 一起使用时，Ultra 需为 0.1.2 或更新版本
```

注意：`dsh plugin add` 在 Windows 上必须用 `link:D:/...`（正斜杠）或 `file:` 加正斜杠；用 `file:D:\...` 会被 pnpm 当成相对路径。

## 更新版本数据

官方发新版本（或改表结构）后执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build\update-versions.ps1
# 需要走代理时：
powershell ... -File .\build\update-versions.ps1 -Proxy http://127.0.0.1:8889
```

脚本用模板与生成的 `VERSIONS` 表重写整个 `lib/client.js`，不改 `cordis.patch.yml`。更新后重启 dsh web。

失败处理：若官方页面改版导致表格行匹配失败，脚本会直接抛错（`table rows not found`），不会写入半成品。

## 已知限制

- 角标只显示 MMDD，不含年份（官方表格本身不给年份，避免自行推断）
- 无障碍文字（aria）仍是原始模型名，角标只在视觉层
- 官方若把日期标记改成结构化字段（例如 `/models` 接口新增版本字段），应优先改用接口字段，本插件可退化为纯数据映射
- 仅供本地私有 profile 使用，未发布到 npm

## 目录

```
package.json              # dsh.client 声明（web 平台 + inject）
cordis.patch.yml          # bundle 层：insert ui-model-version-badge
lib/index.js              # host 半侧：空实现（只为让 Loader 看到包）
lib/client.js             # 浏览器半侧：由模板生成，勿手改
build/client.template.js  # 模板，含 __VERSION_MAP__ 占位符
build/update-versions.ps1 # 抓页面 → 解析 → 生成 client.js
```
