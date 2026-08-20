"""Test automatici del provider MetaTrader 5 read-only."""

from types import SimpleNamespace

import pandas as pd
import pytest

from src.config.settings import load_settings
from src.data.live_provider import LiveDataProvider
from src.data.mt5_provider import (
    MetaTrader5PollingDataProvider,
    MetaTrader5ProviderError,
)


class FakeMetaTrader5:
    """Simula esclusivamente le funzioni MT5 usate dal provider."""

    TIMEFRAME_M1 = 1
    TIMEFRAME_M5 = 5
    TIMEFRAME_M15 = 15
    TIMEFRAME_H1 = 60
    TIMEFRAME_H4 = 240
    TIMEFRAME_D1 = 1440

    def __init__(self) -> None:
        """Inizializza uno stato MT5 deterministico."""

        self.initialize_result = True
        self.terminal_information: object | None = SimpleNamespace(
            connected=True,
        )
        self.account_information: object | None = SimpleNamespace(
            login=12345678,
        )
        self.symbol_information: object | None = SimpleNamespace(
            name="EURUSD",
        )
        self.symbol_select_result = True
        self.rates: object = create_rates()
        self.error_value: object = (0, "success")
        self.initialize_calls: list[dict[str, object]] = []
        self.copy_calls: list[tuple[str, int, int, int]] = []
        self.shutdown_calls = 0

    def initialize(self, *args: object, **kwargs: object) -> bool:
        """Registra i parametri di inizializzazione."""

        del args
        self.initialize_calls.append(dict(kwargs))
        return self.initialize_result

    def shutdown(self) -> None:
        """Registra la chiusura del collegamento."""

        self.shutdown_calls += 1

    def last_error(self) -> object:
        """Restituisce l'errore simulato."""

        return self.error_value

    def terminal_info(self) -> object:
        """Restituisce le informazioni terminale simulate."""

        return self.terminal_information

    def account_info(self) -> object:
        """Restituisce le informazioni account simulate."""

        return self.account_information

    def symbol_info(self, symbol: str) -> object:
        """Restituisce il simbolo simulato."""

        del symbol
        return self.symbol_information

    def symbol_select(self, symbol: str, enable: bool) -> bool:
        """Simula l'abilitazione del simbolo."""

        del symbol, enable
        return self.symbol_select_result

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_position: int,
        count: int,
    ) -> object:
        """Restituisce candele simulate e registra la richiesta."""

        self.copy_calls.append((symbol, timeframe, start_position, count))
        return self.rates


def create_rates() -> list[dict[str, float | int]]:
    """Crea tre candele M15 deterministiche in formato MT5."""

    timestamps = pd.date_range(
        start="2026-08-20 10:00:00",
        periods=3,
        freq="15min",
        tz="UTC",
    )

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


def create_mt5_settings() -> object:
    """Crea una configurazione MT5 fittizia e sicura."""

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


def create_provider() -> tuple[MetaTrader5PollingDataProvider, FakeMetaTrader5]:
    """Crea provider e modulo MT5 simulato."""

    fake_mt5 = FakeMetaTrader5()
    provider = MetaTrader5PollingDataProvider(
        settings=create_mt5_settings(),
        mt5_module=fake_mt5,
    )
    return provider, fake_mt5


def test_provider_implements_live_interface() -> None:
    """Verifica la compatibilita con LiveDataProvider."""

    provider, _ = create_provider()
    assert isinstance(provider, LiveDataProvider)


def test_connect_uses_configured_credentials_without_logging() -> None:
    """Verifica i parametri passati a initialize."""

    provider, fake_mt5 = create_provider()
    provider.connect()

    assert provider.connected is True
    assert len(fake_mt5.initialize_calls) == 1
    assert fake_mt5.initialize_calls[0]["login"] == 12345678
    assert fake_mt5.initialize_calls[0]["password"] == "test-password"
    assert fake_mt5.initialize_calls[0]["server"] == "Demo-Test-Server"


def test_poll_excludes_current_bar_by_position() -> None:
    """Verifica che la richiesta inizi dalla barra chiusa numero uno."""

    provider, fake_mt5 = create_provider()
    provider.poll(pd.Timestamp("2026-08-20 10:45:00", tz="UTC"))

    assert fake_mt5.copy_calls == [("EURUSD", fake_mt5.TIMEFRAME_M15, 1, 500)]


def test_poll_returns_closed_validated_bars() -> None:
    """Verifica candele, timestamp UTC e tick volume."""

    provider, _ = create_provider()
    result = provider.poll(pd.Timestamp("2026-08-20 10:45:00", tz="UTC"))

    assert result.provider_name == "MT5_READ_ONLY_M15"
    assert len(result.new_closed_bars) == 3
    assert result.total_source_bars == 3
    assert result.new_closed_bars.loc[0, "volume"] == 100
    assert str(result.new_closed_bars["timestamp"].dt.tz) == "UTC"


def test_same_bars_are_not_emitted_twice() -> None:
    """Verifica che il polling sia idempotente."""

    provider, _ = create_provider()
    selected_time = pd.Timestamp("2026-08-20 10:45:00", tz="UTC")

    first_result = provider.poll(selected_time)
    second_result = provider.poll(selected_time)

    assert len(first_result.new_closed_bars) == 3
    assert second_result.new_closed_bars.empty


def test_reset_allows_replay_without_reconnecting() -> None:
    """Verifica il reset dello stato locale."""

    provider, fake_mt5 = create_provider()
    selected_time = pd.Timestamp("2026-08-20 10:45:00", tz="UTC")

    provider.poll(selected_time)
    provider.reset()
    replay_result = provider.poll(selected_time)

    assert len(replay_result.new_closed_bars) == 3
    assert len(fake_mt5.initialize_calls) == 1


def test_naive_poll_timestamp_is_rejected() -> None:
    """Verifica il rifiuto di timestamp privi di timezone."""

    provider, _ = create_provider()

    with pytest.raises(
        MetaTrader5ProviderError,
        match="timezone",
    ):
        provider.poll(pd.Timestamp("2026-08-20 10:45:00"))


def test_failed_initialization_is_reported() -> None:
    """Verifica un errore di inizializzazione MT5."""

    provider, fake_mt5 = create_provider()
    fake_mt5.initialize_result = False
    fake_mt5.error_value = (1001, "initialize failed")

    with pytest.raises(
        MetaTrader5ProviderError,
        match="Inizializzazione MT5 fallita",
    ):
        provider.connect()

    assert provider.connected is False


def test_missing_rate_columns_are_rejected() -> None:
    """Verifica il rifiuto di una risposta MT5 incompleta."""

    provider, fake_mt5 = create_provider()
    fake_mt5.rates = [
        {
            "time": 1787216400,
            "open": 1.1000,
        }
    ]

    with pytest.raises(
        MetaTrader5ProviderError,
        match="Colonne mancanti",
    ):
        provider.poll(pd.Timestamp("2026-08-20 10:45:00", tz="UTC"))


def test_context_manager_disconnects_mt5() -> None:
    """Verifica la chiusura automatica del collegamento."""

    provider, fake_mt5 = create_provider()

    with provider as connected_provider:
        assert connected_provider.connected is True

    assert provider.connected is False
    assert fake_mt5.shutdown_calls == 1
