param(
  [Parameter(Mandatory=$true)][string]$Input,
  [string]$OutDir = './stems',
  [string]$Model = 'htdemucs',
  [int]$Stems = 4,
  [ValidateSet('vocals','drums','bass','other')][string]$TwoStemsTarget = 'vocals'
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path $Input)) { throw "Input not found: $Input" }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$conda = 'C:\Users\Admin\miniconda3\condabin\conda.bat'
if (-not (Test-Path $conda)) { throw "Miniconda not found at $conda" }

$argsList = @('run','-n','audio','demucs','-n', $Model, '-o', (Resolve-Path $OutDir))
if ($Stems -eq 2) { $argsList += @('--two-stems', $TwoStemsTarget) }
$argsList += ,(Resolve-Path $Input)

& $conda $argsList
Write-Host 'Done.'

