"""Test automatici delle feature tecniche."""

# Importa pandas per creare e confrontare i dataset.
import pandas as pd

# Importa pytest per verificare gli errori attesi.
import pytest

# Importa configurazione, errore e pipeline delle feature.
from src.features.technical import (
    TechnicalFeatureConfig,
    TechnicalFeatureError,
    build_technical_features,
)


def create_feature_dataframe(
    candle_count: int = 12,
) -> pd.DataFrame:
    """Crea un dataset OHLCV deterministico."""

    # Genera timestamp consecutivi da 15 minuti.
    timestamps = pd.date_range(
        start="2026-08-13 08:00:00",
        periods=candle_count,
        freq="15min",
        tz="UTC",
    )

    # Genera prezzi di apertura progressivi.
    open_prices = [100.0 + index for index in range(candle_count)]

    # Costruisce un dataset semplice e riproducibile.
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_prices,
            "high": [price + 2.0 for price in open_prices],
            "low": [price - 1.0 for price in open_prices],
            "close": [price + 1.0 for price in open_prices],
            "volume": [100 + (index * 10) for index in range(candle_count)],
        }
    )


def create_test_config() -> TechnicalFeatureConfig:
    """Crea una configurazione ridotta per i test."""

    # Utilizza periodi brevi per lavorare sui piccoli dataset di test.
    return TechnicalFeatureConfig(
        ema_fast_period=3,
        ema_slow_period=5,
        atr_period=3,
        volatility_period=3,
    )


def test_feature_columns_are_created() -> None:
    """Verifica che tutte le feature attese vengano create."""

    # Crea il dataset e calcola le feature.
    result = build_technical_features(
        dataframe=create_feature_dataframe(),
        config=create_test_config(),
    )

    # Definisce le colonne tecniche attese.
    expected_feature_columns = {
        "return_1",
        "ema_fast",
        "ema_slow",
        "ema_distance_pct",
        "true_range",
        "atr",
        "atr_pct",
        "volatility",
    }

    # Verifica che tutte le feature siano presenti.
    assert expected_feature_columns.issubset(set(result.columns))


def test_original_dataframe_is_not_modified() -> None:
    """Verifica che la pipeline non modifichi il dataset originale."""

    # Crea il dataset originale.
    dataframe = create_feature_dataframe()

    # Crea una copia completa per il confronto.
    original_dataframe = dataframe.copy(deep=True)

    # Calcola le feature.
    build_technical_features(
        dataframe=dataframe,
        config=create_test_config(),
    )

    # Verifica che il dataset originale sia rimasto invariato.
    pd.testing.assert_frame_equal(
        dataframe,
        original_dataframe,
    )


def test_initial_warmup_values_are_missing() -> None:
    """Verifica la presenza dei valori NaN durante il warm-up."""

    # Calcola le feature.
    result = build_technical_features(
        dataframe=create_feature_dataframe(),
        config=create_test_config(),
    )

    # La EMA veloce a periodo 3 non è disponibile nelle prime due righe.
    assert result.loc[0:1, "ema_fast"].isna().all()

    # La EMA lenta a periodo 5 non è disponibile nelle prime quattro righe.
    assert result.loc[0:3, "ema_slow"].isna().all()

    # L'ATR a periodo 3 non è disponibile nelle prime due righe.
    assert result.loc[0:1, "atr"].isna().all()

    # La volatilità richiede tre rendimenti validi.
    assert result.loc[0:2, "volatility"].isna().all()


def test_true_range_and_atr_are_correct() -> None:
    """Verifica i calcoli di True Range e ATR."""

    # Calcola le feature sul dataset deterministico.
    result = build_technical_features(
        dataframe=create_feature_dataframe(),
        config=create_test_config(),
    )

    # Ogni candela ha High-Low uguale a 3.
    assert result.loc[0, "true_range"] == 3.0

    # Anche le candele successive hanno True Range uguale a 3.
    assert result.loc[1, "true_range"] == 3.0

    # L'ATR delle prime tre candele valide deve essere uguale a 3.
    assert result.loc[2, "atr"] == 3.0


def test_invalid_ema_periods_are_rejected() -> None:
    """Verifica che la EMA veloce debba essere inferiore alla lenta."""

    # Configura due periodi EMA uguali.
    invalid_config = TechnicalFeatureConfig(
        ema_fast_period=5,
        ema_slow_period=5,
        atr_period=3,
        volatility_period=3,
    )

    # Verifica che la configurazione venga rifiutata.
    with pytest.raises(
        TechnicalFeatureError,
        match="EMA veloce",
    ):
        build_technical_features(
            dataframe=create_feature_dataframe(),
            config=invalid_config,
        )


def test_future_rows_do_not_change_past_features() -> None:
    """Verifica che le feature storiche non usino dati futuri."""

    # Crea il dataset completo.
    complete_dataframe = create_feature_dataframe(candle_count=12)

    # Calcola le feature usando tutte le dodici candele.
    complete_result = build_technical_features(
        dataframe=complete_dataframe,
        config=create_test_config(),
    )

    # Crea una versione troncata alle prime otto candele.
    truncated_dataframe = complete_dataframe.iloc[:8].copy()

    # Calcola nuovamente le feature senza le quattro candele future.
    truncated_result = build_technical_features(
        dataframe=truncated_dataframe,
        config=create_test_config(),
    )

    # Seleziona nel risultato completo solamente le righe disponibili
    # anche nel dataset troncato.
    complete_past_features = complete_result.iloc[:8].reset_index(drop=True)

    # Normalizza anche l'indice del risultato troncato.
    truncated_past_features = truncated_result.reset_index(drop=True)

    # Verifica che tutte le feature storiche siano identiche.
    pd.testing.assert_frame_equal(
        complete_past_features,
        truncated_past_features,
    )
