# dsh-ultra-effort

给 DeepSeek Harness（DSH）输入框提供模型选择、推理强度滑块、紫色星点动效、模型版本角标，以及按会话开启的快速执行（实验）。

## 快速执行（实验）

Ultra 0.3.0 需要 DSH **0.2.1-rc.3 或更新版本**；当前离线集成验证基线为 0.2.1-rc.3，后续宿主版本仍需复核接口。该功能默认关闭，打开强度面板后，左侧闪电可通过点击或键盘切换。后台确认保存后以暖色显示开启；右侧重置仍只重置推理强度。

- 只保存当前主会话的选择，同一会话恢复后继续使用；新会话和分叉会话默认关闭。
- 空闲时切换，下一轮生效。每轮开始冻结策略，运行中其他窗口修改设置也不会改变本轮。
- 在系统提示中要求合并独立读取、复用仍有效的证据、精简重复叙述，同时保留依赖顺序、必要验证和关键进度。执行仍由 DSH 原生工具与权限控制。
- 不切换模型、不降低 Max、不调整服务商计费档位、不自动取消长命令。它是执行流程优化，不代表服务商付费加速，尚未证明真实任务有稳定速度收益。
- 写入冲突会重新读取并提示；超时或断线会核对后台结果，原写入尚未结束时禁止重复提交。后台不可用或只读时显示原因，模型菜单与强度控件仍可使用。

设置保存在 Ultra 的正式 Settings namespace 中，字段为 `fastSessions`（会话 ID 到布尔值），无需手动编辑。只写单个会话字段，不读取 API key，不新增遥测或性能日志。自定义完整系统提示可能屏蔽插件的补充提示，应在对应预设中单独验证。

客户端通过 Cordis 的 `ctx.get('remote.settings')` 读取可选设置服务。不能使用未声明依赖的 `ctx.remote.settings` 点号访问，也不能把该服务变成整个模型控件的强制依赖。

验收：打开闪电 → 确认仍为原模型与 Max → 执行一轮任务 → 换到新会话确认默认关闭 → 回到原会话确认恢复。实际执行效果与速度需在 DSH 中另行验收；离线测试不调用模型 API。

回退时先关闭快速执行；需要恢复旧宿主兼容时安装先前已验证的 Ultra 0.2.4。旧入口能忽略新增偏好，无需重置整个 profile；模型选择、动效与角标应一起复核。

## 模型版本角标

Ultra 0.2.2 内置模型版本角标，模型选择、强度滑块、动效和日期角标只需安装本插件。标签直接调用内部组件，不声明或依赖额外标签插槽。搜索与抓取仍为独立插件。

已有用户：升级 Ultra → 验证角标和动效 → 停用旧 Model Version Badge。旧包暂时仍启用也不会产生重复角标；完整迁移与回退见 [迁移指南](../../docs/ultra-migration.md)。

## 源码与构建

- `src/client.template.js`：模型菜单、交互与生命周期。
- `src/styles.mjs`：现有样式和动效。
- `src/model-label.mjs`：纯展示角标组件。
- `src/model-versions.json`：随包快照版本表。
- `src/fast-control.mjs`：快速执行的设置回执与异常状态机，内联到客户端。
- `lib/fast-mode.js`、`lib/fast-state.js`、`lib/fast-policy.js`：Host 能力、轮次快照与执行提示。
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
| `lib/index.js` | 正式 Config 与可选 Host 能力挂载；缺少后台服务不阻断模型界面 |
| `lib/client.js` | 生成的自包含浏览器入口，发布时随包携带 |
| `package.json` | `dsh.bundle.patch` + `dsh.client.inject` 声明 |
| `cordis.patch.yml` | 往 profile 插入 `ui-ultra-effort` 行 |
| `archive/legacy-patches/apply-v2.ps1` | V2 结构改造脚本（历史记录，不作为构建入口） |
| `archive/legacy-patches/patch-client.ps1` | V1 皮肤补丁脚本（历史） |
| `LICENSE` | 上游 MIT 许可证 |

## 安装

本地路径安装（profile 已配好，一般不需要再执行）：

Ultra 0.3.0 新增官方 `@deepseek-ai/schemastery@3.18.5` 运行依赖。市场 / `file:` 安装由包管理器解析；使用源码 `link:` 时，先在本插件目录运行 `npm install --ignore-scripts --package-lock=false`，再交给 DSH 安装。

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
- 桌面端：优先使用客户端原生插件管理器安装并确认加载状态；已在 DSH 0.2.1-rc.3 验证原生热替换，无须重启。若当前宿主提示需要重启，请先等待正在运行的会话结束，再由用户决定重启。

## 已知限制

- 只在模型声明了 `reasoningEfforts` 时出现强度滑块；没声明就只显示模型按钮。
- 与上游一样以 `priority: -1` 注册到 `conversation.input.model`，同一 profile 里不要同时启用
  `@domitor-syh/dsh-ui-skin-switcher`，否则两个座位会抢同一个槽位。

## 维护入口

当前实现维护于 `src/`，通过 `npm run client:build` 生成 `lib/client.js`。`archive/legacy-patches/` 仅保留历史材料，禁止按版本依次重放；它们依赖当时的代码和路径，不能构建当前版本。
