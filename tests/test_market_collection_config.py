"""Test della configurazione del collector multi-market."""

# Importa pytest per verificare gli errori attesi.
import pytest

# Importa configurazione, valori predefiniti ed errore.
from src.config.market_collection import (
    DEFAULT_MARKET_SYMBOLS,
    DEFAULT_MARKET_TIMEFRAMES,
    MarketCollectionSettingsError,
    load_market_collection_settings,
)


def test_default_market_collection_settings() -> None:
    """Verifica la configurazione predefinita."""

    # Carica un ambiente vuoto.
    settings = load_market_collection_settings({})

    # Verifica i simboli predefiniti.
    assert settings.symbols == DEFAULT_MARKET_SYMBOLS

    # Verifica i timeframe predefiniti.
    assert settings.timeframes == DEFAULT_MARKET_TIMEFRAMES

    # Verifica l'intervallo predefinito.
    assert settings.interval_seconds == 30

    # Quattro simboli per otto timeframe.
    assert settings.dataset_count == 32


def test_gold_symbol_is_xauusd() -> None:
    """Verifica il simbolo predefinito dell'oro."""

    settings = load_market_collection_settings({})

    assert "XAUUSD" in settings.symbols


def test_custom_symbols_are_loaded() -> None:
    """Verifica simboli personalizzati."""

    settings = load_market_collection_settings(
        {
            "MARKET_SYMBOLS": (" eurusd, xauusd, gbpusd "),
        }
    )

    assert settings.symbols == (
        "EURUSD",
        "XAUUSD",
        "GBPUSD",
    )


def test_duplicate_symbols_are_removed() -> None:
    """Verifica la rimozione dei duplicati."""

    settings = load_market_collection_settings(
        {
            "MARKET_SYMBOLS": ("EURUSD,eurusd,XAUUSD"),
        }
    )

    assert settings.symbols == (
        "EURUSD",
        "XAUUSD",
    )


def test_custom_timeframes_are_loaded() -> None:
    """Verifica timeframe personalizzati."""

    settings = load_market_collection_settings(
        {
            "MARKET_TIMEFRAMES": ("m1,m15,h1,w1"),
        }
    )

    assert settings.timeframes == (
        "M1",
        "M15",
        "H1",
        "W1",
    )


def test_duplicate_timeframes_are_removed() -> None:
    """Verifica la rimozione dei timeframe duplicati."""

    settings = load_market_collection_settings(
        {
            "MARKET_TIMEFRAMES": ("M1,m1,M15"),
        }
    )

    assert settings.timeframes == (
        "M1",
        "M15",
    )


def test_unknown_timeframe_is_rejected() -> None:
    """Verifica il rifiuto di un timeframe sconosciuto."""

    with pytest.raises(
        MarketCollectionSettingsError,
        match="non supportato",
    ):
        load_market_collection_settings(
            {
                "MARKET_TIMEFRAMES": ("M1,M7"),
            }
        )


def test_empty_market_symbol_is_rejected() -> None:
    """Verifica il rifiuto di elementi vuoti."""

    with pytest.raises(
        MarketCollectionSettingsError,
        match="valore vuoto",
    ):
        load_market_collection_settings(
            {
                "MARKET_SYMBOLS": ("EURUSD,,XAUUSD"),
            }
        )


def test_invalid_interval_is_rejected() -> None:
    """Verifica il rifiuto di un intervallo non positivo."""

    with pytest.raises(
        MarketCollectionSettingsError,
        match="maggiore di zero",
    ):
        load_market_collection_settings(
            {
                "MARKET_COLLECTOR_INTERVAL_SECONDS": ("0"),
            }
        )


def test_safe_summary_contains_no_credentials() -> None:
    """Verifica il riepilogo sicuro."""

    settings = load_market_collection_settings(
        {
            "MARKET_SYMBOLS": ("EURUSD,XAUUSD"),
            "MARKET_TIMEFRAMES": ("M1,M15"),
            "MARKET_COLLECTOR_INTERVAL_SECONDS": ("20"),
        }
    )

    summary = settings.safe_summary()

    assert summary == {
        "symbols": [
            "EURUSD",
            "XAUUSD",
        ],
        "timeframes": [
            "M1",
            "M15",
        ],
        "interval_seconds": 20,
        "dataset_count": 4,
    }
