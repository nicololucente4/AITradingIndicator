"""Avvia il collector MT5 multi-strumento e multi-timeframe."""

# Importa argparse per gestire le opzioni da terminale.
import argparse

# Importa importlib per caricare MetaTrader5 solo quando necessario.
import importlib

# Importa logging per registrare lo stato del collector.
import logging

# Importa signal per gestire Ctrl+C e SIGTERM.
import signal

# Importa sys per restituire il codice di uscita.
import sys

# Importa time per attendere tra due cicli.
import time

# Importa Path per gestire il file di log.
from pathlib import Path

# Importa cast per tipizzare il modulo MetaTrader5.
from typing import cast

# Importa pandas per il timestamp UTC.
import pandas as pd

# Importa il caricatore del file .env.
from src.config.environment import (
    EnvironmentFileError,
    load_application_settings_from_env,
)

# Importa la configurazione del collector.
from src.config.market_collection import (
    MarketCollectionSettings,
    MarketCollectionSettingsError,
    load_market_collection_settings,
)

# Importa la configurazione applicativa.
from src.config.settings import (
    ApplicationSettings,
    SettingsError,
)

# Importa lo storage SQLite delle candele.
from src.data.market_data_store import (
    MarketDataStoreError,
    SQLiteMarketDataStore,
)

# Importa collector, report ed errore.
from src.data.mt5_market_collector import (
    MarketCollectionReport,
    MetaTrader5MarketCollector,
    MetaTrader5MarketCollectorError,
)

# Importa il protocollo del modulo MetaTrader5.
from src.data.mt5_provider import (
    MetaTrader5Module,
)


class MarketCollectorServiceError(RuntimeError):
    """Errore generato dal servizio del collector."""


def create_argument_parser() -> argparse.ArgumentParser:
    """Crea il parser delle opzioni da terminale."""

    # Crea il parser principale.
    parser = argparse.ArgumentParser(
        description=(
            "Raccoglie candele native MT5 per più strumenti "
            "e timeframe. Nessun ordine viene inviato."
        )
    )

    # Permette di selezionare un file .env differente.
    parser.add_argument(
        "--env-file",
        default=".env",
        help=("Percorso del file .env locale. Valore predefinito: .env"),
    )

    # Permette di limitare i cicli durante i collaudi.
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=None,
        help=("Numero massimo di cicli. Se omesso, continua fino a Ctrl+C."),
    )

    # Valida configurazione e componenti senza interrogare MT5.
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=("Valida configurazione e componenti senza avviare il polling."),
    )

    return parser


def validate_maximum_cycles(
    maximum_cycles: int | None,
) -> None:
    """Valida il limite opzionale dei cicli."""

    # None indica esecuzione continua.
    if maximum_cycles is None:
        return

    # Il limite deve essere strettamente positivo.
    if maximum_cycles <= 0:
        raise MarketCollectorServiceError("max-cycles deve essere maggiore di zero.")


def configure_logging() -> logging.Logger:
    """Configura il logger del collector."""

    # Definisce la cartella dei log.
    log_directory = Path("logs")

    # Crea la cartella se necessario.
    log_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Definisce il file dedicato.
    log_path = log_directory / "mt5_market_collector.log"

    # Crea il logger.
    logger = logging.getLogger("ai_trading_indicator.market_collector")

    # Imposta il livello informativo.
    logger.setLevel(logging.INFO)

    # Evita handler duplicati.
    logger.handlers.clear()

    # Definisce il formato dei messaggi.
    formatter = logging.Formatter(
        fmt=("%(asctime)s | %(levelname)s | %(name)s | %(message)s"),
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Crea l'handler del terminale.
    console_handler = logging.StreamHandler()

    console_handler.setLevel(logging.INFO)

    console_handler.setFormatter(formatter)

    # Crea l'handler del file.
    file_handler = logging.FileHandler(
        log_path,
        encoding="utf-8",
    )

    file_handler.setLevel(logging.INFO)

    file_handler.setFormatter(formatter)

    # Registra gli handler.
    logger.addHandler(console_handler)

    logger.addHandler(file_handler)

    # Evita propagazione al root logger.
    logger.propagate = False

    return logger


def import_metatrader5_module() -> MetaTrader5Module:
    """Importa il pacchetto MetaTrader5."""

    try:
        # Importa dinamicamente il modulo ufficiale.
        imported_module = importlib.import_module("MetaTrader5")

    except ModuleNotFoundError as error:
        raise MarketCollectorServiceError(
            "Pacchetto MetaTrader5 non installato. Installare requirements-mt5.txt."
        ) from error

    # Restituisce il modulo tipizzato.
    return cast(
        MetaTrader5Module,
        imported_module,
    )


def validate_application_settings(
    settings: ApplicationSettings,
) -> None:
    """Verifica i vincoli operativi del collector."""

    # Il collector richiede MetaTrader5.
    if settings.data_provider != "MT5":
        raise MarketCollectorServiceError("Il collector richiede DATA_PROVIDER=MT5.")

    # Il paper trading deve essere obbligatorio.
    if not settings.paper_trading_only:
        raise MarketCollectorServiceError("PAPER_TRADING_ONLY deve essere true.")

    # Gli ordini reali devono restare disabilitati.
    if settings.real_orders_enabled:
        raise MarketCollectorServiceError("REAL_ORDERS_ENABLED deve essere false.")


def create_collector(
    *,
    application_settings: ApplicationSettings,
    collection_settings: MarketCollectionSettings,
) -> MetaTrader5MarketCollector:
    """Crea il collector e lo storage condiviso."""

    # Importa il modulo MT5.
    mt5_module = import_metatrader5_module()

    # Crea lo storage persistente delle candele.
    store = SQLiteMarketDataStore(application_settings.market_data_database_path)

    # Crea il collector multi-market.
    return MetaTrader5MarketCollector(
        settings=application_settings,
        mt5_module=mt5_module,
        store=store,
        symbols=collection_settings.symbols,
        timeframes=collection_settings.timeframes,
    )


def print_startup_summary(
    *,
    application_settings: ApplicationSettings,
    collection_settings: MarketCollectionSettings,
    dry_run: bool,
) -> None:
    """Mostra un riepilogo privo di credenziali."""

    # Crea il riepilogo del collector.
    collection_summary = collection_settings.safe_summary()

    # Mostra l'intestazione.
    print("=" * 72)
    print("AI Trading Indicator - MT5 Market Collector")
    print("=" * 72)

    # Mostra i parametri operativi.
    print(f"Modalità: {application_settings.app_mode}")

    print(f"Provider: {application_settings.data_provider}")

    print(f"Simboli: {', '.join(collection_settings.symbols)}")

    print(f"Timeframe nativi: {', '.join(collection_settings.timeframes)}")

    print(f"Dataset per ciclo: {collection_summary['dataset_count']}")

    print(f"Intervallo collector: {collection_settings.interval_seconds} secondi")

    print(f"Candele per dataset: {application_settings.mt5_bars_per_poll}")

    print(f"Database candele: {application_settings.market_data_database_path}")

    print(f"Dry run: {dry_run}")

    # Ribadisce i vincoli di sicurezza.
    print("-" * 72)
    print("PAPER TRADING: OBBLIGATORIO")
    print("ORDINI REALI: DISABILITATI")
    print("INVIO ORDINI: NON IMPLEMENTATO")
    print("=" * 72)


def log_collection_report(
    report: MarketCollectionReport,
    logger: logging.Logger,
) -> None:
    """Registra un riepilogo sintetico del ciclo."""

    # Registra i contatori principali.
    logger.info(
        "Ciclo collector completato. "
        "Dataset richiesti: %s. "
        "Completati: %s. "
        "Falliti: %s. "
        "Nuove candele: %s.",
        report.requested_datasets,
        report.successful_datasets,
        report.failed_datasets,
        report.inserted_rows,
    )

    # Registra solamente i dataset falliti.
    for result in report.results:
        if result.successful:
            continue

        logger.error(
            "Dataset fallito. Simbolo: %s. Timeframe: %s. Messaggio: %s",
            result.symbol,
            result.timeframe,
            result.message,
        )


def run_collector_loop(
    *,
    collector: MetaTrader5MarketCollector,
    collection_settings: MarketCollectionSettings,
    maximum_cycles: int | None,
    logger: logging.Logger,
) -> int:
    """Esegue il collector fino all'arresto o al limite."""

    # Valida il limite ricevuto.
    validate_maximum_cycles(maximum_cycles)

    # Memorizza la richiesta di arresto.
    stop_requested = False

    # Conta i cicli tentati.
    attempted_cycles = 0

    # Conta i cicli senza dataset falliti.
    successful_cycles = 0

    # Conta i cicli con almeno un dataset fallito.
    failed_cycles = 0

    def handle_stop_signal(
        signal_number: int,
        stack_frame: object,
    ) -> None:
        """Richiede l'arresto controllato."""

        # I parametri non sono necessari.
        del signal_number
        del stack_frame

        # Modifica lo stato del ciclo esterno.
        nonlocal stop_requested

        stop_requested = True

        logger.info("Richiesto arresto controllato del collector.")

    # Registra Ctrl+C.
    signal.signal(
        signal.SIGINT,
        handle_stop_signal,
    )

    # Registra SIGTERM se disponibile.
    if hasattr(
        signal,
        "SIGTERM",
    ):
        signal.signal(
            signal.SIGTERM,
            handle_stop_signal,
        )

    # Registra l'avvio.
    logger.info(
        "Avvio collector MT5 multi-market. Dataset per ciclo: %s.",
        collector.dataset_count,
    )

    try:
        # Continua fino alla richiesta di arresto.
        while not stop_requested:
            # Rispetta il limite opzionale.
            if maximum_cycles is not None and attempted_cycles >= maximum_cycles:
                break

            # Registra il tentativo.
            attempted_cycles += 1

            try:
                # Esegue il ciclo con timestamp UTC.
                report = collector.collect(pd.Timestamp.now(tz="UTC"))

                # Registra il report.
                log_collection_report(
                    report,
                    logger,
                )

                # Classifica il ciclo.
                if report.failed_datasets == 0:
                    successful_cycles += 1
                else:
                    failed_cycles += 1

            except Exception as error:
                # Registra il fallimento completo del ciclo.
                failed_cycles += 1

                logger.error(
                    "Ciclo collector fallito. Tipo: %s. Messaggio: %s",
                    type(error).__name__,
                    str(error),
                )

                # Chiude la connessione non affidabile.
                collector.disconnect()

            # Non attende dopo l'ultimo ciclo configurato.
            if maximum_cycles is not None and attempted_cycles >= maximum_cycles:
                continue

            # Non attende dopo la richiesta di arresto.
            if stop_requested:
                continue

            # Attende prima del ciclo successivo.
            time.sleep(float(collection_settings.interval_seconds))

    finally:
        # Garantisce la chiusura di MT5.
        collector.disconnect()

    # Mostra il riepilogo finale.
    print("=" * 72)
    print("COLLECTOR MT5 TERMINATO")
    print(f"Cicli tentati: {attempted_cycles}")
    print(f"Cicli completati senza errori: {successful_cycles}")
    print(f"Cicli con errori: {failed_cycles}")
    print("ORDINI REALI: DISABILITATI")
    print("=" * 72)

    # Restituisce errore solamente se nessun ciclo è riuscito.
    if successful_cycles == 0 and failed_cycles > 0:
        return 1

    return 0


def main() -> int:
    """Carica la configurazione e avvia il collector."""

    # Interpreta gli argomenti.
    parser = create_argument_parser()

    arguments = parser.parse_args()

    # Configura il logging.
    logger = configure_logging()

    try:
        # Valida il limite dei cicli.
        validate_maximum_cycles(arguments.max_cycles)

        # Carica la configurazione applicativa dal file .env.
        application_settings = load_application_settings_from_env(
            environment_file=(arguments.env_file),
            require_file=True,
            override_existing=True,
        )

        # Carica la configurazione del collector
        # dalle variabili già importate dal file .env.
        collection_settings = load_market_collection_settings()

        # Verifica i vincoli applicativi.
        validate_application_settings(application_settings)

        # Mostra la configurazione sicura.
        print_startup_summary(
            application_settings=(application_settings),
            collection_settings=(collection_settings),
            dry_run=(arguments.dry_run),
        )

        # Il dry run non importa né collega MT5.
        if arguments.dry_run:
            print("DRY RUN COMPLETATO: configurazione collector valida.")

            return 0

        # Crea il collector reale.
        collector = create_collector(
            application_settings=(application_settings),
            collection_settings=(collection_settings),
        )

        # Avvia il ciclo continuo.
        return run_collector_loop(
            collector=collector,
            collection_settings=(collection_settings),
            maximum_cycles=(arguments.max_cycles),
            logger=logger,
        )

    except (
        EnvironmentFileError,
        SettingsError,
        MarketCollectionSettingsError,
        MarketDataStoreError,
        MetaTrader5MarketCollectorError,
        MarketCollectorServiceError,
    ) as error:
        # Registra l'errore senza credenziali.
        logger.error(
            "Avvio collector fallito. Tipo: %s. Messaggio: %s",
            type(error).__name__,
            str(error),
        )

        print("=" * 72)
        print("AVVIO COLLECTOR MT5 FALLITO")
        print(str(error))
        print("ORDINI REALI: DISABILITATI")
        print("=" * 72)

        return 1


if __name__ == "__main__":
    # Termina il processo con il codice restituito.
    sys.exit(main())
