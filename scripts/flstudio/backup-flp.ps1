param(
  [Parameter(Mandatory = $true)]
  [string]$ProjectPath,

  [Parameter(Mandatory = $false)]
  [string]$Message = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Ensure-Dir {
  param([string]$Path)
  if (-not (Test-Path -LiteralPath $Path)) {
    New-Item -ItemType Directory -Path $Path | Out-Null
  }
}

function Get-Hash256 {
  param([string]$File)
  (Get-FileHash -Algorithm SHA256 -LiteralPath $File).Hash
}

$proj = Resolve-Path -LiteralPath $ProjectPath
$flpDir = Join-Path $proj 'flp'
$backupRoot = Join-Path $proj 'backups/flp_history'
$logDir = Join-Path $proj 'backups/logs'
$logFile = Join-Path $logDir 'backup_log.md'

if (-not (Test-Path -LiteralPath $flpDir)) {
  throw "Missing flp directory: $flpDir"
}

Ensure-Dir $backupRoot
Ensure-Dir $logDir

$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$flps = Get-ChildItem -LiteralPath $flpDir -Filter *.flp -File -ErrorAction SilentlyContinue | Sort-Object Name

if (-not $flps -or $flps.Count -eq 0) {
  Write-Host "No .flp files found in $flpDir" -ForegroundColor Yellow
  exit 0
}

$logEntries = @()

foreach ($f in $flps) {
  $nameNoExt = [System.IO.Path]::GetFileNameWithoutExtension($f.Name)
  $destDir = Join-Path $backupRoot $nameNoExt
  Ensure-Dir $destDir

  $slug = if ([string]::IsNullOrWhiteSpace($Message)) { 'backup' } else { $Message -replace '[^a-zA-Z0-9_-]','-' }
  $destName = "${timestamp}_${slug}.flp"
  $dest = Join-Path $destDir $destName

  Copy-Item -LiteralPath $f.FullName -Destination $dest -Force

  $srcHash = Get-Hash256 -File $f.FullName
  $dstHash = Get-Hash256 -File $dest

  $logEntries += "- $($f.Name) → backups/flp_history/$nameNoExt/$destName (src:$srcHash dst:$dstHash)"
}

$humanTime = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
$header = "`n### $humanTime — $($Message)"
Add-Content -LiteralPath $logFile -Value $header
foreach ($entry in $logEntries) { Add-Content -LiteralPath $logFile -Value $entry }

Write-Host "Backed up $($flps.Count) .flp file(s) with tag '$Message'" -ForegroundColor Green

