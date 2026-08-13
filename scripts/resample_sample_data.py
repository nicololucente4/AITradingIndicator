"""Aggrega il dataset di esempio da M15 a H1."""

# Importa Path per gestire i percorsi dei file.
from pathlib import Path

# Importa il provider per leggere e salvare i dati.
from src.data.file_provider import FileDataProvider

# Importa la funzione di aggregazione multi-timeframe.
from src.data.timeframe import resample_ohlcv


def main() -> None:
    """Carica il CSV M15, genera H1 e salva il risultato."""

    # Definisce il CSV M15 sorgente.
    input_path = Path("data/sample/EURUSD_M15_sample.csv")

    # Definisce il file H1 da generare.
    output_path = Path("data/processed/EURUSD_H1_sample.parquet")

    # Crea il provider locale.
    provider = FileDataProvider()

    # Carica e valida il dataset M15.
    m15_dataframe = provider.load_csv(input_path)

    # Aggrega solamente le candele H1 complete.
    h1_dataframe = resample_ohlcv(
        dataframe=m15_dataframe,
        source_minutes=15,
        target_minutes=60,
    )

    # Salva il risultato H1 in formato Parquet.
    saved_path = provider.save_parquet(
        dataframe=h1_dataframe,
        output_path=output_path,
    )

    # Mostra il risultato nel terminale.
    print("Aggregazione M15 -> H1 completata.")
    print(f"Candele M15 disponibili: {len(m15_dataframe)}")
    print(f"Candele H1 complete: {len(h1_dataframe)}")
    print("")
    print(h1_dataframe.to_string(index=False))
    print("")
    print(f"File creato: {saved_path.resolve()}")


if __name__ == "__main__":
    # Avvia lo script solamente se eseguito direttamente.
    main()
