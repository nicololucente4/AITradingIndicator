"""Configurazione centralizzata dell'AI Trading Indicator."""

# Importa os per leggere le variabili d'ambiente.
import os

# Importa dataclass per rappresentare una configurazione immutabile.
from dataclasses import dataclass

# Importa Path per validare e gestire i percorsi locali.
from pathlib import Path


class SettingsError(ValueError):
    """Errore generato da una configurazione applicativa non valida."""


def _read_text(
    environment: dict[str, str],
    variable_name: str,
    default: str,
) -> str:
    """Legge e normalizza una variabile testuale."""

    # Recupera il valore oppure usa quello predefinito.
    selected_value = environment.get(
        variable_name,
        default,
    )

    # Elimina gli spazi esterni.
    normalized_value = selected_value.strip()

    # Le variabili testuali obbligatorie non possono essere vuote.
    if not normalized_value:
        raise SettingsError(f"La variabile {variable_name} non può essere vuota.")

    # Restituisce il valore normalizzato.
    return normalized_value


def _read_optional_text(
    environment: dict[str, str],
    variable_name: str,
) -> str | None:
    """Legge una variabile testuale opzionale."""

    # Recupera il valore, usando una stringa vuota come fallback.
    selected_value = environment.get(
        variable_name,
        "",
    ).strip()

    # Converte una stringa vuota in None.
    if not selected_value:
        return None

    # Restituisce il valore disponibile.
    return selected_value


def _read_positive_integer(
    environment: dict[str, str],
    variable_name: str,
    default: int,
) -> int:
    """Legge un numero intero strettamente positivo."""

    # Recupera il valore come testo.
    raw_value = environment.get(
        variable_name,
        str(default),
    ).strip()

    try:
        # Converte il valore in numero intero.
        selected_value = int(raw_value)

    except ValueError as error:
        raise SettingsError(
            f"La variabile {variable_name} deve essere un numero intero."
        ) from error

    # Il valore deve essere strettamente positivo.
    if selected_value <= 0:
        raise SettingsError(f"La variabile {variable_name} deve essere maggiore di zero.")

    # Restituisce il valore validato.
    return selected_value


def _read_optional_positive_integer(
    environment: dict[str, str],
    variable_name: str,
) -> int | None:
    """Legge un numero intero positivo opzionale."""

    # Recupera il valore come testo.
    raw_value = environment.get(
        variable_name,
        "",
    ).strip()

    # Un valore vuoto viene rappresentato con None.
    if not raw_value:
        return None

    try:
        # Converte il valore in intero.
        selected_value = int(raw_value)

    except ValueError as error:
        raise SettingsError(
            f"La variabile {variable_name} deve essere un numero intero."
        ) from error

    # Il valore deve essere positivo.
    if selected_value <= 0:
        raise SettingsError(f"La variabile {variable_name} deve essere maggiore di zero.")

    # Restituisce il valore validato.
    return selected_value


def _read_boolean(
    environment: dict[str, str],
    variable_name: str,
    default: bool,
) -> bool:
    """Legge una variabile booleana."""

    # Converte il valore predefinito in testo.
    default_text = "true" if default else "false"

    # Recupera e normalizza il valore.
    raw_value = (
        environment.get(
            variable_name,
            default_text,
        )
        .strip()
        .lower()
    )

    # Valori riconosciuti come veri.
    if raw_value in {
        "true",
        "1",
        "yes",
        "on",
    }:
        return True

    # Valori riconosciuti come falsi.
    if raw_value in {
        "false",
        "0",
        "no",
        "off",
    }:
        return False

    # Rifiuta valori ambigui.
    raise SettingsError(f"La variabile {variable_name} deve essere true oppure false.")


@dataclass(frozen=True)
class ApplicationSettings:
    """Configurazione completa dell'applicazione."""

    # Modalità operativa obbligatoriamente simulata.
    app_mode: str

    # Provider dati selezionato.
    data_provider: str

    # Simbolo richiesto al provider.
    trading_symbol: str

    # Durata della candela in minuti.
    timeframe_minutes: int

    # Intervallo tra due polling.
    poll_interval_seconds: int

    # Storico minimo richiesto.
    minimum_history_bars: int

    # Durata massima degli esiti.
    maximum_holding_bars: int

    # Database SQLite locale.
    live_paper_database_path: Path

    # Dataset del provider file.
    file_provider_path: Path

    # Numero account MT5 opzionale.
    mt5_login: int | None

    # Password MT5 opzionale.
    mt5_password: str | None

    # Server MT5 opzionale.
    mt5_server: str | None

    # Percorso opzionale del terminale MT5.
    mt5_terminal_path: Path | None

    # Numero di candele richieste a MT5.
    mt5_bars_per_poll: int

    # Timeout MT5 in millisecondi.
    mt5_timeout_milliseconds: int

    # Vincolo obbligatorio paper trading.
    paper_trading_only: bool

    # Gli ordini reali devono restare disabilitati.
    real_orders_enabled: bool

    def safe_summary(self) -> dict[str, object]:
        """Restituisce un riepilogo privo di credenziali."""

        # Non include mai la password MT5.
        return {
            "app_mode": self.app_mode,
            "data_provider": self.data_provider,
            "trading_symbol": self.trading_symbol,
            "timeframe_minutes": self.timeframe_minutes,
            "poll_interval_seconds": (self.poll_interval_seconds),
            "minimum_history_bars": (self.minimum_history_bars),
            "maximum_holding_bars": (self.maximum_holding_bars),
            "live_paper_database_path": str(self.live_paper_database_path),
            "file_provider_path": str(self.file_provider_path),
            "mt5_login_configured": (self.mt5_login is not None),
            "mt5_password_configured": (self.mt5_password is not None),
            "mt5_server_configured": (self.mt5_server is not None),
            "mt5_terminal_path": (
                None if self.mt5_terminal_path is None else str(self.mt5_terminal_path)
            ),
            "mt5_bars_per_poll": (self.mt5_bars_per_poll),
            "paper_trading_only": (self.paper_trading_only),
            "real_orders_enabled": (self.real_orders_enabled),
        }


def load_settings(
    environment: dict[str, str] | None = None,
) -> ApplicationSettings:
    """Carica e valida la configurazione applicativa."""

    # Usa una copia delle variabili reali se non viene passato
    # un ambiente specifico, ad esempio durante i test.
    selected_environment = dict(os.environ) if environment is None else dict(environment)

    # Legge e normalizza la modalità operativa.
    app_mode = _read_text(
        selected_environment,
        "APP_MODE",
        "PAPER_ONLY",
    ).upper()

    # La release corrente supporta solamente PAPER_ONLY.
    if app_mode != "PAPER_ONLY":
        raise SettingsError("APP_MODE deve essere PAPER_ONLY.")

    # Legge il provider selezionato.
    data_provider = _read_text(
        selected_environment,
        "DATA_PROVIDER",
        "FILE",
    ).upper()

    # Verifica la lista dei provider supportati.
    if data_provider not in {
        "FILE",
        "MT5",
    }:
        raise SettingsError("DATA_PROVIDER deve essere FILE oppure MT5.")

    # Legge i vincoli di sicurezza.
    paper_trading_only = _read_boolean(
        selected_environment,
        "PAPER_TRADING_ONLY",
        True,
    )

    real_orders_enabled = _read_boolean(
        selected_environment,
        "REAL_ORDERS_ENABLED",
        False,
    )

    # Il paper trading non può essere disabilitato.
    if not paper_trading_only:
        raise SettingsError("PAPER_TRADING_ONLY deve essere true.")

    # La release non può abilitare ordini reali.
    if real_orders_enabled:
        raise SettingsError("REAL_ORDERS_ENABLED deve essere false.")

    # Legge la configurazione opzionale MT5.
    mt5_login = _read_optional_positive_integer(
        selected_environment,
        "MT5_LOGIN",
    )

    mt5_password = _read_optional_text(
        selected_environment,
        "MT5_PASSWORD",
    )

    mt5_server = _read_optional_text(
        selected_environment,
        "MT5_SERVER",
    )

    mt5_terminal_path_text = _read_optional_text(
        selected_environment,
        "MT5_TERMINAL_PATH",
    )

    mt5_terminal_path = None if mt5_terminal_path_text is None else Path(mt5_terminal_path_text)

    # Il provider MT5 richiede le informazioni di accesso.
    if data_provider == "MT5":
        missing_variables: list[str] = []

        if mt5_login is None:
            missing_variables.append("MT5_LOGIN")

        if mt5_password is None:
            missing_variables.append("MT5_PASSWORD")

        if mt5_server is None:
            missing_variables.append("MT5_SERVER")

        if missing_variables:
            missing_text = ", ".join(missing_variables)

            raise SettingsError(
                f"Configurazione MT5 incompleta. Variabili mancanti: {missing_text}."
            )

    # Crea e restituisce la configurazione immutabile.
    return ApplicationSettings(
        app_mode=app_mode,
        data_provider=data_provider,
        trading_symbol=_read_text(
            selected_environment,
            "TRADING_SYMBOL",
            "EURUSD",
        ).upper(),
        timeframe_minutes=_read_positive_integer(
            selected_environment,
            "TIMEFRAME_MINUTES",
            15,
        ),
        poll_interval_seconds=_read_positive_integer(
            selected_environment,
            "POLL_INTERVAL_SECONDS",
            5,
        ),
        minimum_history_bars=_read_positive_integer(
            selected_environment,
            "MINIMUM_HISTORY_BARS",
            30,
        ),
        maximum_holding_bars=_read_positive_integer(
            selected_environment,
            "MAXIMUM_HOLDING_BARS",
            12,
        ),
        live_paper_database_path=Path(
            _read_text(
                selected_environment,
                "LIVE_PAPER_DATABASE_PATH",
                "data/live_paper/live_paper.db",
            )
        ),
        file_provider_path=Path(
            _read_text(
                selected_environment,
                "FILE_PROVIDER_PATH",
                "data/sample/EURUSD_M15_sample.csv",
            )
        ),
        mt5_login=mt5_login,
        mt5_password=mt5_password,
        mt5_server=mt5_server,
        mt5_terminal_path=mt5_terminal_path,
        mt5_bars_per_poll=_read_positive_integer(
            selected_environment,
            "MT5_BARS_PER_POLL",
            500,
        ),
        mt5_timeout_milliseconds=_read_positive_integer(
            selected_environment,
            "MT5_TIMEOUT_MILLISECONDS",
            60000,
        ),
        paper_trading_only=paper_trading_only,
        real_orders_enabled=real_orders_enabled,
    )
