"""Esegue Live Paper Engine, Outcome Tracker e statistiche integrate."""

# Importa json per salvare il report finale.
import json

# Importa Path per gestire i percorsi del progetto.
from pathlib import Path

# Importa pandas per creare timestamp e gestire DataFrame.
import pandas as pd

# Importa il provider file in sola lettura.
from src.data.live_provider import FilePollingDataProvider

# Importa il coordinatore Live Paper.
from src.monitoring.live_paper_coordinator import (
    LivePaperCoordinator,
)

# Importa configurazione e Live Paper Engine.
from src.monitoring.live_paper_engine import (
    LivePaperEngine,
    LivePaperEngineConfig,
)

# Importa configurazione e Outcome Tracker.
from src.monitoring.outcome_tracker import (
    OutcomeTracker,
    OutcomeTrackerConfig,
)


def coordinated_demo_processor(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """Genera un segnale dimostrativo sull'ultima candela chiusa."""

    # Recupera esclusivamente l'ultima candela disponibile.
    current_row = dataframe.iloc[[-1]].copy().reset_index(drop=True)

    # Genera un segnale LONG esclusivamente per la demo coordinata.
    current_row["signal"] = "LONG"

    # Il segnale è disponibile solamente a candela chiusa.
    current_row["signal_status"] = "CONFIRMED"

    # Identifica chiaramente la sorgente dimostrativa.
    current_row["signal_source"] = "COORDINATED_DEMO_PROCESSOR"

    # La candela M15 è disponibile quindici minuti dopo l'apertura.
    current_row["signal_available_at"] = current_row["timestamp"] + pd.Timedelta(minutes=15)

    # Utilizza il Close come Entry teorica.
    current_row["entry_price"] = current_row["close"]

    # Definisce livelli sufficientemente vicini per consentire
    # la verifica degli esiti sul piccolo dataset dimostrativo.
    current_row["stop_loss"] = current_row["close"] - 0.0015

    current_row["take_profit_1"] = current_row["close"] + 0.0015

    current_row["take_profit_2"] = current_row["close"] + 0.0030

    current_row["take_profit_3"] = current_row["close"] + 0.0045

    # Aggiunge informazioni dimostrative sulla previsione.
    current_row["prediction_confidence"] = 0.75
    current_row["probability_margin"] = 0.30

    # Registra una versione dimostrativa del processore.
    current_row["model_version"] = "coordinated_demo_0.1.0"

    # Usa un hash dimostrativo della lunghezza prevista.
    current_row["model_sha256"] = "a" * 64

    # Registra la motivazione del segnale.
    current_row["filter_reason"] = "DEMO_SIGNAL"

    # Restituisce il segnale relativo alla candela corrente.
    return current_row


def save_cycle_report(
    report_path: Path,
    poll_time: pd.Timestamp,
    coordinator_report: object,
) -> None:
    """Salva un riepilogo JSON aggiornato dopo ogni ciclo."""

    # Recupera le tre sezioni del report coordinato.
    engine_report = coordinator_report.engine_report
    outcome_report = coordinator_report.outcome_report
    statistics = coordinator_report.statistics

    # Costruisce il report completo del ciclo.
    report_dictionary = {
        "report_version": "coordinated_live_paper_0.1.0",
        "poll_time_utc": poll_time.isoformat(),
        "operating_mode": "LIVE_PAPER",
        "paper_trading_only": True,
        "engine": {
            "new_closed_bars": engine_report.new_closed_bars,
            "total_history_bars": engine_report.total_history_bars,
            "generated_signals": engine_report.generated_signals,
            "inserted_signals": engine_report.inserted_signals,
            "duplicate_signals": engine_report.duplicate_signals,
            "history_ready": engine_report.history_ready,
        },
        "outcomes": {
            "evaluated_signals": outcome_report.evaluated_signals,
            "resolved_signals": outcome_report.resolved_signals,
            "pending_signals": outcome_report.pending_signals,
            "inserted_outcomes": outcome_report.inserted_outcomes,
            "duplicate_outcomes": outcome_report.duplicate_outcomes,
            "ignored_no_trade_signals": (outcome_report.ignored_no_trade_signals),
        },
        "statistics": statistics.to_dict(),
    }

    # Crea la cartella di destinazione.
    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Sovrascrive il report con lo stato più recente.
    report_path.write_text(
        json.dumps(
            report_dictionary,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def main() -> None:
    """Esegue la dimostrazione coordinata completa."""

    # Definisce il dataset CSV sorgente.
    csv_path = Path("data/sample/EURUSD_M15_sample.csv")

    # Definisce il database condiviso.
    database_path = Path("data/live_paper/coordinated_live_paper.db")

    # Definisce il report JSON aggiornato a ogni ciclo.
    report_path = Path("reports/coordinated_live_paper_report.json")

    # Verifica la presenza del dataset.
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
        processor=coordinated_demo_processor,
        config=LivePaperEngineConfig(
            minimum_history_bars=4,
            database_path=str(database_path),
            paper_trading_only=True,
        ),
    )

    # Crea l'Outcome Tracker sul medesimo database.
    outcome_tracker = OutcomeTracker(
        database_path=database_path,
        config=OutcomeTrackerConfig(
            maximum_holding_bars=2,
            stop_first_when_ambiguous=True,
            paper_trading_only=True,
        ),
    )

    # Crea il coordinatore.
    coordinator = LivePaperCoordinator(
        engine=engine,
        outcome_tracker=outcome_tracker,
    )

    # Simula momenti successivi del Live Paper.
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

    # Esegue tutti i cicli coordinati.
    for poll_time in poll_times:
        coordinator_report = coordinator.run_cycle(current_time_utc=poll_time)

        # Salva il report JSON aggiornato.
        save_cycle_report(
            report_path=report_path,
            poll_time=poll_time,
            coordinator_report=coordinator_report,
        )

        # Recupera le sezioni principali.
        engine_report = coordinator_report.engine_report
        outcome_report = coordinator_report.outcome_report
        statistics = coordinator_report.statistics

        # Mostra il riepilogo del ciclo.
        print(f"Polling UTC: {poll_time}")
        print(f"Nuove candele: {engine_report.new_closed_bars}")
        print(f"Segnali inseriti: {engine_report.inserted_signals}")
        print(f"Nuovi esiti: {outcome_report.inserted_outcomes}")
        print(f"Segnali pendenti: {statistics.pending_directional_signals}")
        print(f"Segnali conclusi: {statistics.resolved_directional_signals}")
        print("")

    # Carica segnali ed esiti finali.
    signals = engine.load_signals()
    outcomes = outcome_tracker.load_outcomes()

    # Mostra il riepilogo finale.
    print("Live Paper coordinato completato.")
    print("Modalità: PAPER ONLY")
    print(f"Segnali salvati: {len(signals)}")
    print(f"Esiti salvati: {len(outcomes)}")
    print("")

    # Mostra i segnali.
    if not signals.empty:
        print("Segnali:")
        print(
            signals[
                [
                    "timestamp",
                    "signal",
                    "entry_price",
                    "stop_loss",
                    "take_profit_1",
                    "prediction_confidence",
                ]
            ].to_string(index=False)
        )
        print("")

    # Mostra gli esiti.
    if not outcomes.empty:
        print("Esiti:")
        print(
            outcomes[
                [
                    "signal_id",
                    "direction",
                    "exit_reason",
                    "exit_price",
                    "holding_bars",
                    "result_r",
                ]
            ].to_string(index=False)
        )
        print("")

    # Mostra i percorsi prodotti.
    print(f"Database: {database_path.resolve()}")
    print(f"Report: {report_path.resolve()}")


if __name__ == "__main__":
    # Avvia la demo solamente se eseguita direttamente.
    main()
