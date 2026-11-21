param(
    [string]$BundleRoot = '',
    [string]$InteractiveUser = '',
    [int]$IdleTimeout = 900
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)

function Get-DesktopTarget {
    $desktops = @((& $python (Join-Path $PSScriptRoot 'desktop_session.py') | ConvertFrom-Json) | Where-Object { $_ })
    if ($LASTEXITCODE -ne 0) { throw 'Cannot enumerate active desktop sessions' }
    if ($InteractiveUser) {
        $wanted = [Security.Principal.NTAccount]::new($InteractiveUser).Translate([Security.Principal.SecurityIdentifier])
        $desktops = @($desktops | Where-Object {
            [Security.Principal.NTAccount]::new($_.account).Translate([Security.Principal.SecurityIdentifier]).Equals($wanted)
        })
    }
    if ($desktops.Count -gt 1) { $desktops = @($desktops | Where-Object console) }
    if ($desktops.Count -ne 1) { throw 'No unambiguous active desktop for the requested user' }
    return $desktops[0]
}

function Get-LiveState {
    if (-not [IO.File]::Exists($stateFile)) { return }
    $st = [IO.File]::ReadAllText($stateFile) | ConvertFrom-Json
    if ($st.session_id -ne $desktop.id -or $st.confirm_mode -ne $mode -or $st.allowlist -cne $allow) { return }
    $p = Get-CimInstance Win32_Process -Filter ("ProcessId=" + [int]$st.pid)
    if (-not $p -or $p.SessionId -ne $desktop.id -or $p.ExecutablePath -ine $pythonw) { return }
    $owner = Invoke-CimMethod -InputObject $p -MethodName GetOwnerSid
    if ($owner.ReturnValue -ne 0 -or $owner.Sid -ne $sid.Value) { return }
    $listener = Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort ([int]$st.port) -State Listen -ErrorAction SilentlyContinue
    if ($listener.OwningProcess -eq $p.ProcessId) { return $st }
}

$appDir = Split-Path -Parent $PSScriptRoot
if (-not $BundleRoot) {
    $BundleRoot = if ((Split-Path -Leaf $appDir) -eq 'app') { Split-Path -Parent $appDir } else { $appDir }
}
$python = Join-Path $BundleRoot 'python\python.exe'
if ([IO.Path]::GetFullPath($BundleRoot) -eq $appDir -and (Test-Path -LiteralPath (Join-Path $appDir 'src\core_server.py'))) {
    # Direct invocation from the source checkout uses the developer's interpreter.
    $python = (Get-Command python.exe -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
}
$pythonw = Join-Path (Split-Path -Parent $python) 'pythonw.exe'
if (-not [IO.File]::Exists($pythonw)) { $pythonw = $python }
$daemon = Join-Path $PSScriptRoot 'session1_daemon.py'
$server = Join-Path $appDir 'server.py'
$desktop = Get-DesktopTarget
$sid = [Security.Principal.NTAccount]::new($desktop.account).Translate([Security.Principal.SecurityIdentifier])
$profileDir = (Get-ItemProperty -LiteralPath ("HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\" + $sid.Value)).ProfileImagePath
$mode = [Environment]::GetEnvironmentVariable('JUZI_WIN_DSH_CONFIRM_MODE', 'Machine')
if ($mode -notin @('always', 'allowlist', 'off')) { $mode = 'always' }
$allow = [string][Environment]::GetEnvironmentVariable('JUZI_WIN_DSH_ALLOWLIST', 'Machine')
if ($allow -match '["\\/\x00-\x1f]') { throw 'Invalid process allowlist' }

# Partition by the immutable bundle, desktop identity, session and host policy.
$key = [Text.Encoding]::UTF8.GetBytes([IO.Path]::GetFullPath($BundleRoot).ToUpperInvariant() + '|' + $mode + '|' + $allow)
$digest = [BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash($key)).Replace('-', '')
$runtimeDir = Join-Path ([Environment]::ExpandEnvironmentVariables($profileDir)) ("JuziWinDSH-State-" + $desktop.id + '-' + $digest)
& (Join-Path $PSScriptRoot 'private_state.ps1') -Directory $runtimeDir -UserSid $sid.Value
$stateFile = Join-Path $runtimeDir 'daemon_state.json'
$lockPath = Join-Path $runtimeDir 'bootstrap.lock'
$deadline = [DateTime]::UtcNow.AddSeconds(15)
while ($true) {
    try { $lock = [IO.File]::Open($lockPath, 'OpenOrCreate', 'ReadWrite', 'None'); break }
    catch [IO.IOException] {
        if ([DateTime]::UtcNow -ge $deadline) { throw }
        Start-Sleep -Milliseconds 150
    }
}

try {
    $state = Get-LiveState
    $reused = [bool]$state
    if (-not $reused) {
        $task = 'JuziWinMCP_' + [Guid]::NewGuid().ToString('N')
        $argsLine = '"{0}" --server-py "{1}" --state-file "{2}" --idle-timeout {3} --expected-session {4} --confirm-mode {5}' -f $daemon,$server,$stateFile,$IdleTimeout,$desktop.id,$mode
        if ($allow) { $argsLine += ' --allowlist "' + $allow + '"' }
        $action = New-ScheduledTaskAction -Execute $pythonw -Argument $argsLine
        $principal = New-ScheduledTaskPrincipal -UserId $desktop.account -LogonType Interactive -RunLevel Limited
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 4)
        Register-ScheduledTask -TaskName $task -Action $action -Principal $principal -Settings $settings | Out-Null
        try {
            $scheduler = New-Object -ComObject Schedule.Service
            $scheduler.Connect()
            # TASK_RUN_USE_SESSION_ID binds the launch to the selected logon session.
            $scheduler.GetFolder('\').GetTask($task).RunEx($null, 4, [int]$desktop.id, $null) | Out-Null
            $deadline = [DateTime]::UtcNow.AddSeconds(12)
            do {
                Start-Sleep -Milliseconds 250
                $state = Get-LiveState
            } until ($state -or [DateTime]::UtcNow -ge $deadline)
            if (-not $state) { throw 'Desktop daemon did not become ready in the selected session' }
        } finally {
            Unregister-ScheduledTask -TaskName $task -Confirm:$false
        }
    }
    $current = Get-DesktopTarget
    if ($current.id -ne $desktop.id -or $current.account -ine $desktop.account) { throw 'Desktop changed during bootstrap' }
    @{ok=$true; port=[int]$state.port; token=$state.token; pid=[int]$state.pid; reused=$reused} | ConvertTo-Json -Compress
} finally {
    $lock.Dispose()
}
