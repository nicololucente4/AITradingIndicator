"""Test automatici dell'aggregazione multi-timeframe."""

# Importa pandas per creare i dataset di test.
import pandas as pd

# Importa pytest per verificare gli errori attesi.
import pytest

# Importa la funzione di aggregazione e il relativo errore.
from src.data.timeframe import (
    TimeframeAggregationError,
    resample_ohlcv,
)


def create_m15_dataframe(candle_count: int = 8) -> pd.DataFrame:
    """Crea un dataset deterministico di candele M15."""

    # Genera timestamp consecutivi ogni 15 minuti.
    timestamps = pd.date_range(
        start="2026-08-13 10:00:00",
        periods=candle_count,
        freq="15min",
        tz="UTC",
    )

    # Genera valori progressivi per rendere verificabile l'aggregazione.
    open_prices = [1.1000 + (index * 0.0010) for index in range(candle_count)]

    # Costruisce il dataset OHLCV.
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_prices,
            "high": [price + 0.0020 for price in open_prices],
            "low": [price - 0.0010 for price in open_prices],
            "close": [price + 0.0010 for price in open_prices],
            "volume": [100 + (index * 10) for index in range(candle_count)],
        }
    )


def test_m15_is_aggregated_to_h1() -> None:
    """Verifica l'aggregazione di otto candele M15 in due H1."""

    # Crea otto candele M15 consecutive.
    dataframe = create_m15_dataframe(candle_count=8)

    # Aggrega il dataset da M15 a H1.
    result = resample_ohlcv(
        dataframe=dataframe,
        source_minutes=15,
        target_minutes=60,
    )

    # Otto candele M15 devono produrre due candele H1.
    assert len(result) == 2

    # Verifica il timestamp della prima H1.
    assert result.loc[0, "timestamp"] == pd.Timestamp(
        "2026-08-13 10:00:00",
        tz="UTC",
    )

    # L'Open H1 deve coincidere con l'Open della prima M15.
    assert result.loc[0, "open"] == dataframe.loc[0, "open"]

    # Il Close H1 deve coincidere con il Close dell'ultima M15 del blocco.
    assert result.loc[0, "close"] == dataframe.loc[3, "close"]

    # L'High H1 deve essere il massimo del primo gruppo.
    assert result.loc[0, "high"] == dataframe.loc[0:3, "high"].max()

    # Il Low H1 deve essere il minimo del primo gruppo.
    assert result.loc[0, "low"] == dataframe.loc[0:3, "low"].min()

    # Il volume H1 deve essere la somma dei quattro volumi M15.
    assert result.loc[0, "volume"] == dataframe.loc[0:3, "volume"].sum()


def test_incomplete_final_bucket_is_removed() -> None:
    """Verifica l'esclusione dell'ultima candela H1 incompleta."""

    # Sei candele M15 formano una H1 completa e una incompleta.
    dataframe = create_m15_dataframe(candle_count=6)

    # Aggrega il dataset.
    result = resample_ohlcv(
        dataframe=dataframe,
        source_minutes=15,
        target_minutes=60,
    )

    # Deve essere restituita solamente la prima H1 completa.
    assert len(result) == 1

    # La H1 incompleta delle 11:00 non deve essere presente.
    assert result.loc[0, "timestamp"] == pd.Timestamp(
        "2026-08-13 10:00:00",
        tz="UTC",
    )


def test_missing_source_candle_removes_bucket() -> None:
    """Verifica che un blocco con una candela mancante venga escluso."""

    # Crea otto candele M15, equivalenti a due H1.
    dataframe = create_m15_dataframe(candle_count=8)

    # Elimina la candela delle 10:30 dal primo blocco.
    dataframe = dataframe.drop(index=2).reset_index(drop=True)

    # Aggrega il dataset.
    result = resample_ohlcv(
        dataframe=dataframe,
        source_minutes=15,
        target_minutes=60,
    )

    # Il primo blocco è incompleto, quindi resta solamente il secondo.
    assert len(result) == 1

    # Verifica che la candela rimasta sia quella delle 11:00.
    assert result.loc[0, "timestamp"] == pd.Timestamp(
        "2026-08-13 11:00:00",
        tz="UTC",
    )


def test_dataset_without_complete_bucket_is_rejected() -> None:
    """Verifica il rifiuto di un dataset privo di blocchi completi."""

    # Tre candele M15 non sono sufficienti per generare una H1.
    dataframe = create_m15_dataframe(candle_count=3)

    # Verifica che venga generato un errore chiaro.
    with pytest.raises(
        TimeframeAggregationError,
        match="blocchi temporali completi",
    ):
        resample_ohlcv(
            dataframe=dataframe,
            source_minutes=15,
            target_minutes=60,
        )


def test_invalid_timeframe_ratio_is_rejected() -> None:
    """Verifica il rifiuto di timeframe non multipli."""

    # Crea un dataset valido.
    dataframe = create_m15_dataframe(candle_count=8)

    # Cinquanta minuti non sono un multiplo esatto di quindici.
    with pytest.raises(
        TimeframeAggregationError,
        match="multiplo esatto",
    ):
        resample_ohlcv(
            dataframe=dataframe,
            source_minutes=15,
            target_minutes=50,
        )


def test_target_timeframe_must_be_greater() -> None:
    """Verifica che il timeframe destinazione sia superiore."""

    # Crea un dataset valido.
    dataframe = create_m15_dataframe(candle_count=8)

    # Il timeframe destinazione non può essere uguale al sorgente.
    with pytest.raises(
        TimeframeAggregationError,
        match="deve essere maggiore",
    ):
        resample_ohlcv(
            dataframe=dataframe,
            source_minutes=15,
            target_minutes=15,
        )


def test_original_dataframe_is_not_modified() -> None:
    """Verifica che l'aggregazione non modifichi il dataset sorgente."""

    # Crea il dataset originale.
    dataframe = create_m15_dataframe(candle_count=8)

    # Crea una copia completa da usare per il confronto.
    original_dataframe = dataframe.copy(deep=True)

    # Esegue l'aggregazione.
    resample_ohlcv(
        dataframe=dataframe,
        source_minutes=15,
        target_minutes=60,
    )

    # Verifica che il dataset originale sia rimasto invariato.
    pd.testing.assert_frame_equal(
        dataframe,
        original_dataframe,
    )
