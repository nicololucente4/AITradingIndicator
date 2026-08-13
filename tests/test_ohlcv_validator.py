"""Test automatici del validatore OHLCV."""

# Importa pandas per costruire dataset di test.
import pandas as pd

# Importa pytest per verificare gli errori attesi.
import pytest

# Importa il validatore e l'errore specifico del progetto.
from src.data.validator import OHLCVValidationError, validate_ohlcv


def create_valid_dataframe() -> pd.DataFrame:
    """Crea un piccolo dataset OHLCV valido e deterministico."""

    # Restituisce tre candele consecutive da 15 minuti.
    return pd.DataFrame(
        {
            "timestamp": [
                "2026-08-13 10:00:00",
                "2026-08-13 10:15:00",
                "2026-08-13 10:30:00",
            ],
            "open": [1.1000, 1.1010, 1.1020],
            "high": [1.1020, 1.1030, 1.1040],
            "low": [1.0990, 1.1000, 1.1010],
            "close": [1.1010, 1.1020, 1.1030],
            "volume": [100, 120, 110],
        }
    )


def test_valid_dataframe_is_accepted() -> None:
    """Verifica che un dataset valido venga accettato."""

    # Crea il dataset valido.
    dataframe = create_valid_dataframe()

    # Esegue la validazione.
    result = validate_ohlcv(dataframe)

    # Verifica che tutte le righe siano state conservate.
    assert len(result) == 3

    # Verifica che il timestamp sia stato convertito in UTC.
    assert str(result["timestamp"].dt.tz) == "UTC"

    # Verifica l'ordine standard delle colonne.
    assert list(result.columns) == [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]


def test_original_dataframe_is_not_modified() -> None:
    """Verifica che la funzione non modifichi il DataFrame originale."""

    # Crea il dataset e una copia completa.
    dataframe = create_valid_dataframe()
    original_dataframe = dataframe.copy(deep=True)

    # Valida il dataset.
    validate_ohlcv(dataframe)

    # Verifica che l'oggetto originale sia rimasto invariato.
    pd.testing.assert_frame_equal(dataframe, original_dataframe)


def test_empty_dataframe_is_rejected() -> None:
    """Verifica che un dataset vuoto venga rifiutato."""

    # Crea un DataFrame completamente vuoto.
    dataframe = pd.DataFrame()

    # Verifica che venga generato l'errore previsto.
    with pytest.raises(OHLCVValidationError, match="vuoto"):
        validate_ohlcv(dataframe)


def test_missing_column_is_rejected() -> None:
    """Verifica che una colonna obbligatoria mancante venga rilevata."""

    # Crea un dataset corretto.
    dataframe = create_valid_dataframe()

    # Elimina la colonna volume.
    dataframe = dataframe.drop(columns=["volume"])

    # Verifica che venga indicata la colonna mancante.
    with pytest.raises(OHLCVValidationError, match="volume"):
        validate_ohlcv(dataframe)


def test_duplicate_timestamp_is_rejected() -> None:
    """Verifica che i timestamp duplicati vengano rifiutati."""

    # Crea un dataset corretto.
    dataframe = create_valid_dataframe()

    # Duplica il timestamp della prima candela nella seconda.
    dataframe.loc[1, "timestamp"] = dataframe.loc[0, "timestamp"]

    # Verifica che il duplicato venga rilevato.
    with pytest.raises(OHLCVValidationError, match="duplicati"):
        validate_ohlcv(dataframe)


def test_unsorted_timestamps_are_rejected() -> None:
    """Verifica che un dataset non ordinato venga rifiutato."""

    # Crea un dataset corretto.
    dataframe = create_valid_dataframe()

    # Inverte intenzionalmente l'ordine delle righe.
    dataframe = dataframe.iloc[::-1].reset_index(drop=True)

    # Verifica che l'ordine errato venga rilevato.
    with pytest.raises(OHLCVValidationError, match="cronologicamente"):
        validate_ohlcv(dataframe)


def test_invalid_high_is_rejected() -> None:
    """Verifica che un High inferiore al Close venga rifiutato."""

    # Crea un dataset corretto.
    dataframe = create_valid_dataframe()

    # Imposta un High impossibile.
    dataframe.loc[1, "high"] = 1.0000

    # Verifica che l'incoerenza OHLC venga rilevata.
    with pytest.raises(OHLCVValidationError, match="OHLC incoerenti"):
        validate_ohlcv(dataframe)


def test_negative_volume_is_rejected() -> None:
    """Verifica che un volume negativo venga rifiutato."""

    # Crea un dataset corretto.
    dataframe = create_valid_dataframe()

    # Inserisce un volume impossibile.
    dataframe.loc[1, "volume"] = -10

    # Verifica che il volume negativo venga rilevato.
    with pytest.raises(OHLCVValidationError, match="volumi negativi"):
        validate_ohlcv(dataframe)


def test_non_numeric_price_is_rejected() -> None:
    """Verifica che un prezzo testuale venga rifiutato."""

    # Crea un dataset corretto.
    dataframe = create_valid_dataframe()

    # Inserisce un valore che non può essere convertito in numero.
    dataframe.loc[1, "close"] = "invalid"

    # Verifica che il valore non numerico venga rilevato.
    with pytest.raises(OHLCVValidationError, match="non validi"):
        validate_ohlcv(dataframe)
