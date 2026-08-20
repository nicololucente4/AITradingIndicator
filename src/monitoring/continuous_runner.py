"""Esecuzione continua e controllata del sistema Live Paper."""

# Importa logging per registrare lo stato del servizio.
import logging

# Importa time per attendere tra due cicli.
import time

# Importa Callable per rendere il runner testabile.
from collections.abc import Callable

# Importa dataclass per la configurazione immutabile.
from dataclasses import dataclass

# Importa pandas per gestire timestamp UTC.
import pandas as pd


class ContinuousRunnerError(ValueError):
    """Errore generato dalla configurazione del runner continuo."""


@dataclass(frozen=True)
class ContinuousRunnerConfig:
    """Configurazione del servizio Live Paper continuo."""

    # Numero di secondi tra due polling.
    poll_interval_seconds: int = 5

    # Numero massimo di errori consecutivi consentiti.
    maximum_consecutive_errors: int = 10

    # Numero massimo di cicli.
    # None indica esecuzione continua.
    maximum_cycles: int | None = None

    # Modalità obbligatoriamente simulata.
    paper_trading_only: bool = True


@dataclass(frozen=True)
class ContinuousRunnerReport:
    """Riepilogo finale dell'esecuzione continua."""

    # Numero totale di cicli tentati.
    attempted_cycles: int

    # Numero di cicli completati correttamente.
    successful_cycles: int

    # Numero totale di cicli falliti.
    failed_cycles: int

    # Numero massimo di errori consecutivi osservati.
    maximum_observed_consecutive_errors: int

    # Indica se il runner è stato fermato manualmente.
    stopped_by_request: bool

    # Modalità operativa.
    operating_mode: str = "LIVE_PAPER"


def validate_continuous_runner_config(
    config: ContinuousRunnerConfig,
) -> None:
    """Verifica la configurazione del runner continuo."""

    # L'intervallo deve essere positivo.
    if config.poll_interval_seconds <= 0:
        raise ContinuousRunnerError("poll_interval_seconds deve essere maggiore di zero.")

    # Il numero massimo di errori deve essere positivo.
    if config.maximum_consecutive_errors <= 0:
        raise ContinuousRunnerError("maximum_consecutive_errors deve essere maggiore di zero.")

    # Se valorizzato, il numero massimo di cicli deve essere positivo.
    if config.maximum_cycles is not None and config.maximum_cycles <= 0:
        raise ContinuousRunnerError("maximum_cycles deve essere maggiore di zero oppure None.")

    # La modalità reale non è consentita.
    if not config.paper_trading_only:
        raise ContinuousRunnerError("Il runner richiede paper_trading_only=true.")


class ContinuousLivePaperRunner:
    """Esegue cicli Live Paper fino a una richiesta di arresto."""

    def __init__(
        self,
        cycle_callback: Callable[
            [pd.Timestamp],
            object,
        ],
        config: ContinuousRunnerConfig | None = None,
        *,
        sleep_function: Callable[
            [float],
            None,
        ] = time.sleep,
        utc_now_function: Callable[
            [],
            pd.Timestamp,
        ]
        | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """Inizializza il runner continuo."""

        # Il callback deve essere richiamabile.
        if not callable(cycle_callback):
            raise TypeError("cycle_callback deve essere richiamabile.")

        # Usa la configurazione predefinita se necessario.
        self._config = config or ContinuousRunnerConfig()

        # Valida la configurazione.
        validate_continuous_runner_config(self._config)

        # Salva il callback che esegue il ciclo coordinato.
        self._cycle_callback = cycle_callback

        # Salva la funzione di attesa.
        self._sleep_function = sleep_function

        # Usa una funzione UTC predefinita quando non specificata.
        self._utc_now_function = utc_now_function or self._default_utc_now

        # Usa un logger dedicato se non specificato.
        self._logger = logger or logging.getLogger("ai_trading_indicator.live_paper")

        # Il runner inizialmente non deve arrestarsi.
        self._stop_requested = False

    @staticmethod
    def _default_utc_now() -> pd.Timestamp:
        """Restituisce il timestamp UTC corrente."""

        return pd.Timestamp.now(tz="UTC")

    @property
    def stop_requested(self) -> bool:
        """Indica se è stato richiesto l'arresto."""

        return self._stop_requested

    def request_stop(self) -> None:
        """Richiede l'arresto controllato del runner."""

        # Il ciclo corrente viene completato.
        self._stop_requested = True

        # Registra la richiesta senza dati sensibili.
        self._logger.info("Richiesto arresto controllato del servizio Live Paper.")

    def _validate_cycle_time(
        self,
        current_time: pd.Timestamp,
    ) -> pd.Timestamp:
        """Valida e normalizza il timestamp del ciclo."""

        # Converte il valore ricevuto.
        selected_time = pd.Timestamp(current_time)

        # Il timestamp deve avere una timezone.
        if selected_time.tzinfo is None:
            raise ContinuousRunnerError("Il timestamp del ciclo deve includere una timezone.")

        # Normalizza in UTC.
        return selected_time.tz_convert("UTC")

    def run(self) -> ContinuousRunnerReport:
        """Avvia il servizio Live Paper continuo."""

        # Inizializza i contatori.
        attempted_cycles = 0
        successful_cycles = 0
        failed_cycles = 0
        consecutive_errors = 0
        maximum_observed_errors = 0

        # Registra l'avvio.
        self._logger.info("Avvio servizio Live Paper continuo. Modalità PAPER_ONLY.")

        # Continua finché non viene richiesto l'arresto.
        while not self._stop_requested:
            # Verifica il limite massimo dei cicli.
            if (
                self._config.maximum_cycles is not None
                and attempted_cycles >= self._config.maximum_cycles
            ):
                break

            # Registra un nuovo tentativo.
            attempted_cycles += 1

            try:
                # Recupera e valida il momento corrente.
                current_time = self._validate_cycle_time(self._utc_now_function())

                # Esegue il ciclo coordinato.
                self._cycle_callback(current_time)

                # Registra il ciclo completato.
                successful_cycles += 1

                # Azzera gli errori consecutivi.
                consecutive_errors = 0

                self._logger.info(
                    "Ciclo Live Paper completato alle %s.",
                    current_time.isoformat(),
                )

            except Exception as error:
                # Aggiorna i contatori degli errori.
                failed_cycles += 1
                consecutive_errors += 1

                maximum_observed_errors = max(
                    maximum_observed_errors,
                    consecutive_errors,
                )

                # Registra solo il tipo e il messaggio dell'errore.
                self._logger.error(
                    "Ciclo Live Paper fallito. "
                    "Errore consecutivo %s di %s. "
                    "Tipo: %s. Messaggio: %s",
                    consecutive_errors,
                    self._config.maximum_consecutive_errors,
                    type(error).__name__,
                    str(error),
                )

                # Interrompe il servizio dopo troppi errori.
                if consecutive_errors >= self._config.maximum_consecutive_errors:
                    self._logger.critical("Numero massimo di errori consecutivi raggiunto.")

                    break

            # Non attende dopo l'ultimo ciclo configurato.
            if (
                self._config.maximum_cycles is not None
                and attempted_cycles >= self._config.maximum_cycles
            ):
                continue

            # Non attende dopo una richiesta di arresto.
            if self._stop_requested:
                continue

            # Attende prima del prossimo polling.
            self._sleep_function(float(self._config.poll_interval_seconds))

        # Costruisce il report finale.
        report = ContinuousRunnerReport(
            attempted_cycles=attempted_cycles,
            successful_cycles=successful_cycles,
            failed_cycles=failed_cycles,
            maximum_observed_consecutive_errors=(maximum_observed_errors),
            stopped_by_request=(self._stop_requested),
        )

        # Registra l'arresto.
        self._logger.info(
            "Servizio Live Paper arrestato. Cicli tentati: %s. Completati: %s. Falliti: %s.",
            report.attempted_cycles,
            report.successful_cycles,
            report.failed_cycles,
        )

        # Restituisce il riepilogo.
        return report
