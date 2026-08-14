"""Test automatici della valutazione delle predizioni filtrate."""

import pandas as pd
import pytest

from src.models.filtered_evaluation import (
    FilteredEvaluationError,
    evaluate_filtered_predictions,
)


def create_filtered_predictions() -> pd.DataFrame:
    """Crea predizioni deterministiche prima e dopo il filtro."""

    return pd.DataFrame(
        {
            "actual_target": [
                "LONG",
                "SHORT",
                "NO_TRADE",
                "LONG",
                "SHORT",
                "NO_TRADE",
            ],
            "raw_prediction": [
                "LONG",
                "SHORT",
                "LONG",
                "SHORT",
                "SHORT",
                "NO_TRADE",
            ],
            "filtered_signal": [
                "LONG",
                "SHORT",
                "NO_TRADE",
                "NO_TRADE",
                "SHORT",
                "NO_TRADE",
            ],
            "prediction_accepted": [
                True,
                True,
                False,
                False,
                True,
                True,
            ],
        }
    )


def test_total_predictions_and_coverage() -> None:
    """Verifica conteggio e copertura direzionale."""

    report = evaluate_filtered_predictions(create_filtered_predictions())

    assert report.total_predictions == 6
    assert report.accepted_directional_signals == 3
    assert report.directional_coverage_percentage == 50.0


def test_raw_and_filtered_accuracy_are_calculated() -> None:
    """Verifica le accuracy prima e dopo il filtro."""

    report = evaluate_filtered_predictions(create_filtered_predictions())

    assert report.raw_accuracy == pytest.approx(4 / 6)

    assert report.filtered_accuracy == pytest.approx(5 / 6)


def test_directional_accuracy_is_calculated() -> None:
    """Verifica l'accuracy sui soli segnali direzionali."""

    report = evaluate_filtered_predictions(create_filtered_predictions())

    assert report.accepted_directional_accuracy == 1.0


def test_long_and_short_metrics_are_generated() -> None:
    """Verifica le metriche separate LONG e SHORT."""

    report = evaluate_filtered_predictions(create_filtered_predictions())

    assert 0.0 <= report.long_precision <= 1.0
    assert 0.0 <= report.long_recall <= 1.0
    assert 0.0 <= report.long_f1 <= 1.0

    assert 0.0 <= report.short_precision <= 1.0
    assert 0.0 <= report.short_recall <= 1.0
    assert 0.0 <= report.short_f1 <= 1.0


def test_confusion_matrices_have_expected_shape() -> None:
    """Verifica la struttura delle matrici di confusione."""

    report = evaluate_filtered_predictions(create_filtered_predictions())

    assert len(report.raw_confusion_matrix) == 3
    assert len(report.filtered_confusion_matrix) == 3

    assert all(len(row) == 3 for row in report.raw_confusion_matrix)

    assert all(len(row) == 3 for row in report.filtered_confusion_matrix)


def test_no_directional_signals_returns_none_accuracy() -> None:
    """Verifica il caso senza segnali LONG o SHORT accettati."""

    predictions = create_filtered_predictions()
    predictions["filtered_signal"] = "NO_TRADE"
    predictions["prediction_accepted"] = False

    report = evaluate_filtered_predictions(predictions)

    assert report.accepted_directional_signals == 0
    assert report.accepted_directional_accuracy is None
    assert report.directional_coverage_percentage == 0.0


def test_missing_columns_are_rejected() -> None:
    """Verifica il rifiuto di un dataset incompleto."""

    predictions = create_filtered_predictions().drop(columns=["actual_target"])

    with pytest.raises(
        FilteredEvaluationError,
        match="actual_target",
    ):
        evaluate_filtered_predictions(predictions)


def test_unknown_classes_are_rejected() -> None:
    """Verifica il rifiuto di una classe sconosciuta."""

    predictions = create_filtered_predictions()
    predictions.loc[0, "filtered_signal"] = "BUY"

    with pytest.raises(
        FilteredEvaluationError,
        match="non supportate",
    ):
        evaluate_filtered_predictions(predictions)
