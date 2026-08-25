"""Servizio read-only per il prezzo tick live MetaTrader 5."""

# Importa dataclass per rappresentare un tick immutabile.
from dataclasses import dataclass

# Importa Protocol per descrivere il modulo MT5 richiesto.
from typing import Protocol

# Importa pandas per normalizzare il timestamp UTC.
import pandas as pd

# Importa la configurazione applicativa.
from src.config.settings import ApplicationSettings


class MetaTrader5TickModule(Protocol):
    """Interfaccia minima richiesta al modulo MetaTrader 5."""

    def initialize(
        self,
        *args: object,
        **kwargs: object,
    ) -> bool:
        """Inizializza MetaTrader 5."""

    def shutdown(
        self,
    ) -> None:
        """Chiude MetaTrader 5."""

    def last_error(
        self,
    ) -> object:
        """Restituisce l'ultimo errore MT5."""

    def terminal_info(
        self,
    ) -> object:
        """Restituisce le informazioni del terminale."""

    def account_info(
        self,
    ) -> object:
        """Restituisce le informazioni dell'account."""

    def symbol_info(
        self,
        symbol: str,
    ) -> object:
        """Restituisce le informazioni del simbolo."""

    def symbol_select(
        self,
        symbol: str,
        enable: bool,
    ) -> bool:
        """Abilita il simbolo nel Market Watch."""

    def symbol_info_tick(
        self,
        symbol: str,
    ) -> object:
        """Restituisce l'ultimo tick del simbolo."""


class MetaTrader5TickServiceError(RuntimeError):
    """Errore generato dal servizio tick MT5."""


@dataclass(frozen=True)
class LiveMarketTick:
    """Rappresenta un prezzo live ricevuto da MT5."""

    # Simbolo interrogato.
    symbol: str

    # Miglior prezzo di vendita disponibile.
    bid: float

    # Miglior prezzo di acquisto disponibile.
    ask: float

    # Prezzo medio tra bid e ask.
    mid: float

    # Differenza tra ask e bid.
    spread: float

    # Timestamp UTC del tick.
    timestamp: pd.Timestamp

    # Origine del dato.
    source: str = "MT5_LIVE_TICK"

    def to_dict(
        self,
    ) -> dict[str, object]:
        """Converte il tick in un record JSON."""

        return {
            "symbol": self.symbol,
            "bid": self.bid,
            "ask": self.ask,
            "mid": self.mid,
            "spread": self.spread,
            "timestamp": (self.timestamp.isoformat()),
            "source": self.source,
        }


def normalize_tick_symbol(
    symbol: str,
) -> str:
    """Normalizza e valida un simbolo."""

    if not isinstance(
        symbol,
        str,
    ):
        raise MetaTrader5TickServiceError("symbol deve essere una stringa.")

    selected_symbol = symbol.strip().upper()

    if not selected_symbol:
        raise MetaTrader5TickServiceError("symbol non può essere vuoto.")

    return selected_symbol


class MetaTrader5TickService:
    """Mantiene una connessione read-only per leggere tick live."""

    def __init__(
        self,
        *,
        settings: ApplicationSettings,
        mt5_module: MetaTrader5TickModule,
    ) -> None:
        """Inizializza il servizio tick."""

        if settings.data_provider != "MT5":
            raise MetaTrader5TickServiceError("Il servizio tick richiede DATA_PROVIDER=MT5.")

        if not settings.paper_trading_only:
            raise MetaTrader5TickServiceError("PAPER_TRADING_ONLY deve essere true.")

        if settings.real_orders_enabled:
            raise MetaTrader5TickServiceError("REAL_ORDERS_ENABLED deve essere false.")

        if (
            settings.mt5_login is None
            or settings.mt5_password is None
            or settings.mt5_server is None
        ):
            raise MetaTrader5TickServiceError("La configurazione MT5 è incompleta.")

        self._settings = settings
        self._mt5 = mt5_module
        self._connected = False

    @property
    def connected(
        self,
    ) -> bool:
        """Indica se MT5 è collegato."""

        return self._connected

    def _last_error_text(
        self,
    ) -> str:
        """Restituisce l'ultimo errore MT5."""

        try:
            return str(self._mt5.last_error())

        except Exception:
            return "errore MT5 non disponibile"

    def connect(
        self,
    ) -> None:
        """Apre la connessione read-only a MT5."""

        if self._connected:
            return

        initialize_arguments: dict[
            str,
            object,
        ] = {
            "login": self._settings.mt5_login,
            "password": self._settings.mt5_password,
            "server": self._settings.mt5_server,
            "timeout": (self._settings.mt5_timeout_milliseconds),
        }

        if self._settings.mt5_terminal_path is not None:
            initialize_arguments["path"] = str(self._settings.mt5_terminal_path)

        try:
            initialized = self._mt5.initialize(**initialize_arguments)

        except Exception as error:
            raise MetaTrader5TickServiceError("Errore durante l'inizializzazione MT5.") from error

        if not initialized:
            raise MetaTrader5TickServiceError(
                f"Inizializzazione MT5 fallita: {self._last_error_text()}."
            )

        if self._mt5.terminal_info() is None:
            self._mt5.shutdown()

            raise MetaTrader5TickServiceError("Informazioni terminale MT5 non disponibili.")

        if self._mt5.account_info() is None:
            self._mt5.shutdown()

            raise MetaTrader5TickServiceError("Informazioni account MT5 non disponibili.")

        self._connected = True

    def disconnect(
        self,
    ) -> None:
        """Chiude la connessione MT5."""

        if not self._connected:
            return

        self._mt5.shutdown()

        self._connected = False

    def get_tick(
        self,
        symbol: str,
    ) -> LiveMarketTick:
        """Restituisce l'ultimo tick live del simbolo."""

        selected_symbol = normalize_tick_symbol(symbol)

        if not self._connected:
            self.connect()

        if self._mt5.symbol_info(selected_symbol) is None:
            raise MetaTrader5TickServiceError(f"Simbolo MT5 non disponibile: {selected_symbol}.")

        if not self._mt5.symbol_select(
            selected_symbol,
            True,
        ):
            raise MetaTrader5TickServiceError(
                f"Impossibile abilitare il simbolo {selected_symbol}: {self._last_error_text()}."
            )

        try:
            tick = self._mt5.symbol_info_tick(selected_symbol)

        except Exception as error:
            self.disconnect()

            raise MetaTrader5TickServiceError("Errore durante la lettura del tick MT5.") from error

        if tick is None:
            error_text = self._last_error_text()

            self.disconnect()

            raise MetaTrader5TickServiceError(f"MT5 non ha restituito il tick: {error_text}.")

        try:
            bid = float(
                getattr(
                    tick,
                    "bid",
                )
            )

            ask = float(
                getattr(
                    tick,
                    "ask",
                )
            )

            time_milliseconds = getattr(
                tick,
                "time_msc",
                None,
            )

            if time_milliseconds is not None:
                timestamp = pd.to_datetime(
                    int(time_milliseconds),
                    unit="ms",
                    utc=True,
                )
            else:
                timestamp = pd.to_datetime(
                    int(
                        getattr(
                            tick,
                            "time",
                        )
                    ),
                    unit="s",
                    utc=True,
                )

        except (
            AttributeError,
            TypeError,
            ValueError,
        ) as error:
            raise MetaTrader5TickServiceError("Il tick MT5 contiene valori non validi.") from error

        if bid <= 0 or ask <= 0:
            raise MetaTrader5TickServiceError("Bid e ask devono essere maggiori di zero.")

        if ask < bid:
            raise MetaTrader5TickServiceError("Il prezzo ask non può essere inferiore al bid.")

        spread = ask - bid

        mid = (bid + ask) / 2

        return LiveMarketTick(
            symbol=selected_symbol,
            bid=bid,
            ask=ask,
            mid=mid,
            spread=spread,
            timestamp=timestamp,
        )

    def __enter__(
        self,
    ) -> "MetaTrader5TickService":
        """Apre il servizio come context manager."""

        self.connect()

        return self

    def __exit__(
        self,
        exception_type: object,
        exception_value: object,
        traceback: object,
    ) -> None:
        """Chiude il servizio come context manager."""

        del exception_type
        del exception_value
        del traceback

        self.disconnect()
