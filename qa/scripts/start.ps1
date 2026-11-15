param(
  [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
)
$ErrorActionPreference = 'Stop'
$results = Join-Path $RepoRoot 'work\qa-results'
New-Item -ItemType Directory -Force -Path $results | Out-Null
$required = @('backend\pyproject.toml', 'frontend\package.json')
$missing = @($required | Where-Object { -not (Test-Path (Join-Path $RepoRoot $_)) })
if ($missing.Count) {
  throw "BLOCKED: application sources are not present in the QA worktree: $($missing -join ', '). The scripts will not start absent code."
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'BLOCKED: Docker CLI is unavailable.' }
docker info *> (Join-Path $results 'docker-info.log')
if ($LASTEXITCODE -ne 0) { throw 'BLOCKED: Docker daemon is unavailable; no test services were started.' }

$env:APP_ENV = 'test'
$env:APP_MODE = 'demo'
$env:SECRET_KEY = 'qa-only-not-a-production-secret-32chars'
$env:DATABASE_URL = 'postgresql+psycopg://omniva:qa_only_disposable@127.0.0.1:55432/omniva_qa'
$env:CORS_ORIGINS = 'http://127.0.0.1:5173'
$env:SMTP_HOST = '127.0.0.1'
$env:SMTP_PORT = '1025'
$env:EMAIL_FROM = 'omniva-qa@example.test'
$env:VITE_APP_MODE = 'demo'
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8000/api/v1'
$compose = Join-Path $RepoRoot 'qa\docker-compose.test.yml'
docker compose -p omniva-phase5b-qa -f $compose up -d
if ($LASTEXITCODE -ne 0) { throw 'BLOCKED: test PostgreSQL/Mailpit could not start.' }
Push-Location (Join-Path $RepoRoot 'backend')
try {
  uv sync --frozen --extra test --extra lint
  if ($LASTEXITCODE -ne 0) { throw 'Backend environment setup failed.' }
  uv run alembic upgrade head
  if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
  uv run python -m app.seed
  if ($LASTEXITCODE -ne 0) { throw 'Deterministic demo seed failed.' }
} finally { Pop-Location }

$backend = Start-Process -FilePath 'uv' -ArgumentList @('run','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory (Join-Path $RepoRoot 'backend') -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $results 'backend.log') -RedirectStandardError (Join-Path $results 'backend-error.log')
$env:VITE_APP_MODE = 'demo'
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8000/api/v1'
$frontend = Start-Process -FilePath 'pnpm' -ArgumentList @('exec','vite','--host','127.0.0.1','--port','5173','--strictPort') -WorkingDirectory (Join-Path $RepoRoot 'frontend') -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $results 'frontend.log') -RedirectStandardError (Join-Path $results 'frontend-error.log')
@{ backend = $backend.Id; frontend = $frontend.Id } | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $results 'server-pids.json')
$ready = $false
for ($i=0; $i -lt 45; $i++) {
  try {
    $null = Invoke-RestMethod 'http://127.0.0.1:8000/health/live' -TimeoutSec 2
    $null = Invoke-WebRequest 'http://127.0.0.1:5173/' -TimeoutSec 2
    $ready = $true
    break
  } catch { Start-Sleep -Seconds 1 }
}
if (-not $ready) { throw "BLOCKED: local services did not become ready; inspect $results logs and run stop.ps1." }
Write-Output "PASS: QA-only services running. Results/logs: $results"
Write-Output 'Backend: http://127.0.0.1:8000; frontend: http://127.0.0.1:5173; Mailpit UI: http://127.0.0.1:8025'
