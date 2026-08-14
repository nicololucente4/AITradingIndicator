"""Monitoraggio immutabile degli esiti dei segnali Live Paper."""

# Importa SQLite per salvare localmente gli esiti dei segnali.
import sqlite3

# Importa dataclass per rappresentare configurazione e report.
from dataclasses import dataclass

# Importa Path per gestire il percorso del database.
from pathlib import Path

# Importa pandas per elaborare segnali, timestamp e dati OHLCV.
import pandas as pd

# Importa il validatore centrale dei dati OHLCV.
from src.data.validator import validate_ohlcv


class OutcomeTrackerError(ValueError):
    """Errore generato durante il monitoraggio degli esiti."""


@dataclass(frozen=True)
class OutcomeTrackerConfig:
    """Configurazione del monitoraggio degli esiti."""

    # Numero massimo di candele durante cui monitorare il segnale.
    maximum_holding_bars: int = 12

    # In caso di TP e SL nella stessa candela prevale lo Stop Loss.
    stop_first_when_ambiguous: bool = True

    # Il sistema rimane esclusivamente in modalità simulata.
    paper_trading_only: bool = True


@dataclass(frozen=True)
class OutcomeUpdateReport:
    """Risultato di un ciclo di valutazione degli esiti."""

    # Numero totale di segnali direzionali analizzati.
    evaluated_signals: int

    # Numero di nuovi esiti conclusivi trovati.
    resolved_signals: int

    # Numero di segnali ancora in attesa.
    pending_signals: int

    # Numero di esiti inseriti nel database.
    inserted_outcomes: int

    # Numero di esiti già presenti e quindi ignorati.
    duplicate_outcomes: int

    # Numero di segnali NO_TRADE ignorati.
    ignored_no_trade_signals: int


def _validate_config(
    config: OutcomeTrackerConfig,
) -> None:
    """Verifica la configurazione dell'Outcome Tracker."""

    # La durata massima deve includere almeno una candela.
    if config.maximum_holding_bars <= 0:
        raise OutcomeTrackerError("La durata massima deve essere maggiore di zero.")

    # Questa versione utilizza una gestione intrabar conservativa.
    if not config.stop_first_when_ambiguous:
        raise OutcomeTrackerError(
            "La prima versione richiede una gestione conservativa delle candele ambigue."
        )

    # Non è consentito utilizzare il modulo fuori dal paper trading.
    if not config.paper_trading_only:
        raise OutcomeTrackerError("L'Outcome Tracker richiede paper_trading_only=true.")


def _validate_signals(
    signals: pd.DataFrame,
) -> None:
    """Verifica il registro dei segnali ricevuto."""

    # L'input deve essere un DataFrame.
    if not isinstance(signals, pd.DataFrame):
        raise TypeError("Il registro dei segnali deve essere un pandas DataFrame.")

    # Definisce le colonne necessarie per valutare un segnale.
    required_columns = {
        "signal_id",
        "timestamp",
        "signal_available_at",
        "signal",
        "signal_status",
        "entry_price",
        "stop_loss",
        "take_profit_1",
    }

    # Individua eventuali colonne mancanti.
    missing_columns = sorted(required_columns.difference(signals.columns))

    # Interrompe la valutazione se manca almeno una colonna.
    if missing_columns:
        missing_text = ", ".join(missing_columns)

        raise OutcomeTrackerError(f"Colonne mancanti nel registro segnali: {missing_text}.")

    # Ogni segnale deve avere un identificativo univoco.
    if signals["signal_id"].duplicated().any():
        raise OutcomeTrackerError("Il registro contiene signal_id duplicati.")


def _calculate_return(
    entry_price: float,
    exit_price: float,
    direction: str,
) -> float:
    """Calcola il rendimento percentuale simulato."""

    # Calcola il rendimento di un segnale LONG.
    if direction == "LONG":
        return (exit_price / entry_price) - 1.0

    # Calcola il rendimento di un segnale SHORT.
    return (entry_price / exit_price) - 1.0


def _detect_bar_outcome(
    candle: pd.Series,
    direction: str,
    stop_loss: float,
    take_profit: float,
) -> tuple[str | None, float | None]:
    """Controlla se una candela raggiunge Stop Loss oppure TP1."""

    # Verifica i livelli per un segnale LONG.
    if direction == "LONG":
        stop_touched = float(candle["low"]) <= stop_loss
        target_touched = float(candle["high"]) >= take_profit

    # Verifica i livelli in modo speculare per un segnale SHORT.
    else:
        stop_touched = float(candle["high"]) >= stop_loss
        target_touched = float(candle["low"]) <= take_profit

    # Con i soli dati OHLC non conosciamo l'ordine intrabar.
    # La gestione conservativa considera raggiunto prima lo Stop Loss.
    if stop_touched and target_touched:
        return "STOP_LOSS_AMBIGUOUS", stop_loss

    # Restituisce lo Stop Loss se è stato raggiunto.
    if stop_touched:
        return "STOP_LOSS", stop_loss

    # Restituisce TP1 se è stato raggiunto.
    if target_touched:
        return "TAKE_PROFIT_1", take_profit

    # Nessun livello è stato raggiunto.
    return None, None


class OutcomeTracker:
    """Valuta i segnali e salva separatamente gli esiti conclusivi."""

    def __init__(
        self,
        database_path: str | Path,
        config: OutcomeTrackerConfig | None = None,
    ) -> None:
        """Inizializza l'Outcome Tracker."""

        # Usa la configurazione predefinita se non specificata.
        self._config = config or OutcomeTrackerConfig()

        # Verifica la configurazione.
        _validate_config(self._config)

        # Converte il percorso in un oggetto Path.
        self._database_path = Path(database_path)

        # Verifica che il percorso non sia vuoto.
        if not str(self._database_path).strip():
            raise OutcomeTrackerError("Il percorso del database non può essere vuoto.")

        # Crea il database e la relativa tabella.
        self._initialize_database()

    @property
    def database_path(self) -> Path:
        """Restituisce il percorso del database."""

        return self._database_path

    def _connect(self) -> sqlite3.Connection:
        """Crea una connessione SQLite."""

        # Restituisce una nuova connessione al database locale.
        return sqlite3.connect(self._database_path)

    def _initialize_database(self) -> None:
        """Crea la tabella separata degli esiti."""

        # Crea la cartella del database se non esiste.
        self._database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # Apre una connessione al database.
        with self._connect() as connection:
            # Crea la tabella senza modificare l'eventuale tabella signals.
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS signal_outcomes (
                    signal_id TEXT PRIMARY KEY,
                    direction TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL NOT NULL,
                    exit_reason TEXT NOT NULL,
                    exit_timestamp TEXT NOT NULL,
                    holding_bars INTEGER NOT NULL,
                    gross_return_percentage REAL NOT NULL,
                    result_r REAL,
                    evaluated_at_utc TEXT NOT NULL,
                    outcome_mode TEXT NOT NULL
                )
                """
            )

            # Conferma la creazione della struttura.
            connection.commit()

    def _existing_signal_ids(self) -> set:
        """Recupera gli identificativi dei segnali già valutati."""

        # Apre una connessione al database degli esiti.
        with self._connect() as connection:
            # Recupera gli identificativi già registrati.
            cursor = connection.execute(
                """
                SELECT signal_id
                FROM signal_outcomes
                """
            )

            # Converte i risultati in un insieme.
            existing_ids = {str(row[0]) for row in cursor.fetchall()}

        # Restituisce gli identificativi recuperati.
        return existing_ids

    def _resolve_signal(
        self,
        signal_row: pd.Series,
        market_data: pd.DataFrame,
    ) -> dict[str, object] | None:
        """Determina l'esito conclusivo di un singolo segnale."""

        # Recupera la direzione del segnale.
        direction = str(signal_row["signal"])

        # NO_TRADE non produce un esito operativo.
        if direction not in {
            "LONG",
            "SHORT",
        }:
            return None

        # Sono accettati solamente segnali confermati.
        if signal_row["signal_status"] != "CONFIRMED":
            raise OutcomeTrackerError("L'Outcome Tracker accetta solamente segnali confermati.")

        # Recupera i livelli necessari.
        required_numeric_values = [
            signal_row["entry_price"],
            signal_row["stop_loss"],
            signal_row["take_profit_1"],
        ]

        # Un segnale direzionale deve avere tutti i livelli valorizzati.
        if any(pd.isna(value) for value in required_numeric_values):
            raise OutcomeTrackerError("Il segnale direzionale non contiene livelli completi.")

        # Converte i livelli in valori numerici.
        entry_price = float(signal_row["entry_price"])
        stop_loss = float(signal_row["stop_loss"])
        take_profit = float(signal_row["take_profit_1"])

        # Il prezzo di ingresso deve essere valido.
        if entry_price <= 0:
            raise OutcomeTrackerError("Il prezzo di ingresso deve essere positivo.")

        # Recupera il momento in cui il segnale è diventato disponibile.
        signal_available_at = pd.Timestamp(signal_row["signal_available_at"])

        # Seleziona solamente le candele disponibili dopo il segnale.
        future_bars = market_data.loc[market_data["timestamp"] >= signal_available_at].head(
            self._config.maximum_holding_bars
        )

        # Se non esistono candele future, il segnale resta pendente.
        if future_bars.empty:
            return None

        # Inizializza i dati dell'eventuale uscita.
        selected_exit_reason: str | None = None
        selected_exit_price: float | None = None
        selected_exit_timestamp: pd.Timestamp | None = None
        selected_holding_bars = 0

        # Analizza le candele future in ordine cronologico.
        for holding_bar, (_, candle) in enumerate(
            future_bars.iterrows(),
            start=1,
        ):
            # Verifica il raggiungimento di Stop Loss oppure TP1.
            exit_reason, exit_price = _detect_bar_outcome(
                candle=candle,
                direction=direction,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )

            # Chiude la valutazione al primo evento disponibile.
            if exit_reason is not None:
                selected_exit_reason = exit_reason
                selected_exit_price = float(exit_price)
                selected_exit_timestamp = pd.Timestamp(candle["timestamp"])
                selected_holding_bars = holding_bar
                break

        # Se nessun livello è stato raggiunto, valuta la scadenza.
        if selected_exit_reason is None:
            # Il trade resta pendente se l'orizzonte non è ancora completo.
            if len(future_bars) < self._config.maximum_holding_bars:
                return None

            # Usa il Close dell'ultima candela disponibile alla scadenza.
            final_candle = future_bars.iloc[-1]

            selected_exit_reason = "TIME_EXPIRY"
            selected_exit_price = float(final_candle["close"])
            selected_exit_timestamp = pd.Timestamp(final_candle["timestamp"])
            selected_holding_bars = len(future_bars)

        # Controllo difensivo sui valori determinati.
        if (
            selected_exit_price is None
            or selected_exit_timestamp is None
            or selected_exit_reason is None
        ):
            raise OutcomeTrackerError("Impossibile determinare i dati di uscita.")

        # Calcola il rendimento percentuale lordo.
        gross_return = _calculate_return(
            entry_price=entry_price,
            exit_price=selected_exit_price,
            direction=direction,
        )

        # Calcola la distanza iniziale di rischio.
        risk_distance = abs(entry_price - stop_loss)

        # Converte il risultato in multipli di rischio R.
        result_r = gross_return / (risk_distance / entry_price) if risk_distance > 0 else None

        # Restituisce l'esito completo.
        return {
            "signal_id": str(signal_row["signal_id"]),
            "direction": direction,
            "entry_price": entry_price,
            "exit_price": selected_exit_price,
            "exit_reason": selected_exit_reason,
            "exit_timestamp": (selected_exit_timestamp.isoformat()),
            "holding_bars": selected_holding_bars,
            "gross_return_percentage": gross_return,
            "result_r": result_r,
        }

    def _insert_outcome(
        self,
        outcome: dict[str, object],
        evaluated_at_utc: pd.Timestamp,
    ) -> bool:
        """Inserisce l'esito senza sovrascrivere record esistenti."""

        # Prepara tutti i valori da salvare.
        values = (
            outcome["signal_id"],
            outcome["direction"],
            outcome["entry_price"],
            outcome["exit_price"],
            outcome["exit_reason"],
            outcome["exit_timestamp"],
            outcome["holding_bars"],
            outcome["gross_return_percentage"],
            outcome["result_r"],
            evaluated_at_utc.isoformat(),
            "PAPER_ONLY",
        )

        # Apre una connessione al database.
        with self._connect() as connection:
            # INSERT OR IGNORE impedisce la modifica di un esito esistente.
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO signal_outcomes (
                    signal_id,
                    direction,
                    entry_price,
                    exit_price,
                    exit_reason,
                    exit_timestamp,
                    holding_bars,
                    gross_return_percentage,
                    result_r,
                    evaluated_at_utc,
                    outcome_mode
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )

            # Conferma l'operazione.
            connection.commit()

            # rowcount uguale a uno indica un nuovo inserimento.
            return cursor.rowcount == 1

    def evaluate(
        self,
        signals: pd.DataFrame,
        market_data: pd.DataFrame,
        evaluated_at_utc: pd.Timestamp,
    ) -> OutcomeUpdateReport:
        """Valuta tutti i segnali non ancora conclusi."""

        # Valida il registro dei segnali.
        _validate_signals(signals)

        # Normalizza il timestamp della valutazione.
        selected_time = pd.Timestamp(evaluated_at_utc)

        # Il timestamp deve contenere una timezone.
        if selected_time.tzinfo is None:
            raise OutcomeTrackerError("Il timestamp di valutazione deve includere una timezone.")

        # Converte il timestamp in UTC.
        selected_time = selected_time.tz_convert("UTC")

        # Valida il dataset OHLCV usato per monitorare i segnali.
        validated_market_data = validate_ohlcv(market_data)

        # Recupera gli esiti già presenti nel database.
        existing_signal_ids = self._existing_signal_ids()

        # Inizializza i contatori del report.
        evaluated_signals = 0
        resolved_signals = 0
        pending_signals = 0
        inserted_outcomes = 0
        duplicate_outcomes = 0
        ignored_no_trade_signals = 0

        # Analizza ogni segnale.
        for _, signal_row in signals.iterrows():
            # Recupera l'identificativo del segnale.
            signal_id = str(signal_row["signal_id"])

            # NO_TRADE viene ignorato perché non genera un'operazione.
            if signal_row["signal"] == "NO_TRADE":
                ignored_no_trade_signals += 1
                continue

            # Conta il segnale direzionale analizzato.
            evaluated_signals += 1

            # Un segnale già concluso non viene rivalutato.
            if signal_id in existing_signal_ids:
                duplicate_outcomes += 1
                continue

            # Cerca un esito nel dataset di mercato.
            outcome = self._resolve_signal(
                signal_row=signal_row,
                market_data=validated_market_data,
            )

            # Se non esiste ancora un esito, il segnale resta pendente.
            if outcome is None:
                pending_signals += 1
                continue

            # Conta il nuovo esito trovato.
            resolved_signals += 1

            # Inserisce l'esito senza sovrascritture.
            inserted = self._insert_outcome(
                outcome=outcome,
                evaluated_at_utc=selected_time,
            )

            # Aggiorna i contatori.
            if inserted:
                inserted_outcomes += 1
                existing_signal_ids.add(signal_id)
            else:
                duplicate_outcomes += 1

        # Restituisce il report del ciclo.
        return OutcomeUpdateReport(
            evaluated_signals=evaluated_signals,
            resolved_signals=resolved_signals,
            pending_signals=pending_signals,
            inserted_outcomes=inserted_outcomes,
            duplicate_outcomes=duplicate_outcomes,
            ignored_no_trade_signals=ignored_no_trade_signals,
        )

    def load_outcomes(self) -> pd.DataFrame:
        """Carica tutti gli esiti registrati."""

        # Legge gli esiti in ordine cronologico.
        with self._connect() as connection:
            outcomes = pd.read_sql_query(
                """
                SELECT *
                FROM signal_outcomes
                ORDER BY exit_timestamp ASC
                """,
                connection,
            )

        # Restituisce il registro completo.
        return outcomes
