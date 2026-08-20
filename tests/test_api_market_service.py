"""Test del servizio multi-timeframe usato da FastAPI."""

# Importa Path per creare database temporanei.
from pathlib import Path

# Importa pandas per costruire candele OHLCV.
import pandas as pd

# Importa pytest per verificare gli errori attesi.
import pytest

# Importa il servizio dati di mercato.
from src.api.market_service import (
    MarketDataQueryService,
    MarketDataServiceError,
)

# Importa lo storage persistente.
from src.data.market_data_store import (
    SQLiteMarketDataStore,
)


def create_candles(
    *,
    timeframe_minutes: int,
    row_count: int,
    start: str = "2026-08-14 00:00:00",
) -> pd.DataFrame:
    """Crea candele deterministiche e allineate."""

    # Genera timestamp consecutivi.
    timestamps = pd.date_range(
        start=start,
        periods=row_count,
        freq=f"{timeframe_minutes}min",
        tz="UTC",
    )

    # Genera prezzi progressivi.
    open_prices = [1.1000 + index * 0.00001 for index in range(row_count)]

    # Costruisce il dataset OHLCV.
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_prices,
            "high": [price + 0.00020 for price in open_prices],
            "low": [price - 0.00020 for price in open_prices],
            "close": [price + 0.00005 for price in open_prices],
            "volume": [100 + index for index in range(row_count)],
        }
    )


def create_store(
    tmp_path: Path,
) -> SQLiteMarketDataStore:
    """Crea uno storage temporaneo."""

    return SQLiteMarketDataStore(tmp_path / "market_data.db")


def insert_candles(
    store: SQLiteMarketDataStore,
    *,
    timeframe: str,
    timeframe_minutes: int,
    row_count: int,
) -> None:
    """Inserisce candele native nello storage."""

    store.insert_candles(
        create_candles(
            timeframe_minutes=(timeframe_minutes),
            row_count=row_count,
        ),
        symbol="EURUSD",
        timeframe=timeframe,
        provider_name=(f"TEST_{timeframe}"),
        received_at_utc=pd.Timestamp(
            "2026-08-20 12:00:00",
            tz="UTC",
        ),
    )


def test_empty_store_has_no_available_timeframes(
    tmp_path: Path,
) -> None:
    """Verifica un archivio senza candele."""

    # Crea il servizio su storage vuoto.
    service = MarketDataQueryService(
        create_store(tmp_path),
        symbol="EURUSD",
    )

    # Recupera il catalogo.
    availability = {item.code: item for item in service.list_timeframes()}

    # Tutti i timeframe devono essere indisponibili.
    assert all(not item.available for item in availability.values())


def test_native_m15_is_available(
    tmp_path: Path,
) -> None:
    """Verifica la disponibilità nativa di M15."""

    # Crea e popola lo storage.
    store = create_store(tmp_path)

    insert_candles(
        store,
        timeframe="M15",
        timeframe_minutes=15,
        row_count=96,
    )

    # Crea il servizio.
    service = MarketDataQueryService(
        store,
        symbol="EURUSD",
    )

    # Recupera M15.
    item = service.get_timeframe_availability("M15")

    assert item.available is True
    assert item.native is True
    assert item.source_timeframe == "M15"
    assert item.stored_candle_count == 96
    assert item.model_enabled is True


def test_lower_timeframes_are_not_reconstructed_from_m15(
    tmp_path: Path,
) -> None:
    """Verifica che M1, M2, M3, M5 e M10 restino disabilitati."""

    # Inserisce solamente candele M15.
    store = create_store(tmp_path)

    insert_candles(
        store,
        timeframe="M15",
        timeframe_minutes=15,
        row_count=96,
    )

    service = MarketDataQueryService(
        store,
        symbol="EURUSD",
    )

    # Nessun timeframe inferiore può essere ricostruito.
    for code in (
        "M1",
        "M2",
        "M3",
        "M5",
        "M10",
    ):
        item = service.get_timeframe_availability(code)

        assert item.available is False
        assert item.native is False
        assert item.source_timeframe is None


def test_higher_timeframes_are_derived_from_m15(
    tmp_path: Path,
) -> None:
    """Verifica le aggregazioni superiori da M15."""

    # Inserisce un giorno completo M15.
    store = create_store(tmp_path)

    insert_candles(
        store,
        timeframe="M15",
        timeframe_minutes=15,
        row_count=96,
    )

    service = MarketDataQueryService(
        store,
        symbol="EURUSD",
    )

    # Questi timeframe sono divisibili per M15.
    for code in (
        "M30",
        "H1",
        "H2",
        "H4",
        "H8",
        "H12",
        "D1",
        "W1",
    ):
        item = service.get_timeframe_availability(code)

        assert item.available is True
        assert item.native is False
        assert item.source_timeframe == "M15"


def test_native_timeframe_is_preferred(
    tmp_path: Path,
) -> None:
    """Verifica che un dataset nativo prevalga sull'aggregazione."""

    # Inserisce M15 e H1 nativi.
    store = create_store(tmp_path)

    insert_candles(
        store,
        timeframe="M15",
        timeframe_minutes=15,
        row_count=96,
    )

    insert_candles(
        store,
        timeframe="H1",
        timeframe_minutes=60,
        row_count=24,
    )

    service = MarketDataQueryService(
        store,
        symbol="EURUSD",
    )

    # H1 deve essere letto come nativo.
    item = service.get_timeframe_availability("H1")

    assert item.native is True
    assert item.source_timeframe == "H1"
    assert item.stored_candle_count == 24


def test_best_native_source_is_selected(
    tmp_path: Path,
) -> None:
    """Verifica la scelta della sorgente nativa più vicina."""

    # Inserisce M15 e H1.
    store = create_store(tmp_path)

    insert_candles(
        store,
        timeframe="M15",
        timeframe_minutes=15,
        row_count=96,
    )

    insert_candles(
        store,
        timeframe="H1",
        timeframe_minutes=60,
        row_count=24,
    )

    service = MarketDataQueryService(
        store,
        symbol="EURUSD",
    )

    # H4 deve preferire H1 rispetto a M15.
    item = service.get_timeframe_availability("H4")

    assert item.native is False
    assert item.source_timeframe == "H1"


def test_native_candles_are_loaded(
    tmp_path: Path,
) -> None:
    """Verifica la lettura diretta di un timeframe nativo."""

    # Inserisce candele M15.
    store = create_store(tmp_path)

    insert_candles(
        store,
        timeframe="M15",
        timeframe_minutes=15,
        row_count=96,
    )

    service = MarketDataQueryService(
        store,
        symbol="EURUSD",
    )

    # Richiede le ultime dieci.
    dataframe = service.load_candles(
        timeframe_code="M15",
        limit=10,
    )

    assert len(dataframe) == 10
    assert dataframe["timestamp"].is_monotonic_increasing


def test_m15_is_aggregated_to_h1(
    tmp_path: Path,
) -> None:
    """Verifica l'aggregazione M15 verso H1."""

    # Inserisce ventiquattro ore complete.
    store = create_store(tmp_path)

    insert_candles(
        store,
        timeframe="M15",
        timeframe_minutes=15,
        row_count=96,
    )

    service = MarketDataQueryService(
        store,
        symbol="EURUSD",
    )

    # Aggrega verso H1.
    dataframe = service.load_candles(
        timeframe_code="H1",
        limit=500,
    )

    assert len(dataframe) == 24


def test_m15_is_aggregated_to_d1(
    tmp_path: Path,
) -> None:
    """Verifica l'aggregazione M15 verso D1."""

    # Inserisce una giornata completa.
    store = create_store(tmp_path)

    insert_candles(
        store,
        timeframe="M15",
        timeframe_minutes=15,
        row_count=96,
    )

    service = MarketDataQueryService(
        store,
        symbol="EURUSD",
    )

    # Aggrega verso D1.
    dataframe = service.load_candles(
        timeframe_code="D1",
        limit=500,
    )

    assert len(dataframe) == 1


def test_unavailable_lower_timeframe_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il rifiuto di M5 quando esiste solo M15."""

    # Inserisce M15.
    store = create_store(tmp_path)

    insert_candles(
        store,
        timeframe="M15",
        timeframe_minutes=15,
        row_count=96,
    )

    service = MarketDataQueryService(
        store,
        symbol="EURUSD",
    )

    # M5 non può essere ricostruito.
    with pytest.raises(
        MarketDataServiceError,
        match="non disponibile",
    ):
        service.load_candles(
            timeframe_code="M5",
            limit=500,
        )


def test_unknown_timeframe_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il rifiuto di un codice sconosciuto."""

    service = MarketDataQueryService(
        create_store(tmp_path),
        symbol="EURUSD",
    )

    with pytest.raises(
        MarketDataServiceError,
        match="non supportato",
    ):
        service.load_candles(
            timeframe_code="M7",
            limit=500,
        )


def test_invalid_limit_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il rifiuto di un limite non positivo."""

    service = MarketDataQueryService(
        create_store(tmp_path),
        symbol="EURUSD",
    )

    with pytest.raises(
        MarketDataServiceError,
        match="limit",
    ):
        service.load_candles(
            timeframe_code="M15",
            limit=0,
        )
