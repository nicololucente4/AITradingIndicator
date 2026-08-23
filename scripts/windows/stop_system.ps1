# Arresta tutti i processi avviati da start_system.ps1.
#
# Ordine di arresto:
# 1. Frontend Next.js
# 2. FastAPI
# 3. Live Paper Engine
# 4. MT5 Market Collector
#
# Lo script non elimina database, log, modello o file .env.

$ErrorActionPreference = "Continue"

# Recupera la root del progetto.
$ProjectRoot = Resolve-Path (
    Join-Path $PSScriptRoot "..\.."
)

# Definisce la cartella dei PID.
$PidDirectory = Join-Path `
    $ProjectRoot `
    "data\live_paper\pids"

function Stop-ManagedProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProcessName,

        [Parameter(Mandatory = $true)]
        [string] $PidFile
    )

    # Costruisce il percorso del file PID.
    $PidPath = Join-Path `
        $PidDirectory `
        $PidFile

    # Passa al processo successivo se il PID non esiste.
    if (-not (Test-Path $PidPath)) {
        Write-Host (
            $ProcessName +
            ": PID non presente."
        )

        return
    }

    # Legge e normalizza il PID.
    $StoredPid = (
        Get-Content `
            -Path $PidPath `
            -Raw
    ).Trim()

    # Verifica che il PID sia numerico.
    if ($StoredPid -notmatch "^[0-9]+$") {
        Write-Host (
            $ProcessName +
            ": PID non valido."
        )

        Remove-Item `
            -Path $PidPath `
            -Force `
            -ErrorAction SilentlyContinue

        return
    }

    # Recupera il processo.
    $SelectedProcess = Get-Process `
        -Id ([int] $StoredPid) `
        -ErrorAction SilentlyContinue

    # Il processo potrebbe essere già terminato.
    if ($null -eq $SelectedProcess) {
        Write-Host (
            $ProcessName +
            ": processo non attivo."
        )

        Remove-Item `
            -Path $PidPath `
            -Force `
            -ErrorAction SilentlyContinue

        return
    }

    Write-Host (
        "Arresto " +
        $ProcessName +
        ". PID: " +
        $StoredPid
    )

    # Usa taskkill con /T per arrestare anche processi figli.
    # È importante soprattutto per npm e Next.js.
    & taskkill.exe `
        /PID ([int] $StoredPid) `
        /T `
        /F `
        2>$null |
        Out-Null

    # Attende brevemente la chiusura.
    Start-Sleep -Milliseconds 500

    # Controlla se il processo principale è ancora attivo.
    $RemainingProcess = Get-Process `
        -Id ([int] $StoredPid) `
        -ErrorAction SilentlyContinue

    if ($null -eq $RemainingProcess) {
        Write-Host (
            $ProcessName +
            ": arrestato correttamente."
        )
    }
    else {
        # Fallback tramite Stop-Process.
        Stop-Process `
            -Id ([int] $StoredPid) `
            -Force `
            -ErrorAction SilentlyContinue

        Write-Host (
            $ProcessName +
            ": arresto forzato completato."
        )
    }

    # Elimina il file PID.
    Remove-Item `
        -Path $PidPath `
        -Force `
        -ErrorAction SilentlyContinue
}

# Mostra l'intestazione.
Write-Host ""
Write-Host "============================================================"
Write-Host "AI Trading Indicator - Arresto sistema"
Write-Host "============================================================"

# Arresta prima i componenti esposti all'utente.
Stop-ManagedProcess `
    -ProcessName "Frontend Next.js" `
    -PidFile "frontend.pid"

Stop-ManagedProcess `
    -ProcessName "FastAPI" `
    -PidFile "fastapi.pid"

# Arresta il motore delle decisioni.
Stop-ManagedProcess `
    -ProcessName "Live Paper Engine" `
    -PidFile "live_paper.pid"

# Arresta per ultimo il collector MT5.
Stop-ManagedProcess `
    -ProcessName "MT5 Market Collector" `
    -PidFile "market_collector.pid"

# Elimina eventuali file PID residui vuoti o obsoleti.
if (Test-Path $PidDirectory) {
    Get-ChildItem `
        -Path $PidDirectory `
        -Filter "*.pid" `
        -File `
        -ErrorAction SilentlyContinue |
        ForEach-Object {
            $StoredPid = (
                Get-Content `
                    -Path $_.FullName `
                    -Raw `
                    -ErrorAction SilentlyContinue
            ).Trim()

            if (
                $StoredPid -notmatch "^[0-9]+$"
            ) {
                Remove-Item `
                    -Path $_.FullName `
                    -Force `
                    -ErrorAction SilentlyContinue

                return
            }

            $ExistingProcess = Get-Process `
                -Id ([int] $StoredPid) `
                -ErrorAction SilentlyContinue

            if ($null -eq $ExistingProcess) {
                Remove-Item `
                    -Path $_.FullName `
                    -Force `
                    -ErrorAction SilentlyContinue
            }
        }
}

Write-Host ""
Write-Host "============================================================"
Write-Host "Arresto completato"
Write-Host "Database e configurazione locale conservati"
Write-Host "ORDINI REALI: DISABILITATI"
Write-Host "============================================================"