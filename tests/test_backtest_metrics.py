"""Test automatici delle metriche di backtest."""

# Importa math per verificare il Profit Factor infinito.
import math

# Importa pandas per creare trade log deterministici.
import pandas as pd

# Importa pytest per verificare gli errori attesi.
import pytest

# Importa errore e funzione di calcolo delle metriche.
from src.backtest.metrics import (
    BacktestMetricsError,
    calculate_backtest_metrics,
)


def create_trade_log() -> pd.DataFrame:
    """Crea un trade log deterministico con vincite e perdite."""

    # Restituisce quattro trade con due vincite e due perdite.
    return pd.DataFrame(
        {
            "trade_id": [1, 2, 3, 4],
            "net_return_percentage": [
                0.02,
                -0.01,
                0.03,
                -0.02,
            ],
            "total_cost_percentage": [
                0.001,
                0.001,
                0.001,
                0.001,
            ],
            "result_r": [
                1.0,
                -0.5,
                1.5,
                -1.0,
            ],
        }
    )


def test_basic_metrics_are_correct() -> None:
    """Verifica conteggi, win rate ed expectancy."""

    # Calcola le metriche.
    metrics = calculate_backtest_metrics(create_trade_log())

    # Verifica il numero totale di trade.
    assert metrics.total_trades == 4

    # Verifica vincite e perdite.
    assert metrics.winning_trades == 2
    assert metrics.losing_trades == 2
    assert metrics.breakeven_trades == 0

    # Due trade positivi su quattro equivalgono al 50%.
    assert metrics.win_rate_percentage == 50.0

    # L'expectancy è la media di 1, -0,5, 1,5 e -1.
    assert metrics.expectancy_r == 0.25

    # Verifica il risultato medio delle vincite.
    assert metrics.average_win_r == 1.25

    # Verifica la perdita media assoluta.
    assert metrics.average_loss_r == 0.75


def test_profit_factor_is_correct() -> None:
    """Verifica il calcolo del Profit Factor."""

    # Calcola le metriche.
    metrics = calculate_backtest_metrics(create_trade_log())

    # Profitto lordo R = 2,5.
    # Perdita lorda R = 1,5.
    assert metrics.profit_factor == pytest.approx(1.666667)


def test_compounded_return_is_correct() -> None:
    """Verifica il rendimento composto."""

    # Calcola le metriche.
    metrics = calculate_backtest_metrics(create_trade_log())

    # Calcola manualmente il risultato composto.
    expected_return = (1.02 * 0.99 * 1.03 * 0.98 - 1.0) * 100.0

    # Confronta il risultato arrotondato.
    assert metrics.cumulative_return_percentage == pytest.approx(round(expected_return, 6))


def test_maximum_drawdown_is_calculated() -> None:
    """Verifica che il drawdown sia positivo e coerente."""

    # Calcola le metriche.
    metrics = calculate_backtest_metrics(create_trade_log())

    # Il dataset contiene perdite e deve produrre un drawdown.
    assert metrics.maximum_drawdown_percentage > 0.0

    # Il drawdown non può superare il 100% in questo test.
    assert metrics.maximum_drawdown_percentage < 100.0


def test_consecutive_streaks_are_calculated() -> None:
    """Verifica le serie consecutive di vincite e perdite."""

    # Crea una sequenza con due vincite e tre perdite consecutive.
    trades = pd.DataFrame(
        {
            "trade_id": [1, 2, 3, 4, 5],
            "net_return_percentage": [
                0.01,
                0.02,
                -0.01,
                -0.02,
                -0.01,
            ],
            "total_cost_percentage": [
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
            ],
            "result_r": [
                1.0,
                1.0,
                -1.0,
                -1.0,
                -1.0,
            ],
        }
    )

    # Calcola le metriche.
    metrics = calculate_backtest_metrics(trades)

    # Verifica le serie massime.
    assert metrics.maximum_consecutive_wins == 2
    assert metrics.maximum_consecutive_losses == 3


def test_empty_trade_log_returns_zero_metrics() -> None:
    """Verifica la gestione di un trade log vuoto."""

    # Crea un DataFrame vuoto con lo schema richiesto.
    trades = pd.DataFrame(
        columns=[
            "trade_id",
            "net_return_percentage",
            "total_cost_percentage",
            "result_r",
        ]
    )

    # Calcola le metriche.
    metrics = calculate_backtest_metrics(trades)

    # Tutte le metriche principali devono essere nulle.
    assert metrics.total_trades == 0
    assert metrics.win_rate_percentage == 0.0
    assert metrics.expectancy_r == 0.0
    assert metrics.maximum_drawdown_percentage == 0.0

    # Il Profit Factor non è definito.
    assert metrics.profit_factor is None


def test_all_winning_trades_have_infinite_profit_factor() -> None:
    """Verifica il Profit Factor senza trade negativi."""

    # Crea un trade log composto solamente da vincite.
    trades = pd.DataFrame(
        {
            "trade_id": [1, 2],
            "net_return_percentage": [0.01, 0.02],
            "total_cost_percentage": [0.0, 0.0],
            "result_r": [1.0, 2.0],
        }
    )

    # Calcola le metriche.
    metrics = calculate_backtest_metrics(trades)

    # Senza perdite, il Profit Factor è infinito.
    assert metrics.profit_factor is not None
    assert math.isinf(metrics.profit_factor)


def test_missing_columns_are_rejected() -> None:
    """Verifica il rifiuto di un trade log incompleto."""

    # Crea un DataFrame privo delle colonne richieste.
    trades = pd.DataFrame(
        {
            "trade_id": [1],
        }
    )

    # Verifica che venga generato un errore leggibile.
    with pytest.raises(
        BacktestMetricsError,
        match="mancanti",
    ):
        calculate_backtest_metrics(trades)


def test_negative_costs_are_rejected() -> None:
    """Verifica che i costi negativi vengano rifiutati."""

    # Crea un trade log valido.
    trades = create_trade_log()

    # Inserisce un costo non valido.
    trades.loc[0, "total_cost_percentage"] = -0.001

    # Verifica che venga prodotto l'errore previsto.
    with pytest.raises(
        BacktestMetricsError,
        match="costi percentuali negativi",
    ):
        calculate_backtest_metrics(trades)
