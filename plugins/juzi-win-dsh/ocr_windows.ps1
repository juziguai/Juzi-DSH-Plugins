param(
    [Parameter(Mandatory = $true)][string]$Path,
    [string]$LangTag = "zh-Hans-CN"
)
# Windows.Media.Ocr 识别单张 PNG，输出一行 JSON：
# { ok, engine, lang, requested_lang, lines:[{text, words:[{text,x,y,w,h}]}] }
# 只做 OCR，不落盘、不写日志；调用方负责删除传入的临时图片。
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ProgressPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Foundation, ContentType=WindowsRuntime]

function Await($WinRtTask, $ResultType) {
    $asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    })[0]
    $netTask = $asTask.MakeGenericMethod($ResultType).Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}

try {
    $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($Path)) ([Windows.Storage.StorageFile])
    $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])

    $engine = $null
    $language = [Windows.Globalization.Language]::new($LangTag)
    if ([Windows.Media.Ocr.OcrEngine]::IsLanguageSupported($language)) {
        $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($language)
    }
    if ($null -eq $engine) {
        $available = [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages
        if ($available.Count -gt 0) {
            $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($available[0])
        }
    }
    if ($null -eq $engine) {
        @{ ok = $false; error = "ocr_unavailable"; message = "Windows OCR 没有可用的识别语言包。" } | ConvertTo-Json -Compress
        exit 0
    }

    $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    $lines = @()
    foreach ($line in $result.Lines) {
        $words = @()
        foreach ($word in $line.Words) {
            $words += [pscustomobject]@{
                text = $word.Text
                x = [int][Math]::Round($word.BoundingRect.X)
                y = [int][Math]::Round($word.BoundingRect.Y)
                w = [int][Math]::Round($word.BoundingRect.Width)
                h = [int][Math]::Round($word.BoundingRect.Height)
            }
        }
        $lines += [pscustomobject]@{ text = $line.Text; words = $words }
    }
    @{
        ok = $true
        engine = "windows-ocr"
        lang = $engine.RecognizerLanguage.LanguageTag
        requested_lang = $LangTag
        lines = $lines
    } | ConvertTo-Json -Compress -Depth 8
} catch {
    @{ ok = $false; error = "ocr_failed"; message = $_.Exception.Message } | ConvertTo-Json -Compress
    exit 0
}
