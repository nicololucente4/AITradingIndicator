"""Creazione del target ML tramite metodo Triple Barrier."""

# Importa dataclass per rappresentare la configurazione del target.
from dataclasses import dataclass

# Importa pandas per elaborare le serie temporali.
import pandas as pd

# Importa il validatore OHLCV centrale.
from src.data.validator import validate_ohlcv


class TripleBarrierError(ValueError):
    """Errore generato da una configurazione Triple Barrier non valida."""


@dataclass(frozen=True)
class TripleBarrierConfig:
    """Configurazione del target Triple Barrier."""

    # Numero massimo di candele future da osservare.
    maximum_holding_bars: int = 12

    # Moltiplicatore ATR della barriera superiore.
    upper_atr_multiplier: float = 1.5

    # Moltiplicatore ATR della barriera inferiore.
    lower_atr_multiplier: float = 1.5

    # Etichetta applicata quando entrambe le barriere
    # vengono raggiunte nella stessa candela.
    ambiguous_label: str = "NO_TRADE"

    # Etichetta applicata quando nessuna barriera viene raggiunta.
    timeout_label: str = "NO_TRADE"


def _validate_config(config: TripleBarrierConfig) -> None:
    """Verifica che la configurazione Triple Barrier sia valida."""

    # Deve essere osservata almeno una candela futura.
    if config.maximum_holding_bars <= 0:
        raise TripleBarrierError(
            "Il numero massimo di candele future deve essere maggiore di zero."
        )

    # La barriera superiore deve essere positiva.
    if config.upper_atr_multiplier <= 0:
        raise TripleBarrierError("Il moltiplicatore ATR superiore deve essere maggiore di zero.")

    # La barriera inferiore deve essere positiva.
    if config.lower_atr_multiplier <= 0:
        raise TripleBarrierError("Il moltiplicatore ATR inferiore deve essere maggiore di zero.")

    # Definisce le etichette supportate.
    allowed_labels = {
        "LONG",
        "SHORT",
        "NO_TRADE",
    }

    # Verifica l'etichetta dei casi ambigui.
    if config.ambiguous_label not in allowed_labels:
        raise TripleBarrierError("L'etichetta ambigua non è supportata.")

    # Verifica l'etichetta applicata alla scadenza.
    if config.timeout_label not in allowed_labels:
        raise TripleBarrierError("L'etichetta di scadenza non è supportata.")


def _validate_input_columns(dataframe: pd.DataFrame) -> None:
    """Verifica la presenza delle colonne necessarie."""

    # Definisce le colonne richieste dal target builder.
    required_columns = {
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "atr",
    }

    # Individua le colonne mancanti.
    missing_columns = sorted(required_columns.difference(dataframe.columns))

    # Interrompe l'elaborazione se manca almeno una colonna.
    if missing_columns:
        missing_text = ", ".join(missing_columns)

        raise TripleBarrierError(f"Colonne necessarie al Triple Barrier mancanti: {missing_text}.")


def _find_barrier_result(
    future_candles: pd.DataFrame,
    upper_barrier: float,
    lower_barrier: float,
    config: TripleBarrierConfig,
) -> tuple[str, int | None]:
    """Determina quale barriera viene raggiunta per prima."""

    # Analizza le future candele in ordine cronologico.
    for future_offset, (_, candle) in enumerate(
        future_candles.iterrows(),
        start=1,
    ):
        # Verifica il raggiungimento della barriera superiore.
        upper_touched = candle["high"] >= upper_barrier

        # Verifica il raggiungimento della barriera inferiore.
        lower_touched = candle["low"] <= lower_barrier

        # Con dati OHLC non è possibile conoscere l'ordine intrabar.
        if upper_touched and lower_touched:
            return config.ambiguous_label, future_offset

        # La barriera superiore raggiunta per prima produce LONG.
        if upper_touched:
            return "LONG", future_offset

        # La barriera inferiore raggiunta per prima produce SHORT.
        if lower_touched:
            return "SHORT", future_offset

    # Nessuna barriera è stata raggiunta entro l'orizzonte.
    return config.timeout_label, None


def build_triple_barrier_labels(
    dataframe: pd.DataFrame,
    config: TripleBarrierConfig | None = None,
) -> pd.DataFrame:
    """Aggiunge il target LONG, SHORT o NO_TRADE al dataset.

    Il target utilizza intenzionalmente dati futuri e deve essere usato
    esclusivamente durante la preparazione del dataset di training.
    Non deve essere utilizzato come feature o durante l'inferenza live.

    Args:
        dataframe: Dataset OHLCV contenente anche la colonna ATR.
        config: Configurazione facoltativa del Triple Barrier.

    Returns:
        Copia del dataset con target, barriere e informazioni sull'esito.
    """

    # Verifica che l'input sia un DataFrame.
    if not isinstance(dataframe, pd.DataFrame):
        raise TypeError("Il dato ricevuto deve essere un pandas DataFrame.")

    # Impedisce l'elaborazione di dataset vuoti.
    if dataframe.empty:
        raise TripleBarrierError("Il dataset Triple Barrier è vuoto.")

    # Usa la configurazione predefinita se non specificata.
    selected_config = config or TripleBarrierConfig()

    # Valida configurazione e colonne.
    _validate_config(selected_config)
    _validate_input_columns(dataframe)

    # Valida solamente le colonne OHLCV tramite il validatore centrale.
    validated_ohlcv = validate_ohlcv(
        dataframe[
            [
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ]
        ]
    )

    # Crea una copia completa del dataset originale.
    result_dataframe = dataframe.copy(deep=True).reset_index(drop=True)

    # Sostituisce le colonne OHLCV con la versione validata.
    for column in validated_ohlcv.columns:
        result_dataframe[column] = validated_ohlcv[column]

    # Prepara le colonne del target.
    target_labels: list[str | None] = []
    upper_barriers: list[float | None] = []
    lower_barriers: list[float | None] = []
    bars_to_event: list[int | None] = []
    target_available: list[bool] = []

    # Analizza ogni candela come possibile punto iniziale.
    for row_index, row in result_dataframe.iterrows():
        # L'ATR deve essere disponibile e positivo.
        if pd.isna(row["atr"]) or float(row["atr"]) <= 0:
            target_labels.append(None)
            upper_barriers.append(None)
            lower_barriers.append(None)
            bars_to_event.append(None)
            target_available.append(False)
            continue

        # Calcola l'ultimo indice futuro osservabile.
        future_end_index = min(
            row_index + selected_config.maximum_holding_bars,
            len(result_dataframe) - 1,
        )

        # Verifica che l'orizzonte futuro sia interamente disponibile.
        available_future_bars = future_end_index - row_index

        if available_future_bars < selected_config.maximum_holding_bars:
            target_labels.append(None)
            upper_barriers.append(None)
            lower_barriers.append(None)
            bars_to_event.append(None)
            target_available.append(False)
            continue

        # Calcola le barriere usando Close e ATR della candela corrente.
        entry_reference = float(row["close"])
        atr_value = float(row["atr"])

        upper_barrier = entry_reference + atr_value * selected_config.upper_atr_multiplier

        lower_barrier = entry_reference - atr_value * selected_config.lower_atr_multiplier

        # Seleziona solamente le candele future.
        future_candles = result_dataframe.iloc[row_index + 1 : future_end_index + 1]

        # Determina il risultato del target.
        target_label, event_offset = _find_barrier_result(
            future_candles=future_candles,
            upper_barrier=upper_barrier,
            lower_barrier=lower_barrier,
            config=selected_config,
        )

        # Registra il risultato.
        target_labels.append(target_label)
        upper_barriers.append(upper_barrier)
        lower_barriers.append(lower_barrier)
        bars_to_event.append(event_offset)
        target_available.append(True)

    # Aggiunge le informazioni del target al dataset.
    result_dataframe["target"] = target_labels
    result_dataframe["target_upper_barrier"] = upper_barriers
    result_dataframe["target_lower_barrier"] = lower_barriers
    result_dataframe["target_bars_to_event"] = bars_to_event
    result_dataframe["target_available"] = target_available

    # Identifica esplicitamente l'uso futuro del target.
    result_dataframe["target_uses_future_data"] = True

    # Restituisce il dataset etichettato.
    return result_dataframe
