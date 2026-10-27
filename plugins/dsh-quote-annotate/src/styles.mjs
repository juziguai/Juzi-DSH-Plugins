export const QUOTE_CSS = `
.jq-root{position:fixed;inset:0;z-index:40;pointer-events:none;color:var(--dsw-alias-label-primary,#0f1115);font:var(--dsw-font-xs-13,13px/20px sans-serif)}
.jq-surface{box-sizing:border-box;position:fixed;pointer-events:auto;background:var(--dsw-alias-bg-layer-2,#fff);border:.5px solid var(--dsw-alias-border-l2,#0000001a);border-radius:var(--dsw-radius-md,12px);box-shadow:var(--dsw-elevation-prominent,0 3px 12px #0000000d);animation:jq-enter 150ms var(--ds-ease-in-out,cubic-bezier(.4,0,.2,1))}
.jq-button{appearance:none;display:inline-flex;align-items:center;justify-content:center;gap:4px;background:transparent;color:var(--dsw-alias-label-secondary,#61666b);border:0;border-radius:var(--dsw-radius-xs,4px);font:inherit;cursor:pointer;padding:4px}
.jq-button:hover{background:var(--dsw-alias-interactive-bg-hover,#2631480f);color:var(--dsw-alias-label-primary,#0f1115)}
.jq-button:focus-visible{outline:2px solid var(--dsw-alias-state-business-primary,#4176e6);outline-offset:2px}
.jq-icon{display:block;width:16px;height:16px;flex:none;fill:none;stroke:currentColor;stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round}
.jq-bubble{width:28px;height:28px;padding:6px;border-radius:var(--dsw-radius-sm,8px);background:var(--dsw-specific-menu,var(--dsw-alias-bg-layer-2,#fff));backdrop-filter:var(--dsw-menu-backdrop-filter,blur(40px) saturate(150%))}
.jq-arrow{position:absolute;bottom:-4px;width:8px;height:5px;left:calc(var(--jq-arrow) - 4px);overflow:visible;pointer-events:none;fill:var(--dsw-alias-bg-layer-2,#fff);stroke:var(--dsw-alias-label-secondary,#61666b);stroke-width:.8;stroke-linejoin:round}
.jq-surface[data-jq-side=bottom]>.jq-arrow{top:-4px;bottom:auto;transform:rotate(180deg)}
.jq-surface[data-jq-side=right]>.jq-arrow{left:-6px;top:calc(var(--jq-arrow) - 2.5px);bottom:auto;transform:rotate(90deg)}
.jq-surface[data-jq-side=left]>.jq-arrow{right:-6px;left:auto;top:calc(var(--jq-arrow) - 2.5px);bottom:auto;transform:rotate(-90deg)}
.jq-bubble:after{content:attr(aria-label);position:absolute;bottom:36px;left:50%;transform:translateX(-50%);white-space:nowrap;padding:4px 8px;border-radius:var(--dsw-radius-xs,4px);background:var(--dsw-alias-bg-layer-2,#fff);color:var(--dsw-alias-label-primary,#0f1115);box-shadow:var(--dsw-elevation-prominent);opacity:0;pointer-events:none}
.jq-bubble:hover:after{opacity:1;transition:opacity 100ms 500ms}
.jq-compose{display:flex;align-items:center;gap:8px;padding:6px;width:min(320px,calc(100vw - 16px));max-width:360px;min-height:48px;border-radius:24px;corner-shape:round;animation-duration:var(--ds-transition-duration,200ms)}
.jq-compose:focus-within{border-color:var(--dsw-alias-border-l3,#00000026)}
.jq-comment-field{flex:1;min-width:0;padding:8px}
.jq-comment{display:block;box-sizing:border-box;width:100%;height:20px;min-height:20px;max-height:120px;resize:none;padding:0;border:0;outline:none;background:transparent;color:var(--dsw-alias-label-primary,#0f1115);font:var(--dsw-font-xs-13,13px/20px sans-serif);overflow:auto;scrollbar-gutter:stable}
.jq-comment::placeholder{color:var(--dsw-alias-label-tertiary,#81858c)}
.jq-comment,.jq-text,.jq-note,.jq-dock-list,.jq-sent-body,.jq-sent-original{scrollbar-color:var(--dsw-alias-scrollbar-bg-l2,#00000026) transparent;scrollbar-width:thin}
/* Chromium's non-auto scrollbar-width overrides webkit button styling. Firefox keeps thin. */
@supports selector(::-webkit-scrollbar){
 .jq-comment,.jq-text,.jq-note,.jq-dock-list,.jq-sent-body,.jq-sent-original{scrollbar-width:auto;scrollbar-color:auto}
 .jq-comment::-webkit-scrollbar,.jq-text::-webkit-scrollbar,.jq-note::-webkit-scrollbar,.jq-dock-list::-webkit-scrollbar,.jq-sent-body::-webkit-scrollbar,.jq-sent-original::-webkit-scrollbar{width:6px;height:6px}
 .jq-comment::-webkit-scrollbar-thumb,.jq-text::-webkit-scrollbar-thumb,.jq-note::-webkit-scrollbar-thumb,.jq-dock-list::-webkit-scrollbar-thumb,.jq-sent-body::-webkit-scrollbar-thumb,.jq-sent-original::-webkit-scrollbar-thumb{background:var(--dsw-alias-scrollbar-bg-l2,#00000026);border-radius:4px}
 .jq-comment::-webkit-scrollbar-thumb:hover,.jq-text::-webkit-scrollbar-thumb:hover,.jq-note::-webkit-scrollbar-thumb:hover,.jq-dock-list::-webkit-scrollbar-thumb:hover,.jq-sent-body::-webkit-scrollbar-thumb:hover,.jq-sent-original::-webkit-scrollbar-thumb:hover{background:var(--dsw-alias-scrollbar-hover-l2,#00000040)}
 .jq-comment::-webkit-scrollbar-button,.jq-text::-webkit-scrollbar-button,.jq-note::-webkit-scrollbar-button,.jq-dock-list::-webkit-scrollbar-button,.jq-sent-body::-webkit-scrollbar-button,.jq-sent-original::-webkit-scrollbar-button{display:none;width:0;height:0}
 .jq-comment::-webkit-scrollbar-track,.jq-text::-webkit-scrollbar-track,.jq-note::-webkit-scrollbar-track,.jq-dock-list::-webkit-scrollbar-track,.jq-sent-body::-webkit-scrollbar-track,.jq-sent-original::-webkit-scrollbar-track{background:transparent}
}
.jq-count{flex:none;color:var(--dsw-alias-label-secondary,#61666b);font:var(--dsw-font-xxs-12,12px/18px sans-serif)}.jq-count[data-jq-limit]{color:var(--dsw-alias-state-error-primary,#c43d3d)}
.jq-confirm{flex:none;width:32px;height:32px;padding:8px;border-radius:50%;corner-shape:round;background:var(--dsw-alias-label-primary,#0f1115);color:var(--dsw-alias-label-primary-inverted,#fff)}
.jq-confirm:hover{background:var(--dsw-alias-label-secondary,#61666b);color:var(--dsw-alias-label-primary-inverted,#fff)}
.jq-compose>.jq-confirm{align-self:flex-end;margin-block:2px}
.jq-selection{pointer-events:none}.jq-selection-mark{position:fixed;background:color-mix(in srgb,var(--dsw-alias-state-business-primary,#4176e6) 28%,transparent)}
.jq-selection-number{position:fixed;display:flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:10px 10px 10px 2px;background:color-mix(in srgb,var(--dsw-alias-state-business-primary,#4176e6) 88%,var(--dsw-alias-label-primary,#0f1115));color:var(--dsw-alias-label-primary-inverted,#fff);font:var(--dsw-font-xs-13,13px/20px sans-serif);font-weight:600}
.jq-card{display:flex;flex-direction:column;width:360px;max-width:calc(100vw - 16px);max-height:360px;padding:12px;overflow:visible;isolation:isolate;opacity:1;background:var(--dsw-alias-bg-layer-2,#fff);border-color:var(--dsw-alias-border-l3,#00000026);box-shadow:var(--dsw-elevation-prominent,0 6px 24px #00000026);animation-name:jq-card-enter}
.jq-card:before{content:'';position:absolute;left:0;right:0;bottom:-8px;height:8px}
.jq-card[data-jq-side=bottom]:before{top:-8px;bottom:auto}
.jq-card-head{display:flex;flex:none;align-items:center;justify-content:space-between;margin-bottom:8px;font:var(--dsw-font-xxs-12,12px/18px sans-serif);color:var(--dsw-alias-label-secondary,#61666b)}
.jq-actions{display:flex;align-items:center;gap:4px}.jq-actions>.jq-button{height:24px;width:24px;padding:4px}
.jq-text{flex-shrink:1;min-height:0;margin:0;border-left:2px solid var(--dsw-alias-border-l3,#00000026);padding-left:10px;max-height:160px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;color:var(--dsw-alias-label-secondary,#61666b)}
.jq-code{font-family:var(--ds-font-family-code,monospace);background:var(--dsw-alias-markdown-code-block,var(--dsw-alias-bg-layer-1,#fff));border-radius:var(--dsw-radius-xs,4px)}
.jq-note{flex-shrink:1;min-height:0;margin-top:8px;border-top:.5px solid var(--dsw-alias-border-l1,#0000000a);padding-top:8px;white-space:pre-wrap;overflow:auto;max-height:120px;color:var(--dsw-alias-label-primary,#0f1115)}
.jq-meta{font:var(--dsw-font-xxs-12,12px/18px sans-serif);color:var(--dsw-alias-label-secondary,#61666b)}
.jq-badge{padding:0 4px;border-radius:var(--dsw-radius-xs,4px);background:var(--dsw-alias-interactive-bg-hover,#2631480f);white-space:nowrap}
.jq-danger:hover{color:var(--dsw-alias-state-error-primary,#c43d3d);background:var(--dsw-alias-interactive-bg-hover-danger,#d9302510)}
.jq-dock{box-sizing:border-box;width:calc(100% - var(--dsh-composer-side-clearance,16px) - var(--dsh-composer-side-clearance,16px) - var(--dsh-composer-dock-inset,8px) - var(--dsh-composer-dock-inset,8px));max-width:calc(var(--dsh-composer-card-max-width,760px) - var(--dsh-composer-dock-inset,8px) - var(--dsh-composer-dock-inset,8px));margin:0 auto;border:.5px solid var(--dsw-alias-border-l1,#0000000a);border-radius:var(--dsw-radius-md,12px);background:var(--dsw-alias-bg-layer-1,#fff);box-shadow:var(--dsw-elevation-panel);padding:4px 8px;color:var(--dsw-alias-label-primary,#0f1115);font:var(--dsw-font-xxs-12,12px/18px sans-serif)}
.jq-dock-head{display:flex;align-items:center;justify-content:space-between;min-height:28px;gap:8px;padding-inline:4px}.jq-dock-list{max-height:96px;overflow:auto}.jq-dock-list[data-jq-expanded]{max-height:240px}
.jq-row{display:flex;align-items:center;gap:8px;height:32px;border-radius:var(--dsw-radius-sm,8px);padding:0 4px;box-sizing:border-box}.jq-row[data-jq-active],.jq-row:hover{background:var(--dsw-alias-interactive-bg-hover,#2631480f)}
.jq-ellipsis{display:block;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.jq-summary{flex:1 1 0;min-width:0;padding-inline:0;justify-content:flex-start;text-align:left;color:var(--dsw-alias-label-primary,#0f1115)}
.jq-separator{flex:none;color:var(--dsw-alias-label-secondary,#61666b)}
.jq-row-comment{display:block;flex:0 1 28%;min-width:0;max-width:28%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--dsw-alias-label-secondary,#61666b)}
.jq-row>.jq-actions{opacity:0}.jq-row:hover>.jq-actions,.jq-row:focus-within>.jq-actions{opacity:1}
.jq-alert{margin:4px 0;padding:6px 8px;border-radius:var(--dsw-radius-sm,8px);color:var(--dsw-alias-label-primary,#0f1115);background:var(--dsw-alias-interactive-bg-hover,#2631480f)}
.jq-sr{position:absolute;width:1px;height:1px;padding:0;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
[data-composer-chip="juzi.quote-annotate"]>span[title]{pointer-events:none}
[data-composer-chip="juzi.quote-annotate"]{display:inline-flex;vertical-align:middle;margin-inline:0 6px}
[data-composer-chip="juzi.quote-annotate"]>span{box-sizing:border-box;gap:4px;align-items:center;min-height:24px;padding:1px 6px;color:var(--dsw-alias-label-primary,#0f1115);max-width:220px;border:.5px solid var(--dsw-alias-border-l2,#0000001a);border-radius:var(--dsw-radius-xs,4px);background:var(--dsw-alias-bg-layer-1,#fff)}
[data-composer-chip="juzi.quote-annotate"]>span>span:last-of-type{display:block;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
[data-composer-chip="juzi.quote-annotate"]>span::after{align-self:center;line-height:1}
[data-composer-chip="juzi.quote-annotate"]>span>span[aria-hidden]{display:none}
[data-composer-chip="juzi.quote-annotate"]:hover>span{background:var(--dsw-alias-interactive-bg-hover,#2631480f)}
[data-composer-chip="juzi.quote-annotate"]:focus-within{outline:2px solid var(--dsw-alias-state-business-primary,#4176e6)}
@keyframes jq-enter{from{opacity:0;transform:translateY(4px) scale(.98)}to{opacity:1;transform:none}}
@keyframes jq-card-enter{from{transform:translateY(4px)}to{transform:none}}
.jq-sent{display:block;box-sizing:border-box;width:fit-content;max-width:100%;margin:0 0 8px;padding:4px 8px;border:.5px solid var(--dsw-alias-border-l2,#0000001a);border-radius:var(--dsw-radius-sm,8px);background:var(--dsw-alias-bg-layer-1,#fff);color:var(--dsw-alias-label-primary,#0f1115);font:var(--dsw-font-xs-13,13px/20px sans-serif);white-space:normal}
.jq-sent[data-jq-expanded]{width:min(440px,100%)}
.jq-sent-toggle{gap:8px;padding:2px 4px;color:var(--dsw-alias-label-primary,#0f1115)}
.jq-sent-chevron{font-size:13px;color:var(--dsw-alias-label-secondary,#61666b)}
.jq-sent-body{display:block;max-height:360px;overflow:auto;padding:8px 4px 4px}
.jq-sent-item{display:block}.jq-sent-item+.jq-sent-item{margin-top:12px;padding-top:12px;border-top:.5px solid var(--dsw-alias-border-l1,#0000000a)}
.jq-sent-original{display:block;max-height:160px;overflow:auto;margin-top:6px;border-left:2px solid var(--dsw-alias-border-l3,#00000026);padding-left:10px;white-space:pre-wrap;overflow-wrap:anywhere;color:var(--dsw-alias-label-secondary,#61666b)}
.jq-sent-note{display:block;margin-top:8px;padding-top:8px;border-top:.5px solid var(--dsw-alias-border-l1,#0000000a);white-space:pre-wrap;overflow-wrap:anywhere}
@media(prefers-reduced-motion:reduce){.jq-surface,.jq-bubble:after{animation:none;transition:none;transform:none}}
@media(hover:none){.jq-row>.jq-actions{opacity:1}}
`;
