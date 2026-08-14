"""Confronta Logistic Regression e Gradient Boosting Walk-Forward."""

import json
from pathlib import Path

import pandas as pd

from src.models.dataset import MLDataset
from src.models.walk_forward import WalkForwardConfig
from src.models.walk_forward_comparison import (
    compare_models_walk_forward,
)


def load_dataset() -> MLDataset:
    """Carica il dataset ML separato."""

    features = pd.read_parquet(
        "data/features/sample_ml_features.parquet",
        engine="pyarrow",
    )

    target_dataframe = pd.read_parquet(
        "data/features/sample_ml_target.parquet",
        engine="pyarrow",
    )

    metadata = pd.read_parquet(
        "data/features/sample_ml_metadata.parquet",
        engine="pyarrow",
    )

    return MLDataset(
        features=features,
        target=target_dataframe["target"],
        metadata=metadata,
    )


def main() -> None:
    """Esegue il confronto e salva i risultati."""

    folds_path = Path("reports/model_walk_forward_folds.csv")

    predictions_path = Path("reports/model_walk_forward_predictions.csv")

    summary_path = Path("reports/model_walk_forward_summary.json")

    dataset = load_dataset()

    config = WalkForwardConfig(
        initial_training_rows=200,
        test_rows=40,
        step_rows=40,
        gap_rows=2,
        maximum_iterations=200,
        random_state=42,
        class_weight="balanced",
    )

    result = compare_models_walk_forward(
        dataset=dataset,
        config=config,
    )

    folds_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.fold_results.to_csv(
        folds_path,
        index=False,
    )

    result.predictions.to_csv(
        predictions_path,
        index=False,
    )

    summary_path.write_text(
        json.dumps(
            result.summary,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("Confronto Walk-Forward completato.")
    print("")
    print(
        result.fold_results.groupby("model_name")[["accuracy", "macro_f1"]].agg(
            ["mean", "min", "max"]
        )
    )
    print("")
    print(f"Modello selezionato: {result.summary['best_model_by_mean_macro_f1']}")
    print("")
    print(f"Finestre: {folds_path.resolve()}")
    print(f"Predizioni: {predictions_path.resolve()}")
    print(f"Riepilogo: {summary_path.resolve()}")


if __name__ == "__main__":
    main()
