# update-versions.ps1
# Regenerate lib/client.js from the official DeepSeek pricing page.
#
# Source of truth:
#   https://api-docs.deepseek.com/zh-cn/quick_start/pricing
#   -> 表格「模型」列 = 调用名(id)，「模型版本」行 = 官方完整快照名(含 MMDD)
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\build\update-versions.ps1
#   powershell ... -File .\build\update-versions.ps1 -SourceUrl <url> -Proxy http://127.0.0.1:8889
#
# The script writes lib/client.js (template + generated VERSIONS map).
# It never touches cordis.patch.yml.

param(
  [string]$SourceUrl = 'https://api-docs.deepseek.com/zh-cn/quick_start/pricing',
  [string]$Proxy = '',
  [string]$PackageRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'

# --- 1. fetch -----------------------------------------------------------------
$tmp = Join-Path $env:TEMP ('ds-pricing-' + [guid]::NewGuid().ToString('N') + '.html')
$curlArgs = @('-sS', '--max-time', '40', '-L', '-o', $tmp, '-w', '%{http_code}', $SourceUrl)
if ($Proxy) { $curlArgs = @('-sS','--max-time','40','-L','--proxy',$Proxy,'-o',$tmp,'-w','%{http_code}',$SourceUrl) }
$code = & curl.exe @curlArgs
if ($code -ne '200') { throw "pricing page fetch failed: HTTP $code" }
$html = Get-Content $tmp -Raw -Encoding UTF8
Write-Host "fetched $SourceUrl ($($html.Length) chars)"

# --- 2. parse the two table rows ----------------------------------------------
# Strip tags helper: <sup>(1)</sup> and <a> wrappers must not leak into ids.
function Strip-Html([string]$s) {
  # Drop footnote markers wholesale before removing tags: the header cell reads
  # `deepseek-flash<sup>(1)</sup>`, and a plain tag strip would leave "deepseek-flash(1)".
  $s = $s -replace '(?s)<sup>.*?</sup>', ''
  return ($s -replace '<[^>]+>', '').Trim()
}

$idRow  = [regex]::Match($html, '<td colspan="3"[^>]*>\s*模型\s*</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>', 'Singleline')
$verRow = [regex]::Match($html, '<td colspan="3"[^>]*>\s*模型版本\s*</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>', 'Singleline')
if (-not $idRow.Success -or -not $verRow.Success) { throw 'table rows not found; page layout may have changed' }

# NOTE: call the function once per value — `Strip-Html $a, $b` would coerce the
# array into a single string because the parameter is typed [string].
$ids      = @((Strip-Html $idRow.Groups[1].Value), (Strip-Html $idRow.Groups[2].Value))
$versions = @((Strip-Html $verRow.Groups[1].Value), (Strip-Html $verRow.Groups[2].Value))
Write-Host ("ids     = " + ($ids -join ', '))
Write-Host ("versions= " + ($versions -join ', '))

# Keep the official MMDD suffix verbatim as the badge (e.g. "1017", "0813").
# Anything not ending in four digits keeps its full version string.
function Get-Badge([string]$version) {
  $m = [regex]::Match($version, '-(\d{4})$')
  if ($m.Success) { return $m.Groups[1].Value }
  return $version
}

$map = [ordered]@{}
for ($i = 0; $i -lt [Math]::Min($ids.Count, $versions.Count); $i++) {
  $map[$ids[$i]] = [ordered]@{ full = $versions[$i]; badge = (Get-Badge $versions[$i]) }
}

# --- 3. legacy aliases from the footnote --------------------------------------
# Footnote (1) says the old ids are still callable and are served by the same
# snapshot as the first column. Parse the ids, then bind them to that version.
$text = Strip-Html $html
$note = [regex]::Match($text, '旧模型名\s*([^。]+?)\s*仍可调用[^。]*?由\s*(DeepSeek-[A-Za-z0-9.\-]+)\s*模型提供服务')
if ($note.Success) {
  $legacyIds = [regex]::Matches($note.Groups[1].Value, 'deepseek-[a-z0-9.\-]+') | ForEach-Object { $_.Value }
  $servedBy = $note.Groups[2].Value
  foreach ($legacy in $legacyIds) {
    if (-not $map.Contains($legacy)) {
      $map[$legacy] = [ordered]@{ full = $servedBy; badge = (Get-Badge $servedBy); legacy = $true }
      Write-Host "legacy alias: $legacy -> $servedBy"
    }
  }
} else {
  Write-Host 'warning: legacy footnote not parsed (page wording changed?); aliases skipped'
}

# --- 4. render client.js ------------------------------------------------------
$templatePath = Join-Path $PackageRoot 'build\client.template.js'
$outPath      = Join-Path $PackageRoot 'lib\client.js'
$template = Get-Content $templatePath -Raw -Encoding UTF8
if ($template -notmatch '__VERSION_MAP__') { throw 'template placeholder __VERSION_MAP__ missing' }

# ConvertTo-Json keeps the map readable; one key per line for easy diffing.
$json = $map | ConvertTo-Json -Depth 5
$client = $template.Replace('__VERSION_MAP__', $json)
[IO.File]::WriteAllText($outPath, $client, (New-Object Text.UTF8Encoding($false)))

Write-Host "written: $outPath ($($client.Length) chars)"
Write-Host ('entries: ' + $map.Keys.Count + ' -> ' + (($map.Keys) -join ', '))
