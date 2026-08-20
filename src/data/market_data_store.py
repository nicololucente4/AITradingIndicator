"""Archivio SQLite persistente delle candele di mercato."""

# Importa SQLite per la persistenza locale.
import sqlite3

# Importa dataclass per creare report immutabili.
from dataclasses import dataclass

# Importa Path per gestire il percorso del database.
from pathlib import Path

# Importa pandas per elaborare i dati OHLCV.
import pandas as pd

# Importa il catalogo centralizzato dei timeframe.
from src.data.market_timeframes import (
    MarketTimeframeError,
    get_timeframe_by_code,
)

# Importa il validatore OHLCV centrale.
from src.data.validator import validate_ohlcv


class MarketDataStoreError(ValueError):
    """Errore generato dall'archivio delle candele."""


@dataclass(frozen=True)
class MarketDataInsertReport:
    """Risultato dell'inserimento delle candele."""

    # Simbolo associato alle candele.
    symbol: str

    # Timeframe associato alle candele.
    timeframe: str

    # Numero di righe ricevute.
    received_rows: int

    # Numero di nuove righe inserite.
    inserted_rows: int

    # Numero di righe duplicate ignorate.
    duplicate_rows: int

    # Nome del provider dati.
    provider_name: str

    # Timestamp UTC dell'operazione.
    received_at_utc: pd.Timestamp


@dataclass(frozen=True)
class MarketDataAvailability:
    """Descrive un dataset disponibile nell'archivio."""

    # Simbolo disponibile.
    symbol: str

    # Timeframe disponibile.
    timeframe: str

    # Numero di candele archiviate.
    candle_count: int

    # Timestamp della prima candela.
    first_timestamp: pd.Timestamp

    # Timestamp dell'ultima candela.
    latest_timestamp: pd.Timestamp


def _normalize_required_text(
    value: str,
    field_name: str,
) -> str:
    """Normalizza un valore testuale obbligatorio."""

    # Il valore deve essere una stringa.
    if not isinstance(value, str):
        raise MarketDataStoreError(f"{field_name} deve essere una stringa.")

    # Rimuove gli spazi esterni.
    normalized_value = value.strip()

    # Rifiuta stringhe vuote.
    if not normalized_value:
        raise MarketDataStoreError(f"{field_name} non può essere vuoto.")

    return normalized_value


def _normalize_utc_timestamp(
    value: object,
    field_name: str,
) -> pd.Timestamp:
    """Valida e converte un timestamp in UTC."""

    # Converte il valore ricevuto.
    selected_timestamp = pd.Timestamp(value)

    # Il timestamp deve includere una timezone.
    if selected_timestamp.tzinfo is None:
        raise MarketDataStoreError(f"{field_name} deve includere una timezone.")

    # Converte esplicitamente in UTC.
    return selected_timestamp.tz_convert("UTC")


def _validate_timeframe(
    timeframe: str,
) -> str:
    """Normalizza e valida un codice timeframe."""

    # Normalizza il codice.
    selected_timeframe = _normalize_required_text(
        timeframe,
        "timeframe",
    ).upper()

    try:
        # Verifica la presenza nel catalogo centrale.
        get_timeframe_by_code(selected_timeframe)

    except MarketTimeframeError as error:
        raise MarketDataStoreError(f"Timeframe non supportato: {selected_timeframe}.") from error

    return selected_timeframe


class SQLiteMarketDataStore:
    """Archivia candele senza sovrascrivere i record esistenti."""

    def __init__(
        self,
        database_path: str | Path,
    ) -> None:
        """Inizializza l'archivio SQLite."""

        # Verifica che il percorso non sia vuoto.
        if not str(database_path).strip():
            raise MarketDataStoreError("Il percorso del database non può essere vuoto.")

        # Converte il percorso in Path.
        self._database_path = Path(database_path)

        # Crea la cartella di destinazione.
        self._database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # Inizializza il database.
        self._initialize_database()

    @property
    def database_path(self) -> Path:
        """Restituisce il percorso del database."""

        return self._database_path

    def _connect(self) -> sqlite3.Connection:
        """Apre una connessione SQLite."""

        # Crea la connessione.
        connection = sqlite3.connect(self._database_path)

        # Abilita le chiavi esterne.
        connection.execute("PRAGMA foreign_keys = ON")

        return connection

    def _initialize_database(self) -> None:
        """Crea la tabella e gli indici."""

        # Apre una transazione SQLite.
        with self._connect() as connection:
            # Crea la tabella delle candele.
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS market_candles (
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    provider_name TEXT NOT NULL,
                    received_at_utc TEXT NOT NULL,
                    PRIMARY KEY (
                        symbol,
                        timeframe,
                        timestamp
                    )
                )
                """
            )

            # Crea l'indice per le letture cronologiche.
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_market_candles_lookup
                ON market_candles (
                    symbol,
                    timeframe,
                    timestamp
                )
                """
            )

            # Conferma la transazione.
            connection.commit()

    def insert_candles(
        self,
        dataframe: pd.DataFrame,
        *,
        symbol: str,
        timeframe: str,
        provider_name: str,
        received_at_utc: pd.Timestamp,
    ) -> MarketDataInsertReport:
        """Inserisce candele senza modificare quelle esistenti."""

        # Il valore ricevuto deve essere un DataFrame.
        if not isinstance(
            dataframe,
            pd.DataFrame,
        ):
            raise TypeError("dataframe deve essere un pandas DataFrame.")

        # Non accetta dataset vuoti.
        if dataframe.empty:
            raise MarketDataStoreError("Non è possibile archiviare un DataFrame vuoto.")

        # Normalizza il simbolo.
        selected_symbol = _normalize_required_text(
            symbol,
            "symbol",
        ).upper()

        # Normalizza e valida il timeframe.
        selected_timeframe = _validate_timeframe(timeframe)

        # Normalizza il provider.
        selected_provider = _normalize_required_text(
            provider_name,
            "provider_name",
        ).upper()

        # Normalizza il momento di ricezione.
        selected_received_at = _normalize_utc_timestamp(
            received_at_utc,
            "received_at_utc",
        )

        # Valida il dataset OHLCV.
        validated_dataframe = validate_ohlcv(dataframe)

        # Prepara le righe da inserire.
        values: list[tuple[object, ...]] = []

        # Converte ogni candela in una riga SQLite.
        for row in validated_dataframe.itertuples(index=False):
            # Normalizza il timestamp della candela.
            candle_timestamp = _normalize_utc_timestamp(
                row.timestamp,
                "timestamp",
            )

            # Prepara la riga SQLite.
            values.append(
                (
                    selected_symbol,
                    selected_timeframe,
                    candle_timestamp.isoformat(),
                    float(row.open),
                    float(row.high),
                    float(row.low),
                    float(row.close),
                    float(row.volume),
                    selected_provider,
                    selected_received_at.isoformat(),
                )
            )

        # Inserisce le candele in una sola transazione.
        with self._connect() as connection:
            # Memorizza il numero iniziale di modifiche.
            changes_before = connection.total_changes

            # INSERT OR IGNORE mantiene immutabili i record esistenti.
            connection.executemany(
                """
                INSERT OR IGNORE INTO market_candles (
                    symbol,
                    timeframe,
                    timestamp,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    provider_name,
                    received_at_utc
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )

            # Calcola quante righe sono state inserite.
            inserted_rows = connection.total_changes - changes_before

            # Conferma la transazione.
            connection.commit()

        # Calcola il numero di duplicati.
        duplicate_rows = len(validated_dataframe) - inserted_rows

        # Restituisce il report.
        return MarketDataInsertReport(
            symbol=selected_symbol,
            timeframe=selected_timeframe,
            received_rows=len(validated_dataframe),
            inserted_rows=inserted_rows,
            duplicate_rows=duplicate_rows,
            provider_name=selected_provider,
            received_at_utc=(selected_received_at),
        )

    def load_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """Carica le candele in ordine cronologico."""

        # Normalizza il simbolo.
        selected_symbol = _normalize_required_text(
            symbol,
            "symbol",
        ).upper()

        # Normalizza e valida il timeframe.
        selected_timeframe = _validate_timeframe(timeframe)

        # Verifica il limite opzionale.
        if limit is not None and limit <= 0:
            raise MarketDataStoreError("limit deve essere maggiore di zero oppure None.")

        # Senza limite legge tutte le candele.
        if limit is None:
            query = """
                SELECT
                    timestamp,
                    open,
                    high,
                    low,
                    close,
                    volume
                FROM market_candles
                WHERE symbol = ?
                  AND timeframe = ?
                ORDER BY timestamp ASC
            """

            parameters: tuple[
                object,
                ...,
            ] = (
                selected_symbol,
                selected_timeframe,
            )

        # Con limite legge le candele più recenti.
        else:
            query = """
                SELECT
                    timestamp,
                    open,
                    high,
                    low,
                    close,
                    volume
                FROM (
                    SELECT
                        timestamp,
                        open,
                        high,
                        low,
                        close,
                        volume
                    FROM market_candles
                    WHERE symbol = ?
                      AND timeframe = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                )
                ORDER BY timestamp ASC
            """

            parameters = (
                selected_symbol,
                selected_timeframe,
                limit,
            )

        # Esegue la query.
        with self._connect() as connection:
            dataframe = pd.read_sql_query(
                query,
                connection,
                params=parameters,
            )

        # Restituisce uno schema OHLCV vuoto.
        if dataframe.empty:
            return pd.DataFrame(
                columns=[
                    "timestamp",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                ]
            )

        # Converte i timestamp in UTC.
        dataframe["timestamp"] = pd.to_datetime(
            dataframe["timestamp"],
            utc=True,
            errors="raise",
        )

        # Valida il risultato.
        return validate_ohlcv(dataframe)

    def list_availability(
        self,
        *,
        symbol: str | None = None,
    ):
        """Elenca simboli e timeframe presenti nell'archivio."""

        # Senza simbolo restituisce tutti i dataset.
        if symbol is None:
            query = """
                SELECT
                    symbol,
                    timeframe,
                    COUNT(*) AS candle_count,
                    MIN(timestamp) AS first_timestamp,
                    MAX(timestamp) AS latest_timestamp
                FROM market_candles
                GROUP BY symbol, timeframe
                ORDER BY symbol, timeframe
            """

            parameters: tuple[
                object,
                ...,
            ] = ()

        # Con simbolo applica il filtro.
        else:
            selected_symbol = _normalize_required_text(
                symbol,
                "symbol",
            ).upper()

            query = """
                SELECT
                    symbol,
                    timeframe,
                    COUNT(*) AS candle_count,
                    MIN(timestamp) AS first_timestamp,
                    MAX(timestamp) AS latest_timestamp
                FROM market_candles
                WHERE symbol = ?
                GROUP BY symbol, timeframe
                ORDER BY symbol, timeframe
            """

            parameters = (selected_symbol,)

        # Esegue la query aggregata.
        with self._connect() as connection:
            rows = connection.execute(
                query,
                parameters,
            ).fetchall()

        # Prepara il risultato.
        availability: list[MarketDataAvailability] = []

        # Converte ogni riga SQLite.
        for row in rows:
            # Converte il primo timestamp.
            first_timestamp = pd.Timestamp(row[3])

            # Converte l'ultimo timestamp.
            latest_timestamp = pd.Timestamp(row[4])

            # Verifica che i timestamp abbiano una timezone.
            if first_timestamp.tzinfo is None or latest_timestamp.tzinfo is None:
                raise MarketDataStoreError("L'archivio contiene timestamp senza timezone.")

            # Aggiunge la disponibilità.
            availability.append(
                MarketDataAvailability(
                    symbol=str(row[0]),
                    timeframe=str(row[1]),
                    candle_count=int(row[2]),
                    first_timestamp=(first_timestamp.tz_convert("UTC")),
                    latest_timestamp=(latest_timestamp.tz_convert("UTC")),
                )
            )

        return availability

    def count_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
    ) -> int:
        """Conta le candele di un simbolo e timeframe."""

        # Normalizza e valida il timeframe.
        selected_timeframe = _validate_timeframe(timeframe)

        # Recupera i dataset disponibili per il simbolo.
        availability = self.list_availability(symbol=symbol)

        # Cerca il timeframe richiesto.
        for item in availability:
            if item.timeframe == selected_timeframe:
                return item.candle_count

        # Il dataset non è disponibile.
        return 0
