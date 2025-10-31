# Master audio with FFmpeg: denoise, de-ess, vocal presence EQ, compression, two-pass loudness, limiter
param(
  [Parameter(Mandatory=$true)][string]$InFile,
  [string]$OutFile,
  [double]$TargetLufs = -9.0,         # Integrated LUFS target
  [double]$TruePeak = -1.0,           # True peak ceiling for loudnorm
  [double]$NoiseReduce = 12,          # afftdn nr (dB)
  [double]$NoiseFloor = -30,          # afftdn nf (dB)
  [double]$DeEssCenter = 0.28,        # deesser center (0..1 -> ~6-7 kHz at 48k)
  [double]$DeEssStrength = 1.0,       # deesser sensitivity (0..2)
  [int]$Highpass = 30,                # Hz (remove sub rumble)
  [int]$Lowpass = 17000,              # Hz (tame extreme hiss)
  [double]$PresenceGain = 2.0,        # dB boost for 3–5 kHz band
  [int]$PresenceLoHz = 3000,
  [int]$PresenceHiHz = 5000,
  [string]$Compressor = 'threshold=-16dB:ratio=3:attack=20:release=200:makeup=6' # acompressor
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path $InFile)) { throw "Input not found: $InFile" }
if (-not $OutFile) {
  $dir = Split-Path -Parent $InFile
  if (-not $dir -or $dir -eq '') { $dir = (Get-Location).Path }
  $name = [IO.Path]::GetFileNameWithoutExtension($InFile)
  $ext = '.wav'
  $base = Join-Path $dir ("${name}_master")
  $i = 0
  do { $OutFile = if ($i -eq 0) { "$base$ext" } else { "${base}_$i$ext" }; $i++ } while (Test-Path $OutFile)
}

# Resolve ffmpeg path
$ff = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($ff) { $ffmpeg = $ff.Source }
if (-not $ffmpeg) {
  $candidate = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages\BtbN.FFmpeg.GPL.Shared.8.0_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-n8.0-16-gd8605a6b55-win64-gpl-shared-8.0\bin\ffmpeg.exe'
  if (Test-Path $candidate) { $ffmpeg = $candidate }
}
if (-not $ffmpeg) { throw 'ffmpeg not found on PATH or WinGet default location' }

# Build base processing chain (without loudnorm):
#  - afftdn (denoise)
#  - deesser (tame sibilance)
#  - highpass + lowpass (rumble/hiss control)
#  - presence EQ boost at 3–5 kHz (vocal presence)
#  - compressor (glue and bring vocals up)
$filters = @()
$filters += "afftdn=nr=${NoiseReduce}:nf=${NoiseFloor}:om=o"
$filters += "deesser=f=${DeEssCenter}:s=${DeEssStrength}"
if ($Highpass -gt 0) { $filters += "highpass=f=${Highpass}" }
if ($Lowpass -gt 0) { $filters += "lowpass=f=${Lowpass}" }
# Presence boost using parametric EQ around 3.8 kHz
$filters += "equalizer=f=3800:t=q:w=1.0:g=${PresenceGain}"
$filters += "acompressor=${Compressor}"
$baseChain = ($filters -join ',')

# First pass loudness analysis across the full chain
$af1 = "$baseChain,loudnorm=I=${TargetLufs}:TP=${TruePeak}:LRA=11:print_format=json"

Write-Host "[1/2] Analyzing loudness (two-pass loudnorm)..."
$__oldEAP = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
$analysis = & $ffmpeg -hide_banner -nostats -y -i $InFile -af $af1 -f null NUL 2>&1 | Out-String
$ErrorActionPreference = $__oldEAP

# Extract JSON block
$start = $analysis.IndexOf('{')
$end = $analysis.LastIndexOf('}')
if ($start -lt 0 -or $end -le $start) {
  Write-Warning "Could not parse loudnorm analysis; falling back to single-pass."
  $af_fallback = "$baseChain,loudnorm=I=${TargetLufs}:TP=${TruePeak}:LRA=11,alimiter=limit=0.98"
  & $ffmpeg -hide_banner -y -i $InFile -af $af_fallback -c:a pcm_s24le $OutFile
  Write-Host "Wrote: $OutFile"
  exit 0
}

$jsonText = $analysis.Substring($start, $end - $start + 1)
$ln = $null
try {
  $ln = $jsonText | ConvertFrom-Json
} catch {
  Write-Warning "JSON parse failed; using single-pass loudnorm."
  $af_fallback = "$baseChain,loudnorm=I=${TargetLufs}:TP=${TruePeak}:LRA=11,alimiter=limit=0.98"
  & $ffmpeg -hide_banner -y -i $InFile -af $af_fallback -c:a pcm_s24le $OutFile
  Write-Host "Wrote: $OutFile"
  exit 0
}

$measured_I = $ln.input_i
$measured_TP = $ln.input_tp
$measured_LRA = $ln.input_lra
$measured_thresh = $ln.input_thresh
$offset = $ln.target_offset

# Second pass: apply measured values for accurate normalization, then hard ceiling
$loudnorm2 = "loudnorm=I=${TargetLufs}:TP=${TruePeak}:LRA=11:measured_I=${measured_I}:measured_TP=${measured_TP}:measured_LRA=${measured_LRA}:measured_thresh=${measured_thresh}:offset=${offset}:linear=true:print_format=summary"
$af2 = "$baseChain,$loudnorm2,alimiter=limit=0.98"

Write-Host "[2/2] Rendering mastered output -> $OutFile"
$__oldEAP2 = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& $ffmpeg -hide_banner -y -i $InFile -af $af2 -c:a pcm_s24le $OutFile
$ErrorActionPreference = $__oldEAP2
Write-Host "Wrote: $OutFile"
