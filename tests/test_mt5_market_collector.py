"""Test del collector MT5 multi-strumento e multi-timeframe."""

# Importa SimpleNamespace per simulare MT5.
from types import SimpleNamespace

# Importa pandas per generare candele.
import pandas as pd

# Importa pytest per verificare gli errori.
import pytest

# Importa il caricatore della configurazione.
from src.config.settings import load_settings

# Importa lo storage SQLite.
from src.data.market_data_store import SQLiteMarketDataStore

# Importa il collector.
from src.data.mt5_market_collector import (
    MetaTrader5MarketCollector,
    MetaTrader5MarketCollectorError,
    normalize_market_symbols,
    normalize_market_timeframes,
)


class FakeMultiMarketMetaTrader5:
    """Simula MT5 per più strumenti e timeframe."""

    # Costanti native usate dal collector.
    TIMEFRAME_M1 = 1
    TIMEFRAME_M5 = 5
    TIMEFRAME_M15 = 15
    TIMEFRAME_M30 = 30
    TIMEFRAME_H1 = 60
    TIMEFRAME_H4 = 240
    TIMEFRAME_D1 = 1440
    TIMEFRAME_W1 = 10080

    def __init__(self) -> None:
        """Inizializza il modulo simulato."""

        # Conta inizializzazioni e chiusure.
        self.initialize_calls = 0
        self.shutdown_calls = 0

        # Registra simboli abilitati.
        self.selected_symbols: list[str] = []

        # Registra le richieste dati.
        self.copy_calls: list[tuple[str, int, int, int]] = []

    def initialize(
        self,
        *args: object,
        **kwargs: object,
    ) -> bool:
        """Simula un collegamento riuscito."""

        del args
        del kwargs

        self.initialize_calls += 1

        return True

    def shutdown(self) -> None:
        """Simula la chiusura."""

        self.shutdown_calls += 1

    def last_error(self) -> object:
        """Restituisce uno stato senza errori."""

        return (0, "success")

    def terminal_info(self) -> object:
        """Restituisce informazioni terminale."""

        return SimpleNamespace(connected=True)

    def account_info(self) -> object:
        """Restituisce informazioni account."""

        return SimpleNamespace(login=12345678)

    def symbol_info(
        self,
        symbol: str,
    ) -> object:
        """Restituisce un simbolo disponibile."""

        return SimpleNamespace(name=symbol)

    def symbol_select(
        self,
        symbol: str,
        enable: bool,
    ) -> bool:
        """Simula l'abilitazione del simbolo."""

        if enable:
            self.selected_symbols.append(symbol)

        return True

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_position: int,
        count: int,
    ) -> object:
        """Restituisce tre candele simulate."""

        # Registra la richiesta.
        self.copy_calls.append(
            (
                symbol,
                timeframe,
                start_position,
                count,
            )
        )

        # Genera timestamp coerenti con la durata.
        timestamps = pd.date_range(
            start="2026-08-20 10:00:00",
            periods=3,
            freq=f"{timeframe}min",
            tz="UTC",
        )

        # Restituisce il formato MT5.
        return [
            {
                "time": int(timestamp.timestamp()),
                "open": 1.1000 + index * 0.0010,
                "high": 1.1020 + index * 0.0010,
                "low": 1.0990 + index * 0.0010,
                "close": 1.1010 + index * 0.0010,
                "tick_volume": 100 + index,
                "spread": 10,
                "real_volume": 0,
            }
            for index, timestamp in enumerate(timestamps)
        ]


def create_settings():
    """Crea una configurazione MT5 di test."""

    return load_settings(
        {
            "DATA_PROVIDER": "MT5",
            "TRADING_SYMBOL": "EURUSD",
            "TIMEFRAME_MINUTES": "15",
            "MT5_LOGIN": "12345678",
            "MT5_PASSWORD": "test-password",
            "MT5_SERVER": "Demo-Test-Server",
            "MT5_BARS_PER_POLL": "500",
            "PAPER_TRADING_ONLY": "true",
            "REAL_ORDERS_ENABLED": "false",
        }
    )


def test_symbols_are_normalized() -> None:
    """Verifica normalizzazione e rimozione duplicati."""

    assert normalize_market_symbols(
        (
            " eurusd ",
            "GBPUSD",
            "eurusd",
        )
    ) == (
        "EURUSD",
        "GBPUSD",
    )


def test_timeframes_are_normalized() -> None:
    """Verifica normalizzazione dei timeframe."""

    assert normalize_market_timeframes(
        (
            "m1",
            "M15",
            "m1",
        )
    ) == (
        "M1",
        "M15",
    )


def test_unknown_timeframe_is_rejected() -> None:
    """Verifica il rifiuto di M7."""

    with pytest.raises(
        MetaTrader5MarketCollectorError,
        match="non supportato",
    ):
        normalize_market_timeframes(("M7",))


def test_collector_uses_one_connection(
    tmp_path,
) -> None:
    """Verifica una singola connessione per tutti i dataset."""

    # Crea modulo e storage simulati.
    fake_mt5 = FakeMultiMarketMetaTrader5()

    store = SQLiteMarketDataStore(tmp_path / "market_data.db")

    # Crea due simboli e due timeframe.
    collector = MetaTrader5MarketCollector(
        settings=create_settings(),
        mt5_module=fake_mt5,
        store=store,
        symbols=(
            "EURUSD",
            "GBPUSD",
        ),
        timeframes=(
            "M1",
            "M15",
        ),
    )

    # Esegue un ciclo.
    report = collector.collect(
        pd.Timestamp(
            "2026-08-20 12:00:00",
            tz="UTC",
        )
    )

    # Una sola inizializzazione per quattro dataset.
    assert fake_mt5.initialize_calls == 1

    assert report.requested_datasets == 4
    assert report.successful_datasets == 4
    assert report.failed_datasets == 0
    assert report.inserted_rows == 12

    # Tutte le combinazioni devono essere richieste.
    assert len(fake_mt5.copy_calls) == 4

    # I simboli devono essere abilitati una sola volta.
    assert fake_mt5.selected_symbols == [
        "EURUSD",
        "GBPUSD",
    ]

    collector.disconnect()

    assert fake_mt5.shutdown_calls == 1


def test_candles_are_separated_by_dataset(
    tmp_path,
) -> None:
    """Verifica separazione per simbolo e timeframe."""

    fake_mt5 = FakeMultiMarketMetaTrader5()

    store = SQLiteMarketDataStore(tmp_path / "market_data.db")

    collector = MetaTrader5MarketCollector(
        settings=create_settings(),
        mt5_module=fake_mt5,
        store=store,
        symbols=(
            "EURUSD",
            "XAUUSD",
        ),
        timeframes=(
            "M5",
            "H1",
        ),
    )

    collector.collect(
        pd.Timestamp(
            "2026-08-20 12:00:00",
            tz="UTC",
        )
    )

    # Ogni dataset deve contenere tre candele.
    assert (
        store.count_candles(
            symbol="EURUSD",
            timeframe="M5",
        )
        == 3
    )

    assert (
        store.count_candles(
            symbol="EURUSD",
            timeframe="H1",
        )
        == 3
    )

    assert (
        store.count_candles(
            symbol="XAUUSD",
            timeframe="M5",
        )
        == 3
    )

    assert (
        store.count_candles(
            symbol="XAUUSD",
            timeframe="H1",
        )
        == 3
    )


def test_second_collection_has_no_duplicates(
    tmp_path,
) -> None:
    """Verifica l'idempotenza tra cicli successivi."""

    fake_mt5 = FakeMultiMarketMetaTrader5()

    store = SQLiteMarketDataStore(tmp_path / "market_data.db")

    collector = MetaTrader5MarketCollector(
        settings=create_settings(),
        mt5_module=fake_mt5,
        store=store,
        symbols=("EURUSD",),
        timeframes=("M15",),
    )

    first_report = collector.collect(
        pd.Timestamp(
            "2026-08-20 12:00:00",
            tz="UTC",
        )
    )

    second_report = collector.collect(
        pd.Timestamp(
            "2026-08-20 12:01:00",
            tz="UTC",
        )
    )

    assert first_report.inserted_rows == 3
    assert second_report.inserted_rows == 0

    assert second_report.results[0].duplicate_rows == 3

    assert (
        store.count_candles(
            symbol="EURUSD",
            timeframe="M15",
        )
        == 3
    )


def test_naive_timestamp_is_rejected(
    tmp_path,
) -> None:
    """Verifica il rifiuto di timestamp senza timezone."""

    collector = MetaTrader5MarketCollector(
        settings=create_settings(),
        mt5_module=FakeMultiMarketMetaTrader5(),
        store=SQLiteMarketDataStore(tmp_path / "market_data.db"),
        symbols=("EURUSD",),
        timeframes=("M15",),
    )

    with pytest.raises(
        MetaTrader5MarketCollectorError,
        match="timezone",
    ):
        collector.collect(pd.Timestamp("2026-08-20 12:00:00"))
