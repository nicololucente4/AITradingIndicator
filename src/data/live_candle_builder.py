"""Costruzione della candela live in formazione dai tick MT5."""

# Importa dataclass per rappresentare tick e candela live.
from dataclasses import dataclass

# Importa pandas per timestamp e gestione UTC.
import pandas as pd


class LiveCandleBuilderError(ValueError):
    """Errore generato durante la costruzione della candela live."""


@dataclass(frozen=True)
class LiveMarketTickData:
    """Tick di mercato utilizzato dalla candela live."""

    # Simbolo finanziario normalizzato.
    symbol: str

    # Prezzo BID ricevuto da MT5.
    bid: float

    # Prezzo ASK ricevuto da MT5.
    ask: float

    # Timestamp UTC del tick.
    timestamp: pd.Timestamp

    # Volume del tick, se disponibile.
    volume: float = 0.0

    @property
    def mid(
        self,
    ) -> float:
        """Calcola il prezzo medio tra BID e ASK."""

        return (self.bid + self.ask) / 2.0

    @property
    def spread(
        self,
    ) -> float:
        """Calcola lo spread corrente."""

        return self.ask - self.bid


@dataclass(frozen=True)
class LiveCandle:
    """Candela OHLCV attualmente in formazione."""

    # Simbolo finanziario.
    symbol: str

    # Timeframe della candela.
    timeframe: str

    # Inizio UTC dell'intervallo.
    timestamp: pd.Timestamp

    # Fine UTC esclusiva dell'intervallo.
    closes_at_utc: pd.Timestamp

    # Prezzo di apertura.
    open: float

    # Prezzo massimo.
    high: float

    # Prezzo minimo.
    low: float

    # Ultimo prezzo disponibile.
    close: float

    # Volume cumulativo disponibile.
    volume: float

    # Timestamp dell'ultimo tick applicato.
    last_tick_at_utc: pd.Timestamp

    # Indica che la candela non è ancora definitiva.
    is_closed: bool = False

    # Sorgente del prezzo.
    price_source: str = "MT5_LIVE_BID"

    def to_dict(
        self,
    ) -> dict[str, object]:
        """Converte la candela in un record serializzabile."""

        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "timestamp": (self.timestamp.isoformat()),
            "closes_at_utc": (self.closes_at_utc.isoformat()),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "last_tick_at_utc": (self.last_tick_at_utc.isoformat()),
            "is_closed": self.is_closed,
            "price_source": self.price_source,
        }


# Durata in minuti dei timeframe supportati.
TIMEFRAME_MINUTES: dict[str, int] = {
    "M1": 1,
    "M2": 2,
    "M3": 3,
    "M5": 5,
    "M10": 10,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H2": 120,
    "H4": 240,
    "H8": 480,
    "H12": 720,
    "D1": 1440,
    "W1": 10080,
}


def _normalize_required_code(
    value: str,
    *,
    field_name: str,
) -> str:
    """Normalizza un codice testuale obbligatorio."""

    if not isinstance(
        value,
        str,
    ):
        raise LiveCandleBuilderError(f"{field_name} deve essere una stringa.")

    normalized_value = value.strip().upper()

    if not normalized_value:
        raise LiveCandleBuilderError(f"{field_name} non può essere vuoto.")

    return normalized_value


def _normalize_timestamp(
    value: pd.Timestamp,
    *,
    field_name: str,
) -> pd.Timestamp:
    """Converte un timestamp timezone-aware in UTC."""

    selected_timestamp = pd.Timestamp(value)

    if selected_timestamp.tzinfo is None:
        raise LiveCandleBuilderError(f"{field_name} deve includere una timezone.")

    return selected_timestamp.tz_convert("UTC")


def _validate_positive_price(
    value: float,
    *,
    field_name: str,
) -> float:
    """Verifica che un prezzo sia numerico e positivo."""

    try:
        selected_value = float(value)

    except (
        TypeError,
        ValueError,
    ) as error:
        raise LiveCandleBuilderError(f"{field_name} deve essere numerico.") from error

    if selected_value <= 0:
        raise LiveCandleBuilderError(f"{field_name} deve essere maggiore di zero.")

    return selected_value


def _validate_volume(
    value: float,
) -> float:
    """Verifica il volume associato al tick."""

    try:
        selected_value = float(value)

    except (
        TypeError,
        ValueError,
    ) as error:
        raise LiveCandleBuilderError("volume deve essere numerico.") from error

    if selected_value < 0:
        raise LiveCandleBuilderError("volume non può essere negativo.")

    return selected_value


def get_timeframe_minutes(
    timeframe: str,
) -> int:
    """Restituisce la durata del timeframe in minuti."""

    normalized_timeframe = _normalize_required_code(
        timeframe,
        field_name="timeframe",
    )

    if normalized_timeframe not in TIMEFRAME_MINUTES:
        raise LiveCandleBuilderError(f"Timeframe non supportato: {normalized_timeframe}.")

    return TIMEFRAME_MINUTES[normalized_timeframe]


def get_candle_open_timestamp(
    timestamp: pd.Timestamp,
    timeframe: str,
) -> pd.Timestamp:
    """Calcola l'inizio UTC della candela del tick."""

    selected_timestamp = _normalize_timestamp(
        timestamp,
        field_name="timestamp",
    )

    normalized_timeframe = _normalize_required_code(
        timeframe,
        field_name="timeframe",
    )

    timeframe_minutes = get_timeframe_minutes(normalized_timeframe)

    # Il timeframe settimanale parte dal lunedì UTC.
    if normalized_timeframe == "W1":
        day_start = selected_timestamp.normalize()

        return day_start - pd.Timedelta(days=(selected_timestamp.weekday()))

    # Utilizza il numero di minuti trascorsi dall'epoca Unix.
    timestamp_nanoseconds = selected_timestamp.value

    timeframe_nanoseconds = int(pd.Timedelta(minutes=timeframe_minutes).value)

    bucket_nanoseconds = timestamp_nanoseconds // timeframe_nanoseconds * timeframe_nanoseconds

    return pd.Timestamp(
        bucket_nanoseconds,
        tz="UTC",
    )


def create_live_market_tick(
    *,
    symbol: str,
    bid: float,
    ask: float,
    timestamp: pd.Timestamp,
    volume: float = 0.0,
) -> LiveMarketTickData:
    """Crea e valida un tick di mercato."""

    normalized_symbol = _normalize_required_code(
        symbol,
        field_name="symbol",
    )

    selected_bid = _validate_positive_price(
        bid,
        field_name="bid",
    )

    selected_ask = _validate_positive_price(
        ask,
        field_name="ask",
    )

    if selected_ask < selected_bid:
        raise LiveCandleBuilderError("ask non può essere inferiore a bid.")

    selected_timestamp = _normalize_timestamp(
        timestamp,
        field_name="timestamp",
    )

    selected_volume = _validate_volume(volume)

    return LiveMarketTickData(
        symbol=normalized_symbol,
        bid=selected_bid,
        ask=selected_ask,
        timestamp=selected_timestamp,
        volume=selected_volume,
    )


class LiveCandleBuilder:
    """Costruisce la candela live usando il prezzo BID MT5."""

    def __init__(
        self,
        symbol: str,
        timeframe: str,
    ) -> None:
        """Inizializza il costruttore della candela live."""

        self._symbol = _normalize_required_code(
            symbol,
            field_name="symbol",
        )

        self._timeframe = _normalize_required_code(
            timeframe,
            field_name="timeframe",
        )

        self._timeframe_minutes = get_timeframe_minutes(self._timeframe)

        # Conserva la candela attualmente in formazione.
        self._current_candle: LiveCandle | None = None

        # Conserva l'ultima candela conclusa.
        self._last_closed_candle: LiveCandle | None = None

    @property
    def symbol(
        self,
    ) -> str:
        """Restituisce il simbolo elaborato."""

        return self._symbol

    @property
    def timeframe(
        self,
    ) -> str:
        """Restituisce il timeframe elaborato."""

        return self._timeframe

    @property
    def current_candle(
        self,
    ) -> LiveCandle | None:
        """Restituisce la candela attualmente in formazione."""

        return self._current_candle

    @property
    def last_closed_candle(
        self,
    ) -> LiveCandle | None:
        """Restituisce l'ultima candela chiusa dal builder."""

        return self._last_closed_candle

    def _create_candle(
        self,
        tick: LiveMarketTickData,
    ) -> LiveCandle:
        """Crea una nuova candela dal primo tick."""

        candle_timestamp = get_candle_open_timestamp(
            tick.timestamp,
            self._timeframe,
        )

        closes_at_utc = candle_timestamp + pd.Timedelta(minutes=(self._timeframe_minutes))

        # Il grafico viene costruito sul prezzo BID.
        selected_price = tick.bid

        return LiveCandle(
            symbol=self._symbol,
            timeframe=self._timeframe,
            timestamp=candle_timestamp,
            closes_at_utc=closes_at_utc,
            open=selected_price,
            high=selected_price,
            low=selected_price,
            close=selected_price,
            volume=tick.volume,
            last_tick_at_utc=(tick.timestamp),
            is_closed=False,
            price_source="MT5_LIVE_BID",
        )

    def _close_current_candle(
        self,
    ) -> LiveCandle | None:
        """Chiude e conserva la candela corrente."""

        if self._current_candle is None:
            return None

        closed_candle = LiveCandle(
            symbol=(self._current_candle.symbol),
            timeframe=(self._current_candle.timeframe),
            timestamp=(self._current_candle.timestamp),
            closes_at_utc=(self._current_candle.closes_at_utc),
            open=(self._current_candle.open),
            high=(self._current_candle.high),
            low=(self._current_candle.low),
            close=(self._current_candle.close),
            volume=(self._current_candle.volume),
            last_tick_at_utc=(self._current_candle.last_tick_at_utc),
            is_closed=True,
            price_source=(self._current_candle.price_source),
        )

        self._last_closed_candle = closed_candle

        return closed_candle

    def update(
        self,
        tick: LiveMarketTickData,
    ) -> tuple[
        LiveCandle,
        LiveCandle | None,
    ]:
        """Aggiorna la candela con un nuovo tick.

        Restituisce:

        1. la candela corrente in formazione;
        2. l'eventuale candela appena chiusa.
        """

        if not isinstance(
            tick,
            LiveMarketTickData,
        ):
            raise TypeError("tick deve essere un'istanza di LiveMarketTickData.")

        if tick.symbol != self._symbol:
            raise LiveCandleBuilderError(
                "Il simbolo del tick non corrisponde al simbolo del builder."
            )

        if (
            self._current_candle is not None
            and tick.timestamp < self._current_candle.last_tick_at_utc
        ):
            raise LiveCandleBuilderError("I tick devono essere ricevuti in ordine cronologico.")

        tick_candle_timestamp = get_candle_open_timestamp(
            tick.timestamp,
            self._timeframe,
        )

        # Il primo tick crea una nuova candela.
        if self._current_candle is None:
            self._current_candle = self._create_candle(tick)

            return (
                self._current_candle,
                None,
            )

        # Un nuovo intervallo chiude la candela precedente.
        if tick_candle_timestamp > self._current_candle.timestamp:
            closed_candle = self._close_current_candle()

            self._current_candle = self._create_candle(tick)

            return (
                self._current_candle,
                closed_candle,
            )

        # Un tick non può appartenere a un intervallo precedente.
        if tick_candle_timestamp < self._current_candle.timestamp:
            raise LiveCandleBuilderError(
                "Il tick appartiene a una candela precedente a quella corrente."
            )

        # Aggiorna OHLCV usando il BID MT5.
        selected_price = tick.bid

        self._current_candle = LiveCandle(
            symbol=(self._current_candle.symbol),
            timeframe=(self._current_candle.timeframe),
            timestamp=(self._current_candle.timestamp),
            closes_at_utc=(self._current_candle.closes_at_utc),
            open=(self._current_candle.open),
            high=max(
                self._current_candle.high,
                selected_price,
            ),
            low=min(
                self._current_candle.low,
                selected_price,
            ),
            close=selected_price,
            volume=(self._current_candle.volume + tick.volume),
            last_tick_at_utc=(tick.timestamp),
            is_closed=False,
            price_source="MT5_LIVE_BID",
        )

        return (
            self._current_candle,
            None,
        )

    def reset(
        self,
    ) -> None:
        """Azzera lo stato del builder."""

        self._current_candle = None
        self._last_closed_candle = None
