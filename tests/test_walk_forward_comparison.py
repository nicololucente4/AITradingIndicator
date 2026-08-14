"""Test del confronto Walk-Forward tra modelli."""

import pandas as pd
import pytest

from src.models.dataset import MLDataset
from src.models.walk_forward import WalkForwardConfig
from src.models.walk_forward_comparison import (
    WalkForwardComparisonError,
    compare_models_walk_forward,
)


def create_dataset(
    row_count: int = 140,
) -> MLDataset:
    """Crea un dataset temporale con tre classi."""

    timestamps = pd.date_range(
        start="2025-01-01",
        periods=row_count,
        freq="15min",
        tz="UTC",
    )

    features = pd.DataFrame(
        {
            "return_1": [((index % 9) - 4) / 1000 for index in range(row_count)],
            "ema_fast": [100 + index * 0.01 for index in range(row_count)],
            "ema_slow": [100 + index * 0.008 for index in range(row_count)],
            "ema_distance_pct": [((index % 7) - 3) / 1000 for index in range(row_count)],
            "true_range": [1 + (index % 5) * 0.1 for index in range(row_count)],
            "atr": [1 + (index % 4) * 0.1 for index in range(row_count)],
            "atr_pct": [0.01 + (index % 4) * 0.001 for index in range(row_count)],
            "volatility": [0.01 + (index % 6) * 0.002 for index in range(row_count)],
        }
    )

    target = pd.Series(
        [["LONG", "SHORT", "NO_TRADE"][index % 3] for index in range(row_count)],
        name="target",
    )

    metadata = pd.DataFrame(
        {
            "sample_id": range(row_count),
            "timestamp": timestamps,
        }
    )

    return MLDataset(
        features=features,
        target=target,
        metadata=metadata,
    )


def create_config() -> WalkForwardConfig:
    """Crea la configurazione comune."""

    return WalkForwardConfig(
        initial_training_rows=60,
        test_rows=20,
        step_rows=20,
        gap_rows=2,
        maximum_iterations=30,
        random_state=42,
        class_weight="balanced",
    )


def test_both_models_use_same_number_of_folds() -> None:
    """Verifica che i due modelli usino le stesse finestre."""

    result = compare_models_walk_forward(
        dataset=create_dataset(),
        config=create_config(),
    )

    fold_counts = result.fold_results.groupby("model_name")["fold_id"].nunique()

    assert fold_counts.nunique() == 1
    assert result.summary["same_folds_used"] is True


def test_training_windows_expand() -> None:
    """Verifica l'espansione delle finestre."""

    result = compare_models_walk_forward(
        dataset=create_dataset(),
        config=create_config(),
    )

    logistic_folds = result.fold_results[result.fold_results["model_name"] == "LOGISTIC_REGRESSION"]

    assert list(logistic_folds["training_rows"]) == [60, 80, 100]


def test_predictions_exist_for_both_models() -> None:
    """Verifica le predizioni dei due modelli."""

    result = compare_models_walk_forward(
        dataset=create_dataset(),
        config=create_config(),
    )

    assert set(result.predictions["model_name"]) == {
        "LOGISTIC_REGRESSION",
        "HIST_GRADIENT_BOOSTING",
    }


def test_probability_columns_are_available() -> None:
    """Verifica le probabilità di tutte le classi."""

    result = compare_models_walk_forward(
        dataset=create_dataset(),
        config=create_config(),
    )

    probability_columns = [
        "probability_long",
        "probability_short",
        "probability_no_trade",
    ]

    assert set(probability_columns).issubset(result.predictions.columns)

    probability_sum = result.predictions[probability_columns].sum(axis=1)

    assert all(value == pytest.approx(1.0) for value in probability_sum)


def test_summary_contains_both_models() -> None:
    """Verifica il riepilogo dei modelli."""

    result = compare_models_walk_forward(
        dataset=create_dataset(),
        config=create_config(),
    )

    models = result.summary["models"]

    assert "LOGISTIC_REGRESSION" in models
    assert "HIST_GRADIENT_BOOSTING" in models
    assert "best_model_by_mean_macro_f1" in result.summary


def test_insufficient_dataset_is_rejected() -> None:
    """Verifica il rifiuto di uno storico insufficiente."""

    with pytest.raises(
        WalkForwardComparisonError,
        match="righe sufficienti",
    ):
        compare_models_walk_forward(
            dataset=create_dataset(70),
            config=create_config(),
        )
