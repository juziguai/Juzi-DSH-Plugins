param([string]$TextB64)

# 把文本写入剪贴板并在前台窗口执行 Ctrl+V，然后恢复原剪贴板。
# 使用 STA + WinForms；stdout 只输出一行 JSON。
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Windows.Forms

$text = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($TextB64))

# 先尽量把所有可读取的剪贴板格式快照到内存。
$backupData = @{}
try {
    $source = [System.Windows.Forms.Clipboard]::GetDataObject()
    if ($null -ne $source) {
        foreach ($format in $source.GetFormats($false)) {
            try {
                $backupData[$format] = $source.GetData($format, $false)
            } catch { }
        }
    }
} catch { }

$set = $false
for ($i = 0; $i -lt 5 -and -not $set; $i++) {
    try {
        [System.Windows.Forms.Clipboard]::SetText($text)
        $set = $true
    } catch {
        Start-Sleep -Milliseconds 80
    }
}
if (-not $set) {
    @{ ok = $false; error = "clipboard_set_failed" } | ConvertTo-Json -Compress
    exit 1
}

Start-Sleep -Milliseconds 120
[System.Windows.Forms.SendKeys]::SendWait('^v')
Start-Sleep -Milliseconds 500

$restored = $false
if ($backupData.Count -gt 0) {
    for ($i = 0; $i -lt 5 -and -not $restored; $i++) {
        try {
            $restore = New-Object System.Windows.Forms.DataObject
            foreach ($format in $backupData.Keys) {
                try { $restore.SetData($format, $backupData[$format]) } catch { }
            }
            if ($restore.GetFormats($false).Count -gt 0) {
                [System.Windows.Forms.Clipboard]::SetDataObject($restore, $true)
            } else {
                [System.Windows.Forms.Clipboard]::Clear()
            }
            $restored = $true
        } catch {
            Start-Sleep -Milliseconds 80
        }
    }
} else {
    [System.Windows.Forms.Clipboard]::Clear()
    $restored = $true
}

@{ ok = $true; restored = $restored; chars = $text.Length } | ConvertTo-Json -Compress
