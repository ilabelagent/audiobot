param(
  [int]$Port = 8000,
  [string]$Host = '0.0.0.0',
  [string]$GcpKey = 'Z:\\Projects\\audiobot\\peaceful-access-473817-v1-b6c23a77fab4.json',
  [string]$Bucket,
  [string]$Prefix
)

$ErrorActionPreference = 'Stop'
$conda = 'C:\Users\Admin\miniconda3\condabin\conda.bat'
if (-not (Test-Path $conda)) { throw "Miniconda not found at $conda" }

# Set env for GCS if provided/exists
if ($GcpKey -and (Test-Path $GcpKey)) { $env:GOOGLE_APPLICATION_CREDENTIALS = $GcpKey }
if ($Bucket) { $env:GCS_BUCKET = $Bucket }
if ($Prefix) { $env:GCS_PREFIX = $Prefix }

# Run uvicorn under the 'audio' environment
& $conda run -n audio uvicorn web.app:app --host $Host --port $Port

