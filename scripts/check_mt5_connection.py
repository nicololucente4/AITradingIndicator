"""Verifica read-only della connessione a MetaTrader 5."""

# Importa argparse per gestire le opzioni da terminale.
import argparse

# Importa importlib per caricare MetaTrader5 solamente quando necessario.
import importlib

# Importa sys per restituire un codice di uscita.
import sys

# Importa Path per gestire il file .env.
from pathlib import Path

# Importa Protocol e cast per tipizzare il modulo MT5.
from typing import cast

# Importa pandas per ottenere il timestamp UTC corrente.
import pandas as pd

# Importa il caricatore sicuro del file .env.
from src.config.environment import (
    EnvironmentFileError,
    load_application_settings_from_env,
)

# Importa gli errori di configurazione.
from src.config.settings import (
    ApplicationSettings,
    SettingsError,
)

# Importa provider, interfaccia MT5 ed errore dedicato.
from src.data.mt5_provider import (
    MetaTrader5Module,
    MetaTrader5PollingDataProvider,
    MetaTrader5ProviderError,
)


class ConnectionCheckError(RuntimeError):
    """Errore generato durante la verifica della connessione MT5."""


def create_argument_parser() -> argparse.ArgumentParser:
    """Crea il parser delle opzioni da terminale."""

    # Crea il parser principale.
    parser = argparse.ArgumentParser(
        description=(
            "Verifica read-only del collegamento a MetaTrader 5. Lo script non invia ordini."
        )
    )

    # Consente di specificare un file .env differente.
    parser.add_argument(
        "--env-file",
        default=".env",
        help=("Percorso del file .env locale. Valore predefinito: .env"),
    )

    # Consente di verificare la configurazione senza importare MT5.
    parser.add_argument(
        "--config-only",
        action="store_true",
        help=("Verifica solamente il file .env senza collegarsi a MetaTrader 5."),
    )

    # Restituisce il parser configurato.
    return parser


def import_metatrader5_module() -> MetaTrader5Module:
    """Importa il pacchetto MetaTrader5 in modo controllato."""

    try:
        # Importa dinamicamente il pacchetto.
        imported_module = importlib.import_module("MetaTrader5")

    except ModuleNotFoundError as error:
        raise ConnectionCheckError(
            "Pacchetto MetaTrader5 non installato. "
            "Sul PC di test eseguire: "
            "python -m pip install -r requirements-mt5.txt"
        ) from error

    # Converte il modulo nell'interfaccia attesa dal provider.
    return cast(
        MetaTrader5Module,
        imported_module,
    )


def print_separator() -> None:
    """Stampa un separatore leggibile."""

    print("=" * 64)


def print_safe_configuration(
    settings: ApplicationSettings,
) -> None:
    """Mostra la configurazione senza esporre credenziali."""

    # Genera il riepilogo privo di password.
    summary = settings.safe_summary()

    # Mostra l'intestazione.
    print_separator()
    print("AI Trading Indicator - Verifica configurazione")
    print_separator()

    # Mostra solamente valori non sensibili.
    print(f"Modalità applicativa: {summary['app_mode']}")

    print(f"Provider dati: {summary['data_provider']}")

    print(f"Simbolo configurato: {summary['trading_symbol']}")

    print(f"Timeframe minuti: {summary['timeframe_minutes']}")

    print(f"Candele per polling: {summary['mt5_bars_per_poll']}")

    print(f"Login MT5 configurato: {summary['mt5_login_configured']}")

    print(f"Password MT5 configurata: {summary['mt5_password_configured']}")

    print(f"Server MT5 configurato: {summary['mt5_server_configured']}")

    print(f"Percorso terminale: {summary['mt5_terminal_path']}")

    print(f"Paper trading obbligatorio: {summary['paper_trading_only']}")

    print(f"Ordini reali abilitati: {summary['real_orders_enabled']}")

    # Ribadisce il vincolo operativo.
    print_separator()
    print("SICUREZZA: NESSUN ORDINE VERRÀ INVIATO")
    print_separator()


def validate_mt5_settings(
    settings: ApplicationSettings,
) -> None:
    """Verifica i requisiti minimi della configurazione MT5."""

    # Il provider deve essere MT5.
    if settings.data_provider != "MT5":
        raise ConnectionCheckError(
            "DATA_PROVIDER deve essere MT5 per eseguire il controllo della connessione."
        )

    # La modalità deve essere PAPER_ONLY.
    if settings.app_mode != "PAPER_ONLY":
        raise ConnectionCheckError("APP_MODE deve essere PAPER_ONLY.")

    # Il paper trading non può essere disabilitato.
    if not settings.paper_trading_only:
        raise ConnectionCheckError("PAPER_TRADING_ONLY deve essere true.")

    # Gli ordini reali devono restare disabilitati.
    if settings.real_orders_enabled:
        raise ConnectionCheckError("REAL_ORDERS_ENABLED deve essere false.")


def print_candle_summary(
    dataframe: pd.DataFrame,
) -> None:
    """Mostra un riepilogo delle candele ricevute."""

    # Gestisce un polling senza nuove candele.
    if dataframe.empty:
        print("Nessuna nuova candela chiusa rilevata. La connessione è comunque attiva.")

        return

    # Recupera la prima candela ricevuta.
    first_candle = dataframe.iloc[0]

    # Recupera l'ultima candela ricevuta.
    latest_candle = dataframe.iloc[-1]

    # Mostra il numero di candele.
    print(f"Candele chiuse ricevute: {len(dataframe)}")

    # Mostra l'intervallo temporale.
    print(f"Prima candela UTC: {first_candle['timestamp']}")

    print(f"Ultima candela UTC: {latest_candle['timestamp']}")

    # Mostra i valori OHLCV dell'ultima candela.
    print("Ultima candela:")

    print(f"  Open: {latest_candle['open']}")

    print(f"  High: {latest_candle['high']}")

    print(f"  Low: {latest_candle['low']}")

    print(f"  Close: {latest_candle['close']}")

    print(f"  Tick volume: {latest_candle['volume']}")


def run_connection_check(
    settings: ApplicationSettings,
    mt5_module: MetaTrader5Module,
) -> None:
    """Esegue la verifica read-only del terminale MT5."""

    # Crea il provider read-only.
    provider = MetaTrader5PollingDataProvider(
        settings=settings,
        mt5_module=mt5_module,
    )

    # Utilizza il context manager per garantire la disconnessione.
    with provider:
        # Mostra lo stato della connessione.
        print("Terminale MT5: COLLEGATO")
        print("Account MT5: DISPONIBILE")
        print(f"Simbolo: {settings.trading_symbol}")

        print(f"Timeframe minuti: {settings.timeframe_minutes}")

        # Recupera il timestamp UTC corrente.
        current_time_utc = pd.Timestamp.now(tz="UTC")

        # Esegue un singolo polling read-only.
        poll_result = provider.poll(current_time_utc=current_time_utc)

        # Mostra informazioni non sensibili.
        print(f"Provider: {poll_result.provider_name}")

        print(f"Polling UTC: {poll_result.polled_at_utc}")

        print(f"Candele sorgente disponibili: {poll_result.total_source_bars}")

        # Mostra il riepilogo delle candele.
        print_candle_summary(poll_result.new_closed_bars)

    # Conferma la chiusura della connessione.
    print("Connessione MT5: CHIUSA CORRETTAMENTE")

    print_separator()
    print("VERIFICA MT5 READ-ONLY COMPLETATA")
    print("ORDINI REALI: DISABILITATI")
    print_separator()


def main() -> int:
    """Esegue il controllo configurazione o connessione."""

    # Crea e interpreta gli argomenti da terminale.
    parser = create_argument_parser()

    arguments = parser.parse_args()

    # Recupera il percorso del file .env.
    environment_path = Path(arguments.env_file)

    try:
        # Carica e valida il file .env.
        settings = load_application_settings_from_env(
            environment_file=environment_path,
            require_file=True,
            override_existing=True,
        )

        # Verifica i vincoli MT5 e PAPER_ONLY.
        validate_mt5_settings(settings)

        # Mostra la configurazione in forma sicura.
        print_safe_configuration(settings)

        # In modalità config-only non importa MetaTrader5.
        if arguments.config_only:
            print("Configurazione MT5 valida. Connessione non eseguita.")

            return 0

        # Importa il pacchetto MT5 solamente quando necessario.
        mt5_module = import_metatrader5_module()

        # Esegue il controllo read-only.
        run_connection_check(
            settings=settings,
            mt5_module=mt5_module,
        )

        # Restituisce successo.
        return 0

    except (
        EnvironmentFileError,
        SettingsError,
        ConnectionCheckError,
        MetaTrader5ProviderError,
    ) as error:
        # Mostra un errore privo di password.
        print_separator()
        print("VERIFICA MT5 FALLITA")
        print(str(error))
        print("ORDINI REALI: DISABILITATI")
        print_separator()

        # Restituisce un codice di errore.
        return 1


if __name__ == "__main__":
    # Termina il processo usando il codice restituito da main.
    sys.exit(main())
