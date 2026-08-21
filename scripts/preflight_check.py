"""Verifica preventiva dell'ambiente AI Trading Indicator."""

# Importa argparse per gestire le opzioni da terminale.
import argparse

# Importa importlib per verificare dipendenze opzionali.
import importlib

# Importa json per leggere il Model Registry.
import json

# Importa sys per controllare Python e il codice di uscita.
import sys

# Importa dataclass per rappresentare i controlli.
from dataclasses import dataclass

# Importa Path per verificare file e cartelle.
from pathlib import Path

# Importa il caricatore sicuro della configurazione.
from src.config.environment import (
    EnvironmentFileError,
    load_application_settings_from_env,
)

# Importa gli errori di configurazione.
from src.config.settings import (
    SettingsError,
)

# Importa la funzione di calcolo hash già usata dal progetto.
from src.models.registry import (
    calculate_file_sha256,
)


@dataclass(frozen=True)
class PreflightResult:
    """Rappresenta il risultato di un controllo."""

    # Nome del controllo.
    name: str

    # Esito del controllo.
    passed: bool

    # Descrizione non sensibile.
    message: str


def create_argument_parser() -> argparse.ArgumentParser:
    """Crea il parser delle opzioni."""

    # Crea il parser principale.
    parser = argparse.ArgumentParser(
        description=("Verifica configurazione, modello e dipendenze prima dell'avvio Live Paper.")
    )

    # Permette di indicare un file .env differente.
    parser.add_argument(
        "--env-file",
        default=".env",
        help=("Percorso del file .env locale. Valore predefinito: .env"),
    )

    return parser


def check_python_version() -> PreflightResult:
    """Verifica l'utilizzo di Python 3.11."""

    # Recupera la versione corrente.
    current_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    # Il progetto richiede Python 3.11.
    passed = sys.version_info.major == 3 and sys.version_info.minor == 11

    return PreflightResult(
        name="Python",
        passed=passed,
        message=(f"Versione rilevata: {current_version}. Versione richiesta: 3.11.x."),
    )


def check_registry_and_model():
    """Verifica Model Registry, modello e hash."""

    # Definisce il percorso del registry.
    registry_path = Path("models/registry.json")

    # Verifica la presenza del registry.
    if not registry_path.is_file():
        return [
            PreflightResult(
                name="Model Registry",
                passed=False,
                message=("File models/registry.json non trovato."),
            )
        ]

    try:
        # Legge il contenuto JSON.
        registry_content = json.loads(registry_path.read_text(encoding="utf-8"))

    except Exception as error:
        return [
            PreflightResult(
                name="Model Registry",
                passed=False,
                message=(f"Model Registry non leggibile: {type(error).__name__}."),
            )
        ]

    # Il registry deve contenere una lista.
    if not isinstance(
        registry_content,
        list,
    ):
        return [
            PreflightResult(
                name="Model Registry",
                passed=False,
                message=("Il Model Registry deve contenere una lista."),
            )
        ]

    # Cerca il modello operativo.
    selected_model = next(
        (
            item
            for item in registry_content
            if item.get("model_version") == "gradient_boosting_0.1.0"
        ),
        None,
    )

    # Il modello deve essere registrato.
    if selected_model is None:
        return [
            PreflightResult(
                name="Modello operativo",
                passed=False,
                message=("gradient_boosting_0.1.0 non è presente nel registry."),
            )
        ]

    # Recupera il percorso del file.
    model_path = Path(
        str(
            selected_model.get(
                "model_path",
                "",
            )
        )
    )

    # Verifica il file del modello.
    if not model_path.is_file():
        return [
            PreflightResult(
                name="Modello operativo",
                passed=False,
                message=(f"File modello non trovato: {model_path}."),
            )
        ]

    # Recupera l'hash registrato.
    expected_hash = str(
        selected_model.get(
            "model_sha256",
            "",
        )
    )

    # Calcola l'hash corrente.
    actual_hash = calculate_file_sha256(model_path)

    # Verifica l'integrità.
    hash_matches = actual_hash == expected_hash

    return [
        PreflightResult(
            name="Model Registry",
            passed=True,
            message=("Registry disponibile e leggibile."),
        ),
        PreflightResult(
            name="Modello operativo",
            passed=True,
            message=(
                f"gradient_boosting_0.1.0 disponibile. Stato: {selected_model.get('status')}."
            ),
        ),
        PreflightResult(
            name="Integrità modello",
            passed=hash_matches,
            message=(
                "Hash SHA-256 verificato."
                if hash_matches
                else "Hash SHA-256 differente dal registry."
            ),
        ),
    ]


def check_provider(
    data_provider: str,
    file_provider_path: Path,
) -> PreflightResult:
    """Verifica il provider selezionato."""

    # Verifica il provider FILE.
    if data_provider == "FILE":
        return PreflightResult(
            name="Provider FILE",
            passed=file_provider_path.is_file(),
            message=(f"Dataset configurato: {file_provider_path}."),
        )

    # Verifica il pacchetto MetaTrader5.
    try:
        importlib.import_module("MetaTrader5")

    except ModuleNotFoundError:
        return PreflightResult(
            name="Provider MT5",
            passed=False,
            message=("Pacchetto MetaTrader5 non installato."),
        )

    return PreflightResult(
        name="Provider MT5",
        passed=True,
        message=(
            "Pacchetto MetaTrader5 disponibile. Connessione account non eseguita dal preflight."
        ),
    )


def print_results(
    results: list[PreflightResult],
) -> bool:
    """Mostra i risultati e restituisce l'esito complessivo."""

    # Mostra l'intestazione.
    print("=" * 68)
    print("AI Trading Indicator - Preflight Check")
    print("=" * 68)

    # Stampa ogni controllo.
    for result in results:
        status = "OK" if result.passed else "ERRORE"

        print(f"[{status}] {result.name}: {result.message}")

    # Calcola l'esito complessivo.
    all_passed = all(result.passed for result in results)

    print("-" * 68)
    print("ESITO: " + ("SISTEMA PRONTO" if all_passed else "CONFIGURAZIONE NON PRONTA"))
    print("PAPER TRADING: OBBLIGATORIO")
    print("ORDINI REALI: DISABILITATI")
    print("=" * 68)

    return all_passed


def main() -> int:
    """Esegue tutti i controlli preventivi."""

    # Interpreta gli argomenti.
    parser = create_argument_parser()

    arguments = parser.parse_args()

    try:
        # Carica la configurazione locale.
        settings = load_application_settings_from_env(
            environment_file=(arguments.env_file),
            require_file=True,
            override_existing=True,
        )

    except (
        EnvironmentFileError,
        SettingsError,
    ) as error:
        # Mostra un errore privo di credenziali.
        print("=" * 68)
        print("PREFLIGHT FALLITO")
        print(str(error))
        print("ORDINI REALI: DISABILITATI")
        print("=" * 68)

        return 1

    # Prepara i risultati generali.
    results = [
        check_python_version(),
        PreflightResult(
            name="Modalità applicativa",
            passed=(settings.app_mode == "PAPER_ONLY"),
            message=(f"Modalità: {settings.app_mode}."),
        ),
        PreflightResult(
            name="Ordini reali",
            passed=(settings.real_orders_enabled is False),
            message=("REAL_ORDERS_ENABLED=false."),
        ),
        PreflightResult(
            name="Database Live Paper",
            passed=True,
            message=(f"Percorso configurato: {settings.live_paper_database_path}."),
        ),
        PreflightResult(
            name="Database candele",
            passed=True,
            message=(f"Percorso configurato: {settings.market_data_database_path}."),
        ),
        check_provider(
            settings.data_provider,
            settings.file_provider_path,
        ),
    ]

    # Aggiunge i controlli del modello.
    results.extend(check_registry_and_model())

    # Mostra il riepilogo.
    all_passed = print_results(results)

    # Restituisce zero solamente se tutto è valido.
    return 0 if all_passed else 1


if __name__ == "__main__":
    # Termina il processo con il codice appropriato.
    sys.exit(main())
