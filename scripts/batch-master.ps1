# Batch master WAVs with preset variants for audition
param(
  [Parameter(Mandatory=$true)][string]$InputDir,
  [string]$OutDir,
  [string]$Glob = "*.wav",
  [switch]$OverWrite
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path $InputDir)) { throw "InputDir not found: $InputDir" }
if (-not $OutDir) { $OutDir = Join-Path $InputDir "_masters" }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# Variant presets: Clean, Airy, Aggressive (tweak as needed)
$variants = @(
  @{ name = 'Clean';      lufs=-12.0; tp=-1.0; nr=12; nf=-30; deF=0.27; deS=1.0; hp=30; lp=18000; pres=1.5; comp='threshold=-18dB:ratio=2.5:attack=25:release=250:makeup=4' },
  @{ name = 'Airy';       lufs=-10.0; tp=-1.0; nr=12; nf=-30; deF=0.27; deS=1.3; hp=30; lp=19000; pres=2.0; comp='threshold=-17dB:ratio=2.8:attack=20:release=220:makeup=5' },
  @{ name = 'Aggressive'; lufs= -8.0; tp=-1.0; nr=16; nf=-32; deF=0.27; deS=1.2; hp=30; lp=17000; pres=3.0; comp='threshold=-20dB:ratio=4:attack=10:release=150:makeup=8' }
)

Get-ChildItem -Path $InputDir -Recurse -File -Filter $Glob | ForEach-Object {
  $src = $_.FullName
  $base = [IO.Path]::GetFileNameWithoutExtension($src)
  foreach ($v in $variants) {
    $dest = Join-Path $OutDir ("${base}_$($v.name).wav")
    if ((-not $OverWrite) -and (Test-Path $dest)) { Write-Host "Skip existing: $dest"; continue }
    Write-Host "Mastering $src -> $dest ($($v.name))"
    powershell -ExecutionPolicy Bypass -File "scripts/master-audio.ps1" `
      -InFile $src -OutFile $dest -TargetLufs $($v.lufs) -TruePeak $($v.tp) `
      -NoiseReduce $($v.nr) -NoiseFloor $($v.nf) -DeEssCenter $($v.deF) -DeEssStrength $($v.deS) `
      -Highpass $($v.hp) -Lowpass $($v.lp) -PresenceGain $($v.pres) -Compressor $($v.comp)
  }
}

Write-Host "Done -> $OutDir"

