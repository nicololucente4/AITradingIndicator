"""Provider MetaTrader 5 read-only per il Live Paper Engine."""

# Importa Protocol per descrivere il modulo MetaTrader 5.
from typing import Protocol

# Importa pandas per normalizzare candele e timestamp.
import pandas as pd

# Importa la configurazione centralizzata.
from src.config.settings import ApplicationSettings

# Importa l'interfaccia comune dei provider Live Paper.
from src.data.live_provider import (
    LiveDataProvider,
    LiveDataProviderError,
    PollResult,
)

# Importa il catalogo centralizzato dei timeframe.
from src.data.market_timeframes import (
    MarketTimeframeError,
    get_timeframe_by_minutes,
)

# Importa il validatore centrale OHLCV.
from src.data.validator import validate_ohlcv


class MetaTrader5Module(Protocol):
    """Interfaccia minima richiesta al modulo MetaTrader 5."""

    # Timeframe espressi in minuti.
    TIMEFRAME_M1: int
    TIMEFRAME_M2: int
    TIMEFRAME_M3: int
    TIMEFRAME_M5: int
    TIMEFRAME_M10: int
    TIMEFRAME_M15: int
    TIMEFRAME_M30: int

    # Timeframe espressi in ore.
    TIMEFRAME_H1: int
    TIMEFRAME_H2: int
    TIMEFRAME_H4: int
    TIMEFRAME_H8: int
    TIMEFRAME_H12: int

    # Timeframe giornaliero e settimanale.
    TIMEFRAME_D1: int
    TIMEFRAME_W1: int

    def initialize(
        self,
        *args: object,
        **kwargs: object,
    ) -> bool:
        """Inizializza il collegamento al terminale."""

    def shutdown(self) -> None:
        """Chiude il collegamento al terminale."""

    def last_error(self) -> object:
        """Restituisce l'ultimo errore MT5."""

    def terminal_info(self) -> object:
        """Restituisce le informazioni del terminale."""

    def account_info(self) -> object:
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


class MetaTrader5PollingDataProvider(LiveDataProvider):
    """Legge esclusivamente candele chiuse da MetaTrader 5."""

    def __init__(
        self,
        settings: ApplicationSettings,
        mt5_module: MetaTrader5Module,
    ) -> None:
        """Inizializza il provider read-only."""

        # La configurazione deve selezionare MT5.
        if settings.data_provider != "MT5":
            raise MetaTrader5ProviderError("La configurazione deve utilizzare DATA_PROVIDER=MT5.")

        # Il paper trading deve restare obbligatorio.
        if not settings.paper_trading_only:
            raise MetaTrader5ProviderError("PAPER_TRADING_ONLY deve essere true.")

        # Gli ordini reali devono restare disabilitati.
        if settings.real_orders_enabled:
            raise MetaTrader5ProviderError("REAL_ORDERS_ENABLED deve essere false.")

        # Verifica che la configurazione MT5 sia completa.
        if (
            settings.mt5_login is None
            or settings.mt5_password is None
            or settings.mt5_server is None
        ):
            raise MetaTrader5ProviderError("La configurazione MT5 è incompleta.")

        try:
            # Verifica che il timeframe sia presente nel catalogo.
            get_timeframe_by_minutes(settings.timeframe_minutes)

        except MarketTimeframeError as error:
            raise MetaTrader5ProviderError(
                f"Timeframe MT5 non supportato: {settings.timeframe_minutes} minuti."
            ) from error

        # Salva la configurazione validata.
        self._settings = settings

        # Salva il modulo MT5 reale oppure simulato.
        self._mt5 = mt5_module

        # Nessuna candela è stata ancora emessa.
        self._last_emitted_timestamp: pd.Timestamp | None = None

        # Il collegamento inizialmente è chiuso.
        self._connected = False

    @property
    def last_emitted_timestamp(
        self,
    ) -> pd.Timestamp | None:
        """Restituisce l'ultima candela emessa."""

        return self._last_emitted_timestamp

    @property
    def connected(self) -> bool:
        """Indica se il provider è collegato a MT5."""

        return self._connected

    @property
    def timeframe_code(self) -> str:
        """Restituisce il codice del timeframe configurato."""

        # Recupera il timeframe dal catalogo.
        timeframe = get_timeframe_by_minutes(self._settings.timeframe_minutes)

        return timeframe.code

    def _last_error_text(self) -> str:
        """Restituisce l'ultimo errore MT5 senza credenziali."""

        try:
            # Converte l'errore MT5 in testo.
            return str(self._mt5.last_error())

        except Exception:
            # Mantiene un messaggio sicuro anche se MT5 non risponde.
            return "errore MT5 non disponibile"

    def _resolve_timeframe(self) -> int:
        """Recupera la costante MT5 del timeframe configurato."""

        try:
            # Recupera il timeframe centralizzato.
            timeframe = get_timeframe_by_minutes(self._settings.timeframe_minutes)

        except MarketTimeframeError as error:
            raise MetaTrader5ProviderError(
                f"Timeframe MT5 non supportato: {self._settings.timeframe_minutes} minuti."
            ) from error

        try:
            # Recupera la costante corrispondente dal modulo MT5.
            timeframe_value = getattr(
                self._mt5,
                timeframe.mt5_attribute,
            )

        except AttributeError as error:
            raise MetaTrader5ProviderError(
                f"Il modulo MT5 non espone {timeframe.mt5_attribute}."
            ) from error

        # La costante deve essere rappresentata da un intero.
        if not isinstance(
            timeframe_value,
            int,
        ):
            raise MetaTrader5ProviderError(f"{timeframe.mt5_attribute} non è valido.")

        return timeframe_value

    def connect(self) -> None:
        """Inizializza MT5 e verifica terminale, account e simbolo."""

        # Non ripete l'inizializzazione.
        if self._connected:
            return

        # Prepara i parametri per initialize.
        initialize_arguments: dict[
            str,
            object,
        ] = {
            "login": self._settings.mt5_login,
            "password": (self._settings.mt5_password),
            "server": self._settings.mt5_server,
            "timeout": (self._settings.mt5_timeout_milliseconds),
        }

        # Aggiunge il percorso del terminale solo se configurato.
        if self._settings.mt5_terminal_path is not None:
            initialize_arguments["path"] = str(self._settings.mt5_terminal_path)

        try:
            # Inizializza il collegamento al terminale.
            initialized = self._mt5.initialize(**initialize_arguments)

        except Exception as error:
            raise MetaTrader5ProviderError("Errore durante l'inizializzazione MT5.") from error

        # Interrompe l'operazione se initialize restituisce False.
        if not initialized:
            raise MetaTrader5ProviderError(
                f"Inizializzazione MT5 fallita: {self._last_error_text()}."
            )

        # Verifica le informazioni del terminale.
        if self._mt5.terminal_info() is None:
            self._mt5.shutdown()

            raise MetaTrader5ProviderError("Informazioni terminale MT5 non disponibili.")

        # Verifica le informazioni dell'account.
        if self._mt5.account_info() is None:
            self._mt5.shutdown()

            raise MetaTrader5ProviderError("Informazioni account MT5 non disponibili.")

        # Recupera il simbolo configurato.
        symbol = self._settings.trading_symbol

        # Verifica che il simbolo sia disponibile.
        if self._mt5.symbol_info(symbol) is None:
            self._mt5.shutdown()

            raise MetaTrader5ProviderError(f"Simbolo MT5 non disponibile: {symbol}.")

        # Abilita il simbolo nel Market Watch.
        if not self._mt5.symbol_select(
            symbol,
            True,
        ):
            error_text = self._last_error_text()

            self._mt5.shutdown()

            raise MetaTrader5ProviderError(
                f"Impossibile abilitare il simbolo {symbol}: {error_text}."
            )

        # Registra la connessione completata.
        self._connected = True

    def disconnect(self) -> None:
        """Chiude in modo sicuro il collegamento MT5."""

        # Non chiude un collegamento già inattivo.
        if not self._connected:
            return

        # Chiude il collegamento al terminale.
        self._mt5.shutdown()

        # Aggiorna lo stato interno.
        self._connected = False

    def _validate_current_time(
        self,
        current_time_utc: pd.Timestamp,
    ) -> pd.Timestamp:
        """Valida e normalizza il timestamp del polling."""

        # Converte il valore in Timestamp pandas.
        selected_time = pd.Timestamp(current_time_utc)

        # Il timestamp deve includere una timezone.
        if selected_time.tzinfo is None:
            raise MetaTrader5ProviderError("Il timestamp del polling deve includere una timezone.")

        # Normalizza esplicitamente in UTC.
        return selected_time.tz_convert("UTC")

    def _rates_to_dataframe(
        self,
        rates: object,
    ) -> pd.DataFrame:
        """Converte la risposta MT5 in OHLCV validato."""

        # Converte la risposta MT5 in DataFrame.
        dataframe = pd.DataFrame(rates)

        # Rifiuta una risposta senza candele.
        if dataframe.empty:
            raise MetaTrader5ProviderError("MT5 non ha restituito candele.")

        # Definisce le colonne minime richieste.
        required_columns = {
            "time",
            "open",
            "high",
            "low",
            "close",
            "tick_volume",
        }

        # Individua eventuali colonne mancanti.
        missing_columns = required_columns - set(dataframe.columns)

        # Interrompe la conversione se lo schema è incompleto.
        if missing_columns:
            missing_text = ", ".join(sorted(missing_columns))

            raise MetaTrader5ProviderError(
                f"Risposta MT5 incompleta. Colonne mancanti: {missing_text}."
            )

        # Converte i secondi Unix in timestamp UTC.
        dataframe["timestamp"] = pd.to_datetime(
            dataframe["time"],
            unit="s",
            utc=True,
            errors="raise",
        )

        # Usa il tick volume come volume operativo.
        dataframe["volume"] = dataframe["tick_volume"]

        # Mantiene esclusivamente lo schema OHLCV centrale.
        selected_dataframe = dataframe[
            [
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ]
        ].copy()

        # Ordina cronologicamente e rimuove duplicati.
        selected_dataframe = (
            selected_dataframe.sort_values("timestamp")
            .drop_duplicates(
                subset=["timestamp"],
                keep="last",
            )
            .reset_index(drop=True)
        )

        # Valida il dataset prima di restituirlo.
        return validate_ohlcv(selected_dataframe)

    def poll(
        self,
        current_time_utc: pd.Timestamp,
    ) -> PollResult:
        """Restituisce nuove candele chiuse e non ancora emesse."""

        # Valida il momento del polling.
        selected_time = self._validate_current_time(current_time_utc)

        # Inizializza MT5 solamente quando necessario.
        if not self._connected:
            self.connect()

        # Recupera la costante MT5 del timeframe.
        timeframe_value = self._resolve_timeframe()

        try:
            # start_position=1 esclude la candela corrente.
            rates = self._mt5.copy_rates_from_pos(
                self._settings.trading_symbol,
                timeframe_value,
                1,
                self._settings.mt5_bars_per_poll,
            )

        except Exception as error:
            # Chiude una connessione potenzialmente non affidabile.
            self.disconnect()

            raise MetaTrader5ProviderError(
                "Errore durante la lettura delle candele MT5."
            ) from error

        # None indica un errore dell'API MT5.
        if rates is None:
            error_text = self._last_error_text()

            self.disconnect()

            raise MetaTrader5ProviderError(f"MT5 non ha restituito dati: {error_text}.")

        # Converte e valida le candele.
        dataframe = self._rates_to_dataframe(rates)

        # Calcola l'orario teorico di chiusura.
        candle_close_times = dataframe["timestamp"] + pd.to_timedelta(
            self._settings.timeframe_minutes,
            unit="minutes",
        )

        # Mantiene solamente le candele già chiuse.
        closed_dataframe = dataframe.loc[candle_close_times <= selected_time].copy()

        # Elimina candele già emesse in polling precedenti.
        if self._last_emitted_timestamp is not None:
            closed_dataframe = closed_dataframe.loc[
                closed_dataframe["timestamp"] > self._last_emitted_timestamp
            ].copy()

        # Ripristina l'indice progressivo.
        closed_dataframe = closed_dataframe.reset_index(drop=True)

        # Aggiorna lo stato se sono presenti nuove candele.
        if not closed_dataframe.empty:
            self._last_emitted_timestamp = closed_dataframe.iloc[-1]["timestamp"]

        # Restituisce il risultato standardizzato.
        return PollResult(
            new_closed_bars=closed_dataframe,
            total_source_bars=len(dataframe),
            last_emitted_timestamp=(self._last_emitted_timestamp),
            polled_at_utc=selected_time,
            provider_name=(f"MT5_READ_ONLY_{self.timeframe_code}"),
        )

    def reset(self) -> None:
        """Azzera il timestamp dell'ultima candela emessa."""

        # Non modifica lo stato della connessione.
        self._last_emitted_timestamp = None

    def __enter__(
        self,
    ) -> "MetaTrader5PollingDataProvider":
        """Apre il provider tramite context manager."""

        # Inizializza il collegamento.
        self.connect()

        return self

    def __exit__(
        self,
        exception_type: object,
        exception_value: object,
        traceback: object,
    ) -> None:
        """Chiude il provider tramite context manager."""

        # I parametri descrivono un eventuale errore interno
        # e non sono necessari per la chiusura.
        del exception_type
        del exception_value
        del traceback

        # Chiude il collegamento.
        self.disconnect()
