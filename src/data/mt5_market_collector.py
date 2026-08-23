"""Collector MT5 multi-strumento e multi-timeframe in sola lettura."""

# Importa dataclass per report e configurazioni immutabili.
from dataclasses import dataclass

# Importa pandas per convertire e validare le candele.
import pandas as pd

# Importa la configurazione applicativa.
from src.config.settings import ApplicationSettings

# Importa lo storage SQLite condiviso.
from src.data.market_data_store import SQLiteMarketDataStore

# Importa il catalogo centralizzato dei timeframe.
from src.data.market_timeframes import (
    MarketTimeframeError,
    get_timeframe_by_code,
)

# Importa il protocollo minimo del modulo MetaTrader 5.
from src.data.mt5_provider import MetaTrader5Module

# Importa il validatore OHLCV centrale.
from src.data.validator import validate_ohlcv


class MetaTrader5MarketCollectorError(RuntimeError):
    """Errore generato dal collector MT5 multi-market."""


@dataclass(frozen=True)
class MarketDatasetRequest:
    """Identifica un dataset richiesto al terminale."""

    # Simbolo MT5, per esempio EURUSD oppure XAUUSD.
    symbol: str

    # Timeframe interno, per esempio M1 oppure H4.
    timeframe: str


@dataclass(frozen=True)
class MarketDatasetResult:
    """Riepilogo dell'acquisizione di un singolo dataset."""

    # Simbolo interrogato.
    symbol: str

    # Timeframe interrogato.
    timeframe: str

    # Numero di candele restituite da MT5.
    received_rows: int

    # Numero di nuove candele inserite.
    inserted_rows: int

    # Numero di duplicati ignorati.
    duplicate_rows: int

    # Esito del dataset.
    successful: bool

    # Messaggio non sensibile.
    message: str


@dataclass(frozen=True)
class MarketCollectionReport:
    """Riepilogo di un ciclo completo del collector."""

    # Timestamp UTC del ciclo.
    collected_at_utc: pd.Timestamp

    # Numero di dataset richiesti.
    requested_datasets: int

    # Numero di dataset completati.
    successful_datasets: int

    # Numero di dataset falliti.
    failed_datasets: int

    # Numero totale di nuove candele.
    inserted_rows: int

    # Risultati dei singoli dataset.
    results: tuple[MarketDatasetResult, ...]


def normalize_market_symbols(
    symbols: tuple[str, ...],
) -> tuple[str, ...]:
    """Normalizza e valida i simboli configurati."""

    # Prepara la lista ordinata senza duplicati.
    normalized_symbols: list[str] = []

    for symbol in symbols:
        # Ogni simbolo deve essere una stringa.
        if not isinstance(symbol, str):
            raise MetaTrader5MarketCollectorError("Ogni simbolo deve essere una stringa.")

        # Normalizza il simbolo.
        selected_symbol = symbol.strip().upper()

        # Rifiuta simboli vuoti.
        if not selected_symbol:
            raise MetaTrader5MarketCollectorError("I simboli configurati non possono essere vuoti.")

        # Mantiene l'ordine ed elimina duplicati.
        if selected_symbol not in normalized_symbols:
            normalized_symbols.append(selected_symbol)

    # Deve esistere almeno un simbolo.
    if not normalized_symbols:
        raise MetaTrader5MarketCollectorError("Deve essere configurato almeno un simbolo.")

    return tuple(normalized_symbols)


def normalize_market_timeframes(
    timeframes: tuple[str, ...],
) -> tuple[str, ...]:
    """Normalizza e valida i timeframe configurati."""

    # Prepara la lista ordinata senza duplicati.
    normalized_timeframes: list[str] = []

    for timeframe in timeframes:
        # Ogni timeframe deve essere una stringa.
        if not isinstance(timeframe, str):
            raise MetaTrader5MarketCollectorError("Ogni timeframe deve essere una stringa.")

        # Normalizza il codice.
        selected_timeframe = timeframe.strip().upper()

        try:
            # Verifica il codice nel catalogo centrale.
            get_timeframe_by_code(selected_timeframe)

        except MarketTimeframeError as error:
            raise MetaTrader5MarketCollectorError(
                f"Timeframe non supportato: {selected_timeframe or '<VUOTO>'}."
            ) from error

        # Mantiene l'ordine ed elimina duplicati.
        if selected_timeframe not in normalized_timeframes:
            normalized_timeframes.append(selected_timeframe)

    # Deve esistere almeno un timeframe.
    if not normalized_timeframes:
        raise MetaTrader5MarketCollectorError("Deve essere configurato almeno un timeframe.")

    return tuple(normalized_timeframes)


class MetaTrader5MarketCollector:
    """Raccoglie candele native MT5 usando una sola connessione."""

    def __init__(
        self,
        *,
        settings: ApplicationSettings,
        mt5_module: MetaTrader5Module,
        store: SQLiteMarketDataStore,
        symbols: tuple[str, ...],
        timeframes: tuple[str, ...],
    ) -> None:
        """Inizializza il collector read-only."""

        # Il collector richiede il provider MT5.
        if settings.data_provider != "MT5":
            raise MetaTrader5MarketCollectorError("Il collector richiede DATA_PROVIDER=MT5.")

        # La modalità deve essere esclusivamente simulata.
        if not settings.paper_trading_only:
            raise MetaTrader5MarketCollectorError("PAPER_TRADING_ONLY deve essere true.")

        # Gli ordini reali devono restare disabilitati.
        if settings.real_orders_enabled:
            raise MetaTrader5MarketCollectorError("REAL_ORDERS_ENABLED deve essere false.")

        # Verifica la configurazione di accesso.
        if (
            settings.mt5_login is None
            or settings.mt5_password is None
            or settings.mt5_server is None
        ):
            raise MetaTrader5MarketCollectorError("La configurazione MT5 è incompleta.")

        # Verifica lo storage.
        if not isinstance(store, SQLiteMarketDataStore):
            raise TypeError("store deve essere un'istanza di SQLiteMarketDataStore.")

        # Salva i componenti.
        self._settings = settings
        self._mt5 = mt5_module
        self._store = store

        # Normalizza simboli e timeframe.
        self._symbols = normalize_market_symbols(symbols)
        self._timeframes = normalize_market_timeframes(timeframes)

        # Il collegamento inizialmente è chiuso.
        self._connected = False

    @property
    def symbols(self) -> tuple[str, ...]:
        """Restituisce i simboli configurati."""

        return self._symbols

    @property
    def timeframes(self) -> tuple[str, ...]:
        """Restituisce i timeframe configurati."""

        return self._timeframes

    @property
    def connected(self) -> bool:
        """Indica se MT5 è collegato."""

        return self._connected

    @property
    def dataset_count(self) -> int:
        """Restituisce il numero di combinazioni richieste."""

        return len(self._symbols) * len(self._timeframes)

    def _last_error_text(self) -> str:
        """Restituisce l'ultimo errore MT5 in forma sicura."""

        try:
            return str(self._mt5.last_error())

        except Exception:
            return "errore MT5 non disponibile"

    def connect(self) -> None:
        """Apre una singola connessione al terminale MT5."""

        # Evita inizializzazioni duplicate.
        if self._connected:
            return

        # Prepara gli argomenti di inizializzazione.
        initialize_arguments: dict[str, object] = {
            "login": self._settings.mt5_login,
            "password": self._settings.mt5_password,
            "server": self._settings.mt5_server,
            "timeout": self._settings.mt5_timeout_milliseconds,
        }

        # Il percorso del terminale è opzionale.
        if self._settings.mt5_terminal_path is not None:
            initialize_arguments["path"] = str(self._settings.mt5_terminal_path)

        try:
            # Inizializza il terminale.
            initialized = self._mt5.initialize(**initialize_arguments)

        except Exception as error:
            raise MetaTrader5MarketCollectorError(
                "Errore durante l'inizializzazione MT5."
            ) from error

        # Verifica l'esito.
        if not initialized:
            raise MetaTrader5MarketCollectorError(
                f"Inizializzazione MT5 fallita: {self._last_error_text()}."
            )

        # Verifica terminale e account.
        if self._mt5.terminal_info() is None:
            self._mt5.shutdown()

            raise MetaTrader5MarketCollectorError("Informazioni terminale MT5 non disponibili.")

        if self._mt5.account_info() is None:
            self._mt5.shutdown()

            raise MetaTrader5MarketCollectorError("Informazioni account MT5 non disponibili.")

        # Verifica e abilita tutti i simboli.
        for symbol in self._symbols:
            if self._mt5.symbol_info(symbol) is None:
                self._mt5.shutdown()

                raise MetaTrader5MarketCollectorError(f"Simbolo MT5 non disponibile: {symbol}.")

            if not self._mt5.symbol_select(symbol, True):
                error_text = self._last_error_text()

                self._mt5.shutdown()

                raise MetaTrader5MarketCollectorError(
                    f"Impossibile abilitare il simbolo {symbol}: {error_text}."
                )

        # Registra la connessione completata.
        self._connected = True

    def disconnect(self) -> None:
        """Chiude la connessione MT5."""

        # Evita chiusure duplicate.
        if not self._connected:
            return

        # Chiude il terminale.
        self._mt5.shutdown()

        # Aggiorna lo stato.
        self._connected = False

    def _resolve_mt5_timeframe(
        self,
        timeframe_code: str,
    ) -> int:
        """Recupera la costante nativa del modulo MT5."""

        # Recupera la definizione centralizzata.
        timeframe = get_timeframe_by_code(timeframe_code)

        try:
            # Legge la costante, per esempio TIMEFRAME_M15.
            timeframe_value = getattr(
                self._mt5,
                timeframe.mt5_attribute,
            )

        except AttributeError as error:
            raise MetaTrader5MarketCollectorError(
                f"Il modulo MT5 non espone {timeframe.mt5_attribute}."
            ) from error

        # La costante deve essere intera.
        if not isinstance(timeframe_value, int):
            raise MetaTrader5MarketCollectorError(f"{timeframe.mt5_attribute} non è valido.")

        return timeframe_value

    @staticmethod
    def _rates_to_dataframe(
        rates: object,
    ) -> pd.DataFrame:
        """Converte una risposta MT5 in OHLCV validato."""

        # Converte la risposta in DataFrame.
        dataframe = pd.DataFrame(rates)

        # Rifiuta una risposta vuota.
        if dataframe.empty:
            raise MetaTrader5MarketCollectorError("MT5 non ha restituito candele.")

        # Definisce lo schema minimo.
        required_columns = {
            "time",
            "open",
            "high",
            "low",
            "close",
            "tick_volume",
        }

        # Individua colonne mancanti.
        missing_columns = required_columns.difference(dataframe.columns)

        if missing_columns:
            missing_text = ", ".join(sorted(missing_columns))

            raise MetaTrader5MarketCollectorError(
                f"Risposta MT5 incompleta. Colonne mancanti: {missing_text}."
            )

        # Converte il timestamp Unix in UTC.
        dataframe["timestamp"] = pd.to_datetime(
            dataframe["time"],
            unit="s",
            utc=True,
            errors="raise",
        )

        # Usa il tick volume come volume operativo.
        dataframe["volume"] = dataframe["tick_volume"]

        # Mantiene lo schema centrale.
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

        # Ordina ed elimina duplicati nella risposta.
        selected_dataframe = (
            selected_dataframe.sort_values("timestamp")
            .drop_duplicates(
                subset=["timestamp"],
                keep="last",
            )
            .reset_index(drop=True)
        )

        # Valida e restituisce.
        return validate_ohlcv(selected_dataframe)

    def _collect_dataset(
        self,
        request: MarketDatasetRequest,
        collected_at_utc: pd.Timestamp,
    ) -> MarketDatasetResult:
        """Raccoglie e archivia un singolo dataset."""

        try:
            # Recupera la costante MT5 nativa.
            timeframe_value = self._resolve_mt5_timeframe(request.timeframe)

            # start_position=1 esclude la candela ancora aperta.
            rates = self._mt5.copy_rates_from_pos(
                request.symbol,
                timeframe_value,
                1,
                self._settings.mt5_bars_per_poll,
            )

            # None indica un errore MT5.
            if rates is None:
                raise MetaTrader5MarketCollectorError(
                    f"MT5 non ha restituito dati: {self._last_error_text()}."
                )

            # Converte e valida le candele.
            dataframe = self._rates_to_dataframe(rates)

            # Salva le candele senza sovrascrivere duplicati.
            insert_report = self._store.insert_candles(
                dataframe,
                symbol=request.symbol,
                timeframe=request.timeframe,
                provider_name=(f"MT5_NATIVE_{request.symbol}_{request.timeframe}"),
                received_at_utc=collected_at_utc,
            )

            # Restituisce il risultato positivo.
            return MarketDatasetResult(
                symbol=request.symbol,
                timeframe=request.timeframe,
                received_rows=len(dataframe),
                inserted_rows=insert_report.inserted_rows,
                duplicate_rows=insert_report.duplicate_rows,
                successful=True,
                message="Dataset acquisito correttamente.",
            )

        except Exception as error:
            # Isola l'errore del singolo dataset.
            return MarketDatasetResult(
                symbol=request.symbol,
                timeframe=request.timeframe,
                received_rows=0,
                inserted_rows=0,
                duplicate_rows=0,
                successful=False,
                message=(f"{type(error).__name__}: {error}"),
            )

    def collect(
        self,
        current_time_utc: pd.Timestamp,
    ) -> MarketCollectionReport:
        """Esegue un ciclo su strumenti e timeframe configurati."""

        # Normalizza il timestamp del ciclo.
        collected_at_utc = pd.Timestamp(current_time_utc)

        # Il timestamp deve avere una timezone.
        if collected_at_utc.tzinfo is None:
            raise MetaTrader5MarketCollectorError(
                "Il timestamp del collector deve includere una timezone."
            )

        # Converte in UTC.
        collected_at_utc = collected_at_utc.tz_convert("UTC")

        # Apre MT5 una sola volta.
        if not self._connected:
            self.connect()

        # Prepara i risultati.
        results: list[MarketDatasetResult] = []

        # Interroga tutte le combinazioni configurate.
        for symbol in self._symbols:
            for timeframe in self._timeframes:
                request = MarketDatasetRequest(
                    symbol=symbol,
                    timeframe=timeframe,
                )

                results.append(
                    self._collect_dataset(
                        request,
                        collected_at_utc,
                    )
                )

        # Calcola i contatori finali.
        successful_datasets = sum(1 for result in results if result.successful)

        failed_datasets = len(results) - successful_datasets

        inserted_rows = sum(result.inserted_rows for result in results)

        # Restituisce il report immutabile.
        return MarketCollectionReport(
            collected_at_utc=collected_at_utc,
            requested_datasets=len(results),
            successful_datasets=successful_datasets,
            failed_datasets=failed_datasets,
            inserted_rows=inserted_rows,
            results=tuple(results),
        )

    def __enter__(
        self,
    ) -> "MetaTrader5MarketCollector":
        """Apre il collector come context manager."""

        self.connect()

        return self

    def __exit__(
        self,
        exception_type: object,
        exception_value: object,
        traceback: object,
    ) -> None:
        """Chiude il collector come context manager."""

        # Gli argomenti non sono necessari per la chiusura.
        del exception_type
        del exception_value
        del traceback

        self.disconnect()
