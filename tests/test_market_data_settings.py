"""Test della configurazione dell'archivio candele."""

# Importa Path per confrontare i percorsi
# in modo indipendente dal sistema operativo.
from pathlib import Path

# Importa il caricatore della configurazione.
from src.config.settings import (
    load_settings,
)


def test_default_market_data_database_path() -> None:
    """Verifica il percorso predefinito dell'archivio."""

    # Carica la configurazione predefinita.
    settings = load_settings({})

    # Confronta due oggetti Path.
    # In questo modo il test funziona sia su Windows sia su Linux.
    assert settings.market_data_database_path == Path("data/live_paper/market_data.db")


def test_custom_market_data_database_path() -> None:
    """Verifica un percorso personalizzato."""

    # Carica una configurazione personalizzata.
    settings = load_settings(
        {
            "MARKET_DATA_DATABASE_PATH": ("data/live_paper/custom_market.db"),
        }
    )

    # Confronta il percorso caricato con il Path atteso.
    assert settings.market_data_database_path == Path("data/live_paper/custom_market.db")


def test_safe_summary_contains_market_data_path() -> None:
    """Verifica il riepilogo sicuro."""

    # Carica la configurazione.
    settings = load_settings(
        {
            "MARKET_DATA_DATABASE_PATH": ("data/live_paper/test_market.db"),
        }
    )

    # Genera il riepilogo.
    summary = settings.safe_summary()

    # Converte nuovamente la stringa del riepilogo in Path.
    # Questo evita differenze tra "/" e "\" sui diversi sistemi.
    assert Path(str(summary["market_data_database_path"])) == Path("data/live_paper/test_market.db")

    # Il riepilogo non deve contenere la password.
    assert "mt5_password" not in summary

    # Deve essere presente soltanto lo stato
    # dell'avvenuta configurazione.
    assert "mt5_password_configured" in summary
