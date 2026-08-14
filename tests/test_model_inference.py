"""Test automatici dell'inferenza tramite Model Registry."""

import json
from pathlib import Path

import joblib
import pandas as pd
import pytest
from sklearn.ensemble import HistGradientBoostingClassifier

from src.models.inference import (
    ModelInferenceError,
    load_registered_model,
    run_registered_inference,
)
from src.models.registry import calculate_file_sha256


def create_model_and_registry(
    tmp_path: Path,
    status: str = "CANDIDATE",
) -> tuple[Path, Path]:
    """Crea un modello e un Registry temporanei."""

    feature_columns = [
        "return_1",
        "ema_fast",
        "atr",
    ]

    training_features = pd.DataFrame(
        {
            "return_1": [
                -0.02,
                -0.01,
                0.00,
                0.01,
                0.02,
                0.03,
            ],
            "ema_fast": [
                99.0,
                99.5,
                100.0,
                100.5,
                101.0,
                101.5,
            ],
            "atr": [
                1.0,
                1.1,
                1.0,
                1.1,
                1.0,
                1.1,
            ],
        }
    )

    training_target = pd.Series(
        [
            "SHORT",
            "SHORT",
            "NO_TRADE",
            "LONG",
            "LONG",
            "LONG",
        ]
    )

    model = HistGradientBoostingClassifier(
        max_iter=20,
        min_samples_leaf=1,
        random_state=42,
        early_stopping=False,
    )

    model.fit(
        training_features,
        training_target,
    )

    model_path = tmp_path / "model.joblib"

    joblib.dump(
        model,
        model_path,
    )

    registry_path = tmp_path / "registry.json"

    registry_entry = {
        "model_version": "test_model_0.1.0",
        "model_type": "HIST_GRADIENT_BOOSTING",
        "status": status,
        "model_path": str(model_path),
        "model_sha256": calculate_file_sha256(model_path),
        "feature_set_version": "0.1.0",
        "feature_columns": feature_columns,
        "validation_type": "TEST",
        "fold_count": 2,
        "mean_macro_f1": 0.5,
        "minimum_macro_f1": 0.4,
        "mean_accuracy": 0.6,
        "registered_at_utc": ("2026-08-14T10:00:00+00:00"),
        "paper_trading_only": True,
    }

    registry_path.write_text(
        json.dumps(
            [registry_entry],
            indent=4,
        ),
        encoding="utf-8",
    )

    return model_path, registry_path


def create_inference_features() -> pd.DataFrame:
    """Crea feature valide per l'inferenza."""

    return pd.DataFrame(
        {
            "return_1": [
                0.015,
                -0.015,
            ],
            "ema_fast": [
                100.8,
                99.2,
            ],
            "atr": [
                1.0,
                1.1,
            ],
        }
    )


def test_registered_model_is_loaded(
    tmp_path: Path,
) -> None:
    """Verifica il caricamento di un modello registrato."""

    _, registry_path = create_model_and_registry(tmp_path)

    model, entry = load_registered_model(
        registry_path=registry_path,
        model_version="test_model_0.1.0",
    )

    assert hasattr(model, "predict")
    assert entry["status"] == "CANDIDATE"


def test_predictions_and_probabilities_are_generated(
    tmp_path: Path,
) -> None:
    """Verifica classe, probabilità e audit."""

    _, registry_path = create_model_and_registry(tmp_path)

    result = run_registered_inference(
        features=create_inference_features(),
        registry_path=registry_path,
        model_version="test_model_0.1.0",
    )

    assert len(result) == 2

    required_columns = {
        "predicted_target",
        "probability_long",
        "probability_short",
        "probability_no_trade",
        "prediction_confidence",
        "model_version",
        "model_sha256",
        "inference_mode",
    }

    assert required_columns.issubset(result.columns)

    probability_sum = result[
        [
            "probability_long",
            "probability_short",
            "probability_no_trade",
        ]
    ].sum(axis=1)

    assert all(value == pytest.approx(1.0) for value in probability_sum)

    assert (result["inference_mode"] == "PAPER_ONLY").all()


def test_feature_order_is_restored_from_registry(
    tmp_path: Path,
) -> None:
    """Verifica il riordinamento automatico delle feature."""

    _, registry_path = create_model_and_registry(tmp_path)

    features = create_inference_features()[
        [
            "atr",
            "return_1",
            "ema_fast",
        ]
    ]

    result = run_registered_inference(
        features=features,
        registry_path=registry_path,
        model_version="test_model_0.1.0",
    )

    assert len(result) == 2


def test_missing_feature_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il rifiuto di una feature mancante."""

    _, registry_path = create_model_and_registry(tmp_path)

    features = create_inference_features().drop(columns=["atr"])

    with pytest.raises(
        ModelInferenceError,
        match="atr",
    ):
        run_registered_inference(
            features=features,
            registry_path=registry_path,
            model_version="test_model_0.1.0",
        )


def test_modified_model_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il blocco di un modello con hash differente."""

    model_path, registry_path = create_model_and_registry(tmp_path)

    # Modifica il file dopo la registrazione.
    with model_path.open("ab") as model_file:
        model_file.write(b"unauthorized-change")

    with pytest.raises(
        ModelInferenceError,
        match="SHA-256",
    ):
        load_registered_model(
            registry_path=registry_path,
            model_version="test_model_0.1.0",
        )


def test_unregistered_version_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il rifiuto di una versione non registrata."""

    _, registry_path = create_model_and_registry(tmp_path)

    with pytest.raises(
        ModelInferenceError,
        match="non è presente",
    ):
        load_registered_model(
            registry_path=registry_path,
            model_version="unknown_model",
        )


def test_rejected_model_is_not_loaded(
    tmp_path: Path,
) -> None:
    """Verifica il blocco di un modello REJECTED."""

    _, registry_path = create_model_and_registry(
        tmp_path,
        status="REJECTED",
    )

    with pytest.raises(
        ModelInferenceError,
        match="non consentito",
    ):
        load_registered_model(
            registry_path=registry_path,
            model_version="test_model_0.1.0",
        )


def test_only_approved_status_can_be_required(
    tmp_path: Path,
) -> None:
    """Verifica la possibilità di richiedere APPROVED."""

    _, registry_path = create_model_and_registry(
        tmp_path,
        status="CANDIDATE",
    )

    with pytest.raises(
        ModelInferenceError,
        match="non consentito",
    ):
        load_registered_model(
            registry_path=registry_path,
            model_version="test_model_0.1.0",
            allowed_statuses={"APPROVED"},
        )


def test_original_features_are_not_modified(
    tmp_path: Path,
) -> None:
    """Verifica che l'inferenza non modifichi le feature."""

    _, registry_path = create_model_and_registry(tmp_path)

    features = create_inference_features()
    original_features = features.copy(deep=True)

    run_registered_inference(
        features=features,
        registry_path=registry_path,
        model_version="test_model_0.1.0",
    )

    pd.testing.assert_frame_equal(
        features,
        original_features,
    )
