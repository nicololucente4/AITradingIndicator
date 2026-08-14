"""Replay ML con inferenza registrata, filtro di confidenza e Risk Engine."""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.features.technical import (
    TechnicalFeatureConfig,
    build_technical_features,
)
from src.models.dataset import DEFAULT_FEATURE_COLUMNS
from src.models.inference import run_registered_inference
from src.risk.levels import RiskLevelConfig, build_risk_levels
from src.signals.confidence_filter import (
    ConfidenceFilterConfig,
    apply_confidence_filter,
)


class MLReplayError(ValueError):
    """Errore generato durante l'elaborazione Replay ML."""


@dataclass(frozen=True)
class MLReplayConfig:
    """Configurazione del processore Replay ML."""

    # Versione esatta del modello registrato.
    model_version: str

    # Durata della candela operativa.
    timeframe_minutes: int = 15

    # Stati del modello ammessi durante lo sviluppo.
    allowed_model_statuses: tuple[str, ...] = (
        "CANDIDATE",
        "APPROVED",
    )


def _validate_config(config: MLReplayConfig) -> None:
    """Verifica la configurazione Replay ML."""

    # La versione del modello deve essere valorizzata.
    if not config.model_version.strip():
        raise MLReplayError("La versione del modello non può essere vuota.")

    # Il timeframe deve essere positivo.
    if config.timeframe_minutes <= 0:
        raise MLReplayError("Il timeframe deve essere maggiore di zero.")

    # Deve essere ammesso almeno uno stato.
    if not config.allowed_model_statuses:
        raise MLReplayError("Deve essere consentito almeno uno stato del modello.")

    # Definisce gli stati supportati.
    supported_statuses = {
        "CANDIDATE",
        "APPROVED",
    }

    # Individua eventuali stati non supportati.
    invalid_statuses = sorted(set(config.allowed_model_statuses).difference(supported_statuses))

    if invalid_statuses:
        invalid_text = ", ".join(invalid_statuses)

        raise MLReplayError(f"Stati del modello non supportati: {invalid_text}.")


def process_ml_replay_snapshot(
    dataframe: pd.DataFrame,
    registry_path: str | Path,
    replay_config: MLReplayConfig,
    feature_config: TechnicalFeatureConfig,
    confidence_config: ConfidenceFilterConfig,
    risk_config: RiskLevelConfig,
) -> pd.DataFrame:
    """Elabora uno snapshot storico tramite il modello registrato.

    Il modello non viene riaddestrato. Le feature vengono calcolate
    utilizzando solamente le candele presenti nello snapshot.

    Args:
        dataframe: Storico disponibile fino alla candela corrente.
        registry_path: Percorso del Model Registry.
        replay_config: Configurazione Replay ML.
        feature_config: Configurazione delle feature tecniche.
        confidence_config: Soglie del filtro ML.
        risk_config: Configurazione dei livelli TP e SL.

    Returns:
        Dataset con l'ultima previsione ML confermata e i livelli simulati.
    """

    # Valida la configurazione principale.
    _validate_config(replay_config)

    # Calcola le feature esclusivamente sullo storico ricevuto.
    featured_dataframe = build_technical_features(
        dataframe=dataframe,
        config=feature_config,
    )

    # Seleziona solamente le righe con tutte le feature disponibili.
    valid_feature_rows = featured_dataframe[list(DEFAULT_FEATURE_COLUMNS)].notna().all(axis=1)

    # Il modello non può essere utilizzato prima del completamento
    # del periodo di warm-up.
    if not valid_feature_rows.iloc[-1]:
        raise MLReplayError(
            "Le feature della candela corrente non sono ancora disponibili dopo il warm-up."
        )

    # Estrae esclusivamente l'ultima riga delle feature.
    current_features = featured_dataframe.loc[
        [featured_dataframe.index[-1]],
        list(DEFAULT_FEATURE_COLUMNS),
    ].reset_index(drop=True)

    # Esegue l'inferenza senza effettuare alcun training.
    raw_prediction = run_registered_inference(
        features=current_features,
        registry_path=registry_path,
        model_version=replay_config.model_version,
        allowed_statuses=set(replay_config.allowed_model_statuses),
    )

    # Applica il filtro di confidenza.
    filtered_prediction = apply_confidence_filter(
        predictions=raw_prediction,
        config=confidence_config,
    )

    # Recupera la candela corrente con le relative feature.
    current_row = featured_dataframe.iloc[[-1]].copy().reset_index(drop=True)

    # Il segnale finale proviene dalla previsione filtrata.
    current_row["signal"] = filtered_prediction.loc[
        0,
        "filtered_signal",
    ]

    # Memorizza la previsione grezza per audit.
    current_row["raw_ml_prediction"] = filtered_prediction.loc[
        0,
        "raw_prediction",
    ]

    # Memorizza probabilità, confidenza e margine.
    current_row["probability_long"] = filtered_prediction.loc[
        0,
        "probability_long",
    ]

    current_row["probability_short"] = filtered_prediction.loc[
        0,
        "probability_short",
    ]

    current_row["probability_no_trade"] = filtered_prediction.loc[
        0,
        "probability_no_trade",
    ]

    current_row["prediction_confidence"] = filtered_prediction.loc[
        0,
        "prediction_confidence",
    ]

    current_row["probability_margin"] = filtered_prediction.loc[
        0,
        "probability_margin",
    ]

    current_row["filter_reason"] = filtered_prediction.loc[
        0,
        "filter_reason",
    ]

    # Registra versione, tipo, stato e hash del modello.
    current_row["model_version"] = filtered_prediction.loc[
        0,
        "model_version",
    ]

    current_row["model_type"] = filtered_prediction.loc[
        0,
        "model_type",
    ]

    current_row["model_status"] = filtered_prediction.loc[
        0,
        "model_status",
    ]

    current_row["model_sha256"] = filtered_prediction.loc[
        0,
        "model_sha256",
    ]

    # Il timestamp OHLCV rappresenta l'apertura della candela.
    # Il segnale diventa disponibile solamente alla sua chiusura.
    current_row["signal_available_at"] = current_row["timestamp"] + pd.to_timedelta(
        replay_config.timeframe_minutes,
        unit="minutes",
    )

    # Il segnale Replay ML è sempre confermato.
    current_row["signal_status"] = "CONFIRMED"

    # Identifica la sorgente della decisione.
    current_row["signal_source"] = "REGISTERED_ML_MODEL"

    # Aggiunge Entry teorica, Stop Loss e Take Profit.
    result = build_risk_levels(
        dataframe=current_row,
        config=risk_config,
    )

    # Registra esplicitamente la modalità simulata.
    result["operating_mode"] = "REPLAY_ML"
    result["execution_mode"] = "PAPER_ONLY"

    # Restituisce una sola riga, relativa alla candela corrente.
    return result.reset_index(drop=True)
