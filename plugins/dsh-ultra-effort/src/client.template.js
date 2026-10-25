window.__ModuleLoader__.load({
	id: "@juzi/dsh-ultra-effort",
	factory: (require) => {
		var module = { exports: {} };
		var exports = module.exports;
		Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
		Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
		//#region \0rolldown/runtime.js
		var __create = Object.create;
		var __defProp = Object.defineProperty;
		var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
		var __getOwnPropNames = Object.getOwnPropertyNames;
		var __getProtoOf = Object.getPrototypeOf;
		var __hasOwnProp = Object.prototype.hasOwnProperty;
		var __copyProps = (to, from, except, desc) => {
			if (from && typeof from === "object" || typeof from === "function") for (var keys = __getOwnPropNames(from), i = 0, n = keys.length, key; i < n; i++) {
				key = keys[i];
				if (!__hasOwnProp.call(to, key) && key !== except) __defProp(to, key, {
					get: ((k) => from[k]).bind(null, key),
					enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable
				});
			}
			return to;
		};
		var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(isNodeMode || !mod || !mod.__esModule || !__hasOwnProp.call(mod, "default") ? __defProp(target, "default", {
			value: mod,
			enumerable: true
		}) : target, mod));
		//#endregion
		let react = require("react");
		react = __toESM(react, 1);
		const ModelVersionBadge = (__MODEL_LABEL_FACTORY__)(react, __MODEL_VERSIONS__);
		//#region src/client/index.ts
		/**
		* Skin-switcher plugin, browser half — the composer's model + reasoning-effort
		* switcher. Registers the named `conversation.input.model` seat, loads the
		* session's provider-grouped directory through `session.models` and submits
		* through `session.selectModel` (the same session-scoped RPC the first-party
		* selector uses), so a switch made here takes effect on the current session and
		* is what `/model` shows next. Above the model list it renders a two-level
		* (Off/Max) reasoning-effort slider for models that declare `reasoningEfforts`,
		* remembering each model's last effort.
		*/
		/**
		* Required Browser Services, exported as the Client Loader's declaration site.
		*
		* The Client Loader creates this package's entry from the module table and the
		* fiber's dependencies come from THIS export — `dsh.client.inject` in
		* package.json only orders bundle arrival. Without the export the fiber injects
		* nothing, every `ctx.<service>` below stays undefined, and the shell reports
		* the package as "is waiting for activation".
		*
		* Same six names the first-party `@deepseek-ai/dsh-client-ui-model-selection`
		* declares; `modelDirectories` is the Service that plugin provides.
		*/
		const inject = [
			"locale",
			"modelDirectories",
			"remote",
			"remote.session",
			"sessions",
			"slots"
		];
		/** Dictionary namespace owned by this plugin. */
		/** Ultra skin: purple gradient track, sparkles, Ultra title. Visual only. */
				const ULTRA_CSS = __ULTRA_CSS__;		const NS = "ui-skin-switcher";
		/** Plugin-owned copy: `zh` is the key-set source of truth, `en` mirrors it. */
		const DICTS = {
			zh: {
				"trigger.fallbackModel": "模型",
				"trigger.selectModel": "选择模型",
				"effort.title": "思考强度",
				"effort.default": "默认",
				"panel.aria": "选择推理强度",
				"reset.title": "重置为默认",
				"reset.aria": "重置为默认推理强度",
				"slider.aria": "推理强度",
				"label.faster": "更快",
				"label.smarter": "更聪明",
				"sr.level": "{label}，第 {i} 项，共 {n} 项",
				"hint.slider": "使用左右方向键调整强度",
				"status.loading": "加载中…",
				"status.noModels": "暂无可用模型"
			},
			en: {
				"trigger.fallbackModel": "Model",
				"trigger.selectModel": "Select model",
				"effort.title": "Reasoning effort",
				"effort.default": "Default",
				"panel.aria": "Reasoning effort",
				"reset.title": "Reset to default",
				"reset.aria": "Reset reasoning effort to default",
				"slider.aria": "Reasoning effort",
				"label.faster": "Faster",
				"label.smarter": "Smarter",
				"sr.level": "{label}, {i} of {n}",
				"hint.slider": "Use the left and right arrow keys to adjust",
				"status.loading": "Loading…",
				"status.noModels": "No models available"
			}
		};
		/** Insert one stylesheet and return its disposer. */
		function injectCss(css) {
			const tag = document.createElement("style");
			tag.dataset.plugin = "skin-switcher";
			tag.textContent = css;
			document.head.appendChild(tag);
			return () => {
				tag.remove();
			};
		}
		/** Extract a message from an unknown error. */
		function msg(e) {
			if (e !== null && typeof e === "object" && typeof e.message === "string") return e.message;
			return String(e);
		}
		/** Find the model descriptor inside one provider group. */
		function findModel(groups, provider, model) {
			const g = groups.find((x) => x.id === provider);
			if (g === void 0) return void 0;
			return g.models.find((m) => m.id === model);
		}
		/** Effort slider / matrix / model list styles, injected once for this plugin. */
		const CSS = __CSS__;
		/** Per-model (provider\u0000model) effort memory, shared across the whole page. */
		const effortMemory = /* @__PURE__ */ new Map();
		/**
		* Snapshot handed to `useSyncExternalStore` when a session resolved no
		* directory. Module-level on purpose: `useSyncExternalStore` compares snapshots
		* by identity, so a literal rebuilt on every render would report a change on
		* every render and re-render forever.
		*/
		const NO_DIRECTORY_STATE = {
			current: null,
			groups: [],
			status: "idle",
			error: null
		};
		/** Two-level mask curve: right side opaque, left transparent, transition over 5%→75%. */
		function fadeAt(fx) {
			if (fx <= .05) return 0;
			if (fx >= .75) return 1;
			const t = (fx - .05) / .7;
			return t * t * (3 - 2 * t);
		}
		/**
		* Client plugin body: inject the stylesheet once, then register the composer
		* model seat whose component reads `sessions.models` and writes
		* `sessions.selectModel`.
		* @param ctx - client root context carrying connection and slots.
		*/
		function apply(ctx) {
			/**
			* The first-party model directory service. It carries the same host catalog
			* and the same session selection projection the official `/model` selector
			* renders, so this seat always shows what `/model` shows. DSH 0.1.5 replaced
			* the older `connection.api.sessions` RPC face with this service.
			*
			* `select` answers with an outcome envelope — `{ ok: true }` or
			* `{ ok: false, error: { code, message } }` — and only rejects for a
			* transport-level throw, so a refused selection has to be unwrapped rather
			* than caught.
			*/
			const directories = ctx.modelDirectories;
			/** Unknown sessions make `directoryFor` throw; that must not break the seat. */
			const directoryOf = (sessionId) => {
				try {
					return directories.directoryFor(sessionId);
				} catch {
					return null;
				}
			};
			const runtimeSessions = ctx.sessions;
			ctx.effect(() => injectCss(CSS));
			ctx.effect(() => injectCss(ULTRA_CSS), "ui-ultra-effort: skin");
			ctx.effect(() => ctx.locale.register(NS, DICTS), "ui-skin-switcher: dictionaries");
			ctx.slots.inject("conversation.input.model", () => ctx.slots.register({
				name: "conversation.input.model",
				priority: -1,
				locale: NS
			}, (props) => {
				const { locked, sessionId, t } = props;
				const renderModelLabel = (group, model) => react.createElement(ModelVersionBadge, {
					provider: { id: group.id, name: providerLabel(group) }, model
				});
				/**
				* Read one dictionary key through the framework-injected `t` seat; the
				* Chinese table backs a host that shipped no locale service.
				*/
				const tr = (key) => typeof t === "function" ? t(key) : DICTS.zh[key] ?? key;
				const [menu, setMenu] = react.useState(null);
				const [closing, setClosing] = react.useState(false);
				const closeTimerRef = react.useRef(null);
				const closingRef = react.useRef(false);
				/** 统一关闭入口：150ms 退出动画后再卸载；reduce 下同步卸载。 */
				const requestClose = (focusTrigger) => {
					if (focusTrigger !== false) {
						skipFocusReturnRef.current = true;
						if (effortTriggerRef.current !== null) effortTriggerRef.current.focus({ preventScroll: true });
					}
					if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
						closingRef.current = false;
						setClosing(false);
						setMenu(null);
						return;
					}
					closingRef.current = true;
					setClosing(true);
					if (closeTimerRef.current !== null) clearTimeout(closeTimerRef.current);
					closeTimerRef.current = setTimeout(() => {
						closeTimerRef.current = null;
						closingRef.current = false;
						setMenu(null);
						setClosing(false);
					}, 150);
				};
				const [busyKind, setBusy] = react.useState(null);
				const busy = busyKind !== null;
				const [error, setError] = react.useState(null);
				const [hoverIdx, setHoverIdx] = react.useState(null);
								const rootRef = react.useRef(null);
				const effortTriggerRef = react.useRef(null);
				const effortValueRef = react.useRef(null);
				const trackRef = react.useRef(null);
				const [moving, setMoving] = react.useState(false);
				const dragIdxRef = react.useRef(null);
				const busyRef = react.useRef(false);
				const pendingRef = react.useRef(null);
				const [settledIdx, setSettledIdx] = react.useState(null);
				/** V2: 面板内视图（effort | model）、终点动画、重置反馈。 */
				const [panelView, setPanelView] = react.useState("effort");
				const [burst, setBurst] = react.useState(false);
				const [resetFlash, setResetFlash] = react.useState(false);
				const burstRef = react.useRef(false);
				const resetTimerRef = react.useRef(null);
				/** 拖拽连续跟随：不经过 React 状态，直接写 CSS 变量。 */
				const dragFracRef = react.useRef(0);
				const dragRectRef = react.useRef(null);
				const dragElRef = react.useRef(null);
				const dragPointerIdRef = react.useRef(null);
				const dragRafRef = react.useRef(null);
				const tipRef = react.useRef(null);
				const tipTextRef = react.useRef(null);
				const tipIdxRef = react.useRef(-1);
				const tipBoxRef = react.useRef(null);
				const panelRef = react.useRef(null);
				const modelsRef = react.useRef(null);
				const rowRefs = react.useRef([]);
				const modelBtnRef = react.useRef(null);
				const [focusIdx, setFocusIdx] = react.useState(-1);
				const panelIdRef = react.useRef("ue-panel-" + Math.random().toString(36).slice(2, 8));
				const hintIdRef = react.useRef("ue-hint-" + Math.random().toString(36).slice(2, 8));
				const listInitRef = react.useRef(false);
				const skipFocusReturnRef = react.useRef(false);
				const openedByKeyboardRef = react.useRef(false);
				const pressTimerRef = react.useRef(null);
				const [showLabels, setShowLabels] = react.useState(false);
				/**
				 * 面板定位（V6）：
				 * 1) 垂直：抬到输入框之上，留 8px；
				 * 2) 水平：右缘对齐输入框容器右缘（不是座位），左右各留 ≥8px；
				 * 3) 矮窗口：先压缩（ue-compact），仍放不下再内部滚动。
				 */
				react.useLayoutEffect(() => {
					const root = rootRef.current;
					const panel = panelRef.current;
					if (root === null) return;
					if (menu === null) {
						root.style.removeProperty("--ue-drop-lift");
						root.style.removeProperty("--ue-drop-right");
						return;
					}
					const apply = () => {
						const r = root.getBoundingClientRect();
						let node = root.parentElement;
						let composer = null;
						for (let i = 0; i < 6 && node !== null; i++, node = node.parentElement) {
							const b = node.getBoundingClientRect();
							if (b.height >= 70) {
								composer = b;
								break;
							}
						}
						const vw = window.innerWidth;
						/** V7：面板贴在触发器上方 8px（可覆盖输入框文本区），不再整体抬到输入框之上。 */
						root.style.setProperty("--ue-drop-lift", "8px");
						if (panel === null) return;
						const pw = panel.getBoundingClientRect().width;
						/** 右缘对齐发送按钮右缘（composer 外框内约 8px 内缩）。 */
						const targetRight = (composer ? composer.right : r.right) - 8;
						const right = Math.min(Math.max(targetRight, 8 + pw), vw - 8);
						root.style.setProperty("--ue-drop-right", (r.right - right) + "px");
						const avail = Math.max(120, r.top - 16);
						/** 先量原始高度，放不下才压缩间距，仍放不下才滚动。 */
						panel.classList.remove("ue-compact");
						panel.style.maxHeight = "none";
						panel.style.overflowY = "";
						const natural = panel.scrollHeight;
						let needed = natural;
						if (natural > avail) {
							panel.classList.add("ue-compact");
							needed = panel.scrollHeight;
						}
						panel.style.maxHeight = Math.min(needed, avail) + "px";
						/** 夹紧后一律允许滚动：无溢出时浏览器不会显示滚动条，有溢出也不会被裁掉。 */
						panel.style.overflowY = "auto";
					};
					apply();
					window.addEventListener("resize", apply);
					return () => window.removeEventListener("resize", apply);
				}, [menu, panelView]);

				/** 视图切换（滑杆↔列表）时给面板高度做 FLIP 过渡，避免硬切。 */
				const heightRef = react.useRef(null);
				react.useLayoutEffect(() => {
					const panel = panelRef.current;
					if (panel === null) return;
					const next = panel.scrollHeight;
					const prev = heightRef.current;
					heightRef.current = next;
					if (prev === null || prev === next) return;
					if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
					panel.style.height = prev + "px";
					panel.style.transition = "height .28s cubic-bezier(.19,1,.22,1)";
					void panel.offsetHeight;
					panel.style.height = next + "px";
					const id = setTimeout(() => {
						panel.style.height = "";
						panel.style.transition = "";
					}, 300);
					return () => clearTimeout(id);
				}, [panelView, menu]);
				/** 焦点：打开面板聚焦滑杆；关闭后回到触发按钮。 */
				const prevMenuRef = react.useRef(null);
				react.useEffect(() => {
					const prev = prevMenuRef.current;
					prevMenuRef.current = menu;
					if (menu === "effort" && panelView === "effort") {
						const root = rootRef.current;
						if (root !== null) root.classList.toggle("ue-kb", openedByKeyboardRef.current);
						if (prev !== "effort") {
							if (trackRef.current !== null) trackRef.current.focus({ preventScroll: true });
						} else if (modelBtnRef.current !== null) {
							modelBtnRef.current.focus({ preventScroll: true });
						}
					} else if (menu === null && prev !== null) {
						if (skipFocusReturnRef.current) skipFocusReturnRef.current = false;
						else if (effortTriggerRef.current !== null) effortTriggerRef.current.focus({ preventScroll: true });
					}
				}, [menu, panelView]);
				/** This session's shared directory — the official selector's own data source. */
				const directory = react.useMemo(() => directoryOf(sessionId), [sessionId]);
				const state = react.useSyncExternalStore(react.useCallback((listener) => directory === null ? () => {} : directory.store.subscribe(listener), [directory]), react.useCallback(() => directory === null ? NO_DIRECTORY_STATE : directory.store.getSnapshot(), [directory]));
				/** Composer trigger row owns this width; the slider handle spans half of it. */
				const HANDLE_W = 26;
				const TRACK_H = 30;
				const load = () => {
					if (directory !== null) directory.load().catch(() => {});
				};
				react.useEffect(() => {
					load();
				}, []);
				react.useEffect(() => {
					if (menu !== null) load();
				}, [menu]);
				react.useEffect(() => {
					if (menu === null) return;
					const handler = (ev) => {
						if (rootRef.current === null || rootRef.current.contains(ev.target)) return;
						/** 阻止浏览器把焦点移到被点元素，交给关闭逻辑回收给触发按钮。 */
						ev.preventDefault();
						requestClose();
					};
					/** V2: Escape 先在面板内退出模型列表，再关闭整个面板。 */
					const onKey = (ev) => {
            if (ev.key !== "Escape" || menu !== "effort" || closingRef.current) return;
            ev.preventDefault();
            ev.stopPropagation();
						if (menu === "effort" && panelView === "model") {
							setPanelView("effort");
							ev.stopPropagation();
							return;
						}
						requestClose();
						setPanelView("effort");
					};
					document.addEventListener("mousedown", handler);
					window.addEventListener("keydown", onKey, true);
					return () => {
						document.removeEventListener("mousedown", handler);
						window.removeEventListener("keydown", onKey, true);
					};
				}, [menu, panelView]);
				react.useEffect(() => {
					if (menu !== "effort") {
						stopDrag();
						setPanelView("effort");
					}
				}, [menu]);
				react.useEffect(() => () => {
					if (resetTimerRef.current !== null) clearTimeout(resetTimerRef.current);
					if (closeTimerRef.current !== null) clearTimeout(closeTimerRef.current);
					if (dragRafRef.current !== null) cancelAnimationFrame(dragRafRef.current);
					if (pressTimerRef.current !== null) clearTimeout(pressTimerRef.current);
					const el = dragElRef.current;
					if (el !== null) {
						el.removeEventListener("pointermove", onWinMove);
						el.removeEventListener("pointerup", onWinUp);
						el.removeEventListener("pointercancel", onWinCancel);
						el.removeEventListener("lostpointercapture", onWinCancel);
						if (dragPointerIdRef.current !== null && el.hasPointerCapture(dragPointerIdRef.current)) {
							try { el.releasePointerCapture(dragPointerIdRef.current); } catch (e) { /* already released */ }
						}
					}
					window.removeEventListener("blur", onWinCancel);
				}, []);

				react.useEffect(() => {
					setHoverIdx(null);
				}, [state.current === null ? null : state.current.reasoningEffort]);
				const apply = (sel, keepOpen) => {
					if (directory === null) return;
					pendingRef.current = sel;
					if (busyRef.current) return;
					busyRef.current = true;
					setBusy(keepOpen ? "effort" : "model");
					setError(null);
					/**
					* The call itself can throw instead of answering — `select` refuses a
					* session that may not use Agent-bound model RPCs before it goes async —
					* and a refused selection RESOLVES with the Remote failure inside the
					* envelope instead of rejecting. Both paths land on the seat's own error.
					*/
					let pending;
					try {
						pending = directory.select({
							provider: sel.provider,
							model: sel.model,
							...sel.reasoningEffort === void 0 ? {} : { reasoningEffort: sel.reasoningEffort }
						});
					} catch (e) {
						busyRef.current = false;
						setBusy(null);
						setError(msg(e));
						pendingRef.current = null;
						return;
					}
					pending.then((result) => {
						busyRef.current = false;
						setBusy(null);
						if (result !== void 0 && result !== null && result.ok === false) {
							const failure = result.error;
							setHoverIdx(null);
							setError(failure === void 0 || failure === null ? "selection failed" : failure.code + ": " + failure.message);
							pendingRef.current = null;
							return;
						}
						if (!keepOpen) requestClose();
						effortMemory.set(sel.provider + "\0" + sel.model, sel.reasoningEffort);
						const next = pendingRef.current;
						if (next !== null && next !== sel) {
							pendingRef.current = null;
							apply(next, true);
						}
					}, (e) => {
						busyRef.current = false;
						setBusy(null);
						setHoverIdx(null);
						setError(msg(e));
						pendingRef.current = null;
					});
				};
				const groups = state.groups;
				const current = state.current;
				/** Selection failures are local; catalog failures live on the shared store. */
				const shownError = error !== null ? error : state.error;
				const loaded = state.status !== "idle";
				/** 所有提供商的模型行拍平，供跨组键盘导航使用（不改变分组渲染）。 */
				const flatRows = react.useMemo(() => groups.reduce((acc, g) => acc.concat(g.models.map((m) => ({ g, m }))), []), [groups]);
				const flatIndexById = react.useMemo(() => { const map = new Map(); flatRows.forEach((r, i) => map.set(r.g.id + "\u0000" + r.m.id, i)); return map; }, [flatRows]);
				const activeFlatIdx = flatRows.findIndex((r) => current !== null && r.g.id === current.provider && r.m.id === current.model);
				/** 列表打开：聚焦当前选中行并滚到容器中部；每次打开只执行一次，避免抢焦点。 */
				react.useEffect(() => {
					if (panelView !== "model") {
						listInitRef.current = false;
						return;
					}
					if (!loaded || listInitRef.current) return;
					listInitRef.current = true;
					const idx = activeFlatIdx >= 0 ? activeFlatIdx : 0;
					setFocusIdx(idx);
					const container = modelsRef.current;
					const row = rowRefs.current[idx];
					if (container !== null && row !== null && row !== void 0) {
						container.scrollTop = Math.max(0, row.offsetTop - container.clientHeight / 2 + row.offsetHeight / 2);
						row.focus({ preventScroll: true });
					}
				}, [panelView, loaded, activeFlatIdx]);

				/** 行键盘导航：跨组连续、不循环；Home/End；Enter/Space 选择。 */
				const onRowKeyDown = (ev, i) => {
					const n = flatRows.length;
					if (n === 0) return;
					let next = null;
					if (ev.key === "ArrowDown") next = Math.min(n - 1, i + 1);
					else if (ev.key === "ArrowUp") next = Math.max(0, i - 1);
					else if (ev.key === "Home") next = 0;
					else if (ev.key === "End") next = n - 1;
					else if (ev.key === "Enter" || ev.key === " ") {
						ev.preventDefault();
						const r = flatRows[i];
						if (r !== void 0) {
							onPickModel(r.m, r.g);
							setPanelView("effort");
						}
						return;
					} else return;
					ev.preventDefault();
					setFocusIdx(next);
					const container = modelsRef.current;
					const row = rowRefs.current[next];
					if (row !== null && row !== void 0) {
						row.focus({ preventScroll: true });
						if (container !== null) container.scrollTop = Math.max(0, row.offsetTop - container.clientHeight / 2 + row.offsetHeight / 2);
					}
				};
				const curGroup = current === null ? void 0 : groups.find((g) => g.id === current.provider);
				const curModel = current === null ? void 0 : findModel(groups, current.provider, current.model);
				const modelLabel = curModel !== void 0 ? curModel.name : current !== null && current.model !== "" ? current.model : tr("trigger.fallbackModel");
				const reasoning = curModel !== void 0 ? curModel.reasoning : void 0;
				const effectiveEffort = current !== null && current.reasoningEffort !== void 0 ? current.reasoningEffort : reasoning !== void 0 && reasoning.defaultEffort !== void 0 ? reasoning.defaultEffort : void 0;

				const defaultEffort = reasoning !== void 0 ? reasoning.defaultEffort : void 0;
				/** 重置目标 = 当前模型的 defaultEffort；两者归一化后相等即视为“已在默认档”。 */
				const normEffort = (v) => (v === void 0 || v === null ? "" : String(v).toLowerCase());
				const atDefaultEffort = normEffort(effectiveEffort) === normEffort(defaultEffort);
				/** 当前选中的是“默认”档（仅当模型未声明 defaultEffort 时才会出现该档）——用于标题取正文色。 */
				const choices = reasoning === void 0 ? [] : [...reasoning.defaultEffort === void 0 ? [{
					key: "default",
					effort: void 0,
					label: tr("effort.default")
				}] : [], ...reasoning.efforts.map((e) => ({
					key: "e:" + e.id,
					effort: e.id,
					label: e.name
				}))];
				const activeKey = effectiveEffort === void 0 ? "default" : "e:" + effectiveEffort;
				const activeIdx = Math.max(0, choices.findIndex((c) => c.key === activeKey));
				const posIdx = hoverIdx !== null ? hoverIdx : activeIdx;
				const safePosIdx = choices.length > 0 ? Math.max(0, Math.min(choices.length - 1, posIdx)) : 0;
				/** 面板内常驻档位名：与滑动/键盘位置同源。 */
				const levelLabel = choices.length > 0 ? choices[safePosIdx].label : tr("effort.default");

				const tickLeft = (i) => "calc(14px + (100% - 28px) * " + (choices.length > 1 ? i / (choices.length - 1) : 0) + ")";
				/** 14 个流动光点：纵向随机 ±8px，时长/延迟随机（只算一次）。 */
				const streamDots = react.useMemo(() => Array.from({ length: 14 }, () => {
					const dy = (Math.random() * 16 - 8).toFixed(1);
					return { top: "calc(50% + " + dy + "px)", dur: (2.4 + Math.random() * 2.6).toFixed(2) + "s", delay: (-Math.random() * 4.5).toFixed(2) + "s" };
				}), []);
				const atMaxPos = choices.length > 1 && safePosIdx === choices.length - 1;
				const displayIdx = settledIdx === null ? activeIdx : settledIdx;
				const safeDisplayIdx = choices.length > 0 ? Math.max(0, Math.min(choices.length - 1, displayIdx)) : 0;
				const displayChoice = choices.length > 0 ? choices[safeDisplayIdx] : null;
				const displayLabel = displayChoice !== null ? displayChoice.label : tr("effort.default");
				const hasEffort = reasoning !== void 0 && choices.length > 0;
				/** V2: 端点状态跟随交互位置（hover/drag），而不是等待提交回写后的显示位置。 */
				const inMax = choices.length > 1 && safePosIdx === choices.length - 1;
				/** 触发器色调：最高档紫、默认档灰、其余蓝。 */
				const levelTone = inMax ? "ue-lv-max" : (atDefaultEffort ? "ue-lv-def" : "ue-lv-norm");
				/** 面板标题语调色：最高档紫、其余一律蓝（Codex 原型）。 */

				/** 提供商显示名：仅做展示映射（与设置页一致），不改 groups 数据与选择回调。 */
				const providerLabel = (g) => {
					const key = (String(g.id) + " " + String(g.name)).toLowerCase();
					if (key.indexOf("account") >= 0) return "DeepSeek 账号";
					if (key.indexOf("workbuddy") >= 0 || key.indexOf("work-buddy") >= 0 || key.indexOf("work buddy") >= 0) return "WorkBuddy";
					if (key.indexOf("deepseek") >= 0) return "DeepSeek";
					return g.name;
				};
				const isDefaultChoice = choices.length > 0 && choices[safePosIdx].key === "default";
				const titleTone = inMax ? "ue-lv-max" : (isDefaultChoice ? "ue-lv-text" : "ue-lv-norm");
				/** 端点动画：仅在“首次进入终点”时触发一次，离开后复位可重播。 */
				react.useEffect(() => {
					if (!inMax) {
						burstRef.current = false;
						setBurst(false);
						return;
					}
					if (burstRef.current) return;
					burstRef.current = true;
					setBurst(true);
					const id = setTimeout(() => setBurst(false), 680);
					return () => clearTimeout(id);
				}, [inMax]);
								const posPct = choices.length > 1 ? posIdx / (choices.length - 1) * 100 : 0;
				/** 提交值 → CSS 变量；拖拽期间让位给 dragFrac，避免回跳。 */
				react.useLayoutEffect(() => {
					if (moving) return;
					const el = trackRef.current;
					if (el !== null) el.style.setProperty("--ue-pos", String(Math.max(0, Math.min(1, posPct / 100))));
				}, [posPct, moving, menu, panelView, choices.length]);

				react.useEffect(() => {
					const id = setTimeout(() => setSettledIdx(safePosIdx), 160);
					return () => clearTimeout(id);
				}, [safePosIdx]);
				if (runtimeSessions.subagentAddress(sessionId) !== void 0) return null;
				if (directory === null) return null;
				const onPickModel = (m, g) => {
					setSettledIdx(null);
					const remembered = effortMemory.get(g.id + "\0" + m.id);
					apply({
						provider: g.id,
						model: m.id,
						...remembered === void 0 ? {} : { reasoningEffort: remembered }
					}, false);
				};
				const onPickEffort = (effort) => {
					if (current === null) return;
					apply({
						provider: current.provider,
						model: current.model,
						...effort === void 0 ? {} : { reasoningEffort: effort }
					}, true);
				};
				const onReset = () => {
					if (current === null || reasoning === void 0) return;
					setResetFlash(true);
					if (resetTimerRef.current !== null) clearTimeout(resetTimerRef.current);
					resetTimerRef.current = setTimeout(() => setResetFlash(false), 260);
					if (effectiveEffort !== defaultEffort) onPickEffort(defaultEffort);
				};
				/** 滑杆键盘控制：方向键逐档、Home/End 到两端。 */
				const onTrackKeyDown = (ev) => {
					if (rootRef.current !== null) rootRef.current.classList.add("ue-kb");
					if (choices.length < 2) return;
					let next = null;
					if (ev.key === "ArrowRight" || ev.key === "ArrowUp") next = Math.min(choices.length - 1, safePosIdx + 1);
					else if (ev.key === "ArrowLeft" || ev.key === "ArrowDown") next = Math.max(0, safePosIdx - 1);
					else if (ev.key === "PageUp") next = Math.min(choices.length - 1, safePosIdx + 2);
					else if (ev.key === "PageDown") next = Math.max(0, safePosIdx - 2);
					else if (ev.key === "Home") next = 0;
					else if (ev.key === "End") next = choices.length - 1;
					else return;
					ev.preventDefault();
					setHoverIdx(next);
					onPickEffort(choices[next].effort);
				};
				const fracFromEvent = (ev, rect) => {
					const usable = Math.max(rect.width - HANDLE_W, 1);
					return Math.max(0, Math.min(1, (ev.clientX - rect.left - HANDLE_W / 2) / usable));
				};
				const idxFromFrac = (frac) => Math.max(0, Math.min(choices.length - 1, Math.round(frac * (choices.length - 1))));
				/**
				 * 档位磁吸：档位点前后各 w 的区间内把指针位移压缩到 k 倍，
				 * 区间外略快以保证总行程仍是 0→1；档位点自身映射到原位，不累积误差。
				 */
				const DETENT_W = 0.03;
				const DETENT_K = 0.5;
				const mapDrag = (frac) => {
					const n = choices.length;
					if (n < 2) return frac;
					const step = 1 / (n - 1);
					const w = Math.min(DETENT_W, step * 0.4);
					const zoneTotal = 2 * w * (n - 1);
					const slopeOut = (1 - DETENT_K * zoneTotal) / (1 - zoneTotal);
					const idx = Math.max(0, Math.min(n - 1, Math.round(frac / step)));
					const p = idx * step;
					if (Math.abs(frac - p) <= w) return p + (frac - p) * DETENT_K;
					const dir = frac > p ? 1 : -1;
					const from = p + dir * w;
					const to = p + dir * (step - w);
					const yFrom = p + dir * w * DETENT_K;
					const yTo = p + dir * (w * DETENT_K + (step - 2 * w) * slopeOut);
					const d = Math.max(0, Math.min(1, (frac - from) / (to - from)));
					return yFrom + (yTo - yFrom) * d;
				};
				/** 拖拽期间每帧只写 CSS 变量与气泡，不触发 React 重渲染。 */
				const paintPos = (rawFrac) => {
					const el = trackRef.current;
					if (el === null) return;
					const frac = mapDrag(rawFrac);
					el.style.setProperty("--ue-pos", String(frac));
					const tip = tipRef.current;
					if (tip === null) return;
					const n = choices.length;
					const step = n > 1 ? 1 / (n - 1) : 1;
					const w = Math.min(DETENT_W, step * 0.4);
					const near = Math.max(0, Math.min(n - 1, Math.round(frac / step)));
					const dist = Math.abs(frac - near * step);
					tip.style.opacity = String(n < 2 ? 0 : Math.max(0, Math.min(1, 1 - dist / (w * 1.6))));
					const rect = dragRectRef.current;
					const box = tipBoxRef.current;
					if (rect !== null && box !== null) {
						tip.style.left = rect.left - box.left + HANDLE_W / 2 + (rect.width - HANDLE_W) * frac + "px";
					}
					if (near !== tipIdxRef.current) {
						tipIdxRef.current = near;
						if (tipTextRef.current !== null) tipTextRef.current.textContent = choices[near].label;
					}
				};
				function onWinMove(ev) {
					if (dragIdxRef.current === null) return;
					const rect = dragRectRef.current;
					if (rect === null) return;
					const frac = fracFromEvent(ev, rect);
					dragFracRef.current = frac;
					if (dragRafRef.current === null) {
						dragRafRef.current = requestAnimationFrame(() => {
							dragRafRef.current = null;
							paintPos(dragFracRef.current);
						});
					}
					const idx = idxFromFrac(frac);
					if (idx !== dragIdxRef.current) {
						dragIdxRef.current = idx;
						setHoverIdx(idx);
					}
				}
				/**
				* 停止拖拽并清理监听。
				*
				* 必须用函数声明而不是 const 箭头函数：组件在子代理会话
				* （subagentAddress 非空）或模型目录未就绪时会提前 return null，
				* 此时第 394 行的 useEffect 依然会在挂载后执行并调用本函数。
				* const 绑定在提前 return 的渲染里从未初始化，会抛
				* "Cannot access 'stopDrag' before initialization"，
				* 导致 conversation.input.model 槽位条目崩溃、回退原生选择器。
				* 函数声明在作用域入口即完成初始化，不受提前 return 影响。
				*/
				function stopDrag() {
					const el = dragElRef.current;
					if (el !== null) {
						el.removeEventListener("pointermove", onWinMove);
						el.removeEventListener("pointerup", onWinUp);
						el.removeEventListener("pointercancel", onWinCancel);
						el.removeEventListener("lostpointercapture", onWinCancel);
						if (dragPointerIdRef.current !== null && el.hasPointerCapture(dragPointerIdRef.current)) {
							try { el.releasePointerCapture(dragPointerIdRef.current); } catch (e) { /* already released */ }
						}
						dragElRef.current = null;
						dragPointerIdRef.current = null;
					}
					window.removeEventListener("blur", onWinCancel);
					if (dragRafRef.current !== null) {
						cancelAnimationFrame(dragRafRef.current);
						dragRafRef.current = null;
					}
					dragRectRef.current = null;
				}
				function onWinUp() {
					if (dragIdxRef.current === null) return;
					const idx = dragIdxRef.current;
					dragIdxRef.current = null;
					setMoving(false);
					stopDrag();
					if (pressTimerRef.current !== null) { clearTimeout(pressTimerRef.current); pressTimerRef.current = null; }
					setShowLabels(false);
					if (tipRef.current !== null) tipRef.current.style.opacity = "0";
					tipIdxRef.current = -1;
					const c = choices[idx];
					if (c !== void 0) {
						setHoverIdx(idx);
						onPickEffort(c.effort);
					}
				}
				function onWinCancel() {
					dragIdxRef.current = null;
					setMoving(false);
					if (pressTimerRef.current !== null) { clearTimeout(pressTimerRef.current); pressTimerRef.current = null; }
					setShowLabels(false);
					stopDrag();
					setHoverIdx(null);
				}
				const onTrackDown = (ev) => {
					if (choices.length === 0) return;
					const el = trackRef.current;
					if (el === null) return;
					if (ev.button !== 0) return;
					const rect = el.getBoundingClientRect();
					dragRectRef.current = rect;
					const tipEl = tipRef.current;
					tipBoxRef.current = tipEl !== null && tipEl.offsetParent !== null ? tipEl.offsetParent.getBoundingClientRect() : null;
					const frac = fracFromEvent(ev, rect);
					dragFracRef.current = frac;
					paintPos(frac);
					dragIdxRef.current = idxFromFrac(frac);
					setHoverIdx(dragIdxRef.current);
					setMoving(true);
					if (pressTimerRef.current !== null) clearTimeout(pressTimerRef.current);
					pressTimerRef.current = setTimeout(() => setShowLabels(true), 150);
					dragElRef.current = el;
					dragPointerIdRef.current = ev.pointerId;
					try { el.setPointerCapture(ev.pointerId); } catch (e) { /* capture unsupported */ }
					el.addEventListener("pointermove", onWinMove);
					el.addEventListener("pointerup", onWinUp);
					el.addEventListener("pointercancel", onWinCancel);
					el.addEventListener("lostpointercapture", onWinCancel);
					window.addEventListener("blur", onWinCancel);
				};				const triggerTitle = curGroup !== void 0 && curModel !== void 0 ? curGroup.name + " / " + curModel.name + (effectiveEffort !== void 0 ? " · " + displayLabel : "") : tr("trigger.selectModel");
				return react.createElement("div", {
					ref: rootRef,
					className: "sk5-root" + (menu !== null ? " ue-open" : ""),
					onKeyDown: (ev) => {
						if (ev.key !== "Tab") return;
						const rootEl = ev.currentTarget;
						requestAnimationFrame(() => {
							if (rootEl.contains(document.activeElement)) return;
							skipFocusReturnRef.current = true;
							requestClose(false);
						});
					}
				}, react.createElement("button", {
					ref: effortTriggerRef,
					type: "button",
					className: "ue-trigger",
					disabled: locked || busy || current === null,
					title: triggerTitle,
					"aria-haspopup": "dialog",
					"aria-expanded": menu === "effort",
					onClick: (ev) => {
						openedByKeyboardRef.current = ev.detail === 0;
						if (closeTimerRef.current !== null) { clearTimeout(closeTimerRef.current); closeTimerRef.current = null; }
						closingRef.current = false;
						setClosing(false);
						if (menu === "effort") { requestClose(); return; }
						setMenu("effort");
					}
				}, react.createElement("span", { className: "ue-triggerModel" }, curModel === void 0 ? modelLabel : renderModelLabel(curGroup, curModel)), react.createElement("span", { className: "ue-triggerLevel " + levelTone }, displayLabel), react.createElement("svg", {
					className: "ue-triggerChev",
					viewBox: "0 0 16 16",
					"aria-hidden": "true"
				}, react.createElement("path", { d: "M4 6l4 4 4-4" }))), react.createElement("span", {
					className: "ue-sr",
					role: "status",
					"aria-live": "polite"
				}, tr("sr.level").replace("{label}", displayLabel).replace("{i}", String(safePosIdx + 1)).replace("{n}", String(Math.max(choices.length, 1)))), react.createElement("span", {
					className: "ue-sr",
					id: hintIdRef.current
				}, tr("hint.slider")), (menu === "effort" || closing) ? react.createElement("div", {
					ref: panelRef,
					id: panelIdRef.current,
					"data-state": closing ? "closing" : "open",
					className: "sk5-drop sk5-effort ue-panel" + (closing ? " ue-closing" : ""),
					role: "dialog",
					"aria-label": tr("panel.aria")
				}, react.createElement("div", { className: "ue-head" }, react.createElement("span", {
					className: "ue-icon ue-bolt",
					"aria-hidden": "true"
				}, react.createElement("svg", { viewBox: "0 0 24 24" }, react.createElement("path", { d: "M13 2 3 14h7l-1 8 10-12h-7l1-8z" }))), react.createElement("div", { className: "ue-labels" + (showLabels ? " ue-labelsOn" : "") }, react.createElement("span", null, tr("label.faster")), react.createElement("span", null, tr("label.smarter"))), react.createElement("div", { className: "ue-center" }, react.createElement("div", { className: "ue-title " + titleTone }, displayLabel), react.createElement("button", {
					type: "button",
					ref: modelBtnRef,
					className: "ue-model" + (panelView === "model" ? " ue-modelOpen" : "") + (showLabels ? " ue-modelHidden" : ""),
					"aria-controls": panelIdRef.current,
					disabled: locked || busy,
					title: triggerTitle,
					"aria-haspopup": "listbox",
					"aria-expanded": panelView === "model",
					onClick: () => setPanelView((v) => v === "model" ? "effort" : "model")
				}, react.createElement("span", { className: "ue-modelName" }, curModel === void 0 ? modelLabel : renderModelLabel(curGroup, curModel)), react.createElement("svg", { className: "ue-modelChev", viewBox: "0 0 16 16", "aria-hidden": "true" }, react.createElement("path", { d: "M4 6l4 4 4-4" })))), react.createElement("button", {
					type: "button",
					className: "ue-icon ue-reset" + (resetFlash ? " ue-resetFlash" : "") + (atDefaultEffort ? " ue-resetHidden" : ""),
					"aria-hidden": atDefaultEffort ? "true" : void 0,
					tabIndex: atDefaultEffort ? -1 : 0,
					title: tr("reset.title"),
					"aria-label": tr("reset.aria"),
					disabled: locked || busy || current === null || reasoning === void 0,
					onClick: onReset
				}, react.createElement("svg", { viewBox: "0 0 16 16" }, react.createElement("path", { d: "M2.8 6.2A5.6 5.6 0 1 1 2.6 9.4" }), react.createElement("path", { d: "M2.4 2.4v4h4" })))), panelView === "model" ? react.createElement("div", {
					ref: modelsRef,
					className: "ue-models",
					role: "listbox",
					"aria-label": tr("trigger.selectModel")
				}, !loaded && shownError === null ? react.createElement("div", { className: "sk5-status" }, tr("status.loading")) : null, shownError !== null ? react.createElement("div", { className: "sk5-err" }, shownError) : null, loaded && groups.length === 0 ? react.createElement("div", { className: "sk5-status" }, tr("status.noModels")) : null, loaded ? groups.map((g, gi) => react.createElement("div", { key: g.id, className: "ue-group", role: "group", "aria-labelledby": "ue-g-" + gi }, react.createElement("div", { className: "ue-groupName", id: "ue-g-" + gi }, providerLabel(g)), g.models.map((m) => {
					const isCur = current !== null && current.provider === g.id && current.model === m.id;
					return react.createElement("button", {
						key: m.id,
						type: "button",
						role: "option",
						"aria-selected": isCur,
						ref: (el) => { rowRefs.current[flatIndexById.get(g.id + "\u0000" + m.id)] = el; },
						tabIndex: (flatIndexById.get(g.id + "\u0000" + m.id) === focusIdx) ? 0 : -1,
						onKeyDown: (ev) => onRowKeyDown(ev, flatIndexById.get(g.id + "\u0000" + m.id)),
						className: "ue-row" + (isCur ? " ue-rowActive" : ""),
						disabled: busy,
						onClick: () => {
							onPickModel(m, g);
							setPanelView("effort");
						}
					}, react.createElement("span", { className: "ue-rowText" }, react.createElement("span", { className: "ue-rowName" }, renderModelLabel(g, m)), m.description !== void 0 ? react.createElement("span", { className: "ue-rowDesc" }, m.description) : null), isCur ? react.createElement("span", { className: "ue-check" }, "✓") : null);
				}))) : null) : react.createElement("div", { className: "ue-sliderArea" + (showLabels ? " ue-labelsOn" : "") }, react.createElement("div", { className: "ue-sliderRow" }, react.createElement("div", {
					ref: trackRef,
					className: "sk5-track ue-track" + (inMax ? " ue-trackMax" : "") + (moving ? " ue-moving" : "") + (burst ? " ue-burst" : "") + (showLabels ? " ue-labelsOn" : ""),
					role: "slider",
					tabIndex: 0,
					"aria-label": tr("slider.aria"),
					"aria-describedby": hintIdRef.current,
					"aria-valuemin": 0,
					"aria-valuemax": Math.max(0, choices.length - 1),
					"aria-valuenow": safePosIdx,
					"aria-valuetext": displayLabel,
					onPointerDown: onTrackDown,
					onKeyDown: onTrackKeyDown
				}, react.createElement("div", { className: "ue-fill" }), react.createElement("div", { className: "ue-ultraLayer", "aria-hidden": "true" }), react.createElement("div", { className: "ue-stream", "aria-hidden": "true" }, streamDots.map((d, i) => react.createElement("i", { key: i, style: { top: d.top, animationDuration: d.dur, animationDelay: d.delay } }))), react.createElement("div", { className: "ue-burstLayer", "aria-hidden": "true" }, react.createElement("span", null), react.createElement("span", null), react.createElement("span", null), react.createElement("span", null), react.createElement("span", null), react.createElement("span", null), react.createElement("span", null), react.createElement("span", null), react.createElement("span", null), react.createElement("span", null), react.createElement("span", null), react.createElement("span", null), react.createElement("span", null), react.createElement("span", null), react.createElement("span", null), react.createElement("span", null)), choices.map((c, i) => react.createElement("span", {
					key: c.key,
					className: "ue-tick" + (i <= safePosIdx ? " ue-tickOn" : ""),
					style: { left: tickLeft(i) }
				})), react.createElement("div", { className: "ue-handle" })))), shownError !== null ? react.createElement("div", { className: "sk5-err" }, shownError) : null) : null);
			}));
		}
		//#endregion
		exports.apply = apply;
		exports.inject = inject;
		return module.exports;
	}
});
