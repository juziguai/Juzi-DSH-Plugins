$ErrorActionPreference = "Stop"
$f = "D:\Tools\AI\Juzi-Skill\Juzi-DeepSeek-Tools\dsh-ultra-effort\lib\client.js"
$t = [System.IO.File]::ReadAllText($f, [System.Text.Encoding]::UTF8)

function Rep([string]$old, [string]$new, [string]$name) {
    $c = ([regex]::Matches($script:t, [regex]::Escape($old))).Count
    if ($c -ne 1) { throw ("{0}: expected 1, got {1}" -f $name, $c) }
    $script:t = $script:t.Replace($old, $new); Write-Output ("ok: " + $name)
}
function RepRx([string]$pat, [string]$new, [string]$name) {
    $c = ([regex]::Matches($script:t, $pat)).Count
    if ($c -ne 1) { throw ("{0}: expected 1, got {1}" -f $name, $c) }
    $script:t = [regex]::Replace($script:t, $pat, { param($m) $new }, 1); Write-Output ("ok: " + $name)
}

$oldClick = '					onClick: () => setMenu((m) => m === "effort" ? null : "effort")'
$newClick = "					onClick: (ev) => {`r`n						openedByKeyboardRef.current = ev.detail === 0;`r`n						setMenu((m) => m === `"effort`" ? null : `"effort`");`r`n					}"
Rep $oldClick $newClick "click-handler"

$refA = '				const panelRef = react.useRef(null);'
Rep $refA ($refA + "`r`n				const openedByKeyboardRef = react.useRef(false);") "kb-ref"

$patFocus = '(?m)^(\s*)if \(trackRef\.current !== null\) trackRef\.current\.focus'
$newFocus = '$1const root = rootRef.current;' + "`r`n" + '$1if (root !== null) root.classList.toggle("ue-kb", openedByKeyboardRef.current);' + "`r`n" + '$1if (trackRef.current !== null) trackRef.current.focus'
$c = ([regex]::Matches($t, $patFocus)).Count
if ($c -ne 1) { throw ("focus-kb-class: expected 1, got {0}" -f $c) }
$t = [regex]::Replace($t, $patFocus, $newFocus)
Write-Output "ok: focus-kb-class"
$patKey = 'const onTrackKeyDown = \(ev\) => \{\s*\r?\n\s*if \(choices\.length < 2\) return;'
$newKey = "const onTrackKeyDown = (ev) => {`r`n					if (rootRef.current !== null) rootRef.current.classList.add(`"ue-kb`");`r`n					if (choices.length < 2) return;"
RepRx $patKey $newKey "key-kb-class"

$cssOld = '.sk5-root .ue-track:focus-visible{outline:2px solid rgba(124,58,237,.75);outline-offset:3px;border-radius:999px;}'
$cssNew = $cssOld + "`r`n" + '.sk5-root:not(.ue-kb) .ue-track:focus-visible{outline:none;}'
Rep $cssOld $cssNew "focus-css"

$modelOld = '.sk5-root .ue-model{display:inline-flex;align-items:center;justify-content:center;'
$modelNew = '.sk5-root .ue-model{display:inline-flex;align-items:flex-start;justify-content:center;'
Rep $modelOld $modelNew "model-align"

$chevOld = '.sk5-root .ue-chev{width:13px;height:13px;flex:none;opacity:.5;'
$chevNew = '.sk5-root .ue-chev{width:13px;height:13px;flex:none;margin-top:4px;opacity:.5;'
Rep $chevOld $chevNew "chev-align"

[System.IO.File]::WriteAllText($f, $t, (New-Object System.Text.UTF8Encoding($false)))
Write-Output ("written size=" + (Get-Item $f).Length)


