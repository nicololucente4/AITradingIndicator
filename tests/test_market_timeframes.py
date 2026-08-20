"""Test automatici del catalogo timeframe professionale."""

# Importa pytest per verificare gli errori attesi.
import pytest

# Importa catalogo e funzioni di ricerca.
from src.data.market_timeframes import (
    MARKET_TIMEFRAMES,
    MarketTimeframeError,
    build_public_timeframe_catalog,
    get_model_timeframe_codes,
    get_supported_timeframe_codes,
    get_timeframe_by_code,
    get_timeframe_by_minutes,
)


def test_professional_timeframes_are_available() -> None:
    """Verifica l'elenco completo delle risoluzioni."""

    assert get_supported_timeframe_codes() == (
        "M1",
        "M2",
        "M3",
        "M5",
        "M10",
        "M15",
        "M30",
        "H1",
        "H2",
        "H4",
        "H8",
        "H12",
        "D1",
        "W1",
    )


def test_timeframes_are_ordered_by_duration() -> None:
    """Verifica l'ordinamento crescente del catalogo."""

    minutes = [timeframe.minutes for timeframe in MARKET_TIMEFRAMES]

    assert minutes == sorted(minutes)


def test_timeframe_can_be_selected_by_code() -> None:
    """Verifica la ricerca tramite codice."""

    timeframe = get_timeframe_by_code("m15")

    assert timeframe.code == "M15"
    assert timeframe.minutes == 15
    assert timeframe.mt5_attribute == "TIMEFRAME_M15"


def test_timeframe_can_be_selected_by_minutes() -> None:
    """Verifica la ricerca tramite durata."""

    timeframe = get_timeframe_by_minutes(240)

    assert timeframe.code == "H4"
    assert timeframe.display_label == "4h"


def test_only_m15_is_model_enabled() -> None:
    """Verifica che il modello corrente operi solo su M15."""

    assert get_model_timeframe_codes() == ("M15",)


def test_public_catalog_excludes_mt5_internal_name() -> None:
    """Verifica il catalogo pubblico destinato a FastAPI."""

    catalog = build_public_timeframe_catalog()

    assert len(catalog) == 14

    assert catalog[0] == {
        "code": "M1",
        "label": "1m",
        "minutes": 1,
        "model_enabled": False,
    }

    assert "mt5_attribute" not in catalog[0]


def test_unknown_code_is_rejected() -> None:
    """Verifica il rifiuto di un codice sconosciuto."""

    with pytest.raises(
        MarketTimeframeError,
        match="non supportato",
    ):
        get_timeframe_by_code("M7")


def test_unknown_duration_is_rejected() -> None:
    """Verifica il rifiuto di una durata sconosciuta."""

    with pytest.raises(
        MarketTimeframeError,
        match="non supportata",
    ):
        get_timeframe_by_minutes(7)


def test_all_timeframes_have_unique_codes() -> None:
    """Verifica l'univocità dei codici."""

    codes = [timeframe.code for timeframe in MARKET_TIMEFRAMES]

    assert len(codes) == len(set(codes))


def test_all_timeframes_have_unique_minutes() -> None:
    """Verifica l'univocità delle durate."""

    minutes = [timeframe.minutes for timeframe in MARKET_TIMEFRAMES]

    assert len(minutes) == len(set(minutes))
