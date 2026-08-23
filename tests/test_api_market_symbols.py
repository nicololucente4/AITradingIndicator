"""Test del servizio API multi-strumento."""

# Importa Path per database temporanei.
from pathlib import Path

# Importa pandas per creare candele.
import pandas as pd

# Importa servizio e helper simboli.
from src.api.market_service import (
    MarketDataQueryService,
    list_available_symbols,
)

# Importa lo storage SQLite.
from src.data.market_data_store import (
    SQLiteMarketDataStore,
)


def create_candles(
    *,
    start: str,
) -> pd.DataFrame:
    """Crea quattro candele M15."""

    timestamps = pd.date_range(
        start=start,
        periods=4,
        freq="15min",
        tz="UTC",
    )

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [
                1.1000,
                1.1010,
                1.1020,
                1.1030,
            ],
            "high": [
                1.1020,
                1.1030,
                1.1040,
                1.1050,
            ],
            "low": [
                1.0990,
                1.1000,
                1.1010,
                1.1020,
            ],
            "close": [
                1.1010,
                1.1020,
                1.1030,
                1.1040,
            ],
            "volume": [
                100,
                101,
                102,
                103,
            ],
        }
    )


def create_store(
    tmp_path: Path,
) -> SQLiteMarketDataStore:
    """Crea uno storage multi-strumento."""

    store = SQLiteMarketDataStore(tmp_path / "market_data.db")

    received_at = pd.Timestamp(
        "2026-08-20 12:00:00",
        tz="UTC",
    )

    for symbol in (
        "EURUSD",
        "GBPUSD",
        "USDJPY",
        "XAUUSD",
    ):
        store.insert_candles(
            create_candles(start=("2026-08-20 10:00:00")),
            symbol=symbol,
            timeframe="M15",
            provider_name=(f"TEST_{symbol}_M15"),
            received_at_utc=(received_at),
        )

    return store


def test_available_symbols_are_listed(
    tmp_path: Path,
) -> None:
    """Verifica i quattro strumenti disponibili."""

    store = create_store(tmp_path)

    symbols = list_available_symbols(
        store,
        model_symbols=(
            "EURUSD",
            "GBPUSD",
            "USDJPY",
            "XAUUSD",
        ),
    )

    assert [item.symbol for item in symbols] == [
        "EURUSD",
        "GBPUSD",
        "USDJPY",
        "XAUUSD",
    ]

    assert all(item.model_enabled for item in symbols)


def test_symbol_counts_are_separated(
    tmp_path: Path,
) -> None:
    """Verifica conteggi separati per simbolo."""

    symbols = list_available_symbols(create_store(tmp_path))

    assert all(item.stored_candle_count == 4 for item in symbols)

    assert all(item.native_timeframe_count == 1 for item in symbols)


def test_xauusd_candles_are_loaded(
    tmp_path: Path,
) -> None:
    """Verifica la lettura delle candele XAUUSD."""

    service = MarketDataQueryService(
        create_store(tmp_path),
        symbol="XAUUSD",
        model_enabled=True,
    )

    dataframe = service.load_candles(
        timeframe_code="M15",
        limit=500,
    )

    assert len(dataframe) == 4
    assert service.symbol == "XAUUSD"


def test_model_is_enabled_only_on_m15(
    tmp_path: Path,
) -> None:
    """Verifica il vincolo iniziale del modello M15."""

    service = MarketDataQueryService(
        create_store(tmp_path),
        symbol="GBPUSD",
        model_enabled=True,
    )

    m15 = service.get_timeframe_availability("M15")

    h1 = service.get_timeframe_availability("H1")

    assert m15.model_enabled is True

    assert h1.model_enabled is False


def test_symbol_without_model_is_identified(
    tmp_path: Path,
) -> None:
    """Verifica un simbolo senza modello registrato."""

    service = MarketDataQueryService(
        create_store(tmp_path),
        symbol="XAUUSD",
        model_enabled=False,
    )

    m15 = service.get_timeframe_availability("M15")

    assert m15.model_enabled is False
