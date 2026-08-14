"""Coordinamento di segnali, esiti e statistiche Live Paper."""

# Importa dataclass per rappresentare il report del ciclo completo.
from dataclasses import dataclass

# Importa pandas per gestire timestamp e DataFrame.
import pandas as pd

# Importa il Live Paper Engine.
from src.monitoring.live_paper_engine import (
    LivePaperCycleReport,
    LivePaperEngine,
)

# Importa il generatore delle statistiche.
from src.monitoring.live_paper_report import (
    LivePaperStatistics,
    generate_live_paper_statistics,
)

# Importa l'Outcome Tracker.
from src.monitoring.outcome_tracker import (
    OutcomeTracker,
    OutcomeUpdateReport,
)


class LivePaperCoordinatorError(ValueError):
    """Errore generato dal coordinatore Live Paper."""


@dataclass(frozen=True)
class LivePaperCoordinatorReport:
    """Risultato completo di un ciclo Live Paper."""

    # Risultato del polling e della generazione del segnale.
    engine_report: LivePaperCycleReport

    # Risultato dell'aggiornamento degli esiti.
    outcome_report: OutcomeUpdateReport

    # Statistiche aggiornate della sessione.
    statistics: LivePaperStatistics


class LivePaperCoordinator:
    """Coordina segnali, esiti e statistiche Live Paper."""

    def __init__(
        self,
        engine: LivePaperEngine,
        outcome_tracker: OutcomeTracker,
    ) -> None:
        """Inizializza il coordinatore."""

        # Verifica il tipo del Live Paper Engine.
        if not isinstance(engine, LivePaperEngine):
            raise TypeError("engine deve essere un'istanza di LivePaperEngine.")

        # Verifica il tipo dell'Outcome Tracker.
        if not isinstance(outcome_tracker, OutcomeTracker):
            raise TypeError("outcome_tracker deve essere un'istanza di OutcomeTracker.")

        # I due componenti devono utilizzare lo stesso database.
        if engine.database_path.resolve() != outcome_tracker.database_path.resolve():
            raise LivePaperCoordinatorError(
                "Live Paper Engine e Outcome Tracker devono utilizzare lo stesso database."
            )

        # Salva i componenti verificati.
        self._engine = engine
        self._outcome_tracker = outcome_tracker

    def run_cycle(
        self,
        current_time_utc: pd.Timestamp,
    ) -> LivePaperCoordinatorReport:
        """Esegue un ciclo completo Live Paper.

        Il ciclo:

        1. interroga il provider;
        2. aggiorna lo storico;
        3. genera e salva il nuovo segnale;
        4. rivaluta gli esiti ancora pendenti;
        5. aggiorna le statistiche.

        Args:
            current_time_utc: Momento UTC del ciclo.

        Returns:
            Report completo del ciclo Live Paper.
        """

        # Converte il timestamp ricevuto.
        selected_time = pd.Timestamp(current_time_utc)

        # Il timestamp deve includere una timezone.
        if selected_time.tzinfo is None:
            raise LivePaperCoordinatorError("Il timestamp del ciclo deve includere una timezone.")

        # Normalizza il timestamp in UTC.
        selected_time = selected_time.tz_convert("UTC")

        # Esegue polling, aggiornamento storico e generazione segnale.
        engine_report = self._engine.run_cycle(current_time_utc=selected_time)

        # Carica il registro immutabile dei segnali.
        signals = self._engine.load_signals()

        # Recupera lo storico OHLCV disponibile.
        market_data = self._engine.history

        # L'Outcome Tracker richiede lo schema dei segnali.
        # Se non esistono ancora segnali, crea un registro vuoto compatibile.
        if signals.empty:
            outcome_report = OutcomeUpdateReport(
                evaluated_signals=0,
                resolved_signals=0,
                pending_signals=0,
                inserted_outcomes=0,
                duplicate_outcomes=0,
                ignored_no_trade_signals=0,
            )

        # Valuta gli esiti solamente quando esiste almeno un segnale.
        else:
            outcome_report = self._outcome_tracker.evaluate(
                signals=signals,
                market_data=market_data,
                evaluated_at_utc=selected_time,
            )

        # Carica gli esiti conclusivi.
        outcomes = self._outcome_tracker.load_outcomes()

        # Genera le statistiche aggiornate.
        statistics = generate_live_paper_statistics(
            signals=signals,
            outcomes=outcomes,
        )

        # Restituisce il report completo.
        return LivePaperCoordinatorReport(
            engine_report=engine_report,
            outcome_report=outcome_report,
            statistics=statistics,
        )
