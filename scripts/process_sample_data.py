"""Elabora il CSV di esempio e lo salva in formato Parquet."""

# Importa Path per gestire i percorsi dei file.
from pathlib import Path

# Importa il provider sviluppato nel progetto.
from src.data.file_provider import FileDataProvider


def main() -> None:
    """Carica, valida e salva il dataset di esempio."""

    # Definisce il percorso del CSV sorgente.
    input_path = Path("data/sample/EURUSD_M15_sample.csv")

    # Definisce il percorso del file Parquet da generare.
    output_path = Path("data/processed/EURUSD_M15_sample.parquet")

    # Crea il provider locale.
    provider = FileDataProvider()

    # Carica e valida il dataset CSV.
    dataframe = provider.load_csv(input_path)

    # Salva il dataset validato in formato Parquet.
    saved_path = provider.save_parquet(
        dataframe,
        output_path,
    )

    # Mostra il risultato nel terminale.
    print("Dataset elaborato correttamente.")
    print(f"Righe validate: {len(dataframe)}")
    print(f"Prima candela: {dataframe['timestamp'].min()}")
    print(f"Ultima candela: {dataframe['timestamp'].max()}")
    print(f"File creato: {saved_path.resolve()}")


if __name__ == "__main__":
    # Avvia lo script solamente quando viene eseguito direttamente.
    main()
