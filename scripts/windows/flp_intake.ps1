# Watches a folder for new WAVs and processes them via CLI
param(
  [string]$WatchDir = "C:\\AudioInbox",
  [string]$OutDir = "C:\\AudioOut",
  [double]$LUFS = -14
)

Write-Host "Watching $WatchDir -> $OutDir"
New-Item -ItemType Directory -Force -Path $WatchDir | Out-Null
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$fsw = New-Object IO.FileSystemWatcher $WatchDir, '*.wav'
$fsw.IncludeSubdirectories = $true
$fsw.EnableRaisingEvents = $true

Register-ObjectEvent $fsw Created -Action {
  Start-Sleep -Milliseconds 500
  $path = $Event.SourceEventArgs.FullPath
  $name = [IO.Path]::GetFileName($path)
  $dest = Join-Path $using:OutDir $name
  Write-Host "Processing: $path"
  audiobot clean "$path" -o "$dest" --lufs $using:LUFS
  Write-Host "Done -> $dest"
} | Out-Null

while ($true) { Start-Sleep -Seconds 5 }

