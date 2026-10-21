# dsh-ultra-effort

给 DeepSeek Harness（DSH）输入框做的「Ultra 推理档位」控件：把模型选择 + 思考强度做成
一枚座位，强度面板是紫色渐变轨道 + 星点动画 + "Ultra" 标题，副标题提示"使用额度消耗更快"。

## 来源

Fork 自 [`@domitor-syh/dsh-ui-skin-switcher@0.2.5`](https://github.com/domitor-syh/dsh-ui-skin-switcher)（MIT）。
上游已经实现：模型分组菜单、`conversation.input.model` 槽位接管、`modelDirectories` /
`session.selectModel` 提交、逐模型记忆强度、最高档点阵动画。本仓库只做了视觉层改造：

| 改动 | 位置 |
|---|---|
| 模块 id 改为 `@juzi/dsh-ultra-effort` | `lib/client.js` 第 2 行 |
| 标题位改成「⚡ Ultra」+ 副标题「使用额度消耗更快」 | 强度面板 titleRow |
| 紫色渐变轨道、星点动画、白色发光旋钮、Ultra 渐变字 | 注入的 `ULTRA_CSS` |

交互逻辑、数据通道、无障碍标签全部沿用上游，未改动。

## 文件

| 文件 | 作用 |
|---|---|
| `lib/index.js` | 宿主半身（空 `apply`，只为了让 loader 发现插件行） |
| `lib/client.js` | 浏览器半身：座位 UI + 滑块 + Ultra 皮肤 |
| `package.json` | `dsh.bundle.patch` + `dsh.client.inject` 声明 |
| `cordis.patch.yml` | 往 profile 插入 `ui-ultra-effort` 行 |
| `build/patch-client.ps1` | 重新打皮肤补丁时用的脚本（保留可复现） |
| `LICENSE` | 上游 MIT 许可证 |

## 安装

本地路径安装（profile 已配好，一般不需要再执行）：

```powershell
dsh plugin --profile web add "D:\Tools\AI\Juzi-Skill\Juzi-DeepSeek-Tools\dsh-ultra-effort"
```

桌面端 profile 走 `link:` 依赖：

```json
"@juzi/dsh-ultra-effort": "link:D:/Tools/AI/Juzi-Skill/Juzi-DeepSeek-Tools/dsh-ultra-effort"
```

并把 `@juzi/dsh-ultra-effort` 加进 `dsh.profile.bundles`，然后
`pnpm install`（用桌面端自带的 pnpm：`resources\runtime\primary-runtime\dependencies\pnpm`）。

## 生效条件

- Web：重启 `dsh web` 并刷新页面。
- 桌面端：重启桌面应用（客户端 bundle 只在启动时扫描 `dsh.client` 元数据）。

## 已知限制

- 只在模型声明了 `reasoningEfforts` 时出现强度滑块；没声明就只显示模型按钮。
- 与上游一样以 `priority: -1` 注册到 `conversation.input.model`，同一 profile 里不要同时启用
  `@domitor-syh/dsh-ui-skin-switcher`，否则两个座位会抢同一个槽位。
