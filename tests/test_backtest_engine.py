"""Test automatici del motore di backtest."""

# Importa pandas per creare dataset deterministici.
import pandas as pd

# Importa pytest per verificare gli errori attesi.
import pytest

# Importa configurazione, errore e motore di backtest.
from src.backtest.engine import (
    BacktestConfig,
    BacktestError,
    run_backtest,
)


def create_backtest_dataframe(
    direction: str = "LONG",
) -> pd.DataFrame:
    """Crea un dataset minimo per testare un trade."""

    # Genera quattro timestamp M15 consecutivi.
    timestamps = pd.date_range(
        start="2026-08-13 10:00:00",
        periods=4,
        freq="15min",
        tz="UTC",
    )

    # Costruisce candele inizialmente neutrali.
    dataframe = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0, 100.0, 101.0, 101.0],
            "high": [101.0, 101.5, 103.0, 102.0],
            "low": [99.0, 99.5, 100.0, 100.0],
            "close": [100.0, 101.0, 102.0, 101.0],
            "signal": [
                direction,
                "NO_TRADE",
                "NO_TRADE",
                "NO_TRADE",
            ],
            "signal_status": [
                "CONFIRMED",
                "CONFIRMED",
                "CONFIRMED",
                "CONFIRMED",
            ],
            "signal_available_at": [
                timestamps[0] + pd.Timedelta(minutes=15),
                timestamps[1] + pd.Timedelta(minutes=15),
                timestamps[2] + pd.Timedelta(minutes=15),
                timestamps[3] + pd.Timedelta(minutes=15),
            ],
            "risk_distance": [2.0, float("nan"), float("nan"), float("nan")],
        }
    )

    # Restituisce il dataset configurato.
    return dataframe


def create_backtest_config() -> BacktestConfig:
    """Crea una configurazione semplice e deterministica."""

    # Disabilita slippage e commissioni per verificare i calcoli base.
    return BacktestConfig(
        slippage_percentage=0.0,
        round_trip_commission_percentage=0.0,
        maximum_holding_bars=3,
        take_profit_r=1.0,
        stop_first_when_ambiguous=True,
    )


def test_entry_occurs_on_next_candle_open() -> None:
    """Verifica che l'ingresso avvenga sulla candela successiva."""

    # Esegue il backtest.
    trades = run_backtest(
        dataframe=create_backtest_dataframe(),
        config=create_backtest_config(),
    )

    # Deve essere generato un solo trade.
    assert len(trades) == 1

    # L'ingresso deve usare l'Open della seconda candela.
    assert trades.loc[0, "entry_price"] == 100.0

    # L'ingresso deve avvenire alle 10:15.
    assert trades.loc[0, "entry_timestamp"] == ("2026-08-13T10:15:00+00:00")


def test_long_take_profit_is_detected() -> None:
    """Verifica la chiusura LONG al Take Profit."""

    # Crea il dataset LONG.
    dataframe = create_backtest_dataframe("LONG")

    # Il TP è pari a 102 e viene raggiunto dalla terza candela.
    trades = run_backtest(
        dataframe=dataframe,
        config=create_backtest_config(),
    )

    # Verifica il motivo dell'uscita.
    assert trades.loc[0, "exit_reason"] == "TAKE_PROFIT"

    # Verifica il prezzo di uscita.
    assert trades.loc[0, "exit_price"] == 102.0

    # Verifica il risultato lordo.
    assert trades.loc[0, "gross_return_percentage"] == pytest.approx(0.02)


def test_short_take_profit_is_detected() -> None:
    """Verifica la chiusura SHORT al Take Profit."""

    # Crea il dataset SHORT.
    dataframe = create_backtest_dataframe("SHORT")

    # Imposta una discesa sufficiente a raggiungere il TP SHORT a 98.
    dataframe.loc[1, ["high", "low", "close"]] = [
        100.5,
        99.0,
        99.5,
    ]
    dataframe.loc[2, ["open", "high", "low", "close"]] = [
        99.5,
        100.0,
        97.5,
        98.0,
    ]

    # Esegue il backtest.
    trades = run_backtest(
        dataframe=dataframe,
        config=create_backtest_config(),
    )

    # Verifica l'uscita al Take Profit.
    assert trades.loc[0, "exit_reason"] == "TAKE_PROFIT"

    # Verifica il prezzo di uscita.
    assert trades.loc[0, "exit_price"] == 98.0


def test_stop_loss_is_detected() -> None:
    """Verifica la chiusura LONG allo Stop Loss."""

    # Crea il dataset LONG.
    dataframe = create_backtest_dataframe("LONG")

    # Il livello Stop Loss è pari a 98.
    dataframe.loc[1, "low"] = 97.5
    dataframe.loc[1, "high"] = 101.0

    # Esegue il backtest.
    trades = run_backtest(
        dataframe=dataframe,
        config=create_backtest_config(),
    )

    # Verifica l'uscita allo Stop Loss.
    assert trades.loc[0, "exit_reason"] == "STOP_LOSS"

    # Verifica il prezzo di uscita.
    assert trades.loc[0, "exit_price"] == 98.0


def test_ambiguous_candle_uses_stop_loss() -> None:
    """Verifica la regola conservativa quando SL e TP sono toccati."""

    # Crea il dataset LONG.
    dataframe = create_backtest_dataframe("LONG")

    # La candela di ingresso tocca sia SL 98 sia TP 102.
    dataframe.loc[1, "low"] = 97.5
    dataframe.loc[1, "high"] = 102.5

    # Esegue il backtest.
    trades = run_backtest(
        dataframe=dataframe,
        config=create_backtest_config(),
    )

    # Deve prevalere lo Stop Loss.
    assert trades.loc[0, "exit_reason"] == "STOP_LOSS_AMBIGUOUS"

    # Verifica il prezzo selezionato.
    assert trades.loc[0, "exit_price"] == 98.0


def test_trade_expires_at_final_close() -> None:
    """Verifica la chiusura temporale se SL e TP non sono raggiunti."""

    # Crea il dataset LONG.
    dataframe = create_backtest_dataframe("LONG")

    # Mantiene tutte le candele fra SL 98 e TP 102.
    dataframe.loc[1:, "high"] = [101.0, 101.5, 101.5]
    dataframe.loc[1:, "low"] = [99.0, 99.5, 99.5]
    dataframe.loc[1:, "close"] = [100.5, 101.0, 101.5]

    # Esegue il backtest.
    trades = run_backtest(
        dataframe=dataframe,
        config=create_backtest_config(),
    )

    # Verifica la chiusura per scadenza.
    assert trades.loc[0, "exit_reason"] == "TIME_EXPIRY"

    # La chiusura deve usare il Close dell'ultima candela ammessa.
    assert trades.loc[0, "exit_price"] == 101.5


def test_costs_reduce_net_return() -> None:
    """Verifica che i costi riducano il rendimento netto."""

    # Crea una configurazione con costi e slippage.
    config = BacktestConfig(
        slippage_percentage=0.001,
        round_trip_commission_percentage=0.002,
        maximum_holding_bars=3,
        take_profit_r=1.0,
        stop_first_when_ambiguous=True,
    )

    # Esegue il backtest.
    trades = run_backtest(
        dataframe=create_backtest_dataframe(),
        config=config,
    )

    # Il rendimento netto deve essere inferiore al lordo.
    assert trades.loc[0, "net_return_percentage"] < trades.loc[0, "gross_return_percentage"]

    # Verifica il costo configurato.
    assert trades.loc[0, "total_cost_percentage"] == 0.002


def test_no_trade_produces_empty_trade_log() -> None:
    """Verifica che NO_TRADE non produca operazioni."""

    # Crea il dataset.
    dataframe = create_backtest_dataframe()

    # Rimuove il segnale operativo.
    dataframe["signal"] = "NO_TRADE"
    dataframe["risk_distance"] = float("nan")

    # Esegue il backtest.
    trades = run_backtest(
        dataframe=dataframe,
        config=create_backtest_config(),
    )

    # Il registro deve essere vuoto.
    assert trades.empty

    # Le colonne devono comunque essere presenti.
    assert "trade_id" in trades.columns
    assert "net_return_percentage" in trades.columns


def test_original_dataframe_is_not_modified() -> None:
    """Verifica che il backtest non modifichi il dataset originale."""

    # Crea il dataset originale.
    dataframe = create_backtest_dataframe()

    # Crea una copia completa.
    original_dataframe = dataframe.copy(deep=True)

    # Esegue il backtest.
    run_backtest(
        dataframe=dataframe,
        config=create_backtest_config(),
    )

    # Verifica che l'input sia rimasto invariato.
    pd.testing.assert_frame_equal(
        dataframe,
        original_dataframe,
    )


def test_invalid_configuration_is_rejected() -> None:
    """Verifica il rifiuto di una durata massima non valida."""

    # Crea una configurazione non valida.
    invalid_config = BacktestConfig(
        maximum_holding_bars=0,
    )

    # Verifica che venga prodotto l'errore previsto.
    with pytest.raises(
        BacktestError,
        match="durata massima",
    ):
        run_backtest(
            dataframe=create_backtest_dataframe(),
            config=invalid_config,
        )
