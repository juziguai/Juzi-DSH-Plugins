$ErrorActionPreference = "Stop"
$f = "D:\Tools\AI\Juzi-Skill\Juzi-DeepSeek-Tools\dsh-ultra-effort\lib\client.js"
$t = [System.IO.File]::ReadAllText($f, [System.Text.Encoding]::UTF8)

function Rep([string]$old, [string]$new, [string]$name) {
    $c = ([regex]::Matches($script:t, [regex]::Escape($old))).Count
    if ($c -ne 1) { throw ("{0}: expected 1, got {1}" -f $name, $c) }
    $script:t = $script:t.Replace($old, $new)
    Write-Output ("ok: " + $name)
}

$stateAnchor = "				const dragRafRef = react.useRef(null);"
Rep $stateAnchor ($stateAnchor + @"

				const tipRef = react.useRef(null);
				const tipTextRef = react.useRef(null);
				const tipIdxRef = react.useRef(-1);
				const tipBoxRef = react.useRef(null);
"@) "tip-refs"

$paintAnchor = @'
				/** 直接写 CSS 变量，避免每次 pointermove 触发 React 重渲染。 */
				const paintPos = (frac) => {
					const el = trackRef.current;
					if (el !== null) el.style.setProperty("--ue-pos", String(frac));
				};
'@
$paintNew = @'
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
						tip.style.left = rect.left - box.left + 10 + (rect.width - 20) * frac + "px";
					}
					if (near !== tipIdxRef.current) {
						tipIdxRef.current = near;
						if (tipTextRef.current !== null) tipTextRef.current.textContent = choices[near].label;
					}
				};
'@
Rep $paintAnchor $paintNew "detent-map"

$upAnchor = @'
					stopDrag();
					const c = choices[idx];
'@
Rep $upAnchor @'
					stopDrag();
					if (tipRef.current !== null) tipRef.current.style.opacity = "0";
					tipIdxRef.current = -1;
					const c = choices[idx];
'@ "tip-hide-on-up"

# 在拖拽开始时缓存气泡定位基准
$downAnchor = @'
					dragRectRef.current = rect;
'@
Rep $downAnchor @'
					dragRectRef.current = rect;
					const tipEl = tipRef.current;
					tipBoxRef.current = tipEl !== null && tipEl.offsetParent !== null ? tipEl.offsetParent.getBoundingClientRect() : null;
'@ "tip-box-cache"

# 把气泡插入面板（头部之后）
Rep 'panelView === "model" ? react.createElement("div", {' 'react.createElement("span", { ref: tipRef, className: "ue-tip", "aria-hidden": "true" }, react.createElement("span", { ref: tipTextRef, className: "ue-tipText" }, "")), panelView === "model" ? react.createElement("div", {' "tip-element"

Rep '.ue-labelsRow{display:flex;justify-content:space-between;margin:0 2px 8px;font-size:12px;line-height:16px;color:var(--dsw-alias-label-secondary,rgba(15,23,42,.55));}' '.ue-labelsRow{display:flex;justify-content:space-between;margin:0 2px 8px;font-size:12px;line-height:16px;color:var(--dsw-alias-label-secondary,rgba(15,23,42,.55));}
.ue-tip{position:absolute;bottom:calc(100% + 6px);left:0;transform:translateX(-50%);padding:2px 9px;border-radius:999px;background:rgba(255,255,255,.96);border:1px solid rgba(124,58,237,.18);box-shadow:0 4px 14px rgba(76,29,149,.18);color:#6d28d9;font-size:11px;line-height:16px;white-space:nowrap;pointer-events:none;opacity:0;transition:opacity .1s linear;z-index:9;}' "tip-css"

[System.IO.File]::WriteAllText($f, $t, (New-Object System.Text.UTF8Encoding($false)))
Write-Output ("written size=" + (Get-Item $f).Length)
