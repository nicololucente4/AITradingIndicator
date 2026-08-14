"""Esegue inferenza tramite un modello registrato e verificato."""

from pathlib import Path

import pandas as pd

from src.models.inference import run_registered_inference


def main() -> None:
    """Carica le ultime feature e genera predizioni PAPER_ONLY."""

    # Definisce input, Registry e output.
    features_path = Path("data/features/sample_ml_features.parquet")

    metadata_path = Path("data/features/sample_ml_metadata.parquet")

    registry_path = Path("models/registry.json")

    output_path = Path("reports/registered_model_inference.csv")

    # Verifica la presenza dei file necessari.
    for required_path in [
        features_path,
        metadata_path,
        registry_path,
    ]:
        if not required_path.exists():
            raise FileNotFoundError(f"File richiesto non trovato: {required_path}.")

    # Carica feature e metadati.
    features = pd.read_parquet(
        features_path,
        engine="pyarrow",
    )

    metadata = pd.read_parquet(
        metadata_path,
        engine="pyarrow",
    )

    # Utilizza le ultime venti righe come dimostrazione.
    inference_features = features.tail(20).reset_index(drop=True)

    inference_metadata = metadata.tail(20).reset_index(drop=True)

    # Esegue inferenza tramite il modello candidato registrato.
    predictions = run_registered_inference(
        features=inference_features,
        registry_path=registry_path,
        model_version="gradient_boosting_0.1.0",
        allowed_statuses={
            "CANDIDATE",
            "APPROVED",
        },
    )

    # Riunisce timestamp e predizioni.
    output = pd.concat(
        [
            inference_metadata,
            predictions,
        ],
        axis=1,
    )

    # Salva il risultato.
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.to_csv(
        output_path,
        index=False,
    )

    # Mostra un riepilogo.
    print("Inferenza tramite Model Registry completata.")
    print("Modalità: PAPER ONLY")
    print(f"Righe elaborate: {len(output)}")
    print("")
    print(
        output[
            [
                "timestamp",
                "predicted_target",
                "prediction_confidence",
                "model_version",
                "model_status",
            ]
        ]
        .tail(10)
        .to_string(index=False)
    )
    print("")
    print(f"Risultato: {output_path.resolve()}")


if __name__ == "__main__":
    main()
