param(
  [Parameter(Mandatory=$true)][string]$Bucket,
  [string]$Prefix = 'audiobot/outputs',
  [Parameter(Mandatory=$true)][string]$OutDir
)

$ErrorActionPreference = 'Stop'
if (-not (Get-Command gsutil -ErrorAction SilentlyContinue)) {
  Write-Error 'gsutil not found. Install Google Cloud SDK and ensure gsutil is on PATH.'
}

if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }
$uri = if ($Prefix) { "gs://$Bucket/$Prefix" } else { "gs://$Bucket" }
Write-Host "Syncing $uri -> $OutDir" -ForegroundColor Cyan
gsutil -m rsync -d -r $uri $OutDir

