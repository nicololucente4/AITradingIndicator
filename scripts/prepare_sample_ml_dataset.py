"""Prepara un dataset ML dimostrativo con feature e target separati."""

# Importa json per salvare il report del dataset.
import json

# Importa Path per gestire i percorsi dei file.
from pathlib import Path

# Importa pandas per costruire e salvare i dataset.
import pandas as pd

# Importa il validatore OHLCV.
from src.data.validator import validate_ohlcv

# Importa configurazione e pipeline delle feature tecniche.
from src.features.technical import (
    TechnicalFeatureConfig,
    build_technical_features,
)

# Importa configurazione e generatore del target Triple Barrier.
from src.labels.triple_barrier import (
    TripleBarrierConfig,
    build_triple_barrier_labels,
)

# Importa il preparatore del dataset Machine Learning.
from src.models.dataset import build_ml_dataset


def create_demo_dataframe() -> pd.DataFrame:
    """Crea un dataset sintetico con regimi di mercato differenti."""

    # Genera quattrocento timestamp consecutivi da quindici minuti.
    timestamps = pd.date_range(
        start="2025-01-01 00:00:00",
        periods=400,
        freq="15min",
        tz="UTC",
    )

    # Conterrà i prezzi di chiusura generati.
    close_prices: list[float] = []

    # Definisce il prezzo iniziale.
    current_price = 1.1000

    # Genera quattro fasi di mercato differenti.
    for index in range(len(timestamps)):
        # Prima fase rialzista.
        if index < 100:
            movement = 0.00025

        # Seconda fase ribassista.
        elif index < 200:
            movement = -0.00030

        # Terza fase laterale con oscillazioni alternate.
        elif index < 300:
            movement = 0.00015 if index % 2 == 0 else -0.00015

        # Quarta fase rialzista più volatile.
        else:
            movement = 0.00040 if index % 3 != 0 else -0.00010

        # Aggiorna il prezzo corrente.
        current_price += movement

        # Salva il prezzo con precisione controllata.
        close_prices.append(round(current_price, 6))

    # Il primo Open precede leggermente il primo Close.
    # Gli Open successivi coincidono con il Close precedente.
    open_prices = [
        close_prices[0] - 0.0002,
        *close_prices[:-1],
    ]

    # Costruisce il dataset OHLCV.
    dataframe = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_prices,
            "high": [
                max(open_price, close_price) + 0.0005
                for open_price, close_price in zip(
                    open_prices,
                    close_prices,
                    strict=True,
                )
            ],
            "low": [
                min(open_price, close_price) - 0.0005
                for open_price, close_price in zip(
                    open_prices,
                    close_prices,
                    strict=True,
                )
            ],
            "close": close_prices,
            "volume": [100 + (index % 50) for index in range(len(timestamps))],
        }
    )

    # Valida e normalizza il dataset sintetico.
    return validate_ohlcv(dataframe)


def build_distribution_report(
    target: pd.Series,
    source_rows: int,
    ml_rows: int,
) -> dict[str, object]:
    """Crea il report sulla distribuzione delle classi."""

    # Conta il numero di esempi per ogni classe.
    class_counts = target.value_counts().to_dict()

    # Calcola la distribuzione percentuale.
    class_percentages = target.value_counts(normalize=True).mul(100.0).round(4).to_dict()

    # Costruisce il report completo.
    return {
        "dataset_type": "SYNTHETIC_DEMO",
        "source_rows": source_rows,
        "ml_rows": ml_rows,
        "excluded_rows": source_rows - ml_rows,
        "feature_count": 8,
        "feature_columns": [
            "return_1",
            "ema_fast",
            "ema_slow",
            "ema_distance_pct",
            "true_range",
            "atr",
            "atr_pct",
            "volatility",
        ],
        "target_classes": [
            "LONG",
            "SHORT",
            "NO_TRADE",
        ],
        "class_counts": class_counts,
        "class_percentages": class_percentages,
        "target_uses_future_data": True,
        "future_based_columns_in_features": False,
        "timestamp_in_features": False,
    }


def main() -> None:
    """Genera feature, target e file separati per il ML."""

    # Definisce i file da generare.
    features_path = Path("data/features/sample_ml_features.parquet")

    target_path = Path("data/features/sample_ml_target.parquet")

    metadata_path = Path("data/features/sample_ml_metadata.parquet")

    report_path = Path("reports/sample_ml_dataset_report.json")

    # Crea il dataset OHLCV dimostrativo.
    source_dataframe = create_demo_dataframe()

    # Configura le feature tecniche.
    feature_config = TechnicalFeatureConfig(
        ema_fast_period=10,
        ema_slow_period=30,
        atr_period=14,
        volatility_period=20,
    )

    # Calcola le feature usando solamente presente e passato.
    featured_dataframe = build_technical_features(
        dataframe=source_dataframe,
        config=feature_config,
    )

    # Configura il target Triple Barrier.
    label_config = TripleBarrierConfig(
        maximum_holding_bars=12,
        upper_atr_multiplier=1.5,
        lower_atr_multiplier=1.5,
        ambiguous_label="NO_TRADE",
        timeout_label="NO_TRADE",
    )

    # Genera le etichette usando le candele future.
    labeled_dataframe = build_triple_barrier_labels(
        dataframe=featured_dataframe,
        config=label_config,
    )

    # Separa feature, target e metadati.
    ml_dataset = build_ml_dataset(
        dataframe=labeled_dataframe,
    )

    # Verifica che feature e target abbiano lo stesso numero di righe.
    if len(ml_dataset.features) != len(ml_dataset.target):
        raise RuntimeError("Feature e target hanno un numero di righe differente.")

    # Verifica che i metadati siano allineati.
    if len(ml_dataset.metadata) != len(ml_dataset.target):
        raise RuntimeError("Metadati e target hanno un numero di righe differente.")

    # Verifica che il target non sia presente nelle feature.
    if "target" in ml_dataset.features.columns:
        raise RuntimeError("Rilevato data leakage: target presente nelle feature.")

    # Verifica che il timestamp non sia presente nelle feature.
    if "timestamp" in ml_dataset.features.columns:
        raise RuntimeError("Rilevato timestamp nelle feature del modello.")

    # Crea le cartelle necessarie.
    features_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Salva la matrice delle feature.
    ml_dataset.features.to_parquet(
        features_path,
        index=False,
        engine="pyarrow",
    )

    # Salva il target come DataFrame a singola colonna.
    ml_dataset.target.to_frame().to_parquet(
        target_path,
        index=False,
        engine="pyarrow",
    )

    # Salva separatamente sample ID e timestamp.
    ml_dataset.metadata.to_parquet(
        metadata_path,
        index=False,
        engine="pyarrow",
    )

    # Genera il report sulla distribuzione delle classi.
    report = build_distribution_report(
        target=ml_dataset.target,
        source_rows=len(source_dataframe),
        ml_rows=len(ml_dataset.features),
    )

    # Salva il report JSON.
    report_path.write_text(
        json.dumps(
            report,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Mostra il riepilogo nel terminale.
    print("Dataset Machine Learning preparato correttamente.")
    print("Tipo dataset: SYNTHETIC DEMO")
    print(f"Righe OHLCV iniziali: {len(source_dataframe)}")
    print(f"Righe ML disponibili: {len(ml_dataset.features)}")
    print(f"Feature disponibili: {len(ml_dataset.features.columns)}")
    print("")
    print("Distribuzione del target:")
    print(ml_dataset.target.value_counts().to_string())
    print("")
    print(f"Feature: {features_path.resolve()}")
    print(f"Target: {target_path.resolve()}")
    print(f"Metadati: {metadata_path.resolve()}")
    print(f"Report: {report_path.resolve()}")


if __name__ == "__main__":
    # Avvia lo script solamente quando eseguito direttamente.
    main()
