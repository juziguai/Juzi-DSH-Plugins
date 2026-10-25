// Styles preserved from the accepted Ultra 0.1.2 UI.
export const ULTRA_CSS = `
/* ── Ultra 面板 V7 · Codex 原型对齐 ─────────────────────────────
   尺寸基准：面板 266×~100、padding 4、头部 min-height 56、滑杆行 32。
   选择器统一 .sk5-root 前缀提高特异性，不使用 important 声明。
   ───────────────────────────────────────────────────────────── */
.sk5-root .sk5-drop{font-family:inherit;}
.sk5-root{--ue-blue:#3a83f7;--ue-brand:#3a83f7;--ue-purple:#924ff7;--ue-hover:color-mix(in srgb,var(--dsw-alias-label-primary,#0f172a) 6%,transparent);--ue-border:var(--dsw-alias-border-l2,color-mix(in srgb,var(--dsw-alias-label-primary,#0f172a) 12%,transparent));--ue-tertiary:color-mix(in srgb,var(--dsw-alias-label-primary,#0f172a) 38%,transparent);--ue-secondary:color-mix(in srgb,var(--dsw-alias-label-primary,#0f172a) 55%,transparent);--ue-track:color-mix(in srgb,var(--dsw-alias-label-primary,#0f172a) 10%,transparent);--ue-motion:cubic-bezier(.23,1,.32,1);}
/* 触发器：模型名 + 档位名 + ▾ 合并成一个按钮 */
.sk5-root .ue-trigger{display:inline-flex;align-items:center;gap:4px;max-width:260px;padding:2px 6px;border:0;border-radius:8px;background:transparent;font-size:13px;line-height:20px;color:var(--dsw-alias-label-primary,#0f172a);cursor:pointer;transition:background .14s ease;}
.sk5-root .ue-trigger:hover{background:color-mix(in srgb,var(--dsw-alias-label-primary,#0f172a) 6%,transparent);}
.sk5-root.ue-open .ue-trigger{background:color-mix(in srgb,var(--dsw-alias-label-primary,#0f172a) 8%,transparent);}
.sk5-root .ue-trigger[disabled]{opacity:.5;cursor:default;}
.sk5-root .ue-triggerModel{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.sk5-root .ue-triggerLevel{flex:none;font-weight:500;}
.sk5-root .ue-triggerChev{width:12px;height:12px;flex:none;fill:none;stroke:currentColor;stroke-width:1.6;opacity:.45;transition:transform .18s var(--ue-motion);}
.sk5-root.ue-open .ue-triggerChev{transform:rotate(180deg);}
/* 档位配色 */
.sk5-root .ue-lv-max{color:var(--ue-purple);}
.sk5-root .ue-lv-norm{color:var(--ue-blue);}
.sk5-root .ue-lv-def{color:color-mix(in srgb,var(--dsw-alias-label-primary,#0f172a) 55%,transparent);}
.sk5-root .ue-lv-text{color:var(--dsw-alias-label-primary,#0f172a);}
.sk5-root .ue-resetHidden{visibility:hidden;pointer-events:none;}
/* 面板 */
.sk5-root .sk5-drop{bottom:calc(100% + 8px);right:var(--ue-drop-right,0px);}
.sk5-root .ue-panel[data-state="closing"]{opacity:0;transform:translateY(4px) scale(.98);pointer-events:none;transition:opacity .15s ease,transform .15s ease;transform-origin:bottom right;}
.sk5-root .sk5-drop.ue-panel{width:min(266px,calc(100vw - 24px));padding:4px;border-radius:14px;border:1px solid var(--dsw-alias-border-l2,color-mix(in srgb,var(--dsw-alias-label-primary,#0f172a) 12%,transparent));background:var(--dsw-alias-bg-layer-1,#fff);box-shadow:0 12px 32px color-mix(in srgb,var(--dsw-alias-label-primary,#0f172a) 16%,transparent),0 2px 8px color-mix(in srgb,var(--dsw-alias-label-primary,#0f172a) 6%,transparent);
body[data-ds-dark-theme] .sk5-root .sk5-drop.ue-panel{box-shadow:0 16px 40px rgba(0,0,0,.55),0 2px 10px rgba(0,0,0,.4);}overflow:hidden;}
/* 头部 */
.sk5-root .ue-head{position:relative;display:flex;align-items:center;justify-content:center;min-height:46px;padding:2px 36px 4px;}
.sk5-root .ue-center{display:flex;flex-direction:column;align-items:center;gap:1px;min-width:0;max-width:100%;}
.sk5-root .ue-title{font-size:16px;line-height:22px;font-weight:500;letter-spacing:.01em;}
.sk5-root .ue-model{display:inline-flex;align-items:center;gap:2px;max-width:100%;padding:2px 4px;border:0;border-radius:6px;background:transparent;color:var(--ue-secondary);font-size:12px;line-height:16px;font-weight:400;cursor:pointer;transition:background .12s ease;}
.sk5-root .ue-model:hover{background:color-mix(in srgb,var(--dsw-alias-label-primary,#0f172a) 6%,transparent);}
.sk5-root .ue-model[aria-expanded="true"] .ue-modelChev{transform:rotate(180deg);}
.sk5-root .ue-model:focus-visible{outline:2px solid var(--ue-brand,#3a83f7);outline-offset:1px;}
.sk5-root .ue-modelName{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.sk5-root .ue-modelChev{flex:none;width:12px;height:12px;fill:none;stroke:currentColor;stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round;opacity:.5;transition:transform .18s var(--ue-motion);}
.sk5-root .ue-icon{position:absolute;top:50%;transform:translateY(-50%);display:flex;align-items:center;justify-content:center;width:32px;height:32px;padding:0;border:0;border-radius:7px;background:transparent;color:color-mix(in srgb,var(--dsw-alias-label-primary,#0f172a) 45%,transparent);cursor:pointer;transition:background .12s ease,color .12s ease;}
.sk5-root .ue-icon:hover{background:color-mix(in srgb,var(--dsw-alias-label-primary,#0f172a) 6%,transparent);color:color-mix(in srgb,var(--dsw-alias-label-primary,#0f172a) 60%,transparent);}
.sk5-root .ue-icon:active{transform:translateY(-50%) scale(.94);}
.sk5-root .ue-icon:focus-visible{outline:2px solid var(--ue-brand,#3a83f7);outline-offset:1px;}
.sk5-root .ue-icon svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.4;stroke-linecap:round;stroke-linejoin:round;}
.sk5-root .ue-bolt{left:2px;}
.sk5-root .ue-bolt.ue-fastOn{color:light-dark(#a65300,#ffd182);background:light-dark(#fff3dc,#45361f);}
.sk5-root .ue-bolt.ue-fastOn svg{fill:currentColor;stroke-width:1;}
.sk5-root .ue-bolt[aria-disabled="true"]{cursor:default;opacity:.6;}
.sk5-root .ue-bolt[aria-busy="true"]{opacity:.65;}
.sk5-root .ue-fastStatus{padding:4px 2px 7px;color:var(--ue-secondary);font-size:11px;line-height:1.5;overflow-wrap:anywhere;}
.sk5-root .ue-fastStatus button{border:0;background:transparent;color:var(--ue-brand,#3a83f7);font:inherit;cursor:pointer;padding:0 4px;text-decoration:underline;}
.sk5-root .ue-fastStatus button:focus-visible{outline:2px solid var(--ue-brand,#3a83f7);outline-offset:2px;}
.sk5-root .ue-reset{right:2px;}
.sk5-root .ue-resetFlash{background:rgba(146,79,247,.14);color:var(--ue-purple);}
/* 滑杆区 */
.sk5-root .ue-sliderArea{position:relative;margin-inline:2px;padding:1px 6px 2px;}
.sk5-root .ue-sliderRow{position:relative;height:32px;display:flex;align-items:center;}
.sk5-root .ue-track{corner-shape:round;position:relative;width:100%;height:24px;border-radius:12px;background:var(--ue-track);box-shadow:inset 0 0 0 .5px color-mix(in srgb,var(--dsw-alias-label-primary,#0f172a) 12%,transparent);cursor:pointer;touch-action:none;outline:none;overflow:visible;isolation:isolate;transition:background .2s ease;}
.sk5-root .ue-fill{corner-shape:round;position:absolute;left:0;top:0;bottom:0;width:calc(28px + (100% - 28px) * var(--ue-pos,0));border-radius:12px;background:var(--ue-blue);transition:width .3s var(--ue-motion),opacity .2s ease;z-index:1;}
.sk5-root .ue-trackMax .ue-fill{opacity:0;}
/* Ultra 渐变 + 揭示 */
.sk5-root .ue-ultraLayer{position:absolute;inset:0;border-radius:12px;transition:opacity .35s ease;background:linear-gradient(90deg,color-mix(in srgb,#3a83f7 60%,#924ff7) 0%,#924ff7 55%,color-mix(in srgb,#924ff7 72%,#3a83f7) 100%);opacity:0;pointer-events:none;z-index:1;}
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
.sk5-root .ue-handle{corner-shape:round;border-radius:999px;position:absolute;box-sizing:border-box;top:50%;left:calc(14px + (100% - 28px) * var(--ue-pos,0));width:28px;height:28px;margin:-14px 0 0 0;border-radius:999px;background:#fff;border:.5px solid color-mix(in srgb,var(--dsw-alias-label-primary,#0f172a) 28%,transparent);box-shadow:0 0 2px rgba(0,0,0,.1);transform:translateX(-50%);z-index:4;will-change:left;transition:left .3s var(--ue-motion),transform .18s var(--ue-motion),box-shadow .18s ease;}
.sk5-root .ue-moving .ue-handle{transition:left .15s var(--ue-motion),transform .18s var(--ue-motion),box-shadow .18s ease;transform:translateX(-50%) scale(1.14);box-shadow:0 0 2px rgba(0,0,0,.1),0 2px 8px color-mix(in srgb,var(--dsw-alias-label-primary,#0f172a) 18%,transparent);}
.sk5-root .ue-track:focus-visible{outline:none;}
.sk5-root .ue-track:focus-visible .ue-handle{outline:2px solid var(--ue-brand,#3a83f7);outline-offset:1px;}
.sk5-root:not(.ue-kb) .ue-track:focus-visible .ue-handle{outline:none;}
/* 端点标签：按住 150ms 才出现 */
.sk5-root .ue-labels{position:absolute;left:8px;right:8px;bottom:2px;display:flex;align-items:center;justify-content:space-between;pointer-events:none;opacity:0;transition:opacity .15s var(--ue-motion);font-size:11px;line-height:14px;color:color-mix(in srgb,var(--dsw-alias-label-primary,#0f172a) 48%,transparent);z-index:6;}
.sk5-root .ue-labels.ue-labelsOn{opacity:1;}
.sk5-root .ue-model.ue-modelHidden{opacity:0;pointer-events:none;}
.sk5-root .ue-model{transition:opacity .15s var(--ue-motion),background .12s ease;}
/* 内容进场 */
.sk5-root .ue-head{opacity:0;translate:0 10px;animation:ue-enter .2s var(--ue-motion) 40ms both;}
.sk5-root .ue-sliderArea{opacity:0;translate:0 10px;animation:ue-enter .2s var(--ue-motion) 56ms both;}
@keyframes ue-enter{to{opacity:1;translate:0 0}}
@keyframes ue-list-in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
/* 模型列表 */
.sk5-root .ue-models{margin:2px -2px 0;padding:4px 2px 4px;max-height:min(280px,45vh);overflow-y:auto;overscroll-behavior:contain;animation:ue-list-in .18s cubic-bezier(.23,1,.32,1) both;}
.sk5-root .ue-models::-webkit-scrollbar,.sk5-root .sk5-drop.ue-panel::-webkit-scrollbar{width:6px;height:6px;}
.sk5-root .ue-models::-webkit-scrollbar-track,.sk5-root .sk5-drop.ue-panel::-webkit-scrollbar-track{background:transparent;}
.sk5-root .ue-models::-webkit-scrollbar-thumb,.sk5-root .sk5-drop.ue-panel::-webkit-scrollbar-thumb{background:color-mix(in srgb,var(--dsw-alias-label-primary,#0f172a) 20%,transparent);border-radius:999px;}
.sk5-root .ue-models::-webkit-scrollbar-thumb:hover,.sk5-root .sk5-drop.ue-panel::-webkit-scrollbar-thumb:hover{background:color-mix(in srgb,var(--dsw-alias-label-primary,#0f172a) 32%,transparent);}
.sk5-root .ue-models::-webkit-scrollbar-button,.sk5-root .sk5-drop.ue-panel::-webkit-scrollbar-button{display:none;width:0;height:0;}

.sk5-root .ue-group{margin-top:16px;}
.sk5-root .ue-group:first-child{margin-top:2px;}

.sk5-root .ue-groupName{margin:0 2px 6px;font-size:13px;line-height:18px;font-weight:600;letter-spacing:0;text-transform:none;color:color-mix(in srgb,var(--dsw-alias-label-primary,#0f172a) 58%,transparent);cursor:default;user-select:none;}
.sk5-root .ue-row{display:flex;align-items:center;justify-content:space-between;gap:10px;width:calc(100% - 14px);margin-left:14px;min-height:34px;padding:7px 10px;border:0;border-radius:10px;background:transparent;text-align:left;cursor:pointer;color:var(--dsw-alias-label-primary,#0f172a);transition:background .14s ease;}
.sk5-root .ue-rowHasDesc{min-height:44px;}
.sk5-root .ue-row:hover{background:color-mix(in srgb,var(--dsw-alias-label-primary,#0f172a) 5%,transparent);}
.sk5-root .ue-row:focus-visible{outline:2px solid var(--ue-brand,#3a83f7);outline-offset:-2px;}
.sk5-root .ue-row.ue-rowActive{background:color-mix(in srgb,var(--ue-brand,#3a83f7) 12%,transparent);}
.sk5-root .ue-row.ue-rowActive:hover{background:color-mix(in srgb,var(--ue-brand,#3a83f7) 16%,transparent);}
.sk5-root .ue-rowText{display:flex;flex-direction:column;min-width:0;}
.sk5-root .ue-rowName{font-size:13px;line-height:18px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.sk5-root .ue-rowDesc{margin-top:2px;font-size:11px;line-height:15px;color:color-mix(in srgb,var(--dsw-alias-label-primary,#0f172a) 48%,transparent);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.sk5-root .ue-check{flex:none;color:var(--ue-brand,#3a83f7);font-size:14px;line-height:1;}
/* 屏幕阅读器 */
.sk5-root .ue-sr{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0;}
/* 减少动画 */
@media (prefers-reduced-motion: reduce){
.sk5-root .ue-head,.sk5-root .ue-sliderArea,.sk5-root .ue-models{animation:none;opacity:1;translate:0 0;transform:none;}
.sk5-root .ue-panel[data-state="closing"]{transition:none;}
.sk5-root .ue-modelChev,.sk5-root .ue-triggerChev{transition:none;}
.sk5-root .ue-model[aria-expanded="true"] .ue-modelChev{transform:none;}
.sk5-root .ue-ultraLayer,.sk5-root .ue-stream i,.sk5-root .ue-burstLayer span,.sk5-root .ue-tick,.sk5-root .ue-handle,.sk5-root .ue-fill{animation:none;transition:none;}
.sk5-root .ue-trackMax .ue-ultraLayer{-webkit-mask-image:none;mask-image:none;}
.sk5-root .ue-ultraLayer::after{animation:none;background-position:60% 50%;}
}
`;

export const CSS = ".sk5-root{position:relative;display:inline-flex;}.sk5-drop{font-family:inherit;position:absolute;bottom:calc(100% + 6px);right:0;border-radius:14px;border:1px solid var(--dsw-alias-border-l2);background:var(--dsw-alias-bg-layer-1);box-shadow:0 10px 32px rgb(0 0 0 / .35);z-index:1200;color:var(--dsw-alias-label-primary);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);}.sk5-status{padding:14px;font-size:12.5px;opacity:.65;text-align:center;}.sk5-err{padding:8px 4px 0;font-size:11.5px;color:var(--dsw-alias-state-error-primary);text-align:left;}.sk5-effort{width:225px;max-width:calc(100vw - 32px);box-sizing:border-box;padding:10px 12px 12px;}.sk5-track{position:relative;height:23px;border-radius:9px;background:color-mix(in srgb,var(--dsw-alias-label-primary) 15%,transparent);cursor:pointer;touch-action:none;user-select:none;-webkit-user-select:none;}";
