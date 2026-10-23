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
				const ULTRA_CSS = `
/* ── Ultra 面板 V7 · Codex 原型对齐 ─────────────────────────────
   尺寸基准：面板 266×~100、padding 4、头部 min-height 56、滑杆行 32。
   选择器统一 .sk5-root 前缀提高特异性，不使用 important 声明。
   ───────────────────────────────────────────────────────────── */
.sk5-root .sk5-drop{font-family:inherit;}
.sk5-root{--ue-blue:#3a83f7;--ue-purple:#924ff7;--ue-tertiary:rgba(15,23,42,.38);--ue-secondary:rgba(15,23,42,.55);--ue-track:color-mix(in srgb,var(--dsw-alias-label-primary,#0f172a) 10%,transparent);--ue-motion:cubic-bezier(.23,1,.32,1);}
/* 触发器：模型名 + 档位名 + ▾ 合并成一个按钮 */
.sk5-root .ue-trigger{display:inline-flex;align-items:center;gap:4px;max-width:260px;padding:2px 6px;border:0;border-radius:8px;background:transparent;font-size:13px;line-height:20px;color:var(--dsw-alias-label-primary,#0f172a);cursor:pointer;transition:background .14s ease;}
.sk5-root .ue-trigger:hover{background:rgba(15,23,42,.06);}
.sk5-root.ue-open .ue-trigger{background:rgba(15,23,42,.08);}
.sk5-root .ue-trigger[disabled]{opacity:.5;cursor:default;}
.sk5-root .ue-triggerModel{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.sk5-root .ue-triggerLevel{flex:none;font-weight:500;}
.sk5-root .ue-triggerChev{width:12px;height:12px;flex:none;fill:none;stroke:currentColor;stroke-width:1.6;opacity:.45;transition:transform .18s var(--ue-motion);}
.sk5-root.ue-open .ue-triggerChev{transform:rotate(180deg);}
/* 档位配色 */
.sk5-root .ue-lv-max{color:var(--ue-purple);}
.sk5-root .ue-lv-norm{color:var(--ue-blue);}
.sk5-root .ue-lv-def{color:rgba(15,23,42,.45);}
.sk5-root .ue-lv-text{color:var(--dsw-alias-label-primary,#0f172a);}
.sk5-root .ue-resetHidden{visibility:hidden;pointer-events:none;}
/* 面板 */
.sk5-root .sk5-drop{bottom:calc(100% + 8px);right:var(--ue-drop-right,0px);}
.sk5-root .sk5-drop.ue-panel{width:min(266px,calc(100vw - 24px));padding:4px;border-radius:14px;border:1px solid rgba(15,23,42,.08);background:var(--dsw-alias-bg-elevated,#fff);box-shadow:0 12px 32px rgba(15,23,42,.16),0 2px 8px rgba(15,23,42,.06);overflow:hidden;}
/* 头部 */
.sk5-root .ue-head{position:relative;display:flex;align-items:center;justify-content:center;min-height:46px;padding:2px 36px 4px;}
.sk5-root .ue-center{display:flex;flex-direction:column;align-items:center;gap:1px;min-width:0;max-width:100%;}
.sk5-root .ue-title{font-size:16px;line-height:22px;font-weight:500;letter-spacing:.01em;}
.sk5-root .ue-model{display:inline-flex;align-items:center;gap:2px;max-width:100%;padding:2px 4px;border:0;border-radius:6px;background:transparent;color:var(--ue-secondary);font-size:12px;line-height:16px;font-weight:400;cursor:pointer;transition:background .12s ease;}
.sk5-root .ue-model:hover{background:rgba(15,23,42,.06);}
.sk5-root .ue-model[aria-expanded="true"] .ue-modelChev{transform:rotate(180deg);}
.sk5-root .ue-model:focus-visible{outline:2px solid rgba(58,131,247,.7);outline-offset:1px;}
.sk5-root .ue-modelName{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.sk5-root .ue-modelChev{flex:none;width:12px;height:12px;fill:none;stroke:currentColor;stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round;opacity:.5;transition:transform .18s var(--ue-motion);}
.sk5-root .ue-icon{position:absolute;top:50%;transform:translateY(-50%);display:flex;align-items:center;justify-content:center;width:32px;height:32px;padding:0;border:0;border-radius:7px;background:transparent;color:var(--ue-tertiary);cursor:pointer;transition:background .12s ease,color .12s ease;}
.sk5-root .ue-icon:hover{background:rgba(15,23,42,.06);color:rgba(15,23,42,.6);}
.sk5-root .ue-icon:active{transform:translateY(-50%) scale(.94);}
.sk5-root .ue-icon:focus-visible{outline:2px solid rgba(58,131,247,.7);outline-offset:1px;}
.sk5-root .ue-icon svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.4;stroke-linecap:round;stroke-linejoin:round;}
.sk5-root .ue-bolt{left:2px;}
.sk5-root .ue-reset{right:2px;}
.sk5-root .ue-resetFlash{background:rgba(146,79,247,.14);color:var(--ue-purple);}
/* 滑杆区 */
.sk5-root .ue-sliderArea{position:relative;margin-inline:2px;padding:1px 6px 2px;}
.sk5-root .ue-sliderRow{position:relative;height:32px;display:flex;align-items:center;}
.sk5-root .ue-track{corner-shape:round;position:relative;width:100%;height:24px;border-radius:12px;background:var(--ue-track);box-shadow:inset 0 0 0 .5px rgba(15,23,42,.12);cursor:pointer;touch-action:none;outline:none;overflow:visible;isolation:isolate;transition:background .2s ease;}
.sk5-root .ue-fill{corner-shape:round;position:absolute;left:0;top:0;bottom:0;width:calc(28px + (100% - 28px) * var(--ue-pos,0));border-radius:12px;background:var(--ue-blue);transition:width .3s var(--ue-motion),opacity .2s ease;z-index:1;}
.sk5-root .ue-trackMax .ue-fill{opacity:0;}
/* Ultra 渐变 + 揭示 */
.sk5-root .ue-ultraLayer{position:absolute;inset:0;border-radius:12px;background:linear-gradient(90deg,color-mix(in srgb,#3a83f7 60%,#924ff7) 0%,#924ff7 55%,color-mix(in srgb,#924ff7 72%,#3a83f7) 100%);opacity:0;pointer-events:none;z-index:1;}
.sk5-root .ue-trackMax .ue-ultraLayer{opacity:1;animation:ue-reveal 2s cubic-bezier(.19,1,.22,1) both;}
.sk5-root .ue-ultraLayer::after{content:"";position:absolute;inset:0;border-radius:12px;background-image:radial-gradient(ellipse 50% 120% at 50% 50%,rgba(196,160,255,.55) 0%,rgba(196,160,255,0) 72%);background-size:40% 100%;background-repeat:no-repeat;background-position:-12% 50%;animation:ue-sheen 10s ease-in-out infinite alternate;pointer-events:none;}
@keyframes ue-sheen{0%{background-position:-12% 50%}100%{background-position:112% 50%}}
@keyframes ue-reveal{0%{-webkit-mask-position:110% 0;mask-position:110% 0}100%{-webkit-mask-position:0 0;mask-position:0 0}}
.sk5-root .ue-ultraLayer{-webkit-mask-image:linear-gradient(90deg,#000 0%,#000 62%,transparent 100%);-webkit-mask-size:220% 100%;-webkit-mask-repeat:no-repeat;mask-image:linear-gradient(90deg,#000 0%,#000 62%,transparent 100%);mask-size:220% 100%;mask-repeat:no-repeat;}
/* 持续流动光点 */
.sk5-root .ue-stream{position:absolute;inset:0;border-radius:12px;overflow:hidden;pointer-events:none;opacity:0;transition:opacity .35s ease;z-index:2;}
.sk5-root .ue-trackMax .ue-stream{opacity:1;}
.sk5-root .ue-stream i{corner-shape:round;position:absolute;width:3px;height:3px;border-radius:999px;background:#ffffffb8;box-shadow:0 0 5px #ffffff57;animation-name:ue-flow;animation-timing-function:linear;animation-iteration-count:infinite;}
.sk5-root .ue-stream i:nth-child(1){top:28%;animation-delay:-.2s}
.sk5-root .ue-stream i:nth-child(2){top:58%;animation-delay:-1.1s}
.sk5-root .ue-stream i:nth-child(3){top:40%;animation-delay:-2.0s}
.sk5-root .ue-stream i:nth-child(4){top:68%;animation-delay:-2.8s}
.sk5-root .ue-stream i:nth-child(5){top:34%;animation-delay:-1.6s}
.sk5-root .ue-stream i:nth-child(6){top:52%;animation-delay:-.7s}
.sk5-root .ue-stream i:nth-child(7){top:46%;animation-delay:-2.4s}
.sk5-root .ue-stream i:nth-child(8){top:62%;animation-delay:-3.2s}
@keyframes ue-flow{0%{left:102%;opacity:0}8%{opacity:1}92%{opacity:1}100%{left:-2%;opacity:0}}
/* 迸发 */
.sk5-root .ue-burstLayer{position:absolute;left:0;top:50%;width:1px;height:1px;pointer-events:none;z-index:3;opacity:0;}
.sk5-root .ue-track.ue-burst .ue-burstLayer{opacity:1;}
.sk5-root .ue-burstLayer span{position:absolute;left:0;top:0;width:5px;height:5px;border-radius:999px;background:var(--ue-purple);transform:translate(-50%,-50%) scale(.2);opacity:0;}
.sk5-root .ue-track.ue-burst .ue-burstLayer span{animation:ue-burst .62s cubic-bezier(.25,1,.5,1) both;}
.sk5-root .ue-burstLayer span:nth-child(4n+3){background:color-mix(in srgb,var(--ue-purple) 82%,var(--ue-blue));}
.sk5-root .ue-burstLayer span:nth-child(4n+1):not(:first-child){background:color-mix(in srgb,var(--ue-purple) 68%,var(--ue-blue));}
.sk5-root .ue-burstLayer span:nth-child(1){--x:-3px;--y:-34px}
.sk5-root .ue-burstLayer span:nth-child(2){--x:15px;--y:-29px;animation-delay:8ms}
.sk5-root .ue-burstLayer span:nth-child(3){--x:30px;--y:-19px}
.sk5-root .ue-burstLayer span:nth-child(4){--x:34px;--y:-2px;animation-delay:12ms}
.sk5-root .ue-burstLayer span:nth-child(5){--x:26px;--y:20px}
.sk5-root .ue-burstLayer span:nth-child(6){--x:12px;--y:31px;animation-delay:10ms}
.sk5-root .ue-burstLayer span:nth-child(7){--x:-6px;--y:34px}
.sk5-root .ue-burstLayer span:nth-child(8){--x:-22px;--y:26px;animation-delay:14ms}
.sk5-root .ue-burstLayer span:nth-child(9){--x:-32px;--y:9px}
.sk5-root .ue-burstLayer span:nth-child(10){--x:-32px;--y:-10px;animation-delay:8ms}
.sk5-root .ue-burstLayer span:nth-child(11){--x:-21px;--y:-26px}
.sk5-root .ue-burstLayer span:nth-child(12){--x:7px;--y:-24px;animation-delay:6ms}
.sk5-root .ue-burstLayer span:nth-child(13){--x:24px;--y:-9px}
.sk5-root .ue-burstLayer span:nth-child(14){--x:20px;--y:10px;animation-delay:10ms}
.sk5-root .ue-burstLayer span:nth-child(15){--x:-9px;--y:21px}
.sk5-root .ue-burstLayer span:nth-child(16){--x:-25px;--y:-5px;animation-delay:12ms}
@keyframes ue-burst{0%{opacity:1;transform:translate(-50%,-50%) scale(.2)}100%{opacity:0;transform:translate(calc(-50% + var(--x)),calc(-50% + var(--y))) scale(.55)}}
/* 刻度点 */
.sk5-root .ue-tick{corner-shape:round;position:absolute;top:50%;width:4px;height:4px;margin:-2px 0 0 -2px;border-radius:999px;background:color-mix(in srgb,var(--dsw-alias-label-primary,#0f172a) 50%,transparent);pointer-events:none;transition:transform .12s ease,opacity .2s ease;z-index:3;}
.sk5-root .ue-tickOn{background:rgba(255,255,255,.3);}
.sk5-root .ue-trackMax .ue-tick{opacity:0;}
.sk5-root .ue-track:hover .ue-tick{transform:scale(1.6);}
/* 手柄 */
.sk5-root .ue-handle{corner-shape:round;border-radius:999px;position:absolute;box-sizing:border-box;top:50%;left:calc(14px + (100% - 28px) * var(--ue-pos,0));width:28px;height:28px;margin:-14px 0 0 0;border-radius:999px;background:#fff;border:.5px solid rgba(15,23,42,.28);box-shadow:0 0 2px rgba(0,0,0,.1);transform:translateX(-50%);z-index:4;will-change:left;transition:left .3s var(--ue-motion),transform .18s var(--ue-motion),box-shadow .18s ease;}
.sk5-root .ue-moving .ue-handle{transition:left .15s var(--ue-motion),transform .18s var(--ue-motion),box-shadow .18s ease;transform:translateX(-50%) scale(1.14);box-shadow:0 0 2px rgba(0,0,0,.1),0 2px 8px rgba(15,23,42,.18);}
.sk5-root .ue-track:focus-visible{outline:none;}
.sk5-root .ue-track:focus-visible .ue-handle{outline:2px solid rgba(58,131,247,.85);outline-offset:1px;}
.sk5-root:not(.ue-kb) .ue-track:focus-visible .ue-handle{outline:none;}
/* 端点标签：按住 150ms 才出现 */
.sk5-root .ue-labels{position:absolute;left:8px;right:8px;bottom:2px;display:flex;align-items:center;justify-content:space-between;pointer-events:none;opacity:0;transition:opacity .15s var(--ue-motion);font-size:11px;line-height:14px;color:var(--ue-tertiary);z-index:6;}
.sk5-root .ue-labels.ue-labelsOn{opacity:1;}
.sk5-root .ue-model.ue-modelHidden{opacity:0;pointer-events:none;}
.sk5-root .ue-model{transition:opacity .15s var(--ue-motion),background .12s ease;}
/* 内容进场 */
.sk5-root .ue-head{opacity:0;translate:0 10px;animation:ue-enter .2s var(--ue-motion) 40ms both;}
.sk5-root .ue-sliderArea{opacity:0;translate:0 10px;animation:ue-enter .2s var(--ue-motion) 56ms both;}
@keyframes ue-enter{to{opacity:1;translate:0 0}}
@keyframes ue-list-in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
/* 模型列表 */
.sk5-root .ue-models{margin:2px -2px 0;padding:0 2px 4px;max-height:min(280px,45vh);overflow-y:auto;overscroll-behavior:contain;scrollbar-width:thin;scrollbar-color:rgba(15,23,42,.18) transparent;animation:ue-list-in .18s cubic-bezier(.23,1,.32,1) both;}
.sk5-root .ue-models::-webkit-scrollbar{width:4px;height:4px;}
.sk5-root .ue-models::-webkit-scrollbar-track{background:transparent;}
.sk5-root .ue-models::-webkit-scrollbar-thumb{background:rgba(15,23,42,.18);border-radius:999px;}
.sk5-root .ue-modelsTitle{margin:4px 2px 8px;font-size:11px;line-height:14px;font-weight:500;letter-spacing:.02em;color:rgba(15,23,42,.45);}
.sk5-root .ue-group{margin-top:12px;}
.sk5-root .ue-modelsTitle + .ue-group{margin-top:2px;}
.sk5-root .ue-groupName{margin:0 2px 4px;font-size:11px;line-height:15px;font-weight:500;letter-spacing:0;text-transform:none;color:rgba(15,23,42,.42);cursor:default;user-select:none;}
.sk5-root .ue-row{display:flex;align-items:center;justify-content:space-between;gap:10px;width:calc(100% - 14px);margin-left:14px;min-height:34px;padding:7px 10px;border:0;border-radius:10px;background:transparent;text-align:left;cursor:pointer;color:var(--dsw-alias-label-primary,#0f172a);transition:background .14s ease;}
.sk5-root .ue-rowHasDesc{min-height:44px;}
.sk5-root .ue-row:hover{background:rgba(15,23,42,.05);}
.sk5-root .ue-row:focus-visible{outline:2px solid rgba(58,131,247,.7);outline-offset:-2px;}
.sk5-root .ue-rowActive{background:rgba(58,131,247,.10);}
.sk5-root .ue-rowText{display:flex;flex-direction:column;min-width:0;}
.sk5-root .ue-rowName{font-size:13px;line-height:18px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.sk5-root .ue-rowDesc{margin-top:2px;font-size:11px;line-height:15px;color:rgba(15,23,42,.48);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.sk5-root .ue-check{flex:none;color:var(--ue-blue);font-size:14px;line-height:1;}
/* 屏幕阅读器 */
.sk5-root .ue-sr{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0;}
/* 减少动画 */
@media (prefers-reduced-motion: reduce){
.sk5-root .ue-head,.sk5-root .ue-sliderArea,.sk5-root .ue-models{animation:none;opacity:1;translate:0 0;transform:none;}
.sk5-root .ue-modelChev,.sk5-root .ue-triggerChev{transition:none;}
.sk5-root .ue-model[aria-expanded="true"] .ue-modelChev{transform:none;}
.sk5-root .ue-ultraLayer,.sk5-root .ue-stream i,.sk5-root .ue-burstLayer span,.sk5-root .ue-tick,.sk5-root .ue-handle,.sk5-root .ue-fill{animation:none;transition:none;}
.sk5-root .ue-trackMax .ue-ultraLayer{-webkit-mask-image:none;mask-image:none;}
.sk5-root .ue-ultraLayer::after{animation:none;background-position:60% 50%;}
}
`;		const NS = "ui-skin-switcher";
		/** Plugin-owned copy: `zh` is the key-set source of truth, `en` mirrors it. */
		const DICTS = {
			zh: {
				"trigger.fallbackModel": "模型",
				"trigger.selectModel": "选择模型",
				"effort.title": "思考强度",
				"effort.default": "默认",
				"menu.models": "模型",
				"status.loading": "加载中…",
				"status.noModels": "暂无可用模型",
				"help.aria": "思考强度说明",
				"help.text": "调节模型推理深度，低强度回复快、内容简洁；高强度思考更全面，适合复杂问题，响应会稍慢。"
			},
			en: {
				"trigger.fallbackModel": "Model",
				"trigger.selectModel": "Select model",
				"effort.title": "Reasoning effort",
				"effort.default": "Default",
				"menu.models": "Models",
				"status.loading": "Loading…",
				"status.noModels": "No models available",
				"help.aria": "About reasoning effort",
				"help.text": "Adjusts how deeply the model reasons: lower effort answers faster and more concisely, while higher effort thinks more thoroughly for complex problems and responds a little slower."
			}
		};
		/** Dot-matrix rows to render. */
		const MATRIX_ROWS = 5;
		/** Designed track height in CSS px; the matrix is solved to land near it. */
		const MATRIX_TRACK_DESIGN = 23;
		/** Smallest block edge, in device px, that still reads as a square rather than a dot. */
		const MATRIX_MIN_BLOCK_DEV = 3;
		/** Design gap between blocks, in CSS px at 100% scaling. */
		const MATRIX_GAP_DESIGN = 1;
		/** Design margin above the first and below the last block row, in CSS px. */
		const MATRIX_MARGIN_DESIGN = .5;
		/** Flash cycle length in seconds, matching the `.sk5-sq` animation shorthand. */
		const FLASH_CYCLE_S = 1.7;
		/** Per-cell cycle spread (±8%): drifts the phases apart so no pattern repeats. */
		const FLASH_JITTER = .08;
		/**
		* Resolve the dot-matrix grid in whole device pixels. Rounding the sizes here —
		* instead of handing the browser a fractional remainder — is what keeps the
		* matrix uniform: a fractional pitch rasterizes as alternating 7/8px gaps, and
		* a centered fractional remainder leaves one edge with a different gap.
		*
		* The matrix carries no vertical margin: `rows * block + (rows - 1) * gap` is
		* both the content and the track height, so the first row starts at the track's
		* top edge and the last row ends at its bottom edge. The track is re-heighted to
		* that value because a fixed 26px track is 39 device px at 150%, which no
		* six-row arrangement fills with square blocks and a one-pixel gap.
		* @param wDev - track width in whole device pixels.
		* @param dpr - device pixels per CSS px.
		* @returns the resolved layout.
		*/
		function solveMatrix(wDev, dpr) {
			const gap = Math.max(1, Math.round(MATRIX_GAP_DESIGN * dpr));
			const margin = Math.max(1, Math.round(MATRIX_MARGIN_DESIGN * dpr));
			const rows = MATRIX_ROWS;
			const block = Math.max(MATRIX_MIN_BLOCK_DEV, Math.round((MATRIX_TRACK_DESIGN * dpr - 2 * margin - 4 * gap) / rows));
			const cols = Math.max(1, Math.floor((wDev + gap) / (block + gap)));
			const restX = wDev - (cols * block + (cols - 1) * gap);
			const padX = Math.floor(restX / 2);
			return {
				c: cols,
				r: rows,
				sq: block / dpr,
				gap: gap / dpr,
				radius: block * .3 / dpr,
				trackHeight: (2 * margin + rows * block + 4 * gap) / dpr,
				trackWDev: wDev,
				padTop: margin / dpr,
				padBottom: margin / dpr,
				padLeft: padX / dpr,
				padRight: (restX - padX) / dpr
			};
		}
		/**
		* Scatter one cell's phase. A linear rule such as `(7r + 13c) % 29` maps
		* neighbours onto a regular lattice, which the eye reads as diagonal bands;
		* avalanching both coordinates first scatters them instead. The result stays
		* continuous rather than quantised into buckets: with 29 buckets up to 14 cells
		* share a phase and flip in the very same instant, every round — a synchrony
		* the eye picks up even though the arrangement itself is random.
		* @param r - grid row.
		* @param c - grid column.
		* @param seed - keeps independent scatters (phase, brightness) uncorrelated.
		* @returns a value in `[0, 1)`.
		*/
		function cellUnit(r, c, seed) {
			let h = Math.imul(r + 1, 2654435761) ^ Math.imul(c + 1, 2246822507) ^ Math.imul(seed, 668265263);
			h = Math.imul(h ^ h >>> 15, 625341585);
			h ^= h >>> 13;
			return (h >>> 0) / 4294967296;
		}
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
		const CSS = ".sk5-root{position:relative;display:inline-flex;}.sk5-triggers{display:inline-flex;align-items:center;gap:2px;}.sk5-trigger{display:inline-flex;align-items:center;padding:4px 8px;border-radius:10px;border:none;background:transparent;color:var(--dsw-alias-label-primary);font-size:12.5px;cursor:pointer;max-width:210px;}.sk5-trigger:hover{background:color-mix(in srgb,var(--dsw-alias-label-primary) 10%,transparent);}.sk5-trigger:disabled{opacity:.55;cursor:not-allowed;}.sk5-triggerName{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}.sk5-triggerEffort{color:var(--dsw-alias-brand-primary);line-height:var(--sk5-effort-line-height,inherit);}.sk5-drop{font-family:var(--dsw-font-family,ui-sans-serif,system-ui,sans-serif);position:absolute;bottom:calc(100% + 6px);right:0;border-radius:14px;border:1px solid var(--dsw-alias-border-l2);background:var(--dsw-alias-bg-layer-1);box-shadow:0 10px 32px rgb(0 0 0 / .35);z-index:1200;color:var(--dsw-alias-label-primary);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);}.sk5-model{width:256px;}.sk5-modelsTitle{font-size:14px;font-weight:700;color:var(--dsw-alias-label-secondary);padding:12px 14px 6px;text-align:left;}.sk5-list{overflow-y:auto;padding:2px 6px 10px;max-height:min(420px,60vh);}.sk5-group{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--dsw-alias-label-tertiary);padding:8px 10px 3px;text-align:left;}.sk5-row{display:flex;align-items:center;justify-content:space-between;gap:8px;width:100%;text-align:left;padding:6px 10px;border-radius:12px;border:none;background:transparent;color:var(--dsw-alias-label-primary);font-size:12.5px;cursor:pointer;}.sk5-row:hover{background:color-mix(in srgb,var(--dsw-alias-label-primary) 10%,transparent);}.sk5-row:disabled{opacity:.6;cursor:wait;}.sk5-rowDesc{font-size:11px;color:var(--dsw-alias-label-secondary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}.sk5-check{font-size:12px;color:var(--dsw-alias-brand-primary);}.sk5-status{padding:14px;font-size:12.5px;opacity:.65;text-align:center;}.sk5-err{padding:8px 4px 0;font-size:11.5px;color:var(--dsw-alias-state-error-primary);text-align:left;}.sk5-effort{width:225px;max-width:calc(100vw - 32px);box-sizing:border-box;padding:10px 12px 12px;}.sk5-titleRow{display:flex;align-items:center;gap:8px;margin-bottom:8px;}.sk5-effortLabel{font-size:13px;font-weight:600;color:var(--dsw-alias-label-secondary);}.sk5-help{position:relative;margin-left:auto;display:inline-flex;}/* The ring is an SVG stroke, not a CSS border or gradient: a vector stroke is anti-aliased by the rasterizer at every size, while a sub-pixel gradient ring at this diameter quantises into visible steps. The ring inherits currentColor, so the existing hover colour change lights it up. */.sk5-helpBtn{position:relative;width:16px;height:16px;min-width:0;min-height:0;box-sizing:border-box;padding:0;border:none;box-shadow:none;outline:none;border-radius:50%;clip-path:circle(50%);background:transparent;color:var(--dsw-alias-label-secondary);font-size:11px;line-height:1;display:flex;align-items:center;justify-content:center;cursor:help;flex:none;appearance:none;}.sk5-helpRing{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;overflow:visible;}.sk5-helpQ{position:relative;}.sk5-helpBtn:hover{color:var(--dsw-alias-label-primary);}.sk5-helpTip{font-family:var(--dsw-font-family,ui-sans-serif,system-ui,sans-serif);position:absolute;top:calc(100% + 6px);right:0;width:206px;box-sizing:border-box;background:var(--dsw-alias-bg-layer-1);border:1px solid var(--dsw-alias-border-l2);border-radius:8px;padding:8px 10px;box-shadow:0 8px 24px rgb(0 0 0 / .35);z-index:20;backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);opacity:0;visibility:hidden;pointer-events:none;transition:opacity .12s ease,visibility .12s ease;}.sk5-helpBtn:hover ~ .sk5-helpTip{opacity:1;visibility:visible;}.sk5-helpTip:hover{opacity:1;visibility:visible;}.sk5-helpTip::before{content:\"\";position:absolute;top:-8px;left:0;right:0;height:8px;}.sk5-helpTitle{font-size:12.5px;font-weight:600;color:var(--dsw-alias-label-primary);margin-bottom:3px;text-align:left;}.sk5-helpText{font-size:11.5px;line-height:1.55;color:var(--dsw-alias-label-secondary);text-align:left;}.sk5-effortValue{font-size:13px;font-weight:600;color:var(--dsw-alias-label-primary);line-height:var(--sk5-effort-line-height,inherit);}.sk5-effortValueMax{color:var(--dsw-static-deepseek-400);}@keyframes sk5-nameBlur{from{filter:blur(5px);opacity:.3}to{filter:blur(0);opacity:1}}.sk5-labelsRow{display:flex;justify-content:space-between;margin-bottom:6px;}.sk5-endLabel{font-size:12.5px;font-weight:600;color:var(--dsw-alias-label-secondary);}.sk5-track{position:relative;height:23px;border-radius:9px;background:color-mix(in srgb,var(--dsw-alias-label-primary) 15%,transparent);cursor:pointer;touch-action:none;user-select:none;-webkit-user-select:none;}.sk5-fill{position:absolute;top:0;bottom:0;left:0;border-radius:9px 0 0 9px;transition:width .16s ease,opacity .16s ease;pointer-events:none;}.sk5-fillEnd{border-radius:9px;}.sk5-dotHit{position:absolute;top:0;bottom:0;width:16px;transform:translateX(-50%);display:flex;align-items:flex-start;justify-content:center;cursor:pointer;z-index:2;}/* The dot is drawn as an SVG circle rather than a CSS background: at 4px on a 150% display that is a 6-device-pixel disc, and a vector circle is coverage-antialiased far more evenly than a border-radius fill at this size. The span keeps the 50% box radius so the hover glow stays circular. *//* The level marks and the handle are pinned to the theme static white instead of the alias label token: they must stay white in both appearances, so they never follow the light-mode near-black value. Only the top level keeps its brand blue. */.sk5-dot{width:4px;height:4px;min-width:0;min-height:0;flex:none;border-radius:50%;background:transparent;color:var(--dsw-static-neutral-bluish-00);opacity:.9;pointer-events:none;transition:opacity .12s ease;}.sk5-dotShape{display:block;width:100%;height:100%;overflow:visible;}/* Hover lights a soft halo with drop-shadow, not box-shadow: drop-shadow follows the painted alpha (our SVG circle), while box-shadow follows the element box — and the host overrides this span's border-radius, so a box-shadow halo came out as a blurred square with diamond corners. The resting state carries no filter at all: any filter, even a zero-blur one, moves the element onto its own rasterization layer and changes how this 6-device-pixel circle is antialiased. */.sk5-dotHit:hover .sk5-dot{opacity:1;}.sk5-dotShape{transition:filter .14s ease;filter:none;}.sk5-dotHit:hover .sk5-dotShape{filter:drop-shadow(0 0 2.5px currentColor);}.sk5-dotMax{color:var(--dsw-static-deepseek-400);}.sk5-handle{position:absolute;top:0;bottom:0;width:20px;border-radius:9px;background:var(--dsw-static-neutral-bluish-00);transform:translateX(-50%);box-shadow:0 0 0 transparent;transition:left .16s ease,transform .16s ease,box-shadow .5s ease,background-color .5s ease;z-index:3;cursor:grab;}.sk5-handleMax{background:color-mix(in srgb, var(--dsw-static-deepseek-450) 25%, var(--dsw-static-neutral-bluish-00));box-shadow:0 0 10px color-mix(in srgb, var(--dsw-static-deepseek-400) 90%, transparent);}.sk5-handleMoving{transform:translateX(-50%) scale(1.14);}.sk5-handleMax{background:color-mix(in srgb, var(--dsw-static-deepseek-450) 25%, var(--dsw-static-neutral-bluish-00));box-shadow:0 0 10px color-mix(in srgb, var(--dsw-static-deepseek-400) 90%, transparent);}/* Day mode only: a soft grey-black halo around the white knob, so that where it meets an equally white dropdown panel its own pixel edge is masked instead of showing. Night mode keeps the bare handle, and the top level keeps its blue glow. The host removes data-ds-dark-theme from <body> in the light appearance, so :not() is the day-mode test. */body:not([data-ds-dark-theme]) .sk5-handle:not(.sk5-handleMax){box-shadow:0 0 3px rgb(0 0 0 / .28);}.sk5-matrix{position:absolute;top:0;left:0;right:0;bottom:0;overflow:hidden;border-radius:9px;pointer-events:none;z-index:1;box-sizing:border-box;display:grid;gap:1px;justify-content:start;align-content:start;}.sk5-cell{width:100%;height:100%;opacity:0;animation:sk5-appear .6s ease forwards;}@keyframes sk5-appear{from{opacity:.1}to{opacity:1}}.sk5-sq{width:100%;height:100%;border-radius:1px;animation:sk5-flash 1.45s infinite ease-in-out;}/* One flash cycle: hold blue 250ms, jump to light, hold light 480ms, fade back over 720ms. */@keyframes sk5-flash{0%,29.41%{background:var(--dsw-static-deepseek-500)}29.42%,57.65%{background:var(--flash-light,var(--dsw-static-deepseek-400))}100%{background:var(--dsw-static-deepseek-500)}}";
		/**
		* Keep the existing Latin-label line box on each platform. A fixed numeric
		* line-height would also stop fallback-font jumps, but resize the working UI
		* on platforms whose native font metrics differ. Measure our own font only;
		* computed CSS height excludes ancestor transforms and display scaling.
		*/
		function measureEffortLineHeight(element) {
			const previous = element.style.getPropertyValue("--sk5-effort-line-height");
			element.style.removeProperty("--sk5-effort-line-height");
			const font = window.getComputedStyle(element);
			const inheritedLineHeight = font.lineHeight;
			const nativeFont = [
				"fontSize",
				"fontFamily",
				"fontWeight",
				"fontStyle",
				"fontStretch",
				"fontVariationSettings",
				"fontFeatureSettings",
				"fontSizeAdjust",
				"fontOpticalSizing"
			].map((key) => [key, font[key]]);
			if (previous !== "") element.style.setProperty("--sk5-effort-line-height", previous);
			if (Number.parseFloat(inheritedLineHeight) > 0) return inheritedLineHeight;
			const sample = document.createElement("span");
			sample.textContent = "Max";
			sample.style.cssText = "position:absolute;visibility:hidden;pointer-events:none;display:block;white-space:nowrap;line-height:normal;margin:0;padding:0;border:0;width:auto;height:auto;min-height:0;max-height:none;";
			for (const [key, value] of nativeFont) sample.style[key] = value;
			sample.style.lineHeight = "normal";
			element.appendChild(sample);
			try {
				const height = window.getComputedStyle(sample).height;
				return Number.parseFloat(height) > 0 ? height : null;
			} finally {
				sample.remove();
			}
		}
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
				/**
				* Read one dictionary key through the framework-injected `t` seat; the
				* Chinese table backs a host that shipped no locale service.
				*/
				const tr = (key) => typeof t === "function" ? t(key) : DICTS.zh[key] ?? key;
				const [menu, setMenu] = react.useState(null);
				const [busyKind, setBusy] = react.useState(null);
				const busy = busyKind !== null;
				const [error, setError] = react.useState(null);
				const [hoverIdx, setHoverIdx] = react.useState(null);
				const [grid, setGrid] = react.useState(null);
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
				const dragRafRef = react.useRef(null);
				const tipRef = react.useRef(null);
				const tipTextRef = react.useRef(null);
				const tipIdxRef = react.useRef(-1);
				const tipBoxRef = react.useRef(null);
				const panelRef = react.useRef(null);
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
						if (trackRef.current !== null) trackRef.current.focus({ preventScroll: true });
					} else if (menu === null && prev !== null) {
						if (effortTriggerRef.current !== null) effortTriggerRef.current.focus({ preventScroll: true });
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
						setMenu(null);
					};
					/** V2: Escape 先在面板内退出模型列表，再关闭整个面板。 */
					const onKey = (ev) => {
						if (ev.key !== "Escape") return;
						if (menu === "effort" && panelView === "model") {
							setPanelView("effort");
							ev.stopPropagation();
							return;
						}
						setMenu(null);
						setPanelView("effort");
					};
					document.addEventListener("mousedown", handler);
					document.addEventListener("keydown", onKey);
					return () => {
						document.removeEventListener("mousedown", handler);
						document.removeEventListener("keydown", onKey);
					};
				}, [menu, panelView]);
				react.useEffect(() => {
					if (menu !== "effort") {
						setPanelView("effort");
					}
				}, [menu]);
				react.useEffect(() => () => {
					if (resetTimerRef.current !== null) clearTimeout(resetTimerRef.current);
				}, []);
				react.useEffect(() => {
					if (menu !== "effort") return;
					const measure = () => {
						if (trackRef.current !== null) {
							const w = trackRef.current.getBoundingClientRect().width;
							const dpr = window.devicePixelRatio > 0 ? window.devicePixelRatio : 1;
							const next = solveMatrix(Math.floor(w * dpr), dpr);
							setGrid((g) => g !== null && g.c === next.c && g.r === next.r && g.sq === next.sq && g.gap === next.gap && g.trackWDev === next.trackWDev && g.padTop === next.padTop && g.padBottom === next.padBottom && g.padLeft === next.padLeft && g.padRight === next.padRight ? g : next);
						}
					};
					measure();
					window.addEventListener("resize", measure);
					return () => window.removeEventListener("resize", measure);
				}, [menu]);
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
						if (!keepOpen) setMenu(null);
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
				react.useLayoutEffect(() => {
					let active = true;
					const elements = [effortTriggerRef.current, effortValueRef.current].filter((element) => element !== null);
					const stabilize = () => {
						if (!active) return;
						const heights = elements.map((element) => measureEffortLineHeight(element));
						elements.forEach((element, index) => {
							const height = heights[index];
							if (height !== null) element.style.setProperty("--sk5-effort-line-height", height);
						});
					};
					stabilize();
					const fonts = document.fonts;
					fonts?.ready.then(stabilize);
					fonts?.addEventListener("loadingdone", stabilize);
					return () => {
						active = false;
						fonts?.removeEventListener("loadingdone", stabilize);
						for (const element of elements) element.style.removeProperty("--sk5-effort-line-height");
					};
				}, [
					menu,
					hasEffort,
					displayLabel,
					current?.provider,
					current?.model
				]);
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
				const matrixVisible = inMax && atMaxPos;
				const posPct = choices.length > 1 ? posIdx / (choices.length - 1) * 100 : 0;
				/** 提交值 → CSS 变量；拖拽期间让位给 dragFrac，避免回跳。 */
				react.useLayoutEffect(() => {
					if (moving) return;
					const el = trackRef.current;
					if (el !== null) el.style.setProperty("--ue-pos", String(Math.max(0, Math.min(1, posPct / 100))));
				}, [posPct, moving, menu, choices.length]);
				const matrixCells = react.useMemo(() => {
					if (!inMax || grid === null) return [];
					/** Blend a colour toward its own luminance: same hue, less saturation. */
					const desat = (rgb, f) => {
						const l = .299 * rgb[0] + .587 * rgb[1] + .114 * rgb[2];
						return rgb.map((v) => Math.round(v + (l - v) * f));
					};
					const deep = desat([
						65,
						118,
						230
					], .15);
					const lightMax = desat([
						103,
						158,
						254
					], .15);
					/**
					* How far the lightest cells reach past deepseek-400 (103,158,254)
					* toward deepseek-300 (183,200,254): a small lift reads lighter without
					* going pale. This is the knob for "a touch lighter".
					*/
					const lightLift = .3;
					const lightPeak = lightMax.map((v, i) => Math.round(v + ([
						183,
						200,
						254
					][i] - v) * lightLift));
					/** Overall right-to-left sweep duration of the reveal. */
					const revealMs = 1800;
					/** Per-cell random stagger, ± this many ms: perforates the front edge. */
					const staggerMs = 80;
					/** Integer-lattice hash folded into [0,1). */
					const noiseHash = (x, y, seed) => {
						let h = Math.imul(x, 374761393) + Math.imul(y, 668265263) + Math.imul(seed, 2246822519) | 0;
						h = h ^ h >>> 13 | 0;
						h = Math.imul(h, 1274126177);
						return ((h ^ h >>> 16) >>> 0) / 4294967296;
					};
					/** Value noise: lattice hashes blended by a smoothstep, hence smooth. */
					const valueNoise = (x, y, seed) => {
						const x0 = Math.floor(x);
						const y0 = Math.floor(y);
						const fx = x - x0;
						const fy = y - y0;
						const sx = fx * fx * (3 - 2 * fx);
						const sy = fy * fy * (3 - 2 * fy);
						const n00 = noiseHash(x0, y0, seed);
						const n10 = noiseHash(x0 + 1, y0, seed);
						const n01 = noiseHash(x0, y0 + 1, seed);
						const n11 = noiseHash(x0 + 1, y0 + 1, seed);
						return (n00 * (1 - sx) + n10 * sx) * (1 - sy) + (n01 * (1 - sx) + n11 * sx) * sy;
					};
					/**
					* Two octaves in [-1,1]: a broad fog bank plus a finer grain, so the
					* frontier reads as eroded by noise rather than as a straight edge.
					*/
					/**
					* Column-wise cluster centre: a smooth 1-D noise, so neighbouring columns
					* share the cluster and the frontier reads as melting rather than
					* flickering. Returns a fractional row index in [0, rows-1].
					*/
					const clusterAt = (c) => {
						return (valueNoise(c * .35, .5, 71) * .65 + valueNoise(c * .9, 3.5, 89) * .35) * (grid.r - 1);
					};
					const out = [];
					for (let r = 0; r < grid.r; r++) for (let c = 0; c < grid.c; c++) {
						const k = .45 + cellUnit(r, c, 1) * .5;
						const lc = deep.map((v, i) => Math.round(v + (lightPeak[i] - v) * k));
						const flashDelay = (cellUnit(r, c, 2) * 1.38 + .35).toFixed(3) + "s";
						/**
						* Per-cell cycle length, jittered around the stylesheet's 1.45s base.
						* With one shared duration every cell keeps a fixed phase, so the
						* whole pattern repeats exactly each round and a local area replays
						* the same order; the spread drifts the phases apart instead.
						*/
						const flashDuration = (FLASH_CYCLE_S * (.92 + cellUnit(r, c, 3) * 2 * FLASH_JITTER)).toFixed(3) + "s";
						const fx = grid.c > 1 ? c / (grid.c - 1) : 0;
						const u = grid.c > 1 ? (grid.c - 1 - c) / (grid.c - 1) : 0;
						const m = clusterAt(c);
						const rank = Math.abs(r - m) / (grid.r - 1);
						const stages = 5;
						const stage = Math.min(stages, Math.round(rank * stages));
						const stagger = (cellUnit(r, c, 4) * 2 - 1) * staggerMs;
						const appearDelay = (revealMs * Math.max(0, Math.min(1, u + stage / (grid.c - 1) + stagger / revealMs)) / 1e3).toFixed(3) + "s";
						out.push({
							key: r + "-" + c,
							flashLight: "rgb(" + lc[0] + "," + lc[1] + "," + lc[2] + ")",
							flashDeep: "rgb(" + deep.join(",") + ")",
							animationDelay: flashDelay,
							flashDuration,
							appearDelay,
							fade: fadeAt(fx)
						});
					}
					return out;
				}, [inMax, grid]);
				react.useEffect(() => {
					const id = setTimeout(() => setSettledIdx(safePosIdx), 160);
					return () => clearTimeout(id);
				}, [safePosIdx]);
				if (runtimeSessions.subagentAddress(sessionId) !== void 0) return null;
				if (directory === null) return null;
				const insetPx = HANDLE_W / 2;
				const posFrac = posPct / 100;
				const dotLeft = (i) => "calc(" + HANDLE_W / 2 + "px + (100% - " + HANDLE_W + "px) * " + (choices.length > 1 ? i / (choices.length - 1) : 0) + ")";
				/**
				* Level dots are laid out in whole device pixels. Their proportional
				* `left` is fractional by nature, and a 6-device-pixel circle that
				* straddles two pixels reads as a rounded square: snapping both axes to
				* the device grid gives the rasterizer a symmetric circle to draw.
				*/
				const dpr = typeof window !== "undefined" && window.devicePixelRatio > 0 ? window.devicePixelRatio : 1;
				const dotDev = 4 * dpr;
				const insetDev = insetPx * dpr;
				const dotLeftSnapped = (i) => {
					if (grid === null) return dotLeft(i);
					const frac = choices.length > 1 ? i / (choices.length - 1) : 0;
					return Math.round(insetDev + (grid.trackWDev - 2 * insetDev) * frac) / dpr + "px";
				};
				const dotTopSnapped = grid === null ? void 0 : Math.round((grid.trackHeight * dpr - dotDev) / 2) / dpr + "px";
				const handleLeft = "calc(" + HANDLE_W / 2 + "px + (100% - " + HANDLE_W + "px) * " + posFrac + ")";
				const fillWidth = handleLeft;
				const fillHidden = inMax && atMaxPos;
				const fillSolid = "color-mix(in srgb, var(--dsw-alias-label-primary) 42%, transparent)";
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
				const onWinMove = (ev) => {
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
				};
				const stopDrag = () => {
					window.removeEventListener("pointermove", onWinMove);
					window.removeEventListener("pointerup", onWinUp);
					window.removeEventListener("pointercancel", onWinCancel);
					window.removeEventListener("blur", onWinCancel);
					if (dragRafRef.current !== null) {
						cancelAnimationFrame(dragRafRef.current);
						dragRafRef.current = null;
					}
					dragRectRef.current = null;
				};				const onWinUp = () => {
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
				};
				const onWinCancel = () => {
					dragIdxRef.current = null;
					setMoving(false);
					if (pressTimerRef.current !== null) { clearTimeout(pressTimerRef.current); pressTimerRef.current = null; }
					setShowLabels(false);
					stopDrag();
					setHoverIdx(null);
				};
				const onTrackDown = (ev) => {
					if (choices.length === 0) return;
					const el = trackRef.current;
					if (el === null) return;
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
					window.addEventListener("pointermove", onWinMove);
					window.addEventListener("pointerup", onWinUp);
					window.addEventListener("pointercancel", onWinCancel);
					window.addEventListener("blur", onWinCancel);
				};				const triggerTitle = curGroup !== void 0 && curModel !== void 0 ? curGroup.name + " / " + curModel.name + (effectiveEffort !== void 0 ? " · " + displayLabel : "") : tr("trigger.selectModel");
				return react.createElement("div", {
					ref: rootRef,
					className: "sk5-root" + (menu !== null ? " ue-open" : "")
				}, react.createElement("button", {
					ref: effortTriggerRef,
					type: "button",
					className: "ue-trigger",
					disabled: locked || busy || current === null,
					title: triggerTitle,
					"aria-haspopup": "menu",
					"aria-expanded": menu === "effort",
					onClick: (ev) => {
						openedByKeyboardRef.current = ev.detail === 0;
						setMenu((m) => m === "effort" ? null : "effort");
					}
				}, react.createElement("span", { className: "ue-triggerModel" }, modelLabel), react.createElement("span", { className: "ue-triggerLevel " + levelTone }, displayLabel), react.createElement("svg", {
					className: "ue-triggerChev",
					viewBox: "0 0 16 16",
					"aria-hidden": "true"
				}, react.createElement("path", { d: "M4 6l4 4 4-4" }))), react.createElement("span", {
					className: "ue-sr",
					role: "status",
					"aria-live": "polite"
				}, displayLabel + "，第 " + (safePosIdx + 1) + " 项，共 " + Math.max(choices.length, 1) + " 项"), menu === "effort" ? react.createElement("div", {
					ref: panelRef,
					className: "sk5-drop sk5-effort ue-panel",
					role: "menu",
					"aria-label": "选择推理强度"
				}, react.createElement("div", { className: "ue-head" }, react.createElement("span", {
					className: "ue-icon ue-bolt",
					"aria-hidden": "true"
				}, react.createElement("svg", { viewBox: "0 0 24 24" }, react.createElement("path", { d: "M13 2 3 14h7l-1 8 10-12h-7l1-8z" }))), react.createElement("div", { className: "ue-labels" + (showLabels ? " ue-labelsOn" : "") }, react.createElement("span", null, "Faster"), react.createElement("span", null, "Smarter")), react.createElement("div", { className: "ue-center" }, react.createElement("div", { className: "ue-title " + titleTone }, displayLabel), react.createElement("button", {
					type: "button",
					className: "ue-model" + (panelView === "model" ? " ue-modelOpen" : "") + (showLabels ? " ue-modelHidden" : ""),
					disabled: locked || busy,
					title: triggerTitle,
					"aria-haspopup": "listbox",
					"aria-expanded": panelView === "model",
					onClick: () => setPanelView((v) => v === "model" ? "effort" : "model")
				}, react.createElement("span", { className: "ue-modelName" }, modelLabel), react.createElement("svg", { className: "ue-modelChev", viewBox: "0 0 16 16", "aria-hidden": "true" }, react.createElement("path", { d: "M4 6l4 4 4-4" })))), react.createElement("button", {
					type: "button",
					className: "ue-icon ue-reset" + (resetFlash ? " ue-resetFlash" : "") + (atDefaultEffort ? " ue-resetHidden" : ""),
					"aria-hidden": atDefaultEffort ? "true" : void 0,
					tabIndex: atDefaultEffort ? -1 : 0,
					title: "重置为默认",
					"aria-label": "重置为默认推理强度",
					disabled: locked || busy || current === null || reasoning === void 0,
					onClick: onReset
				}, react.createElement("svg", { viewBox: "0 0 16 16" }, react.createElement("path", { d: "M2.8 6.2A5.6 5.6 0 1 1 2.6 9.4" }), react.createElement("path", { d: "M2.4 2.4v4h4" })))), panelView === "model" ? react.createElement("div", {
					className: "ue-models",
					role: "listbox",
					"aria-label": tr("trigger.selectModel")
				}, react.createElement("div", { className: "ue-modelsTitle" }, tr("trigger.selectModel")), !loaded && shownError === null ? react.createElement("div", { className: "sk5-status" }, tr("status.loading")) : null, shownError !== null ? react.createElement("div", { className: "sk5-err" }, shownError) : null, loaded && groups.length === 0 ? react.createElement("div", { className: "sk5-status" }, tr("status.noModels")) : null, loaded ? groups.map((g) => react.createElement("div", {
					key: g.id,
					className: "ue-group"
				}, react.createElement("div", { className: "ue-groupName" }, providerLabel(g)), g.models.map((m) => {
					const isCur = current !== null && current.provider === g.id && current.model === m.id;
					return react.createElement("button", {
						key: m.id,
						type: "button",
						role: "option",
						"aria-selected": isCur,
						className: "ue-row" + (isCur ? " ue-rowActive" : ""),
						disabled: busy,
						onClick: () => {
							onPickModel(m, g);
							setPanelView("effort");
						}
					}, react.createElement("span", { className: "ue-rowText" }, react.createElement("span", { className: "ue-rowName" }, m.name), m.description !== void 0 ? react.createElement("span", { className: "ue-rowDesc" }, m.description) : null), isCur ? react.createElement("span", { className: "ue-check" }, "✓") : null);
				}))) : null) : react.createElement("div", { className: "ue-sliderArea" + (showLabels ? " ue-labelsOn" : "") }, react.createElement("div", { className: "ue-sliderRow" }, react.createElement("div", {
					ref: trackRef,
					className: "sk5-track ue-track" + (inMax ? " ue-trackMax" : "") + (moving ? " ue-moving" : "") + (burst ? " ue-burst" : "") + (showLabels ? " ue-labelsOn" : ""),
					role: "slider",
					tabIndex: 0,
					"aria-label": "推理强度",
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
