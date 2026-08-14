"""Confronto Walk-Forward tra modelli Machine Learning."""

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

from src.models.dataset import MLDataset
from src.models.walk_forward import WalkForwardConfig


class WalkForwardComparisonError(ValueError):
    """Errore generato durante il confronto Walk-Forward."""


@dataclass(frozen=True)
class ModelFoldResult:
    """Risultato di un modello in una singola finestra."""

    fold_id: int
    model_name: str
    training_rows: int
    test_rows: int
    training_end_timestamp: str
    test_start_timestamp: str
    accuracy: float
    macro_f1: float

    def to_dict(self) -> dict[str, int | float | str]:
        """Converte il risultato in un dizionario."""

        return asdict(self)


@dataclass(frozen=True)
class WalkForwardComparisonResult:
    """Risultato complessivo del confronto."""

    fold_results: pd.DataFrame
    predictions: pd.DataFrame
    summary: dict[str, object]


def _validate_dataset(
    dataset: MLDataset,
    config: WalkForwardConfig,
) -> None:
    """Verifica dataset e configurazione."""

    if not (len(dataset.features) == len(dataset.target) == len(dataset.metadata)):
        raise WalkForwardComparisonError("Feature, target e metadati non sono allineati.")

    if dataset.features.empty:
        raise WalkForwardComparisonError("Il dataset ML è vuoto.")

    if dataset.features.isna().any().any():
        raise WalkForwardComparisonError("Le feature contengono valori mancanti.")

    if dataset.target.isna().any():
        raise WalkForwardComparisonError("Il target contiene valori mancanti.")

    if "timestamp" not in dataset.metadata.columns:
        raise WalkForwardComparisonError("I metadati non contengono il timestamp.")

    if not dataset.metadata["timestamp"].is_monotonic_increasing:
        raise WalkForwardComparisonError("I timestamp non sono ordinati.")

    minimum_rows = config.initial_training_rows + config.gap_rows + config.test_rows

    if len(dataset.features) < minimum_rows:
        raise WalkForwardComparisonError("Il dataset non contiene righe sufficienti.")


def _create_logistic_model(
    config: WalkForwardConfig,
) -> Pipeline:
    """Crea la pipeline della regressione logistica."""

    return Pipeline(
        steps=[
            (
                "scaler",
                StandardScaler(),
            ),
            (
                "classifier",
                LogisticRegression(
                    max_iter=config.maximum_iterations,
                    random_state=config.random_state,
                    class_weight=config.class_weight,
                ),
            ),
        ]
    )


def _create_gradient_model(
    config: WalkForwardConfig,
) -> HistGradientBoostingClassifier:
    """Crea il modello Gradient Boosting."""

    return HistGradientBoostingClassifier(
        max_iter=min(config.maximum_iterations, 200),
        learning_rate=0.05,
        max_leaf_nodes=15,
        min_samples_leaf=10,
        l2_regularization=1.0,
        random_state=config.random_state,
        early_stopping=False,
    )


def _add_probabilities(
    dataframe: pd.DataFrame,
    probabilities: np.ndarray,
    model_classes: list[str],
) -> pd.DataFrame:
    """Aggiunge le probabilità delle tre classi."""

    result = dataframe.copy()

    for class_name in [
        "LONG",
        "SHORT",
        "NO_TRADE",
    ]:
        column = f"probability_{class_name.lower()}"

        if class_name not in model_classes:
            result[column] = 0.0
            continue

        class_index = model_classes.index(class_name)
        result[column] = probabilities[:, class_index]

    result["prediction_confidence"] = result[
        [
            "probability_long",
            "probability_short",
            "probability_no_trade",
        ]
    ].max(axis=1)

    return result


def compare_models_walk_forward(
    dataset: MLDataset,
    config: WalkForwardConfig,
) -> WalkForwardComparisonResult:
    """Confronta i modelli usando le stesse finestre temporali."""

    _validate_dataset(
        dataset=dataset,
        config=config,
    )

    class_order = [
        "LONG",
        "SHORT",
        "NO_TRADE",
    ]

    fold_rows: list[dict[str, int | float | str]] = []
    prediction_frames: list[pd.DataFrame] = []

    training_end = config.initial_training_rows
    fold_id = 1

    while True:
        test_start = training_end + config.gap_rows
        test_end = test_start + config.test_rows

        if test_end > len(dataset.features):
            break

        training_features = dataset.features.iloc[:training_end].copy()

        training_target = dataset.target.iloc[:training_end].copy()

        test_features = dataset.features.iloc[test_start:test_end].copy()

        test_target = dataset.target.iloc[test_start:test_end].copy()

        test_metadata = dataset.metadata.iloc[test_start:test_end].reset_index(drop=True)

        training_metadata = dataset.metadata.iloc[:training_end]

        if training_target.nunique() < 2:
            raise WalkForwardComparisonError(f"La finestra {fold_id} contiene meno di due classi.")

        models = {
            "LOGISTIC_REGRESSION": _create_logistic_model(config),
            "HIST_GRADIENT_BOOSTING": _create_gradient_model(config),
        }

        for model_name, model in models.items():
            if model_name == "HIST_GRADIENT_BOOSTING":
                sample_weight = compute_sample_weight(
                    class_weight="balanced",
                    y=training_target,
                )

                model.fit(
                    training_features,
                    training_target,
                    sample_weight=sample_weight,
                )
            else:
                model.fit(
                    training_features,
                    training_target,
                )

            predicted_target = model.predict(test_features)

            probabilities = model.predict_proba(test_features)

            model_classes = [str(value) for value in model.classes_]

            accuracy = float(
                accuracy_score(
                    test_target,
                    predicted_target,
                )
            )

            macro_f1 = float(
                f1_score(
                    test_target,
                    predicted_target,
                    labels=class_order,
                    average="macro",
                    zero_division=0,
                )
            )

            fold_result = ModelFoldResult(
                fold_id=fold_id,
                model_name=model_name,
                training_rows=len(training_features),
                test_rows=len(test_features),
                training_end_timestamp=(training_metadata.iloc[-1]["timestamp"].isoformat()),
                test_start_timestamp=(test_metadata.iloc[0]["timestamp"].isoformat()),
                accuracy=round(accuracy, 6),
                macro_f1=round(macro_f1, 6),
            )

            fold_rows.append(fold_result.to_dict())

            fold_predictions = test_metadata.copy()

            fold_predictions.insert(
                0,
                "model_name",
                model_name,
            )

            fold_predictions.insert(
                0,
                "fold_id",
                fold_id,
            )

            fold_predictions["actual_target"] = test_target.reset_index(drop=True)

            fold_predictions["predicted_target"] = predicted_target

            fold_predictions = _add_probabilities(
                dataframe=fold_predictions,
                probabilities=probabilities,
                model_classes=model_classes,
            )

            prediction_frames.append(fold_predictions)

        training_end += config.step_rows
        fold_id += 1

    if not fold_rows:
        raise WalkForwardComparisonError("Nessuna finestra Walk-Forward generata.")

    fold_dataframe = pd.DataFrame(fold_rows)

    predictions = pd.concat(
        prediction_frames,
        ignore_index=True,
    )

    model_summary: dict[str, dict[str, float]] = {}

    for model_name in fold_dataframe["model_name"].unique():
        model_folds = fold_dataframe[fold_dataframe["model_name"] == model_name]

        model_summary[str(model_name)] = {
            "mean_accuracy": round(
                float(model_folds["accuracy"].mean()),
                6,
            ),
            "minimum_accuracy": round(
                float(model_folds["accuracy"].min()),
                6,
            ),
            "maximum_accuracy": round(
                float(model_folds["accuracy"].max()),
                6,
            ),
            "mean_macro_f1": round(
                float(model_folds["macro_f1"].mean()),
                6,
            ),
            "minimum_macro_f1": round(
                float(model_folds["macro_f1"].min()),
                6,
            ),
            "maximum_macro_f1": round(
                float(model_folds["macro_f1"].max()),
                6,
            ),
        }

    best_model = max(
        model_summary,
        key=lambda name: (
            model_summary[name]["mean_macro_f1"],
            model_summary[name]["minimum_macro_f1"],
        ),
    )

    summary: dict[str, object] = {
        "comparison_type": "WALK_FORWARD_SAME_FOLDS",
        "fold_count_per_model": fold_id - 1,
        "models": model_summary,
        "best_model_by_mean_macro_f1": best_model,
        "shuffle_used": False,
        "same_folds_used": True,
        "training_window_expands": True,
        "gap_rows": config.gap_rows,
        "paper_trading_only": True,
    }

    return WalkForwardComparisonResult(
        fold_results=fold_dataframe,
        predictions=predictions,
        summary=summary,
    )
