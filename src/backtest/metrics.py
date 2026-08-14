"""Calcolo delle metriche di valutazione del backtest."""

# Importa dataclass per rappresentare il report in modo strutturato.
# Importa math per gestire valori infiniti e controlli numerici.
import math
from dataclasses import asdict, dataclass

# Importa pandas per analizzare il registro dei trade.
import pandas as pd


class BacktestMetricsError(ValueError):
    """Errore generato da un trade log non valido."""


@dataclass(frozen=True)
class BacktestMetrics:
    """Metriche riassuntive prodotte dal backtest."""

    # Numero totale di trade simulati.
    total_trades: int

    # Numero di trade con rendimento netto positivo.
    winning_trades: int

    # Numero di trade con rendimento netto negativo.
    losing_trades: int

    # Numero di trade con rendimento netto uguale a zero.
    breakeven_trades: int

    # Percentuale di trade positivi.
    win_rate_percentage: float

    # Rendimento netto composto di tutti i trade.
    cumulative_return_percentage: float

    # Rendimento netto medio per trade.
    average_net_return_percentage: float

    # Risultato medio espresso in multipli di rischio.
    expectancy_r: float

    # Guadagno medio dei trade positivi espresso in R.
    average_win_r: float

    # Perdita media assoluta dei trade negativi espressa in R.
    average_loss_r: float

    # Rapporto fra profitti lordi e perdite lorde.
    profit_factor: float | None

    # Massimo drawdown della curva composta.
    maximum_drawdown_percentage: float

    # Serie massima consecutiva di trade positivi.
    maximum_consecutive_wins: int

    # Serie massima consecutiva di trade negativi.
    maximum_consecutive_losses: int

    # Costi percentuali complessivi applicati.
    total_cost_percentage: float

    def to_dict(self) -> dict[str, int | float | None]:
        """Converte le metriche in un dizionario serializzabile."""

        # Converte automaticamente tutti i campi della dataclass.
        return asdict(self)


def _validate_trade_log(trades: pd.DataFrame) -> None:
    """Verifica che il trade log contenga le colonne necessarie."""

    # Verifica che l'input sia un DataFrame.
    if not isinstance(trades, pd.DataFrame):
        raise TypeError("Il trade log deve essere un pandas DataFrame.")

    # Definisce le colonne necessarie per calcolare le metriche.
    required_columns = {
        "trade_id",
        "net_return_percentage",
        "total_cost_percentage",
        "result_r",
    }

    # Individua le colonne mancanti.
    missing_columns = sorted(required_columns.difference(trades.columns))

    # Interrompe il calcolo se manca una colonna obbligatoria.
    if missing_columns:
        missing_text = ", ".join(missing_columns)

        raise BacktestMetricsError(f"Colonne necessarie alle metriche mancanti: {missing_text}.")

    # Verifica l'assenza di valori mancanti nelle colonne numeriche.
    numeric_columns = [
        "net_return_percentage",
        "total_cost_percentage",
        "result_r",
    ]

    if trades[numeric_columns].isna().any().any():
        raise BacktestMetricsError("Il trade log contiene valori numerici mancanti.")

    # Verifica che i costi non siano negativi.
    if (trades["total_cost_percentage"] < 0).any():
        raise BacktestMetricsError("Il trade log contiene costi percentuali negativi.")


def _calculate_maximum_drawdown(
    net_returns: pd.Series,
) -> float:
    """Calcola il maximum drawdown dalla curva composta."""

    # Costruisce la curva del capitale partendo da un valore unitario.
    equity_curve = (1.0 + net_returns).cumprod()

    # Calcola il massimo storico raggiunto dalla curva.
    running_maximum = equity_curve.cummax()

    # Calcola il drawdown relativo a ogni trade.
    drawdown = (equity_curve / running_maximum) - 1.0

    # Restituisce il drawdown massimo come valore percentuale positivo.
    return abs(float(drawdown.min())) * 100.0


def _calculate_maximum_streak(
    conditions: pd.Series,
) -> int:
    """Calcola la serie consecutiva massima di condizioni vere."""

    # Contiene la lunghezza della serie corrente.
    current_streak = 0

    # Contiene la massima serie rilevata.
    maximum_streak = 0

    # Analizza ogni condizione in ordine cronologico.
    for condition in conditions:
        # Incrementa la serie se la condizione è vera.
        if bool(condition):
            current_streak += 1

            # Aggiorna il massimo se necessario.
            maximum_streak = max(
                maximum_streak,
                current_streak,
            )

        # Azzera la serie quando la condizione è falsa.
        else:
            current_streak = 0

    # Restituisce la massima serie consecutiva.
    return maximum_streak


def calculate_backtest_metrics(
    trades: pd.DataFrame,
) -> BacktestMetrics:
    """Calcola le metriche riassuntive del trade log.

    Args:
        trades: Registro dei trade prodotto dal motore di backtest.

    Returns:
        Metriche strutturate del backtest.

    Raises:
        BacktestMetricsError: se il trade log non è valido.
    """

    # Valida struttura e contenuto del trade log.
    _validate_trade_log(trades)

    # Gestisce esplicitamente un backtest senza operazioni.
    if trades.empty:
        return BacktestMetrics(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            breakeven_trades=0,
            win_rate_percentage=0.0,
            cumulative_return_percentage=0.0,
            average_net_return_percentage=0.0,
            expectancy_r=0.0,
            average_win_r=0.0,
            average_loss_r=0.0,
            profit_factor=None,
            maximum_drawdown_percentage=0.0,
            maximum_consecutive_wins=0,
            maximum_consecutive_losses=0,
            total_cost_percentage=0.0,
        )

    # Crea maschere per trade positivi, negativi e in pareggio.
    winning_mask = trades["net_return_percentage"] > 0
    losing_mask = trades["net_return_percentage"] < 0
    breakeven_mask = trades["net_return_percentage"] == 0

    # Conta i risultati.
    total_trades = len(trades)
    winning_trades = int(winning_mask.sum())
    losing_trades = int(losing_mask.sum())
    breakeven_trades = int(breakeven_mask.sum())

    # Calcola la percentuale di trade positivi.
    win_rate_percentage = (winning_trades / total_trades) * 100.0

    # Calcola il rendimento composto dell'intera sequenza.
    cumulative_return_percentage = ((1.0 + trades["net_return_percentage"]).prod() - 1.0) * 100.0

    # Calcola il rendimento netto medio per trade.
    average_net_return_percentage = trades["net_return_percentage"].mean() * 100.0

    # Calcola l'expectancy media in multipli di rischio.
    expectancy_r = float(trades["result_r"].mean())

    # Calcola il guadagno medio in R.
    average_win_r = (
        float(trades.loc[winning_mask, "result_r"].mean()) if winning_trades > 0 else 0.0
    )

    # Calcola la perdita media assoluta in R.
    average_loss_r = (
        abs(float(trades.loc[losing_mask, "result_r"].mean())) if losing_trades > 0 else 0.0
    )

    # Somma i risultati R positivi.
    gross_profit_r = float(
        trades.loc[
            trades["result_r"] > 0,
            "result_r",
        ].sum()
    )

    # Somma il valore assoluto dei risultati R negativi.
    gross_loss_r = abs(
        float(
            trades.loc[
                trades["result_r"] < 0,
                "result_r",
            ].sum()
        )
    )

    # Calcola il Profit Factor quando esistono perdite.
    if gross_loss_r > 0:
        profit_factor = gross_profit_r / gross_loss_r

    # Se esistono guadagni ma nessuna perdita, il rapporto è infinito.
    elif gross_profit_r > 0:
        profit_factor = math.inf

    # Se non esistono né guadagni né perdite, il valore non è definito.
    else:
        profit_factor = None

    # Calcola il massimo drawdown della curva composta.
    maximum_drawdown_percentage = _calculate_maximum_drawdown(trades["net_return_percentage"])

    # Calcola le serie consecutive.
    maximum_consecutive_wins = _calculate_maximum_streak(winning_mask)
    maximum_consecutive_losses = _calculate_maximum_streak(losing_mask)

    # Somma tutti i costi percentuali applicati.
    total_cost_percentage = trades["total_cost_percentage"].sum() * 100.0

    # Restituisce il report completo.
    return BacktestMetrics(
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        breakeven_trades=breakeven_trades,
        win_rate_percentage=round(
            win_rate_percentage,
            6,
        ),
        cumulative_return_percentage=round(
            cumulative_return_percentage,
            6,
        ),
        average_net_return_percentage=round(
            average_net_return_percentage,
            6,
        ),
        expectancy_r=round(
            expectancy_r,
            6,
        ),
        average_win_r=round(
            average_win_r,
            6,
        ),
        average_loss_r=round(
            average_loss_r,
            6,
        ),
        profit_factor=(None if profit_factor is None else round(profit_factor, 6)),
        maximum_drawdown_percentage=round(
            maximum_drawdown_percentage,
            6,
        ),
        maximum_consecutive_wins=maximum_consecutive_wins,
        maximum_consecutive_losses=maximum_consecutive_losses,
        total_cost_percentage=round(
            total_cost_percentage,
            6,
        ),
    )
