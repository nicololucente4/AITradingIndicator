"""Definizioni condivise per i dati di mercato OHLCV."""

# Colonne minime obbligatorie per ogni dataset OHLCV.
REQUIRED_OHLCV_COLUMNS: tuple[str, ...] = (
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
)

# Colonne che devono contenere valori numerici.
NUMERIC_OHLCV_COLUMNS: tuple[str, ...] = (
    "open",
    "high",
    "low",
    "close",
    "volume",
)

# Colonne che rappresentano i prezzi.
PRICE_COLUMNS: tuple[str, ...] = (
    "open",
    "high",
    "low",
    "close",
)
