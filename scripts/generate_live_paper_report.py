"""Genera il report statistico Live Paper leggendo il database SQLite."""

# Importa json per salvare il report in formato strutturato.
import json

# Importa sqlite3 per leggere il database Live Paper.
import sqlite3

# Importa Path per gestire i percorsi dei file.
from pathlib import Path

# Importa pandas per leggere le tabelle SQLite.
import pandas as pd

# Importa il generatore delle statistiche Live Paper.
from src.monitoring.live_paper_report import (
    generate_live_paper_statistics,
)


def table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    """Verifica se una tabella esiste nel database SQLite."""

    # Interroga il catalogo interno di SQLite.
    cursor = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    )

    # Restituisce True se la tabella è stata trovata.
    return cursor.fetchone() is not None


def create_empty_outcomes_dataframe() -> pd.DataFrame:
    """Crea un registro esiti vuoto con lo schema richiesto."""

    # Mantiene le colonne necessarie al modulo statistico.
    return pd.DataFrame(
        columns=[
            "signal_id",
            "exit_reason",
            "holding_bars",
            "gross_return_percentage",
            "result_r",
        ]
    )


def load_live_paper_data(
    database_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Carica segnali ed esiti dal database Live Paper."""

    # Verifica che il database esista.
    if not database_path.exists():
        raise FileNotFoundError(f"Database Live Paper non trovato: {database_path}.")

    # Apre il database in sola lettura applicativa.
    with sqlite3.connect(database_path) as connection:
        # La tabella signals è obbligatoria.
        if not table_exists(
            connection,
            "signals",
        ):
            raise RuntimeError("Il database non contiene la tabella signals.")

        # Carica tutti i segnali confermati.
        signals = pd.read_sql_query(
            """
            SELECT *
            FROM signals
            ORDER BY timestamp ASC
            """,
            connection,
        )

        # Carica gli esiti se la tabella è già stata creata.
        if table_exists(
            connection,
            "signal_outcomes",
        ):
            outcomes = pd.read_sql_query(
                """
                SELECT *
                FROM signal_outcomes
                ORDER BY exit_timestamp ASC
                """,
                connection,
            )

        # Se la tabella non esiste ancora, crea un registro vuoto.
        else:
            outcomes = create_empty_outcomes_dataframe()

    # Restituisce i due registri separati.
    return signals, outcomes


def main() -> None:
    """Legge SQLite e genera il report statistico JSON."""

    # Definisce il database prodotto dalla demo Live Paper.
    database_path = Path("data/live_paper/demo_live_paper.db")

    # Definisce il report JSON da generare.
    report_path = Path("reports/live_paper_statistics.json")

    # Carica segnali ed esiti.
    signals, outcomes = load_live_paper_data(database_path)

    # Genera le statistiche aggregate.
    statistics = generate_live_paper_statistics(
        signals=signals,
        outcomes=outcomes,
    )

    # Converte le statistiche in dizionario.
    report = statistics.to_dict()

    # Aggiunge informazioni di audit.
    report["report_version"] = "live_paper_statistics_0.1.0"
    report["database_path"] = str(database_path)
    report["generated_from_sqlite"] = True
    report["signals_table_immutable"] = True
    report["outcomes_table_separate"] = True

    # Crea la cartella dei report.
    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Salva il report in formato JSON.
    report_path.write_text(
        json.dumps(
            report,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Mostra il riepilogo nel terminale.
    print("Report statistico Live Paper generato.")
    print("Modalità: PAPER ONLY")
    print(f"Segnali totali: {statistics.total_signals}")
    print(f"Segnali direzionali: {statistics.directional_signals}")
    print(f"Segnali conclusi: {statistics.resolved_directional_signals}")
    print(f"Segnali pendenti: {statistics.pending_directional_signals}")
    print(f"Tasso di risoluzione: {statistics.resolution_rate_percentage:.2f}%")
    print(f"Win rate: {statistics.win_rate_percentage:.2f}%")
    print(f"Expectancy: {statistics.expectancy_r:.4f} R")
    print(f"Maximum Drawdown: {statistics.maximum_drawdown_percentage:.4f}%")
    print("")
    print(f"Report: {report_path.resolve()}")


if __name__ == "__main__":
    # Avvia lo script solamente se eseguito direttamente.
    main()
