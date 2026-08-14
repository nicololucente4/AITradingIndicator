"""Riproduzione sequenziale di dati storici come flusso realtime."""

# Importa dataclass per configurazione e statistiche del replay.
# Importa Callable per definire la funzione che elabora ogni snapshot.
from collections.abc import Callable
from dataclasses import asdict, dataclass

# Importa pandas per gestire dati e risultati.
import pandas as pd

# Importa il validatore centrale OHLCV.
from src.data.validator import validate_ohlcv


class ReplayError(ValueError):
    """Errore generato da una configurazione Replay non valida."""


@dataclass(frozen=True)
class ReplayConfig:
    """Configurazione della modalità Replay."""

    # Numero minimo di candele prima di chiamare il processore.
    minimum_history_bars: int = 30

    # Numero massimo facoltativo di candele da riprodurre.
    maximum_replay_bars: int | None = None

    # Il replay deve utilizzare esclusivamente candele chiuse.
    confirmed_candles_only: bool = True


@dataclass(frozen=True)
class ReplayReport:
    """Statistiche riassuntive della sessione Replay."""

    # Numero totale di candele disponibili nel dataset.
    total_source_bars: int

    # Numero di candele effettivamente elaborate.
    processed_bars: int

    # Numero di snapshot generati.
    generated_snapshots: int

    # Numero di segnali LONG confermati.
    long_signals: int

    # Numero di segnali SHORT confermati.
    short_signals: int

    # Numero di segnali NO_TRADE.
    no_trade_signals: int

    # Timestamp dell'ultima candela elaborata.
    last_processed_timestamp: str | None

    def to_dict(self) -> dict[str, int | str | None]:
        """Converte il report in un dizionario serializzabile."""

        # Converte automaticamente tutti i campi.
        return asdict(self)


def _validate_config(config: ReplayConfig) -> None:
    """Verifica che la configurazione Replay sia coerente."""

    # Deve essere disponibile almeno una candela storica.
    if config.minimum_history_bars <= 0:
        raise ReplayError("Il numero minimo di candele storiche deve essere maggiore di zero.")

    # Il limite massimo, se presente, deve essere positivo.
    if config.maximum_replay_bars is not None and config.maximum_replay_bars <= 0:
        raise ReplayError("Il numero massimo di candele Replay deve essere maggiore di zero.")

    # Questa prima versione supporta solamente candele confermate.
    if not config.confirmed_candles_only:
        raise ReplayError("La modalità Replay richiede confirmed_candles_only=true.")


def _validate_processor_output(
    output: pd.DataFrame,
) -> None:
    """Verifica il risultato restituito dal processore."""

    # Il processore deve restituire un DataFrame.
    if not isinstance(output, pd.DataFrame):
        raise ReplayError("Il processore Replay deve restituire un pandas DataFrame.")

    # Il risultato non può essere vuoto.
    if output.empty:
        raise ReplayError("Il processore Replay ha restituito un DataFrame vuoto.")

    # Definisce le colonne minime richieste.
    required_columns = {
        "timestamp",
        "signal",
        "signal_status",
        "signal_available_at",
    }

    # Individua eventuali colonne mancanti.
    missing_columns = sorted(required_columns.difference(output.columns))

    # Interrompe il Replay se l'output non è compatibile.
    if missing_columns:
        missing_text = ", ".join(missing_columns)

        raise ReplayError(f"Colonne mancanti nell'output Replay: {missing_text}.")


def run_replay(
    dataframe: pd.DataFrame,
    processor: Callable[[pd.DataFrame], pd.DataFrame],
    config: ReplayConfig | None = None,
) -> tuple[pd.DataFrame, ReplayReport]:
    """Riproduce un dataset storico una candela alla volta.

    A ogni iterazione il processore riceve solamente le candele
    disponibili fino a quel momento. Non riceve mai righe future.

    Args:
        dataframe: Dataset OHLCV storico.
        processor: Funzione che genera feature e segnali.
        config: Configurazione facoltativa del Replay.

    Returns:
        Una coppia composta dal registro Replay e dal report riassuntivo.
    """

    # Verifica che processor sia una funzione richiamabile.
    if not callable(processor):
        raise TypeError("Il processore Replay deve essere richiamabile.")

    # Usa la configurazione predefinita se non specificata.
    selected_config = config or ReplayConfig()

    # Valida la configurazione.
    _validate_config(selected_config)

    # Valida e normalizza il dataset sorgente.
    validated_dataframe = validate_ohlcv(dataframe)

    # Verifica che siano disponibili abbastanza candele.
    if len(validated_dataframe) < selected_config.minimum_history_bars:
        raise ReplayError("Il dataset contiene meno candele rispetto al minimo storico richiesto.")

    # Determina il limite effettivo del Replay.
    replay_end = len(validated_dataframe)

    if selected_config.maximum_replay_bars is not None:
        replay_end = min(
            replay_end,
            selected_config.maximum_replay_bars,
        )

    # Contiene uno snapshot per ogni candela elaborata.
    replay_rows: list[dict[str, object]] = []

    # Inizia quando è disponibile il numero minimo di candele.
    for history_size in range(
        selected_config.minimum_history_bars,
        replay_end + 1,
    ):
        # Crea uno snapshot contenente solamente passato e presente.
        historical_snapshot = validated_dataframe.iloc[:history_size].copy()

        # Elabora lo snapshot senza fornire righe future.
        processed_snapshot = processor(historical_snapshot)

        # Verifica la struttura dell'output.
        _validate_processor_output(processed_snapshot)

        # Recupera esclusivamente l'ultima riga disponibile.
        current_row = processed_snapshot.iloc[-1]

        # Verifica che l'output si riferisca alla candela corrente.
        expected_timestamp = historical_snapshot.iloc[-1]["timestamp"]

        if current_row["timestamp"] != expected_timestamp:
            raise ReplayError(
                "Il processore Replay non ha restituito la candela corrente come ultima riga."
            )

        # Salva solamente informazioni disponibili in quel momento.
        replay_rows.append(
            {
                "replay_step": len(replay_rows) + 1,
                "available_bars": history_size,
                "timestamp": current_row["timestamp"],
                "signal_available_at": current_row["signal_available_at"],
                "signal": current_row["signal"],
                "signal_status": current_row["signal_status"],
                "close": current_row.get(
                    "close",
                    float("nan"),
                ),
                "entry_price": current_row.get(
                    "entry_price",
                    float("nan"),
                ),
                "stop_loss": current_row.get(
                    "stop_loss",
                    float("nan"),
                ),
                "take_profit_1": current_row.get(
                    "take_profit_1",
                    float("nan"),
                ),
                "take_profit_2": current_row.get(
                    "take_profit_2",
                    float("nan"),
                ),
                "take_profit_3": current_row.get(
                    "take_profit_3",
                    float("nan"),
                ),
            }
        )

    # Converte gli snapshot in un DataFrame.
    replay_log = pd.DataFrame(replay_rows)

    # Conta le diverse tipologie di segnale.
    signal_counts = replay_log["signal"].value_counts()

    # Recupera il timestamp finale.
    last_processed_timestamp = (
        replay_log.iloc[-1]["timestamp"].isoformat() if not replay_log.empty else None
    )

    # Costruisce il report della sessione.
    report = ReplayReport(
        total_source_bars=len(validated_dataframe),
        processed_bars=replay_end,
        generated_snapshots=len(replay_log),
        long_signals=int(signal_counts.get("LONG", 0)),
        short_signals=int(signal_counts.get("SHORT", 0)),
        no_trade_signals=int(signal_counts.get("NO_TRADE", 0)),
        last_processed_timestamp=last_processed_timestamp,
    )

    # Restituisce registro e report.
    return replay_log, report
