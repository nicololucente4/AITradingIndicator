"""Caricamento e salvataggio locale dei dati OHLCV."""

# Importa Path per gestire correttamente i percorsi dei file.
from pathlib import Path

# Importa pandas per leggere CSV e scrivere file Parquet.
import pandas as pd

# Importa il validatore OHLCV già sviluppato.
from src.data.validator import OHLCVValidationError, validate_ohlcv


class FileDataProviderError(RuntimeError):
    """Errore relativo alla lettura o scrittura dei dati locali."""


class FileDataProvider:
    """Carica dati OHLCV da file locali e li valida."""

    def load_csv(self, file_path: str | Path) -> pd.DataFrame:
        """Carica e valida un dataset OHLCV da un file CSV.

        Args:
            file_path: Percorso del file CSV da caricare.

        Returns:
            DataFrame OHLCV validato e normalizzato.

        Raises:
            FileDataProviderError: se il file non esiste, non è leggibile
                oppure non supera la validazione OHLCV.
        """

        # Converte il percorso ricevuto in un oggetto Path.
        csv_path = Path(file_path)

        # Verifica che il percorso esista.
        if not csv_path.exists():
            raise FileDataProviderError(f"Il file CSV non esiste: {csv_path}.")

        # Verifica che il percorso rappresenti un file e non una cartella.
        if not csv_path.is_file():
            raise FileDataProviderError(f"Il percorso non rappresenta un file: {csv_path}.")

        # Accetta solamente file con estensione CSV.
        if csv_path.suffix.lower() != ".csv":
            raise FileDataProviderError(f"Il file deve avere estensione .csv: {csv_path}.")

        try:
            # Legge il contenuto del CSV.
            # La conversione del timestamp viene gestita dal validatore.
            dataframe = pd.read_csv(csv_path)

        except (OSError, UnicodeDecodeError, pd.errors.ParserError) as error:
            # Converte gli errori tecnici in un errore specifico del progetto.
            raise FileDataProviderError(
                f"Impossibile leggere il file CSV {csv_path}: {error}"
            ) from error

        try:
            # Valida e normalizza il dataset letto dal CSV.
            return validate_ohlcv(dataframe)

        except OHLCVValidationError as error:
            # Aggiunge il nome del file al messaggio del validatore.
            raise FileDataProviderError(f"Il file CSV {csv_path} non è valido: {error}") from error

    def save_parquet(
        self,
        dataframe: pd.DataFrame,
        output_path: str | Path,
    ) -> Path:
        """Valida e salva un dataset OHLCV in formato Parquet.

        Args:
            dataframe: Dataset OHLCV da validare e salvare.
            output_path: Percorso del file Parquet da creare.

        Returns:
            Percorso del file Parquet creato.

        Raises:
            FileDataProviderError: se il dataset non è valido oppure
                il file non può essere scritto.
        """

        # Converte il percorso di destinazione in un oggetto Path.
        parquet_path = Path(output_path)

        # Aggiunge automaticamente l'estensione se non è presente.
        if parquet_path.suffix.lower() != ".parquet":
            parquet_path = parquet_path.with_suffix(".parquet")

        try:
            # Ripete la validazione prima di scrivere il file.
            validated_dataframe = validate_ohlcv(dataframe)

        except OHLCVValidationError as error:
            raise FileDataProviderError(f"Il dataset non può essere salvato: {error}") from error

        try:
            # Crea automaticamente la cartella di destinazione.
            parquet_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            # Salva i dati senza includere l'indice numerico di pandas.
            validated_dataframe.to_parquet(
                parquet_path,
                index=False,
                engine="pyarrow",
            )

        except (OSError, ValueError, ImportError) as error:
            raise FileDataProviderError(
                f"Impossibile salvare il file Parquet {parquet_path}: {error}"
            ) from error

        # Restituisce il percorso del file creato.
        return parquet_path
