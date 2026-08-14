"""Test automatici della Walk-Forward Validation."""

import pandas as pd
import pytest

from src.models.dataset import MLDataset
from src.models.walk_forward import (
    WalkForwardConfig,
    WalkForwardError,
    run_walk_forward,
)


def create_walk_forward_dataset(
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


def create_walk_forward_config() -> WalkForwardConfig:
    """Crea la configurazione comune ai test."""

    return WalkForwardConfig(
        initial_training_rows=60,
        test_rows=20,
        step_rows=20,
        gap_rows=0,
        maximum_iterations=1000,
        random_state=42,
        class_weight="balanced",
    )


def test_expected_number_of_folds_is_generated() -> None:
    """Verifica il numero delle finestre generate."""

    result = run_walk_forward(
        dataset=create_walk_forward_dataset(120),
        config=create_walk_forward_config(),
    )

    assert len(result.fold_reports) == 3
    assert result.metrics["fold_count"] == 3
    assert len(result.predictions) == 60


def test_training_window_expands() -> None:
    """Verifica che il training aumenti a ogni finestra."""

    result = run_walk_forward(
        dataset=create_walk_forward_dataset(120),
        config=create_walk_forward_config(),
    )

    training_sizes = [report.training_rows for report in result.fold_reports]

    assert training_sizes == [60, 80, 100]


def test_test_windows_are_chronologically_after_training() -> None:
    """Verifica la separazione temporale di tutte le finestre."""

    result = run_walk_forward(
        dataset=create_walk_forward_dataset(120),
        config=create_walk_forward_config(),
    )

    for report in result.fold_reports:
        training_end = pd.Timestamp(report.training_end_timestamp)
        test_start = pd.Timestamp(report.test_start_timestamp)

        assert test_start > training_end


def test_predictions_contain_probabilities() -> None:
    """Verifica la presenza delle probabilità per tutte le classi."""

    result = run_walk_forward(
        dataset=create_walk_forward_dataset(120),
        config=create_walk_forward_config(),
    )

    required_columns = {
        "fold_id",
        "actual_target",
        "predicted_target",
        "probability_long",
        "probability_short",
        "probability_no_trade",
        "prediction_confidence",
    }

    assert required_columns.issubset(result.predictions.columns)

    probability_sum = result.predictions[
        [
            "probability_long",
            "probability_short",
            "probability_no_trade",
        ]
    ].sum(axis=1)

    assert all(value == pytest.approx(1.0) for value in probability_sum)


def test_gap_is_respected() -> None:
    """Verifica l'esclusione delle righe presenti nel gap."""

    config = WalkForwardConfig(
        initial_training_rows=60,
        test_rows=20,
        step_rows=20,
        gap_rows=5,
    )

    result = run_walk_forward(
        dataset=create_walk_forward_dataset(125),
        config=config,
    )

    first_report = result.fold_reports[0]

    training_end = pd.Timestamp(first_report.training_end_timestamp)
    test_start = pd.Timestamp(first_report.test_start_timestamp)

    assert test_start - training_end == pd.Timedelta(minutes=90)

    assert result.metrics["gap_rows"] == 5


def test_aggregate_metrics_are_generated() -> None:
    """Verifica la presenza delle metriche aggregate."""

    result = run_walk_forward(
        dataset=create_walk_forward_dataset(120),
        config=create_walk_forward_config(),
    )

    assert "aggregate_accuracy" in result.metrics
    assert "aggregate_macro_f1" in result.metrics
    assert "mean_fold_accuracy" in result.metrics
    assert "minimum_fold_accuracy" in result.metrics
    assert "maximum_fold_accuracy" in result.metrics
    assert result.metrics["shuffle_used"] is False
    assert result.metrics["training_window_expands"] is True


def test_insufficient_dataset_is_rejected() -> None:
    """Verifica il rifiuto di un dataset troppo corto."""

    with pytest.raises(
        WalkForwardError,
        match="righe sufficienti",
    ):
        run_walk_forward(
            dataset=create_walk_forward_dataset(70),
            config=create_walk_forward_config(),
        )


def test_unordered_timestamps_are_rejected() -> None:
    """Verifica il rifiuto di timestamp non ordinati."""

    dataset = create_walk_forward_dataset(120)

    invalid_metadata = dataset.metadata.iloc[::-1].reset_index(drop=True)

    invalid_dataset = MLDataset(
        features=dataset.features,
        target=dataset.target,
        metadata=invalid_metadata,
    )

    with pytest.raises(
        WalkForwardError,
        match="non sono ordinati",
    ):
        run_walk_forward(
            dataset=invalid_dataset,
            config=create_walk_forward_config(),
        )


def test_invalid_configuration_is_rejected() -> None:
    """Verifica il rifiuto di un avanzamento non valido."""

    invalid_config = WalkForwardConfig(
        initial_training_rows=60,
        test_rows=20,
        step_rows=0,
    )

    with pytest.raises(
        WalkForwardError,
        match="avanzamento",
    ):
        run_walk_forward(
            dataset=create_walk_forward_dataset(120),
            config=invalid_config,
        )
