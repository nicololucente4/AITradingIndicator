"""Catalogo centralizzato dei timeframe di mercato supportati."""

# Importa dataclass per rappresentare un timeframe immutabile.
from dataclasses import dataclass


class MarketTimeframeError(ValueError):
    """Errore generato da un timeframe non supportato."""


@dataclass(frozen=True)
class MarketTimeframe:
    """Rappresenta una risoluzione temporale del mercato."""

    # Codice interno utilizzato dall'applicazione.
    code: str

    # Etichetta compatta mostrata nel frontend.
    display_label: str

    # Durata della candela espressa in minuti.
    minutes: int

    # Nome della costante esposta dal modulo MetaTrader5.
    mt5_attribute: str

    # Indica se il timeframe può produrre segnali ML.
    model_enabled: bool = False


# Catalogo ordinato delle risoluzioni professionali.
MARKET_TIMEFRAMES: tuple[
    MarketTimeframe,
    ...,
] = (
    MarketTimeframe(
        code="M1",
        display_label="1m",
        minutes=1,
        mt5_attribute="TIMEFRAME_M1",
    ),
    MarketTimeframe(
        code="M2",
        display_label="2m",
        minutes=2,
        mt5_attribute="TIMEFRAME_M2",
    ),
    MarketTimeframe(
        code="M3",
        display_label="3m",
        minutes=3,
        mt5_attribute="TIMEFRAME_M3",
    ),
    MarketTimeframe(
        code="M5",
        display_label="5m",
        minutes=5,
        mt5_attribute="TIMEFRAME_M5",
    ),
    MarketTimeframe(
        code="M10",
        display_label="10m",
        minutes=10,
        mt5_attribute="TIMEFRAME_M10",
    ),
    MarketTimeframe(
        code="M15",
        display_label="15m",
        minutes=15,
        mt5_attribute="TIMEFRAME_M15",
        model_enabled=True,
    ),
    MarketTimeframe(
        code="M30",
        display_label="30m",
        minutes=30,
        mt5_attribute="TIMEFRAME_M30",
    ),
    MarketTimeframe(
        code="H1",
        display_label="1h",
        minutes=60,
        mt5_attribute="TIMEFRAME_H1",
    ),
    MarketTimeframe(
        code="H2",
        display_label="2h",
        minutes=120,
        mt5_attribute="TIMEFRAME_H2",
    ),
    MarketTimeframe(
        code="H4",
        display_label="4h",
        minutes=240,
        mt5_attribute="TIMEFRAME_H4",
    ),
    MarketTimeframe(
        code="H8",
        display_label="8h",
        minutes=480,
        mt5_attribute="TIMEFRAME_H8",
    ),
    MarketTimeframe(
        code="H12",
        display_label="12h",
        minutes=720,
        mt5_attribute="TIMEFRAME_H12",
    ),
    MarketTimeframe(
        code="D1",
        display_label="1D",
        minutes=1440,
        mt5_attribute="TIMEFRAME_D1",
    ),
    MarketTimeframe(
        code="W1",
        display_label="1W",
        minutes=10080,
        mt5_attribute="TIMEFRAME_W1",
    ),
)


# Indicizzazione tramite codice interno.
TIMEFRAME_BY_CODE: dict[
    str,
    MarketTimeframe,
] = {timeframe.code: timeframe for timeframe in MARKET_TIMEFRAMES}


# Indicizzazione tramite durata in minuti.
TIMEFRAME_BY_MINUTES: dict[
    int,
    MarketTimeframe,
] = {timeframe.minutes: timeframe for timeframe in MARKET_TIMEFRAMES}


def get_timeframe_by_code(
    code: str,
) -> MarketTimeframe:
    """Recupera un timeframe tramite il codice interno."""

    # Verifica che il codice sia una stringa.
    if not isinstance(code, str):
        raise MarketTimeframeError("Il codice del timeframe deve essere una stringa.")

    # Normalizza il codice ricevuto.
    normalized_code = code.strip().upper()

    try:
        # Restituisce il timeframe corrispondente.
        return TIMEFRAME_BY_CODE[normalized_code]

    except KeyError as error:
        # Usa un'etichetta leggibile quando il codice è vuoto.
        displayed_code = normalized_code if normalized_code else "<VUOTO>"

        raise MarketTimeframeError(f"Timeframe non supportato: {displayed_code}.") from error


def get_timeframe_by_minutes(
    minutes: int,
) -> MarketTimeframe:
    """Recupera un timeframe tramite la durata in minuti."""

    # Verifica che la durata sia un numero intero.
    if not isinstance(minutes, int):
        raise MarketTimeframeError("La durata del timeframe deve essere un numero intero.")

    try:
        # Restituisce il timeframe corrispondente.
        return TIMEFRAME_BY_MINUTES[minutes]

    except KeyError as error:
        raise MarketTimeframeError(f"Durata timeframe non supportata: {minutes} minuti.") from error


def get_supported_timeframe_codes() -> tuple[
    str,
    ...,
]:
    """Restituisce i codici supportati nell'ordine del catalogo."""

    return tuple(timeframe.code for timeframe in MARKET_TIMEFRAMES)


def get_model_timeframe_codes() -> tuple[
    str,
    ...,
]:
    """Restituisce i timeframe abilitati alla generazione ML."""

    return tuple(timeframe.code for timeframe in MARKET_TIMEFRAMES if timeframe.model_enabled)


def build_public_timeframe_catalog() -> list[dict[str, object]]:
    """Restituisce il catalogo pubblico destinato a FastAPI."""

    return [
        {
            "code": timeframe.code,
            "label": (timeframe.display_label),
            "minutes": timeframe.minutes,
            "model_enabled": (timeframe.model_enabled),
        }
        for timeframe in MARKET_TIMEFRAMES
    ]
