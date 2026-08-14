"""Esegue il Replay usando un modello ML registrato e verificato."""

import json
from pathlib import Path

import pandas as pd

from src.backtest.replay import ReplayConfig, run_replay
from src.data.validator import validate_ohlcv
from src.features.technical import TechnicalFeatureConfig
from src.monitoring.ml_replay import (
    MLReplayConfig,
    process_ml_replay_snapshot,
)
from src.risk.levels import RiskLevelConfig
from src.signals.confidence_filter import ConfidenceFilterConfig


def create_demo_dataframe() -> pd.DataFrame:
    """Crea uno storico sintetico per il Replay ML."""

    timestamps = pd.date_range(
        start="2026-07-01 00:00:00",
        periods=180,
        freq="15min",
        tz="UTC",
    )

    close_prices: list[float] = []
    current_price = 1.1000

    for index in range(len(timestamps)):
        if index < 60:
            movement = 0.00025
        elif index < 120:
            movement = -0.00030
        else:
            movement = 0.00035 if index % 3 != 0 else -0.00015

        current_price += movement
        close_prices.append(round(current_price, 6))

    open_prices = [
        close_prices[0] - 0.0002,
        *close_prices[:-1],
    ]

    dataframe = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_prices,
            "high": [
                max(open_price, close_price) + 0.0005
                for open_price, close_price in zip(
                    open_prices,
                    close_prices,
                    strict=True,
                )
            ],
            "low": [
                min(open_price, close_price) - 0.0005
                for open_price, close_price in zip(
                    open_prices,
                    close_prices,
                    strict=True,
                )
            ],
            "close": close_prices,
            "volume": [100 + index % 40 for index in range(len(timestamps))],
        }
    )

    return validate_ohlcv(dataframe)


def main() -> None:
    """Esegue il Replay ML e salva registro e report."""

    registry_path = Path("models/registry.json")

    log_path = Path("reports/ml_replay_log.csv")

    report_path = Path("reports/ml_replay_report.json")

    if not registry_path.exists():
        raise FileNotFoundError(
            "Model Registry non trovato. Eseguire prima scripts.register_candidate_model."
        )

    dataframe = create_demo_dataframe()

    ml_config = MLReplayConfig(
        model_version="gradient_boosting_0.1.0",
        timeframe_minutes=15,
        allowed_model_statuses=(
            "CANDIDATE",
            "APPROVED",
        ),
    )

    feature_config = TechnicalFeatureConfig(
        ema_fast_period=10,
        ema_slow_period=30,
        atr_period=14,
        volatility_period=20,
    )

    confidence_config = ConfidenceFilterConfig(
        minimum_confidence=0.60,
        minimum_probability_margin=0.10,
        fallback_signal="NO_TRADE",
    )

    risk_config = RiskLevelConfig(
        stop_atr_multiplier=1.5,
        minimum_stop_percentage=0.001,
        take_profit_1_r=1.0,
        take_profit_2_r=2.0,
        take_profit_3_r=3.0,
    )

    def processor(
        historical_snapshot: pd.DataFrame,
    ) -> pd.DataFrame:
        """Elabora lo snapshot senza riaddestrare il modello."""

        return process_ml_replay_snapshot(
            dataframe=historical_snapshot,
            registry_path=registry_path,
            replay_config=ml_config,
            feature_config=feature_config,
            confidence_config=confidence_config,
            risk_config=risk_config,
        )

    replay_log, replay_report = run_replay(
        dataframe=dataframe,
        processor=processor,
        config=ReplayConfig(
            minimum_history_bars=30,
            maximum_replay_bars=None,
            confirmed_candles_only=True,
        ),
    )

    report_dictionary = replay_report.to_dict()

    report_dictionary["model_version"] = ml_config.model_version

    report_dictionary["minimum_confidence"] = confidence_config.minimum_confidence

    report_dictionary["minimum_probability_margin"] = confidence_config.minimum_probability_margin

    report_dictionary["paper_trading_only"] = True

    log_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    replay_log.to_csv(
        log_path,
        index=False,
    )

    report_path.write_text(
        json.dumps(
            report_dictionary,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("Replay ML completato correttamente.")
    print("Modalità: PAPER ONLY")
    print(f"Snapshot: {len(replay_log)}")
    print(f"LONG: {replay_report.long_signals}")
    print(f"SHORT: {replay_report.short_signals}")
    print(f"NO_TRADE: {replay_report.no_trade_signals}")
    print("")
    print(replay_log.tail(10).to_string(index=False))
    print("")
    print(f"Replay log: {log_path.resolve()}")
    print(f"Report: {report_path.resolve()}")


if __name__ == "__main__":
    main()
