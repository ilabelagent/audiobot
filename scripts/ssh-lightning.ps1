param(
  [string]$User = 's_01k6hw3nt9zsfcbp143hq8tw36',
  [string]$Host = 'ssh.lightning.ai',
  [int]$WebPort = 8000,
  [int]$LitPort = 8080,
  [string]$IdentityFile
)

$ErrorActionPreference = 'Stop'

$sshArgs = @(
  '-o','ServerAliveInterval=60',
  '-o','ServerAliveCountMax=5',
  '-o','StrictHostKeyChecking=no',
  '-L',"$WebPort:localhost:$WebPort",
  '-L',"$LitPort:localhost:$LitPort"
)
if ($IdentityFile -and (Test-Path $IdentityFile)) {
  $sshArgs += @('-i', $IdentityFile)
}
$sshArgs += @("$User@$Host")

Write-Host "SSH -> $User@$Host (tunnels: $WebPort,$LitPort)" -ForegroundColor Cyan
ssh @sshArgs

