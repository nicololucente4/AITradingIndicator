"""Test automatici del caricamento del file .env."""

# Importa Path per gestire i file temporanei.
from pathlib import Path

# Importa pytest per verificare gli errori attesi.
import pytest

# Importa il caricatore centralizzato dell'ambiente.
from src.config.environment import (
    EnvironmentFileError,
    load_application_settings_from_env,
    load_environment_file,
)


def write_environment_file(
    file_path: Path,
    content: str,
) -> None:
    """Scrive un file .env temporaneo."""

    # Salva il contenuto usando UTF-8.
    file_path.write_text(
        content,
        encoding="utf-8",
    )


def test_missing_required_environment_file_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il rifiuto di un file obbligatorio assente."""

    # Definisce un file che non esiste.
    missing_path = tmp_path / ".env"

    # Il caricamento deve interrompersi con un messaggio chiaro.
    with pytest.raises(
        EnvironmentFileError,
        match="non trovato",
    ):
        load_environment_file(
            environment_file=missing_path,
            require_file=True,
        )


def test_optional_missing_file_uses_process_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifica il comportamento senza file opzionale."""

    # Imposta una variabile temporanea nel processo.
    monkeypatch.setenv(
        "TRADING_SYMBOL",
        "GBPUSD",
    )

    # Carica un file inesistente ma non obbligatorio.
    loaded_environment = load_environment_file(
        environment_file=(tmp_path / "missing.env"),
        require_file=False,
    )

    # La variabile del processo deve essere disponibile.
    assert loaded_environment["TRADING_SYMBOL"] == "GBPUSD"


def test_environment_file_loads_mt5_settings(
    tmp_path: Path,
) -> None:
    """Verifica il caricamento di una configurazione MT5."""

    # Definisce il file temporaneo.
    environment_path = tmp_path / ".env"

    # Scrive credenziali esclusivamente fittizie.
    write_environment_file(
        environment_path,
        "\n".join(
            [
                "APP_MODE=PAPER_ONLY",
                "DATA_PROVIDER=MT5",
                "TRADING_SYMBOL=EURUSD",
                "TIMEFRAME_MINUTES=15",
                "MT5_LOGIN=12345678",
                "MT5_PASSWORD=test-password",
                "MT5_SERVER=Demo-Test-Server",
                "PAPER_TRADING_ONLY=true",
                "REAL_ORDERS_ENABLED=false",
            ]
        ),
    )

    # Carica e valida la configurazione.
    settings = load_application_settings_from_env(
        environment_file=environment_path,
        override_existing=True,
    )

    # Verifica i valori principali.
    assert settings.data_provider == "MT5"
    assert settings.trading_symbol == "EURUSD"
    assert settings.mt5_login == 12345678
    assert settings.mt5_server == "Demo-Test-Server"
    assert settings.paper_trading_only is True
    assert settings.real_orders_enabled is False


def test_existing_environment_has_priority_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifica che l'ambiente esistente non venga sovrascritto."""

    # Imposta il valore già presente nel processo.
    monkeypatch.setenv(
        "TRADING_SYMBOL",
        "GBPUSD",
    )

    # Prepara un valore differente nel file.
    environment_path = tmp_path / ".env"

    write_environment_file(
        environment_path,
        "TRADING_SYMBOL=EURUSD\n",
    )

    # Carica senza abilitare override.
    loaded_environment = load_environment_file(
        environment_file=environment_path,
        override_existing=False,
    )

    # Deve prevalere il valore già presente.
    assert loaded_environment["TRADING_SYMBOL"] == "GBPUSD"


def test_environment_file_can_override_existing_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifica l'override esplicito delle variabili."""

    # Imposta il valore iniziale.
    monkeypatch.setenv(
        "TRADING_SYMBOL",
        "GBPUSD",
    )

    # Scrive il nuovo valore nel file.
    environment_path = tmp_path / ".env"

    write_environment_file(
        environment_path,
        "TRADING_SYMBOL=EURUSD\n",
    )

    # Carica abilitando l'override.
    loaded_environment = load_environment_file(
        environment_file=environment_path,
        override_existing=True,
    )

    # Deve prevalere il file locale.
    assert loaded_environment["TRADING_SYMBOL"] == "EURUSD"
