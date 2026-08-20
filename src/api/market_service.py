"""Servizio di lettura multi-timeframe per FastAPI."""

# Importa dataclass per rappresentare la disponibilità.
from dataclasses import dataclass

# Importa pandas per elaborare i dataset OHLCV.
import pandas as pd

# Importa lo storage persistente delle candele.
from src.data.market_data_store import (
    SQLiteMarketDataStore,
)

# Importa il catalogo centralizzato dei timeframe.
from src.data.market_timeframes import (
    MARKET_TIMEFRAMES,
    MarketTimeframe,
    MarketTimeframeError,
    get_timeframe_by_code,
)

# Importa l'aggregatore OHLCV.
from src.data.timeframe import (
    TimeframeAggregationError,
    resample_ohlcv,
)


class MarketDataServiceError(ValueError):
    """Errore generato dal servizio dati di mercato."""


@dataclass(frozen=True)
class TimeframeAvailability:
    """Descrive la disponibilità di una risoluzione."""

    # Codice interno del timeframe.
    code: str

    # Etichetta compatta del frontend.
    label: str

    # Durata della candela in minuti.
    minutes: int

    # Indica se il timeframe è disponibile.
    available: bool

    # Indica se le candele sono native.
    native: bool

    # Indica se il modello opera sul timeframe.
    model_enabled: bool

    # Timeframe sorgente usato per l'aggregazione.
    source_timeframe: str | None

    # Numero di candele native archiviate.
    stored_candle_count: int

    # Motivo dell'eventuale indisponibilità.
    reason: str | None

    def to_dict(
        self,
    ) -> dict[str, object]:
        """Converte la disponibilità in un dizionario JSON."""

        return {
            "code": self.code,
            "label": self.label,
            "minutes": self.minutes,
            "available": self.available,
            "native": self.native,
            "model_enabled": self.model_enabled,
            "source_timeframe": self.source_timeframe,
            "stored_candle_count": self.stored_candle_count,
            "reason": self.reason,
        }


class MarketDataQueryService:
    """Legge candele native e genera aggregazioni superiori."""

    def __init__(
        self,
        store: SQLiteMarketDataStore,
        *,
        symbol: str,
    ) -> None:
        """Inizializza il servizio di interrogazione."""

        # Verifica il tipo dello storage.
        if not isinstance(
            store,
            SQLiteMarketDataStore,
        ):
            raise TypeError("store deve essere un'istanza di SQLiteMarketDataStore.")

        # Il simbolo deve essere una stringa.
        if not isinstance(
            symbol,
            str,
        ):
            raise MarketDataServiceError("symbol deve essere una stringa.")

        # Normalizza il simbolo.
        selected_symbol = symbol.strip().upper()

        # Il simbolo non può essere vuoto.
        if not selected_symbol:
            raise MarketDataServiceError("symbol non può essere vuoto.")

        # Salva i componenti validati.
        self._store = store
        self._symbol = selected_symbol

    @property
    def store(
        self,
    ) -> SQLiteMarketDataStore:
        """Restituisce l'archivio persistente."""

        return self._store

    @property
    def symbol(self) -> str:
        """Restituisce il simbolo selezionato."""

        return self._symbol

    def _native_counts(
        self,
    ) -> dict[str, int]:
        """Restituisce il numero di candele native per timeframe."""

        # Recupera la disponibilità del simbolo.
        availability = self._store.list_availability(symbol=self._symbol)

        # Indicizza i conteggi per codice.
        return {item.timeframe: item.candle_count for item in availability}

    @staticmethod
    def _find_aggregation_source(
        target: MarketTimeframe,
        native_counts: dict[str, int],
    ) -> MarketTimeframe | None:
        """Trova il miglior timeframe sorgente per l'aggregazione."""

        # Recupera i timeframe nativi più piccoli del target
        # e divisori esatti della durata richiesta.
        candidates = [
            timeframe
            for timeframe in MARKET_TIMEFRAMES
            if (
                native_counts.get(
                    timeframe.code,
                    0,
                )
                > 0
                and timeframe.minutes < target.minutes
                and target.minutes % timeframe.minutes == 0
            )
        ]

        # Nessuna sorgente è disponibile.
        if not candidates:
            return None

        # Usa il timeframe nativo con durata maggiore.
        # Questo riduce il numero di barre da aggregare.
        return max(
            candidates,
            key=lambda item: item.minutes,
        )

    def list_timeframes(
        self,
    ):
        """Elenca tutti i timeframe e la relativa disponibilità."""

        # Recupera i conteggi nativi.
        native_counts = self._native_counts()

        # Prepara il risultato ordinato.
        result: list[TimeframeAvailability] = []

        # Valuta ogni timeframe del catalogo.
        for timeframe in MARKET_TIMEFRAMES:
            # Recupera il numero di candele native.
            native_count = native_counts.get(
                timeframe.code,
                0,
            )

            # Un dataset nativo è immediatamente disponibile.
            if native_count > 0:
                result.append(
                    TimeframeAvailability(
                        code=timeframe.code,
                        label=(timeframe.display_label),
                        minutes=timeframe.minutes,
                        available=True,
                        native=True,
                        model_enabled=(timeframe.model_enabled),
                        source_timeframe=(timeframe.code),
                        stored_candle_count=(native_count),
                        reason=None,
                    )
                )

                continue

            # Cerca una sorgente aggregabile.
            source = self._find_aggregation_source(
                timeframe,
                native_counts,
            )

            # Se esiste una sorgente, il timeframe è derivabile.
            if source is not None:
                result.append(
                    TimeframeAvailability(
                        code=timeframe.code,
                        label=(timeframe.display_label),
                        minutes=timeframe.minutes,
                        available=True,
                        native=False,
                        model_enabled=(timeframe.model_enabled),
                        source_timeframe=(source.code),
                        stored_candle_count=0,
                        reason=None,
                    )
                )

                continue

            # Nessuna sorgente è disponibile.
            result.append(
                TimeframeAvailability(
                    code=timeframe.code,
                    label=(timeframe.display_label),
                    minutes=timeframe.minutes,
                    available=False,
                    native=False,
                    model_enabled=(timeframe.model_enabled),
                    source_timeframe=None,
                    stored_candle_count=0,
                    reason=("Nessuna candela nativa o sorgente aggregabile disponibile."),
                )
            )

        return result

    def get_timeframe_availability(
        self,
        timeframe_code: str,
    ) -> TimeframeAvailability:
        """Recupera la disponibilità di un singolo timeframe."""

        try:
            # Normalizza e valida il codice.
            timeframe = get_timeframe_by_code(timeframe_code)

        except MarketTimeframeError as error:
            raise MarketDataServiceError(str(error)) from error

        # Cerca il timeframe nel catalogo calcolato.
        for item in self.list_timeframes():
            if item.code == timeframe.code:
                return item

        # Controllo difensivo.
        raise MarketDataServiceError(f"Disponibilità non determinabile per {timeframe.code}.")

    def load_candles(
        self,
        *,
        timeframe_code: str,
        limit: int = 500,
    ) -> pd.DataFrame:
        """Carica candele native oppure aggregate."""

        # Il limite deve essere positivo.
        if limit <= 0:
            raise MarketDataServiceError("limit deve essere maggiore di zero.")

        try:
            # Recupera il timeframe richiesto.
            target = get_timeframe_by_code(timeframe_code)

        except MarketTimeframeError as error:
            raise MarketDataServiceError(str(error)) from error

        # Recupera la disponibilità.
        availability = self.get_timeframe_availability(target.code)

        # Rifiuta timeframe non disponibili.
        if not availability.available:
            raise MarketDataServiceError(f"Timeframe non disponibile: {target.code}.")

        # Le candele native vengono lette direttamente.
        if availability.native:
            return self._store.load_candles(
                symbol=self._symbol,
                timeframe=target.code,
                limit=limit,
            )

        # Il timeframe aggregato deve avere una sorgente.
        if availability.source_timeframe is None:
            raise MarketDataServiceError(
                f"Sorgente aggregazione non disponibile per {target.code}."
            )

        # Recupera la definizione della sorgente.
        source = get_timeframe_by_code(availability.source_timeframe)

        # Calcola quante candele sorgente possono servire.
        source_ratio = target.minutes // source.minutes

        # Legge un margine aggiuntivo per scartare
        # eventuali bucket incompleti iniziali e finali.
        source_limit = limit * source_ratio + source_ratio * 2

        # Carica le candele native della sorgente.
        source_dataframe = self._store.load_candles(
            symbol=self._symbol,
            timeframe=source.code,
            limit=source_limit,
        )

        # Non aggrega un dataset vuoto.
        if source_dataframe.empty:
            raise MarketDataServiceError(f"Nessuna candela sorgente disponibile per {target.code}.")

        try:
            # Genera solamente bucket completi.
            aggregated = resample_ohlcv(
                dataframe=source_dataframe,
                source_minutes=(source.minutes),
                target_minutes=(target.minutes),
            )

        except TimeframeAggregationError as error:
            raise MarketDataServiceError(
                f"Impossibile generare il timeframe {target.code}: {error}"
            ) from error

        # Mantiene solamente le ultime candele richieste.
        return aggregated.tail(limit).reset_index(drop=True)
