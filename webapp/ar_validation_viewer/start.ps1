param(
    [int]$Port = 8767,
    [string]$BindAddress = '0.0.0.0',
    [string]$RunDirectory = ''
)
$ErrorActionPreference = 'Stop'
$appRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $appRoot '..\..')).Path
$viewerPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $viewerPython)) { $viewerPython = (Get-Command python -ErrorAction Stop).Source }
$viewerArgs = @('-B', (Join-Path $appRoot 'server.py'), '--host', $BindAddress, '--port', $Port)
if ($RunDirectory) { $viewerArgs += @('--run', $RunDirectory) }
& $viewerPython @viewerArgs
