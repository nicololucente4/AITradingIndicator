"""Test automatici del Live Paper Engine."""

from pathlib import Path

import pandas as pd
import pytest

from src.data.live_provider import FilePollingDataProvider
from src.monitoring.live_paper_engine import (
    LivePaperEngine,
    LivePaperEngineConfig,
    LivePaperEngineError,
)


def create_csv(
    file_path: Path,
    candle_count: int = 6,
) -> None:
    """Crea un CSV M15 valido."""

    timestamps = pd.date_range(
        start="2026-08-14 10:00:00",
        periods=candle_count,
        freq="15min",
        tz="UTC",
    )

    dataframe = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0 + index for index in range(candle_count)],
            "high": [102.0 + index for index in range(candle_count)],
            "low": [99.0 + index for index in range(candle_count)],
            "close": [101.0 + index for index in range(candle_count)],
            "volume": [100 + index for index in range(candle_count)],
        }
    )

    dataframe.to_csv(
        file_path,
        index=False,
    )


def simple_processor(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """Genera un segnale confermato per l'ultima candela."""

    current_row = dataframe.iloc[[-1]].copy().reset_index(drop=True)

    current_row["signal"] = "LONG"
    current_row["signal_status"] = "CONFIRMED"
    current_row["signal_source"] = "TEST_PROCESSOR"

    current_row["signal_available_at"] = current_row["timestamp"] + pd.Timedelta(minutes=15)

    current_row["entry_price"] = current_row["close"]
    current_row["stop_loss"] = current_row["close"] - 1.0
    current_row["take_profit_1"] = current_row["close"] + 1.0
    current_row["take_profit_2"] = current_row["close"] + 2.0
    current_row["take_profit_3"] = current_row["close"] + 3.0

    current_row["prediction_confidence"] = 0.80
    current_row["probability_margin"] = 0.40
    current_row["model_version"] = "test_model_0.1.0"
    current_row["model_sha256"] = "a" * 64
    current_row["filter_reason"] = "PREDICTION_ACCEPTED"

    return current_row


def create_engine(
    tmp_path: Path,
    minimum_history_bars: int = 2,
) -> LivePaperEngine:
    """Crea un Live Paper Engine temporaneo."""

    csv_path = tmp_path / "market.csv"

    create_csv(csv_path)

    provider = FilePollingDataProvider(
        file_path=csv_path,
        timeframe_minutes=15,
    )

    return LivePaperEngine(
        provider=provider,
        processor=simple_processor,
        config=LivePaperEngineConfig(
            minimum_history_bars=minimum_history_bars,
            database_path=str(tmp_path / "live_paper.db"),
            paper_trading_only=True,
        ),
    )


def test_database_is_created(
    tmp_path: Path,
) -> None:
    """Verifica la creazione del database SQLite."""

    engine = create_engine(tmp_path)

    assert engine.database_path.exists()


def test_no_signal_before_minimum_history(
    tmp_path: Path,
) -> None:
    """Verifica il warm-up dello storico."""

    engine = create_engine(
        tmp_path,
        minimum_history_bars=4,
    )

    report = engine.run_cycle(
        pd.Timestamp(
            "2026-08-14 10:30:00",
            tz="UTC",
        )
    )

    assert report.total_history_bars == 2
    assert report.history_ready is False
    assert report.generated_signals == 0
    assert engine.load_signals().empty


def test_signal_is_generated_when_history_is_ready(
    tmp_path: Path,
) -> None:
    """Verifica la generazione e il salvataggio del segnale."""

    engine = create_engine(
        tmp_path,
        minimum_history_bars=2,
    )

    report = engine.run_cycle(
        pd.Timestamp(
            "2026-08-14 10:30:00",
            tz="UTC",
        )
    )

    assert report.history_ready is True
    assert report.generated_signals == 1
    assert report.inserted_signals == 1

    signals = engine.load_signals()

    assert len(signals) == 1
    assert signals.loc[0, "signal"] == "LONG"
    assert signals.loc[0, "operating_mode"] == "LIVE_PAPER"


def test_same_poll_does_not_create_duplicate_signal(
    tmp_path: Path,
) -> None:
    """Verifica che un polling ripetuto non generi duplicati."""

    engine = create_engine(
        tmp_path,
        minimum_history_bars=2,
    )

    selected_time = pd.Timestamp(
        "2026-08-14 10:30:00",
        tz="UTC",
    )

    first_report = engine.run_cycle(selected_time)

    second_report = engine.run_cycle(selected_time)

    assert first_report.inserted_signals == 1
    assert second_report.new_closed_bars == 0
    assert second_report.generated_signals == 0
    assert len(engine.load_signals()) == 1


def test_next_closed_candle_creates_new_signal(
    tmp_path: Path,
) -> None:
    """Verifica il salvataggio del segnale successivo."""

    engine = create_engine(
        tmp_path,
        minimum_history_bars=2,
    )

    engine.run_cycle(
        pd.Timestamp(
            "2026-08-14 10:30:00",
            tz="UTC",
        )
    )

    report = engine.run_cycle(
        pd.Timestamp(
            "2026-08-14 10:45:00",
            tz="UTC",
        )
    )

    assert report.new_closed_bars == 1
    assert report.inserted_signals == 1
    assert len(engine.load_signals()) == 2


def test_history_does_not_contain_duplicates(
    tmp_path: Path,
) -> None:
    """Verifica l'unicità delle candele nello storico."""

    engine = create_engine(
        tmp_path,
        minimum_history_bars=2,
    )

    engine.run_cycle(
        pd.Timestamp(
            "2026-08-14 10:30:00",
            tz="UTC",
        )
    )

    engine.run_cycle(
        pd.Timestamp(
            "2026-08-14 10:45:00",
            tz="UTC",
        )
    )

    history = engine.history

    assert not history["timestamp"].duplicated().any()
    assert len(history) == 3


def test_unconfirmed_signal_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il blocco dei segnali non confermati."""

    csv_path = tmp_path / "market.csv"

    create_csv(csv_path)

    provider = FilePollingDataProvider(
        file_path=csv_path,
        timeframe_minutes=15,
    )

    def invalid_processor(
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """Crea intenzionalmente un segnale non confermato."""

        result = simple_processor(dataframe)
        result["signal_status"] = "PRE_SIGNAL"

        return result

    engine = LivePaperEngine(
        provider=provider,
        processor=invalid_processor,
        config=LivePaperEngineConfig(
            minimum_history_bars=2,
            database_path=str(tmp_path / "invalid.db"),
            paper_trading_only=True,
        ),
    )

    with pytest.raises(
        LivePaperEngineError,
        match="solamente segnali confermati",
    ):
        engine.run_cycle(
            pd.Timestamp(
                "2026-08-14 10:30:00",
                tz="UTC",
            )
        )


def test_invalid_configuration_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il rifiuto della modalità non paper."""

    csv_path = tmp_path / "market.csv"

    create_csv(csv_path)

    provider = FilePollingDataProvider(
        file_path=csv_path,
        timeframe_minutes=15,
    )

    with pytest.raises(
        LivePaperEngineError,
        match="paper_trading_only",
    ):
        LivePaperEngine(
            provider=provider,
            processor=simple_processor,
            config=LivePaperEngineConfig(
                minimum_history_bars=2,
                database_path=str(tmp_path / "real.db"),
                paper_trading_only=False,
            ),
        )
