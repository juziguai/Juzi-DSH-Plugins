param(
    [string]$ExpectedHwnd = "0"
)
# 从 stdin 读取文本（避免 Windows argv 上限），备份剪贴板后粘贴，再按序列号事务恢复。
# stdout 只输出一行 JSON。
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Windows.Forms
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class JuziClipboardNative {
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern uint GetClipboardSequenceNumber();
}
'@

$text = [Console]::In.ReadToEnd()
$expected = 0
if ($ExpectedHwnd -match '^\d+$') {
    $expected = [int64]$ExpectedHwnd
}

function Emit([hashtable]$payload) {
    $payload | ConvertTo-Json -Compress
}

if ([string]::IsNullOrEmpty($text)) {
    Emit @{ ok = $false; error = "invalid_text"; paste_ok = $false; restore_ok = $false }
    exit 0
}

# 1) 快照所有可读取格式；无法可靠读取则不写入。
$backupData = @{}
$backupStatus = "empty"
$source = $null
$sourceRead = $false
for ($i = 0; $i -lt 5; $i++) {
    try {
        $source = [System.Windows.Forms.Clipboard]::GetDataObject()
        $sourceRead = $true
        break
    } catch {
        Start-Sleep -Milliseconds 80
    }
}
if (-not $sourceRead) {
    Emit @{ ok = $false; error = "clipboard_backup_failed"; paste_ok = $false; restore_ok = $false; backup_status = "failed" }
    exit 0
}
if ($null -ne $source) {
    try {
        $formats = @($source.GetFormats($false))
    } catch {
        $backupStatus = "failed"
        $formats = @()
    }
    if ($formats.Count -gt 0) {
        $backupStatus = "success"
        foreach ($format in $formats) {
            try {
                $backupData[$format] = $source.GetData($format, $false)
            } catch {
                $backupStatus = "failed"
                break
            }
        }
    }
}
if ($backupStatus -eq "failed") {
    Emit @{ ok = $false; error = "clipboard_backup_failed"; paste_ok = $false; restore_ok = $false; backup_status = "failed" }
    exit 0
}

$seqBefore = [JuziClipboardNative]::GetClipboardSequenceNumber()

# 2) 写入待粘贴文本（仅在快照成功后）。
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
    Emit @{ ok = $false; error = "clipboard_set_failed"; paste_ok = $false; restore_ok = $false; backup_status = $backupStatus }
    exit 0
}
$ownedSeq = [JuziClipboardNative]::GetClipboardSequenceNumber()

# 3) 派发前再次核对前台窗口；变化则不粘贴并恢复快照。
$targetChanged = $false
if ($expected -gt 0 -and [int64][JuziClipboardNative]::GetForegroundWindow() -ne $expected) {
    $targetChanged = $true
}

$pasteOk = $false
if (-not $targetChanged) {
    Start-Sleep -Milliseconds 120
    try {
        [System.Windows.Forms.SendKeys]::SendWait('^v')
        Start-Sleep -Milliseconds 500
        $pasteOk = $true
    } catch {
        $pasteOk = $false
    }
}

# 4) 恢复：若外部已产生新内容（序列号变化）则保留新内容并报告冲突。
$restoreOk = $false
$restoreConflict = $false
$restoreError = $null
$currentSeq = [JuziClipboardNative]::GetClipboardSequenceNumber()
if ($currentSeq -ne $ownedSeq) {
    $restoreConflict = $true
} else {
    try {
        if ($backupData.Count -gt 0) {
            $restore = New-Object System.Windows.Forms.DataObject
            foreach ($format in $backupData.Keys) {
                $restore.SetData($format, $backupData[$format])
            }
            [System.Windows.Forms.Clipboard]::SetDataObject($restore, $true)
        } else {
            [System.Windows.Forms.Clipboard]::Clear()
        }
        $restoreOk = $true
    } catch {
        $restoreError = $_.Exception.Message
    }
}

Emit @{
    ok = ($pasteOk -and -not $targetChanged)
    paste_ok = $pasteOk
    restore_ok = $restoreOk
    restore_conflict = $restoreConflict
    backup_status = $backupStatus
    target_changed = $targetChanged
    chars = $text.Length
    restore_error = $restoreError
}
