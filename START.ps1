$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    $taskPython = (Get-Command python -ErrorAction Stop).Source
}
Write-Host 'DASH Meal Prep AI: http://127.0.0.1:8767. Press Ctrl+C to stop.'
& $taskPython (Join-Path $PSScriptRoot 'app.py')
