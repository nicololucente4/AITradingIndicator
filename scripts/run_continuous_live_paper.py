"""Avvia il servizio continuo AI Trading Indicator in modalità PAPER_ONLY."""

# Importa argparse per gestire le opzioni da terminale.
import argparse

# Importa importlib per caricare MetaTrader5 solo quando richiesto.
import importlib

# Importa logging per registrare lo stato del servizio.
import logging

# Importa signal per gestire Ctrl+C e l'arresto del processo.
import signal

# Importa sys per restituire il codice di uscita.
import sys

# Importa Path per gestire database, configurazioni e log.
from pathlib import Path

# Importa cast per tipizzare il modulo MetaTrader5.
from typing import cast

# Importa il caricatore sicuro del file .env.
from src.config.environment import (
    EnvironmentFileError,
    load_application_settings_from_env,
)

# Importa configurazione ed errore applicativo.
from src.config.settings import (
    ApplicationSettings,
    SettingsError,
)

# Importa l'interfaccia centrale dei provider.
from src.data.live_provider import (
    FilePollingDataProvider,
    LiveDataProvider,
)

# Importa l'archivio SQLite condiviso delle candele.
from src.data.market_data_store import (
    SQLiteMarketDataStore,
)

# Importa il catalogo centralizzato dei timeframe.
from src.data.market_timeframes import (
    get_timeframe_by_minutes,
)

# Importa il provider MetaTrader5 read-only.
from src.data.mt5_provider import (
    MetaTrader5Module,
    MetaTrader5PollingDataProvider,
    MetaTrader5ProviderError,
)

# Importa il decorator che salva automaticamente le candele.
from src.data.persisting_provider import (
    PersistingLiveDataProvider,
)

# Importa il runner continuo.
from src.monitoring.continuous_runner import (
    ContinuousLivePaperRunner,
    ContinuousRunnerConfig,
    ContinuousRunnerError,
)

# Importa il coordinatore Live Paper.
from src.monitoring.live_paper_coordinator import (
    LivePaperCoordinator,
)

# Importa il Live Paper Engine.
from src.monitoring.live_paper_engine import (
    LivePaperEngine,
    LivePaperEngineConfig,
)

# Importa il vero processore ML registrato.
from src.monitoring.live_processor import (
    LiveMLProcessorConfig,
    LiveMLProcessorError,
    RegisteredLiveMLProcessor,
)

# Importa Outcome Tracker e relativa configurazione.
from src.monitoring.outcome_tracker import (
    OutcomeTracker,
    OutcomeTrackerConfig,
)

# Percorso predefinito dell'archivio condiviso delle candele.
DEFAULT_MARKET_DATA_DATABASE_PATH = Path("data/live_paper/market_data.db")


class ContinuousServiceError(RuntimeError):
    """Errore generato dalla costruzione del servizio continuo."""


def create_argument_parser() -> argparse.ArgumentParser:
    """Crea il parser delle opzioni da terminale."""

    # Crea il parser principale.
    parser = argparse.ArgumentParser(
        description=(
            "Avvia AI Trading Indicator in modalità Live Paper continua. "
            "Nessun ordine viene inviato."
        )
    )

    # Consente di selezionare il file locale di configurazione.
    parser.add_argument(
        "--env-file",
        default=".env",
        help=("Percorso del file .env locale. Valore predefinito: .env"),
    )

    # Permette un numero limitato di cicli per i collaudi.
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=None,
        help=("Numero massimo di cicli. Se omesso, il servizio continua fino a Ctrl+C."),
    )

    # Consente di controllare tutto senza avviare il ciclo.
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=("Valida configurazione e componenti senza avviare il servizio continuo."),
    )

    # Permette di specificare un archivio candele differente.
    parser.add_argument(
        "--market-data-db",
        default=str(DEFAULT_MARKET_DATA_DATABASE_PATH),
        help=(
            "Percorso del database SQLite delle candele. "
            "Valore predefinito: data/live_paper/market_data.db"
        ),
    )

    return parser


def configure_logging() -> logging.Logger:
    """Configura log su terminale e file locale."""

    # Definisce e crea la cartella dei log.
    log_directory = Path("logs")

    log_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Definisce il file di log.
    log_path = log_directory / "continuous_live_paper.log"

    # Crea il logger dedicato.
    logger = logging.getLogger("ai_trading_indicator.live_paper")

    logger.setLevel(logging.INFO)

    # Evita handler duplicati.
    logger.handlers.clear()

    # Definisce il formato comune.
    formatter = logging.Formatter(
        fmt=("%(asctime)s | %(levelname)s | %(name)s | %(message)s"),
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Crea l'output sul terminale.
    console_handler = logging.StreamHandler()

    console_handler.setLevel(logging.INFO)

    console_handler.setFormatter(formatter)

    # Crea l'output sul file.
    file_handler = logging.FileHandler(
        log_path,
        encoding="utf-8",
    )

    file_handler.setLevel(logging.INFO)

    file_handler.setFormatter(formatter)

    # Registra entrambi gli handler.
    logger.addHandler(console_handler)

    logger.addHandler(file_handler)

    # Evita la propagazione al logger root.
    logger.propagate = False

    return logger


def import_metatrader5_module() -> MetaTrader5Module:
    """Importa MetaTrader5 solo quando il provider selezionato è MT5."""

    try:
        # Importa dinamicamente il modulo ufficiale.
        imported_module = importlib.import_module("MetaTrader5")

    except ModuleNotFoundError as error:
        raise ContinuousServiceError(
            "Pacchetto MetaTrader5 non installato. "
            "Eseguire: python -m pip install "
            "-r requirements-mt5.txt"
        ) from error

    return cast(
        MetaTrader5Module,
        imported_module,
    )


def create_base_provider(
    settings: ApplicationSettings,
) -> LiveDataProvider:
    """Crea il provider FILE o MT5 senza persistenza."""

    # Crea il provider file.
    if settings.data_provider == "FILE":
        # Verifica la presenza del dataset.
        if not settings.file_provider_path.exists():
            raise ContinuousServiceError(
                f"Dataset del provider FILE non trovato: {settings.file_provider_path.resolve()}."
            )

        return FilePollingDataProvider(
            file_path=(settings.file_provider_path),
            timeframe_minutes=(settings.timeframe_minutes),
        )

    # Crea il provider MT5 read-only.
    if settings.data_provider == "MT5":
        # Importa MT5 solamente in questo caso.
        mt5_module = import_metatrader5_module()

        return MetaTrader5PollingDataProvider(
            settings=settings,
            mt5_module=mt5_module,
        )

    # Controllo difensivo.
    raise ContinuousServiceError(f"Provider dati non supportato: {settings.data_provider}.")


def create_persisting_provider(
    settings: ApplicationSettings,
    market_data_database_path: Path,
) -> PersistingLiveDataProvider:
    """Crea il provider con persistenza automatica delle candele."""

    # Il percorso non può essere vuoto.
    if not str(market_data_database_path).strip():
        raise ContinuousServiceError("Il percorso del database candele non può essere vuoto.")

    # Recupera il codice timeframe dal catalogo centrale.
    timeframe = get_timeframe_by_minutes(settings.timeframe_minutes)

    # Crea il provider originale.
    base_provider = create_base_provider(settings)

    # Crea l'archivio persistente.
    market_data_store = SQLiteMarketDataStore(market_data_database_path)

    # Restituisce il decorator persistente.
    return PersistingLiveDataProvider(
        provider=base_provider,
        store=market_data_store,
        symbol=settings.trading_symbol,
        timeframe=timeframe.code,
    )


def create_processor(
    settings: ApplicationSettings,
) -> RegisteredLiveMLProcessor:
    """Crea il processore del modello ML registrato."""

    # Il modello corrente è sviluppato esclusivamente per M15.
    if settings.timeframe_minutes != 15:
        raise ContinuousServiceError(
            "Il modello gradient_boosting_0.1.0 richiede TIMEFRAME_MINUTES=15."
        )

    # Crea il processore ML.
    processor = RegisteredLiveMLProcessor(
        LiveMLProcessorConfig(
            registry_path=Path("models/registry.json"),
            model_version=("gradient_boosting_0.1.0"),
            timeframe_minutes=(settings.timeframe_minutes),
            allowed_model_statuses=(
                "CANDIDATE",
                "APPROVED",
            ),
            paper_trading_only=True,
        )
    )

    # Verifica registry e file runtime.
    processor.validate_runtime_files()

    return processor


def create_coordinator(
    settings: ApplicationSettings,
    provider: LiveDataProvider,
    processor: RegisteredLiveMLProcessor,
) -> LivePaperCoordinator:
    """Crea engine, Outcome Tracker e coordinatore."""

    # Crea il Live Paper Engine.
    engine = LivePaperEngine(
        provider=provider,
        processor=processor,
        config=LivePaperEngineConfig(
            minimum_history_bars=(settings.minimum_history_bars),
            database_path=str(settings.live_paper_database_path),
            paper_trading_only=True,
        ),
    )

    # Crea l'Outcome Tracker sullo stesso database.
    outcome_tracker = OutcomeTracker(
        database_path=(settings.live_paper_database_path),
        config=OutcomeTrackerConfig(
            maximum_holding_bars=(settings.maximum_holding_bars),
            stop_first_when_ambiguous=True,
            paper_trading_only=True,
        ),
    )

    return LivePaperCoordinator(
        engine=engine,
        outcome_tracker=outcome_tracker,
    )


def print_startup_summary(
    settings: ApplicationSettings,
    processor: RegisteredLiveMLProcessor,
    provider: PersistingLiveDataProvider,
    dry_run: bool,
) -> None:
    """Mostra un riepilogo privo di credenziali."""

    # Recupera i riepiloghi sicuri.
    settings_summary = settings.safe_summary()

    processor_summary = processor.safe_summary()

    # Mostra l'intestazione.
    print("=" * 68)
    print("AI Trading Indicator - Continuous Live Paper")
    print("=" * 68)

    # Mostra i parametri non sensibili.
    print(f"Modalità: {settings_summary['app_mode']}")

    print(f"Provider: {settings_summary['data_provider']}")

    print(f"Simbolo: {settings_summary['trading_symbol']}")

    print(f"Timeframe operativo: {settings_summary['timeframe_minutes']} minuti")

    print(f"Intervallo polling: {settings_summary['poll_interval_seconds']} secondi")

    print(f"Database segnali ed esiti: {settings_summary['live_paper_database_path']}")

    print(f"Database candele: {provider.store.database_path}")

    print(f"Timeframe archivio: {provider.timeframe}")

    print(f"Modello: {processor_summary['model_version']}")

    print(f"Stati modello accettati: {processor_summary['allowed_model_statuses']}")

    print(f"Confidenza minima: {processor_summary['minimum_confidence']}")

    print(f"Dry run: {dry_run}")

    # Ribadisce i vincoli di sicurezza.
    print("-" * 68)
    print("PAPER TRADING: OBBLIGATORIO")
    print("ORDINI REALI: DISABILITATI")
    print("INVIO ORDINI: NON IMPLEMENTATO")
    print("=" * 68)


def disconnect_provider(
    provider: LiveDataProvider,
    logger: logging.Logger,
) -> None:
    """Chiude il provider se espone il metodo disconnect."""

    # Recupera dinamicamente il metodo.
    disconnect_method = getattr(
        provider,
        "disconnect",
        None,
    )

    # Chiude solamente provider che lo supportano.
    if callable(disconnect_method):
        try:
            disconnect_method()

        except Exception as error:
            logger.error(
                "Errore durante la chiusura del provider. Tipo: %s. Messaggio: %s",
                type(error).__name__,
                str(error),
            )


def main() -> int:
    """Costruisce e avvia il servizio continuo."""

    # Interpreta gli argomenti.
    parser = create_argument_parser()

    arguments = parser.parse_args()

    # Configura il logging.
    logger = configure_logging()

    # Inizializza riferimenti usati nella chiusura.
    provider: LiveDataProvider | None = None

    runner: ContinuousLivePaperRunner | None = None

    try:
        # Carica il file .env.
        settings = load_application_settings_from_env(
            environment_file=(arguments.env_file),
            require_file=True,
            override_existing=True,
        )

        # Verifica i vincoli di sicurezza.
        if not settings.paper_trading_only:
            raise ContinuousServiceError("PAPER_TRADING_ONLY deve essere true.")

        if settings.real_orders_enabled:
            raise ContinuousServiceError("REAL_ORDERS_ENABLED deve essere false.")

        # Converte il percorso dell'archivio candele.
        market_data_database_path = Path(arguments.market_data_db)

        # Crea provider e archivio persistente.
        persisting_provider = create_persisting_provider(
            settings=settings,
            market_data_database_path=(market_data_database_path),
        )

        # Mantiene il riferimento per la chiusura finale.
        provider = persisting_provider

        # Crea il processore ML.
        processor = create_processor(settings)

        # Crea il coordinatore.
        coordinator = create_coordinator(
            settings=settings,
            provider=persisting_provider,
            processor=processor,
        )

        # Mostra il riepilogo sicuro.
        print_startup_summary(
            settings=settings,
            processor=processor,
            provider=persisting_provider,
            dry_run=arguments.dry_run,
        )

        # Il dry run termina senza eseguire polling.
        if arguments.dry_run:
            print("DRY RUN COMPLETATO: configurazione e componenti validi.")

            return 0

        # Crea il runner continuo.
        runner = ContinuousLivePaperRunner(
            cycle_callback=(coordinator.run_cycle),
            config=ContinuousRunnerConfig(
                poll_interval_seconds=(settings.poll_interval_seconds),
                maximum_consecutive_errors=10,
                maximum_cycles=(arguments.max_cycles),
                paper_trading_only=True,
            ),
            logger=logger,
        )

        # Gestisce Ctrl+C e SIGTERM.
        def handle_stop_signal(
            signal_number: int,
            stack_frame: object,
        ) -> None:
            """Richiede un arresto controllato."""

            # I parametri non vengono utilizzati.
            del signal_number
            del stack_frame

            # Richiede l'arresto al runner.
            if runner is not None:
                runner.request_stop()

        # Registra Ctrl+C.
        signal.signal(
            signal.SIGINT,
            handle_stop_signal,
        )

        # Registra SIGTERM quando disponibile.
        if hasattr(
            signal,
            "SIGTERM",
        ):
            signal.signal(
                signal.SIGTERM,
                handle_stop_signal,
            )

        # Avvia il servizio.
        report = runner.run()

        # Mostra il riepilogo finale.
        print("=" * 68)
        print("SERVIZIO LIVE PAPER TERMINATO")

        print(f"Cicli tentati: {report.attempted_cycles}")

        print(f"Cicli completati: {report.successful_cycles}")

        print(f"Cicli falliti: {report.failed_cycles}")

        print(f"Arresto richiesto: {report.stopped_by_request}")

        print("ORDINI REALI: DISABILITATI")
        print("=" * 68)

        # Restituisce errore se tutti i cicli sono falliti.
        if report.successful_cycles == 0 and report.failed_cycles > 0:
            return 1

        return 0

    except (
        EnvironmentFileError,
        SettingsError,
        ContinuousServiceError,
        ContinuousRunnerError,
        LiveMLProcessorError,
        MetaTrader5ProviderError,
    ) as error:
        # Registra l'errore senza informazioni sensibili.
        logger.error(
            "Avvio servizio fallito. Tipo: %s. Messaggio: %s",
            type(error).__name__,
            str(error),
        )

        print("=" * 68)
        print("AVVIO LIVE PAPER FALLITO")
        print(str(error))
        print("ORDINI REALI: DISABILITATI")
        print("=" * 68)

        return 1

    finally:
        # Garantisce la chiusura del provider.
        if provider is not None:
            disconnect_provider(
                provider=provider,
                logger=logger,
            )


if __name__ == "__main__":
    # Termina il processo con il codice restituito.
    sys.exit(main())
