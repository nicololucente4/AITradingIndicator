"""Test del filtro selettivo delle aperture paper."""

# Importa pandas per creare segnali di test.
import pandas as pd

# Importa pytest per verificare gli errori.
import pytest

# Importa filtro, configurazione ed errore.
from src.monitoring.selective_trade_filter import (
    SelectiveTradeFilter,
    SelectiveTradeFilterConfig,
    SelectiveTradeFilterError,
)


def create_signal(
    *,
    signal: str = "LONG",
    confidence: float | None = 0.90,
    probability_margin: float | None = 0.40,
    signal_status: str = "CONFIRMED",
) -> pd.Series:
    """Crea un segnale operativo coerente."""

    if signal == "SHORT":
        entry_price = 1.1000
        stop_loss = 1.1050
        take_profit_1 = 1.0900

    else:
        entry_price = 1.1000
        stop_loss = 1.0950
        take_profit_1 = 1.1100

    return pd.Series(
        {
            "signal_id": "signal-001",
            "signal": signal,
            "signal_status": signal_status,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit_1": take_profit_1,
            "prediction_confidence": (confidence),
            "probability_margin": (probability_margin),
        }
    )


def test_high_confidence_long_is_accepted() -> None:
    """Verifica l'accettazione di un LONG forte."""

    trade_filter = SelectiveTradeFilter()

    decision = trade_filter.evaluate(
        create_signal(
            signal="LONG",
            confidence=0.91,
            probability_margin=0.42,
        )
    )

    assert decision.accepted is True
    assert decision.reason == "HIGH_CONFIDENCE_SIGNAL"
    assert decision.signal == "LONG"


def test_high_confidence_short_is_accepted() -> None:
    """Verifica l'accettazione di uno SHORT forte."""

    trade_filter = SelectiveTradeFilter()

    decision = trade_filter.evaluate(
        create_signal(
            signal="SHORT",
            confidence=0.88,
            probability_margin=0.35,
        )
    )

    assert decision.accepted is True
    assert decision.signal == "SHORT"


def test_low_confidence_is_rejected() -> None:
    """Verifica il rifiuto di una confidenza debole."""

    trade_filter = SelectiveTradeFilter()

    decision = trade_filter.evaluate(
        create_signal(
            confidence=0.79,
            probability_margin=0.50,
        )
    )

    assert decision.accepted is False
    assert decision.reason == "LOW_CONFIDENCE"


def test_low_probability_margin_is_rejected() -> None:
    """Verifica il rifiuto di un margine debole."""

    trade_filter = SelectiveTradeFilter()

    decision = trade_filter.evaluate(
        create_signal(
            confidence=0.95,
            probability_margin=0.19,
        )
    )

    assert decision.accepted is False

    assert decision.reason == "LOW_PROBABILITY_MARGIN"


def test_no_trade_is_rejected() -> None:
    """Verifica che NO_TRADE non apra una posizione."""

    trade_filter = SelectiveTradeFilter()

    decision = trade_filter.evaluate(
        create_signal(
            signal="NO_TRADE",
            confidence=0.70,
            probability_margin=0.12,
        )
    )

    assert decision.accepted is False
    assert decision.reason == "NO_TRADE"


def test_unconfirmed_signal_is_rejected() -> None:
    """Verifica il rifiuto di un segnale non confermato."""

    trade_filter = SelectiveTradeFilter()

    decision = trade_filter.evaluate(
        create_signal(
            signal_status="PENDING",
        )
    )

    assert decision.accepted is False

    assert decision.reason == "SIGNAL_NOT_CONFIRMED"


def test_invalid_long_levels_are_rejected() -> None:
    """Verifica livelli LONG incoerenti."""

    signal = create_signal(signal="LONG")

    signal["stop_loss"] = 1.1050

    trade_filter = SelectiveTradeFilter()

    decision = trade_filter.evaluate(signal)

    assert decision.accepted is False

    assert decision.reason == "INVALID_PRICE_LEVELS"


def test_custom_thresholds_are_applied() -> None:
    """Verifica soglie personalizzate più severe."""

    trade_filter = SelectiveTradeFilter(
        SelectiveTradeFilterConfig(
            minimum_confidence=0.90,
            minimum_probability_margin=0.30,
        )
    )

    decision = trade_filter.evaluate(
        create_signal(
            confidence=0.89,
            probability_margin=0.50,
        )
    )

    assert decision.accepted is False
    assert decision.reason == "LOW_CONFIDENCE"


def test_invalid_configuration_is_rejected() -> None:
    """Verifica il rifiuto di soglie non valide."""

    with pytest.raises(
        SelectiveTradeFilterError,
        match="minimum_confidence",
    ):
        SelectiveTradeFilter(
            SelectiveTradeFilterConfig(
                minimum_confidence=1.10,
            )
        )


def test_missing_margin_is_rejected() -> None:
    """Verifica il rifiuto di un margine assente."""

    trade_filter = SelectiveTradeFilter()

    decision = trade_filter.evaluate(
        create_signal(
            confidence=0.95,
            probability_margin=None,
        )
    )

    assert decision.accepted is False

    assert decision.reason == "MISSING_PROBABILITY_MARGIN"
