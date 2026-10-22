$ErrorActionPreference = "Stop"
$f = "D:\Tools\AI\Juzi-Skill\Juzi-DeepSeek-Tools\dsh-ultra-effort\lib\client.js"
$t = [System.IO.File]::ReadAllText($f, [System.Text.Encoding]::UTF8)

function Rep([string]$old, [string]$new, [string]$name) {
    $c = ([regex]::Matches($script:t, [regex]::Escape($old))).Count
    if ($c -ne 1) { throw ("{0}: expected 1, got {1}" -f $name, $c) }
    $script:t = $script:t.Replace($old, $new)
    Write-Output ("ok: " + $name)
}
function RepRange([string]$startMark, [string]$endMark, [string]$new, [string]$name) {
    $s = $script:t.IndexOf($startMark)
    $e = $script:t.IndexOf($endMark)
    if ($s -lt 0 -or $e -lt 0 -or $e -le $s) { throw ("{0}: range not found" -f $name) }
    $script:t = $script:t.Substring(0, $s) + $new + $script:t.Substring($e)
    Write-Output ("ok: " + $name)
}

$stateAnchor = "				const resetTimerRef = react.useRef(null);"
Rep $stateAnchor ($stateAnchor + @"

				/** 拖拽连续跟随：不经过 React 状态，直接写 CSS 变量。 */
				const dragFracRef = react.useRef(0);
				const dragRectRef = react.useRef(null);
				const dragRafRef = react.useRef(null);
"@) "refs"

$newDrag = @'
				const fracFromEvent = (ev, rect) => {
					const usable = Math.max(rect.width - 20, 1);
					return Math.max(0, Math.min(1, (ev.clientX - rect.left - 10) / usable));
				};
				const idxFromFrac = (frac) => Math.max(0, Math.min(choices.length - 1, Math.round(frac * (choices.length - 1))));
				/** 直接写 CSS 变量，避免每次 pointermove 触发 React 重渲染。 */
				const paintPos = (frac) => {
					const el = trackRef.current;
					if (el !== null) el.style.setProperty("--ue-pos", String(frac));
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
				};
'@
RepRange "				const idxFromEvent = (ev) => {" "				const onWinUp = () => {" $newDrag "drag-handlers"

$newDown = @'
				const onTrackDown = (ev) => {
					if (choices.length === 0) return;
					const el = trackRef.current;
					if (el === null) return;
					const rect = el.getBoundingClientRect();
					dragRectRef.current = rect;
					const frac = fracFromEvent(ev, rect);
					dragFracRef.current = frac;
					paintPos(frac);
					dragIdxRef.current = idxFromFrac(frac);
					setHoverIdx(dragIdxRef.current);
					setMoving(true);
					window.addEventListener("pointermove", onWinMove);
					window.addEventListener("pointerup", onWinUp);
					window.addEventListener("pointercancel", onWinCancel);
					window.addEventListener("blur", onWinCancel);
				};
'@
RepRange "				const onTrackDown = (ev) => {" "				const triggerTitle = " $newDown "drag-start"

$maxAnchor = "				const inMax = choices.length > 1 && safePosIdx === choices.length - 1;"
Rep $maxAnchor ($maxAnchor + @"

				/** 提交值 → CSS 变量；拖拽期间让位给 dragFrac，避免回跳。 */
				react.useLayoutEffect(() => {
					if (moving) return;
					const el = trackRef.current;
					if (el !== null) el.style.setProperty("--ue-pos", String(Math.max(0, Math.min(1, posPct / 100))));
				}, [posPct, moving, menu, choices.length]);
"@) "pos-effect"

Rep 'style: { left: handleLeft },' 'style: void 0,' "handle-style"

$fillPattern = 'width: fillWidth,\s*\r?\n(\s*)opacity: fillHidden'
if (([regex]::Matches($t, $fillPattern)).Count -ne 1) { throw "fill-style: anchor missing" }
$t = [regex]::Replace($t, $fillPattern, { param($m) $m.Groups[1].Value + "opacity: fillHidden" }, 1)
Write-Output "ok: fill-style"

Rep '.sk5-track .ue-handle{position:absolute!important;top:50%!important;bottom:auto!important;width:20px!important;height:20px!important;margin-top:-10px!important;margin-left:0!important;border-radius:50%!important;background:#fff!important;box-shadow:0 2px 8px rgba(15,23,42,.28);z-index:4;transform:translateX(-50%);transition:transform .16s ease,box-shadow .16s ease;}' '.sk5-track .ue-handle{position:absolute!important;top:50%!important;bottom:auto!important;left:calc(10px + (100% - 20px) * var(--ue-pos,0))!important;width:20px!important;height:20px!important;margin-top:-10px!important;margin-left:0!important;border-radius:50%!important;background:#fff!important;box-shadow:0 2px 8px rgba(15,23,42,.28);z-index:4;transform:translateX(-50%);will-change:left;transition:left .2s cubic-bezier(.22,.61,.36,1),transform .16s ease,box-shadow .16s ease;}' "handle-css"

Rep '.ue-fill{position:absolute;left:0;top:0;bottom:0;border-radius:999px;background:linear-gradient(90deg,#3b34c9 0%,#6f4ff2 46%,#a855f7 100%)!important;transition:width .12s linear;z-index:1;}' '.ue-fill{position:absolute;left:0;top:0;bottom:0;width:calc(10px + (100% - 20px) * var(--ue-pos,0));border-radius:999px;background:linear-gradient(90deg,#3b34c9 0%,#6f4ff2 46%,#a855f7 100%)!important;transition:width .2s cubic-bezier(.22,.61,.36,1);z-index:1;}' "fill-css"

Rep '.ue-trackMoving .ue-handle{transform:translateX(-50%) scale(1.16)!important;box-shadow:0 4px 18px rgba(80,60,200,.5)!important;}' '.ue-trackMoving .ue-handle{transform:translateX(-50%) scale(1.16)!important;box-shadow:0 4px 18px rgba(80,60,200,.5)!important;transition:transform .16s ease,box-shadow .16s ease!important;}
.ue-trackMoving .ue-fill{transition:none!important;}' "moving-css"

[System.IO.File]::WriteAllText($f, $t, (New-Object System.Text.UTF8Encoding($false)))
Write-Output ("written size=" + (Get-Item $f).Length)
