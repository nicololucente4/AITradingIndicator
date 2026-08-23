"""Servizio di lettura multi-strumento e multi-timeframe per FastAPI."""

# Importa dataclass per rappresentare le disponibilità.
from dataclasses import dataclass

# Importa pandas per elaborare i dataset OHLCV.
import pandas as pd

# Importa lo storage persistente delle candele.
from src.data.market_data_store import SQLiteMarketDataStore

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
class MarketSymbolAvailability:
    """Descrive uno strumento presente nell'archivio."""

    # Codice del simbolo.
    symbol: str

    # Numero di timeframe nativi disponibili.
    native_timeframe_count: int

    # Numero complessivo di candele archiviate.
    stored_candle_count: int

    # Indica se esiste un modello ML validato.
    model_enabled: bool

    def to_dict(
        self,
    ) -> dict[str, object]:
        """Converte il simbolo in un record JSON."""

        return {
            "symbol": self.symbol,
            "native_timeframe_count": (self.native_timeframe_count),
            "stored_candle_count": (self.stored_candle_count),
            "model_enabled": (self.model_enabled),
        }


@dataclass(frozen=True)
class TimeframeAvailability:
    """Descrive la disponibilità di una risoluzione."""

    # Codice del timeframe.
    code: str

    # Etichetta compatta del frontend.
    label: str

    # Durata della candela in minuti.
    minutes: int

    # Indica se il timeframe è disponibile.
    available: bool

    # Indica se le candele sono native.
    native: bool

    # Indica se esiste un modello validato.
    model_enabled: bool

    # Timeframe usato come sorgente.
    source_timeframe: str | None

    # Numero di candele native archiviate.
    stored_candle_count: int

    # Motivo dell'indisponibilità.
    reason: str | None

    def to_dict(
        self,
    ) -> dict[str, object]:
        """Converte la disponibilità in un record JSON."""

        return {
            "code": self.code,
            "label": self.label,
            "minutes": self.minutes,
            "available": self.available,
            "native": self.native,
            "model_enabled": self.model_enabled,
            "source_timeframe": self.source_timeframe,
            "stored_candle_count": (self.stored_candle_count),
            "reason": self.reason,
        }


def normalize_market_symbol(
    symbol: str,
) -> str:
    """Normalizza e valida un simbolo."""

    # Il simbolo deve essere una stringa.
    if not isinstance(
        symbol,
        str,
    ):
        raise MarketDataServiceError("symbol deve essere una stringa.")

    # Normalizza il codice.
    selected_symbol = symbol.strip().upper()

    # Rifiuta una stringa vuota.
    if not selected_symbol:
        raise MarketDataServiceError("symbol non può essere vuoto.")

    return selected_symbol


def list_available_symbols(
    store: SQLiteMarketDataStore,
    *,
    model_symbols: tuple[str, ...] = (),
):
    """Elenca gli strumenti presenti nell'archivio."""

    # Verifica lo storage.
    if not isinstance(
        store,
        SQLiteMarketDataStore,
    ):
        raise TypeError("store deve essere un'istanza di SQLiteMarketDataStore.")

    # Normalizza l'elenco dei simboli con modello.
    normalized_model_symbols = {normalize_market_symbol(symbol) for symbol in model_symbols}

    # Recupera tutti i dataset disponibili.
    availability = store.list_availability()

    # Aggrega i dati per simbolo.
    grouped_timeframes: dict[
        str,
        set[str],
    ] = {}

    grouped_candle_counts: dict[
        str,
        int,
    ] = {}

    for item in availability:
        # Crea il set dei timeframe del simbolo.
        if item.symbol not in grouped_timeframes:
            grouped_timeframes[item.symbol] = set()

        # Registra il timeframe nativo.
        grouped_timeframes[item.symbol].add(item.timeframe)

        # Aggiorna il conteggio complessivo.
        grouped_candle_counts[item.symbol] = (
            grouped_candle_counts.get(
                item.symbol,
                0,
            )
            + item.candle_count
        )

    # Converte i dati aggregati.
    results = []

    for symbol in sorted(grouped_timeframes):
        results.append(
            MarketSymbolAvailability(
                symbol=symbol,
                native_timeframe_count=len(grouped_timeframes[symbol]),
                stored_candle_count=(
                    grouped_candle_counts.get(
                        symbol,
                        0,
                    )
                ),
                model_enabled=(symbol in normalized_model_symbols),
            )
        )

    return results


class MarketDataQueryService:
    """Legge candele native o aggregate per un simbolo."""

    def __init__(
        self,
        store: SQLiteMarketDataStore,
        *,
        symbol: str,
        model_enabled: bool = True,
    ) -> None:
        """Inizializza il servizio di interrogazione."""

        # Verifica lo storage.
        if not isinstance(
            store,
            SQLiteMarketDataStore,
        ):
            raise TypeError("store deve essere un'istanza di SQLiteMarketDataStore.")

        # Salva lo storage.
        self._store = store

        # Normalizza e salva il simbolo.
        self._symbol = normalize_market_symbol(symbol)

        # Salva la disponibilità del modello.
        self._model_enabled = bool(model_enabled)

    @property
    def store(
        self,
    ) -> SQLiteMarketDataStore:
        """Restituisce l'archivio persistente."""

        return self._store

    @property
    def symbol(
        self,
    ) -> str:
        """Restituisce il simbolo selezionato."""

        return self._symbol

    @property
    def model_enabled(
        self,
    ) -> bool:
        """Indica se il simbolo possiede un modello validato."""

        return self._model_enabled

    def _native_counts(
        self,
    ) -> dict[str, int]:
        """Restituisce le candele native per timeframe."""

        # Recupera la disponibilità del simbolo.
        availability = self._store.list_availability(symbol=self._symbol)

        # Indicizza il conteggio per timeframe.
        return {item.timeframe: (item.candle_count) for item in availability}

    @staticmethod
    def _find_aggregation_source(
        target: MarketTimeframe,
        native_counts: dict[str, int],
    ) -> MarketTimeframe | None:
        """Trova la migliore sorgente aggregabile."""

        # Cerca timeframe nativi inferiori e divisori esatti.
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

        # Nessuna sorgente disponibile.
        if not candidates:
            return None

        # Usa il timeframe nativo più vicino al target.
        return max(
            candidates,
            key=lambda item: item.minutes,
        )

    def list_timeframes(
        self,
    ):
        """Elenca i timeframe del simbolo."""

        # Recupera i conteggi nativi.
        native_counts = self._native_counts()

        # Prepara il risultato.
        result = []

        # Valuta ogni timeframe del catalogo.
        for timeframe in MARKET_TIMEFRAMES:
            # Recupera il numero di candele native.
            native_count = native_counts.get(
                timeframe.code,
                0,
            )

            # Il modello è inizialmente disponibile solo su M15.
            timeframe_model_enabled = self._model_enabled and timeframe.code == "M15"

            # Un timeframe nativo è subito disponibile.
            if native_count > 0:
                result.append(
                    TimeframeAvailability(
                        code=timeframe.code,
                        label=(timeframe.display_label),
                        minutes=(timeframe.minutes),
                        available=True,
                        native=True,
                        model_enabled=(timeframe_model_enabled),
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

            # Il timeframe può essere derivato.
            if source is not None:
                result.append(
                    TimeframeAvailability(
                        code=timeframe.code,
                        label=(timeframe.display_label),
                        minutes=(timeframe.minutes),
                        available=True,
                        native=False,
                        model_enabled=(timeframe_model_enabled),
                        source_timeframe=(source.code),
                        stored_candle_count=0,
                        reason=None,
                    )
                )

                continue

            # Nessuna sorgente disponibile.
            result.append(
                TimeframeAvailability(
                    code=timeframe.code,
                    label=(timeframe.display_label),
                    minutes=(timeframe.minutes),
                    available=False,
                    native=False,
                    model_enabled=(timeframe_model_enabled),
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
        """Recupera un singolo timeframe."""

        try:
            # Normalizza e valida il timeframe.
            timeframe = get_timeframe_by_code(timeframe_code)

        except MarketTimeframeError as error:
            raise MarketDataServiceError(str(error)) from error

        # Cerca il timeframe nel catalogo.
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
            # Normalizza e valida il timeframe target.
            target = get_timeframe_by_code(timeframe_code)

        except MarketTimeframeError as error:
            raise MarketDataServiceError(str(error)) from error

        # Recupera la disponibilità del timeframe.
        availability = self.get_timeframe_availability(target.code)

        # Rifiuta timeframe indisponibili.
        if not availability.available:
            raise MarketDataServiceError(f"Timeframe non disponibile: {target.code}.")

        # Legge direttamente un timeframe nativo.
        if availability.native:
            return self._store.load_candles(
                symbol=self._symbol,
                timeframe=target.code,
                limit=limit,
            )

        # Un timeframe aggregato deve avere una sorgente.
        if availability.source_timeframe is None:
            raise MarketDataServiceError(
                f"Sorgente aggregazione non disponibile per {target.code}."
            )

        # Recupera la definizione della sorgente.
        source = get_timeframe_by_code(availability.source_timeframe)

        # Calcola il rapporto tra target e sorgente.
        source_ratio = target.minutes // source.minutes

        # Legge un margine per i bucket incompleti.
        source_limit = limit * source_ratio + source_ratio * 2

        # Carica le candele sorgente.
        source_dataframe = self._store.load_candles(
            symbol=self._symbol,
            timeframe=source.code,
            limit=source_limit,
        )

        # Non aggrega un dataset vuoto.
        if source_dataframe.empty:
            raise MarketDataServiceError(f"Nessuna candela sorgente disponibile per {target.code}.")

        try:
            # Aggrega solamente bucket completi.
            aggregated = resample_ohlcv(
                dataframe=(source_dataframe),
                source_minutes=(source.minutes),
                target_minutes=(target.minutes),
            )

        except TimeframeAggregationError as error:
            raise MarketDataServiceError(
                f"Impossibile generare il timeframe {target.code}: {error}"
            ) from error

        # Mantiene le ultime candele richieste.
        return aggregated.tail(limit).reset_index(drop=True)
