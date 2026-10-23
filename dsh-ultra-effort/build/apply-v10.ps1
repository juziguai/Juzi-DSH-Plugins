$ErrorActionPreference = "Stop"
$f = "D:\Tools\AI\Juzi-Skill\Juzi-DeepSeek-Tools\dsh-ultra-effort\lib\client.js"
$t = [System.IO.File]::ReadAllText($f, [System.Text.Encoding]::UTF8)

function Rep([string]$old, [string]$new, [string]$name) {
    $c = ([regex]::Matches($script:t, [regex]::Escape($old))).Count
    if ($c -ne 1) { throw ("{0}: expected 1, got {1}" -f $name, $c) }
    $script:t = $script:t.Replace($old, $new); Write-Output ("ok: " + $name)
}

# ── P0 列表排版
Rep '.sk5-root .ue-models{margin:2px -2px 0;padding:0 2px 2px;max-height:320px;overflow-y:auto;overscroll-behavior:contain;animation:ue-enter .2s var(--ue-motion) 40ms both;}' '.sk5-root .ue-models{margin:2px -2px 0;padding:0 2px 4px;max-height:min(280px,45vh);overflow-y:auto;overscroll-behavior:contain;scrollbar-width:thin;scrollbar-color:rgba(15,23,42,.18) transparent;animation:ue-list-in .18s cubic-bezier(.23,1,.32,1) both;}
.sk5-root .ue-models::-webkit-scrollbar{width:4px;height:4px;}
.sk5-root .ue-models::-webkit-scrollbar-track{background:transparent;}
.sk5-root .ue-models::-webkit-scrollbar-thumb{background:rgba(15,23,42,.18);border-radius:999px;}' "models"

Rep '.sk5-root .ue-modelsTitle{margin:2px 4px 6px;font-size:12px;line-height:16px;color:rgba(15,23,42,.5);}' '.sk5-root .ue-modelsTitle{margin:4px 2px 8px;font-size:11px;line-height:14px;font-weight:500;letter-spacing:.02em;color:rgba(15,23,42,.45);}' "title"

Rep '.sk5-root .ue-group{margin-top:4px;}' '.sk5-root .ue-group{margin-top:10px;}
.sk5-root .ue-group:first-of-type{margin-top:2px;}' "group"

Rep '.sk5-root .ue-groupName{margin:6px 4px 2px;font-size:11px;line-height:14px;letter-spacing:.06em;text-transform:uppercase;color:rgba(15,23,42,.42);}' '.sk5-root .ue-groupName{margin:0 2px 4px;font-size:10px;line-height:13px;font-weight:500;letter-spacing:.08em;text-transform:uppercase;color:rgba(15,23,42,.38);}' "groupname"

Rep '.sk5-root .ue-row{display:flex;align-items:center;justify-content:space-between;gap:8px;width:100%;padding:6px 8px;border:0;border-radius:8px;background:transparent;text-align:left;cursor:pointer;color:var(--dsw-alias-label-primary,#0f172a);transition:background .12s ease;}' '.sk5-root .ue-row{display:flex;align-items:center;justify-content:space-between;gap:10px;width:100%;min-height:34px;padding:8px 10px;border:0;border-radius:10px;background:transparent;text-align:left;cursor:pointer;color:var(--dsw-alias-label-primary,#0f172a);transition:background .14s ease;}
.sk5-root .ue-rowHasDesc{min-height:44px;}' "row"

Rep '.sk5-root .ue-rowName{font-size:13px;line-height:18px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}' '.sk5-root .ue-rowName{font-size:13px;line-height:18px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}' "rowname"

Rep '.sk5-root .ue-rowDesc{margin-top:1px;font-size:11px;line-height:14px;color:rgba(15,23,42,.5);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}' '.sk5-root .ue-rowDesc{margin-top:3px;font-size:11px;line-height:15px;color:rgba(15,23,42,.48);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;word-break:break-word;white-space:normal;}' "rowdesc"

Rep '.sk5-root .ue-check{flex:none;color:var(--ue-blue);font-size:13px;line-height:1;}' '.sk5-root .ue-check{flex:none;color:var(--ue-blue);font-size:14px;line-height:1;}' "check"

# ── 动画：列表进场 + 面板高度 FLIP + chevron
Rep '@keyframes ue-enter{to{opacity:1;translate:0 0}}' '@keyframes ue-enter{to{opacity:1;translate:0 0}}
@keyframes ue-list-in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}' "keyframes"

Rep '.sk5-root .ue-model:hover{background:rgba(15,23,42,.06);}' '.sk5-root .ue-model:hover{background:rgba(15,23,42,.06);}
.sk5-root .ue-model[aria-expanded="true"] .ue-modelChev{transform:rotate(180deg);}' "chevron-rotate"

Rep '.sk5-root .ue-trigger:hover{background:rgba(15,23,42,.06);}' '.sk5-root .ue-trigger:hover{background:rgba(15,23,42,.06);}' "noop"

Rep '.sk5-root .ue-trigger{display:inline-flex;align-items:center;gap:4px;max-width:260px;padding:2px 6px;border:0;border-radius:8px;background:transparent;font-size:13px;line-height:20px;color:var(--dsw-alias-label-primary,#0f172a);cursor:pointer;transition:background .12s ease;}' '.sk5-root .ue-trigger{display:inline-flex;align-items:center;gap:4px;max-width:260px;padding:2px 6px;border:0;border-radius:8px;background:transparent;font-size:13px;line-height:20px;color:var(--dsw-alias-label-primary,#0f172a);cursor:pointer;transition:background .14s ease;}' "trigger-transition"

# 模型按钮 chevron 改为 svg（可 180° 旋转）
Rep 'react.createElement("span", { className: "ue-modelChev", "aria-hidden": "true" }, "›")' 'react.createElement("svg", { className: "ue-modelChev", viewBox: "0 0 16 16", "aria-hidden": "true" }, react.createElement("path", { d: "M4 6l4 4 4-4" }))' "model-chevron-svg"

Rep '.sk5-root .ue-modelChev{flex:none;opacity:.55;font-size:12px;line-height:1;}' '.sk5-root .ue-modelChev{flex:none;width:12px;height:12px;fill:none;stroke:currentColor;stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round;opacity:.5;transition:transform .18s var(--ue-motion);}' "model-chevron-css"

# 行描述存在时加类
Rep 'react.createElement("span", { className: "ue-rowText" }, react.createElement("span", { className: "ue-rowName" }, m.name), m.description !== void 0 ? react.createElement("span", { className: "ue-rowDesc" }, m.description) : null)' 'react.createElement("span", { className: "ue-rowText" }, react.createElement("span", { className: "ue-rowName" }, m.name), m.description !== void 0 ? react.createElement("span", { className: "ue-rowDesc" }, m.description) : null)' "noop2"

# ── 面板高度 FLIP 过渡（视图切换）
$anchor = '				/** 焦点：打开面板聚焦滑杆；关闭后回到触发按钮。 */'
$flip = @'
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
'@
Rep $anchor ($flip + "`r`n" + $anchor) "flip"

# 减少动画：关闭列表进场与 chevron
Rep '.sk5-root .ue-head,.sk5-root .ue-sliderArea,.sk5-root .ue-models{animation:none;opacity:1;translate:0 0;}' '.sk5-root .ue-head,.sk5-root .ue-sliderArea,.sk5-root .ue-models{animation:none;opacity:1;translate:0 0;transform:none;}
.sk5-root .ue-modelChev,.sk5-root .ue-triggerChev{transition:none;}
.sk5-root .ue-model[aria-expanded="true"] .ue-modelChev{transform:none;}' "reduced"

[System.IO.File]::WriteAllText($f, $t, (New-Object System.Text.UTF8Encoding($false)))
Write-Output ("written size=" + (Get-Item $f).Length + " important=" + ([regex]::Matches($t, '!important')).Count)
