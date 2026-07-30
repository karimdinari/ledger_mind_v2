# One-shot for Windows PowerShell:
#   .\docker-up.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "Created .env from .env.example — set GEMINI_API_KEY and MISTRAL_API_KEY, then re-run."
  exit 1
}

docker compose up --build @args
