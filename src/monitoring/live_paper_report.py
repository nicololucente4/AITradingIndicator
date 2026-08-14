"""Report statistico dei segnali e degli esiti Live Paper."""

# Importa dataclass per rappresentare il report.
from dataclasses import asdict, dataclass

# Importa pandas per analizzare segnali ed esiti.
import pandas as pd


class LivePaperReportError(ValueError):
    """Errore generato durante la creazione del report Live Paper."""


@dataclass(frozen=True)
class LivePaperStatistics:
    """Statistiche complessive della sessione Live Paper."""

    # Numero totale di segnali registrati.
    total_signals: int

    # Numero di segnali LONG.
    long_signals: int

    # Numero di segnali SHORT.
    short_signals: int

    # Numero di segnali NO_TRADE.
    no_trade_signals: int

    # Numero totale di segnali direzionali.
    directional_signals: int

    # Numero di segnali direzionali conclusi.
    resolved_directional_signals: int

    # Numero di segnali direzionali ancora pendenti.
    pending_directional_signals: int

    # Percentuale di segnali direzionali conclusi.
    resolution_rate_percentage: float

    # Numero di esiti con risultato R positivo.
    winning_outcomes: int

    # Numero di esiti con risultato R negativo.
    losing_outcomes: int

    # Numero di esiti con risultato R uguale a zero.
    breakeven_outcomes: int

    # Percentuale di esiti positivi.
    win_rate_percentage: float

    # Risultato medio espresso in R.
    expectancy_r: float

    # Risultato R medio degli esiti positivi.
    average_win_r: float

    # Perdita R media assoluta degli esiti negativi.
    average_loss_r: float

    # Rapporto tra profitti R e perdite R.
    profit_factor: float | None

    # Rendimento lordo composto percentuale.
    cumulative_return_percentage: float

    # Massimo drawdown percentuale.
    maximum_drawdown_percentage: float

    # Numero di uscite a TP1.
    take_profit_outcomes: int

    # Numero di uscite allo Stop Loss.
    stop_loss_outcomes: int

    # Numero di uscite ambigue trattate come Stop Loss.
    ambiguous_stop_outcomes: int

    # Numero di uscite per scadenza temporale.
    time_expiry_outcomes: int

    # Durata media degli esiti in candele.
    average_holding_bars: float

    # Confidenza media dei segnali direzionali.
    average_directional_confidence: float | None

    # Indica la modalità esclusivamente simulata.
    paper_trading_only: bool

    def to_dict(self) -> dict[str, object]:
        """Converte il report in un dizionario serializzabile."""

        # Converte automaticamente tutti i campi.
        return asdict(self)


def _validate_signals(
    signals: pd.DataFrame,
) -> None:
    """Verifica la struttura del registro dei segnali."""

    # L'input deve essere un DataFrame.
    if not isinstance(signals, pd.DataFrame):
        raise TypeError("Il registro dei segnali deve essere un pandas DataFrame.")

    # Definisce le colonne obbligatorie.
    required_columns = {
        "signal_id",
        "signal",
        "signal_status",
    }

    # Individua eventuali colonne mancanti.
    missing_columns = sorted(required_columns.difference(signals.columns))

    # Interrompe il calcolo se manca almeno una colonna.
    if missing_columns:
        missing_text = ", ".join(missing_columns)

        raise LivePaperReportError(f"Colonne mancanti nel registro segnali: {missing_text}.")

    # Ogni segnale deve avere un identificativo univoco.
    if signals["signal_id"].duplicated().any():
        raise LivePaperReportError("Il registro dei segnali contiene signal_id duplicati.")

    # Definisce i segnali supportati.
    allowed_signals = {
        "LONG",
        "SHORT",
        "NO_TRADE",
    }

    # Individua eventuali segnali sconosciuti.
    invalid_signals = sorted(set(signals["signal"]).difference(allowed_signals))

    if invalid_signals:
        invalid_text = ", ".join(invalid_signals)

        raise LivePaperReportError(f"Segnali non supportati: {invalid_text}.")

    # Tutti i segnali devono essere confermati.
    if not signals["signal_status"].eq("CONFIRMED").all():
        raise LivePaperReportError("Il report accetta solamente segnali confermati.")


def _validate_outcomes(
    outcomes: pd.DataFrame,
) -> None:
    """Verifica la struttura del registro degli esiti."""

    # L'input deve essere un DataFrame.
    if not isinstance(outcomes, pd.DataFrame):
        raise TypeError("Il registro degli esiti deve essere un pandas DataFrame.")

    # Un DataFrame vuoto è valido, purché contenga lo schema previsto.
    required_columns = {
        "signal_id",
        "exit_reason",
        "holding_bars",
        "gross_return_percentage",
        "result_r",
    }

    # Individua eventuali colonne mancanti.
    missing_columns = sorted(required_columns.difference(outcomes.columns))

    if missing_columns:
        missing_text = ", ".join(missing_columns)

        raise LivePaperReportError(f"Colonne mancanti nel registro esiti: {missing_text}.")

    # Ogni segnale può avere un solo esito conclusivo.
    if outcomes["signal_id"].duplicated().any():
        raise LivePaperReportError("Il registro degli esiti contiene signal_id duplicati.")

    # Verifica i valori numerici quando sono presenti esiti.
    if not outcomes.empty:
        numeric_columns = [
            "holding_bars",
            "gross_return_percentage",
            "result_r",
        ]

        if outcomes[numeric_columns].isna().any().any():
            raise LivePaperReportError("Il registro degli esiti contiene valori mancanti.")

        # La durata deve essere positiva.
        if (outcomes["holding_bars"] <= 0).any():
            raise LivePaperReportError("La durata degli esiti deve essere maggiore di zero.")


def _calculate_maximum_drawdown(
    returns: pd.Series,
) -> float:
    """Calcola il massimo drawdown dalla curva composta."""

    # Se non esistono esiti, il drawdown è nullo.
    if returns.empty:
        return 0.0

    # Costruisce la curva composta partendo da capitale unitario.
    equity_curve = (1.0 + returns).cumprod()

    # Calcola il massimo storico della curva.
    running_maximum = equity_curve.cummax()

    # Calcola il drawdown di ogni punto.
    drawdowns = (equity_curve / running_maximum) - 1.0

    # Restituisce il drawdown massimo come percentuale positiva.
    return abs(float(drawdowns.min())) * 100.0


def _calculate_profit_factor(
    result_r: pd.Series,
) -> float | None:
    """Calcola il Profit Factor usando i risultati in R."""

    # Somma tutti i risultati positivi.
    gross_profit = float(result_r.loc[result_r > 0].sum())

    # Somma il valore assoluto dei risultati negativi.
    gross_loss = abs(float(result_r.loc[result_r < 0].sum()))

    # Calcola il rapporto quando esistono perdite.
    if gross_loss > 0:
        return gross_profit / gross_loss

    # Senza perdite ma con profitti, il valore è infinito.
    if gross_profit > 0:
        return float("inf")

    # Senza profitti e perdite, il valore non è definito.
    return None


def generate_live_paper_statistics(
    signals: pd.DataFrame,
    outcomes: pd.DataFrame,
) -> LivePaperStatistics:
    """Genera le statistiche Live Paper da segnali ed esiti.

    Args:
        signals: Registro immutabile dei segnali.
        outcomes: Registro separato degli esiti conclusivi.

    Returns:
        Statistiche aggregate della sessione Live Paper.
    """

    # Valida entrambi i registri.
    _validate_signals(signals)
    _validate_outcomes(outcomes)

    # Verifica che ogni esito faccia riferimento a un segnale esistente.
    unknown_outcome_ids = sorted(set(outcomes["signal_id"]).difference(signals["signal_id"]))

    if unknown_outcome_ids:
        unknown_text = ", ".join(unknown_outcome_ids)

        raise LivePaperReportError(f"Esiti associati a segnali inesistenti: {unknown_text}.")

    # Crea le maschere dei diversi tipi di segnale.
    long_mask = signals["signal"].eq("LONG")
    short_mask = signals["signal"].eq("SHORT")
    no_trade_mask = signals["signal"].eq("NO_TRADE")
    directional_mask = signals["signal"].isin(
        {
            "LONG",
            "SHORT",
        }
    )

    # Conta i segnali.
    total_signals = len(signals)
    long_signals = int(long_mask.sum())
    short_signals = int(short_mask.sum())
    no_trade_signals = int(no_trade_mask.sum())
    directional_signals = int(directional_mask.sum())

    # Recupera gli identificativi direzionali.
    directional_signal_ids = set(
        signals.loc[
            directional_mask,
            "signal_id",
        ]
    )

    # Considera esclusivamente esiti associati a segnali direzionali.
    directional_outcomes = outcomes.loc[outcomes["signal_id"].isin(directional_signal_ids)].copy()

    # Conta esiti conclusi e pendenti.
    resolved_directional_signals = len(directional_outcomes)

    pending_directional_signals = directional_signals - resolved_directional_signals

    # La quantità dei pendenti non può essere negativa.
    if pending_directional_signals < 0:
        raise LivePaperReportError("Il numero di esiti supera i segnali direzionali.")

    # Calcola il tasso di risoluzione.
    resolution_rate_percentage = (
        resolved_directional_signals / directional_signals * 100.0
        if directional_signals > 0
        else 0.0
    )

    # Crea maschere dei risultati in R.
    winning_mask = directional_outcomes["result_r"] > 0

    losing_mask = directional_outcomes["result_r"] < 0

    breakeven_mask = directional_outcomes["result_r"] == 0

    # Conta vincite, perdite e pareggi.
    winning_outcomes = int(winning_mask.sum())

    losing_outcomes = int(losing_mask.sum())

    breakeven_outcomes = int(breakeven_mask.sum())

    # Calcola il win rate sugli esiti conclusi.
    win_rate_percentage = (
        winning_outcomes / resolved_directional_signals * 100.0
        if resolved_directional_signals > 0
        else 0.0
    )

    # Calcola l'Expectancy in R.
    expectancy_r = (
        float(directional_outcomes["result_r"].mean()) if resolved_directional_signals > 0 else 0.0
    )

    # Calcola il risultato medio dei trade positivi.
    average_win_r = (
        float(
            directional_outcomes.loc[
                winning_mask,
                "result_r",
            ].mean()
        )
        if winning_outcomes > 0
        else 0.0
    )

    # Calcola la perdita media assoluta.
    average_loss_r = (
        abs(
            float(
                directional_outcomes.loc[
                    losing_mask,
                    "result_r",
                ].mean()
            )
        )
        if losing_outcomes > 0
        else 0.0
    )

    # Calcola il Profit Factor.
    profit_factor = _calculate_profit_factor(directional_outcomes["result_r"])

    # Calcola il rendimento composto lordo.
    cumulative_return_percentage = (
        ((1.0 + directional_outcomes["gross_return_percentage"]).prod() - 1.0) * 100.0
        if resolved_directional_signals > 0
        else 0.0
    )

    # Calcola il massimo drawdown.
    maximum_drawdown_percentage = _calculate_maximum_drawdown(
        directional_outcomes["gross_return_percentage"]
    )

    # Conta le diverse cause di uscita.
    exit_counts = directional_outcomes["exit_reason"].value_counts()

    take_profit_outcomes = int(
        exit_counts.get(
            "TAKE_PROFIT_1",
            0,
        )
    )

    stop_loss_outcomes = int(
        exit_counts.get(
            "STOP_LOSS",
            0,
        )
    )

    ambiguous_stop_outcomes = int(
        exit_counts.get(
            "STOP_LOSS_AMBIGUOUS",
            0,
        )
    )

    time_expiry_outcomes = int(
        exit_counts.get(
            "TIME_EXPIRY",
            0,
        )
    )

    # Calcola la durata media.
    average_holding_bars = (
        float(directional_outcomes["holding_bars"].mean())
        if resolved_directional_signals > 0
        else 0.0
    )

    # Calcola la confidenza media, se disponibile.
    average_directional_confidence: float | None = None

    if "prediction_confidence" in signals.columns:
        directional_confidence = signals.loc[
            directional_mask,
            "prediction_confidence",
        ].dropna()

        if not directional_confidence.empty:
            average_directional_confidence = float(directional_confidence.mean())

    # Restituisce il report completo.
    return LivePaperStatistics(
        total_signals=total_signals,
        long_signals=long_signals,
        short_signals=short_signals,
        no_trade_signals=no_trade_signals,
        directional_signals=directional_signals,
        resolved_directional_signals=(resolved_directional_signals),
        pending_directional_signals=(pending_directional_signals),
        resolution_rate_percentage=round(
            resolution_rate_percentage,
            6,
        ),
        winning_outcomes=winning_outcomes,
        losing_outcomes=losing_outcomes,
        breakeven_outcomes=breakeven_outcomes,
        win_rate_percentage=round(
            win_rate_percentage,
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
        profit_factor=(
            None
            if profit_factor is None
            else round(
                profit_factor,
                6,
            )
        ),
        cumulative_return_percentage=round(
            cumulative_return_percentage,
            6,
        ),
        maximum_drawdown_percentage=round(
            maximum_drawdown_percentage,
            6,
        ),
        take_profit_outcomes=take_profit_outcomes,
        stop_loss_outcomes=stop_loss_outcomes,
        ambiguous_stop_outcomes=ambiguous_stop_outcomes,
        time_expiry_outcomes=time_expiry_outcomes,
        average_holding_bars=round(
            average_holding_bars,
            6,
        ),
        average_directional_confidence=(
            None
            if average_directional_confidence is None
            else round(
                average_directional_confidence,
                6,
            )
        ),
        paper_trading_only=True,
    )
