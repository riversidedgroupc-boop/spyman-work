param(
    [string]$Configuration = "Release",
    [string]$OutputDir = "dist\cpp_runtime_package"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ExePath = Join-Path $RepoRoot "cpp_runtime\build\cx_vision_runtime.exe"
$ContractDoc = Join-Path $RepoRoot "docs\cpp_runtime_contract.md"
$IntegrationDoc = Join-Path $RepoRoot "docs\cpp_platform_integration.md"

if (-not (Test-Path $ExePath)) {
    throw "Missing runtime executable: $ExePath"
}

$Out = Join-Path $RepoRoot $OutputDir
New-Item -ItemType Directory -Force -Path $Out | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Out "config") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Out "docs") | Out-Null

Copy-Item -LiteralPath $ExePath -Destination (Join-Path $Out "cx_vision_runtime.exe") -Force
Copy-Item -LiteralPath $ContractDoc -Destination (Join-Path $Out "docs\cpp_runtime_contract.md") -Force
Copy-Item -LiteralPath $IntegrationDoc -Destination (Join-Path $Out "docs\cpp_platform_integration.md") -Force

$ExampleConfig = @'
{
  "run_id": "smoke_001",
  "project_id": "project_001",
  "spec_id": "spec_001",
  "backend": "cpp_runtime",
  "cameras": [],
  "model_artifacts": {},
  "confidence": 0.5,
  "iou": 0.45,
  "save_policy": "save_ng_only",
  "output_dir": "D:/data/cx_runtime/output"
}
'@

Set-Content -LiteralPath (Join-Path $Out "config\runtime_config.example.json") -Value $ExampleConfig -Encoding UTF8
Write-Output "C++ runtime package written to: $Out"
