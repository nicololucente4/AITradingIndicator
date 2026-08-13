"""Genera il report di qualità del dataset CSV di esempio."""

# Importa json per salvare il report in formato leggibile.
import json

# Importa timedelta per impostare la frequenza M15.
from datetime import timedelta

# Importa Path per gestire i percorsi dei file.
from pathlib import Path

# Importa il provider locale.
from src.data.file_provider import FileDataProvider

# Importa il generatore del report qualità.
from src.data.quality_report import generate_quality_report


def main() -> None:
    """Carica il dataset e genera il relativo report qualità."""

    # Definisce il CSV da analizzare.
    input_path = Path("data/sample/EURUSD_M15_sample.csv")

    # Definisce il file JSON da produrre.
    output_path = Path("reports/EURUSD_M15_quality_report.json")

    # Crea il provider locale.
    provider = FileDataProvider()

    # Carica e valida il CSV.
    dataframe = provider.load_csv(input_path)

    # Genera il report con frequenza attesa di 15 minuti.
    report = generate_quality_report(
        dataframe,
        expected_interval=timedelta(minutes=15),
    )

    # Crea la cartella reports se non esiste.
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Salva il report in formato JSON leggibile.
    output_path.write_text(
        json.dumps(
            report.to_dict(),
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Mostra un riepilogo nel terminale.
    print("Report di qualità generato correttamente.")
    print(f"Candele presenti: {report.total_rows}")
    print(f"Candele attese: {report.expected_rows}")
    print(f"Candele mancanti: {report.missing_rows}")
    print(f"Completezza: {report.completeness_percentage}%")
    print(f"Intervallo rilevato: {report.detected_interval_seconds} secondi")
    print(f"File creato: {output_path.resolve()}")


if __name__ == "__main__":
    # Avvia lo script solamente se eseguito direttamente.
    main()
