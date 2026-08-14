"""Esegue il backtest completo sul dataset M15 di esempio."""

# Importa Path per gestire i percorsi dei file.
from pathlib import Path

# Importa pandas per creare il dataset dimostrativo esteso
# e salvare il registro dei trade.
import pandas as pd

# Importa configurazione e motore di backtest.
from src.backtest.engine import BacktestConfig, run_backtest

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

    # Crea tre fasi di mercato:
    # crescita, discesa e nuova crescita.
    close_prices: list[float] = []

    # Prima fase crescente.
    close_prices.extend(1.1000 + index * 0.0005 for index in range(30))

    # Seconda fase decrescente.
    second_phase_start = close_prices[-1]
    close_prices.extend(second_phase_start - (index + 1) * 0.0006 for index in range(25))

    # Terza fase nuovamente crescente.
    third_phase_start = close_prices[-1]
    close_prices.extend(third_phase_start + (index + 1) * 0.0007 for index in range(25))

    # Costruisce prezzi Open coerenti con il Close precedente.
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


def print_summary(trades: pd.DataFrame) -> None:
    """Mostra un riepilogo essenziale del backtest."""

    # Gestisce il caso in cui non siano stati generati trade.
    if trades.empty:
        print("Nessun trade generato dalla configurazione corrente.")
        return

    # Identifica i trade con rendimento netto positivo.
    winning_trades = trades[trades["net_return_percentage"] > 0]

    # Calcola il rendimento netto cumulato in modo composto.
    cumulative_return = (1.0 + trades["net_return_percentage"]).prod() - 1.0

    # Calcola la percentuale di trade positivi.
    win_rate = (len(winning_trades) / len(trades)) * 100.0

    # Calcola il risultato medio espresso in R.
    average_result_r = trades["result_r"].mean()

    # Mostra il riepilogo.
    print("Backtest completato correttamente.")
    print("Modalità: PAPER ONLY")
    print(f"Trade totali: {len(trades)}")
    print(f"Trade positivi: {len(winning_trades)}")
    print(f"Win rate: {win_rate:.2f}%")
    print(f"Rendimento netto composto simulato: {cumulative_return * 100:.4f}%")
    print(f"Risultato medio: {average_result_r:.4f} R")
    print("")
    print("Motivi di uscita:")
    print(trades["exit_reason"].value_counts().to_string())


def main() -> None:
    """Esegue l'intera pipeline baseline, rischio e backtest."""

    # Definisce il percorso del registro trade da generare.
    output_path = Path("reports/sample_backtest_trades.csv")

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

    # Configura i livelli teorici di rischio.
    risk_config = RiskLevelConfig(
        stop_atr_multiplier=1.5,
        minimum_stop_percentage=0.001,
        take_profit_1_r=1.0,
        take_profit_2_r=2.0,
        take_profit_3_r=3.0,
    )

    # Calcola Entry teorica, SL e TP.
    risk_dataframe = build_risk_levels(
        dataframe=signal_dataframe,
        config=risk_config,
    )

    # Configura il motore di backtest.
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

    # Mostra il riepilogo nel terminale.
    print_summary(trades)

    # Crea la cartella del report se necessaria.
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Salva il registro dei trade.
    trades.to_csv(
        output_path,
        index=False,
    )

    # Mostra il percorso del file generato.
    print("")
    print(f"Trade log creato: {output_path.resolve()}")


if __name__ == "__main__":
    # Avvia lo script solamente quando eseguito direttamente.
    main()
