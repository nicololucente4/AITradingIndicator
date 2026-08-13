"""Genera segnali baseline e livelli teorici di rischio."""

# Importa Path per gestire il percorso del dataset.
from pathlib import Path

# Importa il provider dei dati locali.
from src.data.file_provider import FileDataProvider

# Importa la configurazione delle feature.
from src.features.technical import TechnicalFeatureConfig

# Importa configurazione e Risk Engine.
from src.risk.levels import (
    RiskLevelConfig,
    build_risk_levels,
)

# Importa configurazione e generatore della baseline.
from src.signals.baseline import (
    BaselineSignalConfig,
    build_baseline_signals,
)


def main() -> None:
    """Genera segnali, Entry, Stop Loss e Take Profit."""

    # Definisce il dataset CSV sorgente.
    input_path = Path("data/sample/EURUSD_M15_sample.csv")

    # Crea il provider locale.
    provider = FileDataProvider()

    # Carica e valida il dataset.
    dataframe = provider.load_csv(input_path)

    # Utilizza periodi ridotti per il dataset dimostrativo.
    feature_config = TechnicalFeatureConfig(
        ema_fast_period=2,
        ema_slow_period=4,
        atr_period=3,
        volatility_period=3,
    )

    # Configura la baseline.
    signal_config = BaselineSignalConfig(
        timeframe_minutes=15,
        minimum_atr_percentage=0.0001,
        maximum_atr_percentage=0.05,
        minimum_absolute_return=0.0,
    )

    # Genera i segnali baseline.
    signal_dataframe = build_baseline_signals(
        dataframe=dataframe,
        feature_config=feature_config,
        signal_config=signal_config,
    )

    # Configura i livelli di rischio simulati.
    risk_config = RiskLevelConfig(
        stop_atr_multiplier=1.5,
        minimum_stop_percentage=0.001,
        take_profit_1_r=1.0,
        take_profit_2_r=2.0,
        take_profit_3_r=3.0,
    )

    # Calcola Entry, Stop Loss e Take Profit.
    result = build_risk_levels(
        dataframe=signal_dataframe,
        config=risk_config,
    )

    # Seleziona le colonne da visualizzare.
    display_columns = [
        "timestamp",
        "signal_available_at",
        "signal",
        "close",
        "atr",
        "entry_price",
        "stop_loss",
        "take_profit_1",
        "take_profit_2",
        "take_profit_3",
        "risk_status",
    ]

    # Mostra il risultato nel terminale.
    print("Livelli teorici di rischio generati correttamente.")
    print("Modalità: PAPER ONLY")
    print("")
    print(result[display_columns].to_string(index=False))


if __name__ == "__main__":
    # Avvia lo script solamente se eseguito direttamente.
    main()
