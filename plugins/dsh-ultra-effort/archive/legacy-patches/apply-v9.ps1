$ErrorActionPreference = "Stop"
$f = "D:\Tools\AI\Juzi-Skill\Juzi-DeepSeek-Tools\dsh-ultra-effort\lib\client.js"
$t = [System.IO.File]::ReadAllText($f, [System.Text.Encoding]::UTF8)

function Rep([string]$old, [string]$new, [string]$name) {
    $c = ([regex]::Matches($script:t, [regex]::Escape($old))).Count
    if ($c -ne 1) { throw ("{0}: expected 1, got {1}" -f $name, $c) }
    $script:t = $script:t.Replace($old, $new); Write-Output ("ok: " + $name)
}

# ── P1-1 重置按钮：值等于重置目标时 visibility:hidden（保留 32px 占位）
$oldBtn = 'atDefaultEffort ? null : react.createElement("button", {
					type: "button",
					className: "ue-icon ue-reset" + (resetFlash ? " ue-resetFlash" : ""),'
$newBtn = 'react.createElement("button", {
					type: "button",
					className: "ue-icon ue-reset" + (resetFlash ? " ue-resetFlash" : "") + (atDefaultEffort ? " ue-resetHidden" : ""),
					"aria-hidden": atDefaultEffort ? "true" : void 0,
					tabIndex: atDefaultEffort ? -1 : 0,'
Rep $oldBtn $newBtn "reset-button"

# 归一化比较（大小写/空值安全）
$oldCmp = '				const atDefaultEffort = effectiveEffort === defaultEffort;'
$newCmp = '				/** 重置目标 = 当前模型的 defaultEffort；两者归一化后相等即视为“已在默认档”。 */
				const normEffort = (v) => (v === void 0 || v === null ? "" : String(v).toLowerCase());
				const atDefaultEffort = normEffort(effectiveEffort) === normEffort(defaultEffort);
				/** 未显式选择过档位（隐式默认）——用于标题取正文色。 */
				const isImplicitDefault = current !== null && current.reasoningEffort === void 0;'
Rep $oldCmp $newCmp "compare"

# ── P1-2 标题配色：默认（隐式）用正文色
$oldTone = '				const titleTone = inMax ? "ue-lv-max" : "ue-lv-norm";'
$newTone = '				const titleTone = inMax ? "ue-lv-max" : (isImplicitDefault ? "ue-lv-text" : "ue-lv-norm");'
Rep $oldTone $newTone "title-tone"

Rep '.sk5-root .ue-lv-def{color:rgba(15,23,42,.45);}' '.sk5-root .ue-lv-def{color:rgba(15,23,42,.45);}
.sk5-root .ue-lv-text{color:var(--dsw-alias-label-primary,#0f172a);}
.sk5-root .ue-resetHidden{visibility:hidden;pointer-events:none;}' "tone-css"

# ── P2-1 最高档缓慢移动的径向高光
$oldUltra = '.sk5-root .ue-trackMax .ue-ultraLayer{opacity:1;animation:ue-reveal 2s cubic-bezier(.19,1,.22,1) both;}'
$newUltra = '.sk5-root .ue-trackMax .ue-ultraLayer{opacity:1;animation:ue-reveal 2s cubic-bezier(.19,1,.22,1) both;}
.sk5-root .ue-ultraLayer::after{content:"";position:absolute;inset:0;border-radius:12px;background-image:radial-gradient(ellipse 50% 120% at 50% 50%,rgba(196,160,255,.55) 0%,rgba(196,160,255,0) 72%);background-size:40% 100%;background-repeat:no-repeat;background-position:-12% 50%;animation:ue-sheen 10s ease-in-out infinite alternate;pointer-events:none;}
@keyframes ue-sheen{0%{background-position:-12% 50%}100%{background-position:112% 50%}}'
Rep $oldUltra $newUltra "ultra-sheen"

Rep '.sk5-root .ue-trackMax .ue-ultraLayer{-webkit-mask-image:none;mask-image:none;}' '.sk5-root .ue-trackMax .ue-ultraLayer{-webkit-mask-image:none;mask-image:none;}
.sk5-root .ue-ultraLayer::after{animation:none;background-position:60% 50%;}' "sheen-reduced"

[System.IO.File]::WriteAllText($f, $t, (New-Object System.Text.UTF8Encoding($false)))
Write-Output ("written size=" + (Get-Item $f).Length + " important=" + ([regex]::Matches($t, '!important')).Count)
