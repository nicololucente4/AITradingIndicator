"""Test automatici del report di qualità OHLCV."""

# Importa timedelta per definire la frequenza attesa.
from datetime import timedelta

# Importa pandas per creare dataset di test.
import pandas as pd

# Importa pytest per verificare gli errori attesi.
import pytest

# Importa la funzione che genera il report.
from src.data.quality_report import generate_quality_report


def create_complete_dataframe() -> pd.DataFrame:
    """Crea un dataset M15 completo e ordinato."""

    # Restituisce quattro candele consecutive da 15 minuti.
    return pd.DataFrame(
        {
            "timestamp": [
                "2026-08-13 10:00:00",
                "2026-08-13 10:15:00",
                "2026-08-13 10:30:00",
                "2026-08-13 10:45:00",
            ],
            "open": [1.1000, 1.1010, 1.1020, 1.1030],
            "high": [1.1020, 1.1030, 1.1040, 1.1050],
            "low": [1.0990, 1.1000, 1.1010, 1.1020],
            "close": [1.1010, 1.1020, 1.1030, 1.1040],
            "volume": [100, 120, 0, 140],
        }
    )


def test_complete_dataset_report() -> None:
    """Verifica il report di un dataset M15 completo."""

    # Crea il dataset completo.
    dataframe = create_complete_dataframe()

    # Genera il report usando una frequenza attesa di 15 minuti.
    report = generate_quality_report(
        dataframe,
        expected_interval=timedelta(minutes=15),
    )

    # Verifica il numero di righe.
    assert report.total_rows == 4

    # Verifica il numero teorico di righe.
    assert report.expected_rows == 4

    # Verifica che non risultino candele mancanti.
    assert report.missing_rows == 0

    # Verifica la completezza totale.
    assert report.completeness_percentage == 100.0

    # Verifica l'intervallo atteso in secondi.
    assert report.expected_interval_seconds == 900.0

    # Verifica l'intervallo rilevato in secondi.
    assert report.detected_interval_seconds == 900.0

    # Verifica l'assenza di intervalli irregolari.
    assert report.irregular_interval_count == 0


def test_missing_candle_is_detected() -> None:
    """Verifica che una candela mancante venga rilevata."""

    # Crea il dataset completo.
    dataframe = create_complete_dataframe()

    # Elimina la candela delle 10:30.
    dataframe = dataframe.drop(index=2).reset_index(drop=True)

    # Genera il report.
    report = generate_quality_report(
        dataframe,
        expected_interval=timedelta(minutes=15),
    )

    # Le candele teoriche restano quattro.
    assert report.expected_rows == 4

    # Deve risultare una candela mancante.
    assert report.missing_rows == 1

    # Deve risultare un intervallo temporale irregolare.
    assert report.irregular_interval_count == 1

    # Tre candele presenti su quattro corrispondono al 75%.
    assert report.completeness_percentage == 75.0


def test_zero_volume_is_detected() -> None:
    """Verifica il conteggio delle candele con volume nullo."""

    # Crea il dataset contenente un volume uguale a zero.
    dataframe = create_complete_dataframe()

    # Genera il report.
    report = generate_quality_report(
        dataframe,
        expected_interval=timedelta(minutes=15),
    )

    # Verifica il numero di righe con volume nullo.
    assert report.zero_volume_rows == 1

    # Verifica la percentuale di righe con volume nullo.
    assert report.zero_volume_percentage == 25.0

    # Verifica il volume minimo.
    assert report.minimum_volume == 0.0

    # Verifica il volume massimo.
    assert report.maximum_volume == 140.0

    # Verifica il volume medio.
    assert report.average_volume == 90.0


def test_report_can_be_converted_to_dictionary() -> None:
    """Verifica la conversione del report in dizionario."""

    # Crea il dataset completo.
    dataframe = create_complete_dataframe()

    # Genera il report.
    report = generate_quality_report(
        dataframe,
        expected_interval=timedelta(minutes=15),
    )

    # Converte il report in dizionario.
    report_dictionary = report.to_dict()

    # Verifica alcuni valori rappresentativi.
    assert report_dictionary["total_rows"] == 4
    assert report_dictionary["missing_rows"] == 0
    assert report_dictionary["completeness_percentage"] == 100.0


def test_non_positive_interval_is_rejected() -> None:
    """Verifica che un intervallo non positivo venga rifiutato."""

    # Crea un dataset valido.
    dataframe = create_complete_dataframe()

    # Verifica il rifiuto di un intervallo uguale a zero.
    with pytest.raises(ValueError, match="maggiore di zero"):
        generate_quality_report(
            dataframe,
            expected_interval=timedelta(seconds=0),
        )
