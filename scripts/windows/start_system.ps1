# Avvia tutti i componenti dell'AI Trading Indicator.
# Eseguire questo script dalla root del progetto.
#
# Processi avviati:
# 1. MT5 Market Collector multi-market
# 2. Live Paper Engine
# 3. FastAPI
# 4. Frontend Next.js
#
# Sicurezza:
# - PAPER ONLY
# - nessun ordine reale
# - nessuna funzione di invio ordini

$ErrorActionPreference = "Stop"

# Recupera la root del progetto dalla posizione dello script.
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

# Definisce i file PID.
$MarketCollectorPidPath = Join-Path `
    $PidDirectory `
    "market_collector.pid"

$LivePaperPidPath = Join-Path `
    $PidDirectory `
    "live_paper.pid"

$FastApiPidPath = Join-Path `
    $PidDirectory `
    "fastapi.pid"

$FrontendPidPath = Join-Path `
    $PidDirectory `
    "frontend.pid"

# Elenca i processi avviati durante questa esecuzione.
$StartedProcesses = @()

function Test-ProcessFromPidFile {
    param(
        [Parameter(Mandatory = $true)]
        [string] $PidPath
    )

    # Un file PID assente non rappresenta un processo attivo.
    if (-not (Test-Path $PidPath)) {
        return $false
    }

    # Legge e normalizza il PID.
    $StoredPid = (
        Get-Content `
            -Path $PidPath `
            -Raw
    ).Trim()

    # Un contenuto non numerico non è valido.
    if ($StoredPid -notmatch "^[0-9]+$") {
        Remove-Item `
            -Path $PidPath `
            -Force `
            -ErrorAction SilentlyContinue

        return $false
    }

    # Cerca il processo.
    $ExistingProcess = Get-Process `
        -Id ([int] $StoredPid) `
        -ErrorAction SilentlyContinue

    # Se il processo non esiste, elimina il PID obsoleto.
    if ($null -eq $ExistingProcess) {
        Remove-Item `
            -Path $PidPath `
            -Force `
            -ErrorAction SilentlyContinue

        return $false
    }

    return $true
}

function Assert-ProcessNotRunning {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProcessName,

        [Parameter(Mandatory = $true)]
        [string] $PidPath
    )

    # Blocca un doppio avvio accidentale.
    if (
        Test-ProcessFromPidFile `
            -PidPath $PidPath
    ) {
        $StoredPid = (
            Get-Content `
                -Path $PidPath `
                -Raw
        ).Trim()

        throw (
            $ProcessName +
            " risulta già attivo. PID: " +
            $StoredPid +
            ". Eseguire prima stop_system.ps1."
        )
    }
}

function Start-ManagedProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProcessName,

        [Parameter(Mandatory = $true)]
        [string] $FilePath,

        [Parameter(Mandatory = $true)]
        [string[]] $ArgumentList,

        [Parameter(Mandatory = $true)]
        [string] $WorkingDirectory,

        [Parameter(Mandatory = $true)]
        [string] $PidPath
    )

    Write-Host (
        "Avvio " +
        $ProcessName +
        "..."
    )

    # Avvia il processo.
    $StartedProcess = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -PassThru

    # Attende brevemente per intercettare errori immediati.
    Start-Sleep -Seconds 2

    # Aggiorna le informazioni del processo.
    $StartedProcess.Refresh()

    # Un processo già terminato indica un errore di avvio.
    if ($StartedProcess.HasExited) {
        throw (
            $ProcessName +
            " si è arrestato subito dopo l'avvio. " +
            "Codice di uscita: " +
            $StartedProcess.ExitCode
        )
    }

    # Salva il PID.
    Set-Content `
        -Path $PidPath `
        -Value $StartedProcess.Id `
        -Encoding ascii

    # Memorizza il processo per un eventuale rollback.
    $script:StartedProcesses += @{
        Name = $ProcessName
        Id = $StartedProcess.Id
        PidPath = $PidPath
    }

    Write-Host (
        $ProcessName +
        " avviato. PID: " +
        $StartedProcess.Id
    )

    return $StartedProcess
}

function Stop-StartedProcesses {
    # Arresta in ordine inverso i processi avviati
    # durante questa esecuzione fallita.
    $ReversedProcesses = @(
        $script:StartedProcesses
    )

    :Reverse(
        $ReversedProcesses
    )

    foreach (
        $ProcessInformation
        in $ReversedProcesses
    ) {
        Write-Host (
            "Rollback: arresto " +
            $ProcessInformation.Name +
            "..."
        )

        # taskkill /T arresta anche gli eventuali processi figli.
        & taskkill.exe `
            /PID $ProcessInformation.Id `
            /T `
            /F `
            2>$null |
            Out-Null

        Remove-Item `
            -Path $ProcessInformation.PidPath `
            -Force `
            -ErrorAction SilentlyContinue
    }
}

# Mostra l'intestazione.
Write-Host ""
Write-Host "============================================================"
Write-Host "AI Trading Indicator - Avvio sistema"
Write-Host "============================================================"
Write-Host "Modalita: PAPER ONLY"
Write-Host "Ordini reali: DISABILITATI"
Write-Host ""

try {
    # Verifica l'ambiente virtuale.
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

    # Verifica che npm sia disponibile.
    $NpmCommand = Get-Command `
        "npm.cmd" `
        -ErrorAction SilentlyContinue

    if ($null -eq $NpmCommand) {
        throw (
            "npm.cmd non trovato. " +
            "Installare Node.js e npm."
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

    # Controlla che il sistema non sia già in esecuzione.
    Assert-ProcessNotRunning `
        -ProcessName "MT5 Market Collector" `
        -PidPath $MarketCollectorPidPath

    Assert-ProcessNotRunning `
        -ProcessName "Live Paper Engine" `
        -PidPath $LivePaperPidPath

    Assert-ProcessNotRunning `
        -ProcessName "FastAPI" `
        -PidPath $FastApiPidPath

    Assert-ProcessNotRunning `
        -ProcessName "Frontend Next.js" `
        -PidPath $FrontendPidPath

    # Si sposta nella root del progetto.
    Set-Location $ProjectRoot

    Write-Host "Esecuzione preflight..."

    # Esegue il controllo preventivo.
    & $PythonExecutable `
        -m scripts.preflight_check `
        --env-file $EnvironmentFile

    # Interrompe l'avvio se il preflight fallisce.
    if ($LASTEXITCODE -ne 0) {
        throw (
            "Preflight fallito. " +
            "Sistema non avviato."
        )
    }

    Write-Host ""
    Write-Host "Preflight superato."

    # Avvia il collector multi-market.
    $MarketCollectorProcess = Start-ManagedProcess `
        -ProcessName "MT5 Market Collector" `
        -FilePath $PythonExecutable `
        -ArgumentList @(
            "-m",
            "scripts.run_mt5_market_collector",
            "--env-file",
            $EnvironmentFile
        ) `
        -WorkingDirectory $ProjectRoot `
        -PidPath $MarketCollectorPidPath

    # Avvia il modello Live Paper su EURUSD M15.
    $LivePaperProcess = Start-ManagedProcess `
        -ProcessName "Live Paper Engine" `
        -FilePath $PythonExecutable `
        -ArgumentList @(
            "-m",
            "scripts.run_continuous_live_paper",
            "--env-file",
            $EnvironmentFile
        ) `
        -WorkingDirectory $ProjectRoot `
        -PidPath $LivePaperPidPath

    # Avvia FastAPI.
    $ApiProcess = Start-ManagedProcess `
        -ProcessName "FastAPI" `
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
        -PidPath $FastApiPidPath

    # Avvia Next.js.
    $FrontendProcess = Start-ManagedProcess `
        -ProcessName "Frontend Next.js" `
        -FilePath $NpmCommand.Source `
        -ArgumentList @(
            "run",
            "dev"
        ) `
        -WorkingDirectory $FrontendDirectory `
        -PidPath $FrontendPidPath

    # Evita warning per variabili intenzionalmente usate
    # solo come riferimento ai processi.
    $null = $MarketCollectorProcess
    $null = $LivePaperProcess
    $null = $ApiProcess
    $null = $FrontendProcess

    Write-Host ""
    Write-Host "============================================================"
    Write-Host "Sistema avviato"
    Write-Host "============================================================"
    Write-Host "MT5 Market Collector: ATTIVO"
    Write-Host "Live Paper Engine:     ATTIVO"
    Write-Host "FastAPI:               ATTIVA"
    Write-Host "Frontend Next.js:      ATTIVO"
    Write-Host ""
    Write-Host "Frontend: http://localhost:3000"
    Write-Host "FastAPI:  http://127.0.0.1:8000"
    Write-Host "API Docs: http://127.0.0.1:8000/docs"
    Write-Host ""
    Write-Host "PAPER TRADING: OBBLIGATORIO"
    Write-Host "ORDINI REALI: DISABILITATI"
    Write-Host "============================================================"
}
catch {
    Write-Host ""
    Write-Host "ERRORE DURANTE L'AVVIO:"
    Write-Host $_.Exception.Message

    # Arresta eventuali processi già avviati.
    Stop-StartedProcesses

    Write-Host ""
    Write-Host "Sistema non avviato."
    Write-Host "ORDINI REALI: DISABILITATI"

    exit 1
}