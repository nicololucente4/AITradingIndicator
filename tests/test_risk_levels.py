"""Test automatici del Risk Engine simulato."""

# Importa pandas per creare e confrontare i dataset.
import pandas as pd

# Importa pytest per verificare gli errori attesi.
import pytest

# Importa configurazione, errore e Risk Engine.
from src.risk.levels import (
    RiskLevelConfig,
    RiskLevelError,
    build_risk_levels,
)


def create_signal_dataframe(
    signal: str,
    close: float = 100.0,
    atr: float = 2.0,
) -> pd.DataFrame:
    """Crea una singola riga di segnale per i test."""

    # Definisce il timestamp di apertura della candela.
    timestamp = pd.Timestamp(
        "2026-08-13 10:00:00",
        tz="UTC",
    )

    # Costruisce un dataset minimo compatibile con il Risk Engine.
    return pd.DataFrame(
        {
            "timestamp": [timestamp],
            "close": [close],
            "atr": [atr],
            "signal": [signal],
            "signal_available_at": [timestamp + pd.Timedelta(minutes=15)],
            "signal_status": ["CONFIRMED"],
        }
    )


def create_risk_config() -> RiskLevelConfig:
    """Crea una configurazione deterministica per i test."""

    # Con Entry 100 e ATR 2, la distanza ATR sarà 3.
    return RiskLevelConfig(
        stop_atr_multiplier=1.5,
        minimum_stop_percentage=0.001,
        take_profit_1_r=1.0,
        take_profit_2_r=2.0,
        take_profit_3_r=3.0,
    )


def test_long_risk_levels_are_correct() -> None:
    """Verifica Entry, Stop Loss e Take Profit LONG."""

    # Genera i livelli per un segnale LONG.
    result = build_risk_levels(
        dataframe=create_signal_dataframe("LONG"),
        config=create_risk_config(),
    )

    # Recupera la prima riga.
    row = result.iloc[0]

    # Entry uguale al Close della candela confermata.
    assert row["entry_price"] == 100.0

    # Distanza di rischio: ATR 2 moltiplicato per 1,5.
    assert row["risk_distance"] == 3.0

    # Stop Loss LONG sotto l'Entry.
    assert row["stop_loss"] == 97.0

    # Take Profit LONG sopra l'Entry.
    assert row["take_profit_1"] == 103.0
    assert row["take_profit_2"] == 106.0
    assert row["take_profit_3"] == 109.0


def test_short_risk_levels_are_correct() -> None:
    """Verifica Entry, Stop Loss e Take Profit SHORT."""

    # Genera i livelli per un segnale SHORT.
    result = build_risk_levels(
        dataframe=create_signal_dataframe("SHORT"),
        config=create_risk_config(),
    )

    # Recupera la prima riga.
    row = result.iloc[0]

    # Stop Loss SHORT sopra l'Entry.
    assert row["stop_loss"] == 103.0

    # Take Profit SHORT sotto l'Entry.
    assert row["take_profit_1"] == 97.0
    assert row["take_profit_2"] == 94.0
    assert row["take_profit_3"] == 91.0


def test_no_trade_has_no_risk_levels() -> None:
    """Verifica che NO_TRADE non produca livelli operativi."""

    # Genera i livelli per un segnale non operativo.
    result = build_risk_levels(
        dataframe=create_signal_dataframe("NO_TRADE"),
        config=create_risk_config(),
    )

    # Definisce le colonne che devono restare vuote.
    level_columns = [
        "entry_price",
        "stop_loss",
        "risk_distance",
        "take_profit_1",
        "take_profit_2",
        "take_profit_3",
    ]

    # Tutti i livelli devono essere NaN.
    assert result.loc[0, level_columns].isna().all()


def test_unconfirmed_signal_has_no_risk_levels() -> None:
    """Verifica che un segnale non confermato non produca livelli."""

    # Crea un segnale LONG.
    dataframe = create_signal_dataframe("LONG")

    # Lo trasforma intenzionalmente in un segnale provvisorio.
    dataframe.loc[0, "signal_status"] = "PRE_SIGNAL"

    # Genera i livelli.
    result = build_risk_levels(
        dataframe=dataframe,
        config=create_risk_config(),
    )

    # Il Risk Engine non deve produrre un'Entry.
    assert pd.isna(result.loc[0, "entry_price"])

    # Il Risk Engine non deve produrre uno Stop Loss.
    assert pd.isna(result.loc[0, "stop_loss"])


def test_minimum_stop_percentage_is_applied() -> None:
    """Verifica l'applicazione della distanza minima percentuale."""

    # Crea una configurazione in cui la distanza minima prevale sull'ATR.
    config = RiskLevelConfig(
        stop_atr_multiplier=1.0,
        minimum_stop_percentage=0.02,
        take_profit_1_r=1.0,
        take_profit_2_r=2.0,
        take_profit_3_r=3.0,
    )

    # Con Entry 100 e ATR 0,5:
    # distanza ATR = 0,5;
    # distanza minima = 2;
    # deve quindi essere utilizzato il valore 2.
    result = build_risk_levels(
        dataframe=create_signal_dataframe(
            signal="LONG",
            close=100.0,
            atr=0.5,
        ),
        config=config,
    )

    # Verifica la distanza selezionata.
    assert result.loc[0, "risk_distance"] == 2.0

    # Verifica lo Stop Loss risultante.
    assert result.loc[0, "stop_loss"] == 98.0


def test_invalid_take_profit_order_is_rejected() -> None:
    """Verifica che i rapporti Take Profit siano crescenti."""

    # Crea una configurazione con TP2 inferiore a TP1.
    invalid_config = RiskLevelConfig(
        stop_atr_multiplier=1.5,
        minimum_stop_percentage=0.001,
        take_profit_1_r=2.0,
        take_profit_2_r=1.0,
        take_profit_3_r=3.0,
    )

    # Verifica che la configurazione venga rifiutata.
    with pytest.raises(
        RiskLevelError,
        match="strettamente crescenti",
    ):
        build_risk_levels(
            dataframe=create_signal_dataframe("LONG"),
            config=invalid_config,
        )


def test_unknown_signal_is_rejected() -> None:
    """Verifica che un segnale sconosciuto venga rifiutato."""

    # Crea un dataset con un valore non supportato.
    dataframe = create_signal_dataframe("BUY_NOW")

    # Verifica che il segnale venga rifiutato.
    with pytest.raises(
        RiskLevelError,
        match="non supportati",
    ):
        build_risk_levels(
            dataframe=dataframe,
            config=create_risk_config(),
        )


def test_original_dataframe_is_not_modified() -> None:
    """Verifica che il Risk Engine non modifichi l'input."""

    # Crea il dataset originale.
    dataframe = create_signal_dataframe("LONG")

    # Crea una copia completa.
    original_dataframe = dataframe.copy(deep=True)

    # Calcola i livelli di rischio.
    build_risk_levels(
        dataframe=dataframe,
        config=create_risk_config(),
    )

    # Verifica che il dataset originale sia rimasto invariato.
    pd.testing.assert_frame_equal(
        dataframe,
        original_dataframe,
    )


def test_future_rows_do_not_change_past_risk_levels() -> None:
    """Verifica che i livelli storici non dipendano da righe future."""

    # Crea tre segnali consecutivi.
    first_dataframe = create_signal_dataframe(
        signal="LONG",
        close=100.0,
        atr=2.0,
    )
    second_dataframe = create_signal_dataframe(
        signal="SHORT",
        close=101.0,
        atr=2.5,
    )
    third_dataframe = create_signal_dataframe(
        signal="LONG",
        close=102.0,
        atr=3.0,
    )

    # Sposta temporalmente il secondo e il terzo segnale.
    second_dataframe["timestamp"] += pd.Timedelta(minutes=15)
    second_dataframe["signal_available_at"] += pd.Timedelta(minutes=15)

    third_dataframe["timestamp"] += pd.Timedelta(minutes=30)
    third_dataframe["signal_available_at"] += pd.Timedelta(minutes=30)

    # Crea il dataset completo.
    complete_dataframe = pd.concat(
        [
            first_dataframe,
            second_dataframe,
            third_dataframe,
        ],
        ignore_index=True,
    )

    # Calcola i livelli usando tutte le righe.
    complete_result = build_risk_levels(
        dataframe=complete_dataframe,
        config=create_risk_config(),
    )

    # Calcola i livelli usando solamente le prime due righe.
    truncated_result = build_risk_levels(
        dataframe=complete_dataframe.iloc[:2].copy(),
        config=create_risk_config(),
    )

    # Confronta le righe storiche comuni.
    pd.testing.assert_frame_equal(
        complete_result.iloc[:2].reset_index(drop=True),
        truncated_result.reset_index(drop=True),
    )
