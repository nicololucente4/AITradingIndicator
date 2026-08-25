"""Test del servizio tick live MetaTrader 5."""

# Importa SimpleNamespace per simulare il tick.
from types import SimpleNamespace

# Importa pandas per verificare il timestamp.
import pandas as pd

# Importa pytest per verificare gli errori.
import pytest

# Importa il caricatore della configurazione.
from src.config.settings import load_settings

# Importa servizio ed errore.
from src.data.mt5_tick_service import (
    MetaTrader5TickService,
    MetaTrader5TickServiceError,
    normalize_tick_symbol,
)


class FakeTickMetaTrader5:
    """Simula il modulo MetaTrader 5."""

    def __init__(
        self,
    ) -> None:
        """Inizializza il modulo simulato."""

        self.initialize_calls = 0
        self.shutdown_calls = 0
        self.selected_symbols: list[str] = []

        self.tick = SimpleNamespace(
            bid=1.16755,
            ask=1.16757,
            time=1787652001,
            time_msc=1787652001123,
        )

    def initialize(
        self,
        *args: object,
        **kwargs: object,
    ) -> bool:
        """Simula un'inizializzazione riuscita."""

        del args
        del kwargs

        self.initialize_calls += 1

        return True

    def shutdown(
        self,
    ) -> None:
        """Simula la chiusura."""

        self.shutdown_calls += 1

    def last_error(
        self,
    ) -> object:
        """Restituisce uno stato positivo."""

        return (
            0,
            "success",
        )

    def terminal_info(
        self,
    ) -> object:
        """Restituisce informazioni terminale."""

        return SimpleNamespace(connected=True)

    def account_info(
        self,
    ) -> object:
        """Restituisce informazioni account."""

        return SimpleNamespace(login=12345678)

    def symbol_info(
        self,
        symbol: str,
    ) -> object:
        """Restituisce informazioni simbolo."""

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

    def symbol_info_tick(
        self,
        symbol: str,
    ) -> object:
        """Restituisce il tick simulato."""

        del symbol

        return self.tick


def create_settings():
    """Crea impostazioni MT5 di test."""

    return load_settings(
        {
            "DATA_PROVIDER": "MT5",
            "TRADING_SYMBOL": "EURUSD",
            "TIMEFRAME_MINUTES": "15",
            "MT5_LOGIN": "12345678",
            "MT5_PASSWORD": "test-password",
            "MT5_SERVER": "Demo-Test-Server",
            "PAPER_TRADING_ONLY": "true",
            "REAL_ORDERS_ENABLED": "false",
        }
    )


def test_tick_symbol_is_normalized() -> None:
    """Verifica la normalizzazione del simbolo."""

    assert normalize_tick_symbol(" xauusd ") == "XAUUSD"


def test_tick_is_loaded() -> None:
    """Verifica la lettura del tick live."""

    fake_mt5 = FakeTickMetaTrader5()

    service = MetaTrader5TickService(
        settings=create_settings(),
        mt5_module=fake_mt5,
    )

    tick = service.get_tick("EURUSD")

    assert tick.symbol == "EURUSD"
    assert tick.bid == 1.16755
    assert tick.ask == 1.16757
    assert tick.mid == pytest.approx(1.16756)
    assert tick.spread == pytest.approx(0.00002)
    assert tick.timestamp == pd.Timestamp(
        1787652001123,
        unit="ms",
        tz="UTC",
    )
    assert tick.source == "MT5_LIVE_TICK"


def test_connection_is_reused() -> None:
    """Verifica il riutilizzo della connessione."""

    fake_mt5 = FakeTickMetaTrader5()

    service = MetaTrader5TickService(
        settings=create_settings(),
        mt5_module=fake_mt5,
    )

    service.get_tick("EURUSD")

    service.get_tick("XAUUSD")

    assert fake_mt5.initialize_calls == 1

    assert fake_mt5.selected_symbols == [
        "EURUSD",
        "XAUUSD",
    ]


def test_disconnect_closes_mt5() -> None:
    """Verifica la chiusura del servizio."""

    fake_mt5 = FakeTickMetaTrader5()

    service = MetaTrader5TickService(
        settings=create_settings(),
        mt5_module=fake_mt5,
    )

    service.get_tick("EURUSD")

    service.disconnect()

    assert service.connected is False
    assert fake_mt5.shutdown_calls == 1


def test_invalid_prices_are_rejected() -> None:
    """Verifica il rifiuto di prezzi non validi."""

    fake_mt5 = FakeTickMetaTrader5()

    fake_mt5.tick = SimpleNamespace(
        bid=1.20,
        ask=1.10,
        time=1787652001,
        time_msc=1787652001123,
    )

    service = MetaTrader5TickService(
        settings=create_settings(),
        mt5_module=fake_mt5,
    )

    with pytest.raises(
        MetaTrader5TickServiceError,
        match="inferiore al bid",
    ):
        service.get_tick("EURUSD")


def test_file_provider_is_rejected() -> None:
    """Verifica il rifiuto del provider FILE."""

    settings = load_settings(
        {
            "DATA_PROVIDER": "FILE",
        }
    )

    with pytest.raises(
        MetaTrader5TickServiceError,
        match="DATA_PROVIDER=MT5",
    ):
        MetaTrader5TickService(
            settings=settings,
            mt5_module=FakeTickMetaTrader5(),
        )
