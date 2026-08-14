"""Valuta le predizioni ML prima e dopo il filtro di confidenza."""

import json
from pathlib import Path

import pandas as pd

from src.models.filtered_evaluation import (
    evaluate_filtered_predictions,
)


def main() -> None:
    """Carica le predizioni filtrate e genera il report."""

    # Definisce input e output.
    input_path = Path("reports/walk_forward_filtered_predictions.csv")

    report_path = Path("reports/filtered_predictions_evaluation.json")

    # Verifica che il filtro sia già stato applicato.
    if not input_path.exists():
        raise FileNotFoundError(
            "Predizioni filtrate non trovate. Eseguire prima scripts.apply_confidence_filter."
        )

    # Carica le predizioni.
    predictions = pd.read_csv(input_path)

    # Genera il report.
    report = evaluate_filtered_predictions(predictions)

    # Converte il report in dizionario.
    report_dictionary = report.to_dict()

    # Aggiunge informazioni di audit.
    report_dictionary["evaluation_version"] = "filtered_evaluation_0.1.0"
    report_dictionary["dataset_type"] = "SYNTHETIC_DEMO"
    report_dictionary["paper_trading_only"] = True

    # Salva il report in JSON.
    report_path.write_text(
        json.dumps(
            report_dictionary,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Mostra il confronto.
    print("Valutazione delle predizioni completata.")
    print("Dataset: SYNTHETIC DEMO")
    print("")
    print(f"Predizioni totali: {report.total_predictions}")
    print(f"Copertura direzionale: {report.directional_coverage_percentage:.2f}%")
    print("")
    print("Prima del filtro:")
    print(f"Accuracy: {report.raw_accuracy}")
    print(f"Macro F1: {report.raw_macro_f1}")
    print("")
    print("Dopo il filtro:")
    print(f"Accuracy: {report.filtered_accuracy}")
    print(f"Macro F1: {report.filtered_macro_f1}")
    print(f"Accuracy segnali direzionali accettati: {report.accepted_directional_accuracy}")
    print("")
    print(f"Precision LONG: {report.long_precision}")
    print(f"Recall LONG: {report.long_recall}")
    print(f"Precision SHORT: {report.short_precision}")
    print(f"Recall SHORT: {report.short_recall}")
    print("")
    print(f"Report: {report_path.resolve()}")


if __name__ == "__main__":
    main()
