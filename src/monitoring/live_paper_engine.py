"""Live Paper Engine con persistenza immutabile dei segnali in SQLite."""

# Importa SQLite per salvare localmente i segnali confermati.
import sqlite3

# Importa Callable per definire il processore degli snapshot.
from collections.abc import Callable

# Importa dataclass per rappresentare configurazione e report.
from dataclasses import dataclass

# Importa Path per gestire il percorso del database.
from pathlib import Path

# Importa pandas per gestire storico, timestamp e segnali.
import pandas as pd

# Importa l'interfaccia comune dei provider Live Paper.
from src.data.live_provider import LiveDataProvider


class LivePaperEngineError(ValueError):
    """Errore generato durante l'esecuzione del Live Paper Engine."""


@dataclass(frozen=True)
class LivePaperEngineConfig:
    """Configurazione del Live Paper Engine."""

    # Numero minimo di candele richieste prima dell'inferenza.
    minimum_history_bars: int = 30

    # Percorso del database SQLite locale.
    database_path: str = "data/live_paper/live_paper.db"

    # Modalità obbligatoriamente simulata.
    paper_trading_only: bool = True


@dataclass(frozen=True)
class LivePaperCycleReport:
    """Risultato di un singolo ciclo del Live Paper Engine."""

    # Momento UTC in cui è stato eseguito il polling.
    polled_at_utc: str

    # Numero di nuove candele chiuse ricevute.
    new_closed_bars: int

    # Numero totale di candele mantenute nello storico.
    total_history_bars: int

    # Numero di segnali generati durante il ciclo.
    generated_signals: int

    # Numero di segnali nuovi salvati nel database.
    inserted_signals: int

    # Numero di segnali duplicati ignorati.
    duplicate_signals: int

    # Indica se lo storico minimo è disponibile.
    history_ready: bool


def _validate_config(
    config: LivePaperEngineConfig,
) -> None:
    """Verifica la configurazione del Live Paper Engine."""

    # Lo storico minimo deve contenere almeno una candela.
    if config.minimum_history_bars <= 0:
        raise LivePaperEngineError("Il numero minimo di candele deve essere maggiore di zero.")

    # Il percorso del database non può essere vuoto.
    if not config.database_path.strip():
        raise LivePaperEngineError("Il percorso del database non può essere vuoto.")

    # Questa versione è utilizzabile esclusivamente in paper trading.
    if not config.paper_trading_only:
        raise LivePaperEngineError("Il Live Paper Engine richiede paper_trading_only=true.")


def _validate_processor_output(
    dataframe: pd.DataFrame,
) -> None:
    """Verifica l'output restituito dal processore."""

    # Il processore deve restituire un DataFrame.
    if not isinstance(dataframe, pd.DataFrame):
        raise LivePaperEngineError("Il processore deve restituire un pandas DataFrame.")

    # Il risultato non può essere vuoto.
    if dataframe.empty:
        raise LivePaperEngineError("Il processore ha restituito un DataFrame vuoto.")

    # Definisce le colonne minime necessarie.
    required_columns = {
        "timestamp",
        "signal_available_at",
        "signal",
        "signal_status",
        "signal_source",
    }

    # Individua eventuali colonne mancanti.
    missing_columns = sorted(required_columns.difference(dataframe.columns))

    # Interrompe l'elaborazione se manca almeno una colonna.
    if missing_columns:
        missing_text = ", ".join(missing_columns)

        raise LivePaperEngineError(f"Colonne mancanti nell'output del processore: {missing_text}.")

    # Sono accettati solamente segnali confermati.
    if not dataframe["signal_status"].eq("CONFIRMED").all():
        raise LivePaperEngineError("Il Live Paper Engine accetta solamente segnali confermati.")


class LivePaperEngine:
    """Coordina provider, storico, inferenza e persistenza SQLite."""

    def __init__(
        self,
        provider: LiveDataProvider,
        processor: Callable[[pd.DataFrame], pd.DataFrame],
        config: LivePaperEngineConfig | None = None,
    ) -> None:
        """Inizializza il Live Paper Engine."""

        # Usa la configurazione predefinita se non specificata.
        self._config = config or LivePaperEngineConfig()

        # Valida la configurazione.
        _validate_config(self._config)

        # Il provider deve implementare l'interfaccia richiesta.
        if not isinstance(provider, LiveDataProvider):
            raise TypeError("Il provider deve implementare LiveDataProvider.")

        # Il processore deve essere richiamabile.
        if not callable(processor):
            raise TypeError("Il processore deve essere richiamabile.")

        # Salva provider e processore.
        self._provider = provider
        self._processor = processor

        # Inizializza uno storico OHLCV vuoto.
        self._history = pd.DataFrame(
            columns=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ]
        )

        # Prepara il percorso del database.
        self._database_path = Path(self._config.database_path)

        # Crea il database e la tabella dei segnali.
        self._initialize_database()

    @property
    def history(self) -> pd.DataFrame:
        """Restituisce una copia dello storico disponibile."""

        # Restituisce una copia per impedire modifiche esterne.
        return self._history.copy(deep=True)

    @property
    def database_path(self) -> Path:
        """Restituisce il percorso del database SQLite."""

        return self._database_path

    def _connect(self) -> sqlite3.Connection:
        """Crea una connessione al database SQLite."""

        return sqlite3.connect(self._database_path)

    def _initialize_database(self) -> None:
        """Crea il database e la tabella dei segnali."""

        # Crea la cartella del database.
        self._database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # Apre una connessione al database.
        with self._connect() as connection:
            # Crea la tabella dei segnali se non esiste.
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS signals (
                    signal_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    signal_available_at TEXT NOT NULL,
                    signal TEXT NOT NULL,
                    signal_status TEXT NOT NULL,
                    signal_source TEXT NOT NULL,
                    close_price REAL,
                    entry_price REAL,
                    stop_loss REAL,
                    take_profit_1 REAL,
                    take_profit_2 REAL,
                    take_profit_3 REAL,
                    prediction_confidence REAL,
                    probability_margin REAL,
                    model_version TEXT,
                    model_sha256 TEXT,
                    filter_reason TEXT,
                    operating_mode TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                )
                """
            )

            # Conferma la creazione della struttura.
            connection.commit()

    def _append_history(
        self,
        new_bars: pd.DataFrame,
    ) -> None:
        """Aggiunge nuove candele allo storico senza duplicati."""

        # Non esegue operazioni se non sono presenti nuove candele.
        if new_bars.empty:
            return

        # Unisce storico precedente e nuove candele.
        combined_history = pd.concat(
            [
                self._history,
                new_bars,
            ],
            ignore_index=True,
        )

        # Ordina cronologicamente le candele.
        combined_history = combined_history.sort_values("timestamp")

        # Mantiene una sola riga per ogni timestamp.
        combined_history = combined_history.drop_duplicates(
            subset=["timestamp"],
            keep="first",
        )

        # Ripristina l'indice progressivo.
        self._history = combined_history.reset_index(drop=True)

    @staticmethod
    def _optional_float(
        value: object,
    ) -> float | None:
        """Converte un valore numerico gestendo i campi mancanti."""

        # Restituisce None per valori mancanti o NaN.
        if value is None or pd.isna(value):
            return None

        # Converte il valore in float.
        return float(value)

    @staticmethod
    def _optional_text(
        value: object,
    ) -> str | None:
        """Converte un valore testuale gestendo i campi mancanti."""

        # Restituisce None per valori mancanti o NaN.
        if value is None or pd.isna(value):
            return None

        # Converte il valore in stringa.
        return str(value)

    def _build_signal_id(
        self,
        row: pd.Series,
    ) -> str:
        """Costruisce l'identificativo immutabile del segnale."""

        # Converte il timestamp in formato ISO.
        timestamp_text = pd.Timestamp(row["timestamp"]).isoformat()

        # Recupera la sorgente del segnale.
        signal_source = str(row["signal_source"])

        # Recupera la versione del modello, se disponibile.
        model_version = self._optional_text(row.get("model_version")) or "NO_MODEL"

        # Combina i valori in un identificativo stabile.
        return f"{timestamp_text}|{signal_source}|{model_version}"

    def _insert_signal(
        self,
        row: pd.Series,
        created_at_utc: pd.Timestamp,
    ) -> bool:
        """Inserisce un segnale senza aggiornare record esistenti."""

        # Costruisce l'identificativo univoco.
        signal_id = self._build_signal_id(row)

        # Prepara i valori da salvare.
        values = (
            signal_id,
            pd.Timestamp(row["timestamp"]).isoformat(),
            pd.Timestamp(row["signal_available_at"]).isoformat(),
            str(row["signal"]),
            str(row["signal_status"]),
            str(row["signal_source"]),
            self._optional_float(row.get("close")),
            self._optional_float(row.get("entry_price")),
            self._optional_float(row.get("stop_loss")),
            self._optional_float(row.get("take_profit_1")),
            self._optional_float(row.get("take_profit_2")),
            self._optional_float(row.get("take_profit_3")),
            self._optional_float(row.get("prediction_confidence")),
            self._optional_float(row.get("probability_margin")),
            self._optional_text(row.get("model_version")),
            self._optional_text(row.get("model_sha256")),
            self._optional_text(row.get("filter_reason")),
            "LIVE_PAPER",
            created_at_utc.isoformat(),
        )

        # INSERT OR IGNORE impedisce la modifica retroattiva.
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO signals (
                    signal_id,
                    timestamp,
                    signal_available_at,
                    signal,
                    signal_status,
                    signal_source,
                    close_price,
                    entry_price,
                    stop_loss,
                    take_profit_1,
                    take_profit_2,
                    take_profit_3,
                    prediction_confidence,
                    probability_margin,
                    model_version,
                    model_sha256,
                    filter_reason,
                    operating_mode,
                    created_at_utc
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )

            # Conferma l'inserimento.
            connection.commit()

            # rowcount uguale a uno indica un nuovo record.
            return cursor.rowcount == 1

    def run_cycle(
        self,
        current_time_utc: pd.Timestamp,
    ) -> LivePaperCycleReport:
        """Esegue un ciclo completo di polling e inferenza."""

        # Converte il timestamp ricevuto.
        selected_time = pd.Timestamp(current_time_utc)

        # Il timestamp deve includere una timezone.
        if selected_time.tzinfo is None:
            raise LivePaperEngineError("Il timestamp del ciclo deve includere una timezone.")

        # Converte il timestamp in UTC.
        selected_time = selected_time.tz_convert("UTC")

        # Interroga il provider dati.
        poll_result = self._provider.poll(current_time_utc=selected_time)

        # Aggiunge allo storico le nuove candele chiuse.
        self._append_history(poll_result.new_closed_bars)

        # Controlla se è disponibile lo storico minimo.
        history_ready = len(self._history) >= self._config.minimum_history_bars

        # Inizializza i contatori del ciclo.
        generated_signals = 0
        inserted_signals = 0
        duplicate_signals = 0

        # Esegue il processore solamente se:
        # 1. sono arrivate nuove candele;
        # 2. lo storico minimo è disponibile.
        if not poll_result.new_closed_bars.empty and history_ready:
            # Elabora una copia dello storico disponibile.
            processor_output = self._processor(self._history.copy(deep=True))

            # Verifica la struttura dell'output.
            _validate_processor_output(processor_output)

            # Considera solamente l'ultima riga prodotta.
            current_signal = processor_output.iloc[-1]

            # Recupera il timestamp dell'ultima candela storica.
            latest_history_timestamp = self._history.iloc[-1]["timestamp"]

            # Il segnale deve riferirsi all'ultima candela disponibile.
            if pd.Timestamp(current_signal["timestamp"]) != pd.Timestamp(latest_history_timestamp):
                raise LivePaperEngineError(
                    "Il processore non ha restituito il segnale "
                    "relativo all'ultima candela disponibile."
                )

            # Registra un segnale generato.
            generated_signals = 1

            # Inserisce il segnale senza consentire sovrascritture.
            inserted = self._insert_signal(
                row=current_signal,
                created_at_utc=selected_time,
            )

            # Aggiorna i contatori.
            if inserted:
                inserted_signals = 1
            else:
                duplicate_signals = 1

        # Restituisce il report del ciclo.
        return LivePaperCycleReport(
            polled_at_utc=selected_time.isoformat(),
            new_closed_bars=len(poll_result.new_closed_bars),
            total_history_bars=len(self._history),
            generated_signals=generated_signals,
            inserted_signals=inserted_signals,
            duplicate_signals=duplicate_signals,
            history_ready=history_ready,
        )

    def load_signals(self) -> pd.DataFrame:
        """Carica tutti i segnali salvati nel database."""

        # Legge i segnali in ordine cronologico.
        with self._connect() as connection:
            signals = pd.read_sql_query(
                """
                SELECT *
                FROM signals
                ORDER BY timestamp ASC
                """,
                connection,
            )

        # Restituisce il registro completo.
        return signals
