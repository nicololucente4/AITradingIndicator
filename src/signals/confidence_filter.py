"""Filtro di confidenza applicato alle predizioni Machine Learning."""

from dataclasses import dataclass

import numpy as np
import pandas as pd


class ConfidenceFilterError(ValueError):
    """Errore generato da predizioni o configurazioni non valide."""


@dataclass(frozen=True)
class ConfidenceFilterConfig:
    """Configurazione del filtro di confidenza ML."""

    # Probabilità minima richiesta per mantenere LONG o SHORT.
    minimum_confidence: float = 0.60

    # Differenza minima tra prima e seconda probabilità.
    minimum_probability_margin: float = 0.10

    # Segnale utilizzato quando la previsione viene filtrata.
    fallback_signal: str = "NO_TRADE"


def _validate_config(config: ConfidenceFilterConfig) -> None:
    """Verifica i parametri del filtro."""

    # La confidenza deve essere compresa tra zero e uno.
    if not 0.0 <= config.minimum_confidence <= 1.0:
        raise ConfidenceFilterError("La confidenza minima deve essere compresa tra zero e uno.")

    # Anche il margine deve essere compreso tra zero e uno.
    if not 0.0 <= config.minimum_probability_margin <= 1.0:
        raise ConfidenceFilterError("Il margine minimo deve essere compreso tra zero e uno.")

    # In questa versione il fallback deve essere NO_TRADE.
    if config.fallback_signal != "NO_TRADE":
        raise ConfidenceFilterError("Il segnale fallback deve essere NO_TRADE.")


def _validate_predictions(predictions: pd.DataFrame) -> None:
    """Verifica struttura e probabilità delle predizioni."""

    # Verifica che l'input sia un DataFrame.
    if not isinstance(predictions, pd.DataFrame):
        raise TypeError("Le predizioni devono essere un pandas DataFrame.")

    # Il dataset non può essere vuoto.
    if predictions.empty:
        raise ConfidenceFilterError("Il dataset delle predizioni è vuoto.")

    # Definisce le colonne necessarie.
    required_columns = {
        "predicted_target",
        "probability_long",
        "probability_short",
        "probability_no_trade",
    }

    # Individua le colonne mancanti.
    missing_columns = sorted(required_columns.difference(predictions.columns))

    if missing_columns:
        missing_text = ", ".join(missing_columns)

        raise ConfidenceFilterError(f"Colonne necessarie al filtro mancanti: {missing_text}.")

    # Seleziona le colonne di probabilità.
    probability_columns = [
        "probability_long",
        "probability_short",
        "probability_no_trade",
    ]

    # Le probabilità non possono contenere valori mancanti.
    if predictions[probability_columns].isna().any().any():
        raise ConfidenceFilterError("Le probabilità contengono valori mancanti.")

    # Le probabilità devono essere comprese tra zero e uno.
    invalid_probability = (
        predictions[probability_columns].lt(0).any().any()
        or predictions[probability_columns].gt(1).any().any()
    )

    if invalid_probability:
        raise ConfidenceFilterError("Le probabilità devono essere comprese tra zero e uno.")

    # Le probabilità delle tre classi devono sommare a uno.
    probability_sums = predictions[probability_columns].sum(axis=1)

    if not np.allclose(
        probability_sums.to_numpy(),
        1.0,
        atol=1e-6,
    ):
        raise ConfidenceFilterError("Le probabilità delle classi non sommano a uno.")

    # Verifica le classi previste.
    allowed_targets = {
        "LONG",
        "SHORT",
        "NO_TRADE",
    }

    invalid_targets = sorted(set(predictions["predicted_target"]).difference(allowed_targets))

    if invalid_targets:
        invalid_text = ", ".join(invalid_targets)

        raise ConfidenceFilterError(f"Predizioni non supportate: {invalid_text}.")


def apply_confidence_filter(
    predictions: pd.DataFrame,
    config: ConfidenceFilterConfig | None = None,
) -> pd.DataFrame:
    """Applica soglie di confidenza e margine alle predizioni ML.

    La previsione originale viene mantenuta nella colonna raw_prediction.
    Le previsioni LONG e SHORT che non superano entrambe le soglie
    vengono trasformate in NO_TRADE.

    Args:
        predictions: Predizioni e probabilità del modello.
        config: Configurazione facoltativa del filtro.

    Returns:
        Copia delle predizioni con segnale filtrato e motivazione.
    """

    # Usa la configurazione predefinita se non specificata.
    selected_config = config or ConfidenceFilterConfig()

    # Valida configurazione e predizioni.
    _validate_config(selected_config)
    _validate_predictions(predictions)

    # Crea una copia per non modificare l'input.
    result = predictions.copy(deep=True)

    # Mantiene la previsione originale del modello.
    result["raw_prediction"] = result["predicted_target"]

    # Ordina le probabilità di ogni riga dal valore più alto al più basso.
    sorted_probabilities = np.sort(
        result[
            [
                "probability_long",
                "probability_short",
                "probability_no_trade",
            ]
        ].to_numpy(),
        axis=1,
    )

    # La confidenza corrisponde alla probabilità più alta.
    result["prediction_confidence"] = sorted_probabilities[:, -1]

    # Il margine è la differenza tra le due probabilità più alte.
    result["probability_margin"] = sorted_probabilities[:, -1] - sorted_probabilities[:, -2]

    # Verifica il superamento della soglia di confidenza.
    result["passes_confidence"] = (
        result["prediction_confidence"] >= selected_config.minimum_confidence
    )

    # Verifica il superamento della soglia di margine.
    result["passes_margin"] = (
        result["probability_margin"] >= selected_config.minimum_probability_margin
    )

    # Una previsione è accettata solamente se supera entrambe le soglie.
    result["prediction_accepted"] = result["passes_confidence"] & result["passes_margin"]

    # Mantiene NO_TRADE anche quando è già la classe prevista dal modello.
    result["filtered_signal"] = result["raw_prediction"]

    # Converte in NO_TRADE le previsioni direzionali non sufficientemente forti.
    directional_rejected = (
        result["raw_prediction"].isin({"LONG", "SHORT"}) & ~result["prediction_accepted"]
    )

    result.loc[
        directional_rejected,
        "filtered_signal",
    ] = selected_config.fallback_signal

    # Definisce una motivazione iniziale per le previsioni accettate.
    result["filter_reason"] = "PREDICTION_ACCEPTED"

    # Identifica i NO_TRADE originariamente previsti dal modello.
    raw_no_trade = result["raw_prediction"].eq("NO_TRADE")

    result.loc[
        raw_no_trade,
        "filter_reason",
    ] = "MODEL_PREDICTED_NO_TRADE"

    # Identifica le previsioni sotto la soglia di confidenza.
    low_confidence = directional_rejected & ~result["passes_confidence"]

    result.loc[
        low_confidence,
        "filter_reason",
    ] = "LOW_CONFIDENCE"

    # Identifica le previsioni con margine insufficiente.
    low_margin = directional_rejected & result["passes_confidence"] & ~result["passes_margin"]

    result.loc[
        low_margin,
        "filter_reason",
    ] = "LOW_PROBABILITY_MARGIN"

    # Identifica i casi che falliscono entrambe le soglie.
    both_failed = directional_rejected & ~result["passes_confidence"] & ~result["passes_margin"]

    result.loc[
        both_failed,
        "filter_reason",
    ] = "LOW_CONFIDENCE_AND_MARGIN"

    # Registra le soglie applicate.
    result["minimum_confidence_threshold"] = selected_config.minimum_confidence

    result["minimum_margin_threshold"] = selected_config.minimum_probability_margin

    # Restituisce le predizioni filtrate.
    return result
