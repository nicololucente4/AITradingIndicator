# Avvia tutti i componenti dell'AI Trading Indicator.
# Lo script deve essere eseguito dalla root del progetto.

$ErrorActionPreference = "Stop"

# Recupera la root del progetto partendo dalla posizione dello script.
$ProjectRoot = Resolve-Path (
    Join-Path $PSScriptRoot "..\.."
)

# Definisce i percorsi principali.
$PythonExecutable = Join-Path `
    $ProjectRoot `
    ".venv\Scripts\python.exe"

$FrontendDirectory = Join-Path `
    $ProjectRoot `
    "frontend"

$EnvironmentFile = Join-Path `
    $ProjectRoot `
    ".env"

$RuntimeDirectory = Join-Path `
    $ProjectRoot `
    "data\live_paper"

$PidDirectory = Join-Path `
    $RuntimeDirectory `
    "pids"

# Mostra l'intestazione.
Write-Host ""
Write-Host "============================================================"
Write-Host "AI Trading Indicator - Avvio sistema"
Write-Host "============================================================"
Write-Host "Modalita: PAPER ONLY"
Write-Host "Ordini reali: DISABILITATI"
Write-Host ""

# Verifica l'ambiente Python.
if (-not (Test-Path $PythonExecutable)) {
    throw (
        "Ambiente Python non trovato: " +
        $PythonExecutable
    )
}

# Verifica il file locale .env.
if (-not (Test-Path $EnvironmentFile)) {
    throw (
        "File .env non trovato. " +
        "Copiare .env.example in .env e configurarlo."
    )
}

# Verifica il frontend.
if (-not (Test-Path $FrontendDirectory)) {
    throw (
        "Cartella frontend non trovata: " +
        $FrontendDirectory
    )
}

# Crea le cartelle runtime.
New-Item `
    -ItemType Directory `
    -Path $RuntimeDirectory `
    -Force |
    Out-Null

New-Item `
    -ItemType Directory `
    -Path $PidDirectory `
    -Force |
    Out-Null

# Si sposta nella root.
Set-Location $ProjectRoot

Write-Host "Esecuzione preflight..."

# Esegue il controllo preventivo.
& $PythonExecutable `
    -m scripts.preflight_check `
    --env-file $EnvironmentFile

# Interrompe l'avvio se il preflight fallisce.
if ($LASTEXITCODE -ne 0) {
    throw "Preflight fallito. Sistema non avviato."
}

Write-Host ""
Write-Host "Preflight superato."
Write-Host "Avvio Live Paper Engine..."

# Avvia il motore Live Paper.
$LivePaperProcess = Start-Process `
    -FilePath $PythonExecutable `
    -ArgumentList @(
        "-m",
        "scripts.run_continuous_live_paper",
        "--env-file",
        $EnvironmentFile
    ) `
    -WorkingDirectory $ProjectRoot `
    -PassThru

# Salva il PID del motore.
Set-Content `
    -Path (
        Join-Path $PidDirectory "live_paper.pid"
    ) `
    -Value $LivePaperProcess.Id `
    -Encoding ascii

Write-Host (
    "Live Paper Engine avviato. PID: " +
    $LivePaperProcess.Id
)

Write-Host "Avvio FastAPI..."

# Avvia FastAPI.
$ApiProcess = Start-Process `
    -FilePath $PythonExecutable `
    -ArgumentList @(
        "-m",
        "uvicorn",
        "src.api.app:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000"
    ) `
    -WorkingDirectory $ProjectRoot `
    -PassThru

# Salva il PID di FastAPI.
Set-Content `
    -Path (
        Join-Path $PidDirectory "fastapi.pid"
    ) `
    -Value $ApiProcess.Id `
    -Encoding ascii

Write-Host (
    "FastAPI avviata. PID: " +
    $ApiProcess.Id
)

Write-Host "Avvio frontend Next.js..."

# Avvia il frontend.
$FrontendProcess = Start-Process `
    -FilePath "cmd.exe" `
    -ArgumentList @(
        "/c",
        "npm run dev"
    ) `
    -WorkingDirectory $FrontendDirectory `
    -PassThru

# Salva il PID del frontend.
Set-Content `
    -Path (
        Join-Path $PidDirectory "frontend.pid"
    ) `
    -Value $FrontendProcess.Id `
    -Encoding ascii

Write-Host (
    "Frontend avviato. PID: " +
    $FrontendProcess.Id
)

Write-Host ""
Write-Host "============================================================"
Write-Host "Sistema avviato"
Write-Host "============================================================"
Write-Host "Frontend: http://localhost:3000"
Write-Host "FastAPI:  http://127.0.0.1:8000"
Write-Host "API Docs: http://127.0.0.1:8000/docs"
Write-Host ""
Write-Host "PAPER TRADING: OBBLIGATORIO"
Write-Host "ORDINI REALI: DISABILITATI"
Write-Host "============================================================"