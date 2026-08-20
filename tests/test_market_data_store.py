"""Test automatici dell'archivio SQLite delle candele."""

# Importa SQLite per verificare direttamente la persistenza.
import sqlite3

# Importa Path per usare database temporanei.
from pathlib import Path

# Importa pandas per costruire dataset OHLCV.
import pandas as pd

# Importa pytest per verificare gli errori attesi.
import pytest

# Importa archivio ed errore.
from src.data.market_data_store import (
    MarketDataStoreError,
    SQLiteMarketDataStore,
)


def create_candles(
    row_count: int = 4,
    *,
    start: str = "2026-08-20 10:00:00",
    frequency: str = "15min",
) -> pd.DataFrame:
    """Crea candele OHLCV deterministiche."""

    # Genera timestamp UTC consecutivi.
    timestamps = pd.date_range(
        start=start,
        periods=row_count,
        freq=frequency,
        tz="UTC",
    )

    # Genera prezzi di apertura.
    open_prices = [1.1000 + index * 0.0010 for index in range(row_count)]

    # Costruisce il dataset valido.
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_prices,
            "high": [price + 0.0020 for price in open_prices],
            "low": [price - 0.0010 for price in open_prices],
            "close": [price + 0.0010 for price in open_prices],
            "volume": [100 + index for index in range(row_count)],
        }
    )


def create_store(
    tmp_path: Path,
) -> SQLiteMarketDataStore:
    """Crea un archivio SQLite temporaneo."""

    return SQLiteMarketDataStore(tmp_path / "market_data.db")


def insert_default_candles(
    store: SQLiteMarketDataStore,
    dataframe: pd.DataFrame,
) -> object:
    """Inserisce candele EURUSD M15 di test."""

    return store.insert_candles(
        dataframe,
        symbol="EURUSD",
        timeframe="M15",
        provider_name="MT5_READ_ONLY_M15",
        received_at_utc=pd.Timestamp(
            "2026-08-20 12:00:00",
            tz="UTC",
        ),
    )


def test_database_and_table_are_created(
    tmp_path: Path,
) -> None:
    """Verifica la creazione della struttura SQLite."""

    # Crea l'archivio.
    store = create_store(tmp_path)

    # Il file deve essere disponibile.
    assert store.database_path.exists()

    # Verifica direttamente la tabella.
    with sqlite3.connect(store.database_path) as connection:
        row = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'market_candles'
            """
        ).fetchone()

    assert row is not None


def test_candles_are_inserted(
    tmp_path: Path,
) -> None:
    """Verifica l'inserimento delle candele."""

    # Crea archivio e dataset.
    store = create_store(tmp_path)

    dataframe = create_candles()

    # Inserisce le candele.
    report = insert_default_candles(
        store,
        dataframe,
    )

    # Verifica il report.
    assert report.symbol == "EURUSD"
    assert report.timeframe == "M15"
    assert report.received_rows == 4
    assert report.inserted_rows == 4
    assert report.duplicate_rows == 0
    assert report.provider_name == "MT5_READ_ONLY_M15"


def test_duplicate_candles_are_ignored(
    tmp_path: Path,
) -> None:
    """Verifica che le candele non vengano sovrascritte."""

    # Crea archivio e dataset.
    store = create_store(tmp_path)

    dataframe = create_candles()

    # Esegue due inserimenti identici.
    first_report = insert_default_candles(
        store,
        dataframe,
    )

    second_report = insert_default_candles(
        store,
        dataframe,
    )

    # Il primo inserimento salva tutto.
    assert first_report.inserted_rows == 4

    # Il secondo inserimento ignora i duplicati.
    assert second_report.inserted_rows == 0
    assert second_report.duplicate_rows == 4

    # Il database deve contenere sempre quattro righe.
    assert (
        store.count_candles(
            symbol="EURUSD",
            timeframe="M15",
        )
        == 4
    )


def test_existing_candle_is_not_overwritten(
    tmp_path: Path,
) -> None:
    """Verifica l'immutabilità di una candela già salvata."""

    # Crea archivio e dataset.
    store = create_store(tmp_path)

    dataframe = create_candles()

    # Salva il dataset originale.
    insert_default_candles(
        store,
        dataframe,
    )

    # Modifica il Close della prima candela.
    modified_dataframe = dataframe.copy(deep=True)

    modified_dataframe.loc[
        0,
        "close",
    ] = 1.9999

    modified_dataframe.loc[
        0,
        "high",
    ] = 2.0000

    # Tenta di reinserire le stesse chiavi.
    insert_default_candles(
        store,
        modified_dataframe,
    )

    # Rilegge i dati.
    loaded = store.load_candles(
        symbol="EURUSD",
        timeframe="M15",
    )

    # Il Close originale deve essere mantenuto.
    assert (
        loaded.loc[
            0,
            "close",
        ]
        == dataframe.loc[
            0,
            "close",
        ]
    )


def test_candles_are_loaded_in_chronological_order(
    tmp_path: Path,
) -> None:
    """Verifica l'ordine cronologico dei dati letti."""

    # Crea archivio e dataset.
    store = create_store(tmp_path)

    dataframe = create_candles()

    # Inserisce i dati.
    insert_default_candles(
        store,
        dataframe,
    )

    # Carica i dati.
    loaded = store.load_candles(
        symbol="EURUSD",
        timeframe="M15",
    )

    # Verifica quantità e ordinamento.
    assert len(loaded) == 4

    assert loaded["timestamp"].is_monotonic_increasing

    assert str(loaded["timestamp"].dt.tz) == "UTC"


def test_limit_returns_latest_candles(
    tmp_path: Path,
) -> None:
    """Verifica che il limite mantenga le candele più recenti."""

    # Crea archivio e dataset.
    store = create_store(tmp_path)

    dataframe = create_candles(row_count=6)

    insert_default_candles(
        store,
        dataframe,
    )

    # Richiede le ultime due candele.
    loaded = store.load_candles(
        symbol="EURUSD",
        timeframe="M15",
        limit=2,
    )

    # Devono essere restituite in ordine crescente.
    assert len(loaded) == 2

    assert loaded.iloc[0]["timestamp"] == dataframe.iloc[-2]["timestamp"]

    assert loaded.iloc[-1]["timestamp"] == dataframe.iloc[-1]["timestamp"]


def test_symbols_and_timeframes_are_separated(
    tmp_path: Path,
) -> None:
    """Verifica la separazione tra dataset distinti."""

    # Crea l'archivio.
    store = create_store(tmp_path)

    # Inserisce EURUSD M15.
    store.insert_candles(
        create_candles(),
        symbol="EURUSD",
        timeframe="M15",
        provider_name="MT5_M15",
        received_at_utc=pd.Timestamp(
            "2026-08-20 12:00:00",
            tz="UTC",
        ),
    )

    # Inserisce GBPUSD H1.
    store.insert_candles(
        create_candles(frequency="60min"),
        symbol="GBPUSD",
        timeframe="H1",
        provider_name="MT5_H1",
        received_at_utc=pd.Timestamp(
            "2026-08-20 12:00:00",
            tz="UTC",
        ),
    )

    # Verifica i conteggi separati.
    assert (
        store.count_candles(
            symbol="EURUSD",
            timeframe="M15",
        )
        == 4
    )

    assert (
        store.count_candles(
            symbol="GBPUSD",
            timeframe="H1",
        )
        == 4
    )

    assert (
        store.count_candles(
            symbol="EURUSD",
            timeframe="H1",
        )
        == 0
    )


def test_availability_is_reported(
    tmp_path: Path,
) -> None:
    """Verifica l'elenco dei dataset disponibili."""

    # Crea l'archivio.
    store = create_store(tmp_path)

    # Inserisce un dataset.
    dataframe = create_candles()

    insert_default_candles(
        store,
        dataframe,
    )

    # Recupera la disponibilità.
    availability = store.list_availability(symbol="EURUSD")

    # Deve essere disponibile un solo dataset.
    assert len(availability) == 1

    item = availability[0]

    assert item.symbol == "EURUSD"
    assert item.timeframe == "M15"
    assert item.candle_count == 4
    assert item.first_timestamp == dataframe.iloc[0]["timestamp"]

    assert item.latest_timestamp == dataframe.iloc[-1]["timestamp"]


def test_empty_result_has_ohlcv_schema(
    tmp_path: Path,
) -> None:
    """Verifica lo schema di una lettura senza risultati."""

    # Crea un archivio vuoto.
    store = create_store(tmp_path)

    # Richiede un dataset non presente.
    loaded = store.load_candles(
        symbol="EURUSD",
        timeframe="M15",
    )

    assert loaded.empty

    assert list(loaded.columns) == [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]


def test_unknown_timeframe_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il rifiuto di timeframe non supportati."""

    # Crea l'archivio.
    store = create_store(tmp_path)

    # Tenta un inserimento su M7.
    with pytest.raises(
        MarketDataStoreError,
        match="non supportato",
    ):
        store.insert_candles(
            create_candles(),
            symbol="EURUSD",
            timeframe="M7",
            provider_name="TEST",
            received_at_utc=pd.Timestamp(
                "2026-08-20 12:00:00",
                tz="UTC",
            ),
        )


def test_naive_received_timestamp_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il rifiuto di un timestamp senza timezone."""

    # Crea l'archivio.
    store = create_store(tmp_path)

    # Tenta un inserimento con timestamp naive.
    with pytest.raises(
        MarketDataStoreError,
        match="timezone",
    ):
        store.insert_candles(
            create_candles(),
            symbol="EURUSD",
            timeframe="M15",
            provider_name="TEST",
            received_at_utc=pd.Timestamp("2026-08-20 12:00:00"),
        )


def test_empty_dataframe_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il rifiuto di un dataset vuoto."""

    # Crea l'archivio.
    store = create_store(tmp_path)

    # Tenta di inserire un DataFrame vuoto.
    with pytest.raises(
        MarketDataStoreError,
        match="vuoto",
    ):
        store.insert_candles(
            pd.DataFrame(),
            symbol="EURUSD",
            timeframe="M15",
            provider_name="TEST",
            received_at_utc=pd.Timestamp(
                "2026-08-20 12:00:00",
                tz="UTC",
            ),
        )


def test_invalid_limit_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il rifiuto di un limite non positivo."""

    # Crea l'archivio.
    store = create_store(tmp_path)

    # Tenta una lettura con limite zero.
    with pytest.raises(
        MarketDataStoreError,
        match="limit",
    ):
        store.load_candles(
            symbol="EURUSD",
            timeframe="M15",
            limit=0,
        )
