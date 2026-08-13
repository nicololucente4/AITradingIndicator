"""Genera le feature tecniche per il dataset M15 di esempio."""

# Importa Path per gestire i percorsi.
from pathlib import Path

# Importa il provider per leggere e salvare i dati.
from src.data.file_provider import FileDataProvider

# Importa configurazione e pipeline delle feature.
from src.features.technical import (
    TechnicalFeatureConfig,
    build_technical_features,
)


def main() -> None:
    """Carica il CSV, calcola le feature e mostra il risultato."""

    # Definisce il CSV M15 sorgente.
    input_path = Path("data/sample/EURUSD_M15_sample.csv")

    # Crea il provider locale.
    provider = FileDataProvider()

    # Carica e valida il dataset.
    dataframe = provider.load_csv(input_path)

    # Usa periodi ridotti perché il CSV dimostrativo contiene sei righe.
    demo_config = TechnicalFeatureConfig(
        ema_fast_period=2,
        ema_slow_period=4,
        atr_period=3,
        volatility_period=3,
    )

    # Calcola le feature tecniche.
    featured_dataframe = build_technical_features(
        dataframe=dataframe,
        config=demo_config,
    )

    # Definisce le colonne da mostrare nel terminale.
    display_columns = [
        "timestamp",
        "close",
        "return_1",
        "ema_fast",
        "ema_slow",
        "ema_distance_pct",
        "atr",
        "atr_pct",
        "volatility",
    ]

    # Mostra il risultato.
    print("Feature tecniche generate correttamente.")
    print(f"Righe elaborate: {len(featured_dataframe)}")
    print("")
    print(featured_dataframe[display_columns].to_string(index=False))


if __name__ == "__main__":
    # Avvia lo script solamente se eseguito direttamente.
    main()
