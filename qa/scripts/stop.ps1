param([string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path)
$ErrorActionPreference = 'Continue'
$results = Join-Path $RepoRoot 'work\qa-results'
$pidsFile = Join-Path $results 'server-pids.json'
if (Test-Path $pidsFile) {
  $processes = Get-Content $pidsFile -Raw | ConvertFrom-Json
  foreach ($id in @($processes.backend, $processes.frontend)) {
    if ($id) { Stop-Process -Id ([int]$id) -Force -ErrorAction SilentlyContinue }
  }
  Remove-Item -LiteralPath $pidsFile -Force
}
$compose = Join-Path $RepoRoot 'qa\docker-compose.test.yml'
docker compose -p omniva-phase5b-qa -f $compose down --volumes --remove-orphans
if ($LASTEXITCODE -ne 0) { Write-Warning 'Disposable QA Compose cleanup did not complete.' }
Write-Output "QA servers stopped. Reports and logs are retained at $results."
