"""Test automatici del modello Gradient Boosting."""

import pandas as pd
import pytest

from src.models.dataset import MLDataset
from src.models.gradient_boosting import (
    GradientBoostingConfig,
    GradientBoostingError,
    train_gradient_boosting,
)


def create_ml_dataset(
    row_count: int = 120,
) -> MLDataset:
    """Crea un dataset ML temporale con tre classi."""

    timestamps = pd.date_range(
        start="2025-01-01 00:00:00",
        periods=row_count,
        freq="15min",
        tz="UTC",
    )

    features = pd.DataFrame(
        {
            "return_1": [((index % 9) - 4) / 1000 for index in range(row_count)],
            "ema_fast": [100.0 + index * 0.01 for index in range(row_count)],
            "ema_slow": [100.0 + index * 0.008 for index in range(row_count)],
            "ema_distance_pct": [((index % 7) - 3) / 1000 for index in range(row_count)],
            "true_range": [1.0 + (index % 5) * 0.1 for index in range(row_count)],
            "atr": [1.0 + (index % 4) * 0.1 for index in range(row_count)],
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


def create_config() -> GradientBoostingConfig:
    """Crea la configurazione comune ai test."""

    return GradientBoostingConfig(
        test_size_percentage=0.20,
        maximum_iterations=30,
        learning_rate=0.05,
        maximum_leaf_nodes=7,
        minimum_samples_leaf=5,
        l2_regularization=1.0,
        random_state=42,
        balance_classes=True,
    )


def test_temporal_split_sizes_are_correct() -> None:
    """Verifica le dimensioni dello split."""

    result = train_gradient_boosting(
        dataset=create_ml_dataset(),
        config=create_config(),
    )

    assert result.training_rows == 96
    assert result.test_rows == 24


def test_test_is_after_training() -> None:
    """Verifica la separazione cronologica."""

    result = train_gradient_boosting(
        dataset=create_ml_dataset(),
        config=create_config(),
    )

    assert pd.Timestamp(result.test_start_timestamp) > pd.Timestamp(result.training_end_timestamp)


def test_probability_columns_are_generated() -> None:
    """Verifica probabilità e confidenza."""

    result = train_gradient_boosting(
        dataset=create_ml_dataset(),
        config=create_config(),
    )

    required_columns = {
        "probability_long",
        "probability_short",
        "probability_no_trade",
        "prediction_confidence",
    }

    assert required_columns.issubset(result.predictions.columns)


def test_probabilities_sum_to_one() -> None:
    """Verifica che le probabilità siano normalizzate."""

    result = train_gradient_boosting(
        dataset=create_ml_dataset(),
        config=create_config(),
    )

    probability_sum = result.predictions[
        [
            "probability_long",
            "probability_short",
            "probability_no_trade",
        ]
    ].sum(axis=1)

    assert all(value == pytest.approx(1.0) for value in probability_sum)


def test_metrics_are_generated() -> None:
    """Verifica le metriche principali."""

    result = train_gradient_boosting(
        dataset=create_ml_dataset(),
        config=create_config(),
    )

    assert "accuracy" in result.metrics
    assert "macro_f1" in result.metrics
    assert "confusion_matrix" in result.metrics
    assert "classification_report" in result.metrics
    assert result.metrics["shuffle_used"] is False


def test_original_dataset_is_not_modified() -> None:
    """Verifica che il dataset sorgente non venga modificato."""

    dataset = create_ml_dataset()

    original_features = dataset.features.copy(deep=True)
    original_target = dataset.target.copy(deep=True)
    original_metadata = dataset.metadata.copy(deep=True)

    train_gradient_boosting(
        dataset=dataset,
        config=create_config(),
    )

    pd.testing.assert_frame_equal(
        dataset.features,
        original_features,
    )

    pd.testing.assert_series_equal(
        dataset.target,
        original_target,
    )

    pd.testing.assert_frame_equal(
        dataset.metadata,
        original_metadata,
    )


def test_missing_values_are_rejected() -> None:
    """Verifica il rifiuto di feature mancanti."""

    dataset = create_ml_dataset()

    invalid_features = dataset.features.copy()
    invalid_features.loc[5, "atr"] = float("nan")

    invalid_dataset = MLDataset(
        features=invalid_features,
        target=dataset.target,
        metadata=dataset.metadata,
    )

    with pytest.raises(
        GradientBoostingError,
        match="valori mancanti",
    ):
        train_gradient_boosting(
            dataset=invalid_dataset,
            config=create_config(),
        )


def test_invalid_configuration_is_rejected() -> None:
    """Verifica il rifiuto di un learning rate non valido."""

    invalid_config = GradientBoostingConfig(
        learning_rate=0.0,
    )

    with pytest.raises(
        GradientBoostingError,
        match="learning rate",
    ):
        train_gradient_boosting(
            dataset=create_ml_dataset(),
            config=invalid_config,
        )
