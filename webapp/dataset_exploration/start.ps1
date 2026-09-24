$ErrorActionPreference = 'Stop'
$appRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $appRoot '..\..')).Path
$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
$python = if (Test-Path $venvPython) { $venvPython } else { (Get-Command python -ErrorAction Stop).Source }
$env:PYTHONPATH = "$appRoot;$repoRoot\src"
Set-Location $repoRoot
& $python -m backend.run
