"""Test automatici del runner Live Paper continuo."""

# Importa pandas per creare timestamp UTC.
import pandas as pd

# Importa pytest per verificare gli errori attesi.
import pytest

# Importa runner e configurazione.
from src.monitoring.continuous_runner import (
    ContinuousLivePaperRunner,
    ContinuousRunnerConfig,
    ContinuousRunnerError,
    validate_continuous_runner_config,
)


def create_utc_clock() -> pd.Timestamp:
    """Restituisce un timestamp UTC deterministico."""

    return pd.Timestamp(
        "2026-08-20 12:00:00",
        tz="UTC",
    )


def test_runner_executes_configured_cycles() -> None:
    """Verifica l'esecuzione del numero richiesto di cicli."""

    # Registra i timestamp ricevuti.
    received_times: list[pd.Timestamp] = []

    # Crea un callback deterministico.
    def cycle_callback(
        current_time: pd.Timestamp,
    ) -> None:
        received_times.append(current_time)

    # Registra le attese senza fermare realmente i test.
    sleep_calls: list[float] = []

    # Crea il runner.
    runner = ContinuousLivePaperRunner(
        cycle_callback=cycle_callback,
        config=ContinuousRunnerConfig(
            poll_interval_seconds=5,
            maximum_cycles=3,
        ),
        sleep_function=(sleep_calls.append),
        utc_now_function=create_utc_clock,
    )

    # Avvia il runner.
    report = runner.run()

    # Verifica i cicli completati.
    assert report.attempted_cycles == 3
    assert report.successful_cycles == 3
    assert report.failed_cycles == 0

    # Il callback deve essere stato chiamato tre volte.
    assert len(received_times) == 3

    # Tra tre cicli servono due attese.
    assert sleep_calls == [
        5.0,
        5.0,
    ]


def test_runner_continues_after_temporary_error() -> None:
    """Verifica il recupero dopo un errore temporaneo."""

    # Conta i tentativi.
    attempts = 0

    def cycle_callback(
        current_time: pd.Timestamp,
    ) -> None:
        # Il timestamp deve essere UTC.
        assert str(current_time.tz) == "UTC"

        nonlocal attempts
        attempts += 1

        # Il primo ciclo fallisce.
        if attempts == 1:
            raise RuntimeError("temporary error")

    # Crea il runner.
    runner = ContinuousLivePaperRunner(
        cycle_callback=cycle_callback,
        config=ContinuousRunnerConfig(
            poll_interval_seconds=1,
            maximum_consecutive_errors=3,
            maximum_cycles=3,
        ),
        sleep_function=lambda _: None,
        utc_now_function=create_utc_clock,
    )

    # Avvia il runner.
    report = runner.run()

    # Il servizio deve recuperare.
    assert report.attempted_cycles == 3
    assert report.successful_cycles == 2
    assert report.failed_cycles == 1

    # Il massimo osservato è un solo errore consecutivo.
    assert report.maximum_observed_consecutive_errors == 1


def test_runner_stops_after_consecutive_errors() -> None:
    """Verifica l'arresto dopo troppi errori consecutivi."""

    # Il callback fallisce sempre.
    def failing_callback(
        current_time: pd.Timestamp,
    ) -> None:
        del current_time

        raise RuntimeError("persistent error")

    # Crea il runner.
    runner = ContinuousLivePaperRunner(
        cycle_callback=failing_callback,
        config=ContinuousRunnerConfig(
            poll_interval_seconds=1,
            maximum_consecutive_errors=2,
            maximum_cycles=10,
        ),
        sleep_function=lambda _: None,
        utc_now_function=create_utc_clock,
    )

    # Avvia il runner.
    report = runner.run()

    # Deve fermarsi al secondo errore.
    assert report.attempted_cycles == 2
    assert report.successful_cycles == 0
    assert report.failed_cycles == 2

    assert report.maximum_observed_consecutive_errors == 2


def test_callback_can_request_controlled_stop() -> None:
    """Verifica l'arresto richiesto dal servizio."""

    # Il riferimento viene assegnato dopo la funzione.
    runner: ContinuousLivePaperRunner

    def stopping_callback(
        current_time: pd.Timestamp,
    ) -> None:
        del current_time

        runner.request_stop()

    # Crea il runner.
    runner = ContinuousLivePaperRunner(
        cycle_callback=stopping_callback,
        config=ContinuousRunnerConfig(
            poll_interval_seconds=1,
            maximum_cycles=None,
        ),
        sleep_function=lambda _: None,
        utc_now_function=create_utc_clock,
    )

    # Avvia il runner.
    report = runner.run()

    # Deve essere stato eseguito un solo ciclo.
    assert report.attempted_cycles == 1
    assert report.successful_cycles == 1
    assert report.stopped_by_request is True


def test_naive_clock_is_rejected_as_cycle_error() -> None:
    """Verifica che un orologio senza timezone venga rifiutato."""

    # Crea un runner con orologio senza timezone.
    runner = ContinuousLivePaperRunner(
        cycle_callback=lambda _: None,
        config=ContinuousRunnerConfig(
            poll_interval_seconds=1,
            maximum_consecutive_errors=1,
            maximum_cycles=1,
        ),
        sleep_function=lambda _: None,
        utc_now_function=lambda: pd.Timestamp("2026-08-20 12:00:00"),
    )

    # Il ciclo viene contato come fallito.
    report = runner.run()

    assert report.attempted_cycles == 1
    assert report.successful_cycles == 0
    assert report.failed_cycles == 1


def test_invalid_poll_interval_is_rejected() -> None:
    """Verifica il rifiuto di intervalli non positivi."""

    with pytest.raises(
        ContinuousRunnerError,
        match="poll_interval_seconds",
    ):
        validate_continuous_runner_config(
            ContinuousRunnerConfig(
                poll_interval_seconds=0,
            )
        )


def test_invalid_error_limit_is_rejected() -> None:
    """Verifica il rifiuto di un limite errori non positivo."""

    with pytest.raises(
        ContinuousRunnerError,
        match="maximum_consecutive_errors",
    ):
        validate_continuous_runner_config(
            ContinuousRunnerConfig(
                maximum_consecutive_errors=0,
            )
        )


def test_non_paper_mode_is_rejected() -> None:
    """Verifica il blocco di modalità non simulate."""

    with pytest.raises(
        ContinuousRunnerError,
        match="paper_trading_only",
    ):
        validate_continuous_runner_config(
            ContinuousRunnerConfig(
                paper_trading_only=False,
            )
        )


def test_callback_must_be_callable() -> None:
    """Verifica il tipo del callback."""

    with pytest.raises(
        TypeError,
        match="richiamabile",
    ):
        ContinuousLivePaperRunner(
            cycle_callback=None,  # type: ignore[arg-type]
        )
