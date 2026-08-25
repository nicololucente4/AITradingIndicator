"""Filtro selettivo per l'apertura delle operazioni paper."""

# Importa dataclass per configurazione e risultato immutabili.
from dataclasses import dataclass

# Importa pandas per gestire i valori mancanti.
import pandas as pd


class SelectiveTradeFilterError(ValueError):
    """Errore generato dal filtro selettivo."""


@dataclass(frozen=True)
class SelectiveTradeFilterConfig:
    """Configurazione delle soglie di apertura."""

    # Confidenza minima richiesta al modello.
    minimum_confidence: float = 0.80

    # Margine minimo tra prima e seconda probabilità.
    minimum_probability_margin: float = 0.20

    # Richiede un segnale confermato.
    require_confirmed_signal: bool = True

    # Mantiene obbligatoria la modalità paper.
    paper_trading_only: bool = True


@dataclass(frozen=True)
class SelectiveTradeDecision:
    """Risultato della valutazione del segnale."""

    # Indica se il segnale può aprire un paper trade.
    accepted: bool

    # Direzione originale.
    signal: str

    # Confidenza rilevata.
    confidence: float | None

    # Margine probabilistico rilevato.
    probability_margin: float | None

    # Codice sintetico della decisione.
    reason: str

    # Descrizione leggibile.
    message: str

    def to_dict(
        self,
    ) -> dict[str, object]:
        """Converte la decisione in un record serializzabile."""

        return {
            "accepted": self.accepted,
            "signal": self.signal,
            "confidence": self.confidence,
            "probability_margin": (self.probability_margin),
            "reason": self.reason,
            "message": self.message,
        }


def _validate_config(
    config: SelectiveTradeFilterConfig,
) -> None:
    """Verifica la configurazione del filtro."""

    if not (0.0 < config.minimum_confidence <= 1.0):
        raise SelectiveTradeFilterError(
            "minimum_confidence deve essere maggiore di zero e minore o uguale a uno."
        )

    if not (0.0 <= config.minimum_probability_margin <= 1.0):
        raise SelectiveTradeFilterError(
            "minimum_probability_margin deve essere compreso tra zero e uno."
        )

    if not config.require_confirmed_signal:
        raise SelectiveTradeFilterError("La prima versione richiede require_confirmed_signal=true.")

    if not config.paper_trading_only:
        raise SelectiveTradeFilterError("Il filtro richiede paper_trading_only=true.")


def _optional_float(
    value: object,
) -> float | None:
    """Converte un valore numerico opzionale."""

    if value is None or pd.isna(value):
        return None

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ) as error:
        raise SelectiveTradeFilterError(
            "Il segnale contiene un valore numerico non valido."
        ) from error


def _required_positive_float(
    value: object,
    *,
    field_name: str,
) -> float:
    """Converte un prezzo obbligatorio e positivo."""

    selected_value = _optional_float(value)

    if selected_value is None:
        raise SelectiveTradeFilterError(f"{field_name} è obbligatorio.")

    if selected_value <= 0:
        raise SelectiveTradeFilterError(f"{field_name} deve essere maggiore di zero.")

    return selected_value


class SelectiveTradeFilter:
    """Decide se un segnale può aprire un paper trade."""

    def __init__(
        self,
        config: SelectiveTradeFilterConfig | None = None,
    ) -> None:
        """Inizializza il filtro selettivo."""

        self._config = config or SelectiveTradeFilterConfig()

        _validate_config(self._config)

    @property
    def config(
        self,
    ) -> SelectiveTradeFilterConfig:
        """Restituisce la configurazione corrente."""

        return self._config

    def evaluate(
        self,
        signal_row: pd.Series,
    ) -> SelectiveTradeDecision:
        """Valuta se il segnale può aprire una posizione."""

        if not isinstance(
            signal_row,
            pd.Series,
        ):
            raise TypeError("signal_row deve essere una pandas Series.")

        signal = (
            str(
                signal_row.get(
                    "signal",
                    "",
                )
            )
            .strip()
            .upper()
        )

        confidence = _optional_float(signal_row.get("prediction_confidence"))

        probability_margin = _optional_float(signal_row.get("probability_margin"))

        # NO_TRADE rimane diagnostico e non apre posizioni.
        if signal == "NO_TRADE":
            return SelectiveTradeDecision(
                accepted=False,
                signal=signal,
                confidence=confidence,
                probability_margin=(probability_margin),
                reason="NO_TRADE",
                message=("Il modello non ha prodotto una direzione operativa."),
            )

        # Rifiuta direzioni sconosciute.
        if signal not in {
            "LONG",
            "SHORT",
        }:
            return SelectiveTradeDecision(
                accepted=False,
                signal=signal,
                confidence=confidence,
                probability_margin=(probability_margin),
                reason="INVALID_SIGNAL",
                message=("La direzione del segnale non è supportata."),
            )

        signal_status = (
            str(
                signal_row.get(
                    "signal_status",
                    "",
                )
            )
            .strip()
            .upper()
        )

        # Accetta solo segnali confermati.
        if self._config.require_confirmed_signal and signal_status != "CONFIRMED":
            return SelectiveTradeDecision(
                accepted=False,
                signal=signal,
                confidence=confidence,
                probability_margin=(probability_margin),
                reason="SIGNAL_NOT_CONFIRMED",
                message=("Il segnale non è stato confermato."),
            )

        # La confidenza deve essere disponibile.
        if confidence is None:
            return SelectiveTradeDecision(
                accepted=False,
                signal=signal,
                confidence=None,
                probability_margin=(probability_margin),
                reason="MISSING_CONFIDENCE",
                message=("La confidenza del modello non è disponibile."),
            )

        if not (0.0 <= confidence <= 1.0):
            raise SelectiveTradeFilterError(
                "prediction_confidence deve essere compresa tra zero e uno."
            )

        # Applica la soglia minima di confidenza.
        if confidence < self._config.minimum_confidence:
            return SelectiveTradeDecision(
                accepted=False,
                signal=signal,
                confidence=confidence,
                probability_margin=(probability_margin),
                reason="LOW_CONFIDENCE",
                message=(
                    f"Confidenza inferiore alla soglia {self._config.minimum_confidence:.0%}."
                ),
            )

        # Il margine deve essere disponibile.
        if probability_margin is None:
            return SelectiveTradeDecision(
                accepted=False,
                signal=signal,
                confidence=confidence,
                probability_margin=None,
                reason="MISSING_PROBABILITY_MARGIN",
                message=("Il margine probabilistico non è disponibile."),
            )

        if not (0.0 <= probability_margin <= 1.0):
            raise SelectiveTradeFilterError(
                "probability_margin deve essere compreso tra zero e uno."
            )

        # Applica la soglia minima del margine.
        if probability_margin < self._config.minimum_probability_margin:
            return SelectiveTradeDecision(
                accepted=False,
                signal=signal,
                confidence=confidence,
                probability_margin=(probability_margin),
                reason="LOW_PROBABILITY_MARGIN",
                message=(
                    "Margine probabilistico inferiore "
                    "alla soglia "
                    f"{self._config.minimum_probability_margin:.0%}."
                ),
            )

        # Recupera e valida i livelli operativi.
        entry_price = _required_positive_float(
            signal_row.get("entry_price"),
            field_name="entry_price",
        )

        stop_loss = _required_positive_float(
            signal_row.get("stop_loss"),
            field_name="stop_loss",
        )

        take_profit_1 = _required_positive_float(
            signal_row.get("take_profit_1"),
            field_name="take_profit_1",
        )

        # Verifica la disposizione dei livelli LONG.
        if signal == "LONG" and not (stop_loss < entry_price < take_profit_1):
            return SelectiveTradeDecision(
                accepted=False,
                signal=signal,
                confidence=confidence,
                probability_margin=(probability_margin),
                reason="INVALID_PRICE_LEVELS",
                message=("I livelli LONG non rispettano Stop Loss < Entry < Take Profit."),
            )

        # Verifica la disposizione dei livelli SHORT.
        if signal == "SHORT" and not (take_profit_1 < entry_price < stop_loss):
            return SelectiveTradeDecision(
                accepted=False,
                signal=signal,
                confidence=confidence,
                probability_margin=(probability_margin),
                reason="INVALID_PRICE_LEVELS",
                message=("I livelli SHORT non rispettano Take Profit < Entry < Stop Loss."),
            )

        return SelectiveTradeDecision(
            accepted=True,
            signal=signal,
            confidence=confidence,
            probability_margin=(probability_margin),
            reason="HIGH_CONFIDENCE_SIGNAL",
            message=("Segnale direzionale accettato per l'apertura paper."),
        )
