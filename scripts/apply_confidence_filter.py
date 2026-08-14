"""Applica il filtro di confidenza alle predizioni Walk-Forward."""

import json
from pathlib import Path

import pandas as pd

from src.signals.confidence_filter import (
    ConfidenceFilterConfig,
    apply_confidence_filter,
)


def main() -> None:
    """Filtra le predizioni e genera un report di copertura."""

    # Definisce i file di input e output.
    input_path = Path("reports/walk_forward_predictions.csv")

    output_path = Path("reports/walk_forward_filtered_predictions.csv")

    report_path = Path("reports/confidence_filter_report.json")

    # Verifica che le predizioni Walk-Forward esistano.
    if not input_path.exists():
        raise FileNotFoundError(
            "Predizioni Walk-Forward non trovate. "
            "Eseguire prima scripts.run_walk_forward_validation."
        )

    # Carica le predizioni fuori campione.
    predictions = pd.read_csv(input_path)

    # Configura le soglie iniziali.
    config = ConfidenceFilterConfig(
        minimum_confidence=0.60,
        minimum_probability_margin=0.10,
        fallback_signal="NO_TRADE",
    )

    # Applica il filtro.
    filtered_predictions = apply_confidence_filter(
        predictions=predictions,
        config=config,
    )

    # Identifica le previsioni direzionali originali.
    raw_directional = filtered_predictions["raw_prediction"].isin({"LONG", "SHORT"})

    # Identifica le previsioni direzionali accettate.
    accepted_directional = filtered_predictions["filtered_signal"].isin({"LONG", "SHORT"})

    # Calcola la copertura direzionale.
    directional_coverage = float(accepted_directional.sum()) / len(filtered_predictions) * 100.0

    # Calcola il tasso di accettazione dei segnali direzionali.
    directional_acceptance_rate = (
        float((raw_directional & accepted_directional).sum())
        / max(int(raw_directional.sum()), 1)
        * 100.0
    )

    # Conta i segnali prima e dopo il filtro.
    raw_counts = filtered_predictions["raw_prediction"].value_counts().to_dict()

    filtered_counts = filtered_predictions["filtered_signal"].value_counts().to_dict()

    # Costruisce il report.
    report = {
        "filter_version": "confidence_filter_0.1.0",
        "minimum_confidence": config.minimum_confidence,
        "minimum_probability_margin": (config.minimum_probability_margin),
        "total_predictions": len(filtered_predictions),
        "raw_signal_counts": raw_counts,
        "filtered_signal_counts": filtered_counts,
        "directional_coverage_percentage": round(
            directional_coverage,
            6,
        ),
        "directional_acceptance_rate_percentage": round(
            directional_acceptance_rate,
            6,
        ),
        "rejection_reasons": (filtered_predictions["filter_reason"].value_counts().to_dict()),
        "thresholds_selected_on_test_set": False,
        "paper_trading_only": True,
    }

    # Salva predizioni e report.
    filtered_predictions.to_csv(
        output_path,
        index=False,
    )

    report_path.write_text(
        json.dumps(
            report,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Mostra il riepilogo.
    print("Filtro di confidenza applicato correttamente.")
    print(f"Predizioni totali: {len(filtered_predictions)}")
    print(f"Copertura direzionale: {directional_coverage:.2f}%")
    print(f"Accettazione segnali direzionali: {directional_acceptance_rate:.2f}%")
    print("")
    print("Segnali filtrati:")
    print(filtered_predictions["filtered_signal"].value_counts().to_string())
    print("")
    print(f"Predizioni: {output_path.resolve()}")
    print(f"Report: {report_path.resolve()}")


if __name__ == "__main__":
    main()
