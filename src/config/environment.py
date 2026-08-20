"""Caricamento controllato della configurazione locale dal file .env."""

# Importa os per leggere le variabili d'ambiente risultanti.
import os

# Importa Path per gestire il percorso del file .env.
from pathlib import Path

# Importa dotenv_values per leggere il file senza modificare
# immediatamente l'ambiente del processo.
from dotenv import dotenv_values

# Importa la configurazione centralizzata del progetto.
from src.config.settings import (
    ApplicationSettings,
    SettingsError,
    load_settings,
)


class EnvironmentFileError(ValueError):
    """Errore generato dal caricamento del file .env."""


def load_environment_file(
    environment_file: str | Path = ".env",
    *,
    require_file: bool = True,
    override_existing: bool = False,
) -> dict[str, str]:
    """Carica un file .env in un dizionario di variabili.

    Args:
        environment_file: Percorso del file di configurazione.
        require_file: Se True, il file deve esistere.
        override_existing: Se True, il file .env sostituisce le
            variabili già presenti nel processo.

    Returns:
        Dizionario contenente l'ambiente risultante.

    Raises:
        EnvironmentFileError: se il file è richiesto ma assente,
            contiene chiavi vuote oppure non è leggibile.
    """

    # Converte il percorso in un oggetto Path.
    selected_path = Path(environment_file)

    # Verifica la presenza del file quando obbligatorio.
    if not selected_path.exists():
        if require_file:
            raise EnvironmentFileError(
                f"File di configurazione non trovato: {selected_path.resolve()}."
            )

        # Senza file restituisce una copia dell'ambiente corrente.
        return dict(os.environ)

    # Verifica che il percorso rappresenti un file.
    if not selected_path.is_file():
        raise EnvironmentFileError(
            f"Il percorso della configurazione non è un file: {selected_path.resolve()}."
        )

    try:
        # Legge il file senza modificare os.environ.
        dotenv_content = dotenv_values(selected_path)

    except Exception as error:
        raise EnvironmentFileError(
            f"Impossibile leggere il file di configurazione: {selected_path.resolve()}."
        ) from error

    # Parte da una copia delle variabili già presenti.
    combined_environment = dict(os.environ)

    # Integra i valori letti dal file.
    for key, value in dotenv_content.items():
        # Rifiuta eventuali chiavi vuote.
        if not key.strip():
            raise EnvironmentFileError("Il file .env contiene una chiave vuota.")

        # Ignora i valori privi di contenuto.
        if value is None:
            continue

        # Mantiene la variabile esistente quando override è disabilitato.
        if not override_existing and key in combined_environment:
            continue

        # Salva il valore nel dizionario risultante.
        combined_environment[key] = value

    # Restituisce l'ambiente completo senza modificare os.environ.
    return combined_environment


def load_application_settings_from_env(
    environment_file: str | Path = ".env",
    *,
    require_file: bool = True,
    override_existing: bool = False,
) -> ApplicationSettings:
    """Carica e valida ApplicationSettings dal file .env.

    Il file viene letto in memoria e validato senza scrivere
    credenziali nel terminale o nei log.
    """

    # Carica il file e combina le variabili.
    selected_environment = load_environment_file(
        environment_file=environment_file,
        require_file=require_file,
        override_existing=override_existing,
    )

    try:
        # Converte le variabili nella configurazione applicativa.
        return load_settings(selected_environment)

    except SettingsError:
        # Mantiene il tipo e il messaggio originale della validazione.
        raise
