param(
    [switch]$Setup,
    [int]$Port = 8766,
    [string]$Storage = ''
)
$ErrorActionPreference = 'Stop'
$appRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $appRoot '..\..')).Path
$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    if (-not $Setup) { throw 'Virtualenv assente. Eseguire start.ps1 -Setup con Python installato.' }
    & python -m venv (Join-Path $repoRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Creazione virtualenv fallita' }
}
Push-Location $appRoot
try {
    if ($Setup) {
        & $venvPython -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) { throw 'Installazione dipendenze Python fallita' }
        $nodeCommand = Get-Command node -ErrorAction SilentlyContinue
        if (-not $nodeCommand) {
            $bundledNode = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin'
            if (Test-Path (Join-Path $bundledNode 'node.exe')) { $env:PATH = "$bundledNode;$env:PATH" }
            else { throw 'Installare Node.js >=22.12 con npm, poi ripetere -Setup.' }
        }
        $npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
        $localNpm = Join-Path $appRoot 'storage\tools\package\bin\npm-cli.js'
        if ($npmCommand) {
            & $npmCommand.Source ci --no-audit --no-fund
            if ($LASTEXITCODE -ne 0) { throw 'npm ci fallito' }
            & $npmCommand.Source run build
        } elseif (Test-Path $localNpm) {
            & node $localNpm ci --no-audit --no-fund
            if ($LASTEXITCODE -ne 0) { throw 'npm ci fallito' }
            & node $localNpm run build
        } else { throw 'npm non trovato. Installare Node.js con npm, poi ripetere -Setup.' }
        if ($LASTEXITCODE -ne 0) { throw 'Build frontend fallita' }
    }
    if (-not (Test-Path (Join-Path $appRoot 'dist\index.html'))) { throw 'Frontend assente: eseguire start.ps1 -Setup.' }
    Set-Location $repoRoot
    $arguments = @('-m','webapp.model_identification_app.backend.run','--port',"$Port")
    if ($Storage) { $arguments += @('--storage',$Storage) }
    & $venvPython @arguments
    if ($LASTEXITCODE -ne 0) { throw 'Il servizio è terminato con un errore.' }
} finally { Pop-Location }
