"""Generazione del report di qualità per dataset OHLCV."""

# Importa dataclass per rappresentare il report in modo strutturato.
from dataclasses import asdict, dataclass

# Importa timedelta per rappresentare la frequenza attesa.
from datetime import timedelta

# Importa pandas per l'analisi delle serie temporali.
import pandas as pd

# Importa il validatore centrale del progetto.
from src.data.validator import validate_ohlcv


@dataclass(frozen=True)
class DataQualityReport:
    """Risultato strutturato dell'analisi di qualità OHLCV."""

    # Numero totale di candele presenti.
    total_rows: int

    # Timestamp della prima candela.
    start_timestamp: str

    # Timestamp dell'ultima candela.
    end_timestamp: str

    # Durata complessiva coperta dal dataset.
    covered_duration_seconds: float

    # Frequenza attesa espressa in secondi.
    expected_interval_seconds: float

    # Frequenza più comune rilevata nel dataset.
    detected_interval_seconds: float | None

    # Numero teorico di candele attese.
    expected_rows: int

    # Numero totale di candele mancanti.
    missing_rows: int

    # Percentuale di completezza temporale.
    completeness_percentage: float

    # Numero di intervalli temporali anomali.
    irregular_interval_count: int

    # Numero di candele con volume uguale a zero.
    zero_volume_rows: int

    # Percentuale di candele con volume uguale a zero.
    zero_volume_percentage: float

    # Volume minimo presente.
    minimum_volume: float

    # Volume massimo presente.
    maximum_volume: float

    # Volume medio presente.
    average_volume: float

    def to_dict(self) -> dict[str, int | float | str | None]:
        """Converte il report in un dizionario serializzabile."""

        # Usa asdict per convertire automaticamente tutti i campi.
        return asdict(self)


def _calculate_detected_interval(
    timestamps: pd.Series,
) -> float | None:
    """Calcola l'intervallo temporale più frequente in secondi."""

    # Calcola la differenza fra ogni timestamp e il precedente.
    timestamp_differences = timestamps.diff().dropna()

    # Se esiste una sola candela, non è possibile rilevare la frequenza.
    if timestamp_differences.empty:
        return None

    # Individua la differenza temporale più frequente.
    most_common_difference = timestamp_differences.mode().iloc[0]

    # Converte l'intervallo rilevato in secondi.
    return float(most_common_difference.total_seconds())


def generate_quality_report(
    dataframe: pd.DataFrame,
    expected_interval: timedelta,
) -> DataQualityReport:
    """Genera un report di qualità per un dataset OHLCV.

    Args:
        dataframe: Dataset OHLCV da analizzare.
        expected_interval: Intervallo temporale previsto fra le candele.

    Returns:
        Report strutturato con indicatori di qualità e completezza.

    Raises:
        ValueError: se l'intervallo atteso non è positivo.
        OHLCVValidationError: se il dataset non supera la validazione.
    """

    # Converte l'intervallo atteso in secondi.
    expected_interval_seconds = expected_interval.total_seconds()

    # Impedisce l'utilizzo di intervalli nulli o negativi.
    if expected_interval_seconds <= 0:
        raise ValueError("L'intervallo temporale atteso deve essere maggiore di zero.")

    # Valida e normalizza il dataset prima dell'analisi.
    validated_dataframe = validate_ohlcv(dataframe)

    # Estrae la serie temporale validata.
    timestamps = validated_dataframe["timestamp"]

    # Legge il primo timestamp.
    start_timestamp = timestamps.iloc[0]

    # Legge l'ultimo timestamp.
    end_timestamp = timestamps.iloc[-1]

    # Calcola la durata complessiva coperta dal dataset.
    covered_duration = end_timestamp - start_timestamp

    # Converte la durata coperta in secondi.
    covered_duration_seconds = float(covered_duration.total_seconds())

    # Calcola il numero teorico di candele previste.
    # Viene aggiunta una candela perché i due estremi sono inclusi.
    expected_rows = int(covered_duration_seconds // expected_interval_seconds) + 1

    # Calcola il numero di candele mancanti.
    missing_rows = max(
        expected_rows - len(validated_dataframe),
        0,
    )

    # Calcola la percentuale di completezza.
    completeness_percentage = round(
        (len(validated_dataframe) / expected_rows) * 100,
        2,
    )

    # Impedisce che la percentuale superi 100 per dataset irregolari.
    completeness_percentage = min(
        completeness_percentage,
        100.0,
    )

    # Calcola tutte le differenze temporali fra candele consecutive.
    timestamp_differences = timestamps.diff().dropna()

    # Conta gli intervalli differenti da quello previsto.
    irregular_interval_count = int(
        (timestamp_differences != pd.Timedelta(seconds=expected_interval_seconds)).sum()
    )

    # Rileva la frequenza temporale più comune.
    detected_interval_seconds = _calculate_detected_interval(timestamps)

    # Conta le righe con volume pari a zero.
    zero_volume_rows = int((validated_dataframe["volume"] == 0).sum())

    # Calcola la percentuale di righe con volume pari a zero.
    zero_volume_percentage = round(
        (zero_volume_rows / len(validated_dataframe)) * 100,
        2,
    )

    # Restituisce il report completo.
    return DataQualityReport(
        total_rows=len(validated_dataframe),
        start_timestamp=start_timestamp.isoformat(),
        end_timestamp=end_timestamp.isoformat(),
        covered_duration_seconds=covered_duration_seconds,
        expected_interval_seconds=float(expected_interval_seconds),
        detected_interval_seconds=detected_interval_seconds,
        expected_rows=expected_rows,
        missing_rows=missing_rows,
        completeness_percentage=completeness_percentage,
        irregular_interval_count=irregular_interval_count,
        zero_volume_rows=zero_volume_rows,
        zero_volume_percentage=zero_volume_percentage,
        minimum_volume=float(validated_dataframe["volume"].min()),
        maximum_volume=float(validated_dataframe["volume"].max()),
        average_volume=float(validated_dataframe["volume"].mean()),
    )
