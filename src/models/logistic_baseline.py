"""Modello ML baseline basato su regressione logistica."""

# Importa dataclass per rappresentare configurazione e risultato.
from dataclasses import dataclass

# Importa NumPy per identificare gli indici delle classi.
import numpy as np

# Importa pandas per gestire feature, target e predizioni.
import pandas as pd

# Importa la regressione logistica.
from sklearn.linear_model import LogisticRegression

# Importa le metriche di classificazione.
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)

# Importa Pipeline per unire scaling e modello.
from sklearn.pipeline import Pipeline

# Importa StandardScaler per normalizzare le feature.
from sklearn.preprocessing import StandardScaler

# Importa la struttura del dataset ML.
from src.models.dataset import MLDataset


class LogisticBaselineError(ValueError):
    """Errore generato durante training o valutazione del modello."""


@dataclass(frozen=True)
class LogisticBaselineConfig:
    """Configurazione del modello di regressione logistica."""

    # Percentuale finale del dataset utilizzata come test.
    test_size_percentage: float = 0.20

    # Numero massimo di iterazioni del modello.
    maximum_iterations: int = 1000

    # Seed utilizzato per rendere il training riproducibile.
    random_state: int = 42

    # Strategia di bilanciamento delle classi.
    class_weight: str | None = "balanced"


@dataclass(frozen=True)
class LogisticBaselineResult:
    """Risultato del training e della valutazione."""

    # Pipeline addestrata contenente scaler e modello.
    model: Pipeline

    # Metriche principali sul test temporale.
    metrics: dict[str, object]

    # Predizioni e probabilità del test set.
    predictions: pd.DataFrame

    # Numero di righe usate per il training.
    training_rows: int

    # Numero di righe usate per il test.
    test_rows: int

    # Timestamp finale del training set.
    training_end_timestamp: str

    # Timestamp iniziale del test set.
    test_start_timestamp: str


def _validate_config(config: LogisticBaselineConfig) -> None:
    """Verifica la configurazione del modello."""

    # Il test deve rappresentare una parte compresa tra 0 e 100%.
    if not 0.0 < config.test_size_percentage < 1.0:
        raise LogisticBaselineError(
            "La percentuale del test set deve essere compresa tra zero e uno."
        )

    # Il numero massimo di iterazioni deve essere positivo.
    if config.maximum_iterations <= 0:
        raise LogisticBaselineError("Il numero massimo di iterazioni deve essere maggiore di zero.")

    # Sono supportati solamente nessun peso oppure bilanciamento automatico.
    if config.class_weight not in {None, "balanced"}:
        raise LogisticBaselineError("class_weight deve essere None oppure 'balanced'.")


def _validate_dataset(dataset: MLDataset) -> None:
    """Verifica che feature, target e metadati siano allineati."""

    # Le tre componenti devono avere la stessa lunghezza.
    if not (len(dataset.features) == len(dataset.target) == len(dataset.metadata)):
        raise LogisticBaselineError("Feature, target e metadati non sono allineati.")

    # Il dataset deve contenere abbastanza righe.
    if len(dataset.features) < 10:
        raise LogisticBaselineError("Il dataset ML deve contenere almeno dieci righe.")

    # Le feature non possono contenere valori mancanti.
    if dataset.features.isna().any().any():
        raise LogisticBaselineError("Le feature contengono valori mancanti.")

    # Il target non può contenere valori mancanti.
    if dataset.target.isna().any():
        raise LogisticBaselineError("Il target contiene valori mancanti.")

    # I timestamp devono essere presenti nei metadati.
    if "timestamp" not in dataset.metadata.columns:
        raise LogisticBaselineError("I metadati non contengono la colonna timestamp.")

    # I timestamp devono essere ordinati cronologicamente.
    if not dataset.metadata["timestamp"].is_monotonic_increasing:
        raise LogisticBaselineError("I timestamp del dataset ML non sono ordinati.")

    # Definisce le classi ammesse.
    allowed_classes = {
        "LONG",
        "SHORT",
        "NO_TRADE",
    }

    # Verifica che non esistano classi sconosciute.
    invalid_classes = sorted(set(dataset.target).difference(allowed_classes))

    if invalid_classes:
        invalid_text = ", ".join(invalid_classes)

        raise LogisticBaselineError(f"Classi target non supportate: {invalid_text}.")


def _create_temporal_split(
    dataset: MLDataset,
    test_size_percentage: float,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.Series,
    pd.Series,
    pd.DataFrame,
    pd.DataFrame,
]:
    """Divide il dataset mantenendo rigorosamente l'ordine temporale."""

    # Calcola il primo indice del test set.
    split_index = int(len(dataset.features) * (1.0 - test_size_percentage))

    # Impedisce la creazione di un training o test set vuoto.
    if split_index <= 0 or split_index >= len(dataset.features):
        raise LogisticBaselineError("Lo split temporale produce un training o test set vuoto.")

    # Separa le feature senza rimescolare le righe.
    training_features = dataset.features.iloc[:split_index].copy()
    test_features = dataset.features.iloc[split_index:].copy()

    # Separa il target con lo stesso indice temporale.
    training_target = dataset.target.iloc[:split_index].copy()
    test_target = dataset.target.iloc[split_index:].copy()

    # Separa anche i metadati.
    training_metadata = dataset.metadata.iloc[:split_index].copy()
    test_metadata = dataset.metadata.iloc[split_index:].copy()

    # Restituisce le componenti dello split.
    return (
        training_features,
        test_features,
        training_target,
        test_target,
        training_metadata,
        test_metadata,
    )


def train_logistic_baseline(
    dataset: MLDataset,
    config: LogisticBaselineConfig | None = None,
) -> LogisticBaselineResult:
    """Addestra e valuta una regressione logistica temporalmente separata.

    Il modello utilizza la parte iniziale del dataset per il training
    e la parte finale per il test. Non viene effettuato alcuno shuffle.

    Args:
        dataset: Dataset ML con feature, target e metadati separati.
        config: Configurazione facoltativa del modello.

    Returns:
        Modello addestrato, metriche e predizioni sul test set.
    """

    # Usa la configurazione predefinita se non specificata.
    selected_config = config or LogisticBaselineConfig()

    # Valida configurazione e dataset.
    _validate_config(selected_config)
    _validate_dataset(dataset)

    # Crea lo split cronologico.
    (
        training_features,
        test_features,
        training_target,
        test_target,
        training_metadata,
        test_metadata,
    ) = _create_temporal_split(
        dataset=dataset,
        test_size_percentage=selected_config.test_size_percentage,
    )

    # Verifica che il training contenga almeno due classi.
    training_classes = sorted(training_target.unique())

    if len(training_classes) < 2:
        raise LogisticBaselineError("Il training set deve contenere almeno due classi.")

    # Crea una pipeline che applica lo scaling solamente
    # dopo lo split e quindi esclusivamente sul training set.
    model = Pipeline(
        steps=[
            (
                "scaler",
                StandardScaler(),
            ),
            (
                "classifier",
                LogisticRegression(
                    max_iter=selected_config.maximum_iterations,
                    random_state=selected_config.random_state,
                    class_weight=selected_config.class_weight,
                ),
            ),
        ]
    )

    # Addestra scaler e classificatore solamente sul training set.
    model.fit(
        training_features,
        training_target,
    )

    # Genera le classi previste per il test set.
    predicted_target = model.predict(test_features)

    # Genera le probabilità associate a ogni classe.
    predicted_probabilities = model.predict_proba(test_features)

    # Recupera l'ordine delle classi usato dal classificatore.
    classifier = model.named_steps["classifier"]
    model_classes = list(classifier.classes_)

    # Crea il registro delle predizioni.
    predictions = test_metadata.reset_index(drop=True).copy()

    # Aggiunge target reale e previsto.
    predictions["actual_target"] = test_target.reset_index(drop=True)
    predictions["predicted_target"] = predicted_target

    # Aggiunge una colonna probabilità per ogni classe disponibile.
    for class_name in [
        "LONG",
        "SHORT",
        "NO_TRADE",
    ]:
        probability_column = f"probability_{class_name.lower()}"

        # Imposta zero se la classe non era presente nel training.
        if class_name not in model_classes:
            predictions[probability_column] = 0.0
            continue

        # Individua la posizione della classe nel risultato predict_proba.
        class_index = int(np.where(np.asarray(model_classes) == class_name)[0][0])

        # Salva la probabilità della classe.
        predictions[probability_column] = predicted_probabilities[:, class_index]

    # Calcola la probabilità massima della previsione.
    predictions["prediction_confidence"] = predictions[
        [
            "probability_long",
            "probability_short",
            "probability_no_trade",
        ]
    ].max(axis=1)

    # Costruisce la matrice di confusione usando un ordine fisso.
    class_order = [
        "LONG",
        "SHORT",
        "NO_TRADE",
    ]

    confusion_matrix_values = confusion_matrix(
        test_target,
        predicted_target,
        labels=class_order,
    ).tolist()

    # Genera il report dettagliato per classe.
    detailed_report = classification_report(
        test_target,
        predicted_target,
        labels=class_order,
        output_dict=True,
        zero_division=0,
    )

    # Costruisce il dizionario delle metriche.
    metrics: dict[str, object] = {
        "model_type": "LOGISTIC_REGRESSION",
        "training_rows": len(training_features),
        "test_rows": len(test_features),
        "feature_count": len(training_features.columns),
        "training_classes": training_classes,
        "accuracy": round(
            float(
                accuracy_score(
                    test_target,
                    predicted_target,
                )
            ),
            6,
        ),
        "macro_f1": round(
            float(
                f1_score(
                    test_target,
                    predicted_target,
                    labels=class_order,
                    average="macro",
                    zero_division=0,
                )
            ),
            6,
        ),
        "confusion_matrix_labels": class_order,
        "confusion_matrix": confusion_matrix_values,
        "classification_report": detailed_report,
        "shuffle_used": False,
        "scaler_fitted_on_training_only": True,
        "test_is_chronologically_after_training": True,
    }

    # Recupera i confini temporali dello split.
    training_end_timestamp = training_metadata.iloc[-1]["timestamp"].isoformat()

    test_start_timestamp = test_metadata.iloc[0]["timestamp"].isoformat()

    # Verifica difensiva dell'ordine temporale.
    if training_metadata.iloc[-1]["timestamp"] >= test_metadata.iloc[0]["timestamp"]:
        raise LogisticBaselineError(
            "Il test set non è cronologicamente successivo al training set."
        )

    # Restituisce il risultato completo.
    return LogisticBaselineResult(
        model=model,
        metrics=metrics,
        predictions=predictions,
        training_rows=len(training_features),
        test_rows=len(test_features),
        training_end_timestamp=training_end_timestamp,
        test_start_timestamp=test_start_timestamp,
    )
