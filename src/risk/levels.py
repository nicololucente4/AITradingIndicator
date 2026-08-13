"""Calcolo dei livelli teorici di rischio per il paper trading."""

# Importa dataclass per rappresentare la configurazione del Risk Engine.
from dataclasses import dataclass

# Importa NumPy per rappresentare i livelli non disponibili con NaN.
import numpy as np

# Importa pandas per elaborare il dataset dei segnali.
import pandas as pd


class RiskLevelError(ValueError):
    """Errore generato da dati o configurazioni di rischio non validi."""


@dataclass(frozen=True)
class RiskLevelConfig:
    """Configurazione dei livelli teorici di rischio."""

    # Moltiplicatore applicato all'ATR per calcolare lo Stop Loss.
    stop_atr_multiplier: float = 1.5

    # Distanza minima dello Stop Loss rispetto all'Entry.
    minimum_stop_percentage: float = 0.001

    # Rapporto rischio/rendimento del primo Take Profit.
    take_profit_1_r: float = 1.0

    # Rapporto rischio/rendimento del secondo Take Profit.
    take_profit_2_r: float = 2.0

    # Rapporto rischio/rendimento del terzo Take Profit.
    take_profit_3_r: float = 3.0


def _validate_config(config: RiskLevelConfig) -> None:
    """Verifica che la configurazione di rischio sia coerente."""

    # Il moltiplicatore ATR deve essere strettamente positivo.
    if config.stop_atr_multiplier <= 0:
        raise RiskLevelError("Il moltiplicatore ATR dello Stop Loss deve essere maggiore di zero.")

    # La distanza minima percentuale non può essere negativa.
    if config.minimum_stop_percentage < 0:
        raise RiskLevelError(
            "La distanza minima percentuale dello Stop Loss non può essere negativa."
        )

    # Tutti i rapporti rischio/rendimento devono essere positivi.
    take_profit_ratios = [
        config.take_profit_1_r,
        config.take_profit_2_r,
        config.take_profit_3_r,
    ]

    if any(ratio <= 0 for ratio in take_profit_ratios):
        raise RiskLevelError("I rapporti rischio/rendimento devono essere maggiori di zero.")

    # I Take Profit devono essere ordinati dal più vicino al più lontano.
    if not (config.take_profit_1_r < config.take_profit_2_r < config.take_profit_3_r):
        raise RiskLevelError("I rapporti dei Take Profit devono essere strettamente crescenti.")


def _validate_input_columns(dataframe: pd.DataFrame) -> None:
    """Verifica la presenza delle colonne necessarie."""

    # Definisce le colonne richieste dal Risk Engine.
    required_columns = {
        "timestamp",
        "close",
        "atr",
        "signal",
        "signal_available_at",
        "signal_status",
    }

    # Individua le colonne mancanti.
    missing_columns = sorted(required_columns.difference(dataframe.columns))

    # Interrompe l'elaborazione se manca almeno una colonna.
    if missing_columns:
        missing_text = ", ".join(missing_columns)

        raise RiskLevelError(f"Colonne necessarie al Risk Engine mancanti: {missing_text}.")


def _validate_signals(dataframe: pd.DataFrame) -> None:
    """Verifica che il dataset contenga solamente segnali supportati."""

    # Definisce gli stati riconosciuti dal Risk Engine.
    allowed_signals = {
        "LONG",
        "SHORT",
        "NO_TRADE",
    }

    # Individua eventuali valori non supportati.
    invalid_signals = sorted(set(dataframe["signal"].dropna()).difference(allowed_signals))

    # Interrompe l'elaborazione se esistono segnali sconosciuti.
    if invalid_signals:
        invalid_text = ", ".join(invalid_signals)

        raise RiskLevelError(f"Segnali non supportati dal Risk Engine: {invalid_text}.")


def _calculate_stop_distance(
    entry_price: float,
    atr_value: float,
    config: RiskLevelConfig,
) -> float:
    """Calcola la distanza dello Stop Loss dall'Entry."""

    # Calcola la distanza basata sulla volatilità.
    atr_distance = atr_value * config.stop_atr_multiplier

    # Calcola la distanza minima percentuale ammessa.
    minimum_distance = entry_price * config.minimum_stop_percentage

    # Utilizza la distanza più prudente tra ATR e soglia minima.
    return max(
        atr_distance,
        minimum_distance,
    )


def _empty_risk_levels() -> dict[str, float]:
    """Restituisce livelli vuoti per un segnale non operativo."""

    # I valori NaN indicano che non esiste alcun piano operativo.
    return {
        "entry_price": np.nan,
        "stop_loss": np.nan,
        "risk_distance": np.nan,
        "take_profit_1": np.nan,
        "take_profit_2": np.nan,
        "take_profit_3": np.nan,
        "risk_reward_1": np.nan,
        "risk_reward_2": np.nan,
        "risk_reward_3": np.nan,
    }


def _calculate_row_levels(
    row: pd.Series,
    config: RiskLevelConfig,
) -> dict[str, float]:
    """Calcola i livelli teorici per una singola riga."""

    # NO_TRADE non deve produrre Entry, Stop Loss o Take Profit.
    if row["signal"] == "NO_TRADE":
        return _empty_risk_levels()

    # Genera livelli solamente per segnali confermati.
    if row["signal_status"] != "CONFIRMED":
        return _empty_risk_levels()

    # Non genera livelli se ATR o Close non sono disponibili.
    if pd.isna(row["atr"]) or pd.isna(row["close"]):
        return _empty_risk_levels()

    # Converte Entry e ATR in valori float.
    entry_price = float(row["close"])
    atr_value = float(row["atr"])

    # Entry e ATR devono essere strettamente positivi.
    if entry_price <= 0 or atr_value <= 0:
        return _empty_risk_levels()

    # Calcola la distanza teorica tra Entry e Stop Loss.
    risk_distance = _calculate_stop_distance(
        entry_price=entry_price,
        atr_value=atr_value,
        config=config,
    )

    # Calcola i livelli per un segnale LONG.
    if row["signal"] == "LONG":
        stop_loss = entry_price - risk_distance

        take_profit_1 = entry_price + risk_distance * config.take_profit_1_r
        take_profit_2 = entry_price + risk_distance * config.take_profit_2_r
        take_profit_3 = entry_price + risk_distance * config.take_profit_3_r

    # Calcola i livelli speculari per un segnale SHORT.
    else:
        stop_loss = entry_price + risk_distance

        take_profit_1 = entry_price - risk_distance * config.take_profit_1_r
        take_profit_2 = entry_price - risk_distance * config.take_profit_2_r
        take_profit_3 = entry_price - risk_distance * config.take_profit_3_r

    # Restituisce il piano di rischio completo.
    return {
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "risk_distance": risk_distance,
        "take_profit_1": take_profit_1,
        "take_profit_2": take_profit_2,
        "take_profit_3": take_profit_3,
        "risk_reward_1": config.take_profit_1_r,
        "risk_reward_2": config.take_profit_2_r,
        "risk_reward_3": config.take_profit_3_r,
    }


def build_risk_levels(
    dataframe: pd.DataFrame,
    config: RiskLevelConfig | None = None,
) -> pd.DataFrame:
    """Aggiunge livelli teorici di rischio ai segnali confermati.

    Il prezzo di chiusura della candela viene utilizzato come Entry di
    riferimento. I livelli sono esclusivamente simulati e non producono
    ordini o raccomandazioni operative.

    Args:
        dataframe: Dataset contenente segnali e feature tecniche.
        config: Configurazione facoltativa del Risk Engine.

    Returns:
        Copia del dataset con Entry, Stop Loss e Take Profit teorici.
    """

    # Verifica che l'input sia un DataFrame.
    if not isinstance(dataframe, pd.DataFrame):
        raise TypeError("Il dato ricevuto deve essere un pandas DataFrame.")

    # Impedisce l'elaborazione di dataset vuoti.
    if dataframe.empty:
        raise RiskLevelError("Il dataset dei segnali è vuoto.")

    # Usa la configurazione predefinita se non specificata.
    selected_config = config or RiskLevelConfig()

    # Valida configurazione, colonne e segnali.
    _validate_config(selected_config)
    _validate_input_columns(dataframe)
    _validate_signals(dataframe)

    # Crea una copia per non modificare il dataset originale.
    result_dataframe = dataframe.copy(deep=True)

    # Calcola il piano di rischio di ogni riga.
    calculated_levels = result_dataframe.apply(
        lambda row: _calculate_row_levels(
            row=row,
            config=selected_config,
        ),
        axis=1,
        result_type="expand",
    )

    # Aggiunge ogni colonna calcolata al risultato.
    for column in calculated_levels.columns:
        result_dataframe[column] = calculated_levels[column]

    # Identifica esplicitamente la natura simulata dei livelli.
    result_dataframe["risk_status"] = "PAPER_ONLY"

    # Registra la logica utilizzata per lo Stop Loss.
    result_dataframe["risk_method"] = "ATR_AND_MINIMUM_PERCENTAGE"

    # I livelli diventano disponibili insieme al segnale confermato.
    result_dataframe["risk_available_at"] = result_dataframe["signal_available_at"]

    # Restituisce il dataset completo.
    return result_dataframe
