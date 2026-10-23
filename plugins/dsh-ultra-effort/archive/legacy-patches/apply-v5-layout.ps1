$ErrorActionPreference = "Stop"
$f = "D:\Tools\AI\Juzi-Skill\Juzi-DeepSeek-Tools\dsh-ultra-effort\lib\client.js"
$t = [System.IO.File]::ReadAllText($f, [System.Text.Encoding]::UTF8)

function Rep([string]$old, [string]$new, [string]$name) {
    $c = ([regex]::Matches($script:t, [regex]::Escape($old))).Count
    if ($c -ne 1) { throw ("{0}: expected 1, got {1}" -f $name, $c) }
    $script:t = $script:t.Replace($old, $new); Write-Output ("ok: " + $name)
}

Rep 'const HANDLE_W = 20;' 'const HANDLE_W = 26;' "handle-w"
Rep 'const usable = Math.max(rect.width - 20, 1);' 'const usable = Math.max(rect.width - HANDLE_W, 1);' "usable"
Rep 'return Math.max(0, Math.min(1, (ev.clientX - rect.left - 10) / usable));' 'return Math.max(0, Math.min(1, (ev.clientX - rect.left - HANDLE_W / 2) / usable));' "frac"
Rep 'tip.style.left = rect.left - box.left + 10 + (rect.width - 20) * frac + "px";' 'tip.style.left = rect.left - box.left + HANDLE_W / 2 + (rect.width - HANDLE_W) * frac + "px";' "tip-left"
Rep 'const dotLeft = (i) => "calc(10px + (100% - 20px) * " + (choices.length > 1 ? i / (choices.length - 1) : 0) + ")";' 'const dotLeft = (i) => "calc(" + HANDLE_W / 2 + "px + (100% - " + HANDLE_W + "px) * " + (choices.length > 1 ? i / (choices.length - 1) : 0) + ")";' "dot-left"
Rep 'const handleLeft = "calc(10px + (100% - 20px) * " + posFrac + ")";' 'const handleLeft = "calc(" + HANDLE_W / 2 + "px + (100% - " + HANDLE_W + "px) * " + posFrac + ")";' "handle-left"

Rep 'style: grid === null ? void 0 : { height: grid.trackHeight + "px" },' 'style: { height: TRACK_H + "px" },' "track-height"
Rep '				const HANDLE_W = 26;' ("				const HANDLE_W = 26;" + "`r`n				const TRACK_H = 30;") "track-const"

$menuAnchor = '				const tipBoxRef = react.useRef(null);'
$menuEffect = @'
				/** 面板锚点在座位（位于输入框内部），只上移 6px 会压住输入框；这里量出输入框高度再抬升。 */
				react.useLayoutEffect(() => {
					const root = rootRef.current;
					if (root === null) return;
					if (menu === null) {
						root.style.removeProperty("--ue-drop-lift");
						return;
					}
					const rootRect = root.getBoundingClientRect();
					let node = root.parentElement;
					let lift = 8;
					for (let i = 0; i < 6 && node !== null; i++, node = node.parentElement) {
						const r = node.getBoundingClientRect();
						if (r.height >= 70) {
							lift = Math.max(8, rootRect.top - r.top + 8);
							break;
						}
					}
					root.style.setProperty("--ue-drop-lift", lift + "px");
				}, [menu]);
'@
Rep $menuAnchor ($menuAnchor + "`r`n" + $menuEffect) "drop-lift"

Rep '.sk5-drop.sk5-effort.ue-panel{width:342px;padding:16px 16px 14px;border-radius:18px;border:1px solid rgba(15,23,42,.07);background:var(--dsw-alias-bg-elevated,#fff);box-shadow:0 18px 44px rgba(15,23,42,.14),0 2px 8px rgba(15,23,42,.06);}' '.sk5-drop{--ue-drop-lift:8px;bottom:calc(100% + var(--ue-drop-lift))!important;}
.sk5-drop.sk5-effort.ue-panel{width:min(360px,calc(100vw - 40px));padding:18px 18px 16px;border-radius:20px;border:1px solid rgba(15,23,42,.07);background:var(--dsw-alias-bg-elevated,#fff);box-shadow:0 24px 60px rgba(15,23,42,.16),0 2px 8px rgba(15,23,42,.06);}' "panel-css"

Rep '.ue-track{position:relative;border-radius:999px;background:linear-gradient(90deg,#ece9ff 0%,#e4defb 100%);cursor:pointer;touch-action:none;outline:none;overflow:hidden;isolation:isolate;}' '.ue-track{position:relative;height:30px;border-radius:999px!important;background:linear-gradient(90deg,#ece9ff 0%,#e4defb 100%);cursor:pointer;touch-action:none;outline:none;overflow:hidden;isolation:isolate;}' "track-css"

Rep '.ue-fill{position:absolute;left:0;top:0;bottom:0;width:calc(10px + (100% - 20px) * var(--ue-pos,0));border-radius:999px;background:linear-gradient(90deg,#3b34c9 0%,#6f4ff2 46%,#a855f7 100%)!important;transition:width .2s cubic-bezier(.22,.61,.36,1);z-index:1;}' '.ue-fill{position:absolute;left:0;top:0;bottom:0;width:calc(26px + (100% - 26px) * var(--ue-pos,0));border-radius:999px!important;background:linear-gradient(90deg,#3b34c9 0%,#6f4ff2 46%,#a855f7 100%)!important;transition:width .2s cubic-bezier(.22,.61,.36,1);z-index:1;}' "fill-css"

Rep '.sk5-track .ue-handle{position:absolute!important;top:50%!important;bottom:auto!important;left:calc(10px + (100% - 20px) * var(--ue-pos,0))!important;width:20px!important;height:20px!important;margin-top:-10px!important;margin-left:0!important;border-radius:50%!important;background:#fff!important;box-shadow:0 2px 8px rgba(15,23,42,.28);z-index:4;transform:translateX(-50%);will-change:left;transition:left .2s cubic-bezier(.22,.61,.36,1),transform .16s ease,box-shadow .16s ease;}' '.sk5-track .ue-handle{position:absolute!important;top:50%!important;bottom:auto!important;left:calc(13px + (100% - 26px) * var(--ue-pos,0))!important;width:26px!important;height:26px!important;margin-top:-13px!important;margin-left:0!important;border-radius:50%!important;background:#fff!important;box-shadow:0 1px 2px rgba(15,23,42,.14),0 4px 12px rgba(15,23,42,.22),0 0 0 .5px rgba(15,23,42,.06);z-index:4;transform:translateX(-50%);will-change:left;transition:left .2s cubic-bezier(.22,.61,.36,1),transform .16s ease,box-shadow .16s ease;}' "handle-css"

Rep '.ue-labelsRow{display:flex;justify-content:space-between;margin:0 2px 8px;font-size:12px;line-height:16px;color:var(--dsw-alias-label-secondary,rgba(15,23,42,.55));}' '.ue-labelsRow{display:flex;justify-content:space-between;margin:0 2px 10px;font-size:11px;line-height:14px;letter-spacing:.01em;color:var(--dsw-alias-label-secondary,rgba(15,23,42,.5));}
.ue-track .sk5-dotHit{align-items:center!important;}
.ue-track .sk5-dot{margin-top:0!important;}' "labels-css"

Rep '.ue-ultra{font-size:24px;' '.ue-ultra{font-size:26px;' "ultra-size"
Rep 'font-size:15px;line-height:20px;cursor:pointer;transition:background .15s ease;}' 'font-size:16px;line-height:22px;cursor:pointer;transition:background .15s ease;}' "model-size"
Rep '.ue-head{display:grid;grid-template-columns:28px minmax(0,1fr) 28px;align-items:center;gap:8px;margin-bottom:16px;}' '.ue-head{display:grid;grid-template-columns:30px minmax(0,1fr) 30px;align-items:center;gap:10px;margin-bottom:18px;}' "head-grid"

[System.IO.File]::WriteAllText($f, $t, (New-Object System.Text.UTF8Encoding($false)))
Write-Output ("written size=" + (Get-Item $f).Length)
