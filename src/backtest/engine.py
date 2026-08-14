"""Motore di backtest conservativo per segnali di paper trading."""

# Importa dataclass per rappresentare configurazione e risultato.
from dataclasses import asdict, dataclass

# Importa pandas per elaborare dati e trade.
import pandas as pd


class BacktestError(ValueError):
    """Errore generato da dati o configurazioni di backtest non validi."""


@dataclass(frozen=True)
class BacktestConfig:
    """Configurazione del motore di backtest."""

    # Slippage applicato all'ingresso e all'uscita, espresso in percentuale.
    slippage_percentage: float = 0.0001

    # Costo percentuale complessivo di ingresso e uscita.
    round_trip_commission_percentage: float = 0.0002

    # Numero massimo di candele durante cui il trade può restare aperto.
    maximum_holding_bars: int = 12

    # Livello Take Profit utilizzato per chiudere il trade.
    take_profit_r: float = 1.0

    # Applica una regola conservativa se SL e TP sono toccati insieme.
    stop_first_when_ambiguous: bool = True


@dataclass(frozen=True)
class SimulatedTrade:
    """Risultato di un singolo trade simulato."""

    # Identificativo progressivo del trade.
    trade_id: int

    # Direzione LONG oppure SHORT.
    direction: str

    # Timestamp del segnale confermato.
    signal_timestamp: str

    # Timestamp dell'ingresso simulato.
    entry_timestamp: str

    # Timestamp dell'uscita simulata.
    exit_timestamp: str

    # Prezzo di ingresso dopo lo slippage.
    entry_price: float

    # Prezzo dello Stop Loss.
    stop_loss: float

    # Prezzo del Take Profit.
    take_profit: float

    # Prezzo di uscita dopo lo slippage.
    exit_price: float

    # Motivo dell'uscita.
    exit_reason: str

    # Numero di candele mantenute.
    holding_bars: int

    # Rendimento lordo percentuale.
    gross_return_percentage: float

    # Costi percentuali complessivi.
    total_cost_percentage: float

    # Rendimento netto percentuale.
    net_return_percentage: float

    # Risultato espresso in multipli di rischio R.
    result_r: float

    def to_dict(self) -> dict[str, int | float | str]:
        """Converte il trade in un dizionario."""

        # Converte automaticamente tutti i campi della dataclass.
        return asdict(self)


def _validate_config(config: BacktestConfig) -> None:
    """Verifica la configurazione del backtest."""

    # Lo slippage non può essere negativo.
    if config.slippage_percentage < 0:
        raise BacktestError("Lo slippage percentuale non può essere negativo.")

    # Le commissioni non possono essere negative.
    if config.round_trip_commission_percentage < 0:
        raise BacktestError("Le commissioni percentuali non possono essere negative.")

    # La durata massima deve includere almeno una candela.
    if config.maximum_holding_bars <= 0:
        raise BacktestError("La durata massima del trade deve essere maggiore di zero.")

    # Il rapporto del Take Profit deve essere positivo.
    if config.take_profit_r <= 0:
        raise BacktestError("Il rapporto rischio/rendimento deve essere maggiore di zero.")

    # La prima versione richiede una gestione conservativa delle ambiguità.
    if not config.stop_first_when_ambiguous:
        raise BacktestError(
            "La prima versione del backtest richiede stop_first_when_ambiguous impostato a true."
        )


def _validate_input(dataframe: pd.DataFrame) -> None:
    """Verifica le colonne richieste dal motore."""

    # Definisce le colonne necessarie al backtest.
    required_columns = {
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "signal",
        "signal_status",
        "signal_available_at",
        "risk_distance",
    }

    # Individua le colonne mancanti.
    missing_columns = sorted(required_columns.difference(dataframe.columns))

    # Interrompe il backtest se manca almeno una colonna.
    if missing_columns:
        missing_text = ", ".join(missing_columns)

        raise BacktestError(f"Colonne necessarie al backtest mancanti: {missing_text}.")

    # Il dataset non può essere vuoto.
    if dataframe.empty:
        raise BacktestError("Il dataset del backtest è vuoto.")

    # I timestamp devono essere ordinati.
    if not dataframe["timestamp"].is_monotonic_increasing:
        raise BacktestError("I timestamp del backtest non sono ordinati.")

    # I timestamp non possono essere duplicati.
    if dataframe["timestamp"].duplicated().any():
        raise BacktestError("Il dataset del backtest contiene timestamp duplicati.")


def _apply_entry_slippage(
    price: float,
    direction: str,
    slippage_percentage: float,
) -> float:
    """Applica slippage sfavorevole al prezzo di ingresso."""

    # Un LONG entra a un prezzo leggermente superiore.
    if direction == "LONG":
        return price * (1.0 + slippage_percentage)

    # Uno SHORT entra a un prezzo leggermente inferiore.
    return price * (1.0 - slippage_percentage)


def _apply_exit_slippage(
    price: float,
    direction: str,
    slippage_percentage: float,
) -> float:
    """Applica slippage sfavorevole al prezzo di uscita."""

    # Un LONG vende a un prezzo leggermente inferiore.
    if direction == "LONG":
        return price * (1.0 - slippage_percentage)

    # Uno SHORT ricopre a un prezzo leggermente superiore.
    return price * (1.0 + slippage_percentage)


def _calculate_trade_levels(
    entry_price: float,
    risk_distance: float,
    direction: str,
    take_profit_r: float,
) -> tuple[float, float]:
    """Ricalcola SL e TP rispetto al prezzo effettivo di ingresso."""

    # Calcola i livelli LONG.
    if direction == "LONG":
        stop_loss = entry_price - risk_distance
        take_profit = entry_price + risk_distance * take_profit_r

    # Calcola i livelli SHORT.
    else:
        stop_loss = entry_price + risk_distance
        take_profit = entry_price - risk_distance * take_profit_r

    # Restituisce Stop Loss e Take Profit.
    return stop_loss, take_profit


def _detect_exit(
    candle: pd.Series,
    direction: str,
    stop_loss: float,
    take_profit: float,
) -> tuple[str | None, float | None]:
    """Verifica se una candela ha raggiunto SL oppure TP."""

    # Controlla i livelli di un trade LONG.
    if direction == "LONG":
        stop_touched = candle["low"] <= stop_loss
        target_touched = candle["high"] >= take_profit

    # Controlla i livelli di un trade SHORT.
    else:
        stop_touched = candle["high"] >= stop_loss
        target_touched = candle["low"] <= take_profit

    # Se entrambi sono toccati, prevale lo Stop Loss.
    if stop_touched and target_touched:
        return "STOP_LOSS_AMBIGUOUS", stop_loss

    # Restituisce lo Stop Loss se è stato raggiunto.
    if stop_touched:
        return "STOP_LOSS", stop_loss

    # Restituisce il Take Profit se è stato raggiunto.
    if target_touched:
        return "TAKE_PROFIT", take_profit

    # Nessun livello è stato raggiunto.
    return None, None


def _calculate_gross_return(
    entry_price: float,
    exit_price: float,
    direction: str,
) -> float:
    """Calcola il rendimento lordo percentuale."""

    # Calcola il rendimento LONG.
    if direction == "LONG":
        return (exit_price / entry_price) - 1.0

    # Calcola il rendimento SHORT.
    return (entry_price / exit_price) - 1.0


def run_backtest(
    dataframe: pd.DataFrame,
    config: BacktestConfig | None = None,
) -> pd.DataFrame:
    """Esegue un backtest sequenziale e conservativo.

    Gli ingressi avvengono esclusivamente all'Open della candela
    successiva al segnale confermato. Non sono consentiti trade
    sovrapposti.

    Args:
        dataframe: Dataset contenente OHLCV, segnali e livelli di rischio.
        config: Configurazione facoltativa del backtest.

    Returns:
        DataFrame contenente il registro dei trade simulati.
    """

    # Verifica che l'input sia un DataFrame.
    if not isinstance(dataframe, pd.DataFrame):
        raise TypeError("Il dato ricevuto deve essere un pandas DataFrame.")

    # Usa la configurazione predefinita se non specificata.
    selected_config = config or BacktestConfig()

    # Valida configurazione e dataset.
    _validate_config(selected_config)
    _validate_input(dataframe)

    # Crea una copia con indice sequenziale.
    working_dataframe = dataframe.copy(deep=True).reset_index(drop=True)

    # Conterrà tutti i trade chiusi.
    completed_trades: list[SimulatedTrade] = []

    # Indice minimo dal quale cercare un nuovo segnale.
    next_available_index = 0

    # Analizza ciascuna riga come possibile segnale.
    for signal_index in range(len(working_dataframe) - 1):
        # Ignora righe appartenenti a un trade già elaborato.
        if signal_index < next_available_index:
            continue

        # Recupera la riga del segnale.
        signal_row = working_dataframe.iloc[signal_index]

        # Accetta solamente LONG e SHORT confermati.
        if signal_row["signal"] not in {"LONG", "SHORT"}:
            continue

        if signal_row["signal_status"] != "CONFIRMED":
            continue

        # Il Risk Engine deve aver prodotto una distanza valida.
        if pd.isna(signal_row["risk_distance"]):
            continue

        risk_distance = float(signal_row["risk_distance"])

        # Ignora distanze di rischio non positive.
        if risk_distance <= 0:
            continue

        # L'ingresso avviene sulla candela immediatamente successiva.
        entry_index = signal_index + 1
        entry_row = working_dataframe.iloc[entry_index]
        direction = str(signal_row["signal"])

        # Applica slippage sfavorevole all'Open di ingresso.
        entry_price = _apply_entry_slippage(
            price=float(entry_row["open"]),
            direction=direction,
            slippage_percentage=selected_config.slippage_percentage,
        )

        # Ricalcola SL e TP sul prezzo effettivo di ingresso.
        stop_loss, take_profit = _calculate_trade_levels(
            entry_price=entry_price,
            risk_distance=risk_distance,
            direction=direction,
            take_profit_r=selected_config.take_profit_r,
        )

        # Definisce l'ultima candela analizzabile.
        last_exit_index = min(
            entry_index + selected_config.maximum_holding_bars - 1,
            len(working_dataframe) - 1,
        )

        # Valori che verranno aggiornati al momento dell'uscita.
        selected_exit_index = last_exit_index
        exit_reason = "TIME_EXPIRY"
        raw_exit_price = float(working_dataframe.iloc[last_exit_index]["close"])

        # Analizza le candele dalla candela di ingresso in avanti.
        for exit_index in range(
            entry_index,
            last_exit_index + 1,
        ):
            # Recupera la candela da controllare.
            exit_candle = working_dataframe.iloc[exit_index]

            # Verifica l'eventuale raggiungimento di SL o TP.
            detected_reason, detected_price = _detect_exit(
                candle=exit_candle,
                direction=direction,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )

            # Chiude il trade al primo evento rilevato.
            if detected_reason is not None:
                selected_exit_index = exit_index
                exit_reason = detected_reason
                raw_exit_price = float(detected_price)
                break

        # Applica slippage sfavorevole all'uscita.
        exit_price = _apply_exit_slippage(
            price=raw_exit_price,
            direction=direction,
            slippage_percentage=selected_config.slippage_percentage,
        )

        # Calcola il rendimento lordo.
        gross_return_percentage = _calculate_gross_return(
            entry_price=entry_price,
            exit_price=exit_price,
            direction=direction,
        )

        # Recupera i costi configurati.
        total_cost_percentage = selected_config.round_trip_commission_percentage

        # Calcola il risultato netto.
        net_return_percentage = gross_return_percentage - total_cost_percentage

        # Converte il risultato netto in multipli di rischio.
        risk_percentage = risk_distance / entry_price
        result_r = net_return_percentage / risk_percentage

        # Recupera la riga di uscita.
        selected_exit_row = working_dataframe.iloc[selected_exit_index]

        # Crea il trade simulato.
        trade = SimulatedTrade(
            trade_id=len(completed_trades) + 1,
            direction=direction,
            signal_timestamp=signal_row["signal_available_at"].isoformat(),
            entry_timestamp=entry_row["timestamp"].isoformat(),
            exit_timestamp=selected_exit_row["timestamp"].isoformat(),
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            exit_price=exit_price,
            exit_reason=exit_reason,
            holding_bars=selected_exit_index - entry_index + 1,
            gross_return_percentage=gross_return_percentage,
            total_cost_percentage=total_cost_percentage,
            net_return_percentage=net_return_percentage,
            result_r=result_r,
        )

        # Registra il trade completato.
        completed_trades.append(trade)

        # Impedisce l'apertura di trade sovrapposti.
        next_available_index = selected_exit_index + 1

    # Definisce le colonne anche quando non esistono trade.
    trade_columns = list(SimulatedTrade.__dataclass_fields__.keys())

    # Converte tutti i trade in un DataFrame.
    return pd.DataFrame(
        [trade.to_dict() for trade in completed_trades],
        columns=trade_columns,
    )
