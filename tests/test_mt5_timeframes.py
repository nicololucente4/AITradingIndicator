"""Test dei timeframe professionali nel provider MetaTrader 5."""

# Importa SimpleNamespace per simulare le risposte MT5.
from types import SimpleNamespace

# Importa pandas per creare timestamp e dati OHLCV.
import pandas as pd

# Importa pytest per parametrizzare i test.
import pytest

# Importa il caricatore della configurazione.
from src.config.settings import load_settings

# Importa il catalogo centralizzato.
from src.data.market_timeframes import (
    MARKET_TIMEFRAMES,
)

# Importa il provider MT5.
from src.data.mt5_provider import (
    MetaTrader5PollingDataProvider,
)


class ProfessionalTimeframeFakeMT5:
    """Simula tutte le costanti timeframe richieste."""

    # Timeframe minuti.
    TIMEFRAME_M1 = 1
    TIMEFRAME_M2 = 2
    TIMEFRAME_M3 = 3
    TIMEFRAME_M5 = 5
    TIMEFRAME_M10 = 10
    TIMEFRAME_M15 = 15
    TIMEFRAME_M30 = 30

    # Timeframe ore.
    TIMEFRAME_H1 = 60
    TIMEFRAME_H2 = 120
    TIMEFRAME_H4 = 240
    TIMEFRAME_H8 = 480
    TIMEFRAME_H12 = 720

    # Timeframe superiori.
    TIMEFRAME_D1 = 1440
    TIMEFRAME_W1 = 10080

    def __init__(
        self,
        timeframe_minutes: int,
    ) -> None:
        """Inizializza il modulo simulato."""

        # Salva la durata usata per generare le candele.
        self.timeframe_minutes = timeframe_minutes

        # Memorizza le richieste effettuate.
        self.copy_calls: list[
            tuple[
                str,
                int,
                int,
                int,
            ]
        ] = []

        # Registra le chiusure.
        self.shutdown_calls = 0

    def initialize(
        self,
        *args: object,
        **kwargs: object,
    ) -> bool:
        """Simula un collegamento riuscito."""

        # I parametri non sono richiesti dal mock.
        del args
        del kwargs

        return True

    def shutdown(self) -> None:
        """Simula la chiusura del collegamento."""

        self.shutdown_calls += 1

    def last_error(self) -> object:
        """Restituisce uno stato senza errori."""

        return (
            0,
            "success",
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
        """Restituisce informazioni simbolo simulate."""

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
        """Restituisce tre candele chiuse simulate."""

        # Registra la richiesta.
        self.copy_calls.append(
            (
                symbol,
                timeframe,
                start_position,
                count,
            )
        )

        # Genera tre timestamp consecutivi.
        timestamps = pd.date_range(
            start="2026-08-01 00:00:00",
            periods=3,
            freq=(f"{self.timeframe_minutes}min"),
            tz="UTC",
        )

        # Restituisce il formato MT5.
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


def create_settings(
    timeframe_minutes: int,
) -> object:
    """Crea una configurazione MT5 fittizia."""

    return load_settings(
        {
            "DATA_PROVIDER": "MT5",
            "TRADING_SYMBOL": "EURUSD",
            "TIMEFRAME_MINUTES": str(timeframe_minutes),
            "MT5_LOGIN": "12345678",
            "MT5_PASSWORD": "test-password",
            "MT5_SERVER": ("Demo-Test-Server"),
            "MT5_BARS_PER_POLL": "500",
            "PAPER_TRADING_ONLY": "true",
            "REAL_ORDERS_ENABLED": "false",
        }
    )


@pytest.mark.parametrize(
    (
        "timeframe_code",
        "timeframe_minutes",
        "mt5_attribute",
    ),
    [
        (
            timeframe.code,
            timeframe.minutes,
            timeframe.mt5_attribute,
        )
        for timeframe in MARKET_TIMEFRAMES
    ],
)
def test_professional_timeframe_is_resolved(
    timeframe_code: str,
    timeframe_minutes: int,
    mt5_attribute: str,
) -> None:
    """Verifica ogni risoluzione del catalogo MT5."""

    # Crea il modulo simulato.
    fake_mt5 = ProfessionalTimeframeFakeMT5(timeframe_minutes)

    # Crea il provider.
    provider = MetaTrader5PollingDataProvider(
        settings=create_settings(timeframe_minutes),
        mt5_module=fake_mt5,
    )

    # Esegue il polling dopo la chiusura delle tre candele.
    result = provider.poll(
        pd.Timestamp(
            "2026-09-01 00:00:00",
            tz="UTC",
        )
    )

    # Recupera la costante prevista dal modulo simulato.
    expected_mt5_value = getattr(
        fake_mt5,
        mt5_attribute,
    )

    # Verifica il codice risolto.
    assert provider.timeframe_code == timeframe_code

    # Verifica la chiamata inviata a MT5.
    assert fake_mt5.copy_calls == [
        (
            "EURUSD",
            expected_mt5_value,
            1,
            500,
        )
    ]

    # Verifica il nome del provider.
    assert result.provider_name == f"MT5_READ_ONLY_{timeframe_code}"

    # Verifica la validazione delle candele.
    assert len(result.new_closed_bars) == 3

    # Chiude il provider.
    provider.disconnect()
