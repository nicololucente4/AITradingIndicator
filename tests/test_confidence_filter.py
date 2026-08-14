"""Test automatici del filtro di confidenza ML."""

import pandas as pd
import pytest

from src.signals.confidence_filter import (
    ConfidenceFilterConfig,
    ConfidenceFilterError,
    apply_confidence_filter,
)


def create_predictions() -> pd.DataFrame:
    """Crea predizioni deterministiche per i test."""

    return pd.DataFrame(
        {
            "predicted_target": [
                "LONG",
                "SHORT",
                "LONG",
                "NO_TRADE",
            ],
            "probability_long": [
                0.75,
                0.20,
                0.45,
                0.20,
            ],
            "probability_short": [
                0.10,
                0.70,
                0.40,
                0.15,
            ],
            "probability_no_trade": [
                0.15,
                0.10,
                0.15,
                0.65,
            ],
        }
    )


def create_config() -> ConfidenceFilterConfig:
    """Crea la configurazione usata nei test."""

    return ConfidenceFilterConfig(
        minimum_confidence=0.60,
        minimum_probability_margin=0.10,
        fallback_signal="NO_TRADE",
    )


def test_strong_directional_predictions_are_accepted() -> None:
    """Verifica l'accettazione delle predizioni forti."""

    result = apply_confidence_filter(
        predictions=create_predictions(),
        config=create_config(),
    )

    assert result.loc[0, "filtered_signal"] == "LONG"
    assert result.loc[1, "filtered_signal"] == "SHORT"
    assert bool(result.loc[0, "prediction_accepted"])
    assert bool(result.loc[1, "prediction_accepted"])


def test_weak_directional_prediction_becomes_no_trade() -> None:
    """Verifica la conversione di un segnale debole."""

    result = apply_confidence_filter(
        predictions=create_predictions(),
        config=create_config(),
    )

    assert result.loc[2, "raw_prediction"] == "LONG"
    assert result.loc[2, "filtered_signal"] == "NO_TRADE"
    assert not bool(result.loc[2, "prediction_accepted"])


def test_original_no_trade_is_preserved() -> None:
    """Verifica che NO_TRADE rimanga invariato."""

    result = apply_confidence_filter(
        predictions=create_predictions(),
        config=create_config(),
    )

    assert result.loc[3, "raw_prediction"] == "NO_TRADE"
    assert result.loc[3, "filtered_signal"] == "NO_TRADE"
    assert result.loc[3, "filter_reason"] == "MODEL_PREDICTED_NO_TRADE"


def test_probability_margin_is_calculated() -> None:
    """Verifica il calcolo del margine tra le prime due classi."""

    result = apply_confidence_filter(
        predictions=create_predictions(),
        config=create_config(),
    )

    assert result.loc[0, "probability_margin"] == pytest.approx(0.60)

    assert result.loc[2, "probability_margin"] == pytest.approx(0.05)


def test_invalid_probability_sum_is_rejected() -> None:
    """Verifica il rifiuto di probabilità non normalizzate."""

    predictions = create_predictions()

    predictions.loc[0, "probability_long"] = 0.90

    with pytest.raises(
        ConfidenceFilterError,
        match="non sommano a uno",
    ):
        apply_confidence_filter(
            predictions=predictions,
            config=create_config(),
        )


def test_invalid_confidence_threshold_is_rejected() -> None:
    """Verifica il rifiuto di una soglia maggiore di uno."""

    invalid_config = ConfidenceFilterConfig(
        minimum_confidence=1.10,
        minimum_probability_margin=0.10,
    )

    with pytest.raises(
        ConfidenceFilterError,
        match="confidenza minima",
    ):
        apply_confidence_filter(
            predictions=create_predictions(),
            config=invalid_config,
        )


def test_original_dataframe_is_not_modified() -> None:
    """Verifica che l'input non venga modificato."""

    predictions = create_predictions()
    original_predictions = predictions.copy(deep=True)

    apply_confidence_filter(
        predictions=predictions,
        config=create_config(),
    )

    pd.testing.assert_frame_equal(
        predictions,
        original_predictions,
    )


def test_required_columns_are_validated() -> None:
    """Verifica il controllo delle colonne obbligatorie."""

    predictions = create_predictions().drop(columns=["probability_short"])

    with pytest.raises(
        ConfidenceFilterError,
        match="probability_short",
    ):
        apply_confidence_filter(
            predictions=predictions,
            config=create_config(),
        )
