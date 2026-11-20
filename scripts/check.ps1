# Run every backend check (format, lint, types, tests). Usage from the repo root:
#   powershell -ExecutionPolicy Bypass -File scripts\check.ps1
# Exits non-zero on the first failure.
$ErrorActionPreference = "Stop"
Push-Location (Join-Path $PSScriptRoot "..\backend")
try {
    uv run ruff format --check .;  if ($LASTEXITCODE) { exit $LASTEXITCODE }
    uv run ruff check .;           if ($LASTEXITCODE) { exit $LASTEXITCODE }
    uv run mypy;                   if ($LASTEXITCODE) { exit $LASTEXITCODE }
    uv run pytest;                 if ($LASTEXITCODE) { exit $LASTEXITCODE }
    Write-Host "All checks passed." -ForegroundColor Green
}
finally {
    Pop-Location
}
