# 文本引用与批注

DSH 0.2.1-rc.3 及以上的独立浏览器插件，无 Host 路由、MCP、运行时第三方依赖。

选中对话中的文字，点选区旁的对话气泡，输入评论并按 Enter（留空即纯引用）。Shift+Enter 换行，Esc 取消，中文输入法组字时 Enter 不会提交。每条引用是一个官方 chip，支持悬停/点击预览、编辑评论、删除及 dock 管理。添加、修改、删除都只改草稿，不调用发送 API。

评论框采用胶囊外观，右侧圆形勾选按钮用于确认；输入期间保留所选原文的高亮和引用编号，滚动及调整窗口时同步定位。不包含麦克风或语音输入。

## 安装与源码

按仓库常规 Git 插件安装流程选择本目录；开发时只 link 到独立测试 web Profile。Host 和 client 分开声明依赖，Host apply 为空。源码入口 `src/client.mjs`、`src/styles.mjs`，纯函数和浏览器桥在 `lib/`。修改后运行 `node plugins/dsh-quote-annotate/build/client.mjs` 生成 client。

引用统一排列在输入框开头，保持添加顺序，以保证发送给模型的内容是「引用容器 → 本轮要求」。普通文字和其他来源的 chip 不改内容。识别为官方斜杠命令时暂时收起引用 chip，列表保留；命令结束后恢复。不会把引用合入命令参数。

## 保存和边界

按会话保存到 `localStorage["juzi.quote-annotate.v1.<sessionId>"]`，版本 1。包括 items 与用于跨窗口冲突合并的版本戳、删除墓碑；发送成功仅移除本次消息中的引用，不清除随后新增的草稿。最多 20 条，原文超过 4000 Unicode 码点截断并标注，批注上限 1000 码点；30 天过期，已删除会话清理。配额失败保留内存草稿并提示；损坏或未知版本忽略并告警一次。

原文和评论仅用 React 文本节点显示。序列化转义 `<`、`>`、`&`，明确引用仅作为上下文，不是本轮指令。失效 chip 会阻止发送，不静默丢掉引用。

## DOM 依赖清单与降级

所有选择器集中在 `lib/dom-anchors.js`：

- 官方只读锚点：`data-conversation-content/session`、`data-conversation-scroll`、`data-chat-flow/node-key/flow-kind/turn`、`data-composer-seat`、`[contenteditable][role=textbox]`、`data-variant=think/others`、`data-code-wrap`、`data-code-block-banner`、`data-clock`。排除工具栏、时间、代码标题等界面文字。
- 官方 assistant-actions 插槽渲染隐藏 `data-jq-message` 锚点；不直接往聊天节点插子节点。
- `data-composer-chip="juzi.quote-annotate"`：按 DOM 顺序与官方 occurrences 一一对应。数量不一致拒绝映射，不猜测。
- 删除通过官方 `inputActions.insertText` 的 detect 范围和 draftRev 校验完成，映射时同时计算其他 source 的原子 chip 长度。统一前缀顺序没有公开接口，仅对本 source 使用版本守卫后的 `__lexicalEditor` / `_nodeMap` / reference-chip `__source`、`__ref`，通过 Lexical update 调整顺序。不修改全局原型或提交函数。
- 自有 source 的 CSS 隐藏默认 @，并让内层原生 title 不参与指针命中，避免与自有预览叠加。除此之外不改官方 chip DOM 或属性。
- 评论标记是由相同引用状态派生的本 source CSS `::after`，保留不可收缩的位置；长摘要被官方省略时，末尾标记仍可见。清空评论即同步移除，不再改写原生 label 字段。
- 自有浮层挂在 shell.overlay，所有 UI 为 `.jq-*` / `data-jq`。官方菜单打开时关闭自有浮层。
- 选区气泡只读测量可见正文行盒，优先上方或末尾右侧；空间不足时避开相邻正文行。胶囊评论框优先居中放在选区上方，空间不足时转向下方或侧面；自有覆盖层保留选区高亮和编号，不修改聊天 DOM。长评论按整行滚动，最多六行。滚动条采用 DSH 色值，Firefox 使用 `scrollbar-width: thin`，Chromium 使用 6px WebKit 样式以去掉上下箭头。

## 已发送引用

通过官方 `uiConversation.userText.register` 与 `conversation.user.text.node` keyed 插槽，把本插件规范格式的消息前缀显示为「引用 N 条」卡片。默认折叠，可用鼠标或键盘展开查看原文和评论；本轮要求继续由 DSH 原生渲染。只改变显示，不修改历史消息、发送文本或模型接收的内容。

解析器按规范逐段匹配，不将引用容器当作 HTML，也不简单寻找第一个结束标签（规范说明句本身包含字面结束标签）。未知版本、损坏结构或官方注册接口不可用时保留原始文本并降级，不隐藏无法识别的内容。停用会注销规则及插槽，历史消息恢复原生文本展示。

发送确认使用官方持久事件或队列接收回执；混合其他 source 时关联官方 pendingSubmission 的 requestId，不假定其他 codec 输出等于其标签。A→B→A 时重新获取 SessionBinding，避免使用已释放的会话代际。并发添加按创建时间与 ID 的稳定顺序排列，dock、chip 与序列化编号一致。

视图卸载时释放 DOM、可见消息索引和输入订阅；有待发送确认的引用时，只保留回执观察，确认完成后释放。关闭视图不会删除本地草稿。选区提取从相关子树开始，浮层避让优先使用 IntersectionObserver 跟踪的可见消息；观察结果尚未到达或接口不可用时按消息边界测量。

## 已知限制

- Q-V9（DSH 官方接口限制，已获用户认可）：rc.3 原生 chip 仅公开点击激活，没有独立 Tab 焦点或 aria 属性定制接口。键盘用户可通过 dock 的「引用预览 N」按钮进入同一张卡片，自动聚焦编辑按钮，继续 Tab、Enter、Esc 完成操作。dock 提供 aria-controls/expanded 与播报；未为补 aria-describedby 而修改官方 chip 属性。
- 多窗口同步引用与评论；DSH 自身普通输入文字仍遵循其本机草稿的最后写入行为，不提供文字协同编辑。
- 只在主对话提供选区入口，其他嵌入视图不提供入口。引用数据仅存本机浏览器，无云同步。
- 浮层正文使用实底 token 保证对比度，气泡使用菜单磨砂 token；仅本 source 的 chip 文字使用 primary token，避免品牌色小字在浅色下不足 AA。

DSH 升级后如果入口消失，属于锚点降级保护。警告仅记一次；已有引用和 DSH 原本复制、选择、输入和发送不会被全局事件拦截。桥不可用时拒绝相关编辑操作并保留数据。精确兼容性与已知限制以本次开发验收报告为准。

## 停用、卸载和清除草稿

在 DSH 插件页停用，先通过官方范围编辑移除本次已绑定会话中的自有 chip，保留普通文字与本地引用数据，再释放插件节点、样式与监听器。刷新后原输入框正常使用；重新启用可恢复引用。未在本次页面绑定过的旧会话如仍有失效 chip，可重新启用后清空引用，或用 Backspace 删除。手动清理草稿时，只删除 localStorage 中以 `juzi.quote-annotate.v1.` 开头的键，不要清除 DSH 的其他键。

### 0.1.1：Enter 发送清空

无引用时插件不再启动编辑器排序事务；发送清空期间没有段落时停止排序，避免嵌套事务异常回滚。发送后的新草稿继续保留。
