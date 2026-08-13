"""Genera i segnali baseline sul dataset M15 di esempio."""

# Importa Path per gestire il percorso del CSV.
from pathlib import Path

# Importa il provider dei dati locali.
from src.data.file_provider import FileDataProvider

# Importa la configurazione delle feature.
from src.features.technical import TechnicalFeatureConfig

# Importa configurazione e generatore della baseline.
from src.signals.baseline import (
    BaselineSignalConfig,
    build_baseline_signals,
)


def main() -> None:
    """Carica il dataset e genera i segnali baseline."""

    # Definisce il CSV sorgente.
    input_path = Path(
        "data/sample/EURUSD_M15_sample.csv"
    )

    # Crea il provider.
    provider = FileDataProvider()

    # Carica e valida il dataset M15.
    dataframe = provider.load_csv(input_path)

    # Utilizza periodi ridotti per il piccolo dataset dimostrativo.
    feature_config = TechnicalFeatureConfig(
        ema_fast_period=2,
        ema_slow_period=4,
        atr_period=3,
        volatility_period=3,
    )

    # Definisce i parametri della baseline.
    signal_config = BaselineSignalConfig(
        timeframe_minutes=15,
        minimum_atr_percentage=0.0001,
        maximum_atr_percentage=0.05,
        minimum_absolute_return=0.0,
    )

    # Genera le feature e i segnali.
    result = build_baseline_signals(
        dataframe=dataframe,
        feature_config=feature_config,
        signal_config=signal_config,
    )

    # Seleziona le colonne da visualizzare.
    display_columns = [
        "timestamp",
        "signal_available_at",
        "close",
        "ema_fast",
        "ema_slow",
        "atr_pct",
        "signal",
        "signal_status",
        "signal_reason",
    ]

    # Mostra il risultato nel terminale.
    print("Segnali baseline generati correttamente.")
    print("")
    print(
        result[display_columns].to_string(
            index=False
        )
    )


if __name__ == "__main__":
    # Avvia lo script solamente se eseguito direttamente.
    main()