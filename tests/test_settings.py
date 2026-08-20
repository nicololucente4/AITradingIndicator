"""Test automatici della configurazione applicativa."""

# Importa pytest per verificare gli errori attesi.
import pytest

# Importa configurazione ed errore.
from src.config.settings import (
    SettingsError,
    load_settings,
)


def test_default_settings_are_paper_only() -> None:
    """Verifica i valori predefiniti sicuri."""

    # Carica un ambiente completamente vuoto.
    settings = load_settings({})

    # Verifica la modalità operativa.
    assert settings.app_mode == "PAPER_ONLY"

    # Il provider predefinito è il file.
    assert settings.data_provider == "FILE"

    # Gli ordini reali devono essere disabilitati.
    assert settings.paper_trading_only is True
    assert settings.real_orders_enabled is False


def test_file_provider_does_not_require_mt5_credentials() -> None:
    """Verifica che il provider file non richieda MT5."""

    # Seleziona esplicitamente il provider file.
    settings = load_settings(
        {
            "DATA_PROVIDER": "FILE",
        }
    )

    # Le credenziali MT5 possono essere assenti.
    assert settings.mt5_login is None
    assert settings.mt5_password is None
    assert settings.mt5_server is None


def test_mt5_provider_requires_credentials() -> None:
    """Verifica il rifiuto di una configurazione MT5 incompleta."""

    # MT5 senza credenziali deve essere rifiutato.
    with pytest.raises(
        SettingsError,
        match="Configurazione MT5 incompleta",
    ):
        load_settings(
            {
                "DATA_PROVIDER": "MT5",
            }
        )


def test_complete_mt5_settings_are_loaded() -> None:
    """Verifica una configurazione MT5 completa."""

    # Carica valori fittizi usati esclusivamente dal test.
    settings = load_settings(
        {
            "DATA_PROVIDER": "MT5",
            "MT5_LOGIN": "12345678",
            "MT5_PASSWORD": "test-password",
            "MT5_SERVER": "Demo-Test-Server",
            "MT5_TERMINAL_PATH": (
                r"C:\Program Files\MetaTrader 5"
                r"\terminal64.exe"
            ),
        }
    )

    # Verifica i valori caricati.
    assert settings.mt5_login == 12345678
    assert settings.mt5_password == "test-password"
    assert settings.mt5_server == "Demo-Test-Server"

    # La modalità deve rimanere PAPER_ONLY.
    assert settings.paper_trading_only is True
    assert settings.real_orders_enabled is False


def test_non_paper_mode_is_rejected() -> None:
    """Verifica il rifiuto di modalità diverse da PAPER_ONLY."""

    with pytest.raises(
        SettingsError,
        match="APP_MODE",
    ):
        load_settings(
            {
                "APP_MODE": "LIVE_REAL",
            }
        )


def test_real_orders_cannot_be_enabled() -> None:
    """Verifica il blocco assoluto degli ordini reali."""

    with pytest.raises(
        SettingsError,
        match="REAL_ORDERS_ENABLED",
    ):
        load_settings(
            {
                "REAL_ORDERS_ENABLED": "true",
            }
        )


def test_invalid_boolean_is_rejected() -> None:
    """Verifica il rifiuto di un booleano ambiguo."""

    with pytest.raises(
        SettingsError,
        match="true oppure false",
    ):
        load_settings(
            {
                "PAPER_TRADING_ONLY": "forse",
            }
        )


def test_invalid_positive_integer_is_rejected() -> None:
    """Verifica il rifiuto di intervalli non positivi."""

    with pytest.raises(
        SettingsError,
        match="maggiore di zero",
    ):
        load_settings(
            {
                "POLL_INTERVAL_SECONDS": "0",
            }
        )


def test_safe_summary_excludes_password() -> None:
    """Verifica che il riepilogo non esponga la password."""

    # Crea una configurazione MT5 fittizia.
    settings = load_settings(
        {
            "DATA_PROVIDER": "MT5",
            "MT5_LOGIN": "12345678",
            "MT5_PASSWORD": "secret-test-value",
            "MT5_SERVER": "Demo-Test-Server",
        }
    )

    # Genera il riepilogo sicuro.
    summary = settings.safe_summary()

    # La password non deve essere presente.
    assert "mt5_password" not in summary

    # Deve essere presente solamente lo stato di configurazione.
    assert summary["mt5_password_configured"] is True

    # Il valore sensibile non deve comparire nel testo.
    assert "secret-test-value" not in str(summary)
