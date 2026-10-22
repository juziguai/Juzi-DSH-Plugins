# Codex 推理强度面板 · 原型规格（dsh-ultra-effort 验收标准）

> 来源：juzi 电脑上的 OpenAI Codex 桌面版 26.1016（`ModelPickerPowerSlider`），2026-10-23 01:54–02:06（北京时间）实机截图，并只读查看了安装包里的 `webview/assets/impl-*.css|js` 和 `app-primary-*.css`。
> 截图都在 `docs/codex-ref/`。屏幕 2160×1440，缩放 150%，下面的数值都换算成了 **CSS px**（物理 px ÷ 1.5）。
> 优先级：**P0 = 必须一致**，P1 = 尽量一致，P2 = 有余力再做。

## 0. 设计理念（为什么这样做）
1. **一个控件同时管模型和强度**：面板顶部的大字是"当前档位名"（不是品牌名），下面一行小灰字是模型名，点模型名进入模型列表。用户看一眼就知道"我现在是什么档"。
2. **克制、小巧**：面板很小（约 266×100），弹在触发器上方 8px 左右。它是一个浮在输入框上的轻量菜单，不是卡片。
3. **普通档位是"开关+刻度"，最高档是"仪式感"**：轻度到极高是灰轨、蓝色填充、刻度点；进入 Ultra 时整条轨道换成流动的蓝紫渐变（WebGL 网格渐变），再加 2s 遮罩揭示、粒子迸发和持续流动的小光点。视觉奖励只给最高档，其他档位安静。
4. **按住才出现辅助信息**：Faster/Smarter 这类端点标签平时不显示，只有按住超过 150ms 才出现。

## 1. 触发器（输入框工具栏）
| 项 | Codex | 要求 |
|---|---|---|
| 关闭态 | 一个合并按钮：`GPT-6 Astra`（正文色）+ 空格 + `Ultra`（档位名，紫 #924ff7；非默认的普通档为蓝 #3a83f7；默认档为 tertiary 灰）+ 小 chevron ▾ | P0：模型名和档位名合成一个触发器，档位名按状态着色。不要单独做一个灰底的「Max」块 |
| 打开态 | 按钮变成灰色胶囊底（ghost-hover），文字变成"选择推理强度"+ ▾ | P1 |
| 截图 | `00-trigger-closed.png`、`01-ultra-open.png` | |

## 2. 面板容器
| 项 | Codex 实测 | 允许误差 |
|---|---|---|
| 尺寸 | 约 **266 × 100**（包括 padding） | 宽 ±12，高 ±8 |
| 位置 | Radix dropdown，`side=top`，底边在触发器上方约 **8px**；右缘约等于输入框发送按钮右缘（离输入框外框右缘约 12px）。**面板可以盖住输入框的文本区**，不必整体抬到输入框上面 | 右缘 ±4 |
| 内边距 | `padding: 4px`（var(--spacing)） | |
| 圆角 / 边框 / 阴影 | 圆角约 14–16；1px 很浅的边框加柔和阴影（菜单标准样式），白底 | P1 |
| 高度切换动画 | `height .32s cubic-bezier(.19,1,.22,1)`；内容区 `opacity .2s cubic-bezier(.23,1,.32,1)` + `translate 0→±10px .32s`，滑杆延迟 40/56ms 依次进场 | P1 |
| 减少动画 | `prefers-reduced-motion` 时去掉全部 transition | P0 |

## 3. 头部（ViewControls，最小高度 36px）
| 项 | Codex | 要求 |
|---|---|---|
| 主标题 | **当前档位名**（轻度 / … / 极高 / Ultra），`font-size: 16px (text-base)`，`font-weight: 500`，颜色：Ultra 用 chart-purple ≈ #924ff7，其他档用 chart-blue ≈ #3a83f7 | P0：标题必须随档位变化，拖动时实时预览。字号 16 左右，不要 26px 粗体 |
| 副标题 | 模型名 `12px (text-xs)`，weight 400，`color: text-secondary`（灰），后面跟一个小 `›`；超长时省略号截断；hover 时出现 ghost 底色（圆角 6，padding 2px 4px） | P0：灰色小字，不要 16px 黑字 |
| Ultra 提示 | 拖到 Ultra 时副标题临时换成"使用额度消耗更快" | P2 |
| 左图标 ⚡ | 这是**快速模式开关**（menuitemcheckbox），点击区 32×32，内容 26×26，圆角 7；默认 tertiary 灰，打开后为蓝（Ultra 档时为紫）；tooltip "{n}x speed" | P0：图标默认灰色。dsh 没有快速模式的话，保持装饰用途但要灰色、低调 |
| 右图标 ↺ | 重置为默认，32×32，tertiary 灰，hover 出现 ghost 底；**只有选了非默认值时才显示** | P1 |

## 4. 滑杆（Container 高 32px，margin-inline 2px，padding 2px 6px）
| 项 | Codex | 要求 |
|---|---|---|
| 轨道 | 高 **24px**，圆角 12，底色 `color-mix(text 10%)`（浅灰），`inset 0 0 0 .5px border` | P0 |
| 普通档填充 | 纯色 chart-blue **#3a83f7**，从左端到手柄中心 | P0：普通档用蓝色实心填充，不用紫渐变 |
| 刻度点 | 每个档位一个 **4px 圆点**，在填充区内为白色 30%，未填充区为灰色 50%；hover 放大 2 倍并稍微变暗；点击区向外扩 6px | P0 |
| 手柄 | **28px 白色正圆**，`border: .5px solid border-strong`，`box-shadow: 0 0 2px rgba(0,0,0,.1)`；比轨道高，上下各超出 2px；在端点时和轨道端点对齐 | P0：正圆，28px，不是内嵌的圆角方块 |
| 按下 / 拖动 | 手柄放大到 32/28 ≈ 1.14 倍，spring(stiffness 420, damping 38)；松开时 spring(220, 26)；拖动中位置过渡 .15s cubic-bezier(.23,1,.32,1)，平时 .3s | P1 |
| 吸附 | 离散档位，拖动时实时预览档位名，松开后提交 | P0 |
| 端点标签 | 按住超过 150ms 才显示，松开就隐藏 | P1：Faster/Smarter **默认不显示** |
| Ultra 档 | 轨道换成蓝紫渐变 `linear-gradient(90deg, mix(blue 60%, purple), purple 55%, mix(purple 72%, blue))`，再叠一层缓慢流动的网格渐变（Codex 用 WebGL，`mix-blend-mode: luminosity`）；进入时有 2s 遮罩揭示和 16 粒 5px 粒子迸发（.62s）；持续有 3px 白色光点（`#ffffffb8`，带光晕）从右往左流动；刻度点隐藏 | P1：渐变、揭示和光点都要有；不用 WebGL 的话用 CSS 动画渐变近似也可以 |
| 进入 / 退出 Ultra | 效果在进入 1200ms 后才进入持续态，退出时 350ms 淡出 | P2 |

## 5. 键盘与无障碍
- 支持 Arrow ←→↑↓、Home、End、PageUp、PageDown（P0）。
- 用 `aria-live=polite` 播报"{档位名}，第 {i} 项，共 {n} 项"，并加隐藏的说明文字"使用左右方向键调整强度"（P1）。
- 只有键盘聚焦时显示焦点环：手柄 `outline: 2px solid ring`（P0）。鼠标点击不显示焦点环。
- Esc 关闭面板，焦点回到触发器（P0）。

## 6. 和 dsh v5 的差距（`compare-v5.png`，同一屏幕同一比例）
1. 面板太大：360×166 vs 266×100，约为 Codex 的 1.35 倍宽、1.66 倍高。
2. 标题固定写 "Ultra"（26px 粗体），不随档位变化；Codex 显示当前档位名，16px、weight 500。
3. 模型名 16px 黑色；Codex 是 12px 灰色。
4. ⚡ 和 ↺ 是紫色/深色；Codex 都是 tertiary 灰。
5. Faster/Smarter 一直显示；Codex 只在按住时显示。
6. 手柄是 26px 的圆角块，嵌在 30px 轨道里；Codex 是 28px 白色正圆，压在 24px 轨道上。
7. 普通档没有蓝色实心填充和刻度点（需要对照 v5-mid 再确认）。
8. 面板被抬到输入框上方，右缘对齐 Max 按钮；Codex 在触发器上方 8px，盖住输入框文本区，右缘对齐发送按钮。
9. 触发器拆成了「模型名 + 灰底 Max 块」；Codex 是一个合并的触发器，档位名带颜色。

## 7. 验收方法
- 用 Playwright 在 1440×900 / 1100×800 / 820×700 下输出 panel、track、handle、title、subtitle 的 boundingBox 和 computedStyle（font-size、weight、color）。数值和本规格逐项对照，列出误差表。
- 在 0 档、中间档、Ultra、按住时、键盘聚焦时各截一张图（docs/v7-*.png），每张都和 `docs/codex-ref/` 里对应的图左右拼起来对比。
- 零 pageerror，`node --check` 通过。
