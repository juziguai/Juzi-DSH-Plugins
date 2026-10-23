$ErrorActionPreference = "Stop"
$f = "D:\Tools\AI\Juzi-Skill\Juzi-DeepSeek-Tools\dsh-ultra-effort\lib\client.js"
$t = [System.IO.File]::ReadAllText($f, [System.Text.Encoding]::UTF8)

function Rep([string]$old, [string]$new, [string]$name) {
    $c = ([regex]::Matches($script:t, [regex]::Escape($old))).Count
    if ($c -ne 1) { throw ("{0}: expected 1 match, got {1}" -f $name, $c) }
    $script:t = $script:t.Replace($old, $new)
    Write-Output ("ok: " + $name)
}

Rep 'id: "@domitor-syh/dsh-ui-skin-switcher",' 'id: "@juzi/dsh-ultra-effort",' "module-id"

$newLabel = 'react.createElement("span", { className: "sk5-effortLabel jz-ultra" }, react.createElement("svg", { className: "jz-bolt", viewBox: "0 0 24 24", "aria-hidden": "true" }, react.createElement("path", { d: "M13 2 3 14h7l-1 8 10-12h-7l1-8z" })), "Ultra")'
Rep 'react.createElement("span", { className: "sk5-effortLabel" }, "Effort")' $newLabel "ultra-label"

Rep ', react.createElement("div", { className: "sk5-labelsRow" }' ', react.createElement("div", { className: "jz-sub" }, "使用额度消耗更快"), react.createElement("div", { className: "sk5-labelsRow" }' "subtitle"

$css = @'
		/** Ultra skin: purple gradient track, sparkles, Ultra title. Visual only. */
		const ULTRA_CSS = `
.jz-titleRow{position:relative;}
.jz-ultra{display:inline-flex;align-items:center;gap:6px;font-size:20px;font-weight:700;letter-spacing:.2px;background:linear-gradient(92deg,#5b21b6 0%,#8b5cf6 45%,#4f46e5 100%);-webkit-background-clip:text;background-clip:text;color:transparent!important;}
.jz-bolt{width:15px;height:15px;fill:#8b5cf6;flex:none;}
.jz-sub{margin:-2px 0 10px;font-size:12px;line-height:18px;color:var(--dsw-alias-label-secondary,rgba(0,0,0,.55));}
.sk5-effort .sk5-effortValue{color:#7c3aed!important;font-weight:600;}
.sk5-track{position:relative;background:linear-gradient(90deg,#ede9fe 0%,#ddd6fe 100%)!important;border-radius:999px!important;}
.sk5-track::after{content:"";position:absolute;inset:0;border-radius:999px;pointer-events:none;background-image:radial-gradient(circle at 16% 34%,rgba(255,255,255,.95) 0 1.1px,transparent 1.7px),radial-gradient(circle at 31% 63%,rgba(255,255,255,.85) 0 1px,transparent 1.6px),radial-gradient(circle at 45% 29%,rgba(255,255,255,.9) 0 1.2px,transparent 1.8px),radial-gradient(circle at 59% 60%,rgba(255,255,255,.8) 0 1px,transparent 1.6px),radial-gradient(circle at 72% 36%,rgba(255,255,255,.95) 0 1.1px,transparent 1.7px),radial-gradient(circle at 85% 58%,rgba(255,255,255,.85) 0 1px,transparent 1.6px);animation:jz-twinkle 2.6s ease-in-out infinite;}
@keyframes jz-twinkle{0%,100%{opacity:.5}50%{opacity:1}}
.sk5-fill{background:linear-gradient(90deg,#4f46e5 0%,#7c3aed 45%,#a855f7 100%)!important;border-radius:999px!important;box-shadow:0 0 10px rgba(139,92,246,.45);}
.sk5-handle{background:#fff!important;box-shadow:0 2px 8px rgba(76,29,149,.32),0 0 0 1px rgba(124,58,237,.10)!important;}
.sk5-handleMax{box-shadow:0 0 0 6px rgba(168,85,247,.16),0 2px 12px rgba(124,58,237,.5)!important;}
.sk5-dot{background:#fff!important;opacity:.8;}
`;
'@
Rep '		const NS = "ui-skin-switcher";' ($css + '		const NS = "ui-skin-switcher";') "css-const"

$t = $t.Replace('ctx.effect(() => injectCss(CSS));', 'ctx.effect(() => injectCss(CSS));' + "`r`n`t`t`t" + 'ctx.effect(() => injectCss(ULTRA_CSS), "ui-ultra-effort: skin");')

[System.IO.File]::WriteAllText($f, $t, (New-Object System.Text.UTF8Encoding($false)))
Write-Output ("written size=" + (Get-Item $f).Length)
