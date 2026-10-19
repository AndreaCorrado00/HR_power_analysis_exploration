param([switch]$Setup,[int]$Port=8770)
$ErrorActionPreference='Stop'
$appRoot=$PSScriptRoot
$repoRoot=Split-Path -Parent $appRoot
$python=Join-Path $repoRoot '.venv/Scripts/python.exe'
if(-not (Test-Path -LiteralPath $python)) {
    if(-not $Setup){throw 'Ambiente Python assente: eseguire .\study_app\start.ps1 -Setup'}
    & python -m venv (Join-Path $repoRoot '.venv')
    if($LASTEXITCODE -ne 0){throw 'Creazione ambiente fallita'}
}
if($Setup){
    & $python -m pip install -r (Join-Path $appRoot 'requirements.txt')
    if($LASTEXITCODE -ne 0){throw 'Installazione Python fallita'}
    $node=Get-Command node -ErrorAction SilentlyContinue
    if(-not $node){
        $nodeBin=Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin'
        if(Test-Path (Join-Path $nodeBin 'node.exe')){$env:PATH="$nodeBin;$env:PATH"}
    }
    $npm=Get-Command npm.cmd -ErrorAction SilentlyContinue
    Push-Location (Join-Path $appRoot 'frontend')
    try{
        if($npm){& $npm.Source ci --no-audit --no-fund;if($LASTEXITCODE -ne 0){throw 'npm ci fallito'}}
        elseif(-not (Test-Path 'node_modules/vite/bin/vite.js')){throw 'Installare Node.js con npm per il setup frontend'}
        & node node_modules/vue-tsc/bin/vue-tsc.js --noEmit
        if($LASTEXITCODE -ne 0){throw 'Controllo TypeScript fallito'}
        & node node_modules/vite/bin/vite.js build
        if($LASTEXITCODE -ne 0){throw 'Build frontend fallita'}
    }finally{Pop-Location}
}
if(-not (Test-Path (Join-Path $appRoot 'frontend/dist/index.html'))){throw 'Frontend non compilato: eseguire start.ps1 -Setup'}
Push-Location $repoRoot
try{& $python -B -m study_app.backend.run --port $Port --open}
finally{Pop-Location}
