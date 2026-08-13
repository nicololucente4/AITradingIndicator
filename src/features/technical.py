"""Calcolo delle feature tecniche basate esclusivamente su dati storici."""

# Importa dataclass per rappresentare i parametri della pipeline.
from dataclasses import dataclass

# Importa pandas per il calcolo delle serie temporali.
import pandas as pd

# Importa il validatore centrale dei dati OHLCV.
from src.data.validator import validate_ohlcv


class TechnicalFeatureError(ValueError):
    """Errore generato da una configurazione delle feature non valida."""


@dataclass(frozen=True)
class TechnicalFeatureConfig:
    """Configurazione delle feature tecniche."""

    # Periodo della media mobile esponenziale veloce.
    ema_fast_period: int = 10

    # Periodo della media mobile esponenziale lenta.
    ema_slow_period: int = 30

    # Periodo utilizzato per calcolare l'ATR.
    atr_period: int = 14

    # Periodo utilizzato per calcolare la volatilità rolling.
    volatility_period: int = 20


def _validate_config(config: TechnicalFeatureConfig) -> None:
    """Verifica che i parametri delle feature siano coerenti."""

    # Tutti i periodi devono essere strettamente positivi.
    if config.ema_fast_period <= 0:
        raise TechnicalFeatureError("Il periodo della EMA veloce deve essere maggiore di zero.")

    if config.ema_slow_period <= 0:
        raise TechnicalFeatureError("Il periodo della EMA lenta deve essere maggiore di zero.")

    if config.atr_period <= 0:
        raise TechnicalFeatureError("Il periodo ATR deve essere maggiore di zero.")

    if config.volatility_period <= 0:
        raise TechnicalFeatureError("Il periodo della volatilità deve essere maggiore di zero.")

    # La EMA veloce deve utilizzare un periodo inferiore alla EMA lenta.
    if config.ema_fast_period >= config.ema_slow_period:
        raise TechnicalFeatureError(
            "Il periodo della EMA veloce deve essere inferiore al periodo della EMA lenta."
        )


def _calculate_true_range(dataframe: pd.DataFrame) -> pd.Series:
    """Calcola il True Range usando solamente dati presenti e passati."""

    # Recupera il Close della candela precedente.
    previous_close = dataframe["close"].shift(1)

    # Calcola l'ampiezza interna della candela corrente.
    high_low_range = dataframe["high"] - dataframe["low"]

    # Calcola la distanza tra High corrente e Close precedente.
    high_previous_close = (dataframe["high"] - previous_close).abs()

    # Calcola la distanza tra Low corrente e Close precedente.
    low_previous_close = (dataframe["low"] - previous_close).abs()

    # Riunisce le tre possibili misure del True Range.
    true_range_components = pd.concat(
        [
            high_low_range,
            high_previous_close,
            low_previous_close,
        ],
        axis=1,
    )

    # Il True Range corrisponde al massimo valore disponibile per riga.
    return true_range_components.max(
        axis=1,
        skipna=True,
    )


def build_technical_features(
    dataframe: pd.DataFrame,
    config: TechnicalFeatureConfig | None = None,
) -> pd.DataFrame:
    """Aggiunge feature tecniche a un dataset OHLCV.

    Tutte le feature vengono calcolate utilizzando esclusivamente la
    candela corrente e le candele precedenti.

    Args:
        dataframe: Dataset OHLCV ordinato cronologicamente.
        config: Configurazione facoltativa delle feature tecniche.

    Returns:
        Copia del dataset OHLCV con le feature tecniche aggiunte.

    Raises:
        TechnicalFeatureError: se la configurazione non è valida.
        OHLCVValidationError: se il dataset sorgente non è valido.
    """

    # Usa la configurazione predefinita se non ne viene fornita una.
    selected_config = config or TechnicalFeatureConfig()

    # Verifica i parametri prima di calcolare le feature.
    _validate_config(selected_config)

    # Valida e normalizza il dataset OHLCV.
    featured_dataframe = validate_ohlcv(dataframe)

    # Calcola il rendimento percentuale rispetto alla candela precedente.
    featured_dataframe["return_1"] = featured_dataframe["close"].pct_change(fill_method=None)

    # Calcola la media mobile esponenziale veloce.
    featured_dataframe["ema_fast"] = (
        featured_dataframe["close"]
        .ewm(
            span=selected_config.ema_fast_period,
            adjust=False,
            min_periods=selected_config.ema_fast_period,
        )
        .mean()
    )

    # Calcola la media mobile esponenziale lenta.
    featured_dataframe["ema_slow"] = (
        featured_dataframe["close"]
        .ewm(
            span=selected_config.ema_slow_period,
            adjust=False,
            min_periods=selected_config.ema_slow_period,
        )
        .mean()
    )

    # Calcola la distanza percentuale tra le due medie.
    featured_dataframe["ema_distance_pct"] = (
        featured_dataframe["ema_fast"] / featured_dataframe["ema_slow"] - 1.0
    )

    # Calcola il True Range.
    featured_dataframe["true_range"] = _calculate_true_range(featured_dataframe)

    # Calcola l'Average True Range tramite media mobile semplice.
    featured_dataframe["atr"] = (
        featured_dataframe["true_range"]
        .rolling(
            window=selected_config.atr_period,
            min_periods=selected_config.atr_period,
        )
        .mean()
    )

    # Calcola l'ATR come percentuale del prezzo di chiusura.
    featured_dataframe["atr_pct"] = featured_dataframe["atr"] / featured_dataframe["close"]

    # Calcola la volatilità rolling dei rendimenti.
    # ddof=0 applica la deviazione standard della popolazione.
    featured_dataframe["volatility"] = (
        featured_dataframe["return_1"]
        .rolling(
            window=selected_config.volatility_period,
            min_periods=selected_config.volatility_period,
        )
        .std(ddof=0)
    )

    # Restituisce il dataset completo senza eliminare i valori NaN iniziali.
    return featured_dataframe
