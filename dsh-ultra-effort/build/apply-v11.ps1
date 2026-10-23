$ErrorActionPreference = "Stop"
$f = "D:\Tools\AI\Juzi-Skill\Juzi-DeepSeek-Tools\dsh-ultra-effort\lib\client.js"
$t = [System.IO.File]::ReadAllText($f, [System.Text.Encoding]::UTF8)

function Rep([string]$old, [string]$new, [string]$name) {
    $c = ([regex]::Matches($script:t, [regex]::Escape($old))).Count
    if ($c -ne 1) { throw ("{0}: expected 1, got {1}" -f $name, $c) }
    $script:t = $script:t.Replace($old, $new); Write-Output ("ok: " + $name)
}

# 1) 删除「选择模型」标题节点
Rep 'react.createElement("div", { className: "ue-modelsTitle" }, tr("trigger.selectModel")), ' '' "remove-title-jsx"

# 2) 分组标题更醒目 + 组间距 16px
Rep '.sk5-root .ue-groupName{margin:0 2px 4px;font-size:11px;line-height:15px;font-weight:500;letter-spacing:0;text-transform:none;color:rgba(15,23,42,.42);cursor:default;user-select:none;}' '.sk5-root .ue-groupName{margin:0 2px 6px;font-size:13px;line-height:18px;font-weight:600;letter-spacing:0;text-transform:none;color:rgba(15,23,42,.58);cursor:default;user-select:none;}' "group-name"

Rep '.sk5-root .ue-group{margin-top:12px;}' '.sk5-root .ue-group{margin-top:16px;}
.sk5-root .ue-group:first-child{margin-top:2px;}' "group-gap"

Rep '.sk5-root .ue-modelsTitle + .ue-group{margin-top:2px;}' '' "remove-first-gap"

# 3) 列表顶部内边距（标题删除后紧贴头部）
Rep '.sk5-root .ue-models{margin:2px -2px 0;padding:0 2px 4px;' '.sk5-root .ue-models{margin:2px -2px 0;padding:4px 2px 4px;' "models-padding"

# 4) 清理不再使用的标题样式
Rep '.sk5-root .ue-modelsTitle{margin:4px 2px 8px;font-size:11px;line-height:14px;font-weight:500;letter-spacing:.02em;color:rgba(15,23,42,.45);}' '' "remove-title-css"

[System.IO.File]::WriteAllText($f, $t, (New-Object System.Text.UTF8Encoding($false)))
Write-Output ("written size=" + (Get-Item $f).Length + " important=" + ([regex]::Matches($t, '!important')).Count)
