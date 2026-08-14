"""Modello Gradient Boosting per classificazione temporale."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.utils.class_weight import compute_sample_weight

from src.models.dataset import MLDataset


class GradientBoostingError(ValueError):
    """Errore generato durante training o valutazione del modello."""


@dataclass(frozen=True)
class GradientBoostingConfig:
    """Configurazione del modello Gradient Boosting."""

    # Percentuale finale del dataset utilizzata per il test.
    test_size_percentage: float = 0.20

    # Numero massimo di iterazioni di boosting.
    maximum_iterations: int = 200

    # Learning rate del modello.
    learning_rate: float = 0.05

    # Numero massimo di foglie per ogni albero.
    maximum_leaf_nodes: int = 15

    # Numero minimo di campioni richiesti in una foglia.
    minimum_samples_leaf: int = 10

    # Regolarizzazione L2.
    l2_regularization: float = 1.0

    # Seed per la riproducibilità.
    random_state: int = 42

    # Abilita il bilanciamento delle classi sul training set.
    balance_classes: bool = True


@dataclass(frozen=True)
class GradientBoostingResult:
    """Risultato del training Gradient Boosting."""

    # Modello addestrato.
    model: HistGradientBoostingClassifier

    # Metriche calcolate sul test temporale.
    metrics: dict[str, object]

    # Predizioni e probabilità del test set.
    predictions: pd.DataFrame

    # Numero di righe di training.
    training_rows: int

    # Numero di righe di test.
    test_rows: int

    # Ultimo timestamp del training.
    training_end_timestamp: str

    # Primo timestamp del test.
    test_start_timestamp: str


def _validate_config(
    config: GradientBoostingConfig,
) -> None:
    """Verifica la configurazione del modello."""

    if not 0.0 < config.test_size_percentage < 1.0:
        raise GradientBoostingError(
            "La percentuale del test set deve essere compresa tra zero e uno."
        )

    if config.maximum_iterations <= 0:
        raise GradientBoostingError("Il numero massimo di iterazioni deve essere maggiore di zero.")

    if config.learning_rate <= 0:
        raise GradientBoostingError("Il learning rate deve essere maggiore di zero.")

    if config.maximum_leaf_nodes < 2:
        raise GradientBoostingError("Il numero massimo di foglie deve essere almeno due.")

    if config.minimum_samples_leaf <= 0:
        raise GradientBoostingError(
            "Il numero minimo di campioni per foglia deve essere maggiore di zero."
        )

    if config.l2_regularization < 0:
        raise GradientBoostingError("La regolarizzazione L2 non può essere negativa.")


def _validate_dataset(dataset: MLDataset) -> None:
    """Verifica struttura e ordine temporale del dataset."""

    if not (len(dataset.features) == len(dataset.target) == len(dataset.metadata)):
        raise GradientBoostingError("Feature, target e metadati non sono allineati.")

    if len(dataset.features) < 10:
        raise GradientBoostingError("Il dataset ML deve contenere almeno dieci righe.")

    if dataset.features.isna().any().any():
        raise GradientBoostingError("Le feature contengono valori mancanti.")

    if dataset.target.isna().any():
        raise GradientBoostingError("Il target contiene valori mancanti.")

    if "timestamp" not in dataset.metadata.columns:
        raise GradientBoostingError("I metadati non contengono la colonna timestamp.")

    if not dataset.metadata["timestamp"].is_monotonic_increasing:
        raise GradientBoostingError("I timestamp del dataset non sono ordinati.")

    if dataset.metadata["timestamp"].duplicated().any():
        raise GradientBoostingError("Il dataset contiene timestamp duplicati.")

    allowed_classes = {
        "LONG",
        "SHORT",
        "NO_TRADE",
    }

    invalid_classes = sorted(set(dataset.target).difference(allowed_classes))

    if invalid_classes:
        invalid_text = ", ".join(invalid_classes)

        raise GradientBoostingError(f"Classi target non supportate: {invalid_text}.")


def _add_probability_columns(
    predictions: pd.DataFrame,
    probabilities: np.ndarray,
    model_classes: list[str],
) -> pd.DataFrame:
    """Aggiunge una probabilità per ogni classe supportata."""

    result = predictions.copy()

    for class_name in [
        "LONG",
        "SHORT",
        "NO_TRADE",
    ]:
        probability_column = f"probability_{class_name.lower()}"

        if class_name not in model_classes:
            result[probability_column] = 0.0
            continue

        class_index = model_classes.index(class_name)

        result[probability_column] = probabilities[
            :,
            class_index,
        ]

    result["prediction_confidence"] = result[
        [
            "probability_long",
            "probability_short",
            "probability_no_trade",
        ]
    ].max(axis=1)

    return result


def train_gradient_boosting(
    dataset: MLDataset,
    config: GradientBoostingConfig | None = None,
) -> GradientBoostingResult:
    """Addestra e valuta il Gradient Boosting con split temporale."""

    selected_config = config or GradientBoostingConfig()

    _validate_config(selected_config)
    _validate_dataset(dataset)

    # Calcola il punto di separazione senza shuffle.
    split_index = int(len(dataset.features) * (1.0 - selected_config.test_size_percentage))

    if split_index <= 0 or split_index >= len(dataset.features):
        raise GradientBoostingError("Lo split temporale produce un training o test set vuoto.")

    # Estrae training e test mantenendo l'ordine cronologico.
    training_features = dataset.features.iloc[:split_index].copy()

    test_features = dataset.features.iloc[split_index:].copy()

    training_target = dataset.target.iloc[:split_index].copy()

    test_target = dataset.target.iloc[split_index:].copy()

    training_metadata = dataset.metadata.iloc[:split_index].copy()

    test_metadata = dataset.metadata.iloc[split_index:].copy()

    # Il training deve contenere almeno due classi.
    training_classes = sorted(str(value) for value in training_target.unique())

    if len(training_classes) < 2:
        raise GradientBoostingError("Il training set deve contenere almeno due classi.")

    # Verifica la separazione temporale.
    training_end_timestamp = training_metadata.iloc[-1]["timestamp"]

    test_start_timestamp = test_metadata.iloc[0]["timestamp"]

    if training_end_timestamp >= test_start_timestamp:
        raise GradientBoostingError(
            "Il test set non è cronologicamente successivo al training set."
        )

    # Crea il modello.
    model = HistGradientBoostingClassifier(
        max_iter=selected_config.maximum_iterations,
        learning_rate=selected_config.learning_rate,
        max_leaf_nodes=selected_config.maximum_leaf_nodes,
        min_samples_leaf=selected_config.minimum_samples_leaf,
        l2_regularization=selected_config.l2_regularization,
        random_state=selected_config.random_state,
        early_stopping=False,
    )

    # Calcola pesi usando esclusivamente il target di training.
    sample_weight = None

    if selected_config.balance_classes:
        sample_weight = compute_sample_weight(
            class_weight="balanced",
            y=training_target,
        )

    # Addestra il modello solamente sul training set.
    model.fit(
        training_features,
        training_target,
        sample_weight=sample_weight,
    )

    # Genera previsioni e probabilità sul test set.
    predicted_target = model.predict(test_features)

    predicted_probabilities = model.predict_proba(test_features)

    model_classes = [str(class_name) for class_name in model.classes_]

    # Costruisce il registro delle predizioni.
    predictions = test_metadata.reset_index(drop=True).copy()

    predictions["actual_target"] = test_target.reset_index(drop=True)

    predictions["predicted_target"] = predicted_target

    predictions = _add_probability_columns(
        predictions=predictions,
        probabilities=predicted_probabilities,
        model_classes=model_classes,
    )

    # Definisce l'ordine fisso delle classi.
    class_order = [
        "LONG",
        "SHORT",
        "NO_TRADE",
    ]

    # Calcola le metriche.
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

    detailed_report = classification_report(
        test_target,
        predicted_target,
        labels=class_order,
        output_dict=True,
        zero_division=0,
    )

    confusion_matrix_values = confusion_matrix(
        test_target,
        predicted_target,
        labels=class_order,
    ).tolist()

    metrics: dict[str, object] = {
        "model_type": "HIST_GRADIENT_BOOSTING",
        "training_rows": len(training_features),
        "test_rows": len(test_features),
        "feature_count": len(training_features.columns),
        "training_classes": training_classes,
        "accuracy": round(accuracy, 6),
        "macro_f1": round(macro_f1, 6),
        "confusion_matrix_labels": class_order,
        "confusion_matrix": confusion_matrix_values,
        "classification_report": detailed_report,
        "shuffle_used": False,
        "class_weights_computed_on_training_only": (selected_config.balance_classes),
        "test_is_chronologically_after_training": True,
    }

    return GradientBoostingResult(
        model=model,
        metrics=metrics,
        predictions=predictions,
        training_rows=len(training_features),
        test_rows=len(test_features),
        training_end_timestamp=(training_end_timestamp.isoformat()),
        test_start_timestamp=(test_start_timestamp.isoformat()),
    )
