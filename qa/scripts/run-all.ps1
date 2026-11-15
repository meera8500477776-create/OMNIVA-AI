param([string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path)
$ErrorActionPreference = 'Stop'
$results = Join-Path $RepoRoot 'work\qa-results'
New-Item -ItemType Directory -Force -Path $results | Out-Null
$summary = [ordered]@{ started = (Get-Date).ToUniversalTime().ToString('o'); checks = @() }
$checks = @(
  @{ name='backend-unit-api-migration'; command='Push-Location backend; try { uv run ruff check app tests; if ($LASTEXITCODE) { throw "ruff failed" }; uv run ruff format --check app tests; if ($LASTEXITCODE) { throw "ruff format failed" }; uv run alembic check; if ($LASTEXITCODE) { throw "migration drift" }; uv run pytest tests ../qa/api/tests -q --junitxml=../work/qa-results/pytest.xml; if ($LASTEXITCODE) { throw "pytest failed" } } finally { Pop-Location }' },
  @{ name='frontend-lint-type-unit-build'; command='Push-Location frontend; try { pnpm lint; if ($LASTEXITCODE) { throw "lint failed" }; pnpm exec tsc -b --pretty false; if ($LASTEXITCODE) { throw "typecheck failed" }; pnpm test; if ($LASTEXITCODE) { throw "unit tests failed" }; pnpm build; if ($LASTEXITCODE) { throw "production build failed" } } finally { Pop-Location }' },
  @{ name='playwright-browser'; command='Push-Location qa/browser; try { npm ci; if ($LASTEXITCODE) { throw "npm ci failed" }; npx playwright install chromium; if ($LASTEXITCODE) { throw "Playwright browser installation failed" }; npm test -- --reporter=line,junit } finally { Pop-Location }' }
)
foreach ($check in $checks) {
  try {
    Invoke-Expression $check.command
    $summary.checks += [ordered]@{ name=$check.name; status='PASS' }
  } catch {
    $summary.checks += [ordered]@{ name=$check.name; status='FAIL'; detail=$_.Exception.Message }
  }
}
$summary.finished = (Get-Date).ToUniversalTime().ToString('o')
$summary | ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8 (Join-Path $results 'test-run-summary.json')
$summary.checks | Format-Table -AutoSize
if (@($summary.checks | Where-Object status -ne 'PASS').Count) { exit 1 }
