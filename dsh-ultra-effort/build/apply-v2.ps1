$ErrorActionPreference = "Stop"
$f = "D:\Tools\AI\Juzi-Skill\Juzi-DeepSeek-Tools\dsh-ultra-effort\lib\client.js"
$t = [System.IO.File]::ReadAllText($f, [System.Text.Encoding]::UTF8)
$panel = [System.IO.File]::ReadAllText("D:\Tools\AI\Juzi-Skill\Juzi-DeepSeek-Tools\dsh-ultra-effort\build\v2-panel.js.txt", [System.Text.Encoding]::UTF8)
$cssBlock = [System.IO.File]::ReadAllText("D:\Tools\AI\Juzi-Skill\Juzi-DeepSeek-Tools\dsh-ultra-effort\build\v2.css.txt", [System.Text.Encoding]::UTF8)
$panel = $panel.Replace("React.Fragment", "react.Fragment").TrimEnd()

function Rep([string]$old, [string]$new, [string]$name) {
    $c = ([regex]::Matches($script:t, [regex]::Escape($old))).Count
    if ($c -ne 1) { throw ("{0}: expected 1 match, got {1}" -f $name, $c) }
    $script:t = $script:t.Replace($old, $new)
    Write-Output ("ok: " + $name)
}

# 1) 替换样式表
$cssNew = "		const ULTRA_CSS = ``" + "`r`n" + $cssBlock.TrimEnd() + "`r`n" + "``;"
$rx = [regex]'const ULTRA_CSS = `[\s\S]*?`;'
if ($rx.Matches($t).Count -ne 1) { throw "css block not unique" }
$t = $rx.Replace($t, $cssNew.Replace('$', '$$'), 1)
Write-Output "ok: css"

# 2) 状态
$stateAnchor = "				const [settledIdx, setSettledIdx] = react.useState(null);"
$stateAdd = @"
$stateAnchor
				/** V2: 面板内视图（effort | model）、终点动画、重置反馈。 */
				const [panelView, setPanelView] = react.useState("effort");
				const [burst, setBurst] = react.useState(false);
				const [resetFlash, setResetFlash] = react.useState(false);
				const burstRef = react.useRef(false);
				const resetTimerRef = react.useRef(null);
"@
Rep $stateAnchor $stateAdd "state"

# 3) 视图复位 + 卸载清理
$effAnchor = "				react.useEffect(() => {
					if (menu !== ""effort"") return;"
$effNew = "				react.useEffect(() => {
					if (menu !== ""effort"") {
						setPanelView(""effort"");
					}
				}, [menu]);
				react.useEffect(() => () => {
					if (resetTimerRef.current !== null) clearTimeout(resetTimerRef.current);
				}, []);
$effAnchor"
Rep $effAnchor $effNew "panel-view-reset"

# 4) 终点动画（放在 inMax 之后）
$maxAnchor = "				const inMax = choices.length > 1 && safeDisplayIdx === choices.length - 1;"
$maxAdd = @"
$maxAnchor
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
"@
Rep $maxAnchor $maxAdd "burst-effect"

# 5) 重置与键盘处理（放在 onPickEffort 之后）
$pickAnchor = @"
				const onPickEffort = (effort) => {
					if (current === null) return;
					apply({
						provider: current.provider,
						model: current.model,
						...effort === void 0 ? {} : { reasoningEffort: effort }
					}, true);
				};
"@
$pickAdd = $pickAnchor + @"

				/** 当前模型的默认推理程度；undefined 表示“默认档”。 */
				const defaultEffort = reasoning !== void 0 ? reasoning.defaultEffort : void 0;
				const atDefaultEffort = effectiveEffort === defaultEffort;
				const onReset = () => {
					if (current === null || reasoning === void 0) return;
					setResetFlash(true);
					if (resetTimerRef.current !== null) clearTimeout(resetTimerRef.current);
					resetTimerRef.current = setTimeout(() => setResetFlash(false), 260);
					if (effectiveEffort !== defaultEffort) onPickEffort(defaultEffort);
				};
				/** 滑杆键盘控制：方向键逐档、Home/End 到两端。 */
				const onTrackKeyDown = (ev) => {
					if (choices.length < 2) return;
					let next = null;
					if (ev.key === "ArrowRight" || ev.key === "ArrowUp") next = Math.min(choices.length - 1, safePosIdx + 1);
					else if (ev.key === "ArrowLeft" || ev.key === "ArrowDown") next = Math.max(0, safePosIdx - 1);
					else if (ev.key === "Home") next = 0;
					else if (ev.key === "End") next = choices.length - 1;
					else return;
					ev.preventDefault();
					setHoverIdx(next);
					onPickEffort(choices[next].effort);
				};
"@
Rep $pickAnchor $pickAdd "reset-and-keys"

# 6) 替换整个强度面板 JSX
$startMarker = 'menu === "effort" ? react.createElement("div", {'
$endMarker = ': null) : null);'
$start = $t.IndexOf($startMarker)
$end = $t.LastIndexOf($endMarker)
if ($start -lt 0 -or $end -lt 0 -or $end -lt $start) { throw "panel markers not found" }
$end = $end + $endMarker.Length
$t = $t.Substring(0, $start) + $panel + $t.Substring($end)
Write-Output "ok: panel"

[System.IO.File]::WriteAllText($f, $t, (New-Object System.Text.UTF8Encoding($false)))
Write-Output ("written size=" + (Get-Item $f).Length)
