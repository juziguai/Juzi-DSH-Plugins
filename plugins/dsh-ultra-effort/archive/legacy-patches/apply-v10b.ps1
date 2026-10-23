$ErrorActionPreference = "Stop"
$f = "D:\Tools\AI\Juzi-Skill\Juzi-DeepSeek-Tools\dsh-ultra-effort\lib\client.js"
$t = [System.IO.File]::ReadAllText($f, [System.Text.Encoding]::UTF8)

function Rep([string]$old, [string]$new, [string]$name) {
    $c = ([regex]::Matches($script:t, [regex]::Escape($old))).Count
    if ($c -ne 1) { throw ("{0}: expected 1, got {1}" -f $name, $c) }
    $script:t = $script:t.Replace($old, $new); Write-Output ("ok: " + $name)
}

# 提供商标题：11/500/.42，非 uppercase
Rep '.sk5-root .ue-groupName{margin:0 2px 4px;font-size:10px;line-height:13px;font-weight:500;letter-spacing:.08em;text-transform:uppercase;color:rgba(15,23,42,.38);}' '.sk5-root .ue-groupName{margin:0 2px 4px;font-size:11px;line-height:15px;font-weight:500;letter-spacing:0;text-transform:none;color:rgba(15,23,42,.42);cursor:default;user-select:none;}' "groupname"

# 组间距 12px；首组 2px
Rep '.sk5-root .ue-group{margin-top:10px;}' '.sk5-root .ue-group{margin-top:12px;}' "group-gap"

# 模型行缩进 14px + padding 7×10
Rep '.sk5-root .ue-row{display:flex;align-items:center;justify-content:space-between;gap:10px;width:100%;min-height:34px;padding:8px 10px;border:0;border-radius:10px;background:transparent;text-align:left;cursor:pointer;color:var(--dsw-alias-label-primary,#0f172a);transition:background .14s ease;}' '.sk5-root .ue-row{display:flex;align-items:center;justify-content:space-between;gap:10px;width:calc(100% - 14px);margin-left:14px;min-height:34px;padding:7px 10px;border:0;border-radius:10px;background:transparent;text-align:left;cursor:pointer;color:var(--dsw-alias-label-primary,#0f172a);transition:background .14s ease;}' "row"

# 描述单行省略
Rep '.sk5-root .ue-rowDesc{margin-top:3px;font-size:11px;line-height:15px;color:rgba(15,23,42,.48);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;word-break:break-word;white-space:normal;}' '.sk5-root .ue-rowDesc{margin-top:2px;font-size:11px;line-height:15px;color:rgba(15,23,42,.48);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}' "rowdesc"

# 组标题中文映射（仅显示层，不改数据/回调）
$mapFn = @'
				/** 提供商显示名：仅做展示映射（与设置页一致），不改 groups 数据与选择回调。 */
				const providerLabel = (g) => {
					const key = (String(g.id) + " " + String(g.name)).toLowerCase();
					if (key.indexOf("account") >= 0) return "DeepSeek 账号";
					if (key.indexOf("workbuddy") >= 0 || key.indexOf("work-buddy") >= 0 || key.indexOf("work buddy") >= 0) return "WorkBuddy";
					if (key.indexOf("deepseek") >= 0) return "DeepSeek";
					return g.name;
				};
'@
$anchor = '				const isDefaultChoice = choices.length > 0 && choices[safePosIdx].key === "default";'
Rep $anchor ($mapFn + "`r`n" + $anchor) "provider-map"

Rep 'react.createElement("div", { className: "ue-groupName" }, g.name)' 'react.createElement("div", { className: "ue-groupName" }, providerLabel(g))' "provider-label-jsx"

[System.IO.File]::WriteAllText($f, $t, (New-Object System.Text.UTF8Encoding($false)))
Write-Output ("written size=" + (Get-Item $f).Length + " important=" + ([regex]::Matches($t, '!important')).Count)
