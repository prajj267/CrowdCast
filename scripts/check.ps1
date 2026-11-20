# Run every check: backend (format, lint, types, tests) and frontend (format, lint, type-checked
# build). Usage from the repo root:
#   powershell -ExecutionPolicy Bypass -File scripts\check.ps1
# Exits non-zero on the first failure. Frontend checks are skipped if `npm install` was not run.
$ErrorActionPreference = "Stop"
Push-Location (Join-Path $PSScriptRoot "..\backend")
try {
    uv run ruff format --check .;  if ($LASTEXITCODE) { exit $LASTEXITCODE }
    uv run ruff check .;           if ($LASTEXITCODE) { exit $LASTEXITCODE }
    uv run mypy;                   if ($LASTEXITCODE) { exit $LASTEXITCODE }
    uv run pytest;                 if ($LASTEXITCODE) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}
$frontend = Join-Path $PSScriptRoot "..\frontend"
if (Test-Path (Join-Path $frontend "node_modules")) {
    Push-Location $frontend
    try {
        npm run --silent format:check;  if ($LASTEXITCODE) { exit $LASTEXITCODE }
        npm run --silent lint;          if ($LASTEXITCODE) { exit $LASTEXITCODE }
        npm run --silent build;         if ($LASTEXITCODE) { exit $LASTEXITCODE }
    }
    finally {
        Pop-Location
    }
} else {
    Write-Host "frontend/node_modules missing: frontend checks skipped (run npm install)" -ForegroundColor Yellow
}
Write-Host "All checks passed." -ForegroundColor Green
