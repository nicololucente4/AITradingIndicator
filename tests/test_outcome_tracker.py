"""Test automatici dell'Outcome Tracker."""

# Importa Path per gestire i database temporanei dei test.
from pathlib import Path

# Importa pandas per creare segnali e dataset OHLCV.
import pandas as pd

# Importa pytest per verificare gli errori attesi.
import pytest

# Importa il tracker, la configurazione e il relativo errore.
from src.monitoring.outcome_tracker import (
    OutcomeTracker,
    OutcomeTrackerConfig,
    OutcomeTrackerError,
)


def create_market_data() -> pd.DataFrame:
    """Crea candele future M15 deterministiche."""

    # Genera cinque timestamp consecutivi da quindici minuti.
    timestamps = pd.date_range(
        start="2026-08-14 10:15:00",
        periods=5,
        freq="15min",
        tz="UTC",
    )

    # Restituisce un dataset OHLCV valido.
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [
                100.0,
                101.0,
                102.0,
                103.0,
                104.0,
            ],
            "high": [
                101.0,
                103.0,
                103.0,
                104.0,
                105.0,
            ],
            "low": [
                99.0,
                100.0,
                101.0,
                102.0,
                103.0,
            ],
            "close": [
                100.5,
                102.0,
                102.5,
                103.5,
                104.5,
            ],
            "volume": [
                100,
                110,
                120,
                130,
                140,
            ],
        }
    )


def create_signal(
    signal: str = "LONG",
) -> pd.DataFrame:
    """Crea un segnale confermato."""

    # Restituisce un segnale LONG, SHORT oppure NO_TRADE.
    return pd.DataFrame(
        {
            "signal_id": [
                "signal-001",
            ],
            "timestamp": [
                pd.Timestamp(
                    "2026-08-14 10:00:00",
                    tz="UTC",
                ),
            ],
            "signal_available_at": [
                pd.Timestamp(
                    "2026-08-14 10:15:00",
                    tz="UTC",
                ),
            ],
            "signal": [
                signal,
            ],
            "signal_status": [
                "CONFIRMED",
            ],
            "entry_price": [
                100.0 if signal != "SHORT" else 102.0,
            ],
            "stop_loss": [
                98.0 if signal != "SHORT" else 104.0,
            ],
            "take_profit_1": [
                102.0 if signal != "SHORT" else 100.0,
            ],
        }
    )


def create_tracker(
    tmp_path: Path,
    maximum_holding_bars: int = 4,
) -> OutcomeTracker:
    """Crea un Outcome Tracker temporaneo."""

    # Restituisce un tracker isolato per ciascun test.
    return OutcomeTracker(
        database_path=(tmp_path / "outcomes.db"),
        config=OutcomeTrackerConfig(
            maximum_holding_bars=maximum_holding_bars,
            stop_first_when_ambiguous=True,
            paper_trading_only=True,
        ),
    )


def test_take_profit_is_recorded(
    tmp_path: Path,
) -> None:
    """Verifica la registrazione del Take Profit."""

    # Crea il tracker.
    tracker = create_tracker(tmp_path)

    # Valuta il segnale LONG.
    report = tracker.evaluate(
        signals=create_signal("LONG"),
        market_data=create_market_data(),
        evaluated_at_utc=pd.Timestamp(
            "2026-08-14 12:00:00",
            tz="UTC",
        ),
    )

    # Verifica il report della valutazione.
    assert report.resolved_signals == 1
    assert report.inserted_outcomes == 1

    # Carica l'esito dal database.
    outcomes = tracker.load_outcomes()

    # Verifica Take Profit e prezzo di uscita.
    assert len(outcomes) == 1
    assert outcomes.loc[0, "exit_reason"] == "TAKE_PROFIT_1"
    assert outcomes.loc[0, "exit_price"] == 102.0


def test_stop_loss_is_recorded(
    tmp_path: Path,
) -> None:
    """Verifica la registrazione dello Stop Loss."""

    # Crea il tracker.
    tracker = create_tracker(tmp_path)

    # Crea il dataset e forza il raggiungimento dello Stop Loss.
    market_data = create_market_data()
    market_data.loc[0, "low"] = 97.5

    # Valuta il segnale.
    tracker.evaluate(
        signals=create_signal("LONG"),
        market_data=market_data,
        evaluated_at_utc=pd.Timestamp(
            "2026-08-14 12:00:00",
            tz="UTC",
        ),
    )

    # Carica l'esito.
    outcomes = tracker.load_outcomes()

    # Verifica lo Stop Loss.
    assert outcomes.loc[0, "exit_reason"] == "STOP_LOSS"
    assert outcomes.loc[0, "exit_price"] == 98.0


def test_ambiguous_candle_uses_stop_loss(
    tmp_path: Path,
) -> None:
    """Verifica la gestione conservativa intrabar."""

    # Crea il tracker.
    tracker = create_tracker(tmp_path)

    # La prima candela raggiunge sia Stop Loss sia Take Profit.
    market_data = create_market_data()
    market_data.loc[0, "low"] = 97.5
    market_data.loc[0, "high"] = 102.5

    # Valuta il segnale.
    tracker.evaluate(
        signals=create_signal("LONG"),
        market_data=market_data,
        evaluated_at_utc=pd.Timestamp(
            "2026-08-14 12:00:00",
            tz="UTC",
        ),
    )

    # Carica l'esito.
    outcomes = tracker.load_outcomes()

    # Deve prevalere lo Stop Loss.
    assert outcomes.loc[0, "exit_reason"] == ("STOP_LOSS_AMBIGUOUS")

    assert outcomes.loc[0, "exit_price"] == 98.0


def test_pending_signal_is_not_inserted(
    tmp_path: Path,
) -> None:
    """Verifica un segnale ancora in attesa."""

    # Configura un orizzonte massimo di quattro candele.
    tracker = create_tracker(
        tmp_path,
        maximum_holding_bars=4,
    )

    # Mantiene solamente una candela futura.
    market_data = create_market_data().iloc[:1].copy()

    # La candela non raggiunge né Stop Loss né Take Profit.
    market_data["high"] = 101.0
    market_data["low"] = 99.0
    market_data["close"] = 100.5

    # Valuta il segnale.
    report = tracker.evaluate(
        signals=create_signal("LONG"),
        market_data=market_data,
        evaluated_at_utc=pd.Timestamp(
            "2026-08-14 10:30:00",
            tz="UTC",
        ),
    )

    # Il segnale deve restare pendente.
    assert report.pending_signals == 1
    assert report.inserted_outcomes == 0
    assert tracker.load_outcomes().empty


def test_time_expiry_is_recorded(
    tmp_path: Path,
) -> None:
    """Verifica la chiusura per scadenza temporale."""

    # Configura una scadenza dopo tre candele.
    tracker = create_tracker(
        tmp_path,
        maximum_holding_bars=3,
    )

    # Crea tre candele OHLCV matematicamente coerenti.
    # Nessuna candela raggiunge SL 98 oppure TP 102.
    market_data = pd.DataFrame(
        {
            "timestamp": pd.date_range(
                start="2026-08-14 10:15:00",
                periods=3,
                freq="15min",
                tz="UTC",
            ),
            "open": [
                100.0,
                100.5,
                101.0,
            ],
            "high": [
                101.0,
                101.5,
                101.8,
            ],
            "low": [
                99.0,
                99.5,
                100.0,
            ],
            "close": [
                100.5,
                101.0,
                101.5,
            ],
            "volume": [
                100,
                110,
                120,
            ],
        }
    )

    # Valuta il segnale.
    tracker.evaluate(
        signals=create_signal("LONG"),
        market_data=market_data,
        evaluated_at_utc=pd.Timestamp(
            "2026-08-14 12:00:00",
            tz="UTC",
        ),
    )

    # Carica l'esito.
    outcomes = tracker.load_outcomes()

    # Verifica la chiusura per scadenza.
    assert len(outcomes) == 1
    assert outcomes.loc[0, "exit_reason"] == "TIME_EXPIRY"
    assert outcomes.loc[0, "holding_bars"] == 3

    # Alla scadenza viene utilizzato il Close dell'ultima candela.
    assert outcomes.loc[0, "exit_price"] == 101.5


def test_existing_outcome_is_not_overwritten(
    tmp_path: Path,
) -> None:
    """Verifica l'immutabilità degli esiti."""

    # Crea il tracker.
    tracker = create_tracker(tmp_path)

    # Registra il primo esito.
    first_report = tracker.evaluate(
        signals=create_signal("LONG"),
        market_data=create_market_data(),
        evaluated_at_utc=pd.Timestamp(
            "2026-08-14 12:00:00",
            tz="UTC",
        ),
    )

    # Modifica successivamente il mercato per simulare un esito differente.
    changed_market_data = create_market_data()
    changed_market_data.loc[0, "low"] = 97.0

    # Rivaluta lo stesso segnale.
    second_report = tracker.evaluate(
        signals=create_signal("LONG"),
        market_data=changed_market_data,
        evaluated_at_utc=pd.Timestamp(
            "2026-08-14 13:00:00",
            tz="UTC",
        ),
    )

    # Il primo esito deve essere inserito.
    assert first_report.inserted_outcomes == 1

    # Il secondo tentativo deve essere considerato duplicato.
    assert second_report.duplicate_outcomes == 1

    # Il database deve contenere ancora un solo esito.
    outcomes = tracker.load_outcomes()

    assert len(outcomes) == 1
    assert outcomes.loc[0, "exit_reason"] == "TAKE_PROFIT_1"


def test_no_trade_is_ignored(
    tmp_path: Path,
) -> None:
    """Verifica che NO_TRADE non produca esiti."""

    # Crea il tracker.
    tracker = create_tracker(tmp_path)

    # Valuta un segnale NO_TRADE.
    report = tracker.evaluate(
        signals=create_signal("NO_TRADE"),
        market_data=create_market_data(),
        evaluated_at_utc=pd.Timestamp(
            "2026-08-14 12:00:00",
            tz="UTC",
        ),
    )

    # Il segnale deve essere ignorato.
    assert report.ignored_no_trade_signals == 1
    assert report.evaluated_signals == 0
    assert tracker.load_outcomes().empty


def test_invalid_configuration_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il rifiuto della modalità non paper."""

    # La modalità non paper deve essere bloccata.
    with pytest.raises(
        OutcomeTrackerError,
        match="paper_trading_only",
    ):
        OutcomeTracker(
            database_path=tmp_path / "invalid.db",
            config=OutcomeTrackerConfig(
                maximum_holding_bars=4,
                paper_trading_only=False,
            ),
        )
