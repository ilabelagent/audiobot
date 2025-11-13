param(
  [string]$Remote = "s_01k6hw3nt9zsfcbp143hq8tw36@ssh.lightning.ai",
  [string]$RemoteDir = "/teamspace/studios/this_studio/jesus-cartel-production"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$zip = "audiobot_upload.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }

# Include-only packaging for reliability
$items = @(
  'audiobot',
  'web',
  'scripts',
  'requirements.txt',
  'environment.yml',
  'pyproject.toml',
  '.gitignore',
  '.env.example',
  'README.md'
)
Compress-Archive -Path $items -DestinationPath $zip -Force -CompressionLevel Optimal

Write-Host "Checking SSH connectivity to $Remote ..."
$sshOpts = "-o StrictHostKeyChecking=no -o ServerAliveInterval=30 -o ServerAliveCountMax=10 -o ConnectTimeout=20"
ssh $sshOpts $Remote "echo connected" | Out-Host

Write-Host "Uploading $zip to $Remote ..."
scp -o StrictHostKeyChecking=no -o ConnectTimeout=30 $zip "${Remote}:~/$zip"

Write-Host "Unpacking on remote and starting background setup ..."
ssh $sshOpts $Remote "mkdir -p $RemoteDir && unzip -o ~/$zip -d $RemoteDir && rm ~/$zip && chmod +x $RemoteDir/scripts/deploy/setup_conda_vm.sh && nohup bash $RemoteDir/scripts/deploy/setup_conda_vm.sh > ~/deploy_setup.log 2>&1 &"

Write-Host "Deployed to ${Remote}:$RemoteDir"
