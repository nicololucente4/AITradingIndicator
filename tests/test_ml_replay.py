"""Test automatici del processore Replay ML."""

import json
from pathlib import Path

import joblib
import pandas as pd
import pytest
from sklearn.ensemble import HistGradientBoostingClassifier

from src.features.technical import TechnicalFeatureConfig
from src.models.registry import calculate_file_sha256
from src.monitoring.ml_replay import (
    MLReplayConfig,
    MLReplayError,
    process_ml_replay_snapshot,
)
from src.risk.levels import RiskLevelConfig
from src.signals.confidence_filter import ConfidenceFilterConfig


def create_ohlcv_dataframe(
    candle_count: int = 20,
) -> pd.DataFrame:
    """Crea uno storico OHLCV deterministico."""

    timestamps = pd.date_range(
        start="2026-08-14 08:00:00",
        periods=candle_count,
        freq="15min",
        tz="UTC",
    )

    close_prices = [100.0 + index * 0.20 for index in range(candle_count)]

    open_prices = [
        close_prices[0] - 0.10,
        *close_prices[:-1],
    ]

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_prices,
            "high": [
                max(open_price, close_price) + 0.50
                for open_price, close_price in zip(
                    open_prices,
                    close_prices,
                    strict=True,
                )
            ],
            "low": [
                min(open_price, close_price) - 0.50
                for open_price, close_price in zip(
                    open_prices,
                    close_prices,
                    strict=True,
                )
            ],
            "close": close_prices,
            "volume": [100 + index for index in range(candle_count)],
        }
    )


def create_model_registry(
    tmp_path: Path,
) -> Path:
    """Crea un modello compatibile e il relativo Registry."""

    feature_columns = [
        "return_1",
        "ema_fast",
        "ema_slow",
        "ema_distance_pct",
        "true_range",
        "atr",
        "atr_pct",
        "volatility",
    ]

    training_features = pd.DataFrame(
        {
            "return_1": [
                -0.02,
                -0.01,
                0.00,
                0.01,
                0.02,
                0.03,
            ],
            "ema_fast": [
                99.0,
                99.5,
                100.0,
                100.5,
                101.0,
                101.5,
            ],
            "ema_slow": [
                100.0,
                100.0,
                100.0,
                100.0,
                100.0,
                100.0,
            ],
            "ema_distance_pct": [
                -0.01,
                -0.005,
                0.0,
                0.005,
                0.01,
                0.015,
            ],
            "true_range": [
                1.0,
                1.0,
                1.0,
                1.0,
                1.0,
                1.0,
            ],
            "atr": [
                1.0,
                1.0,
                1.0,
                1.0,
                1.0,
                1.0,
            ],
            "atr_pct": [
                0.01,
                0.01,
                0.01,
                0.01,
                0.01,
                0.01,
            ],
            "volatility": [
                0.01,
                0.01,
                0.01,
                0.01,
                0.01,
                0.01,
            ],
        }
    )

    training_target = pd.Series(
        [
            "SHORT",
            "SHORT",
            "NO_TRADE",
            "LONG",
            "LONG",
            "LONG",
        ]
    )

    model = HistGradientBoostingClassifier(
        max_iter=20,
        min_samples_leaf=1,
        random_state=42,
        early_stopping=False,
    )

    model.fit(
        training_features,
        training_target,
    )

    model_path = tmp_path / "model.joblib"

    joblib.dump(
        model,
        model_path,
    )

    registry_path = tmp_path / "registry.json"

    registry_entry = {
        "model_version": "replay_model_0.1.0",
        "model_type": "HIST_GRADIENT_BOOSTING",
        "status": "CANDIDATE",
        "model_path": str(model_path),
        "model_sha256": calculate_file_sha256(model_path),
        "feature_set_version": "0.1.0",
        "feature_columns": feature_columns,
        "validation_type": "TEST",
        "fold_count": 2,
        "mean_macro_f1": 0.5,
        "minimum_macro_f1": 0.4,
        "mean_accuracy": 0.6,
        "registered_at_utc": ("2026-08-14T10:00:00+00:00"),
        "paper_trading_only": True,
    }

    registry_path.write_text(
        json.dumps(
            [registry_entry],
            indent=4,
        ),
        encoding="utf-8",
    )

    return registry_path


def create_feature_config() -> TechnicalFeatureConfig:
    """Crea una configurazione breve per i test."""

    return TechnicalFeatureConfig(
        ema_fast_period=2,
        ema_slow_period=4,
        atr_period=3,
        volatility_period=3,
    )


def create_confidence_config() -> ConfidenceFilterConfig:
    """Crea le soglie del filtro."""

    return ConfidenceFilterConfig(
        minimum_confidence=0.0,
        minimum_probability_margin=0.0,
        fallback_signal="NO_TRADE",
    )


def create_risk_config() -> RiskLevelConfig:
    """Crea la configurazione dei livelli simulati."""

    return RiskLevelConfig(
        stop_atr_multiplier=1.5,
        minimum_stop_percentage=0.001,
        take_profit_1_r=1.0,
        take_profit_2_r=2.0,
        take_profit_3_r=3.0,
    )


def test_snapshot_generates_confirmed_ml_signal(
    tmp_path: Path,
) -> None:
    """Verifica la generazione del segnale ML confermato."""

    registry_path = create_model_registry(tmp_path)

    result = process_ml_replay_snapshot(
        dataframe=create_ohlcv_dataframe(),
        registry_path=registry_path,
        replay_config=MLReplayConfig(
            model_version="replay_model_0.1.0",
        ),
        feature_config=create_feature_config(),
        confidence_config=create_confidence_config(),
        risk_config=create_risk_config(),
    )

    assert len(result) == 1
    assert result.loc[0, "signal_status"] == "CONFIRMED"
    assert result.loc[0, "signal_source"] == ("REGISTERED_ML_MODEL")
    assert result.loc[0, "execution_mode"] == "PAPER_ONLY"


def test_signal_is_available_at_candle_close(
    tmp_path: Path,
) -> None:
    """Verifica il timestamp di disponibilità del segnale."""

    registry_path = create_model_registry(tmp_path)

    result = process_ml_replay_snapshot(
        dataframe=create_ohlcv_dataframe(),
        registry_path=registry_path,
        replay_config=MLReplayConfig(
            model_version="replay_model_0.1.0",
            timeframe_minutes=15,
        ),
        feature_config=create_feature_config(),
        confidence_config=create_confidence_config(),
        risk_config=create_risk_config(),
    )

    assert result.loc[0, "signal_available_at"] == (
        result.loc[0, "timestamp"] + pd.Timedelta(minutes=15)
    )


def test_probabilities_and_model_audit_are_present(
    tmp_path: Path,
) -> None:
    """Verifica probabilità e informazioni del modello."""

    registry_path = create_model_registry(tmp_path)

    result = process_ml_replay_snapshot(
        dataframe=create_ohlcv_dataframe(),
        registry_path=registry_path,
        replay_config=MLReplayConfig(
            model_version="replay_model_0.1.0",
        ),
        feature_config=create_feature_config(),
        confidence_config=create_confidence_config(),
        risk_config=create_risk_config(),
    )

    required_columns = {
        "probability_long",
        "probability_short",
        "probability_no_trade",
        "prediction_confidence",
        "probability_margin",
        "model_version",
        "model_type",
        "model_status",
        "model_sha256",
    }

    assert required_columns.issubset(result.columns)

    probability_sum = (
        result.loc[0, "probability_long"]
        + result.loc[0, "probability_short"]
        + result.loc[0, "probability_no_trade"]
    )

    assert probability_sum == pytest.approx(1.0)


def test_risk_levels_follow_filtered_signal(
    tmp_path: Path,
) -> None:
    """Verifica la coerenza dei livelli con il segnale filtrato."""

    registry_path = create_model_registry(tmp_path)

    result = process_ml_replay_snapshot(
        dataframe=create_ohlcv_dataframe(),
        registry_path=registry_path,
        replay_config=MLReplayConfig(
            model_version="replay_model_0.1.0",
        ),
        feature_config=create_feature_config(),
        confidence_config=create_confidence_config(),
        risk_config=create_risk_config(),
    )

    signal = result.loc[0, "signal"]

    if signal == "NO_TRADE":
        assert pd.isna(result.loc[0, "entry_price"])
        assert pd.isna(result.loc[0, "stop_loss"])
    else:
        assert not pd.isna(result.loc[0, "entry_price"])
        assert not pd.isna(result.loc[0, "stop_loss"])
        assert not pd.isna(result.loc[0, "take_profit_1"])


def test_warmup_snapshot_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il rifiuto prima del completamento del warm-up."""

    registry_path = create_model_registry(tmp_path)

    with pytest.raises(
        MLReplayError,
        match="warm-up",
    ):
        process_ml_replay_snapshot(
            dataframe=create_ohlcv_dataframe(candle_count=2),
            registry_path=registry_path,
            replay_config=MLReplayConfig(
                model_version="replay_model_0.1.0",
            ),
            feature_config=create_feature_config(),
            confidence_config=create_confidence_config(),
            risk_config=create_risk_config(),
        )


def test_original_ohlcv_is_not_modified(
    tmp_path: Path,
) -> None:
    """Verifica che lo storico sorgente rimanga invariato."""

    registry_path = create_model_registry(tmp_path)

    dataframe = create_ohlcv_dataframe()
    original_dataframe = dataframe.copy(deep=True)

    process_ml_replay_snapshot(
        dataframe=dataframe,
        registry_path=registry_path,
        replay_config=MLReplayConfig(
            model_version="replay_model_0.1.0",
        ),
        feature_config=create_feature_config(),
        confidence_config=create_confidence_config(),
        risk_config=create_risk_config(),
    )

    pd.testing.assert_frame_equal(
        dataframe,
        original_dataframe,
    )


def test_invalid_timeframe_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il rifiuto di un timeframe non valido."""

    registry_path = create_model_registry(tmp_path)

    with pytest.raises(
        MLReplayError,
        match="timeframe",
    ):
        process_ml_replay_snapshot(
            dataframe=create_ohlcv_dataframe(),
            registry_path=registry_path,
            replay_config=MLReplayConfig(
                model_version="replay_model_0.1.0",
                timeframe_minutes=0,
            ),
            feature_config=create_feature_config(),
            confidence_config=create_confidence_config(),
            risk_config=create_risk_config(),
        )
