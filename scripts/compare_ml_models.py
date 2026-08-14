"""Confronta regressione logistica e Gradient Boosting."""

import json
from pathlib import Path

import joblib
import pandas as pd

from src.models.dataset import MLDataset
from src.models.gradient_boosting import (
    GradientBoostingConfig,
    train_gradient_boosting,
)
from src.models.logistic_baseline import (
    LogisticBaselineConfig,
    train_logistic_baseline,
)


def load_dataset() -> MLDataset:
    """Carica il dataset ML dai file Parquet."""

    features_path = Path("data/features/sample_ml_features.parquet")

    target_path = Path("data/features/sample_ml_target.parquet")

    metadata_path = Path("data/features/sample_ml_metadata.parquet")

    required_paths = [
        features_path,
        target_path,
        metadata_path,
    ]

    missing_paths = [str(path) for path in required_paths if not path.exists()]

    if missing_paths:
        raise FileNotFoundError(f"File ML mancanti: {', '.join(missing_paths)}.")

    features = pd.read_parquet(
        features_path,
        engine="pyarrow",
    )

    target_dataframe = pd.read_parquet(
        target_path,
        engine="pyarrow",
    )

    metadata = pd.read_parquet(
        metadata_path,
        engine="pyarrow",
    )

    if "target" not in target_dataframe.columns:
        raise ValueError("Il file target non contiene la colonna target.")

    target = target_dataframe["target"].copy()
    target.name = "target"

    return MLDataset(
        features=features,
        target=target,
        metadata=metadata,
    )


def main() -> None:
    """Addestra e confronta i due modelli."""

    # Definisce i file di output.
    model_path = Path("models/gradient_boosting_0.1.0.joblib")

    predictions_path = Path("reports/gradient_boosting_predictions.csv")

    report_path = Path("reports/ml_model_comparison.json")

    # Carica il dataset.
    dataset = load_dataset()

    # Addestra la regressione logistica.
    logistic_result = train_logistic_baseline(
        dataset=dataset,
        config=LogisticBaselineConfig(
            test_size_percentage=0.20,
            maximum_iterations=1000,
            random_state=42,
            class_weight="balanced",
        ),
    )

    # Addestra il Gradient Boosting sullo stesso split.
    gradient_result = train_gradient_boosting(
        dataset=dataset,
        config=GradientBoostingConfig(
            test_size_percentage=0.20,
            maximum_iterations=200,
            learning_rate=0.05,
            maximum_leaf_nodes=15,
            minimum_samples_leaf=10,
            l2_regularization=1.0,
            random_state=42,
            balance_classes=True,
        ),
    )

    # Verifica che i due modelli usino gli stessi confini.
    if (
        logistic_result.training_end_timestamp != gradient_result.training_end_timestamp
        or logistic_result.test_start_timestamp != gradient_result.test_start_timestamp
    ):
        raise RuntimeError("I modelli non utilizzano lo stesso split temporale.")

    # Determina il modello migliore secondo Macro F1.
    logistic_macro_f1 = float(logistic_result.metrics["macro_f1"])

    gradient_macro_f1 = float(gradient_result.metrics["macro_f1"])

    best_model = (
        "HIST_GRADIENT_BOOSTING" if gradient_macro_f1 > logistic_macro_f1 else "LOGISTIC_REGRESSION"
    )

    # Costruisce il report.
    report = {
        "comparison_version": "ml_models_0.1.0",
        "dataset_type": "SYNTHETIC_DEMO",
        "same_temporal_split": True,
        "training_end_timestamp": (gradient_result.training_end_timestamp),
        "test_start_timestamp": (gradient_result.test_start_timestamp),
        "logistic_regression": {
            "accuracy": logistic_result.metrics["accuracy"],
            "macro_f1": logistic_result.metrics["macro_f1"],
        },
        "hist_gradient_boosting": {
            "accuracy": gradient_result.metrics["accuracy"],
            "macro_f1": gradient_result.metrics["macro_f1"],
        },
        "best_model_by_macro_f1": best_model,
        "paper_trading_only": True,
    }

    # Crea le cartelle di output.
    model_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    predictions_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Salva il modello e le predizioni.
    joblib.dump(
        gradient_result.model,
        model_path,
    )

    gradient_result.predictions.to_csv(
        predictions_path,
        index=False,
    )

    report_path.write_text(
        json.dumps(
            report,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Mostra il confronto.
    print("Confronto modelli completato.")
    print("Dataset: SYNTHETIC DEMO")
    print("")
    print("Regressione logistica:")
    print(f"Accuracy: {logistic_result.metrics['accuracy']}")
    print(f"Macro F1: {logistic_result.metrics['macro_f1']}")
    print("")
    print("Hist Gradient Boosting:")
    print(f"Accuracy: {gradient_result.metrics['accuracy']}")
    print(f"Macro F1: {gradient_result.metrics['macro_f1']}")
    print("")
    print(f"Migliore per Macro F1: {best_model}")
    print("")
    print(f"Modello: {model_path.resolve()}")
    print(f"Predizioni: {predictions_path.resolve()}")
    print(f"Report: {report_path.resolve()}")


if __name__ == "__main__":
    main()
