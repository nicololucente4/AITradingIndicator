"""Esegue il backtest completo sul dataset dimostrativo."""

# Importa json per salvare le metriche in formato strutturato.
import json

# Importa Path per gestire i percorsi dei file.
from pathlib import Path

# Importa pandas per costruire il dataset dimostrativo.
import pandas as pd

# Importa configurazione e motore di backtest.
from src.backtest.engine import BacktestConfig, run_backtest

# Importa il calcolo centralizzato delle metriche.
from src.backtest.metrics import calculate_backtest_metrics

# Importa il validatore dei dati OHLCV.
from src.data.validator import validate_ohlcv

# Importa la configurazione delle feature tecniche.
from src.features.technical import TechnicalFeatureConfig

# Importa configurazione e Risk Engine.
from src.risk.levels import RiskLevelConfig, build_risk_levels

# Importa configurazione e generatore della baseline.
from src.signals.baseline import (
    BaselineSignalConfig,
    build_baseline_signals,
)


def create_demo_dataframe() -> pd.DataFrame:
    """Crea un dataset dimostrativo sufficientemente lungo."""

    # Genera ottanta timestamp consecutivi da quindici minuti.
    timestamps = pd.date_range(
        start="2026-08-01 08:00:00",
        periods=80,
        freq="15min",
        tz="UTC",
    )

    # Conterrà i prezzi di chiusura delle tre fasi di mercato.
    close_prices: list[float] = []

    # Prima fase crescente.
    close_prices.extend(1.1000 + index * 0.0005 for index in range(30))

    # Seconda fase decrescente.
    second_phase_start = close_prices[-1]

    close_prices.extend(second_phase_start - (index + 1) * 0.0006 for index in range(25))

    # Terza fase nuovamente crescente.
    third_phase_start = close_prices[-1]

    close_prices.extend(third_phase_start + (index + 1) * 0.0007 for index in range(25))

    # Il primo Open precede leggermente il primo Close.
    # Gli Open successivi coincidono con il Close precedente.
    open_prices = [
        close_prices[0] - 0.0002,
        *close_prices[:-1],
    ]

    # Costruisce il dataset OHLCV.
    dataframe = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_prices,
            "high": [
                max(open_price, close_price) + 0.0008
                for open_price, close_price in zip(
                    open_prices,
                    close_prices,
                    strict=True,
                )
            ],
            "low": [
                min(open_price, close_price) - 0.0008
                for open_price, close_price in zip(
                    open_prices,
                    close_prices,
                    strict=True,
                )
            ],
            "close": close_prices,
            "volume": [100 + index for index in range(len(timestamps))],
        }
    )

    # Valida il dataset prima di restituirlo.
    return validate_ohlcv(dataframe)


def print_metrics(metrics: dict[str, int | float | None]) -> None:
    """Mostra nel terminale le metriche principali."""

    # Recupera il Profit Factor.
    profit_factor = metrics["profit_factor"]

    # Converte il valore in una stringa leggibile.
    profit_factor_text = "Non definito" if profit_factor is None else str(profit_factor)

    # Mostra il riepilogo del backtest.
    print("Backtest completato correttamente.")
    print("Modalità: PAPER ONLY")
    print(f"Trade totali: {metrics['total_trades']}")
    print(f"Trade positivi: {metrics['winning_trades']}")
    print(f"Trade negativi: {metrics['losing_trades']}")
    print(f"Win rate: {metrics['win_rate_percentage']:.2f}%")
    print(f"Rendimento netto composto simulato: {metrics['cumulative_return_percentage']:.4f}%")
    print(f"Rendimento netto medio per trade: {metrics['average_net_return_percentage']:.4f}%")
    print(f"Expectancy: {metrics['expectancy_r']:.4f} R")
    print(f"Profit Factor: {profit_factor_text}")
    print(f"Maximum Drawdown: {metrics['maximum_drawdown_percentage']:.4f}%")
    print(f"Serie massima di trade positivi: {metrics['maximum_consecutive_wins']}")
    print(f"Serie massima di trade negativi: {metrics['maximum_consecutive_losses']}")
    print(f"Costi percentuali complessivi: {metrics['total_cost_percentage']:.4f}%")


def main() -> None:
    """Esegue baseline, Risk Engine, backtest e metriche."""

    # Definisce il percorso del registro dei trade.
    trade_log_path = Path("reports/sample_backtest_trades.csv")

    # Definisce il percorso del report delle metriche.
    metrics_path = Path("reports/sample_backtest_metrics.json")

    # Crea il dataset dimostrativo.
    dataframe = create_demo_dataframe()

    # Configura le feature tecniche.
    feature_config = TechnicalFeatureConfig(
        ema_fast_period=5,
        ema_slow_period=12,
        atr_period=5,
        volatility_period=5,
    )

    # Configura la baseline deterministica.
    signal_config = BaselineSignalConfig(
        timeframe_minutes=15,
        minimum_atr_percentage=0.0001,
        maximum_atr_percentage=0.05,
        minimum_absolute_return=0.0,
    )

    # Genera feature e segnali.
    signal_dataframe = build_baseline_signals(
        dataframe=dataframe,
        feature_config=feature_config,
        signal_config=signal_config,
    )

    # Configura il Risk Engine simulato.
    risk_config = RiskLevelConfig(
        stop_atr_multiplier=1.5,
        minimum_stop_percentage=0.001,
        take_profit_1_r=1.0,
        take_profit_2_r=2.0,
        take_profit_3_r=3.0,
    )

    # Calcola i livelli teorici.
    risk_dataframe = build_risk_levels(
        dataframe=signal_dataframe,
        config=risk_config,
    )

    # Configura il backtest conservativo.
    backtest_config = BacktestConfig(
        slippage_percentage=0.0001,
        round_trip_commission_percentage=0.0002,
        maximum_holding_bars=12,
        take_profit_r=1.0,
        stop_first_when_ambiguous=True,
    )

    # Esegue il backtest.
    trades = run_backtest(
        dataframe=risk_dataframe,
        config=backtest_config,
    )

    # Calcola le metriche tramite il modulo centralizzato.
    metrics = calculate_backtest_metrics(trades)

    # Converte le metriche in un dizionario.
    metrics_dictionary = metrics.to_dict()

    # Mostra il riepilogo nel terminale.
    print_metrics(metrics_dictionary)

    # Mostra i motivi di uscita se sono presenti trade.
    if not trades.empty:
        print("")
        print("Motivi di uscita:")
        print(trades["exit_reason"].value_counts().to_string())

    # Crea la cartella dei report.
    trade_log_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Salva il registro completo dei trade.
    trades.to_csv(
        trade_log_path,
        index=False,
    )

    # Salva le metriche in formato JSON.
    metrics_path.write_text(
        json.dumps(
            metrics_dictionary,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Mostra i percorsi dei file generati.
    print("")
    print(f"Trade log: {trade_log_path.resolve()}")
    print(f"Report metriche: {metrics_path.resolve()}")


if __name__ == "__main__":
    # Avvia lo script solamente quando eseguito direttamente.
    main()
