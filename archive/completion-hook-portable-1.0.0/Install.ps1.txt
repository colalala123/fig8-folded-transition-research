param(
    [string]$Python = 'python',
    [switch]$WithHfss,
    [string]$Wheelhouse
)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
& $Python -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ required"'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.10+ is required; pass -Python with its full executable path.' }
$venv = Join-Path $root '.venv'
$venvPython = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venv)) {
    & $Python -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw 'venv creation failed' }
}
if (-not (Test-Path -LiteralPath $venvPython)) { throw 'Existing .venv is invalid; not overwriting it.' }
$requirements = Join-Path $root 'requirements.txt'
if ($WithHfss) { $requirements = Join-Path $root 'requirements-hfss.txt' }
$pipArgs = @('-m','pip','install','-r',$requirements)
if ($Wheelhouse) { $pipArgs += @('--no-index','--find-links',$Wheelhouse) }
& $venvPython @pipArgs
if ($LASTEXITCODE -ne 0) { throw 'Dependencies failed to install; no thread config or notifications were created.' }
& $venvPython -m unittest discover -s (Join-Path $root 'tests') -p 'test_*.py' -v
if ($LASTEXITCODE -ne 0) { throw 'Self-tests failed; do not connect to production.' }
Write-Host 'Installed. No message has been sent and no destination has been authorized.'
Write-Host 'Next: read INSTALL_FOR_AI.md, then explicitly initialize an authorized destination in a Codex desktop terminal.'
