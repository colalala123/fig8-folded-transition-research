param([switch]$Send, [ValidateRange(0,120)][int]$DelaySeconds=30)
$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$script = Join-Path $PSScriptRoot 'examples\smoke_test.py'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run Install.ps1 first.' }
if (-not $Send) {
    & $python $script
    if ($LASTEXITCODE -ne 0) { throw 'Offline smoke failed' }
    exit
}
if (-not $env:CODEX_THREAD_ID -or -not $env:CODEX_APP_TOOLS_PIPE_PATH) {
    throw 'Real send must be launched inside the authorized Codex desktop conversation terminal.'
}
# -Send is an explicit operator action. This test emits a synthetic message,
# not an HFSS result. Default delay lets the current conversation become idle.
$logRoot = Join-Path $PSScriptRoot '.local'
$id = [guid]::NewGuid().ToString('N')
$stdout = Join-Path $logRoot "smoke-$id.stdout.log"
$stderr = Join-Path $logRoot "smoke-$id.stderr.log"
$env:PYTHONIOENCODING = 'utf-8'
$argLine = '-u "' + $script + '" --send --delay-seconds ' + $DelaySeconds
$p = Start-Process -FilePath $python -ArgumentList $argLine -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
Write-Host "Background smoke PID=$($p.Id)"
Write-Host "stdout=$stdout"
Write-Host "stderr=$stderr"
