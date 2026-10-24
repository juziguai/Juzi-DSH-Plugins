# dsh-ultra-effort

给 DeepSeek Harness（DSH）输入框做的「Ultra 推理档位」控件：把模型选择 + 思考强度做成
一枚座位，强度面板是紫色渐变轨道 + 星点动画 + "Ultra" 标题，副标题提示"使用额度消耗更快"。

## 模型版本角标

Ultra 0.2.2 内置模型版本角标，模型选择、强度滑块、动效和日期角标只需安装本插件。标签直接调用内部组件，不声明或依赖额外标签插槽。搜索与抓取仍为独立插件。

已有用户：升级 Ultra → 验证角标和动效 → 停用旧 Model Version Badge。旧包暂时仍启用也不会产生重复角标；完整迁移与回退见 [迁移指南](../../docs/ultra-migration.md)。

## 源码与构建

- `src/client.template.js`：模型菜单、交互与生命周期。
- `src/styles.mjs`：现有样式和动效。
- `src/model-label.mjs`：纯展示角标组件。
- `src/model-versions.json`：随包快照版本表。
- `build/client.mjs`：无第三方依赖的离线构建，生成自包含 `lib/client.js`。

在仓库根目录运行 `npm run client:build`，`npm test` 会检查生成物漂移。更新版本数据时，从本插件目录运行 `powershell -NoProfile -File build/update-versions.ps1`，该命令联网读取官方价格页、更新 JSON 并构建；常规构建与运行期间不联网更新版本。

## 来源

Fork 自 [`@domitor-syh/dsh-ui-skin-switcher@0.2.5`](https://github.com/domitor-syh/dsh-ui-skin-switcher)（MIT）。
上游已经实现：模型分组菜单、`conversation.input.model` 槽位接管、`modelDirectories` /
`session.selectModel` 提交、逐模型记忆强度、最高档点阵动画。初始分支的改动如下（后续交互与内置角标演进见上文及 V2 记录）：

| 改动 | 位置 |
|---|---|
| 模块 id 改为 `@juzi/dsh-ultra-effort` | 客户端模块声明 |
| 标题位改成「⚡ Ultra」+ 副标题「使用额度消耗更快」 | 强度面板 titleRow |
| 紫色渐变轨道、星点动画、白色发光旋钮、Ultra 渐变字 | 注入的 `ULTRA_CSS` |

初始版本沿用上游数据通道；当前版本在此基础上维护交互和内置角标。

## V2 重构（2026-10-22）

在 forked 代码上做的结构性改造（不再只是换皮）：

| 能力 | 实现 |
|---|---|
| 三栏头部 | `CSS Grid: 28px / 1fr / 28px`，左闪电、中「Ultra + 模型名 + chevron」、右重置；中栏始终居中（实测偏移 0px） |
| 面板内模型菜单 | 点模型名在面板内切换到列表：标题「选择模型」+ 真实目录分组 + 当前项 ✓ + 悬停高亮 + 滚动 |
| 重置 | 读取当前模型 `reasoning.defaultEffort` 回写；已是默认时只做视觉反馈、不发请求；不动模型 |
| 端点动画 | 进入最高档触发一次：手柄 `ue-pop` 260ms + 右侧 `ue-glow` 520ms + 粒子 `ue-boost` 620ms；保持不重播，离开后重新武装 |
| 粒子 | 12 个纯 CSS 光点，不同位置/大小/延迟，`ue-twinkle` 3.4s 循环；不参与 React 状态 |
| 手柄反馈 | 拖动时 `scale(1.14)` + 阴影增强；最高档常驻紫色光环 |
| 键盘 | 滑杆 `role="slider"`，方向键逐档、Home/End 到两端；`aria-valuemin/max/now/valuetext` |
| 无障碍 | 重置/模型按钮均有 `aria-label`/`aria-expanded`；`:focus-visible` 描边 |
| 减少动画 | `prefers-reduced-motion: reduce` 下关闭全部 keyframes，保留静态状态（最高档光圈） |
| 响应式 | 1100px 视口下不溢出、不产生横向滚动 |

根因修复：`inMax` 原先取自「提交后稳定下来的显示档位」（要等 `selectModel` 往返），导致端点动画滞后且无法重播；改为跟随交互位置（hover/drag），动画即时且幂等。

截图：`docs/v2-mid.png`、`docs/v2-max.png`、`docs/v2-burst.png`、`docs/v2-menu.png`。

## 文件

| 文件 | 作用 |
|---|---|
| `lib/index.js` | 宿主半身（空 `apply`，只为了让 loader 发现插件行） |
| `lib/client.js` | 生成的自包含浏览器入口，发布时随包携带 |
| `package.json` | `dsh.bundle.patch` + `dsh.client.inject` 声明 |
| `cordis.patch.yml` | 往 profile 插入 `ui-ultra-effort` 行 |
| `archive/legacy-patches/apply-v2.ps1` | V2 结构改造脚本（历史记录，不作为构建入口） |
| `archive/legacy-patches/patch-client.ps1` | V1 皮肤补丁脚本（历史） |
| `LICENSE` | 上游 MIT 许可证 |

## 安装

本地路径安装（profile 已配好，一般不需要再执行）：

```powershell
dsh plugin --profile web add "D:\Tools\AI\Juzi-Skill\Juzi-DSH-Plugins\plugins\dsh-ultra-effort"
```

桌面端 profile 走 `link:` 依赖：

```json
"@juzi/dsh-ultra-effort": "link:D:/Tools/AI/Juzi-Skill/Juzi-DSH-Plugins/plugins/dsh-ultra-effort"
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

## 维护入口

当前实现维护于 `src/`，通过 `npm run client:build` 生成 `lib/client.js`。`archive/legacy-patches/` 仅保留历史材料，禁止按版本依次重放；它们依赖当时的代码和路径，不能构建当前版本。
