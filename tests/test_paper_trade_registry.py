"""Test del registro persistente delle operazioni paper."""

# Importa Path per il database temporaneo.
from pathlib import Path

# Importa pandas per creare segnali ed esiti.
import pandas as pd

# Importa pytest per verificare gli errori.
import pytest

# Importa configurazione, registro ed errore.
from src.monitoring.paper_trade_registry import (
    PaperTradeRegistry,
    PaperTradeRegistryConfig,
    PaperTradeRegistryError,
)


def create_signals() -> pd.DataFrame:
    """Crea segnali direzionali e NO_TRADE."""

    return pd.DataFrame(
        [
            {
                "signal_id": "signal-001",
                "timestamp": ("2026-08-25T08:00:00+00:00"),
                "signal": "LONG",
                "signal_status": "CONFIRMED",
                "entry_price": 1.1000,
                "stop_loss": 1.0950,
                "take_profit_1": 1.1100,
                "prediction_confidence": 0.91,
                "model_version": "model-0.2.0",
            },
            {
                "signal_id": "signal-002",
                "timestamp": ("2026-08-25T08:15:00+00:00"),
                "signal": "SHORT",
                "signal_status": "CONFIRMED",
                "entry_price": 1.1010,
                "stop_loss": 1.1060,
                "take_profit_1": 1.0910,
                "prediction_confidence": 0.88,
                "model_version": "model-0.2.0",
            },
            {
                "signal_id": "signal-003",
                "timestamp": ("2026-08-25T08:30:00+00:00"),
                "signal": "NO_TRADE",
                "signal_status": "CONFIRMED",
                "entry_price": None,
                "stop_loss": None,
                "take_profit_1": None,
                "prediction_confidence": 0.55,
                "model_version": "model-0.2.0",
            },
        ]
    )


def create_outcomes() -> pd.DataFrame:
    """Crea l'esito del primo segnale."""

    return pd.DataFrame(
        [
            {
                "signal_id": "signal-001",
                "direction": "LONG",
                "exit_price": 1.1100,
                "exit_reason": "TAKE_PROFIT_1",
                "exit_timestamp": ("2026-08-25T09:00:00+00:00"),
                "holding_bars": 4,
                "gross_return_percentage": (0.009090909),
                "result_r": 2.0,
            }
        ]
    )


def create_registry(
    tmp_path: Path,
) -> PaperTradeRegistry:
    """Crea un registro temporaneo EURUSD M15."""

    return PaperTradeRegistry(
        tmp_path / "live_paper.db",
        config=PaperTradeRegistryConfig(
            symbol="EURUSD",
            timeframe="M15",
        ),
    )


def test_directional_signal_opens_trade(
    tmp_path: Path,
) -> None:
    """Verifica l'apertura di una posizione paper."""

    registry = create_registry(tmp_path)

    report = registry.synchronize(
        signals=create_signals().iloc[[0]],
        outcomes=pd.DataFrame(),
        synchronized_at_utc=pd.Timestamp(
            "2026-08-25 08:01:00",
            tz="UTC",
        ),
    )

    trades = registry.load_trades()

    assert report.opened_trades == 1
    assert report.closed_trades == 0
    assert len(trades) == 1
    assert trades.iloc[0]["status"] == "OPEN"
    assert trades.iloc[0]["symbol"] == "EURUSD"
    assert trades.iloc[0]["timeframe"] == "M15"
    assert trades.iloc[0]["direction"] == "LONG"

    assert str(trades.iloc[0]["trade_id"]).startswith("TRD-EURUSD-M15-")


def test_outcome_closes_existing_trade(
    tmp_path: Path,
) -> None:
    """Verifica la chiusura tramite outcome."""

    registry = create_registry(tmp_path)

    first_signal = create_signals().iloc[[0]]

    registry.synchronize(
        signals=first_signal,
        outcomes=pd.DataFrame(),
        synchronized_at_utc=pd.Timestamp(
            "2026-08-25 08:01:00",
            tz="UTC",
        ),
    )

    report = registry.synchronize(
        signals=first_signal,
        outcomes=create_outcomes(),
        synchronized_at_utc=pd.Timestamp(
            "2026-08-25 09:01:00",
            tz="UTC",
        ),
    )

    trades = registry.load_trades()

    assert report.closed_trades == 1
    assert len(trades) == 1
    assert trades.iloc[0]["status"] == "CLOSED"
    assert trades.iloc[0]["exit_reason"] == "TAKE_PROFIT_1"
    assert trades.iloc[0]["result_r"] == 2.0


def test_no_trade_does_not_open_position(
    tmp_path: Path,
) -> None:
    """Verifica che NO_TRADE non apra operazioni."""

    registry = create_registry(tmp_path)

    report = registry.synchronize(
        signals=create_signals().iloc[[2]],
        outcomes=pd.DataFrame(),
        synchronized_at_utc=pd.Timestamp(
            "2026-08-25 08:31:00",
            tz="UTC",
        ),
    )

    assert report.ignored_no_trade == 1
    assert registry.load_trades().empty


def test_second_open_trade_is_blocked(
    tmp_path: Path,
) -> None:
    """Verifica una sola operazione aperta per simbolo."""

    registry = create_registry(tmp_path)

    report = registry.synchronize(
        signals=create_signals().iloc[[0, 1]],
        outcomes=pd.DataFrame(),
        synchronized_at_utc=pd.Timestamp(
            "2026-08-25 08:16:00",
            tz="UTC",
        ),
    )

    trades = registry.load_trades()

    assert report.opened_trades == 1
    assert report.ignored_open_position == 1
    assert len(trades) == 1
    assert trades.iloc[0]["signal_id"] == "signal-001"


def test_trade_id_is_stable_after_restart(
    tmp_path: Path,
) -> None:
    """Verifica la stabilità del trade_id."""

    database_path = tmp_path / "live_paper.db"

    first_registry = PaperTradeRegistry(database_path)

    first_registry.synchronize(
        signals=create_signals().iloc[[0]],
        outcomes=pd.DataFrame(),
        synchronized_at_utc=pd.Timestamp(
            "2026-08-25 08:01:00",
            tz="UTC",
        ),
    )

    first_trade_id = str(first_registry.load_trades().iloc[0]["trade_id"])

    restarted_registry = PaperTradeRegistry(database_path)

    restarted_registry.synchronize(
        signals=create_signals().iloc[[0]],
        outcomes=pd.DataFrame(),
        synchronized_at_utc=pd.Timestamp(
            "2026-08-25 08:02:00",
            tz="UTC",
        ),
    )

    restarted_trades = restarted_registry.load_trades()

    assert len(restarted_trades) == 1

    assert str(restarted_trades.iloc[0]["trade_id"]) == first_trade_id


def test_trade_can_open_after_previous_close(
    tmp_path: Path,
) -> None:
    """Verifica una nuova apertura dopo la chiusura."""

    registry = create_registry(tmp_path)

    signals = create_signals()

    registry.synchronize(
        signals=signals.iloc[[0]],
        outcomes=pd.DataFrame(),
        synchronized_at_utc=pd.Timestamp(
            "2026-08-25 08:01:00",
            tz="UTC",
        ),
    )

    registry.synchronize(
        signals=signals.iloc[[0]],
        outcomes=create_outcomes(),
        synchronized_at_utc=pd.Timestamp(
            "2026-08-25 09:01:00",
            tz="UTC",
        ),
    )

    report = registry.synchronize(
        signals=signals.iloc[[0, 1]],
        outcomes=create_outcomes(),
        synchronized_at_utc=pd.Timestamp(
            "2026-08-25 09:02:00",
            tz="UTC",
        ),
    )

    trades = registry.load_trades()

    assert report.opened_trades == 1
    assert len(trades) == 2

    assert len(registry.load_open_trades()) == 1

    assert registry.load_open_trades().iloc[0]["signal_id"] == "signal-002"


def test_naive_sync_timestamp_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il rifiuto di timestamp senza timezone."""

    registry = create_registry(tmp_path)

    with pytest.raises(
        PaperTradeRegistryError,
        match="timezone",
    ):
        registry.synchronize(
            signals=create_signals(),
            outcomes=pd.DataFrame(),
            synchronized_at_utc=pd.Timestamp("2026-08-25 08:00:00"),
        )
