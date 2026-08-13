"""Aggregazione sicura dei dati OHLCV su timeframe superiori."""

# Importa pandas per aggregare e analizzare le serie temporali.
import pandas as pd

# Importa il validatore centrale OHLCV.
from src.data.validator import validate_ohlcv


class TimeframeAggregationError(ValueError):
    """Errore generato da una configurazione timeframe non valida."""


def _validate_timeframe_parameters(
    source_minutes: int,
    target_minutes: int,
) -> int:
    """Valida i timeframe e restituisce il rapporto di aggregazione."""

    # Verifica che il timeframe sorgente sia positivo.
    if source_minutes <= 0:
        raise TimeframeAggregationError("Il timeframe sorgente deve essere maggiore di zero.")

    # Verifica che il timeframe destinazione sia positivo.
    if target_minutes <= 0:
        raise TimeframeAggregationError("Il timeframe destinazione deve essere maggiore di zero.")

    # Il timeframe superiore deve essere più grande di quello sorgente.
    if target_minutes <= source_minutes:
        raise TimeframeAggregationError(
            "Il timeframe destinazione deve essere maggiore del timeframe sorgente."
        )

    # Il timeframe superiore deve essere un multiplo esatto del sorgente.
    if target_minutes % source_minutes != 0:
        raise TimeframeAggregationError(
            "Il timeframe destinazione deve essere un multiplo esatto del timeframe sorgente."
        )

    # Calcola il numero di candele sorgente necessarie.
    return target_minutes // source_minutes


def _is_complete_bucket(
    group: pd.DataFrame,
    bucket_start: pd.Timestamp,
    source_minutes: int,
    required_candles: int,
) -> bool:
    """Verifica che un blocco contenga tutte le candele previste."""

    # Un blocco completo deve avere il numero esatto di candele sorgente.
    if len(group) != required_candles:
        return False

    # Genera i timestamp che dovrebbero essere presenti nel blocco.
    expected_timestamps = pd.date_range(
        start=bucket_start,
        periods=required_candles,
        freq=f"{source_minutes}min",
        tz="UTC",
    )

    # Estrae i timestamp realmente presenti.
    actual_timestamps = pd.DatetimeIndex(group["timestamp"])

    # Il blocco è completo solamente se i timestamp coincidono esattamente.
    return actual_timestamps.equals(expected_timestamps)


def resample_ohlcv(
    dataframe: pd.DataFrame,
    source_minutes: int,
    target_minutes: int,
) -> pd.DataFrame:
    """Aggrega candele OHLCV su un timeframe superiore.

    Il timestamp di ogni candela rappresenta il momento di apertura.
    Vengono restituite solamente candele superiori complete.

    Args:
        dataframe: Dataset OHLCV del timeframe sorgente.
        source_minutes: Durata in minuti della candela sorgente.
        target_minutes: Durata in minuti della candela destinazione.

    Returns:
        DataFrame OHLCV aggregato e validato.

    Raises:
        TimeframeAggregationError: se i timeframe non sono compatibili
            oppure non esiste alcun blocco completo.
    """

    # Valida i timeframe e calcola il numero di candele richieste.
    required_candles = _validate_timeframe_parameters(
        source_minutes=source_minutes,
        target_minutes=target_minutes,
    )

    # Valida il dataset e crea una copia normalizzata.
    validated_dataframe = validate_ohlcv(dataframe)

    # Crea una colonna temporanea con l'apertura del blocco superiore.
    working_dataframe = validated_dataframe.copy()
    working_dataframe["_bucket_start"] = working_dataframe["timestamp"].dt.floor(
        f"{target_minutes}min"
    )

    # Contiene le candele superiori complete generate.
    aggregated_rows: list[dict[str, object]] = []

    # Analizza separatamente ogni blocco temporale superiore.
    for bucket_start, group in working_dataframe.groupby(
        "_bucket_start",
        sort=True,
    ):
        # Ordina le candele sorgente in ordine cronologico.
        ordered_group = group.sort_values("timestamp")

        # Ignora il blocco se manca anche una sola candela sorgente.
        if not _is_complete_bucket(
            group=ordered_group,
            bucket_start=bucket_start,
            source_minutes=source_minutes,
            required_candles=required_candles,
        ):
            continue

        # Aggrega il blocco secondo le regole standard OHLCV.
        aggregated_rows.append(
            {
                "timestamp": bucket_start,
                "open": ordered_group["open"].iloc[0],
                "high": ordered_group["high"].max(),
                "low": ordered_group["low"].min(),
                "close": ordered_group["close"].iloc[-1],
                "volume": ordered_group["volume"].sum(),
            }
        )

    # Interrompe l'elaborazione se nessun blocco è completo.
    if not aggregated_rows:
        raise TimeframeAggregationError(
            "Il dataset non contiene blocchi temporali completi per il timeframe richiesto."
        )

    # Crea il DataFrame aggregato.
    aggregated_dataframe = pd.DataFrame(aggregated_rows)

    # Valida nuovamente il risultato prima di restituirlo.
    return validate_ohlcv(aggregated_dataframe)
