# 模型列表 + 交互动画 · V10/V11 规格（dsh-ultra-effort）

> 对照：用户实机列表 `/workspace/dsh/user-model-list.png`；设置页三家提供商 `/workspace/dsh/user-providers.png`；滑杆区 V9 已验收风格。
> 范围：只改 `dsh-ultra-effort`；零构建；不改 API；不回退 V9。

## A. 现状问题
1. 分组标题全大写英文（DEEPSEEK…）像标签，与设置页「DeepSeek 账号 / DeepSeek / WorkBuddy」不一致。
2. 模型与提供商同级缩进，层次不清。
3. 行偏挤；描述半词砍断难看。
4. 列表过高；打开列表时高度硬切；chevron/触发器过渡弱。

## B. 信息架构（用户已确认 · 必须遵守）
1. **提供商单独成行小标题**：中文名优先，与设置页一致——`DeepSeek 账号` / `DeepSeek` / `WorkBuddy`（自定义可保留角标语义，但标题本身不要全大写 DEEPSEEK 标签感）。字号略小、次级灰。
2. **其下模型左缩进约 12–16px**（约两个汉字宽）；模型名正文色；描述更小更淡、**单行省略**。
3. **选中/悬停只高亮模型行**，不高亮提供商行。
4. **组间距大于组内行距**（组间额外约 6–8px）。
5. **不做 Tab、不做折叠、不合并三家提供商**。三组必须原样保留（对应三个不同提供商）。

## C. 字号与样式（浅色）
| 元素 | 规格 |
|---|---|
| 「选择模型」`.ue-modelsTitle` | **删除**（不再渲染该文案） |
| 提供商小标题 `.ue-groupName` | **13–14px** / **500–600** / 正文色约 **55–65%** 灰（如 `rgba(15,23,42,.58)`）；非 uppercase；不可点、无 hover 底；仍是小标题不是模型名 |
| 模型行 `.ue-row` | 左缩进 **14px**（12–16 可接受）；`padding: 7px 10px`；圆角 10 |
| 模型名 `.ue-rowName` | 13px / 500 / primary |
| 描述 `.ue-rowDesc` | 11px / 400 / `rgba(15,23,42,.48)`；与名间距 2–3px；**单行 ellipsis**（用户确认） |
| 选中勾 | 14px，`--ue-blue` |
| hover | 仅 `.ue-row`：`rgba(15,23,42,.05)`，`.14s` |
| 选中 | 仅 `.ue-rowActive`：`rgba(58,131,247,.10)` |
| 组间距 | 组与组之间 margin-top **14–18px**（V11）；组内行距紧凑 |
| 滚动条 | 宽 4px，thumb `rgba(15,23,42,.18)`；`max-height: min(280px, 45vh)` |

提供商标题映射建议（可按 session 实际 group key 调整，报告里写清）：
- `deepseek account` / `DEEPSEEK ACCOUNT` → `DeepSeek 账号`
- `deepseek` / `DEEPSEEK` → `DeepSeek`
- `workbuddy` / `WORKBUDDY` → `WorkBuddy`

## C2. V11 标题观感（用户反馈后）
1. **删除**列表顶部「选择模型」四字。
2. 分组标题要更醒目：13–14px、字重 500–600、颜色约 55–65% 正文灰（现 11px/.42 太淡）。
3. 缩进层级保持；hover/选中仍只在模型行。
4. 首组在删掉「选择模型」后更贴近上方滑杆区；**组与组之间再松 2–4px**（组间距目标约 14–18px）。
5. 禁止合并/折叠/Tab；不回退 V9/V10。

## D. 交互动画
1. effort↔model：高度 ~.28s `cubic-bezier(.19,1,.22,1)`；内容 180ms 淡入+上移 8→0。
2. 触发器/模型按钮背景 .14s；chevron `aria-expanded` 时转 180°（.18s）。
3. 行只做背景过渡，不位移。
4. `prefers-reduced-motion` 关闭动画。
5. 不回退 V9（手柄正圆、默认档隐藏↺、Max 高光、右缘对齐、Esc 回焦）。

## E. 禁止
- 合并/去重/隐藏任一提供商分组
- Tab / 折叠手风琴
- 改 session.models 语义或选模型回调
- push remote；引入构建依赖；新增 !important

## F. 验收清单
- [ ] 三组提供商中文小标题 + 模型缩进 12–16px 清晰可见
- [ ] hover/选中只作用在模型行
- [ ] 组间距 > 组内行距
- [ ] 描述单行省略；滚动条细；列表高度合理
- [ ] 打开/切换动画流畅；chevron 旋转
- [ ] node --check；pageerror 0；!important=0；本地 commit
- [ ] 实机截图：关闭 / 滑杆 / 列表顶 / 底 / hover / 选中；`docs/v10-compare-list.png`
