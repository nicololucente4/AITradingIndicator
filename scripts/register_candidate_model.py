"""Registra il modello candidato nel Model Registry locale."""

import json
from pathlib import Path

from src.models.registry import (
    create_registry_entry,
    load_registry,
    register_model,
)


def main() -> None:
    """Legge metriche e modello, quindi registra il candidato."""

    # Definisce i file richiesti.
    model_path = Path("models/gradient_boosting_0.1.0.joblib")

    comparison_path = Path("reports/model_walk_forward_summary.json")

    registry_path = Path("models/registry.json")

    # Verifica che il modello sia stato generato.
    if not model_path.exists():
        raise FileNotFoundError(
            "Modello Gradient Boosting non trovato. Eseguire prima scripts.compare_ml_models."
        )

    # Verifica che il confronto Walk-Forward esista.
    if not comparison_path.exists():
        raise FileNotFoundError(
            "Report Walk-Forward non trovato. Eseguire prima scripts.compare_models_walk_forward."
        )

    # Carica il report di confronto.
    comparison_report = json.loads(
        comparison_path.read_text(
            encoding="utf-8",
        )
    )

    # Recupera le metriche del Gradient Boosting.
    model_metrics = comparison_report["models"]["HIST_GRADIENT_BOOSTING"]

    # Recupera il numero di finestre.
    fold_count = int(comparison_report["fold_count_per_model"])

    # Definisce le feature del modello.
    feature_columns = [
        "return_1",
        "ema_fast",
        "ema_slow",
        "ema_distance_pct",
        "true_range",
        "atr",
        "atr_pct",
        "volatility",
    ]

    # Crea la voce candidata.
    entry = create_registry_entry(
        model_version="gradient_boosting_0.1.0",
        model_type="HIST_GRADIENT_BOOSTING",
        status="CANDIDATE",
        model_path=model_path,
        feature_set_version="0.1.0",
        feature_columns=feature_columns,
        validation_type="WALK_FORWARD_SAME_FOLDS",
        fold_count=fold_count,
        mean_macro_f1=float(model_metrics["mean_macro_f1"]),
        minimum_macro_f1=float(model_metrics["minimum_macro_f1"]),
        mean_accuracy=float(model_metrics["mean_accuracy"]),
    )

    # Registra il modello.
    saved_path = register_model(
        entry=entry,
        registry_path=registry_path,
    )

    # Rilegge il registro per controllo.
    registry = load_registry(saved_path)

    # Mostra il risultato.
    print("Modello candidato registrato correttamente.")
    print(f"Versione: {entry.model_version}")
    print(f"Tipo: {entry.model_type}")
    print(f"Stato: {entry.status}")
    print(f"SHA-256: {entry.model_sha256}")
    print(f"Modelli registrati: {len(registry)}")
    print(f"Registro: {saved_path.resolve()}")


if __name__ == "__main__":
    main()
