param(
  [string]$EnvName = 'audio'
)

$ErrorActionPreference = 'Stop'
$conda = 'C:\Users\Admin\miniconda3\condabin\conda.bat'
if (-not (Test-Path $conda)) { throw "Miniconda not found at $conda" }

& $conda run -n $EnvName python -m pip install --upgrade pip build pyinstaller

# Build wheel (optional)
& $conda run -n $EnvName python -m build

# Create single-file CLI binary
& $conda run -n $EnvName pyinstaller -F -n audiobot -c -s -p . audiobot/__main__.py

Write-Host 'Standalone built under dist/audiobot.exe'

