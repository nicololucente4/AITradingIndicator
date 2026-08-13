"""Generazione dei segnali della baseline deterministica non-AI."""

# Importa dataclass per rappresentare la configurazione della baseline.
from dataclasses import dataclass

# Importa pandas per lavorare con i dati e le serie temporali.
import pandas as pd

# Importa la configurazione e la pipeline delle feature tecniche.
from src.features.technical import (
    TechnicalFeatureConfig,
    build_technical_features,
)


class BaselineSignalError(ValueError):
    """Errore generato da una configurazione baseline non valida."""


@dataclass(frozen=True)
class BaselineSignalConfig:
    """Configurazione della baseline deterministica."""

    # Durata in minuti della candela operativa.
    timeframe_minutes: int = 15

    # ATR percentuale minimo richiesto per generare un segnale.
    minimum_atr_percentage: float = 0.0001

    # ATR percentuale massimo consentito per generare un segnale.
    maximum_atr_percentage: float = 0.05

    # Rendimento minimo assoluto richiesto come conferma.
    minimum_absolute_return: float = 0.0


def _validate_signal_config(
    config: BaselineSignalConfig,
) -> None:
    """Verifica la coerenza della configurazione baseline."""

    # Il timeframe deve essere strettamente positivo.
    if config.timeframe_minutes <= 0:
        raise BaselineSignalError("Il timeframe operativo deve essere maggiore di zero.")

    # La volatilità minima non può essere negativa.
    if config.minimum_atr_percentage < 0:
        raise BaselineSignalError("La soglia ATR minima non può essere negativa.")

    # La volatilità massima deve essere positiva.
    if config.maximum_atr_percentage <= 0:
        raise BaselineSignalError("La soglia ATR massima deve essere maggiore di zero.")

    # La soglia massima deve essere superiore alla soglia minima.
    if config.maximum_atr_percentage <= config.minimum_atr_percentage:
        raise BaselineSignalError(
            "La soglia ATR massima deve essere superiore alla soglia ATR minima."
        )

    # La soglia sul rendimento assoluto non può essere negativa.
    if config.minimum_absolute_return < 0:
        raise BaselineSignalError("Il rendimento minimo assoluto non può essere negativo.")


def _has_required_features(row: pd.Series) -> bool:
    """Verifica che tutte le feature necessarie siano disponibili."""

    # Definisce le feature utilizzate dalla baseline.
    required_features = [
        "return_1",
        "ema_fast",
        "ema_slow",
        "ema_distance_pct",
        "atr_pct",
    ]

    # Restituisce True solamente se nessuna feature richiesta è mancante.
    return not row[required_features].isna().any()


def _generate_row_signal(
    row: pd.Series,
    config: BaselineSignalConfig,
) -> tuple[str, str]:
    """Genera segnale e motivazione per una singola candela."""

    # Durante il warm-up non sono disponibili tutte le feature.
    if not _has_required_features(row):
        return (
            "NO_TRADE",
            "Feature tecniche non ancora disponibili durante il warm-up.",
        )

    # Controlla che l'ATR percentuale sia compreso nell'intervallo ammesso.
    volatility_is_valid = (
        config.minimum_atr_percentage <= row["atr_pct"] <= config.maximum_atr_percentage
    )

    # Se la volatilità non è accettabile, non viene generato alcun segnale.
    if not volatility_is_valid:
        return (
            "NO_TRADE",
            "ATR percentuale fuori dall'intervallo consentito.",
        )

    # Verifica le condizioni rialziste.
    long_condition = (
        row["ema_fast"] > row["ema_slow"]
        and row["ema_distance_pct"] > 0
        and row["return_1"] > config.minimum_absolute_return
    )

    # Verifica le condizioni ribassiste.
    short_condition = (
        row["ema_fast"] < row["ema_slow"]
        and row["ema_distance_pct"] < 0
        and row["return_1"] < -config.minimum_absolute_return
    )

    # Restituisce il segnale LONG quando tutte le condizioni sono vere.
    if long_condition:
        return (
            "LONG",
            "EMA veloce sopra EMA lenta, momentum positivo e volatilità ammessa.",
        )

    # Restituisce il segnale SHORT quando tutte le condizioni sono vere.
    if short_condition:
        return (
            "SHORT",
            "EMA veloce sotto EMA lenta, momentum negativo e volatilità ammessa.",
        )

    # In assenza di condizioni complete, il sistema resta neutrale.
    return (
        "NO_TRADE",
        "Condizioni direzionali insufficienti o contrastanti.",
    )


def build_baseline_signals(
    dataframe: pd.DataFrame,
    feature_config: TechnicalFeatureConfig | None = None,
    signal_config: BaselineSignalConfig | None = None,
) -> pd.DataFrame:
    """Calcola le feature e genera i segnali baseline confermati.

    Il timestamp OHLCV rappresenta l'apertura della candela.
    Il segnale diventa disponibile solamente alla chiusura della candela,
    indicata nella colonna signal_available_at.

    Args:
        dataframe: Dataset OHLCV ordinato cronologicamente.
        feature_config: Configurazione delle feature tecniche.
        signal_config: Configurazione della baseline.

    Returns:
        DataFrame contenente feature, segnale, motivazione e timestamp
        di disponibilità.
    """

    # Usa la configurazione predefinita se non specificata.
    selected_signal_config = signal_config or BaselineSignalConfig()

    # Valida i parametri della baseline.
    _validate_signal_config(selected_signal_config)

    # Calcola le feature tecniche usando solamente presente e passato.
    result_dataframe = build_technical_features(
        dataframe=dataframe,
        config=feature_config,
    )

    # Genera segnale e motivazione per ogni candela.
    signal_results = result_dataframe.apply(
        lambda row: _generate_row_signal(
            row=row,
            config=selected_signal_config,
        ),
        axis=1,
    )

    # Estrae la direzione del segnale.
    result_dataframe["signal"] = signal_results.map(lambda result: result[0])

    # Estrae la motivazione del segnale.
    result_dataframe["signal_reason"] = signal_results.map(lambda result: result[1])

    # Calcola quando la candela risulta effettivamente chiusa.
    result_dataframe["signal_available_at"] = result_dataframe["timestamp"] + pd.to_timedelta(
        selected_signal_config.timeframe_minutes,
        unit="minutes",
    )

    # Tutti i segnali prodotti da questa funzione sono confermati.
    result_dataframe["signal_status"] = "CONFIRMED"

    # Identifica esplicitamente il tipo di generatore.
    result_dataframe["signal_source"] = "BASELINE_RULES"

    # Restituisce il dataset completo.
    return result_dataframe
