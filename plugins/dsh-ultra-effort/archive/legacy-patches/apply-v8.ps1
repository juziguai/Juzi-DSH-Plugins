$ErrorActionPreference = "Stop"
$f = "D:\Tools\AI\Juzi-Skill\Juzi-DeepSeek-Tools\dsh-ultra-effort\lib\client.js"
$t = [System.IO.File]::ReadAllText($f, [System.Text.Encoding]::UTF8)
$sizeBefore = (Get-Item $f).Length

function Rep([string]$old, [string]$new, [string]$name) {
    $c = ([regex]::Matches($script:t, [regex]::Escape($old))).Count
    if ($c -ne 1) { throw ("{0}: expected 1, got {1}" -f $name, $c) }
    $script:t = $script:t.Replace($old, $new); Write-Output ("ok: " + $name)
}

# ── P0-1 形状：显式 corner-shape: round（宿主全局 superellipse 会把手柄变 squircle）
Rep '.sk5-root .ue-track{position:relative;width:100%;height:24px;border-radius:12px;' '.sk5-root .ue-track{corner-shape:round;position:relative;width:100%;height:24px;border-radius:12px;' "track-shape"
Rep '.sk5-root .ue-fill{position:absolute;left:0;top:0;bottom:0;' '.sk5-root .ue-fill{corner-shape:round;position:absolute;left:0;top:0;bottom:0;' "fill-shape"
Rep '.sk5-root .ue-tick{position:absolute;top:50%;' '.sk5-root .ue-tick{corner-shape:round;position:absolute;top:50%;' "tick-shape"
Rep '.sk5-root .ue-handle{position:absolute;box-sizing:border-box;' '.sk5-root .ue-handle{corner-shape:round;border-radius:999px;position:absolute;box-sizing:border-box;' "handle-shape"

# ── P1-2 字体：继承宿主
Rep '.sk5-root{--ue-blue:#3a83f7;' '.sk5-root .sk5-drop{font-family:inherit;}
.sk5-root{--ue-blue:#3a83f7;' "font-inherit"

# ── P0-2 标签移到头部（副标题让位）
Rep '.sk5-root .ue-labels{position:absolute;inset:0;display:flex;align-items:center;justify-content:space-between;padding:0 6px;pointer-events:none;opacity:0;transition:opacity .16s ease;font-size:10px;line-height:14px;color:rgba(15,23,42,.55);z-index:5;}' '.sk5-root .ue-labels{position:absolute;left:8px;right:8px;bottom:2px;display:flex;align-items:center;justify-content:space-between;pointer-events:none;opacity:0;transition:opacity .15s var(--ue-motion);font-size:11px;line-height:14px;color:var(--ue-tertiary);z-index:6;}' "labels-css"
Rep '.sk5-root .ue-sliderArea.ue-labelsOn .ue-labels{opacity:1;}
.sk5-root .ue-labels span{background:rgba(255,255,255,.82);border-radius:6px;padding:0 4px;}' '.sk5-root .ue-labels.ue-labelsOn{opacity:1;}
.sk5-root .ue-model.ue-modelHidden{opacity:0;pointer-events:none;}
.sk5-root .ue-model{transition:opacity .15s var(--ue-motion),background .12s ease;}' "labels-css2"

# ── P1-1 光点：3px/#ffffffb8/5px 光晕，流动且 0→1→0
Rep '.sk5-root .ue-stream i{position:absolute;width:3px;height:3px;border-radius:999px;background:#ffffffb8;box-shadow:0 0 5px #ffffff57;animation:ue-flow 3.6s linear infinite;}' '.sk5-root .ue-stream i{corner-shape:round;position:absolute;width:3px;height:3px;border-radius:999px;background:#ffffffb8;box-shadow:0 0 5px #ffffff57;animation-name:ue-flow;animation-timing-function:linear;animation-iteration-count:infinite;}' "stream-css"

# ── P2-1 重置图标逆时针
Rep 'react.createElement("path", { d: "M13.2 6.2A5.6 5.6 0 1 0 13.4 9.4" }), react.createElement("path", { d: "M13.6 2.4v4h-4" })' 'react.createElement("path", { d: "M2.8 6.2A5.6 5.6 0 1 1 2.6 9.4" }), react.createElement("path", { d: "M2.4 2.4v4h4" })' "reset-icon"

# ── 标签 DOM 移到头部
$labelsJsx = 'react.createElement("div", { className: "ue-labels" + (showLabels ? " ue-labelsOn" : "") }, react.createElement("span", null, "Faster"), react.createElement("span", null, "Smarter")), '
Rep 'react.createElement("div", { className: "ue-center" },' ($labelsJsx + 'react.createElement("div", { className: "ue-center" },') "labels-move-in"
Rep ', react.createElement("div", { className: "ue-labels" }, react.createElement("span", null, "Faster"), react.createElement("span", null, "Smarter"))), shownError' '), shownError' "labels-remove-old"

# ── 副标题在按住时让位
Rep 'className: "ue-model" + (panelView === "model" ? " ue-modelOpen" : "")' 'className: "ue-model" + (panelView === "model" ? " ue-modelOpen" : "") + (showLabels ? " ue-modelHidden" : "")' "subtitle-hide"

# ── 光点数量与随机分布
$streamOld = 'react.createElement("div", { className: "ue-stream", "aria-hidden": "true" }, react.createElement("i", null), react.createElement("i", null), react.createElement("i", null), react.createElement("i", null), react.createElement("i", null), react.createElement("i", null), react.createElement("i", null), react.createElement("i", null))'
$streamNew = 'react.createElement("div", { className: "ue-stream", "aria-hidden": "true" }, streamDots.map((d, i) => react.createElement("i", { key: i, style: { top: d.top, animationDuration: d.dur, animationDelay: d.delay } })))'
Rep $streamOld $streamNew "stream-jsx"

$dotsAnchor = '				const tickLeft = (i) => "calc(14px + (100% - 28px) * " + (choices.length > 1 ? i / (choices.length - 1) : 0) + ")";'
Rep $dotsAnchor ($dotsAnchor + "`r`n" + '				/** 14 个流动光点：纵向随机 ±8px，时长/延迟随机（只算一次）。 */' + "`r`n" + '				const streamDots = react.useMemo(() => Array.from({ length: 14 }, () => {' + "`r`n" + '					const dy = (Math.random() * 16 - 8).toFixed(1);' + "`r`n" + '					return { top: "calc(50% + " + dy + "px)", dur: (2.4 + Math.random() * 2.6).toFixed(2) + "s", delay: (-Math.random() * 4.5).toFixed(2) + "s" };' + "`r`n" + '				}), []);') "stream-dots"

# ── 移除内嵌 Space Grotesk 字体（若仅此处使用）
$fontRx = [regex]'@font-face\{font-family:"Space Grotesk"[^}]*\}'
$fontMatches = $fontRx.Matches($t).Count
"font-face blocks: $fontMatches"
if ($fontMatches -ge 1) { $t = $fontRx.Replace($t, '', 1); Write-Output "ok: remove-font-face" }

[System.IO.File]::WriteAllText($f, $t, (New-Object System.Text.UTF8Encoding($false)))
$sizeAfter = (Get-Item $f).Length
Write-Output ("size: {0} -> {1} (delta {2})" -f $sizeBefore, $sizeAfter, ($sizeAfter - $sizeBefore))

