"""Test automatici della baseline deterministica."""

# Importa pandas per creare e confrontare i dataset.
import pandas as pd

# Importa pytest per verificare gli errori attesi.
import pytest

# Importa la configurazione ridotta delle feature.
from src.features.technical import TechnicalFeatureConfig

# Importa configurazione, errore e generatore della baseline.
from src.signals.baseline import (
    BaselineSignalConfig,
    BaselineSignalError,
    build_baseline_signals,
)


def create_trending_dataframe(
    direction: str,
    candle_count: int = 12,
) -> pd.DataFrame:
    """Crea un dataset con trend rialzista oppure ribassista."""

    # Genera timestamp consecutivi M15.
    timestamps = pd.date_range(
        start="2026-08-13 08:00:00",
        periods=candle_count,
        freq="15min",
        tz="UTC",
    )

    # Genera prezzi crescenti per il trend rialzista.
    if direction == "up":
        open_prices = [100.0 + index for index in range(candle_count)]

    # Genera prezzi decrescenti per il trend ribassista.
    elif direction == "down":
        open_prices = [120.0 - index for index in range(candle_count)]

    # Rifiuta direzioni non riconosciute nei test.
    else:
        raise ValueError("La direzione deve essere 'up' oppure 'down'.")

    # Costruisce candele OHLCV coerenti con la direzione.
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_prices,
            "high": [price + 2.0 for price in open_prices],
            "low": [price - 2.0 for price in open_prices],
            "close": [price + 0.5 if direction == "up" else price - 0.5 for price in open_prices],
            "volume": [100 + index for index in range(candle_count)],
        }
    )


def create_feature_config() -> TechnicalFeatureConfig:
    """Crea una configurazione breve per i test."""

    # Usa finestre ridotte per ottenere segnali in pochi dati.
    return TechnicalFeatureConfig(
        ema_fast_period=2,
        ema_slow_period=4,
        atr_period=3,
        volatility_period=3,
    )


def create_signal_config() -> BaselineSignalConfig:
    """Crea la configurazione baseline usata nei test."""

    # Utilizza soglie di volatilità compatibili con i dati sintetici.
    return BaselineSignalConfig(
        timeframe_minutes=15,
        minimum_atr_percentage=0.0001,
        maximum_atr_percentage=0.10,
        minimum_absolute_return=0.0,
    )


def test_bullish_trend_generates_long_signal() -> None:
    """Verifica la generazione di segnali LONG."""

    # Genera segnali su un dataset rialzista.
    result = build_baseline_signals(
        dataframe=create_trending_dataframe("up"),
        feature_config=create_feature_config(),
        signal_config=create_signal_config(),
    )

    # L'ultima candela deve produrre un segnale LONG.
    assert result.iloc[-1]["signal"] == "LONG"

    # Verifica che il segnale sia confermato.
    assert result.iloc[-1]["signal_status"] == "CONFIRMED"

    # Verifica la sorgente del segnale.
    assert result.iloc[-1]["signal_source"] == "BASELINE_RULES"


def test_bearish_trend_generates_short_signal() -> None:
    """Verifica la generazione di segnali SHORT."""

    # Genera segnali su un dataset ribassista.
    result = build_baseline_signals(
        dataframe=create_trending_dataframe("down"),
        feature_config=create_feature_config(),
        signal_config=create_signal_config(),
    )

    # L'ultima candela deve produrre un segnale SHORT.
    assert result.iloc[-1]["signal"] == "SHORT"


def test_warmup_rows_generate_no_trade() -> None:
    """Verifica che il warm-up non produca segnali direzionali."""

    # Genera i segnali.
    result = build_baseline_signals(
        dataframe=create_trending_dataframe("up"),
        feature_config=create_feature_config(),
        signal_config=create_signal_config(),
    )

    # Le prime tre righe non dispongono ancora della EMA lenta.
    assert (result.loc[0:2, "signal"] == "NO_TRADE").all()

    # Verifica la motivazione del mancato segnale.
    assert "warm-up" in result.loc[0, "signal_reason"]


def test_signal_is_available_only_at_candle_close() -> None:
    """Verifica che il segnale sia disponibile alla chiusura M15."""

    # Genera i segnali.
    result = build_baseline_signals(
        dataframe=create_trending_dataframe("up"),
        feature_config=create_feature_config(),
        signal_config=create_signal_config(),
    )

    # Recupera la prima candela.
    first_row = result.iloc[0]

    # Il segnale deve essere disponibile quindici minuti dopo l'apertura.
    assert first_row["signal_available_at"] == (first_row["timestamp"] + pd.Timedelta(minutes=15))


def test_invalid_volatility_range_is_rejected() -> None:
    """Verifica il rifiuto di soglie ATR incoerenti."""

    # Crea una configurazione con soglia massima inferiore alla minima.
    invalid_config = BaselineSignalConfig(
        timeframe_minutes=15,
        minimum_atr_percentage=0.05,
        maximum_atr_percentage=0.01,
        minimum_absolute_return=0.0,
    )

    # Verifica che la configurazione venga rifiutata.
    with pytest.raises(
        BaselineSignalError,
        match="ATR massima",
    ):
        build_baseline_signals(
            dataframe=create_trending_dataframe("up"),
            feature_config=create_feature_config(),
            signal_config=invalid_config,
        )


def test_future_rows_do_not_change_past_signals() -> None:
    """Verifica che i segnali storici non dipendano da dati futuri."""

    # Crea il dataset completo.
    complete_dataframe = create_trending_dataframe(
        direction="up",
        candle_count=12,
    )

    # Calcola i segnali usando tutte le candele.
    complete_result = build_baseline_signals(
        dataframe=complete_dataframe,
        feature_config=create_feature_config(),
        signal_config=create_signal_config(),
    )

    # Mantiene solamente le prime otto candele.
    truncated_dataframe = complete_dataframe.iloc[:8].copy()

    # Calcola i segnali senza le quattro candele future.
    truncated_result = build_baseline_signals(
        dataframe=truncated_dataframe,
        feature_config=create_feature_config(),
        signal_config=create_signal_config(),
    )

    # Confronta le righe storiche comuni ai due risultati.
    pd.testing.assert_frame_equal(
        complete_result.iloc[:8].reset_index(drop=True),
        truncated_result.reset_index(drop=True),
    )


def test_original_dataframe_is_not_modified() -> None:
    """Verifica che la baseline non modifichi il dataset originale."""

    # Crea il dataset originale.
    dataframe = create_trending_dataframe("up")

    # Crea una copia completa.
    original_dataframe = dataframe.copy(deep=True)

    # Genera i segnali.
    build_baseline_signals(
        dataframe=dataframe,
        feature_config=create_feature_config(),
        signal_config=create_signal_config(),
    )

    # Verifica che il dataset sorgente sia rimasto invariato.
    pd.testing.assert_frame_equal(
        dataframe,
        original_dataframe,
    )
