"""Test automatici della modalità Replay."""

# Importa pandas per creare dataset deterministici.
import pandas as pd

# Importa pytest per verificare gli errori attesi.
import pytest

# Importa configurazione e Replay Engine.
from src.backtest.replay import (
    ReplayConfig,
    ReplayError,
    run_replay,
)

# Importa la configurazione delle feature.
from src.features.technical import TechnicalFeatureConfig

# Importa configurazione e Risk Engine.
from src.risk.levels import RiskLevelConfig, build_risk_levels

# Importa configurazione e baseline.
from src.signals.baseline import (
    BaselineSignalConfig,
    build_baseline_signals,
)


def create_replay_dataframe(
    candle_count: int = 20,
) -> pd.DataFrame:
    """Crea un dataset rialzista per il Replay."""

    # Genera timestamp consecutivi M15.
    timestamps = pd.date_range(
        start="2026-08-13 08:00:00",
        periods=candle_count,
        freq="15min",
        tz="UTC",
    )

    # Genera prezzi progressivamente crescenti.
    close_prices = [100.0 + index for index in range(candle_count)]

    # Costruisce prezzi Open coerenti.
    open_prices = [
        close_prices[0] - 0.5,
        *close_prices[:-1],
    ]

    # Restituisce il dataset OHLCV.
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_prices,
            "high": [
                max(open_price, close_price) + 1.0
                for open_price, close_price in zip(
                    open_prices,
                    close_prices,
                    strict=True,
                )
            ],
            "low": [
                min(open_price, close_price) - 1.0
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


def replay_processor(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Genera segnali e livelli usando solamente lo snapshot ricevuto."""

    # Configura feature con finestre brevi.
    feature_config = TechnicalFeatureConfig(
        ema_fast_period=2,
        ema_slow_period=4,
        atr_period=3,
        volatility_period=3,
    )

    # Configura la baseline.
    signal_config = BaselineSignalConfig(
        timeframe_minutes=15,
        minimum_atr_percentage=0.0001,
        maximum_atr_percentage=0.10,
        minimum_absolute_return=0.0,
    )

    # Genera i segnali.
    signal_dataframe = build_baseline_signals(
        dataframe=dataframe,
        feature_config=feature_config,
        signal_config=signal_config,
    )

    # Configura i livelli teorici.
    risk_config = RiskLevelConfig(
        stop_atr_multiplier=1.5,
        minimum_stop_percentage=0.001,
        take_profit_1_r=1.0,
        take_profit_2_r=2.0,
        take_profit_3_r=3.0,
    )

    # Restituisce segnali e livelli.
    return build_risk_levels(
        dataframe=signal_dataframe,
        config=risk_config,
    )


def test_replay_processes_one_snapshot_per_new_bar() -> None:
    """Verifica il numero di snapshot generati."""

    # Esegue il Replay su venti candele partendo dalla quinta.
    replay_log, report = run_replay(
        dataframe=create_replay_dataframe(20),
        processor=replay_processor,
        config=ReplayConfig(
            minimum_history_bars=5,
        ),
    )

    # Da 5 a 20 candele incluse vengono generati 16 snapshot.
    assert len(replay_log) == 16

    # Verifica il report.
    assert report.generated_snapshots == 16
    assert report.total_source_bars == 20


def test_replay_never_passes_future_rows() -> None:
    """Verifica che il processore riceva solamente i dati disponibili."""

    # Registra la dimensione di ogni snapshot ricevuto.
    received_sizes: list[int] = []

    def inspected_processor(
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """Registra la dimensione e avvia il processore reale."""

        # Salva il numero di righe ricevute.
        received_sizes.append(len(dataframe))

        # Restituisce il risultato normale.
        return replay_processor(dataframe)

    # Esegue il Replay.
    run_replay(
        dataframe=create_replay_dataframe(10),
        processor=inspected_processor,
        config=ReplayConfig(
            minimum_history_bars=5,
        ),
    )

    # Il processore deve ricevere dataset progressivi.
    assert received_sizes == [5, 6, 7, 8, 9, 10]


def test_replay_timestamps_are_progressive() -> None:
    """Verifica che ogni snapshot rappresenti una nuova candela."""

    # Esegue il Replay.
    replay_log, _ = run_replay(
        dataframe=create_replay_dataframe(12),
        processor=replay_processor,
        config=ReplayConfig(
            minimum_history_bars=5,
        ),
    )

    # I timestamp devono essere ordinati.
    assert replay_log["timestamp"].is_monotonic_increasing

    # I timestamp non devono essere duplicati.
    assert not replay_log["timestamp"].duplicated().any()


def test_replay_signals_are_confirmed() -> None:
    """Verifica che il Replay produca segnali confermati."""

    # Esegue il Replay.
    replay_log, _ = run_replay(
        dataframe=create_replay_dataframe(12),
        processor=replay_processor,
        config=ReplayConfig(
            minimum_history_bars=5,
        ),
    )

    # Tutti gli snapshot devono essere confermati.
    assert (replay_log["signal_status"] == "CONFIRMED").all()


def test_insufficient_history_is_rejected() -> None:
    """Verifica il rifiuto di uno storico insufficiente."""

    # Il dataset contiene quattro candele, ma ne sono richieste cinque.
    with pytest.raises(
        ReplayError,
        match="meno candele",
    ):
        run_replay(
            dataframe=create_replay_dataframe(4),
            processor=replay_processor,
            config=ReplayConfig(
                minimum_history_bars=5,
            ),
        )


def test_invalid_configuration_is_rejected() -> None:
    """Verifica il rifiuto di una configurazione non valida."""

    # Zero candele minime non è una configurazione valida.
    with pytest.raises(
        ReplayError,
        match="maggiore di zero",
    ):
        run_replay(
            dataframe=create_replay_dataframe(10),
            processor=replay_processor,
            config=ReplayConfig(
                minimum_history_bars=0,
            ),
        )
