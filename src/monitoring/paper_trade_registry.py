"""Registro persistente delle operazioni simulate."""

# Importa hashlib per creare identificativi deterministici.
import hashlib

# Importa SQLite per la persistenza locale.
import sqlite3

# Importa dataclass per configurazione e report immutabili.
from dataclasses import dataclass

# Importa Path per gestire il database.
from pathlib import Path

# Importa pandas per segnali, esiti e timestamp.
import pandas as pd


class PaperTradeRegistryError(ValueError):
    """Errore generato dal registro delle operazioni paper."""


@dataclass(frozen=True)
class PaperTradeRegistryConfig:
    """Configurazione del registro paper trading."""

    # Simbolo associato al motore operativo.
    symbol: str = "EURUSD"

    # Timeframe associato al modello.
    timeframe: str = "M15"

    # Consente una sola operazione aperta per simbolo.
    one_open_trade_per_symbol: bool = True

    # Modalità obbligatoriamente simulata.
    paper_trading_only: bool = True


@dataclass(frozen=True)
class PaperTradeSyncReport:
    """Risultato della sincronizzazione del registro."""

    # Segnali direzionali analizzati.
    evaluated_signals: int

    # Nuove operazioni aperte.
    opened_trades: int

    # Operazioni chiuse durante il ciclo.
    closed_trades: int

    # Segnali ignorati perché esisteva già una posizione aperta.
    ignored_open_position: int

    # Segnali NO_TRADE ignorati.
    ignored_no_trade: int

    # Operazioni già presenti.
    duplicate_trades: int


def _normalize_required_text(
    value: str,
    *,
    field_name: str,
) -> str:
    """Normalizza un valore testuale obbligatorio."""

    if not isinstance(
        value,
        str,
    ):
        raise PaperTradeRegistryError(f"{field_name} deve essere una stringa.")

    normalized_value = value.strip().upper()

    if not normalized_value:
        raise PaperTradeRegistryError(f"{field_name} non può essere vuoto.")

    return normalized_value


def _validate_config(
    config: PaperTradeRegistryConfig,
) -> None:
    """Verifica la configurazione del registro."""

    _normalize_required_text(
        config.symbol,
        field_name="symbol",
    )

    _normalize_required_text(
        config.timeframe,
        field_name="timeframe",
    )

    if not config.one_open_trade_per_symbol:
        raise PaperTradeRegistryError(
            "La prima versione richiede una sola operazione aperta per simbolo."
        )

    if not config.paper_trading_only:
        raise PaperTradeRegistryError("Il registro richiede paper_trading_only=true.")


def _validate_signals(
    signals: pd.DataFrame,
) -> None:
    """Verifica il registro dei segnali."""

    if not isinstance(
        signals,
        pd.DataFrame,
    ):
        raise TypeError("signals deve essere un pandas DataFrame.")

    required_columns = {
        "signal_id",
        "timestamp",
        "signal",
        "signal_status",
        "entry_price",
        "stop_loss",
        "take_profit_1",
        "prediction_confidence",
        "model_version",
    }

    missing_columns = sorted(required_columns.difference(signals.columns))

    if missing_columns:
        raise PaperTradeRegistryError(
            f"Colonne mancanti nei segnali: {', '.join(missing_columns)}."
        )

    if signals["signal_id"].duplicated().any():
        raise PaperTradeRegistryError("Il registro contiene signal_id duplicati.")


def _validate_outcomes(
    outcomes: pd.DataFrame,
) -> None:
    """Verifica il registro degli esiti."""

    if not isinstance(
        outcomes,
        pd.DataFrame,
    ):
        raise TypeError("outcomes deve essere un pandas DataFrame.")

    if outcomes.empty:
        return

    required_columns = {
        "signal_id",
        "direction",
        "exit_price",
        "exit_reason",
        "exit_timestamp",
        "holding_bars",
        "gross_return_percentage",
        "result_r",
    }

    missing_columns = sorted(required_columns.difference(outcomes.columns))

    if missing_columns:
        raise PaperTradeRegistryError(
            f"Colonne mancanti negli esiti: {', '.join(missing_columns)}."
        )

    if outcomes["signal_id"].duplicated().any():
        raise PaperTradeRegistryError("Il registro contiene esiti duplicati.")


class PaperTradeRegistry:
    """Mantiene apertura e chiusura delle operazioni simulate."""

    def __init__(
        self,
        database_path: str | Path,
        config: PaperTradeRegistryConfig | None = None,
    ) -> None:
        """Inizializza il registro persistente."""

        self._config = config or PaperTradeRegistryConfig()

        _validate_config(self._config)

        self._symbol = _normalize_required_text(
            self._config.symbol,
            field_name="symbol",
        )

        self._timeframe = _normalize_required_text(
            self._config.timeframe,
            field_name="timeframe",
        )

        self._database_path = Path(database_path)

        if not str(self._database_path).strip():
            raise PaperTradeRegistryError("Il percorso del database non può essere vuoto.")

        self._initialize_database()

    @property
    def database_path(
        self,
    ) -> Path:
        """Restituisce il percorso del database."""

        return self._database_path

    @property
    def symbol(
        self,
    ) -> str:
        """Restituisce il simbolo operativo."""

        return self._symbol

    @property
    def timeframe(
        self,
    ) -> str:
        """Restituisce il timeframe operativo."""

        return self._timeframe

    def _connect(
        self,
    ) -> sqlite3.Connection:
        """Apre una connessione SQLite."""

        connection = sqlite3.connect(self._database_path)

        connection.row_factory = sqlite3.Row

        return connection

    def _initialize_database(
        self,
    ) -> None:
        """Crea la tabella delle operazioni simulate."""

        self._database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS paper_trades (
                    trade_id TEXT PRIMARY KEY,
                    signal_id TEXT NOT NULL UNIQUE,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    status TEXT NOT NULL,
                    opened_at_utc TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit_1 REAL NOT NULL,
                    prediction_confidence REAL,
                    model_version TEXT,
                    closed_at_utc TEXT,
                    exit_price REAL,
                    exit_reason TEXT,
                    holding_bars INTEGER,
                    gross_return_percentage REAL,
                    result_r REAL,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_paper_trades_symbol_status
                ON paper_trades (
                    symbol,
                    status
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_paper_trades_opened_at
                ON paper_trades (
                    opened_at_utc
                )
                """
            )

            connection.commit()

    def _build_trade_id(
        self,
        signal_id: str,
    ) -> str:
        """Crea un identificativo stabile dell'operazione."""

        signal_hash = hashlib.sha256(signal_id.encode("utf-8")).hexdigest()[:12].upper()

        return f"TRD-{self._symbol}-{self._timeframe}-{signal_hash}"

    def _trade_exists(
        self,
        signal_id: str,
    ) -> bool:
        """Verifica se il segnale possiede già un trade."""

        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT 1
                FROM paper_trades
                WHERE signal_id = ?
                LIMIT 1
                """,
                (signal_id,),
            )

            return cursor.fetchone() is not None

    def _has_open_trade(
        self,
    ) -> bool:
        """Verifica se esiste una posizione aperta sul simbolo."""

        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT 1
                FROM paper_trades
                WHERE symbol = ?
                  AND status = 'OPEN'
                LIMIT 1
                """,
                (self._symbol,),
            )

            return cursor.fetchone() is not None

    @staticmethod
    def _required_float(
        value: object,
        *,
        field_name: str,
    ) -> float:
        """Converte un valore numerico obbligatorio."""

        if value is None or pd.isna(value):
            raise PaperTradeRegistryError(f"{field_name} è obbligatorio.")

        selected_value = float(value)

        if selected_value <= 0:
            raise PaperTradeRegistryError(f"{field_name} deve essere maggiore di zero.")

        return selected_value

    @staticmethod
    def _optional_float(
        value: object,
    ) -> float | None:
        """Converte un valore numerico opzionale."""

        if value is None or pd.isna(value):
            return None

        return float(value)

    @staticmethod
    def _optional_text(
        value: object,
    ) -> str | None:
        """Converte un valore testuale opzionale."""

        if value is None or pd.isna(value):
            return None

        selected_value = str(value).strip()

        return selected_value or None

    def _open_trade(
        self,
        signal_row: pd.Series,
        synchronized_at_utc: pd.Timestamp,
    ) -> bool:
        """Apre una nuova operazione simulata."""

        signal_id = str(signal_row["signal_id"])

        trade_id = self._build_trade_id(signal_id)

        direction = str(signal_row["signal"]).upper()

        entry_price = self._required_float(
            signal_row["entry_price"],
            field_name="entry_price",
        )

        stop_loss = self._required_float(
            signal_row["stop_loss"],
            field_name="stop_loss",
        )

        take_profit_1 = self._required_float(
            signal_row["take_profit_1"],
            field_name="take_profit_1",
        )

        opened_at_utc = pd.Timestamp(signal_row["timestamp"])

        if opened_at_utc.tzinfo is None:
            opened_at_utc = opened_at_utc.tz_localize("UTC")
        else:
            opened_at_utc = opened_at_utc.tz_convert("UTC")

        values = (
            trade_id,
            signal_id,
            self._symbol,
            self._timeframe,
            direction,
            "OPEN",
            opened_at_utc.isoformat(),
            entry_price,
            stop_loss,
            take_profit_1,
            self._optional_float(signal_row["prediction_confidence"]),
            self._optional_text(signal_row["model_version"]),
            synchronized_at_utc.isoformat(),
            synchronized_at_utc.isoformat(),
        )

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO paper_trades (
                    trade_id,
                    signal_id,
                    symbol,
                    timeframe,
                    direction,
                    status,
                    opened_at_utc,
                    entry_price,
                    stop_loss,
                    take_profit_1,
                    prediction_confidence,
                    model_version,
                    created_at_utc,
                    updated_at_utc
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?
                )
                """,
                values,
            )

            connection.commit()

            return cursor.rowcount == 1

    def _close_trade(
        self,
        outcome_row: pd.Series,
        synchronized_at_utc: pd.Timestamp,
    ) -> bool:
        """Chiude l'operazione collegata all'esito."""

        signal_id = str(outcome_row["signal_id"])

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE paper_trades
                SET
                    status = 'CLOSED',
                    closed_at_utc = ?,
                    exit_price = ?,
                    exit_reason = ?,
                    holding_bars = ?,
                    gross_return_percentage = ?,
                    result_r = ?,
                    updated_at_utc = ?
                WHERE signal_id = ?
                  AND status = 'OPEN'
                """,
                (
                    pd.Timestamp(outcome_row["exit_timestamp"]).isoformat(),
                    float(outcome_row["exit_price"]),
                    str(outcome_row["exit_reason"]),
                    int(outcome_row["holding_bars"]),
                    float(outcome_row["gross_return_percentage"]),
                    self._optional_float(outcome_row["result_r"]),
                    synchronized_at_utc.isoformat(),
                    signal_id,
                ),
            )

            connection.commit()

            return cursor.rowcount == 1

    def synchronize(
        self,
        *,
        signals: pd.DataFrame,
        outcomes: pd.DataFrame,
        synchronized_at_utc: pd.Timestamp,
    ) -> PaperTradeSyncReport:
        """Sincronizza segnali ed esiti con le operazioni paper."""

        _validate_signals(signals)

        _validate_outcomes(outcomes)

        selected_time = pd.Timestamp(synchronized_at_utc)

        if selected_time.tzinfo is None:
            raise PaperTradeRegistryError(
                "Il timestamp di sincronizzazione deve includere una timezone."
            )

        selected_time = selected_time.tz_convert("UTC")

        outcome_by_signal_id = {
            str(outcome_row["signal_id"]): outcome_row for _, outcome_row in outcomes.iterrows()
        }

        ordered_signals = signals.sort_values("timestamp")

        evaluated_signals = 0
        opened_trades = 0
        closed_trades = 0
        ignored_open_position = 0
        ignored_no_trade = 0
        duplicate_trades = 0

        for _, signal_row in ordered_signals.iterrows():
            direction = str(signal_row["signal"]).upper()

            if direction == "NO_TRADE":
                ignored_no_trade += 1
                continue

            if direction not in {
                "LONG",
                "SHORT",
            }:
                continue

            if signal_row["signal_status"] != "CONFIRMED":
                continue

            evaluated_signals += 1

            signal_id = str(signal_row["signal_id"])

            trade_exists = self._trade_exists(signal_id)

            if not trade_exists:
                if self._has_open_trade():
                    ignored_open_position += 1
                    continue

                inserted = self._open_trade(
                    signal_row,
                    selected_time,
                )

                if inserted:
                    opened_trades += 1
                else:
                    duplicate_trades += 1

            else:
                duplicate_trades += 1

            outcome_row = outcome_by_signal_id.get(signal_id)

            if outcome_row is not None:
                closed = self._close_trade(
                    outcome_row,
                    selected_time,
                )

                if closed:
                    closed_trades += 1

        return PaperTradeSyncReport(
            evaluated_signals=(evaluated_signals),
            opened_trades=(opened_trades),
            closed_trades=(closed_trades),
            ignored_open_position=(ignored_open_position),
            ignored_no_trade=(ignored_no_trade),
            duplicate_trades=(duplicate_trades),
        )

    def load_trades(
        self,
    ) -> pd.DataFrame:
        """Carica tutte le operazioni paper."""

        with self._connect() as connection:
            trades = pd.read_sql_query(
                """
                SELECT *
                FROM paper_trades
                ORDER BY opened_at_utc ASC
                """,
                connection,
            )

        return trades

    def load_open_trades(
        self,
    ) -> pd.DataFrame:
        """Carica le operazioni ancora aperte."""

        with self._connect() as connection:
            trades = pd.read_sql_query(
                """
                SELECT *
                FROM paper_trades
                WHERE status = 'OPEN'
                ORDER BY opened_at_utc ASC
                """,
                connection,
            )

        return trades
