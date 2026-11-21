param(
    [string]$Path = "",
    [string]$LangTag = "zh-Hans-CN",
    [switch]$Worker
)
# Windows.Media.Ocr 识别 PNG，输出一行 JSON：
# { ok, engine, lang, requested_lang, lines:[{text, words:[{text,x,y,w,h}]}] }
# 支持单次模式（-Path）与常驻 STA worker 模式（-Worker，stdin/stdout newline-JSON）。
# WGC 按需加载；调用方拥有并清理临时图片。
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ProgressPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Foundation, ContentType=WindowsRuntime]

$script:AsTaskMethod = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]
$script:AsTaskCache = @{}
$script:EngineCache = @{}

function Await($WinRtTask, $ResultType) {
    $typeKey = $ResultType.FullName
    $generic = $script:AsTaskCache[$typeKey]
    if ($null -eq $generic) {
        $generic = $script:AsTaskMethod.MakeGenericMethod($ResultType)
        $script:AsTaskCache[$typeKey] = $generic
    }
    $netTask = $generic.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}

function Get-OcrEngine([string]$Tag) {
    if ($script:EngineCache.ContainsKey($Tag)) {
        return $script:EngineCache[$Tag]
    }
    $engine = $null
    try {
        $language = [Windows.Globalization.Language]::new($Tag)
        if ([Windows.Media.Ocr.OcrEngine]::IsLanguageSupported($language)) {
            $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($language)
        }
    } catch {}
    if ($null -eq $engine) {
        $available = [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages
        if ($available.Count -gt 0) {
            $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($available[0])
        }
    }
    if ($null -ne $engine) {
        $script:EngineCache[$Tag] = $engine
    }
    return $engine
}

function Invoke-OcrFile([string]$ImagePath, [string]$Tag) {
    $stream = $null
    $bitmap = $null
    try {
        if ([string]::IsNullOrWhiteSpace($ImagePath)) {
            return (@{ ok = $false; error = "invalid_path"; message = "缺少图片路径。" } | ConvertTo-Json -Compress)
        }
        $engine = Get-OcrEngine $Tag
        if ($null -eq $engine) {
            return (@{ ok = $false; error = "ocr_unavailable"; message = "Windows OCR 没有可用的识别语言包。" } | ConvertTo-Json -Compress)
        }

        $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($ImagePath)) ([Windows.Storage.StorageFile])
        $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
        $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])

        $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
        $lines = [System.Collections.Generic.List[object]]::new()
        foreach ($line in $result.Lines) {
            $words = [System.Collections.Generic.List[object]]::new()
            foreach ($word in $line.Words) {
                $words.Add(@{
                    text = $word.Text
                    x = [int][Math]::Round($word.BoundingRect.X)
                    y = [int][Math]::Round($word.BoundingRect.Y)
                    w = [int][Math]::Round($word.BoundingRect.Width)
                    h = [int][Math]::Round($word.BoundingRect.Height)
                })
            }
            $lines.Add(@{ text = $line.Text; words = $words })
        }
        return (@{
            ok = $true
            engine = "windows-ocr"
            lang = $engine.RecognizerLanguage.LanguageTag
            requested_lang = $Tag
            lines = $lines
        } | ConvertTo-Json -Compress -Depth 8)
    } catch {
        return (@{ ok = $false; error = "ocr_failed"; message = $_.Exception.Message } | ConvertTo-Json -Compress)
    } finally {
        if ($null -ne $bitmap) { try { $bitmap.Dispose() } catch {} }
        if ($null -ne $stream) { try { $stream.Dispose() } catch {} }
    }
}

function Invoke-WindowCapture($Request) {
    if ($null -eq $script:WindowCaptureType) {
        # Use the OS WinRT metadata and .NET Framework compiler; no SDK is required.
        $options = New-Object System.CodeDom.Compiler.CompilerParameters
        $options.GenerateInMemory = $true
        $options.ReferencedAssemblies.Add('System.dll') | Out-Null
        $options.ReferencedAssemblies.Add([System.WindowsRuntimeSystemExtensions].Assembly.Location) | Out-Null
        foreach ($name in ('System.Runtime', 'System.Runtime.InteropServices.WindowsRuntime')) {
            $assembly = [Reflection.Assembly]::Load("$name, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b03f5f7f11d50a3a")
            $options.ReferencedAssemblies.Add($assembly.Location) | Out-Null
        }
        foreach ($name in ('Windows.Foundation', 'Windows.Graphics', 'Windows.Storage')) {
            $options.ReferencedAssemblies.Add("$env:SystemRoot\System32\WinMetadata\$name.winmd") | Out-Null
        }
        $compiler = New-Object Microsoft.CSharp.CSharpCodeProvider
        try {
            $build = $compiler.CompileAssemblyFromFile($options, (Join-Path $PSScriptRoot 'wgc.cs'))
            if ($build.Errors.HasErrors) { throw ($build.Errors -join ' ') }
            $script:WindowCaptureType = $build.CompiledAssembly.GetType('JuziWindowCapture', $true)
        } finally {
            $compiler.Dispose()
        }
    }
    $script:WindowCaptureType::SavePng([long]$Request.hwnd, [int]$Request.frame_width, [int]$Request.frame_height,
        [int]$Request.x, [int]$Request.y, [int]$Request.width, [int]$Request.height, [string]$Request.path)
    return '{"ok":true}'
}

if ($Worker) {
    while ($null -ne ($line = [Console]::ReadLine())) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        try {
            $req = $line | ConvertFrom-Json
            if ($req.operation -eq 'capture_window') {
                $out = Invoke-WindowCapture $req
            } else {
                $tag = if ($req.lang_tag) { [string]$req.lang_tag } else { "zh-Hans-CN" }
                $out = Invoke-OcrFile ([string]$req.path) $tag
            }
        } catch {
            $out = (@{ ok = $false; error = "ocr_failed"; message = $_.Exception.Message } | ConvertTo-Json -Compress)
        }
        [Console]::WriteLine($out)
        [Console]::Out.Flush()
    }
    exit 0
}

[Console]::WriteLine((Invoke-OcrFile $Path $LangTag))
exit 0
