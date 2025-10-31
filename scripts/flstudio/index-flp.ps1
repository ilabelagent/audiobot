param(
  [Parameter(Mandatory = $true)]
  [string]$ProjectPath,

  [Parameter(Mandatory = $false)]
  [string]$OutputPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Rel($base, $path) {
  $uri1 = (Resolve-Path -LiteralPath $base).Path
  $uri2 = (Resolve-Path -LiteralPath $path).Path
  $u1 = New-Object System.Uri($uri1 + [System.IO.Path]::DirectorySeparatorChar)
  $u2 = New-Object System.Uri($uri2)
  $u1.MakeRelativeUri($u2).ToString().Replace('/', [System.IO.Path]::DirectorySeparatorChar)
}

function List-Section {
  param(
    [string]$Title,
    [System.Object[]]$Files
  )
  if (-not $Files -or $Files.Count -eq 0) { return "**$Title**\n- (none)\n" }
  $lines = @("**$Title**")
  foreach ($f in $Files | Sort-Object FullName) {
    $sizeMB = [Math]::Round(($f.Length / 1MB), 2)
    $rel = Rel $ProjectPath $f.FullName
    $lines += "- `$($rel)` — $sizeMB MB — $(Get-Date $f.LastWriteTime -Format 'yyyy-MM-dd HH:mm')"
  }
  ($lines -join "`n") + "`n"
}

$proj = Resolve-Path -LiteralPath $ProjectPath
$out = if ($OutputPath) { $OutputPath } else { Join-Path $proj 'INDEX.md' }

if (-not (Test-Path -LiteralPath $proj)) { throw "Project not found: $ProjectPath" }

$flps = Get-ChildItem -LiteralPath (Join-Path $proj 'flp') -Filter *.flp -File -ErrorAction SilentlyContinue
$backups = Get-ChildItem -LiteralPath (Join-Path $proj 'backups/flp_history') -Recurse -Filter *.flp -File -ErrorAction SilentlyContinue
$zips = Get-ChildItem -LiteralPath (Join-Path $proj 'zipped_loop_packages') -Filter *.zip -File -ErrorAction SilentlyContinue
$vocals = Get-ChildItem -LiteralPath (Join-Path $proj 'vocals') -Recurse -File -Include *.wav,*.flac,*.aif,*.aiff,*.mp3 -ErrorAction SilentlyContinue
$samples = Get-ChildItem -LiteralPath (Join-Path $proj 'samples') -Recurse -File -Include *.wav,*.flac,*.aif,*.aiff,*.mp3 -ErrorAction SilentlyContinue
$stems = Get-ChildItem -LiteralPath (Join-Path $proj 'stems') -Recurse -File -Include *.wav,*.flac,*.aif,*.aiff -ErrorAction SilentlyContinue
$renders = Get-ChildItem -LiteralPath (Join-Path $proj 'renders') -Recurse -File -Include *.wav,*.flac,*.mp3 -ErrorAction SilentlyContinue

$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine("# Project Index")
[void]$sb.AppendLine("")
[void]$sb.AppendLine((List-Section -Title 'FLP Files' -Files $flps))
[void]$sb.AppendLine((List-Section -Title 'FLP Backups' -Files $backups))
[void]$sb.AppendLine((List-Section -Title 'Zipped Loop Packages' -Files $zips))
[void]$sb.AppendLine((List-Section -Title 'Vocals' -Files $vocals))
[void]$sb.AppendLine((List-Section -Title 'Samples' -Files $samples))
[void]$sb.AppendLine((List-Section -Title 'Stems' -Files $stems))
[void]$sb.AppendLine((List-Section -Title 'Renders' -Files $renders))

$notes = Join-Path $proj 'notes/SESSION.md'
if (Test-Path -LiteralPath $notes) {
  [void]$sb.AppendLine("**Notes**")
  [void]$sb.AppendLine("- `notes/SESSION.md`")
}

$chlog = Join-Path $proj 'notes/CHANGELOG.md'
if (Test-Path -LiteralPath $chlog) {
  [void]$sb.AppendLine("**Changelog**")
  [void]$sb.AppendLine("- `notes/CHANGELOG.md`")
}

Set-Content -LiteralPath $out -Value $sb.ToString() -Encoding UTF8
Write-Host "Index written to $out" -ForegroundColor Green

