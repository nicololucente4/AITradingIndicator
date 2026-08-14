"""Walk-forward validation per modelli di classificazione temporale."""

# Importa dataclass per rappresentare configurazione e risultati.
from dataclasses import asdict, dataclass

# Importa NumPy per gestire le probabilità delle classi.
import numpy as np

# Importa pandas per elaborare dataset e predizioni.
import pandas as pd

# Importa la regressione logistica.
from sklearn.linear_model import LogisticRegression

# Importa le metriche di classificazione.
from sklearn.metrics import accuracy_score, f1_score

# Importa Pipeline per unire scaler e classificatore.
from sklearn.pipeline import Pipeline

# Importa StandardScaler per normalizzare le feature.
from sklearn.preprocessing import StandardScaler

# Importa la struttura del dataset ML.
from src.models.dataset import MLDataset


class WalkForwardError(ValueError):
    """Errore generato durante la Walk-Forward Validation."""


@dataclass(frozen=True)
class WalkForwardConfig:
    """Configurazione della Walk-Forward Validation."""

    # Numero iniziale di righe usate per il primo training.
    initial_training_rows: int = 200

    # Numero di righe presenti in ogni finestra di test.
    test_rows: int = 40

    # Numero di righe di avanzamento tra una finestra e la successiva.
    step_rows: int = 40

    # Numero di righe escluse tra training e test.
    gap_rows: int = 0

    # Numero massimo di iterazioni della regressione logistica.
    maximum_iterations: int = 1000

    # Seed utilizzato per rendere il modello riproducibile.
    random_state: int = 42

    # Bilanciamento automatico delle classi.
    class_weight: str | None = "balanced"


@dataclass(frozen=True)
class WalkForwardFoldReport:
    """Metriche e confini temporali di una singola finestra."""

    # Identificativo progressivo della finestra.
    fold_id: int

    # Numero di righe utilizzate per il training.
    training_rows: int

    # Numero di righe utilizzate per il test.
    test_rows: int

    # Primo timestamp del training.
    training_start_timestamp: str

    # Ultimo timestamp del training.
    training_end_timestamp: str

    # Primo timestamp del test.
    test_start_timestamp: str

    # Ultimo timestamp del test.
    test_end_timestamp: str

    # Accuracy della finestra.
    accuracy: float

    # F1 macro della finestra.
    macro_f1: float

    # Classi presenti nel training.
    training_classes: list[str]

    def to_dict(self) -> dict[str, object]:
        """Converte il report della finestra in un dizionario."""

        # Converte automaticamente tutti i campi.
        return asdict(self)


@dataclass(frozen=True)
class WalkForwardResult:
    """Risultato complessivo della Walk-Forward Validation."""

    # Report delle singole finestre.
    fold_reports: list[WalkForwardFoldReport]

    # Predizioni aggregate di tutte le finestre.
    predictions: pd.DataFrame

    # Metriche aggregate.
    metrics: dict[str, object]


def _validate_config(config: WalkForwardConfig) -> None:
    """Verifica la configurazione Walk-Forward."""

    # Il training iniziale deve contenere almeno dieci righe.
    if config.initial_training_rows < 10:
        raise WalkForwardError("Il training iniziale deve contenere almeno dieci righe.")

    # Ogni finestra di test deve contenere almeno una riga.
    if config.test_rows <= 0:
        raise WalkForwardError("La finestra di test deve contenere almeno una riga.")

    # L'avanzamento deve essere positivo.
    if config.step_rows <= 0:
        raise WalkForwardError("L'avanzamento Walk-Forward deve essere maggiore di zero.")

    # Il gap non può essere negativo.
    if config.gap_rows < 0:
        raise WalkForwardError("Il gap tra training e test non può essere negativo.")

    # Il numero massimo di iterazioni deve essere positivo.
    if config.maximum_iterations <= 0:
        raise WalkForwardError("Il numero massimo di iterazioni deve essere maggiore di zero.")

    # Verifica i valori supportati per class_weight.
    if config.class_weight not in {None, "balanced"}:
        raise WalkForwardError("class_weight deve essere None oppure 'balanced'.")


def _validate_dataset(dataset: MLDataset) -> None:
    """Verifica struttura, allineamento e ordine temporale."""

    # Le tre componenti devono avere la stessa lunghezza.
    if not (len(dataset.features) == len(dataset.target) == len(dataset.metadata)):
        raise WalkForwardError("Feature, target e metadati non sono allineati.")

    # Il dataset non può essere vuoto.
    if dataset.features.empty:
        raise WalkForwardError("Il dataset Walk-Forward è vuoto.")

    # Le feature non possono contenere valori mancanti.
    if dataset.features.isna().any().any():
        raise WalkForwardError("Le feature contengono valori mancanti.")

    # Il target non può contenere valori mancanti.
    if dataset.target.isna().any():
        raise WalkForwardError("Il target contiene valori mancanti.")

    # I metadati devono contenere il timestamp.
    if "timestamp" not in dataset.metadata.columns:
        raise WalkForwardError("I metadati non contengono la colonna timestamp.")

    # I timestamp devono essere ordinati cronologicamente.
    if not dataset.metadata["timestamp"].is_monotonic_increasing:
        raise WalkForwardError("I timestamp del dataset non sono ordinati.")

    # I timestamp non possono essere duplicati.
    if dataset.metadata["timestamp"].duplicated().any():
        raise WalkForwardError("Il dataset contiene timestamp duplicati.")


def _create_model(
    config: WalkForwardConfig,
) -> Pipeline:
    """Crea una nuova pipeline indipendente per ogni finestra."""

    # Restituisce scaler e classificatore non ancora addestrati.
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


def _add_probability_columns(
    predictions: pd.DataFrame,
    probabilities: np.ndarray,
    model_classes: list[str],
) -> pd.DataFrame:
    """Aggiunge le probabilità LONG, SHORT e NO_TRADE."""

    # Crea una copia per non modificare l'input.
    result = predictions.copy()

    # Analizza ogni classe prevista dal progetto.
    for class_name in [
        "LONG",
        "SHORT",
        "NO_TRADE",
    ]:
        # Definisce il nome della colonna.
        probability_column = f"probability_{class_name.lower()}"

        # Se la classe non è presente nel training, assegna probabilità zero.
        if class_name not in model_classes:
            result[probability_column] = 0.0
            continue

        # Individua la posizione della classe.
        class_index = model_classes.index(class_name)

        # Copia le probabilità del modello.
        result[probability_column] = probabilities[:, class_index]

    # Calcola la confidenza massima.
    result["prediction_confidence"] = result[
        [
            "probability_long",
            "probability_short",
            "probability_no_trade",
        ]
    ].max(axis=1)

    # Restituisce il risultato completo.
    return result


def run_walk_forward(
    dataset: MLDataset,
    config: WalkForwardConfig | None = None,
) -> WalkForwardResult:
    """Esegue una Walk-Forward Validation con training espandibile.

    La prima finestra usa le righe iniziali per il training. A ogni
    iterazione il training si espande e il test avanza nel futuro.

    Args:
        dataset: Dataset Machine Learning ordinato temporalmente.
        config: Configurazione facoltativa Walk-Forward.

    Returns:
        Report delle finestre, predizioni e metriche aggregate.
    """

    # Usa la configurazione predefinita se non specificata.
    selected_config = config or WalkForwardConfig()

    # Valida configurazione e dataset.
    _validate_config(selected_config)
    _validate_dataset(dataset)

    # Verifica che esista spazio per training, gap e primo test.
    minimum_required_rows = (
        selected_config.initial_training_rows + selected_config.gap_rows + selected_config.test_rows
    )

    if len(dataset.features) < minimum_required_rows:
        raise WalkForwardError(
            "Il dataset non contiene righe sufficienti per la prima finestra Walk-Forward."
        )

    # Conterrà i report delle singole finestre.
    fold_reports: list[WalkForwardFoldReport] = []

    # Conterrà le predizioni di tutte le finestre.
    prediction_frames: list[pd.DataFrame] = []

    # Definisce l'ordine fisso delle classi.
    class_order = [
        "LONG",
        "SHORT",
        "NO_TRADE",
    ]

    # Il training parte dalla prima riga e si espande.
    training_end = selected_config.initial_training_rows

    # Identificativo della prima finestra.
    fold_id = 1

    # Continua finché esiste una finestra di test completa.
    while True:
        # Il test inizia dopo l'eventuale gap.
        test_start = training_end + selected_config.gap_rows

        # Calcola la fine esclusiva del test.
        test_end = test_start + selected_config.test_rows

        # Interrompe se il test completo supera il dataset.
        if test_end > len(dataset.features):
            break

        # Estrae il training espandibile.
        training_features = dataset.features.iloc[:training_end].copy()

        training_target = dataset.target.iloc[:training_end].copy()

        training_metadata = dataset.metadata.iloc[:training_end].copy()

        # Estrae la finestra di test successiva.
        test_features = dataset.features.iloc[test_start:test_end].copy()

        test_target = dataset.target.iloc[test_start:test_end].copy()

        test_metadata = dataset.metadata.iloc[test_start:test_end].copy()

        # Il training deve contenere almeno due classi.
        training_classes = sorted(str(value) for value in training_target.unique())

        if len(training_classes) < 2:
            raise WalkForwardError(
                f"La finestra {fold_id} contiene meno di due classi nel training."
            )

        # Verifica che il test sia temporalmente successivo al training.
        if training_metadata.iloc[-1]["timestamp"] >= test_metadata.iloc[0]["timestamp"]:
            raise WalkForwardError(f"La finestra {fold_id} presenta sovrapposizione temporale.")

        # Crea un nuovo modello indipendente per la finestra.
        model = _create_model(selected_config)

        # Addestra scaler e classificatore solamente sul training.
        model.fit(
            training_features,
            training_target,
        )

        # Genera le predizioni del test.
        predicted_target = model.predict(test_features)

        # Genera le probabilità delle classi.
        predicted_probabilities = model.predict_proba(test_features)

        # Recupera l'ordine delle classi del modello.
        classifier = model.named_steps["classifier"]
        model_classes = [str(class_name) for class_name in classifier.classes_]

        # Costruisce il registro della finestra.
        fold_predictions = test_metadata.reset_index(drop=True).copy()

        # Aggiunge identificativo e confini della finestra.
        fold_predictions.insert(
            loc=0,
            column="fold_id",
            value=fold_id,
        )

        # Aggiunge target reale e previsto.
        fold_predictions["actual_target"] = test_target.reset_index(drop=True)

        fold_predictions["predicted_target"] = predicted_target

        # Aggiunge le probabilità.
        fold_predictions = _add_probability_columns(
            predictions=fold_predictions,
            probabilities=predicted_probabilities,
            model_classes=model_classes,
        )

        # Conserva le predizioni della finestra.
        prediction_frames.append(fold_predictions)

        # Calcola le metriche della finestra.
        fold_accuracy = float(
            accuracy_score(
                test_target,
                predicted_target,
            )
        )

        fold_macro_f1 = float(
            f1_score(
                test_target,
                predicted_target,
                labels=class_order,
                average="macro",
                zero_division=0,
            )
        )

        # Crea il report della finestra.
        fold_reports.append(
            WalkForwardFoldReport(
                fold_id=fold_id,
                training_rows=len(training_features),
                test_rows=len(test_features),
                training_start_timestamp=training_metadata.iloc[0]["timestamp"].isoformat(),
                training_end_timestamp=training_metadata.iloc[-1]["timestamp"].isoformat(),
                test_start_timestamp=test_metadata.iloc[0]["timestamp"].isoformat(),
                test_end_timestamp=test_metadata.iloc[-1]["timestamp"].isoformat(),
                accuracy=round(
                    fold_accuracy,
                    6,
                ),
                macro_f1=round(
                    fold_macro_f1,
                    6,
                ),
                training_classes=training_classes,
            )
        )

        # Espande il training per la finestra successiva.
        training_end += selected_config.step_rows

        # Incrementa l'identificativo della finestra.
        fold_id += 1

    # Verifica che almeno una finestra sia stata completata.
    if not fold_reports:
        raise WalkForwardError("Nessuna finestra Walk-Forward è stata generata.")

    # Unisce le predizioni di tutte le finestre.
    all_predictions = pd.concat(
        prediction_frames,
        ignore_index=True,
    )

    # Calcola le metriche aggregate su tutte le predizioni.
    aggregate_accuracy = float(
        accuracy_score(
            all_predictions["actual_target"],
            all_predictions["predicted_target"],
        )
    )

    aggregate_macro_f1 = float(
        f1_score(
            all_predictions["actual_target"],
            all_predictions["predicted_target"],
            labels=class_order,
            average="macro",
            zero_division=0,
        )
    )

    # Calcola media e variabilità delle finestre.
    fold_accuracy_values = [report.accuracy for report in fold_reports]

    fold_macro_f1_values = [report.macro_f1 for report in fold_reports]

    # Costruisce le metriche complessive.
    metrics: dict[str, object] = {
        "validation_type": "EXPANDING_WALK_FORWARD",
        "fold_count": len(fold_reports),
        "total_predictions": len(all_predictions),
        "aggregate_accuracy": round(
            aggregate_accuracy,
            6,
        ),
        "aggregate_macro_f1": round(
            aggregate_macro_f1,
            6,
        ),
        "mean_fold_accuracy": round(
            float(np.mean(fold_accuracy_values)),
            6,
        ),
        "minimum_fold_accuracy": round(
            float(np.min(fold_accuracy_values)),
            6,
        ),
        "maximum_fold_accuracy": round(
            float(np.max(fold_accuracy_values)),
            6,
        ),
        "mean_fold_macro_f1": round(
            float(np.mean(fold_macro_f1_values)),
            6,
        ),
        "minimum_fold_macro_f1": round(
            float(np.min(fold_macro_f1_values)),
            6,
        ),
        "maximum_fold_macro_f1": round(
            float(np.max(fold_macro_f1_values)),
            6,
        ),
        "shuffle_used": False,
        "training_window_expands": True,
        "scaler_refitted_on_each_training_window": True,
        "future_data_used_for_training": False,
        "gap_rows": selected_config.gap_rows,
    }

    # Restituisce il risultato completo.
    return WalkForwardResult(
        fold_reports=fold_reports,
        predictions=all_predictions,
        metrics=metrics,
    )
