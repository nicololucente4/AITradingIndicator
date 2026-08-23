"""Configurazione del collector MT5 multi-market."""

# Importa os per leggere le variabili del processo.
import os

# Importa dataclass per una configurazione immutabile.
from dataclasses import dataclass

# Importa il catalogo centralizzato dei timeframe.
from src.data.market_timeframes import (
    MarketTimeframeError,
    get_timeframe_by_code,
)


class MarketCollectionSettingsError(ValueError):
    """Errore generato dalla configurazione del collector."""


# Simboli predefiniti raccolti dal terminale MT5.
DEFAULT_MARKET_SYMBOLS = (
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "XAUUSD",
)


# Timeframe nativi principali richiesti a MT5.
DEFAULT_MARKET_TIMEFRAMES = (
    "M1",
    "M5",
    "M15",
    "M30",
    "H1",
    "H4",
    "D1",
    "W1",
)


@dataclass(frozen=True)
class MarketCollectionSettings:
    """Configurazione del collector dati di mercato."""

    # Simboli richiesti al terminale.
    symbols: tuple[str, ...]

    # Timeframe nativi richiesti al terminale.
    timeframes: tuple[str, ...]

    # Numero di secondi tra due cicli completi.
    interval_seconds: int

    @property
    def dataset_count(self) -> int:
        """Restituisce il numero di combinazioni configurate."""

        return len(self.symbols) * len(self.timeframes)

    def safe_summary(self) -> dict[str, object]:
        """Restituisce un riepilogo privo di credenziali."""

        return {
            "symbols": list(self.symbols),
            "timeframes": list(self.timeframes),
            "interval_seconds": (self.interval_seconds),
            "dataset_count": (self.dataset_count),
        }


def _parse_csv_values(
    raw_value: str,
    *,
    variable_name: str,
) -> tuple[str, ...]:
    """Converte una variabile CSV in valori univoci."""

    # Il valore deve essere una stringa.
    if not isinstance(
        raw_value,
        str,
    ):
        raise MarketCollectionSettingsError(f"{variable_name} deve essere una stringa.")

    # Divide la stringa e normalizza ogni elemento.
    raw_items = raw_value.split(",")

    normalized_items: list[str] = []

    for raw_item in raw_items:
        # Normalizza il valore corrente.
        selected_item = raw_item.strip().upper()

        # Rifiuta elementi vuoti.
        if not selected_item:
            raise MarketCollectionSettingsError(f"{variable_name} contiene un valore vuoto.")

        # Mantiene l'ordine eliminando i duplicati.
        if selected_item not in normalized_items:
            normalized_items.append(selected_item)

    # Deve essere presente almeno un elemento.
    if not normalized_items:
        raise MarketCollectionSettingsError(f"{variable_name} non può essere vuota.")

    return tuple(normalized_items)


def _read_positive_integer(
    environment: dict[str, str],
    *,
    variable_name: str,
    default: int,
) -> int:
    """Legge un numero intero strettamente positivo."""

    # Recupera il valore oppure usa quello predefinito.
    raw_value = environment.get(
        variable_name,
        str(default),
    ).strip()

    try:
        # Converte il testo in intero.
        selected_value = int(raw_value)

    except ValueError as error:
        raise MarketCollectionSettingsError(
            f"{variable_name} deve essere un numero intero."
        ) from error

    # Il valore deve essere positivo.
    if selected_value <= 0:
        raise MarketCollectionSettingsError(f"{variable_name} deve essere maggiore di zero.")

    return selected_value


def _validate_timeframes(
    timeframes: tuple[str, ...],
) -> tuple[str, ...]:
    """Verifica i timeframe nel catalogo centrale."""

    for timeframe in timeframes:
        try:
            # Verifica la presenza nel catalogo.
            get_timeframe_by_code(timeframe)

        except MarketTimeframeError as error:
            raise MarketCollectionSettingsError(
                f"Timeframe del collector non supportato: {timeframe}."
            ) from error

    return timeframes


def load_market_collection_settings(
    environment: dict[str, str] | None = None,
) -> MarketCollectionSettings:
    """Carica la configurazione del collector multi-market."""

    # Usa l'ambiente reale oppure una copia ricevuta dai test.
    selected_environment = dict(os.environ) if environment is None else dict(environment)

    # Costruisce il valore predefinito dei simboli.
    default_symbols_text = ",".join(DEFAULT_MARKET_SYMBOLS)

    # Costruisce il valore predefinito dei timeframe.
    default_timeframes_text = ",".join(DEFAULT_MARKET_TIMEFRAMES)

    # Legge e normalizza i simboli.
    symbols = _parse_csv_values(
        selected_environment.get(
            "MARKET_SYMBOLS",
            default_symbols_text,
        ),
        variable_name=("MARKET_SYMBOLS"),
    )

    # Legge e normalizza i timeframe.
    timeframes = _parse_csv_values(
        selected_environment.get(
            "MARKET_TIMEFRAMES",
            default_timeframes_text,
        ),
        variable_name=("MARKET_TIMEFRAMES"),
    )

    # Verifica i timeframe supportati.
    validated_timeframes = _validate_timeframes(timeframes)

    # Legge l'intervallo del collector.
    interval_seconds = _read_positive_integer(
        selected_environment,
        variable_name=("MARKET_COLLECTOR_INTERVAL_SECONDS"),
        default=30,
    )

    # Restituisce la configurazione immutabile.
    return MarketCollectionSettings(
        symbols=symbols,
        timeframes=(validated_timeframes),
        interval_seconds=(interval_seconds),
    )
