"""Addestra e salva il primo modello ML baseline."""

# Importa json per salvare il report delle metriche.
import json

# Importa Path per gestire i percorsi dei file.
from pathlib import Path

# Importa joblib per salvare il modello addestrato.
import joblib

# Importa pandas per leggere i dataset Parquet.
import pandas as pd

# Importa accuracy e F1 per la baseline maggioritaria.
from sklearn.metrics import accuracy_score, f1_score

# Importa la struttura del dataset ML.
from src.models.dataset import MLDataset

# Importa configurazione e training della regressione logistica.
from src.models.logistic_baseline import (
    LogisticBaselineConfig,
    train_logistic_baseline,
)


def load_ml_dataset(
    features_path: Path,
    target_path: Path,
    metadata_path: Path,
) -> MLDataset:
    """Carica feature, target e metadati dai file Parquet."""

    # Verifica che tutti i file richiesti esistano.
    required_paths = [
        features_path,
        target_path,
        metadata_path,
    ]

    # Individua eventuali file mancanti.
    missing_paths = [str(path) for path in required_paths if not path.exists()]

    # Interrompe il training se manca almeno un file.
    if missing_paths:
        missing_text = ", ".join(missing_paths)

        raise FileNotFoundError(
            f"File ML mancanti: {missing_text}. Eseguire prima scripts.prepare_sample_ml_dataset."
        )

    # Carica la matrice delle feature.
    features = pd.read_parquet(
        features_path,
        engine="pyarrow",
    )

    # Carica il DataFrame contenente il target.
    target_dataframe = pd.read_parquet(
        target_path,
        engine="pyarrow",
    )

    # Verifica che il file target contenga la colonna prevista.
    if "target" not in target_dataframe.columns:
        raise ValueError("Il file del target non contiene la colonna 'target'.")

    # Estrae il target come Series.
    target = target_dataframe["target"].copy()
    target.name = "target"

    # Carica i metadati temporali.
    metadata = pd.read_parquet(
        metadata_path,
        engine="pyarrow",
    )

    # Verifica l'allineamento delle tre componenti.
    if not (len(features) == len(target) == len(metadata)):
        raise ValueError("Feature, target e metadati non hanno lo stesso numero di righe.")

    # Restituisce il dataset ML strutturato.
    return MLDataset(
        features=features,
        target=target,
        metadata=metadata,
    )


def calculate_majority_baseline(
    dataset: MLDataset,
    test_size_percentage: float,
) -> dict[str, object]:
    """Calcola una baseline che predice sempre la classe più frequente.

    La classe maggioritaria viene determinata esclusivamente sul
    training set, senza osservare il target del test set.
    """

    # Calcola l'indice dello split temporale.
    split_index = int(len(dataset.target) * (1.0 - test_size_percentage))

    # Estrae target di training e test.
    training_target = dataset.target.iloc[:split_index]
    test_target = dataset.target.iloc[split_index:]

    # Individua la classe più frequente solamente nel training.
    majority_class = training_target.value_counts().idxmax()

    # Crea una previsione costante sul test set.
    majority_predictions = pd.Series(
        [majority_class] * len(test_target),
        index=test_target.index,
        name="majority_prediction",
    )

    # Definisce l'ordine fisso delle classi.
    class_order = [
        "LONG",
        "SHORT",
        "NO_TRADE",
    ]

    # Restituisce le metriche della baseline maggioritaria.
    return {
        "baseline_type": "TRAINING_MAJORITY_CLASS",
        "majority_class": str(majority_class),
        "accuracy": round(
            float(
                accuracy_score(
                    test_target,
                    majority_predictions,
                )
            ),
            6,
        ),
        "macro_f1": round(
            float(
                f1_score(
                    test_target,
                    majority_predictions,
                    labels=class_order,
                    average="macro",
                    zero_division=0,
                )
            ),
            6,
        ),
        "training_only_used_to_select_class": True,
    }


def print_summary(
    model_metrics: dict[str, object],
    majority_metrics: dict[str, object],
    training_rows: int,
    test_rows: int,
    training_end_timestamp: str,
    test_start_timestamp: str,
) -> None:
    """Mostra un riepilogo del training nel terminale."""

    # Mostra le informazioni principali del modello.
    print("Training ML completato correttamente.")
    print("Modello: LOGISTIC REGRESSION")
    print("Dataset: SYNTHETIC DEMO")
    print(f"Righe training: {training_rows}")
    print(f"Righe test: {test_rows}")
    print(f"Fine training: {training_end_timestamp}")
    print(f"Inizio test: {test_start_timestamp}")
    print("")

    # Mostra le metriche del modello.
    print("Regressione logistica:")
    print(f"Accuracy: {model_metrics['accuracy']}")
    print(f"Macro F1: {model_metrics['macro_f1']}")
    print("")

    # Mostra le metriche della baseline maggioritaria.
    print("Baseline maggioritaria:")
    print(f"Classe maggioritaria del training: {majority_metrics['majority_class']}")
    print(f"Accuracy: {majority_metrics['accuracy']}")
    print(f"Macro F1: {majority_metrics['macro_f1']}")


def main() -> None:
    """Carica il dataset, addestra il modello e salva gli artefatti."""

    # Definisce i file di input.
    features_path = Path("data/features/sample_ml_features.parquet")
    target_path = Path("data/features/sample_ml_target.parquet")
    metadata_path = Path("data/features/sample_ml_metadata.parquet")

    # Definisce i file di output.
    model_path = Path("models/logistic_baseline_0.1.0.joblib")
    predictions_path = Path("reports/logistic_baseline_predictions.csv")
    metrics_path = Path("reports/logistic_baseline_metrics.json")

    # Carica le tre componenti del dataset.
    dataset = load_ml_dataset(
        features_path=features_path,
        target_path=target_path,
        metadata_path=metadata_path,
    )

    # Configura la regressione logistica.
    model_config = LogisticBaselineConfig(
        test_size_percentage=0.20,
        maximum_iterations=1000,
        random_state=42,
        class_weight="balanced",
    )

    # Addestra e valuta il modello.
    result = train_logistic_baseline(
        dataset=dataset,
        config=model_config,
    )

    # Calcola la baseline maggioritaria senza utilizzare il test
    # per scegliere la classe predetta.
    majority_metrics = calculate_majority_baseline(
        dataset=dataset,
        test_size_percentage=model_config.test_size_percentage,
    )

    # Costruisce il report finale.
    final_metrics: dict[str, object] = {
        "model_version": "logistic_baseline_0.1.0",
        "dataset_type": "SYNTHETIC_DEMO",
        "training_rows": result.training_rows,
        "test_rows": result.test_rows,
        "training_end_timestamp": result.training_end_timestamp,
        "test_start_timestamp": result.test_start_timestamp,
        "logistic_regression": result.metrics,
        "majority_baseline": majority_metrics,
        "model_accuracy_above_majority": (
            float(result.metrics["accuracy"]) > float(majority_metrics["accuracy"])
        ),
        "model_macro_f1_above_majority": (
            float(result.metrics["macro_f1"]) > float(majority_metrics["macro_f1"])
        ),
        "real_trading_enabled": False,
        "paper_trading_only": True,
    }

    # Crea le cartelle degli artefatti.
    model_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    predictions_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Salva la pipeline completa con scaler e classificatore.
    joblib.dump(
        result.model,
        model_path,
    )

    # Salva predizioni e probabilità del test set.
    result.predictions.to_csv(
        predictions_path,
        index=False,
    )

    # Salva il report delle metriche.
    metrics_path.write_text(
        json.dumps(
            final_metrics,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Mostra il riepilogo nel terminale.
    print_summary(
        model_metrics=result.metrics,
        majority_metrics=majority_metrics,
        training_rows=result.training_rows,
        test_rows=result.test_rows,
        training_end_timestamp=result.training_end_timestamp,
        test_start_timestamp=result.test_start_timestamp,
    )

    # Mostra i file generati.
    print("")
    print(f"Modello: {model_path.resolve()}")
    print(f"Predizioni: {predictions_path.resolve()}")
    print(f"Metriche: {metrics_path.resolve()}")


if __name__ == "__main__":
    # Avvia il training solamente quando eseguito direttamente.
    main()
