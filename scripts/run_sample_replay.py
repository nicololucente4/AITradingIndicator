"""Esegue una sessione Replay completa su un dataset dimostrativo."""

# Importa json per salvare il report della sessione.
import json

# Importa Path per gestire i percorsi dei file.
from pathlib import Path

# Importa pandas per costruire il dataset dimostrativo.
import pandas as pd

# Importa configurazione e motore Replay.
from src.backtest.replay import ReplayConfig, run_replay

# Importa il validatore OHLCV.
from src.data.validator import validate_ohlcv

# Importa la configurazione delle feature tecniche.
from src.features.technical import TechnicalFeatureConfig

# Importa configurazione e Risk Engine.
from src.risk.levels import RiskLevelConfig, build_risk_levels

# Importa configurazione e baseline deterministica.
from src.signals.baseline import (
    BaselineSignalConfig,
    build_baseline_signals,
)


def create_demo_dataframe() -> pd.DataFrame:
    """Crea un dataset con fasi rialziste e ribassiste."""

    # Genera centoventi timestamp consecutivi da quindici minuti.
    timestamps = pd.date_range(
        start="2026-08-01 08:00:00",
        periods=120,
        freq="15min",
        tz="UTC",
    )

    # Conterrà i prezzi di chiusura sintetici.
    close_prices: list[float] = []

    # Prima fase rialzista composta da quaranta candele.
    close_prices.extend(1.1000 + index * 0.0004 for index in range(40))

    # Seconda fase ribassista composta da quaranta candele.
    bearish_start = close_prices[-1]

    close_prices.extend(bearish_start - (index + 1) * 0.0005 for index in range(40))

    # Terza fase nuovamente rialzista.
    bullish_start = close_prices[-1]

    close_prices.extend(bullish_start + (index + 1) * 0.0006 for index in range(40))

    # Il primo Open precede leggermente il primo Close.
    # Gli Open successivi corrispondono al Close precedente.
    open_prices = [
        close_prices[0] - 0.0002,
        *close_prices[:-1],
    ]

    # Costruisce il dataset OHLCV completo.
    dataframe = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_prices,
            "high": [
                max(open_price, close_price) + 0.0007
                for open_price, close_price in zip(
                    open_prices,
                    close_prices,
                    strict=True,
                )
            ],
            "low": [
                min(open_price, close_price) - 0.0007
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

    # Valida e normalizza il dataset prima del Replay.
    return validate_ohlcv(dataframe)


def replay_processor(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """Elabora lo storico disponibile in un singolo step Replay."""

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

    # Genera feature e segnali usando solamente lo storico ricevuto.
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

    # Aggiunge Entry, Stop Loss e Take Profit teorici.
    return build_risk_levels(
        dataframe=signal_dataframe,
        config=risk_config,
    )


def print_summary(
    replay_log: pd.DataFrame,
    report_dictionary: dict[str, int | str | None],
) -> None:
    """Mostra un riepilogo della sessione Replay."""

    # Mostra le informazioni principali.
    print("Sessione Replay completata correttamente.")
    print("Modalità: PAPER ONLY")
    print(f"Candele sorgente: {report_dictionary['total_source_bars']}")
    print(f"Snapshot generati: {report_dictionary['generated_snapshots']}")
    print(f"Segnali LONG: {report_dictionary['long_signals']}")
    print(f"Segnali SHORT: {report_dictionary['short_signals']}")
    print(f"Segnali NO_TRADE: {report_dictionary['no_trade_signals']}")
    print(f"Ultima candela elaborata: {report_dictionary['last_processed_timestamp']}")

    # Mostra gli ultimi cinque snapshot generati.
    print("")
    print("Ultimi cinque snapshot:")

    display_columns = [
        "replay_step",
        "timestamp",
        "signal_available_at",
        "signal",
        "close",
        "entry_price",
        "stop_loss",
        "take_profit_1",
    ]

    print(replay_log[display_columns].tail(5).to_string(index=False))


def main() -> None:
    """Esegue la sessione Replay e salva i risultati."""

    # Definisce il registro sequenziale dei segnali.
    replay_log_path = Path("reports/sample_replay_log.csv")

    # Definisce il report riassuntivo JSON.
    replay_report_path = Path("reports/sample_replay_report.json")

    # Crea il dataset dimostrativo.
    dataframe = create_demo_dataframe()

    # Configura la sessione Replay.
    replay_config = ReplayConfig(
        minimum_history_bars=30,
        maximum_replay_bars=None,
        confirmed_candles_only=True,
    )

    # Esegue il Replay sequenziale.
    replay_log, replay_report = run_replay(
        dataframe=dataframe,
        processor=replay_processor,
        config=replay_config,
    )

    # Converte il report in un dizionario.
    report_dictionary = replay_report.to_dict()

    # Mostra il riepilogo nel terminale.
    print_summary(
        replay_log=replay_log,
        report_dictionary=report_dictionary,
    )

    # Crea la cartella dei report se non esiste.
    replay_log_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Salva lo storico sequenziale dei segnali.
    replay_log.to_csv(
        replay_log_path,
        index=False,
    )

    # Salva il report riassuntivo in formato JSON.
    replay_report_path.write_text(
        json.dumps(
            report_dictionary,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Mostra i percorsi dei file generati.
    print("")
    print(f"Replay log: {replay_log_path.resolve()}")
    print(f"Replay report: {replay_report_path.resolve()}")


if __name__ == "__main__":
    # Avvia lo script solamente quando eseguito direttamente.
    main()
