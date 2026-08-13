"""Test automatici del FileDataProvider."""

# Importa Path per gestire i percorsi temporanei dei test.
from pathlib import Path

# Importa pandas per creare dataset e rileggere file Parquet.
import pandas as pd

# Importa pytest per verificare le eccezioni previste.
import pytest

# Importa il provider e il relativo errore.
from src.data.file_provider import FileDataProvider, FileDataProviderError


def create_valid_csv(file_path: Path) -> None:
    """Crea un piccolo file CSV OHLCV valido."""

    # Costruisce un dataset deterministico di tre candele.
    dataframe = pd.DataFrame(
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

    # Scrive il dataset nel percorso temporaneo.
    dataframe.to_csv(
        file_path,
        index=False,
    )


def test_load_valid_csv(tmp_path: Path) -> None:
    """Verifica il caricamento di un CSV OHLCV valido."""

    # Definisce il percorso temporaneo.
    csv_path = tmp_path / "valid_data.csv"

    # Crea il file CSV valido.
    create_valid_csv(csv_path)

    # Crea il provider.
    provider = FileDataProvider()

    # Carica e valida il dataset.
    result = provider.load_csv(csv_path)

    # Verifica il numero di righe.
    assert len(result) == 3

    # Verifica la conversione dei timestamp in UTC.
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


def test_missing_csv_is_rejected(tmp_path: Path) -> None:
    """Verifica che un file inesistente venga rifiutato."""

    # Definisce un percorso che non esiste.
    missing_path = tmp_path / "missing.csv"

    # Crea il provider.
    provider = FileDataProvider()

    # Verifica che venga generato l'errore previsto.
    with pytest.raises(FileDataProviderError, match="non esiste"):
        provider.load_csv(missing_path)


def test_invalid_extension_is_rejected(tmp_path: Path) -> None:
    """Verifica che un file non CSV venga rifiutato."""

    # Crea un file di testo temporaneo.
    text_path = tmp_path / "data.txt"
    text_path.write_text(
        "test",
        encoding="utf-8",
    )

    # Crea il provider.
    provider = FileDataProvider()

    # Verifica che l'estensione non valida venga rilevata.
    with pytest.raises(FileDataProviderError, match=r"\.csv"):
        provider.load_csv(text_path)


def test_invalid_csv_content_is_rejected(tmp_path: Path) -> None:
    """Verifica che un CSV con schema non valido venga rifiutato."""

    # Crea un CSV privo delle colonne OHLCV obbligatorie.
    csv_path = tmp_path / "invalid_data.csv"
    csv_path.write_text(
        "date,price\n2026-08-13,1.10\n",
        encoding="utf-8",
    )

    # Crea il provider.
    provider = FileDataProvider()

    # Verifica che l'errore del validatore venga propagato.
    with pytest.raises(FileDataProviderError, match="non è valido"):
        provider.load_csv(csv_path)


def test_save_and_reload_parquet(tmp_path: Path) -> None:
    """Verifica il salvataggio e la rilettura in formato Parquet."""

    # Definisce il CSV sorgente.
    csv_path = tmp_path / "source.csv"

    # Crea il CSV valido.
    create_valid_csv(csv_path)

    # Crea il provider.
    provider = FileDataProvider()

    # Carica e valida il CSV.
    dataframe = provider.load_csv(csv_path)

    # Definisce il percorso Parquet senza estensione.
    output_path = tmp_path / "processed" / "market_data"

    # Salva il dataset in formato Parquet.
    saved_path = provider.save_parquet(
        dataframe,
        output_path,
    )

    # Verifica che l'estensione sia stata aggiunta.
    assert saved_path.suffix == ".parquet"

    # Verifica l'esistenza fisica del file.
    assert saved_path.exists()

    # Rilegge il file appena creato.
    reloaded_dataframe = pd.read_parquet(
        saved_path,
        engine="pyarrow",
    )

    # Confronta il dataset originale con quello riletto.
    pd.testing.assert_frame_equal(
        reloaded_dataframe,
        dataframe,
    )
