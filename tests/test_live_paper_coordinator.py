"""Test automatici del coordinatore Live Paper."""

from pathlib import Path

import pandas as pd
import pytest

from src.data.live_provider import FilePollingDataProvider
from src.monitoring.live_paper_coordinator import (
    LivePaperCoordinator,
    LivePaperCoordinatorError,
)
from src.monitoring.live_paper_engine import (
    LivePaperEngine,
    LivePaperEngineConfig,
)
from src.monitoring.outcome_tracker import (
    OutcomeTracker,
    OutcomeTrackerConfig,
)


def create_csv(
    file_path: Path,
) -> None:
    """Crea un dataset M15 con successivo Take Profit."""

    # Genera sei timestamp M15 consecutivi.
    timestamps = pd.date_range(
        start="2026-08-14 10:00:00",
        periods=6,
        freq="15min",
        tz="UTC",
    )

    # Crea un dataset OHLCV valido.
    dataframe = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [
                100.0,
                100.5,
                101.0,
                101.5,
                102.0,
                102.5,
            ],
            "high": [
                101.0,
                101.5,
                102.0,
                102.5,
                103.0,
                103.5,
            ],
            "low": [
                99.5,
                100.0,
                100.5,
                101.0,
                101.5,
                102.0,
            ],
            "close": [
                100.5,
                101.0,
                101.5,
                102.0,
                102.5,
                103.0,
            ],
            "volume": [
                100,
                110,
                120,
                130,
                140,
                150,
            ],
        }
    )

    # Salva il dataset nel file temporaneo.
    dataframe.to_csv(
        file_path,
        index=False,
    )


def simple_processor(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """Genera un segnale LONG sull'ultima candela."""

    # Recupera l'ultima candela disponibile.
    current_row = dataframe.iloc[[-1]].copy().reset_index(drop=True)

    # Imposta il segnale confermato.
    current_row["signal"] = "LONG"
    current_row["signal_status"] = "CONFIRMED"
    current_row["signal_source"] = "COORDINATOR_TEST"

    # Il segnale è disponibile alla chiusura della candela.
    current_row["signal_available_at"] = current_row["timestamp"] + pd.Timedelta(minutes=15)

    # Definisce Entry, Stop Loss e Take Profit.
    current_row["entry_price"] = current_row["close"]

    current_row["stop_loss"] = current_row["close"] - 1.0

    current_row["take_profit_1"] = current_row["close"] + 1.0

    current_row["take_profit_2"] = current_row["close"] + 2.0

    current_row["take_profit_3"] = current_row["close"] + 3.0

    # Aggiunge dati di audit.
    current_row["prediction_confidence"] = 0.80
    current_row["probability_margin"] = 0.30
    current_row["model_version"] = "test_model_0.1.0"
    current_row["model_sha256"] = "a" * 64
    current_row["filter_reason"] = "PREDICTION_ACCEPTED"

    # Restituisce il segnale corrente.
    return current_row


def create_coordinator(
    tmp_path: Path,
    minimum_history_bars: int = 2,
) -> LivePaperCoordinator:
    """Crea un coordinatore temporaneo."""

    # Crea il file CSV.
    csv_path = tmp_path / "market.csv"
    create_csv(csv_path)

    # Definisce un database condiviso.
    database_path = tmp_path / "live_paper.db"

    # Crea il provider.
    provider = FilePollingDataProvider(
        file_path=csv_path,
        timeframe_minutes=15,
    )

    # Crea il Live Paper Engine.
    engine = LivePaperEngine(
        provider=provider,
        processor=simple_processor,
        config=LivePaperEngineConfig(
            minimum_history_bars=minimum_history_bars,
            database_path=str(database_path),
            paper_trading_only=True,
        ),
    )

    # Crea l'Outcome Tracker sullo stesso database.
    tracker = OutcomeTracker(
        database_path=database_path,
        config=OutcomeTrackerConfig(
            maximum_holding_bars=2,
            stop_first_when_ambiguous=True,
            paper_trading_only=True,
        ),
    )

    # Restituisce il coordinatore.
    return LivePaperCoordinator(
        engine=engine,
        outcome_tracker=tracker,
    )


def test_cycle_generates_signal_and_statistics(
    tmp_path: Path,
) -> None:
    """Verifica segnale e statistiche dello stesso ciclo."""

    # Crea il coordinatore.
    coordinator = create_coordinator(tmp_path)

    # Esegue il primo ciclo con due candele chiuse.
    report = coordinator.run_cycle(
        pd.Timestamp(
            "2026-08-14 10:30:00",
            tz="UTC",
        )
    )

    # Deve essere generato un segnale.
    assert report.engine_report.inserted_signals == 1

    # Il segnale è ancora pendente.
    assert report.statistics.total_signals == 1
    assert report.statistics.directional_signals == 1
    assert report.statistics.pending_directional_signals == 1


def test_next_candle_can_resolve_previous_signal(
    tmp_path: Path,
) -> None:
    """Verifica la risoluzione di un segnale precedente."""

    # Crea il coordinatore.
    coordinator = create_coordinator(tmp_path)

    # Genera il primo segnale.
    coordinator.run_cycle(
        pd.Timestamp(
            "2026-08-14 10:30:00",
            tz="UTC",
        )
    )

    # Aggiunge le candele chiuse successive.
    report = coordinator.run_cycle(
        pd.Timestamp(
            "2026-08-14 11:00:00",
            tz="UTC",
        )
    )

    # Deve essere presente almeno un esito conclusivo.
    assert report.statistics.resolved_directional_signals >= 1

    # Il tasso di risoluzione deve essere maggiore di zero.
    assert report.statistics.resolution_rate_percentage > 0.0


def test_no_new_bar_does_not_generate_new_signal(
    tmp_path: Path,
) -> None:
    """Verifica il comportamento senza nuove candele."""

    # Crea il coordinatore.
    coordinator = create_coordinator(tmp_path)

    # Esegue il primo ciclo.
    selected_time = pd.Timestamp(
        "2026-08-14 10:30:00",
        tz="UTC",
    )

    first_report = coordinator.run_cycle(selected_time)

    # Ripete il polling allo stesso momento.
    second_report = coordinator.run_cycle(selected_time)

    # Solo il primo ciclo deve generare un segnale.
    assert first_report.engine_report.inserted_signals == 1
    assert second_report.engine_report.new_closed_bars == 0
    assert second_report.engine_report.inserted_signals == 0

    # Il numero totale dei segnali deve restare invariato.
    assert second_report.statistics.total_signals == 1


def test_shared_database_is_required(
    tmp_path: Path,
) -> None:
    """Verifica che Engine e Tracker usino lo stesso database."""

    # Crea il CSV.
    csv_path = tmp_path / "market.csv"
    create_csv(csv_path)

    # Crea il provider.
    provider = FilePollingDataProvider(
        file_path=csv_path,
        timeframe_minutes=15,
    )

    # Crea il motore sul primo database.
    engine = LivePaperEngine(
        provider=provider,
        processor=simple_processor,
        config=LivePaperEngineConfig(
            minimum_history_bars=2,
            database_path=str(tmp_path / "engine.db"),
        ),
    )

    # Crea il tracker su un database differente.
    tracker = OutcomeTracker(database_path=(tmp_path / "tracker.db"))

    # Il coordinatore deve rifiutare la configurazione.
    with pytest.raises(
        LivePaperCoordinatorError,
        match="stesso database",
    ):
        LivePaperCoordinator(
            engine=engine,
            outcome_tracker=tracker,
        )


def test_timezone_naive_cycle_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il rifiuto di un timestamp senza timezone."""

    # Crea il coordinatore.
    coordinator = create_coordinator(tmp_path)

    # Esegue il ciclo con un timestamp non timezone-aware.
    with pytest.raises(
        LivePaperCoordinatorError,
        match="timezone",
    ):
        coordinator.run_cycle(pd.Timestamp("2026-08-14 10:30:00"))


def test_statistics_remain_paper_only(
    tmp_path: Path,
) -> None:
    """Verifica il vincolo PAPER_ONLY."""

    # Crea il coordinatore.
    coordinator = create_coordinator(tmp_path)

    # Esegue un ciclo.
    report = coordinator.run_cycle(
        pd.Timestamp(
            "2026-08-14 10:30:00",
            tz="UTC",
        )
    )

    # Le statistiche devono dichiarare il paper trading.
    assert report.statistics.paper_trading_only is True
