param([string]$RequestJson = '{}')

# 由 server.py 调用；stdout 只输出一行 JSON。
$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$result = [ordered]@{
    ok = $true
    brightness = $null
    volume = $null
    mute = $null
    locked = $false
    errors = @()
}

function Add-ResultError([string]$Message) {
    $script:result.errors += $Message
    $script:result.ok = $false
}

try {
    $req = $RequestJson | ConvertFrom-Json
} catch {
    $result.ok = $false
    $result.errors += "请求 JSON 无效：$($_.Exception.Message)"
    $result | ConvertTo-Json -Compress
    exit 1
}

function Get-CurrentBrightness {
    try {
        $monitor = Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness -ErrorAction Stop |
            Select-Object -First 1
        if ($null -ne $monitor) { return [int]$monitor.CurrentBrightness }
    } catch {
        return $null
    }
    return $null
}

# ---- 亮度 ----
$result.brightness = Get-CurrentBrightness
if ($null -ne $req.brightness) {
    $target = [int]$req.brightness
    if ($target -lt 0 -or $target -gt 100) {
        Add-ResultError "亮度必须在 0~100 之间。"
    } else {
        try {
            $methods = @(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods -ErrorAction Stop)
            if ($methods.Count -eq 0) {
                Add-ResultError "未找到支持亮度控制的显示器。"
            } else {
                foreach ($method in $methods) {
                    $null = Invoke-CimMethod -InputObject $method -MethodName WmiSetBrightness -Arguments @{
                        Timeout = [uint32]1
                        Brightness = [byte]$target
                    }
                }
                Start-Sleep -Milliseconds 250
                $result.brightness = Get-CurrentBrightness
            }
        } catch {
            Add-ResultError "设置亮度失败：$($_.Exception.Message)"
        }
    }
}

# ---- 音量 / 静音（Core Audio） ----
$audioCode = @'
using System;
using System.Runtime.InteropServices;

[ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
public class MMDeviceEnumeratorComObject { }

[Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IMMDeviceEnumerator {
    int NotImpl1();
    int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice ppDevice);
}

[Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IMMDevice {
    int Activate(ref Guid iid, int dwClsCtx, IntPtr pActivationParams, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface);
}

[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IAudioEndpointVolume {
    int NotImpl1();
    int NotImpl2();
    int GetChannelCount(out int pnChannelCount);
    int SetMasterVolumeLevel(float fLevelDB, Guid pguidEventContext);
    int SetMasterVolumeLevelScalar(float fLevel, Guid pguidEventContext);
    int GetMasterVolumeLevel(out float pfLevelDB);
    int GetMasterVolumeLevelScalar(out float pfLevel);
    int SetChannelVolumeLevel(uint nChannel, float fLevelDB, Guid pguidEventContext);
    int SetChannelVolumeLevelScalar(uint nChannel, float fLevel, Guid pguidEventContext);
    int GetChannelVolumeLevel(uint nChannel, out float pfLevelDB);
    int GetChannelVolumeLevelScalar(uint nChannel, out float pfLevel);
    int SetMute([MarshalAs(UnmanagedType.Bool)] bool bMute, Guid pguidEventContext);
    int GetMute(out bool pbMute);
}

public static class JuziAudio {
    public static IAudioEndpointVolume Get() {
        var enumerator = (IMMDeviceEnumerator)(new MMDeviceEnumeratorComObject());
        IMMDevice device;
        int hr = enumerator.GetDefaultAudioEndpoint(0, 1, out device);
        if (hr != 0) Marshal.ThrowExceptionForHR(hr);
        Guid iid = typeof(IAudioEndpointVolume).GUID;
        object volume;
        hr = device.Activate(ref iid, 1, IntPtr.Zero, out volume);
        if (hr != 0) Marshal.ThrowExceptionForHR(hr);
        return (IAudioEndpointVolume)volume;
    }

    public static float GetVolume() {
        float value;
        int hr = Get().GetMasterVolumeLevelScalar(out value);
        if (hr != 0) Marshal.ThrowExceptionForHR(hr);
        return value;
    }

    public static void SetVolume(float value) {
        int hr = Get().SetMasterVolumeLevelScalar(value, Guid.Empty);
        if (hr != 0) Marshal.ThrowExceptionForHR(hr);
    }

    public static bool GetMute() {
        bool value;
        int hr = Get().GetMute(out value);
        if (hr != 0) Marshal.ThrowExceptionForHR(hr);
        return value;
    }

    public static void SetMute(bool value) {
        int hr = Get().SetMute(value, Guid.Empty);
        if (hr != 0) Marshal.ThrowExceptionForHR(hr);
    }
}
'@

try {
    if (-not ('JuziAudio' -as [type])) {
        Add-Type -TypeDefinition $audioCode -Language CSharp
    }
    $result.volume = [int][math]::Round([JuziAudio]::GetVolume() * 100)
    $result.mute = [bool][JuziAudio]::GetMute()

    if ($null -ne $req.volume) {
        $volume = [int]$req.volume
        if ($volume -lt 0 -or $volume -gt 100) {
            Add-ResultError "音量必须在 0~100 之间。"
        } else {
            [JuziAudio]::SetVolume([float]($volume / 100.0))
            Start-Sleep -Milliseconds 100
            $result.volume = [int][math]::Round([JuziAudio]::GetVolume() * 100)
        }
    }
    if ($null -ne $req.mute) {
        [JuziAudio]::SetMute([bool]$req.mute)
        Start-Sleep -Milliseconds 100
        $result.mute = [bool][JuziAudio]::GetMute()
    }
} catch {
    Add-ResultError "音量控制失败：$($_.Exception.Message)"
}

# ---- 锁屏 ----
if ($req.lock -eq $true) {
    try {
        Start-Process -FilePath "$env:SystemRoot\System32\rundll32.exe" -ArgumentList 'user32.dll,LockWorkStation' -WindowStyle Hidden
        $result.locked = $true
    } catch {
        Add-ResultError "锁屏失败：$($_.Exception.Message)"
    }
}

$result | ConvertTo-Json -Compress
