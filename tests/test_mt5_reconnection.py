"""Test della riconnessione automatica del provider MetaTrader 5."""

# Importa SimpleNamespace per simulare le risposte MT5.
from types import SimpleNamespace

# Importa pandas per creare timestamp e candele.
import pandas as pd

# Importa pytest per verificare gli errori attesi.
import pytest

# Importa il caricatore della configurazione.
from src.config.settings import load_settings

# Importa provider ed errore MT5.
from src.data.mt5_provider import (
    MetaTrader5PollingDataProvider,
    MetaTrader5ProviderError,
)


class ReconnectingFakeMetaTrader5:
    """Simula una perdita temporanea della connessione MT5."""

    # Costanti dei timeframe professionali.
    TIMEFRAME_M1 = 1
    TIMEFRAME_M2 = 2
    TIMEFRAME_M3 = 3
    TIMEFRAME_M5 = 5
    TIMEFRAME_M10 = 10
    TIMEFRAME_M15 = 15
    TIMEFRAME_M30 = 30
    TIMEFRAME_H1 = 60
    TIMEFRAME_H2 = 120
    TIMEFRAME_H4 = 240
    TIMEFRAME_H8 = 480
    TIMEFRAME_H12 = 720
    TIMEFRAME_D1 = 1440
    TIMEFRAME_W1 = 10080

    def __init__(self) -> None:
        """Inizializza il modulo MT5 simulato."""

        # Conta le inizializzazioni.
        self.initialize_calls = 0

        # Conta le chiusure.
        self.shutdown_calls = 0

        # Conta le richieste delle candele.
        self.copy_calls = 0

        # Il primo polling deve fallire.
        self.fail_next_poll = True

        # Prepara le candele valide.
        self.rates = self._create_rates()

    @staticmethod
    def _create_rates():
        """Crea candele M15 valide in formato MT5."""

        # Genera tre timestamp M15 UTC.
        timestamps = pd.date_range(
            start="2026-08-20 10:00:00",
            periods=3,
            freq="15min",
            tz="UTC",
        )

        # Converte le candele nel formato MT5.
        return [
            {
                "time": int(timestamp.timestamp()),
                "open": (1.1000 + index * 0.0010),
                "high": (1.1020 + index * 0.0010),
                "low": (1.0990 + index * 0.0010),
                "close": (1.1010 + index * 0.0010),
                "tick_volume": (100 + index),
                "spread": 10,
                "real_volume": 0,
            }
            for index, timestamp in enumerate(timestamps)
        ]

    def initialize(
        self,
        *args: object,
        **kwargs: object,
    ) -> bool:
        """Simula un'inizializzazione riuscita."""

        # I parametri non servono al mock.
        del args
        del kwargs

        # Incrementa il contatore.
        self.initialize_calls += 1

        return True

    def shutdown(self) -> None:
        """Simula la chiusura della connessione."""

        self.shutdown_calls += 1

    def last_error(self) -> object:
        """Restituisce un errore temporaneo simulato."""

        return (
            1001,
            "temporary connection error",
        )

    def terminal_info(self) -> object:
        """Restituisce informazioni terminale simulate."""

        return SimpleNamespace(connected=True)

    def account_info(self) -> object:
        """Restituisce informazioni account simulate."""

        return SimpleNamespace(login=12345678)

    def symbol_info(
        self,
        symbol: str,
    ) -> object:
        """Restituisce informazioni del simbolo."""

        return SimpleNamespace(name=symbol)

    def symbol_select(
        self,
        symbol: str,
        enable: bool,
    ) -> bool:
        """Simula l'abilitazione del simbolo."""

        del symbol
        del enable

        return True

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_position: int,
        count: int,
    ) -> object:
        """Fallisce una volta e poi restituisce le candele."""

        # I parametri vengono validati dal provider.
        del symbol
        del timeframe
        del start_position
        del count

        # Incrementa il contatore.
        self.copy_calls += 1

        # Simula la prima perdita di connessione.
        if self.fail_next_poll:
            self.fail_next_poll = False

            return None

        # I polling successivi funzionano.
        return self.rates


def create_mt5_settings():
    """Crea una configurazione MT5 fittizia."""

    return load_settings(
        {
            "DATA_PROVIDER": "MT5",
            "TRADING_SYMBOL": "EURUSD",
            "TIMEFRAME_MINUTES": "15",
            "MT5_LOGIN": "12345678",
            "MT5_PASSWORD": "test-password",
            "MT5_SERVER": ("Demo-Test-Server"),
            "MT5_BARS_PER_POLL": "500",
            "PAPER_TRADING_ONLY": "true",
            "REAL_ORDERS_ENABLED": "false",
        }
    )


def test_failed_poll_disconnects_provider() -> None:
    """Verifica la disconnessione dopo un errore MT5."""

    # Crea il modulo simulato.
    fake_mt5 = ReconnectingFakeMetaTrader5()

    # Crea il provider.
    provider = MetaTrader5PollingDataProvider(
        settings=create_mt5_settings(),
        mt5_module=fake_mt5,
    )

    # Il primo polling deve fallire.
    with pytest.raises(
        MetaTrader5ProviderError,
        match="non ha restituito dati",
    ):
        provider.poll(
            pd.Timestamp(
                "2026-08-20 11:00:00",
                tz="UTC",
            )
        )

    # La connessione deve essere chiusa.
    assert provider.connected is False
    assert fake_mt5.initialize_calls == 1
    assert fake_mt5.shutdown_calls == 1


def test_next_poll_reconnects_automatically() -> None:
    """Verifica la riconnessione al polling successivo."""

    # Crea il modulo simulato.
    fake_mt5 = ReconnectingFakeMetaTrader5()

    # Crea il provider.
    provider = MetaTrader5PollingDataProvider(
        settings=create_mt5_settings(),
        mt5_module=fake_mt5,
    )

    # Il primo polling fallisce e forza la disconnessione.
    with pytest.raises(
        MetaTrader5ProviderError,
    ):
        provider.poll(
            pd.Timestamp(
                "2026-08-20 11:00:00",
                tz="UTC",
            )
        )

    # Il secondo polling deve riconnettersi.
    result = provider.poll(
        pd.Timestamp(
            "2026-08-20 11:00:00",
            tz="UTC",
        )
    )

    # Verifica la nuova connessione.
    assert provider.connected is True
    assert fake_mt5.initialize_calls == 2
    assert fake_mt5.copy_calls == 2

    # Verifica la ricezione delle candele.
    assert len(result.new_closed_bars) == 3

    assert result.provider_name == "MT5_READ_ONLY_M15"


def test_reconnected_provider_avoids_duplicates() -> None:
    """Verifica l'idempotenza dopo la riconnessione."""

    # Crea il modulo simulato.
    fake_mt5 = ReconnectingFakeMetaTrader5()

    # Crea il provider.
    provider = MetaTrader5PollingDataProvider(
        settings=create_mt5_settings(),
        mt5_module=fake_mt5,
    )

    # Il primo polling fallisce.
    with pytest.raises(
        MetaTrader5ProviderError,
    ):
        provider.poll(
            pd.Timestamp(
                "2026-08-20 11:00:00",
                tz="UTC",
            )
        )

    # Il secondo polling riceve le candele.
    first_success = provider.poll(
        pd.Timestamp(
            "2026-08-20 11:00:00",
            tz="UTC",
        )
    )

    # Il terzo polling riceve gli stessi dati.
    second_success = provider.poll(
        pd.Timestamp(
            "2026-08-20 11:01:00",
            tz="UTC",
        )
    )

    # Il primo ciclo riuscito contiene tre candele.
    assert len(first_success.new_closed_bars) == 3

    # Il polling successivo non contiene duplicati.
    assert second_success.new_closed_bars.empty
