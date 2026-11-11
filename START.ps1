$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
Write-Host 'DASH Meal Prep AI: http://127.0.0.1:8767. Press Ctrl+C to stop.'
if (Test-Path -LiteralPath $taskPython) {
    & $taskPython (Join-Path $PSScriptRoot 'app.py')
} else {
    $taskUv = (Get-Command uv -ErrorAction Stop).Source
    & $taskUv run --no-project python (Join-Path $PSScriptRoot 'app.py')
}
