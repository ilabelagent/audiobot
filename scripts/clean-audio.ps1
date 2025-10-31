# Clean audio with FFmpeg: denoise, de-ess, rumble/hiss cuts, limiter
param(
  [Parameter(Mandatory=$true)][string]$Input,
  [string]$Output,
  [double]$NoiseReduce = 12,            # afftdn nr (dB)
  [double]$NoiseFloor = -28,            # afftdn nf (dB)
  [double]$DeEssCenter = 0.25,          # deesser center freq (0..1 normalized to Nyquist)
  [double]$DeEssStrength = 1.2,         # deesser sensitivity (0..2)
  [int]$Highpass = 70,                  # Hz
  [int]$Lowpass = 18000,                # Hz
  [double]$Limiter = 0.95,              # peak ceiling (0..1)
  [switch]$KeepFloatPCM                 # keep float PCM if input is float
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path $Input)) { throw "Input not found: $Input" }
if (-not $Output) {
  $dir = Split-Path -Parent $Input
  $name = [IO.Path]::GetFileNameWithoutExtension($Input)
  $ext = '.wav'
  $base = Join-Path $dir ("${name}_clean")
  $i = 0
  do { $Output = if ($i -eq 0) { "$base$ext" } else { "${base}_$i$ext" }; $i++ } while (Test-Path $Output)
}

# Resolve ffmpeg path (use PATH first, else fallback to WinGet package path)
$ffmpeg = (Get-Command ffmpeg -ErrorAction SilentlyContinue)?.Source
if (-not $ffmpeg) {
  $candidate = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages\BtbN.FFmpeg.GPL.Shared.8.0_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-n8.0-16-gd8605a6b55-win64-gpl-shared-8.0\bin\ffmpeg.exe'
  if (Test-Path $candidate) { $ffmpeg = $candidate }
}
if (-not $ffmpeg) { throw 'ffmpeg not found on PATH or WinGet default location' }

$filters = @()
$filters += "afftdn=nr=${NoiseReduce}:nf=${NoiseFloor}:om=o"
$filters += "deesser=f=${DeEssCenter}:s=${DeEssStrength}"
if ($Highpass -gt 0) { $filters += "highpass=f=${Highpass}" }
if ($Lowpass -gt 0) { $filters += "lowpass=f=${Lowpass}" }
$filters += "alimiter=limit=${Limiter}"
$af = ($filters -join ',')

# Choose codec: preserve float vs convert to 16-bit
$codec = if ($KeepFloatPCM) { 'pcm_f32le' } else { 'pcm_s16le' }

& $ffmpeg -hide_banner -y -i $Input -af $af -c:a $codec $Output
Write-Host "Wrote: $Output"

