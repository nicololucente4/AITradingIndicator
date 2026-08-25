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

# Importa il registro persistente delle operazioni paper.
from src.monitoring.paper_trade_registry import (
    PaperTradeRegistry,
    PaperTradeRegistryConfig,
    PaperTradeSyncReport,
)

# Importa il filtro selettivo delle aperture.
from src.monitoring.selective_trade_filter import (
    SelectiveTradeFilter,
    SelectiveTradeFilterConfig,
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

    # Numero di segnali direzionali accettati dal filtro.
    accepted_trade_signals: int

    # Numero di segnali rifiutati dal filtro selettivo.
    rejected_trade_signals: int

    # Statistiche aggiornate della sessione.
    statistics: LivePaperStatistics


class LivePaperCoordinator:
    """Coordina segnali, esiti, paper trade e statistiche."""

    def __init__(
        self,
        engine: LivePaperEngine,
        outcome_tracker: OutcomeTracker,
        paper_trade_registry: PaperTradeRegistry | None = None,
        selective_trade_filter: SelectiveTradeFilter | None = None,
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

        # Engine e Outcome Tracker devono usare lo stesso database.
        if engine.database_path.resolve() != outcome_tracker.database_path.resolve():
            raise LivePaperCoordinatorError(
                "Live Paper Engine e Outcome Tracker devono utilizzare lo stesso database."
            )

        # Crea il registro predefinito quando non fornito.
        selected_trade_registry = paper_trade_registry or PaperTradeRegistry(
            engine.database_path,
            config=PaperTradeRegistryConfig(
                symbol="EURUSD",
                timeframe="M15",
                one_open_trade_per_symbol=True,
                paper_trading_only=True,
            ),
        )

        # Verifica il tipo del registro paper trade.
        if not isinstance(
            selected_trade_registry,
            PaperTradeRegistry,
        ):
            raise TypeError("paper_trade_registry deve essere un'istanza di PaperTradeRegistry.")

        # Il registro deve usare lo stesso database.
        if engine.database_path.resolve() != selected_trade_registry.database_path.resolve():
            raise LivePaperCoordinatorError(
                "Il registro paper trade deve utilizzare lo stesso database del Live Paper Engine."
            )

        # Crea il filtro selettivo predefinito.
        selected_trade_filter = selective_trade_filter or SelectiveTradeFilter(
            SelectiveTradeFilterConfig(
                minimum_confidence=0.80,
                minimum_probability_margin=0.20,
                require_confirmed_signal=True,
                paper_trading_only=True,
            )
        )

        # Verifica il tipo del filtro.
        if not isinstance(
            selected_trade_filter,
            SelectiveTradeFilter,
        ):
            raise TypeError(
                "selective_trade_filter deve essere un'istanza di SelectiveTradeFilter."
            )

        # Salva i componenti verificati.
        self._engine = engine

        self._outcome_tracker = outcome_tracker

        self._paper_trade_registry = selected_trade_registry

        self._selective_trade_filter = selected_trade_filter

    @property
    def paper_trade_registry(
        self,
    ) -> PaperTradeRegistry:
        """Restituisce il registro persistente dei trade."""

        return self._paper_trade_registry

    @property
    def selective_trade_filter(
        self,
    ) -> SelectiveTradeFilter:
        """Restituisce il filtro selettivo delle aperture."""

        return self._selective_trade_filter

    def _filter_trade_signals(
        self,
        signals: pd.DataFrame,
    ) -> tuple[pd.DataFrame, int, int]:
        """Mantiene solo i segnali idonei all'apertura paper."""

        # Un registro vuoto resta vuoto senza alterare le colonne.
        if signals.empty:
            return (
                signals.copy(deep=True),
                0,
                0,
            )

        # Prepara gli indici dei segnali accettati.
        accepted_indices: list[int] = []

        # Inizializza i contatori.
        accepted_count = 0
        rejected_count = 0

        # Analizza ogni segnale indipendentemente.
        for index, signal_row in signals.iterrows():
            # Valuta il segnale con le soglie configurate.
            decision = self._selective_trade_filter.evaluate(signal_row)

            # Mantiene solamente LONG o SHORT forti.
            if decision.accepted:
                accepted_indices.append(index)

                accepted_count += 1

            # Conta solamente i segnali direzionali rifiutati.
            elif str(
                signal_row.get(
                    "signal",
                    "",
                )
            ).strip().upper() in {
                "LONG",
                "SHORT",
            }:
                rejected_count += 1

        # Mantiene tutte le colonne originali.
        filtered_signals = signals.loc[accepted_indices].copy(deep=True)

        # Ripristina un indice progressivo.
        filtered_signals = filtered_signals.reset_index(drop=True)

        return (
            filtered_signals,
            accepted_count,
            rejected_count,
        )

    def run_cycle(
        self,
        current_time_utc: pd.Timestamp,
    ) -> LivePaperCoordinatorReport:
        """Esegue un ciclo completo Live Paper.

        Il ciclo:

        1. interroga il provider;
        2. aggiorna lo storico delle candele chiuse;
        3. genera e salva il segnale diagnostico;
        4. rivaluta gli esiti ancora pendenti;
        5. filtra le aperture in base a confidenza e margine;
        6. apre o chiude i paper trade idonei;
        7. aggiorna le statistiche.
        """

        # Converte il timestamp ricevuto.
        selected_time = pd.Timestamp(current_time_utc)

        # Il timestamp deve includere una timezone.
        if selected_time.tzinfo is None:
            raise LivePaperCoordinatorError("Il timestamp del ciclo deve includere una timezone.")

        # Normalizza esplicitamente in UTC.
        selected_time = selected_time.tz_convert("UTC")

        # Esegue polling, storico e inferenza.
        engine_report = self._engine.run_cycle(current_time_utc=(selected_time))

        # Carica tutti i segnali diagnostici persistenti.
        signals = self._engine.load_signals()

        # Recupera lo storico OHLCV disponibile.
        market_data = self._engine.history

        # Senza segnali restituisce un report esiti vuoto.
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

        # Applica le soglie selettive alle aperture.
        (
            accepted_signals,
            accepted_trade_signals,
            rejected_trade_signals,
        ) = self._filter_trade_signals(signals)

        # Sincronizza solo le aperture sufficientemente forti.
        trade_report = self._paper_trade_registry.synchronize(
            signals=accepted_signals,
            outcomes=outcomes,
            synchronized_at_utc=(selected_time),
        )

        # Le statistiche diagnostiche continuano a considerare
        # tutti i segnali generati dal modello.
        statistics = generate_live_paper_statistics(
            signals=signals,
            outcomes=outcomes,
        )

        # Restituisce il report completo.
        return LivePaperCoordinatorReport(
            engine_report=engine_report,
            outcome_report=outcome_report,
            trade_report=trade_report,
            accepted_trade_signals=(accepted_trade_signals),
            rejected_trade_signals=(rejected_trade_signals),
            statistics=statistics,
        )
