# Arresta i processi avviati da start_system.ps1.

$ErrorActionPreference = "Continue"

# Recupera la root del progetto.
$ProjectRoot = Resolve-Path (
    Join-Path $PSScriptRoot "..\.."
)

# Definisce la cartella dei PID.
$PidDirectory = Join-Path `
    $ProjectRoot `
    "data\live_paper\pids"

# Mostra l'intestazione.
Write-Host ""
Write-Host "============================================================"
Write-Host "AI Trading Indicator - Arresto sistema"
Write-Host "============================================================"

# Elenca i processi gestiti.
$ProcessFiles = @(
    @{
        Name = "Live Paper Engine"
        File = "live_paper.pid"
    },
    @{
        Name = "FastAPI"
        File = "fastapi.pid"
    },
    @{
        Name = "Frontend Next.js"
        File = "frontend.pid"
    }
)

# Arresta ogni processo registrato.
foreach ($ProcessInformation in $ProcessFiles) {
    $PidPath = Join-Path `
        $PidDirectory `
        $ProcessInformation.File

    # Passa al processo successivo se il PID non esiste.
    if (-not (Test-Path $PidPath)) {
        Write-Host (
            $ProcessInformation.Name +
            ": PID non presente."
        )

        continue
    }

    # Legge il PID.
    $ProcessId = Get-Content `
        $PidPath `
        -Raw

    $ProcessId = $ProcessId.Trim()

    # Verifica che il PID sia numerico.
    if (
        $ProcessId -notmatch "^[0-9]+$"
    ) {
        Write-Host (
            $ProcessInformation.Name +
            ": PID non valido."
        )

        Remove-Item `
            $PidPath `
            -Force `
            -ErrorAction SilentlyContinue

        continue
    }

    # Recupera il processo.
    $SelectedProcess = Get-Process `
        -Id ([int] $ProcessId) `
        -ErrorAction SilentlyContinue

    # Arresta il processo se ancora attivo.
    if ($null -ne $SelectedProcess) {
        Stop-Process `
            -Id ([int] $ProcessId) `
            -Force `
            -ErrorAction SilentlyContinue

        Write-Host (
            $ProcessInformation.Name +
            ": arrestato. PID " +
            $ProcessId
        )
    }
    else {
        Write-Host (
            $ProcessInformation.Name +
            ": processo non attivo."
        )
    }

    # Elimina il file PID.
    Remove-Item `
        $PidPath `
        -Force `
        -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "============================================================"
Write-Host "Arresto completato"
Write-Host "============================================================"