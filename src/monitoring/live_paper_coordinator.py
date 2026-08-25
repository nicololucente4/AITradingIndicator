"""Coordinamento di segnali, esiti, trade e statistiche Live Paper."""

# Importa dataclass per rappresentare il report del ciclo.
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

# Importa il registro persistente dei paper trade.
from src.monitoring.paper_trade_registry import (
    PaperTradeRegistry,
    PaperTradeRegistryConfig,
    PaperTradeSyncReport,
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

    # Risultato della sincronizzazione dei paper trade.
    trade_report: PaperTradeSyncReport

    # Statistiche aggiornate della sessione.
    statistics: LivePaperStatistics


class LivePaperCoordinator:
    """Coordina segnali, esiti, paper trade e statistiche."""

    def __init__(
        self,
        engine: LivePaperEngine,
        outcome_tracker: OutcomeTracker,
        paper_trade_registry: PaperTradeRegistry | None = None,
    ) -> None:
        """Inizializza il coordinatore."""

        # Verifica il tipo del Live Paper Engine.
        if not isinstance(
            engine,
            LivePaperEngine,
        ):
            raise TypeError("engine deve essere un'istanza di LivePaperEngine.")

        # Verifica il tipo dell'Outcome Tracker.
        if not isinstance(
            outcome_tracker,
            OutcomeTracker,
        ):
            raise TypeError("outcome_tracker deve essere un'istanza di OutcomeTracker.")

        # I componenti devono usare lo stesso database.
        if engine.database_path.resolve() != outcome_tracker.database_path.resolve():
            raise LivePaperCoordinatorError(
                "Live Paper Engine e Outcome Tracker devono utilizzare lo stesso database."
            )

        # Se non viene fornito un registro, crea quello
        # corrispondente al motore operativo corrente.
        selected_trade_registry = paper_trade_registry or PaperTradeRegistry(
            engine.database_path,
            config=PaperTradeRegistryConfig(
                symbol="EURUSD",
                timeframe="M15",
                one_open_trade_per_symbol=True,
                paper_trading_only=True,
            ),
        )

        # Verifica il tipo del registro dei trade.
        if not isinstance(
            selected_trade_registry,
            PaperTradeRegistry,
        ):
            raise TypeError("paper_trade_registry deve essere un'istanza di PaperTradeRegistry.")

        # Anche il registro deve usare lo stesso database.
        if engine.database_path.resolve() != selected_trade_registry.database_path.resolve():
            raise LivePaperCoordinatorError(
                "Il registro paper trade deve utilizzare lo stesso database del Live Paper Engine."
            )

        # Salva i componenti verificati.
        self._engine = engine

        self._outcome_tracker = outcome_tracker

        self._paper_trade_registry = selected_trade_registry

    @property
    def paper_trade_registry(
        self,
    ) -> PaperTradeRegistry:
        """Restituisce il registro persistente dei trade."""

        return self._paper_trade_registry

    def run_cycle(
        self,
        current_time_utc: pd.Timestamp,
    ) -> LivePaperCoordinatorReport:
        """Esegue un ciclo completo Live Paper.

        Il ciclo:

        1. interroga il provider;
        2. aggiorna lo storico delle candele chiuse;
        3. genera e salva il nuovo segnale;
        4. rivaluta gli esiti ancora pendenti;
        5. apre o chiude i paper trade;
        6. aggiorna le statistiche.
        """

        # Converte il timestamp ricevuto.
        selected_time = pd.Timestamp(current_time_utc)

        # Il timestamp deve includere una timezone.
        if selected_time.tzinfo is None:
            raise LivePaperCoordinatorError("Il timestamp del ciclo deve includere una timezone.")

        # Normalizza il timestamp in UTC.
        selected_time = selected_time.tz_convert("UTC")

        # Esegue polling, storico e inferenza.
        engine_report = self._engine.run_cycle(current_time_utc=(selected_time))

        # Carica il registro immutabile dei segnali.
        signals = self._engine.load_signals()

        # Recupera lo storico OHLCV disponibile.
        market_data = self._engine.history

        # Senza segnali restituisce un report vuoto.
        if signals.empty:
            outcome_report = OutcomeUpdateReport(
                evaluated_signals=0,
                resolved_signals=0,
                pending_signals=0,
                inserted_outcomes=0,
                duplicate_outcomes=0,
                ignored_no_trade_signals=0,
            )

        # Con segnali disponibili valuta gli esiti.
        else:
            outcome_report = self._outcome_tracker.evaluate(
                signals=signals,
                market_data=market_data,
                evaluated_at_utc=(selected_time),
            )

        # Carica gli esiti conclusivi.
        outcomes = self._outcome_tracker.load_outcomes()

        # Sincronizza aperture e chiusure paper.
        trade_report = self._paper_trade_registry.synchronize(
            signals=signals,
            outcomes=outcomes,
            synchronized_at_utc=(selected_time),
        )

        # Genera le statistiche aggiornate.
        statistics = generate_live_paper_statistics(
            signals=signals,
            outcomes=outcomes,
        )

        # Restituisce il report completo.
        return LivePaperCoordinatorReport(
            engine_report=engine_report,
            outcome_report=outcome_report,
            trade_report=trade_report,
            statistics=statistics,
        )
