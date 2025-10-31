param(
  [string]$Root = '.',
  [string]$OutDir,
  [string[]]$Extensions = @('.wav','.aif','.aiff','.mp3','.flac','.m4a'),
  [switch]$Recurse,
  [double]$NoiseReduce = 12,
  [double]$NoiseFloor = -28,
  [double]$DeEssCenter = 0.25,
  [double]$DeEssStrength = 1.2,
  [int]$Highpass = 70,
  [int]$Lowpass = 18000,
  [double]$Limiter = 0.95,
  [switch]$KeepFloatPCM
)

$ErrorActionPreference = 'Stop'
$rootPath = Resolve-Path $Root
if ($OutDir) {
  $OutDir = Resolve-Path -LiteralPath (New-Item -ItemType Directory -Path $OutDir -Force)
}

$cleanScript = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'clean-audio.ps1'
if (-not (Test-Path $cleanScript)) { throw "Missing dependency: $cleanScript" }

Write-Host "Scanning $rootPath for audio: $($Extensions -join ', ')" -ForegroundColor Cyan
$files = Get-ChildItem -Path $rootPath -File -Include $Extensions -Recurse:$Recurse
if ($files.Count -eq 0) { Write-Warning 'No matching files found.'; exit 0 }

foreach ($f in $files) {
  $in = $f.FullName
  if ($OutDir) {
    $rel = Resolve-Path -LiteralPath $f.DirectoryName | ForEach-Object { $_.Path.Substring($rootPath.Path.Length).TrimStart('\\','/') }
    $targetDir = Join-Path $OutDir $rel
    if (-not (Test-Path $targetDir)) { New-Item -ItemType Directory -Path $targetDir | Out-Null }
    $name = [IO.Path]::GetFileNameWithoutExtension($f.Name)
    $out = Join-Path $targetDir ("${name}_clean.wav")
  } else {
    $out = Join-Path $f.DirectoryName (([IO.Path]::GetFileNameWithoutExtension($f.Name)) + '_clean.wav')
  }

  if (Test-Path $out) {
    Write-Host "Skip (exists): $out" -ForegroundColor Yellow
    continue
  }

  Write-Host "Cleaning: $in -> $out" -ForegroundColor Green
  & powershell -NoProfile -ExecutionPolicy Bypass -File $cleanScript -Input $in -Output $out `
    -NoiseReduce $NoiseReduce -NoiseFloor $NoiseFloor -DeEssCenter $DeEssCenter -DeEssStrength $DeEssStrength `
    -Highpass $Highpass -Lowpass $Lowpass -Limiter $Limiter -KeepFloatPCM:$KeepFloatPCM
}

Write-Host 'Batch complete.' -ForegroundColor Cyan

