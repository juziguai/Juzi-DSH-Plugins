$ErrorActionPreference = "Stop"
$f = "D:\Tools\AI\Juzi-Skill\Juzi-DeepSeek-Tools\dsh-ultra-effort\lib\client.js"
$t = [System.IO.File]::ReadAllText($f, [System.Text.Encoding]::UTF8)
$css = [System.IO.File]::ReadAllText("D:\Tools\AI\Juzi-Skill\Juzi-DeepSeek-Tools\dsh-ultra-effort\build\v7.css.txt", [System.Text.Encoding]::UTF8).TrimEnd()
$render = [System.IO.File]::ReadAllText("D:\Tools\AI\Juzi-Skill\Juzi-DeepSeek-Tools\dsh-ultra-effort\build\v7-render.js.txt", [System.Text.Encoding]::UTF8).TrimEnd()

function Rep([string]$old, [string]$new, [string]$name) {
    $c = ([regex]::Matches($script:t, [regex]::Escape($old))).Count
    if ($c -ne 1) { throw ("{0}: expected 1, got {1}" -f $name, $c) }
    $script:t = $script:t.Replace($old, $new); Write-Output ("ok: " + $name)
}

# 1) 样式表整段替换
$rx = [regex]'const ULTRA_CSS = `[\s\S]*?`;'
if ($rx.Matches($t).Count -ne 1) { throw "css block not unique" }
$t = $rx.Replace($t, ("const ULTRA_CSS = ``" + "`r`n" + $css + "`r`n" + "``;").Replace('$', '$$'), 1)
Write-Output "ok: css"

# 2) 状态：按住标签计时
$anchor = "				const pressTimerRef = react.useRef(null);"
if (([regex]::Matches($t, [regex]::Escape($anchor))).Count -eq 1) {
    Rep $anchor ($anchor + "`r`n				const [showLabels, setShowLabels] = react.useState(false);") "labels-state"
} else {
    $a2 = "				const openedByKeyboardRef = react.useRef(false);"
    Rep $a2 ($a2 + "`r`n				const pressTimerRef = react.useRef(null);`r`n				const [showLabels, setShowLabels] = react.useState(false);") "labels-state"
}

# 3) 派生：档位色调 + 刻度位置
$lvl = '				const levelLabel = choices.length > 0 ? choices[safePosIdx].label : tr("effort.default");'
Rep $lvl ($lvl + "`r`n" + '				const levelTone = inMax ? "ue-lv-max" : (atDefaultEffort ? "ue-lv-def" : "ue-lv-norm");' + "`r`n" + '				const tickLeft = (i) => "calc(14px + (100% - 28px) * " + (choices.length > 1 ? i / (choices.length - 1) : 0) + ")";') "tone-and-ticks"

# 4) 按住 150ms 显示端点标签
$down = '					setMoving(true);
					window.addEventListener("pointermove", onWinMove);'
Rep $down ('					setMoving(true);' + "`r`n" + '					if (pressTimerRef.current !== null) clearTimeout(pressTimerRef.current);' + "`r`n" + '					pressTimerRef.current = setTimeout(() => setShowLabels(true), 150);' + "`r`n" + '					window.addEventListener("pointermove", onWinMove);') "press-start"

$patUp = 'stopDrag\(\);\s*\r?\n(\s*)if \(tipRef\.current !== null\) tipRef\.current\.style\.opacity = "0";'
$newUp = 'stopDrag();' + "`r`n" + '$1if (pressTimerRef.current !== null) { clearTimeout(pressTimerRef.current); pressTimerRef.current = null; }' + "`r`n" + '$1setShowLabels(false);' + "`r`n" + '$1if (tipRef.current !== null) tipRef.current.style.opacity = "0";'
$c = ([regex]::Matches($t, $patUp)).Count
if ($c -ne 1) { throw ("press-end: expected 1, got {0}" -f $c) }
$t = [regex]::Replace($t, $patUp, $newUp)
Write-Output "ok: press-end"
$patCancel = 'const onWinCancel = \(\) => \{\s*\r?\n(\s*)dragIdxRef\.current = null;\s*\r?\n(\s*)setMoving\(false\);'
$newCancel = 'const onWinCancel = () => {' + "`r`n" + '$1dragIdxRef.current = null;' + "`r`n" + '$2setMoving(false);' + "`r`n" + '$2if (pressTimerRef.current !== null) { clearTimeout(pressTimerRef.current); pressTimerRef.current = null; }' + "`r`n" + '$2setShowLabels(false);'
$cc = ([regex]::Matches($t, $patCancel)).Count
if ($cc -ne 1) { throw ("press-cancel: expected 1, got {0}" -f $cc) }
$t = [regex]::Replace($t, $patCancel, $newCancel)
Write-Output "ok: press-cancel"
# 5) 整段替换渲染
$startMarker = '				return react.createElement("div", {'
$endMarker = ': null)) : null);'
$s = $t.IndexOf($startMarker)
$e = $t.LastIndexOf($endMarker)
if ($s -lt 0 -or $e -lt 0 -or $e -lt $s) { throw "render markers not found" }
$e = $e + $endMarker.Length
$t = $t.Substring(0, $s) + $render + $t.Substring($e)
Write-Output "ok: render"

[System.IO.File]::WriteAllText($f, $t, (New-Object System.Text.UTF8Encoding($false)))
Write-Output ("written size=" + (Get-Item $f).Length + " | important=" + ([regex]::Matches($t, '!important')).Count)


