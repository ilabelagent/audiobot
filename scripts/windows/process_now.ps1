param(
  [string]$Input,
  [string]$OutDir = "outputs",
  [double]$LUFS = -14
)

if (-not (Test-Path $Input)) { Write-Error "Input not found"; exit 1 }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$dest = Join-Path $OutDir ([IO.Path]::GetFileName($Input))
audiobot clean "$Input" -o "$dest" --lufs $LUFS
Write-Host "Cleaned -> $dest"

