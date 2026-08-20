"""Provider MetaTrader 5 read-only per il Live Paper Engine."""

from typing import Protocol

import pandas as pd

from src.config.settings import ApplicationSettings
from src.data.live_provider import LiveDataProvider, LiveDataProviderError, PollResult
from src.data.validator import validate_ohlcv


class MetaTrader5Module(Protocol):
    """Interfaccia minima richiesta al modulo MetaTrader 5."""

    TIMEFRAME_M1: int
    TIMEFRAME_M5: int
    TIMEFRAME_M15: int
    TIMEFRAME_H1: int
    TIMEFRAME_H4: int
    TIMEFRAME_D1: int

    def initialize(self, *args: object, **kwargs: object) -> bool:
        """Inizializza il collegamento al terminale."""

    def shutdown(self) -> None:
        """Chiude il collegamento al terminale."""

    def last_error(self) -> object:
        """Restituisce l'ultimo errore MT5."""

    def terminal_info(self) -> object:
        """Restituisce le informazioni del terminale."""

    def account_info(self) -> object:
        """Restituisce le informazioni dell'account."""

    def symbol_info(self, symbol: str) -> object:
        """Restituisce le informazioni del simbolo."""

    def symbol_select(self, symbol: str, enable: bool) -> bool:
        """Abilita o disabilita il simbolo nel Market Watch."""

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_position: int,
        count: int,
    ) -> object:
        """Recupera le candele dal terminale."""


class MetaTrader5ProviderError(LiveDataProviderError):
    """Errore generato dal provider MetaTrader 5."""


TIMEFRAME_ATTRIBUTE_BY_MINUTES: dict[int, str] = {
    1: "TIMEFRAME_M1",
    5: "TIMEFRAME_M5",
    15: "TIMEFRAME_M15",
    60: "TIMEFRAME_H1",
    240: "TIMEFRAME_H4",
    1440: "TIMEFRAME_D1",
}


class MetaTrader5PollingDataProvider(LiveDataProvider):
    """Legge esclusivamente candele chiuse da MetaTrader 5."""

    def __init__(
        self,
        settings: ApplicationSettings,
        mt5_module: MetaTrader5Module,
    ) -> None:
        """Inizializza il provider read-only."""

        if settings.data_provider != "MT5":
            raise MetaTrader5ProviderError("La configurazione deve utilizzare DATA_PROVIDER=MT5.")

        if not settings.paper_trading_only:
            raise MetaTrader5ProviderError("PAPER_TRADING_ONLY deve essere true.")

        if settings.real_orders_enabled:
            raise MetaTrader5ProviderError("REAL_ORDERS_ENABLED deve essere false.")

        if (
            settings.mt5_login is None
            or settings.mt5_password is None
            or settings.mt5_server is None
        ):
            raise MetaTrader5ProviderError("La configurazione MT5 e incompleta.")

        if settings.timeframe_minutes not in TIMEFRAME_ATTRIBUTE_BY_MINUTES:
            raise MetaTrader5ProviderError(
                f"Timeframe MT5 non supportato: {settings.timeframe_minutes} minuti."
            )

        self._settings = settings
        self._mt5 = mt5_module
        self._last_emitted_timestamp: pd.Timestamp | None = None
        self._connected = False

    @property
    def last_emitted_timestamp(self) -> pd.Timestamp | None:
        """Restituisce l'ultima candela emessa."""

        return self._last_emitted_timestamp

    @property
    def connected(self) -> bool:
        """Indica se il provider e collegato a MT5."""

        return self._connected

    def _last_error_text(self) -> str:
        """Restituisce l'ultimo errore MT5 senza credenziali."""

        try:
            return str(self._mt5.last_error())
        except Exception:
            return "errore MT5 non disponibile"

    def _resolve_timeframe(self) -> int:
        """Recupera la costante MetaTrader 5 del timeframe configurato."""

        attribute_name = TIMEFRAME_ATTRIBUTE_BY_MINUTES[self._settings.timeframe_minutes]

        try:
            timeframe_value = getattr(self._mt5, attribute_name)
        except AttributeError as error:
            raise MetaTrader5ProviderError(f"Il modulo MT5 non espone {attribute_name}.") from error

        if not isinstance(timeframe_value, int):
            raise MetaTrader5ProviderError(f"{attribute_name} non e valido.")

        return timeframe_value

    def connect(self) -> None:
        """Inizializza MT5 e verifica terminale, account e simbolo."""

        if self._connected:
            return

        initialize_arguments: dict[str, object] = {
            "login": self._settings.mt5_login,
            "password": self._settings.mt5_password,
            "server": self._settings.mt5_server,
            "timeout": self._settings.mt5_timeout_milliseconds,
        }

        if self._settings.mt5_terminal_path is not None:
            initialize_arguments["path"] = str(self._settings.mt5_terminal_path)

        try:
            initialized = self._mt5.initialize(**initialize_arguments)
        except Exception as error:
            raise MetaTrader5ProviderError("Errore durante l'inizializzazione MT5.") from error

        if not initialized:
            raise MetaTrader5ProviderError(
                f"Inizializzazione MT5 fallita: {self._last_error_text()}."
            )

        if self._mt5.terminal_info() is None:
            self._mt5.shutdown()
            raise MetaTrader5ProviderError("Informazioni terminale MT5 non disponibili.")

        if self._mt5.account_info() is None:
            self._mt5.shutdown()
            raise MetaTrader5ProviderError("Informazioni account MT5 non disponibili.")

        symbol = self._settings.trading_symbol

        if self._mt5.symbol_info(symbol) is None:
            self._mt5.shutdown()
            raise MetaTrader5ProviderError(f"Simbolo MT5 non disponibile: {symbol}.")

        if not self._mt5.symbol_select(symbol, True):
            error_text = self._last_error_text()
            self._mt5.shutdown()
            raise MetaTrader5ProviderError(
                f"Impossibile abilitare il simbolo {symbol}: {error_text}."
            )

        self._connected = True

    def disconnect(self) -> None:
        """Chiude in modo sicuro il collegamento MT5."""

        if not self._connected:
            return

        self._mt5.shutdown()
        self._connected = False

    def _validate_current_time(
        self,
        current_time_utc: pd.Timestamp,
    ) -> pd.Timestamp:
        """Valida e normalizza il timestamp del polling."""

        selected_time = pd.Timestamp(current_time_utc)

        if selected_time.tzinfo is None:
            raise MetaTrader5ProviderError("Il timestamp del polling deve includere una timezone.")

        return selected_time.tz_convert("UTC")

    def _rates_to_dataframe(self, rates: object) -> pd.DataFrame:
        """Converte la risposta MT5 in un DataFrame OHLCV validato."""

        dataframe = pd.DataFrame(rates)

        if dataframe.empty:
            raise MetaTrader5ProviderError("MT5 non ha restituito candele.")

        required_columns = {
            "time",
            "open",
            "high",
            "low",
            "close",
            "tick_volume",
        }
        missing_columns = required_columns - set(dataframe.columns)

        if missing_columns:
            missing_text = ", ".join(sorted(missing_columns))
            raise MetaTrader5ProviderError(
                f"Risposta MT5 incompleta. Colonne mancanti: {missing_text}."
            )

        dataframe["timestamp"] = pd.to_datetime(
            dataframe["time"],
            unit="s",
            utc=True,
            errors="raise",
        )
        dataframe["volume"] = dataframe["tick_volume"]

        selected_dataframe = dataframe[
            ["timestamp", "open", "high", "low", "close", "volume"]
        ].copy()
        selected_dataframe = (
            selected_dataframe.sort_values("timestamp")
            .drop_duplicates(subset=["timestamp"], keep="last")
            .reset_index(drop=True)
        )

        return validate_ohlcv(selected_dataframe)

    def poll(self, current_time_utc: pd.Timestamp) -> PollResult:
        """Restituisce le nuove candele MT5 confermate e non ancora emesse."""

        selected_time = self._validate_current_time(current_time_utc)

        if not self._connected:
            self.connect()

        timeframe = self._resolve_timeframe()

        try:
            rates = self._mt5.copy_rates_from_pos(
                self._settings.trading_symbol,
                timeframe,
                1,
                self._settings.mt5_bars_per_poll,
            )
        except Exception as error:
            self.disconnect()
            raise MetaTrader5ProviderError(
                "Errore durante la lettura delle candele MT5."
            ) from error

        if rates is None:
            error_text = self._last_error_text()
            self.disconnect()
            raise MetaTrader5ProviderError(f"MT5 non ha restituito dati: {error_text}.")

        dataframe = self._rates_to_dataframe(rates)
        candle_close_times = dataframe["timestamp"] + pd.to_timedelta(
            self._settings.timeframe_minutes,
            unit="minutes",
        )
        closed_dataframe = dataframe.loc[candle_close_times <= selected_time].copy()

        if self._last_emitted_timestamp is not None:
            closed_dataframe = closed_dataframe.loc[
                closed_dataframe["timestamp"] > self._last_emitted_timestamp
            ].copy()

        closed_dataframe = closed_dataframe.reset_index(drop=True)

        if not closed_dataframe.empty:
            self._last_emitted_timestamp = closed_dataframe.iloc[-1]["timestamp"]

        return PollResult(
            new_closed_bars=closed_dataframe,
            total_source_bars=len(dataframe),
            last_emitted_timestamp=self._last_emitted_timestamp,
            polled_at_utc=selected_time,
            provider_name="MT5_READ_ONLY",
        )

    def reset(self) -> None:
        """Azzera il timestamp dell'ultima candela emessa."""

        self._last_emitted_timestamp = None

    def __enter__(self) -> "MetaTrader5PollingDataProvider":
        """Apre il provider tramite context manager."""

        self.connect()
        return self

    def __exit__(
        self,
        exception_type: object,
        exception_value: object,
        traceback: object,
    ) -> None:
        """Chiude il provider tramite context manager."""

        self.disconnect()
