"""Dimostrazione locale del Live Paper Engine con provider file."""

# Importa Path per gestire il percorso del CSV.
from pathlib import Path

# Importa pandas per timestamp e DataFrame.
import pandas as pd

# Importa il provider file in sola lettura.
from src.data.live_provider import FilePollingDataProvider

# Importa configurazione e Live Paper Engine.
from src.monitoring.live_paper_engine import (
    LivePaperEngine,
    LivePaperEngineConfig,
)


def demo_processor(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """Genera un segnale dimostrativo sull'ultima candela chiusa."""

    # Recupera esclusivamente l'ultima candela disponibile.
    current_row = dataframe.iloc[[-1]].copy().reset_index(drop=True)

    # Genera un segnale LONG esclusivamente dimostrativo.
    current_row["signal"] = "LONG"

    # Il segnale è prodotto solamente a candela chiusa.
    current_row["signal_status"] = "CONFIRMED"

    # Identifica chiaramente la sorgente dimostrativa.
    current_row["signal_source"] = "DEMO_PROCESSOR"

    # Il segnale diventa disponibile quindici minuti dopo l'apertura.
    current_row["signal_available_at"] = current_row["timestamp"] + pd.Timedelta(minutes=15)

    # Utilizza il Close come Entry teorica.
    current_row["entry_price"] = current_row["close"]

    # Definisce livelli teorici esclusivamente per la demo.
    current_row["stop_loss"] = current_row["close"] - 0.0030

    current_row["take_profit_1"] = current_row["close"] + 0.0030

    current_row["take_profit_2"] = current_row["close"] + 0.0060

    current_row["take_profit_3"] = current_row["close"] + 0.0090

    # Aggiunge informazioni dimostrative di confidenza.
    current_row["prediction_confidence"] = 0.75
    current_row["probability_margin"] = 0.30

    # Identifica la versione dimostrativa.
    current_row["model_version"] = "demo_processor_0.1.0"

    # Usa un hash fittizio valido come lunghezza per la demo.
    current_row["model_sha256"] = "a" * 64

    # Registra la motivazione.
    current_row["filter_reason"] = "DEMO_SIGNAL"

    # Restituisce la singola riga elaborata.
    return current_row


def main() -> None:
    """Esegue diversi cicli Live Paper sul CSV locale."""

    # Definisce il CSV utilizzato come sorgente simulata.
    csv_path = Path("data/sample/EURUSD_M15_sample.csv")

    # Definisce il database locale della demo.
    database_path = Path("data/live_paper/demo_live_paper.db")

    # Verifica che il CSV sia presente.
    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset dimostrativo non trovato: {csv_path}.")

    # Crea il provider file in sola lettura.
    provider = FilePollingDataProvider(
        file_path=csv_path,
        timeframe_minutes=15,
    )

    # Crea il Live Paper Engine.
    engine = LivePaperEngine(
        provider=provider,
        processor=demo_processor,
        config=LivePaperEngineConfig(
            minimum_history_bars=4,
            database_path=str(database_path),
            paper_trading_only=True,
        ),
    )

    # Simula quattro polling progressivi.
    poll_times = [
        pd.Timestamp(
            "2026-08-13 08:30:00",
            tz="UTC",
        ),
        pd.Timestamp(
            "2026-08-13 09:00:00",
            tz="UTC",
        ),
        pd.Timestamp(
            "2026-08-13 09:15:00",
            tz="UTC",
        ),
        pd.Timestamp(
            "2026-08-13 09:30:00",
            tz="UTC",
        ),
    ]

    # Esegue i cicli Live Paper.
    for poll_time in poll_times:
        cycle_report = engine.run_cycle(current_time_utc=poll_time)

        # Mostra il risultato del singolo ciclo.
        print(f"Polling: {cycle_report.polled_at_utc}")
        print(f"Nuove candele chiuse: {cycle_report.new_closed_bars}")
        print(f"Candele nello storico: {cycle_report.total_history_bars}")
        print(f"Storico pronto: {cycle_report.history_ready}")
        print(f"Segnali generati: {cycle_report.generated_signals}")
        print(f"Segnali inseriti: {cycle_report.inserted_signals}")
        print("")

    # Carica i segnali salvati nel database.
    signals = engine.load_signals()

    # Mostra il riepilogo finale.
    print("Live Paper demo completata.")
    print("Modalità: PAPER ONLY")
    print("Provider: FILE_POLLING")
    print(f"Segnali salvati: {len(signals)}")
    print("")

    # Mostra i segnali se disponibili.
    if not signals.empty:
        display_columns = [
            "timestamp",
            "signal_available_at",
            "signal",
            "close_price",
            "entry_price",
            "stop_loss",
            "take_profit_1",
            "prediction_confidence",
            "model_version",
        ]

        print(signals[display_columns].to_string(index=False))

    print("")
    print(f"Database: {engine.database_path.resolve()}")


if __name__ == "__main__":
    # Avvia la demo solamente quando eseguita direttamente.
    main()
