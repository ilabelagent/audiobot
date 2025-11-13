# Inspect basic audio properties using ffprobe/ffmpeg
param(
  [Parameter(Mandatory=$true)][string]$Input
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path $Input)) { throw "Input not found: $Input" }

$ffprobe = (Get-Command ffprobe -ErrorAction SilentlyContinue)?.Source
if (-not $ffprobe) {
  $candidate = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages\BtbN.FFmpeg.GPL.Shared.8.0_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-n8.0-16-gd8605a6b55-win64-gpl-shared-8.0\bin\ffprobe.exe'
  if (Test-Path $candidate) { $ffprobe = $candidate }
}
if (-not $ffprobe) { throw 'ffprobe not found on PATH or WinGet default location' }

& $ffprobe -hide_banner -v error -show_entries stream=index,codec_name,codec_type,channels,sample_rate,bit_rate -show_format -of json $Input

Write-Host "\nPeak/RMS (quick scan):" -ForegroundColor Cyan
$ffmpeg = (Get-Command ffmpeg -ErrorAction SilentlyContinue)?.Source
if (-not $ffmpeg) {
  $candidate = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages\BtbN.FFmpeg.GPL.Shared.8.0_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-n8.0-16-gd8605a6b55-win64-gpl-shared-8.0\bin\ffmpeg.exe'
  if (Test-Path $candidate) { $ffmpeg = $candidate }
}
if ($ffmpeg) {
  & $ffmpeg -hide_banner -i $Input -af "astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:mode=print" -f null - 2>&1 | Select-String -Pattern 'RMS_level' | Select-Object -First 1
  & $ffmpeg -hide_banner -i $Input -af "astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.Peak_level:mode=print" -f null - 2>&1 | Select-String -Pattern 'Peak_level' | Select-Object -First 1
} else {
  Write-Warning 'ffmpeg not available for astats; skipped peak/RMS'
}

