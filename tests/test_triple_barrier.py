"""Test automatici del target Triple Barrier."""

# Importa pandas per creare dataset deterministici.
import pandas as pd

# Importa pytest per verificare gli errori attesi.
import pytest

# Importa configurazione, errore e target builder.
from src.labels.triple_barrier import (
    TripleBarrierConfig,
    TripleBarrierError,
    build_triple_barrier_labels,
)


def create_label_dataframe(
    candle_count: int = 8,
) -> pd.DataFrame:
    """Crea un dataset OHLCV con ATR già disponibile."""

    # Genera timestamp consecutivi M15.
    timestamps = pd.date_range(
        start="2026-08-13 08:00:00",
        periods=candle_count,
        freq="15min",
        tz="UTC",
    )

    # Restituisce un dataset inizialmente laterale.
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0] * candle_count,
            "high": [100.5] * candle_count,
            "low": [99.5] * candle_count,
            "close": [100.0] * candle_count,
            "volume": [100] * candle_count,
            "atr": [1.0] * candle_count,
        }
    )


def create_label_config() -> TripleBarrierConfig:
    """Crea una configurazione ridotta per i test."""

    # Le barriere si trovano a un ATR dal Close.
    return TripleBarrierConfig(
        maximum_holding_bars=3,
        upper_atr_multiplier=1.0,
        lower_atr_multiplier=1.0,
        ambiguous_label="NO_TRADE",
        timeout_label="NO_TRADE",
    )


def test_upper_barrier_generates_long_label() -> None:
    """Verifica la generazione del target LONG."""

    # Crea il dataset laterale.
    dataframe = create_label_dataframe()

    # La seconda candela futura raggiunge la barriera superiore 101.
    dataframe.loc[2, "high"] = 101.5

    # Genera i target.
    result = build_triple_barrier_labels(
        dataframe=dataframe,
        config=create_label_config(),
    )

    # La prima riga deve essere etichettata LONG.
    assert result.loc[0, "target"] == "LONG"

    # L'evento è avvenuto dopo due candele.
    assert result.loc[0, "target_bars_to_event"] == 2


def test_lower_barrier_generates_short_label() -> None:
    """Verifica la generazione del target SHORT."""

    # Crea il dataset laterale.
    dataframe = create_label_dataframe()

    # La prima candela futura raggiunge la barriera inferiore 99.
    dataframe.loc[1, "low"] = 98.5

    # Genera i target.
    result = build_triple_barrier_labels(
        dataframe=dataframe,
        config=create_label_config(),
    )

    # La prima riga deve essere etichettata SHORT.
    assert result.loc[0, "target"] == "SHORT"

    # L'evento è avvenuto dopo una candela.
    assert result.loc[0, "target_bars_to_event"] == 1


def test_timeout_generates_no_trade_label() -> None:
    """Verifica NO_TRADE quando nessuna barriera viene raggiunta."""

    # Crea un dataset che rimane tra le due barriere.
    dataframe = create_label_dataframe()

    # Genera i target.
    result = build_triple_barrier_labels(
        dataframe=dataframe,
        config=create_label_config(),
    )

    # Nessuna barriera viene raggiunta.
    assert result.loc[0, "target"] == "NO_TRADE"

    # Non esiste una candela specifica dell'evento.
    assert pd.isna(result.loc[0, "target_bars_to_event"])


def test_ambiguous_candle_generates_no_trade() -> None:
    """Verifica la gestione conservativa di una candela ambigua."""

    # Crea il dataset laterale.
    dataframe = create_label_dataframe()

    # La prima candela futura raggiunge entrambe le barriere.
    dataframe.loc[1, "high"] = 101.5
    dataframe.loc[1, "low"] = 98.5

    # Genera i target.
    result = build_triple_barrier_labels(
        dataframe=dataframe,
        config=create_label_config(),
    )

    # L'ordine intrabar non è noto, quindi il target è NO_TRADE.
    assert result.loc[0, "target"] == "NO_TRADE"

    # L'ambiguità è stata rilevata sulla prima candela futura.
    assert result.loc[0, "target_bars_to_event"] == 1


def test_final_rows_without_full_horizon_have_no_target() -> None:
    """Verifica che le ultime righe senza futuro completo siano escluse."""

    # Crea otto candele con orizzonte futuro pari a tre.
    dataframe = create_label_dataframe(candle_count=8)

    # Genera i target.
    result = build_triple_barrier_labels(
        dataframe=dataframe,
        config=create_label_config(),
    )

    # Le ultime tre righe non dispongono di tre candele future.
    assert result.loc[5:7, "target"].isna().all()

    # Le ultime tre righe non devono essere disponibili per il training.
    assert not result.loc[5:7, "target_available"].any()


def test_missing_atr_produces_unavailable_target() -> None:
    """Verifica che un ATR mancante escluda la riga."""

    # Crea il dataset.
    dataframe = create_label_dataframe()

    # Rimuove l'ATR della prima riga.
    dataframe.loc[0, "atr"] = float("nan")

    # Genera i target.
    result = build_triple_barrier_labels(
        dataframe=dataframe,
        config=create_label_config(),
    )

    # La prima riga non può essere usata per il training.
    assert pd.isna(result.loc[0, "target"])
    assert not bool(result.loc[0, "target_available"])


def test_original_dataframe_is_not_modified() -> None:
    """Verifica che il target builder non modifichi l'input."""

    # Crea il dataset originale.
    dataframe = create_label_dataframe()

    # Crea una copia completa.
    original_dataframe = dataframe.copy(deep=True)

    # Genera i target.
    build_triple_barrier_labels(
        dataframe=dataframe,
        config=create_label_config(),
    )

    # Verifica che il dataset originale sia rimasto invariato.
    pd.testing.assert_frame_equal(
        dataframe,
        original_dataframe,
    )


def test_invalid_holding_period_is_rejected() -> None:
    """Verifica il rifiuto di un orizzonte futuro non valido."""

    # Crea una configurazione con zero candele future.
    invalid_config = TripleBarrierConfig(
        maximum_holding_bars=0,
    )

    # Verifica che venga prodotto l'errore previsto.
    with pytest.raises(
        TripleBarrierError,
        match="maggiore di zero",
    ):
        build_triple_barrier_labels(
            dataframe=create_label_dataframe(),
            config=invalid_config,
        )


def test_target_is_explicitly_marked_as_future_based() -> None:
    """Verifica che il target dichiari l'uso di dati futuri."""

    # Genera i target.
    result = build_triple_barrier_labels(
        dataframe=create_label_dataframe(),
        config=create_label_config(),
    )

    # Tutte le righe devono dichiarare che il target usa il futuro.
    assert result["target_uses_future_data"].all()
