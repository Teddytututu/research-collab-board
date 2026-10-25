param(
  [switch]$Install,
  [switch]$DryRun,
  [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
  [string]$DataDir = 'data',
  [string]$Python = ''
)
$ErrorActionPreference = 'Stop'
if (-not $Python) {
  $candidate = Join-Path $ProjectRoot '.venv/Scripts/python.exe'
  if (Test-Path -LiteralPath $candidate) { $Python = $candidate }
  else { $Python = (Get-Command python -ErrorAction Stop).Source }
}
$arguments = @('-B', (Join-Path $PSScriptRoot 'install_night_watch.py'), '--project-root', $ProjectRoot, '--data-dir', $DataDir, '--python', $Python)
if ($Install) { $arguments += '--install' }
if ($DryRun) { $arguments += '--dry-run' }
& $Python @arguments
exit $LASTEXITCODE
