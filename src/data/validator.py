"""Validazione strutturale e logica dei dataset OHLCV."""

# Importa pandas per gestire dati tabellari e serie temporali.
import pandas as pd

# Importa le definizioni condivise dello schema OHLCV.
from src.data.schema import (
    NUMERIC_OHLCV_COLUMNS,
    PRICE_COLUMNS,
    REQUIRED_OHLCV_COLUMNS,
)


class OHLCVValidationError(ValueError):
    """Errore generato quando un dataset OHLCV non supera la validazione."""


def _validate_required_columns(dataframe: pd.DataFrame) -> None:
    """Verifica che tutte le colonne obbligatorie siano presenti."""

    # Identifica le colonne obbligatorie mancanti.
    missing_columns = [
        column for column in REQUIRED_OHLCV_COLUMNS if column not in dataframe.columns
    ]

    # Interrompe la validazione se manca almeno una colonna.
    if missing_columns:
        missing_text = ", ".join(missing_columns)

        raise OHLCVValidationError(f"Colonne OHLCV obbligatorie mancanti: {missing_text}.")


def _normalize_timestamp(dataframe: pd.DataFrame) -> None:
    """Converte la colonna timestamp in datetime con timezone UTC."""

    # Converte i timestamp in UTC.
    # I valori non interpretabili vengono trasformati in NaT.
    dataframe["timestamp"] = pd.to_datetime(
        dataframe["timestamp"],
        errors="coerce",
        utc=True,
    )

    # Conta i timestamp non validi prodotti dalla conversione.
    invalid_timestamp_count = int(dataframe["timestamp"].isna().sum())

    # Interrompe la validazione se esistono timestamp non interpretabili.
    if invalid_timestamp_count > 0:
        raise OHLCVValidationError(
            f"Sono presenti {invalid_timestamp_count} timestamp non validi o mancanti."
        )


def _normalize_numeric_columns(dataframe: pd.DataFrame) -> None:
    """Converte prezzi e volume in valori numerici."""

    # Converte ogni colonna numerica separatamente.
    for column in NUMERIC_OHLCV_COLUMNS:
        dataframe[column] = pd.to_numeric(
            dataframe[column],
            errors="coerce",
        )

    # Conta i valori numerici mancanti o non convertibili per colonna.
    invalid_values = {
        column: int(dataframe[column].isna().sum())
        for column in NUMERIC_OHLCV_COLUMNS
        if dataframe[column].isna().any()
    }

    # Interrompe la validazione se almeno una colonna contiene valori non validi.
    if invalid_values:
        details = ", ".join(f"{column}: {count}" for column, count in invalid_values.items())

        raise OHLCVValidationError(f"Valori numerici mancanti o non validi: {details}.")


def _validate_timestamp_order(dataframe: pd.DataFrame) -> None:
    """Verifica ordine cronologico e assenza di timestamp duplicati."""

    # Individua eventuali timestamp duplicati.
    duplicate_count = int(dataframe["timestamp"].duplicated().sum())

    # Interrompe la validazione se sono presenti duplicati.
    if duplicate_count > 0:
        raise OHLCVValidationError(f"Sono presenti {duplicate_count} timestamp duplicati.")

    # Verifica che i timestamp siano ordinati dal più vecchio al più recente.
    if not dataframe["timestamp"].is_monotonic_increasing:
        raise OHLCVValidationError("I timestamp non sono ordinati cronologicamente.")


def _validate_price_values(dataframe: pd.DataFrame) -> None:
    """Verifica che tutti i prezzi siano strettamente positivi."""

    # Individua righe con almeno un prezzo minore o uguale a zero.
    invalid_price_rows = dataframe[list(PRICE_COLUMNS)].le(0).any(axis=1)

    # Conta quante righe presentano prezzi non validi.
    invalid_price_count = int(invalid_price_rows.sum())

    # Interrompe la validazione se sono presenti prezzi non positivi.
    if invalid_price_count > 0:
        raise OHLCVValidationError(
            f"Sono presenti {invalid_price_count} righe con prezzi minori o uguali a zero."
        )


def _validate_volume(dataframe: pd.DataFrame) -> None:
    """Verifica che il volume non contenga valori negativi."""

    # Conta le righe con volume negativo.
    negative_volume_count = int((dataframe["volume"] < 0).sum())

    # Interrompe la validazione se esistono volumi negativi.
    if negative_volume_count > 0:
        raise OHLCVValidationError(f"Sono presenti {negative_volume_count} volumi negativi.")


def _validate_ohlc_relationships(dataframe: pd.DataFrame) -> None:
    """Verifica la coerenza matematica tra Open, High, Low e Close."""

    # L'High deve essere maggiore o uguale a Open, Low e Close.
    invalid_high = (
        (dataframe["high"] < dataframe["open"])
        | (dataframe["high"] < dataframe["low"])
        | (dataframe["high"] < dataframe["close"])
    )

    # Il Low deve essere minore o uguale a Open, High e Close.
    invalid_low = (
        (dataframe["low"] > dataframe["open"])
        | (dataframe["low"] > dataframe["high"])
        | (dataframe["low"] > dataframe["close"])
    )

    # Combina tutte le anomalie OHLC.
    invalid_ohlc_rows = invalid_high | invalid_low

    # Conta le righe incoerenti.
    invalid_ohlc_count = int(invalid_ohlc_rows.sum())

    # Interrompe la validazione se esistono relazioni OHLC impossibili.
    if invalid_ohlc_count > 0:
        raise OHLCVValidationError(
            f"Sono presenti {invalid_ohlc_count} righe con relazioni OHLC incoerenti."
        )


def validate_ohlcv(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Valida e normalizza un DataFrame OHLCV.

    Args:
        dataframe: DataFrame contenente almeno timestamp, OHLC e volume.

    Returns:
        Una copia validata con timestamp UTC e colonne numeriche normalizzate.

    Raises:
        OHLCVValidationError: se il dataset non supera uno dei controlli.
    """

    # Verifica che l'oggetto ricevuto sia effettivamente un DataFrame.
    if not isinstance(dataframe, pd.DataFrame):
        raise TypeError("Il dato ricevuto deve essere un pandas DataFrame.")

    # Impedisce l'elaborazione di dataset vuoti.
    if dataframe.empty:
        raise OHLCVValidationError("Il dataset OHLCV è vuoto.")

    # Verifica la presenza delle colonne obbligatorie.
    _validate_required_columns(dataframe)

    # Crea una copia per non modificare il DataFrame originale.
    validated_dataframe = dataframe.copy()

    # Mantiene le colonne OHLCV nell'ordine standard.
    # Eventuali colonne aggiuntive non vengono conservate in questa fase.
    validated_dataframe = validated_dataframe[list(REQUIRED_OHLCV_COLUMNS)]

    # Normalizza e valida i timestamp.
    _normalize_timestamp(validated_dataframe)

    # Normalizza prezzi e volume.
    _normalize_numeric_columns(validated_dataframe)

    # Verifica ordine e unicità dei timestamp.
    _validate_timestamp_order(validated_dataframe)

    # Verifica che i prezzi siano positivi.
    _validate_price_values(validated_dataframe)

    # Verifica che il volume non sia negativo.
    _validate_volume(validated_dataframe)

    # Verifica la coerenza matematica delle candele.
    _validate_ohlc_relationships(validated_dataframe)

    # Restituisce il dataset validato con indice progressivo pulito.
    return validated_dataframe.reset_index(drop=True)
