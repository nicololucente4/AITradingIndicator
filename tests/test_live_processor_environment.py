"""Test delle soglie Live ML configurate tramite ambiente."""

# Importa pytest per verificare gli errori.
import pytest

# Importa configurazione ed errore.
from src.monitoring.live_processor import (
    LiveMLProcessorConfig,
    LiveMLProcessorError,
)


def test_default_thresholds_are_preserved(
    monkeypatch,
) -> None:
    """Verifica i valori predefiniti senza variabili."""

    # Rimuove eventuali variabili della macchina.
    monkeypatch.delenv(
        "MINIMUM_PREDICTION_CONFIDENCE",
        raising=False,
    )

    monkeypatch.delenv(
        "MINIMUM_PROBABILITY_MARGIN",
        raising=False,
    )

    # Crea la configurazione.
    config = LiveMLProcessorConfig()

    # Mantiene compatibilità con il comportamento storico.
    assert config.minimum_confidence == pytest.approx(0.60)

    assert config.minimum_probability_margin == pytest.approx(0.10)


def test_thresholds_are_loaded_from_environment(
    monkeypatch,
) -> None:
    """Verifica le soglie conservative configurate."""

    monkeypatch.setenv(
        "MINIMUM_PREDICTION_CONFIDENCE",
        "0.80",
    )

    monkeypatch.setenv(
        "MINIMUM_PROBABILITY_MARGIN",
        "0.30",
    )

    config = LiveMLProcessorConfig()

    assert config.minimum_confidence == pytest.approx(0.80)

    assert config.minimum_probability_margin == pytest.approx(0.30)


def test_invalid_confidence_is_rejected(
    monkeypatch,
) -> None:
    """Verifica il rifiuto di una confidenza fuori intervallo."""

    monkeypatch.setenv(
        "MINIMUM_PREDICTION_CONFIDENCE",
        "1.50",
    )

    with pytest.raises(
        LiveMLProcessorError,
        match="compresa tra 0 e 1",
    ):
        LiveMLProcessorConfig()


def test_invalid_margin_is_rejected(
    monkeypatch,
) -> None:
    """Verifica il rifiuto di un margine non numerico."""

    monkeypatch.setenv(
        "MINIMUM_PROBABILITY_MARGIN",
        "non-valido",
    )

    with pytest.raises(
        LiveMLProcessorError,
        match="numero decimale",
    ):
        LiveMLProcessorConfig()
