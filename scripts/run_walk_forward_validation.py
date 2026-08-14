"""Esegue la Walk-Forward Validation sul dataset ML dimostrativo."""

# Importa json per salvare il report riassuntivo.
import json

# Importa Path per gestire i percorsi dei file.
from pathlib import Path

# Importa pandas per leggere e salvare i dataset.
import pandas as pd

# Importa la struttura del dataset Machine Learning.
from src.models.dataset import MLDataset

# Importa configurazione e training con singolo split temporale.
from src.models.logistic_baseline import (
    LogisticBaselineConfig,
    train_logistic_baseline,
)

# Importa configurazione e motore Walk-Forward.
from src.models.walk_forward import (
    WalkForwardConfig,
    run_walk_forward,
)


def load_ml_dataset(
    features_path: Path,
    target_path: Path,
    metadata_path: Path,
) -> MLDataset:
    """Carica feature, target e metadati dai file Parquet."""

    # Riunisce i percorsi obbligatori.
    required_paths = [
        features_path,
        target_path,
        metadata_path,
    ]

    # Individua eventuali file mancanti.
    missing_paths = [str(path) for path in required_paths if not path.exists()]

    # Interrompe l'esecuzione se manca almeno un file.
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

    # Carica il target.
    target_dataframe = pd.read_parquet(
        target_path,
        engine="pyarrow",
    )

    # Verifica la presenza della colonna target.
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

    # Le tre componenti devono avere la stessa lunghezza.
    if not (len(features) == len(target) == len(metadata)):
        raise ValueError("Feature, target e metadati non sono allineati.")

    # Restituisce il dataset strutturato.
    return MLDataset(
        features=features,
        target=target,
        metadata=metadata,
    )


def create_fold_dataframe(
    fold_reports: list[object],
) -> pd.DataFrame:
    """Converte i report delle finestre in un DataFrame."""

    # Converte ogni report tramite il relativo metodo to_dict.
    fold_rows = [report.to_dict() for report in fold_reports]

    # Restituisce una tabella con una riga per finestra.
    return pd.DataFrame(fold_rows)


def print_summary(
    walk_forward_metrics: dict[str, object],
    single_split_metrics: dict[str, object],
    fold_dataframe: pd.DataFrame,
) -> None:
    """Mostra un confronto tra Walk-Forward e singolo split."""

    # Mostra il riepilogo della Walk-Forward.
    print("Walk-Forward Validation completata correttamente.")
    print("Dataset: SYNTHETIC DEMO")
    print("Modalità: PAPER ONLY")
    print("")
    print(f"Finestre completate: {walk_forward_metrics['fold_count']}")
    print(f"Predizioni complessive: {walk_forward_metrics['total_predictions']}")
    print(f"Accuracy aggregata: {walk_forward_metrics['aggregate_accuracy']}")
    print(f"Macro F1 aggregato: {walk_forward_metrics['aggregate_macro_f1']}")
    print(f"Accuracy media per finestra: {walk_forward_metrics['mean_fold_accuracy']}")
    print(f"Accuracy minima per finestra: {walk_forward_metrics['minimum_fold_accuracy']}")
    print(f"Accuracy massima per finestra: {walk_forward_metrics['maximum_fold_accuracy']}")
    print("")
    print("Confronto con singolo split temporale:")
    print(f"Accuracy singolo split: {single_split_metrics['accuracy']}")
    print(f"Macro F1 singolo split: {single_split_metrics['macro_f1']}")
    print("")
    print("Risultati per finestra:")

    # Definisce le colonne essenziali da mostrare.
    display_columns = [
        "fold_id",
        "training_rows",
        "test_rows",
        "accuracy",
        "macro_f1",
        "training_end_timestamp",
        "test_start_timestamp",
    ]

    # Mostra la tabella sintetica delle finestre.
    print(fold_dataframe[display_columns].to_string(index=False))


def main() -> None:
    """Carica il dataset ed esegue la validazione temporale."""

    # Definisce i file di input.
    features_path = Path("data/features/sample_ml_features.parquet")

    target_path = Path("data/features/sample_ml_target.parquet")

    metadata_path = Path("data/features/sample_ml_metadata.parquet")

    # Definisce i file di output.
    predictions_path = Path("reports/walk_forward_predictions.csv")

    folds_path = Path("reports/walk_forward_folds.csv")

    summary_path = Path("reports/walk_forward_summary.json")

    # Carica il dataset Machine Learning.
    dataset = load_ml_dataset(
        features_path=features_path,
        target_path=target_path,
        metadata_path=metadata_path,
    )

    # Configura la Walk-Forward Validation.
    walk_forward_config = WalkForwardConfig(
        initial_training_rows=200,
        test_rows=40,
        step_rows=40,
        gap_rows=2,
        maximum_iterations=1000,
        random_state=42,
        class_weight="balanced",
    )

    # Esegue la validazione Walk-Forward.
    walk_forward_result = run_walk_forward(
        dataset=dataset,
        config=walk_forward_config,
    )

    # Converte i report delle finestre in tabella.
    fold_dataframe = create_fold_dataframe(walk_forward_result.fold_reports)

    # Addestra anche il modello con singolo split temporale.
    single_split_result = train_logistic_baseline(
        dataset=dataset,
        config=LogisticBaselineConfig(
            test_size_percentage=0.20,
            maximum_iterations=1000,
            random_state=42,
            class_weight="balanced",
        ),
    )

    # Costruisce il report complessivo.
    summary: dict[str, object] = {
        "validation_version": "walk_forward_0.1.0",
        "dataset_type": "SYNTHETIC_DEMO",
        "walk_forward": walk_forward_result.metrics,
        "single_temporal_split": {
            "accuracy": single_split_result.metrics["accuracy"],
            "macro_f1": single_split_result.metrics["macro_f1"],
            "training_rows": single_split_result.training_rows,
            "test_rows": single_split_result.test_rows,
        },
        "comparison": {
            "walk_forward_accuracy_above_single_split": (
                float(walk_forward_result.metrics["aggregate_accuracy"])
                > float(single_split_result.metrics["accuracy"])
            ),
            "walk_forward_macro_f1_above_single_split": (
                float(walk_forward_result.metrics["aggregate_macro_f1"])
                > float(single_split_result.metrics["macro_f1"])
            ),
        },
        "safety": {
            "shuffle_used": False,
            "training_window_expands": True,
            "gap_rows": walk_forward_config.gap_rows,
            "future_data_used_for_training": False,
            "paper_trading_only": True,
        },
    }

    # Crea la cartella dei report se necessario.
    predictions_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Salva tutte le predizioni fuori campione.
    walk_forward_result.predictions.to_csv(
        predictions_path,
        index=False,
    )

    # Salva una riga per ogni finestra.
    fold_dataframe.to_csv(
        folds_path,
        index=False,
    )

    # Salva il report riassuntivo JSON.
    summary_path.write_text(
        json.dumps(
            summary,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Mostra il riepilogo nel terminale.
    print_summary(
        walk_forward_metrics=walk_forward_result.metrics,
        single_split_metrics=single_split_result.metrics,
        fold_dataframe=fold_dataframe,
    )

    # Mostra i percorsi degli artefatti.
    print("")
    print(f"Predizioni: {predictions_path.resolve()}")
    print(f"Finestre: {folds_path.resolve()}")
    print(f"Riepilogo: {summary_path.resolve()}")


if __name__ == "__main__":
    # Avvia la validazione solamente se eseguito direttamente.
    main()
