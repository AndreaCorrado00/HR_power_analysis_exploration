param(
    [ValidateSet('exploration', 'identification')]
    [string]$App = 'identification',
    [string]$Source = 'dataset',
    [string]$Destination = 'exports',
    [int]$Port = 0,
    [switch]$Setup
)
$ErrorActionPreference = 'Stop'
$repoRoot = $PSScriptRoot
function Resolve-WorkspacePath([string]$Value) {
    if ([IO.Path]::IsPathRooted($Value)) { return [IO.Path]::GetFullPath($Value) }
    return [IO.Path]::GetFullPath((Join-Path $repoRoot $Value))
}
$sourcePath = Resolve-WorkspacePath $Source
$exportPath = Resolve-WorkspacePath $Destination
if ($Source -eq 'dataset') { New-Item -ItemType Directory -Force -Path $sourcePath | Out-Null }
if (-not (Test-Path -LiteralPath $sourcePath -PathType Container)) { throw "Cartella sorgente non trovata: $sourcePath" }
New-Item -ItemType Directory -Force -Path $exportPath | Out-Null
$pythonPath = Join-Path $repoRoot '.venv\Scripts\python.exe'
$appFolder = if ($App -eq 'exploration') { 'dataset_exploration' } else { 'model_identification_app' }
$appRoot = Join-Path $repoRoot "webapp\$appFolder"
$oldSource = $env:HR_POWER_SOURCE
$oldExports = $env:HR_POWER_EXPORTS
$oldPythonPath = $env:PYTHONPATH
$oldPath = $env:PATH
Push-Location $repoRoot
try {
    if ($Setup) {
        if (-not (Test-Path -LiteralPath $pythonPath)) {
            & python -m venv (Join-Path $repoRoot '.venv')
            if ($LASTEXITCODE -ne 0) { throw 'Creazione virtualenv fallita' }
        }
        & $pythonPath -m pip install -r (Join-Path $appRoot 'requirements.txt')
        if ($LASTEXITCODE -ne 0) { throw 'Installazione dipendenze fallita' }
        if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
            $bundledNode = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin'
            if (-not (Test-Path (Join-Path $bundledNode 'node.exe'))) { throw 'Installare Node.js >=22.12 con npm per -Setup.' }
            $env:PATH = "$bundledNode;$env:PATH"
        }
        $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
        $npmScript = Join-Path $repoRoot 'webapp\model_identification_app\storage\tools\package\bin\npm-cli.js'
        Push-Location $appRoot
        try {
            if ($npm) { & $npm.Source ci --no-audit --no-fund }
            elseif (Test-Path $npmScript) { & node $npmScript ci --no-audit --no-fund }
            else { throw 'Installare npm per -Setup.' }
            if ($LASTEXITCODE -ne 0) { throw 'npm ci fallito' }
            if ($npm) { & $npm.Source run build } else { & node $npmScript run build }
            if ($LASTEXITCODE -ne 0) { throw 'Build frontend fallita' }
        } finally { Pop-Location }
    }
    if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Eseguire prima start-athlete.ps1 con -Setup.' }
    if (-not (Test-Path (Join-Path $appRoot 'dist\index.html'))) { throw 'Frontend assente: ripetere con -Setup.' }
    $env:HR_POWER_SOURCE = $sourcePath
    $env:HR_POWER_EXPORTS = $exportPath
    $env:PYTHONPATH = "$repoRoot;$repoRoot\src"
    Write-Host "Workspace atleta: $repoRoot"
    Write-Host "Sorgente X: $sourcePath"
    Write-Host "Export Y: $exportPath"
    if ($App -eq 'identification') { Write-Host "Storage: $appRoot\storage" }
    & $pythonPath -m "webapp.$appFolder.backend.run" --port $Port
    if ($LASTEXITCODE -ne 0) { throw 'Il servizio e terminato con un errore.' }
} finally {
    $env:HR_POWER_SOURCE = $oldSource
    $env:HR_POWER_EXPORTS = $oldExports
    $env:PYTHONPATH = $oldPythonPath
    $env:PATH = $oldPath
    Pop-Location
}
