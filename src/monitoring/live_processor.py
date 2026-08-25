"""Processore ML riutilizzabile per il Live Paper Engine."""

# Importa os per leggere le soglie configurabili dall'ambiente.
import os

# Importa dataclass e field per rappresentare la configurazione immutabile.
from dataclasses import dataclass, field

# Importa Path per gestire il Model Registry.
from pathlib import Path

# Importa pandas per elaborare lo storico OHLCV.
import pandas as pd

# Importa la configurazione delle feature tecniche.
from src.features.technical import TechnicalFeatureConfig

# Importa il processore ML già validato dal Replay.
from src.monitoring.ml_replay import (
    MLReplayConfig,
    process_ml_replay_snapshot,
)

# Importa la configurazione dei livelli di rischio.
from src.risk.levels import RiskLevelConfig

# Importa la configurazione del filtro di confidenza.
from src.signals.confidence_filter import ConfidenceFilterConfig


class LiveMLProcessorError(ValueError):
    """Errore generato dalla configurazione del processore Live ML."""


def _read_environment_threshold(
    variable_name: str,
    default: float,
) -> float:
    """Legge e valida una soglia probabilistica dall'ambiente."""

    # Recupera il valore della variabile oppure usa il valore predefinito.
    raw_value = os.environ.get(
        variable_name,
        str(default),
    ).strip()

    try:
        # Converte il testo in un numero decimale.
        selected_value = float(raw_value)

    except ValueError as error:
        raise LiveMLProcessorError(f"{variable_name} deve essere un numero decimale.") from error

    # Le soglie probabilistiche devono essere comprese tra zero e uno.
    if not 0.0 <= selected_value <= 1.0:
        raise LiveMLProcessorError(f"{variable_name} deve essere compresa tra 0 e 1.")

    return selected_value


def _default_minimum_confidence() -> float:
    """Legge la confidenza minima configurata."""

    return _read_environment_threshold(
        "MINIMUM_PREDICTION_CONFIDENCE",
        0.60,
    )


def _default_minimum_probability_margin() -> float:
    """Legge il margine probabilistico minimo configurato."""

    return _read_environment_threshold(
        "MINIMUM_PROBABILITY_MARGIN",
        0.10,
    )


@dataclass(frozen=True)
class LiveMLProcessorConfig:
    """Configurazione del processore ML per Live Paper."""

    # Percorso del Model Registry.
    registry_path: Path = Path("models/registry.json")

    # Versione esatta del modello registrato.
    model_version: str = "gradient_boosting_0.1.0"

    # Timeframe operativo del modello.
    timeframe_minutes: int = 15

    # Stati del modello ammessi nel paper trading.
    allowed_model_statuses: tuple[
        str,
        ...,
    ] = (
        "CANDIDATE",
        "APPROVED",
    )

    # Periodo della media mobile veloce.
    ema_fast_period: int = 10

    # Periodo della media mobile lenta.
    ema_slow_period: int = 30

    # Periodo ATR.
    atr_period: int = 14

    # Periodo della volatilità.
    volatility_period: int = 20

    # Confidenza minima richiesta.
    minimum_confidence: float = field(default_factory=(_default_minimum_confidence))

    # Margine minimo tra la prima e la seconda probabilità.
    minimum_probability_margin: float = field(default_factory=(_default_minimum_probability_margin))

    # Segnale usato quando il filtro rifiuta la previsione.
    fallback_signal: str = "NO_TRADE"

    # Moltiplicatore ATR per lo Stop Loss.
    stop_atr_multiplier: float = 1.5

    # Stop Loss percentuale minimo.
    minimum_stop_percentage: float = 0.001

    # Primo Take Profit espresso in R.
    take_profit_1_r: float = 1.0

    # Secondo Take Profit espresso in R.
    take_profit_2_r: float = 2.0

    # Terzo Take Profit espresso in R.
    take_profit_3_r: float = 3.0

    # La release deve rimanere in paper trading.
    paper_trading_only: bool = True


def validate_live_ml_processor_config(
    config: LiveMLProcessorConfig,
) -> None:
    """Verifica la configurazione del processore Live ML."""

    # Il percorso del Model Registry deve essere valorizzato.
    if not str(config.registry_path).strip():
        raise LiveMLProcessorError("Il percorso del Model Registry non può essere vuoto.")

    # La versione del modello deve essere valorizzata.
    if not config.model_version.strip():
        raise LiveMLProcessorError("La versione del modello non può essere vuota.")

    # Il modello corrente è stato sviluppato sul timeframe M15.
    if config.timeframe_minutes != 15:
        raise LiveMLProcessorError("Il modello corrente richiede il timeframe M15.")

    # Deve essere consentito almeno uno stato del modello.
    if not config.allowed_model_statuses:
        raise LiveMLProcessorError("Deve essere ammesso almeno uno stato del modello.")

    # Definisce gli stati supportati.
    supported_statuses = {
        "CANDIDATE",
        "APPROVED",
    }

    # Individua eventuali stati non supportati.
    invalid_statuses = set(config.allowed_model_statuses).difference(supported_statuses)

    # Rifiuta gli stati sconosciuti.
    if invalid_statuses:
        invalid_text = ", ".join(sorted(invalid_statuses))

        raise LiveMLProcessorError(f"Stati modello non supportati: {invalid_text}.")

    # La confidenza minima deve essere compresa tra zero e uno.
    if not (0.0 <= config.minimum_confidence <= 1.0):
        raise LiveMLProcessorError("La confidenza minima deve essere compresa tra 0 e 1.")

    # Il margine minimo deve essere compreso tra zero e uno.
    if not (0.0 <= config.minimum_probability_margin <= 1.0):
        raise LiveMLProcessorError("Il margine minimo deve essere compreso tra 0 e 1.")

    # Il fallback deve restare NO_TRADE.
    if config.fallback_signal != "NO_TRADE":
        raise LiveMLProcessorError("Il segnale fallback deve essere NO_TRADE.")

    # La modalità reale non è consentita.
    if not config.paper_trading_only:
        raise LiveMLProcessorError("Il processore richiede paper_trading_only=true.")


class RegisteredLiveMLProcessor:
    """Esegue inferenza tramite un modello registrato e verificato."""

    def __init__(
        self,
        config: LiveMLProcessorConfig | None = None,
    ) -> None:
        """Inizializza il processore Live ML."""

        # Usa la configurazione predefinita quando non viene specificata.
        self._config = config or LiveMLProcessorConfig()

        # Valida la configurazione selezionata.
        validate_live_ml_processor_config(self._config)

        # Costruisce la configurazione delle feature tecniche.
        self._feature_config = TechnicalFeatureConfig(
            ema_fast_period=(self._config.ema_fast_period),
            ema_slow_period=(self._config.ema_slow_period),
            atr_period=(self._config.atr_period),
            volatility_period=(self._config.volatility_period),
        )

        # Costruisce la configurazione del filtro selettivo.
        self._confidence_config = ConfidenceFilterConfig(
            minimum_confidence=(self._config.minimum_confidence),
            minimum_probability_margin=(self._config.minimum_probability_margin),
            fallback_signal=(self._config.fallback_signal),
        )

        # Costruisce la configurazione dei livelli teorici.
        self._risk_config = RiskLevelConfig(
            stop_atr_multiplier=(self._config.stop_atr_multiplier),
            minimum_stop_percentage=(self._config.minimum_stop_percentage),
            take_profit_1_r=(self._config.take_profit_1_r),
            take_profit_2_r=(self._config.take_profit_2_r),
            take_profit_3_r=(self._config.take_profit_3_r),
        )

        # Costruisce la configurazione dell'inferenza.
        self._replay_config = MLReplayConfig(
            model_version=(self._config.model_version),
            timeframe_minutes=(self._config.timeframe_minutes),
            allowed_model_statuses=(self._config.allowed_model_statuses),
        )

    @property
    def config(
        self,
    ) -> LiveMLProcessorConfig:
        """Restituisce la configurazione corrente."""

        return self._config

    def validate_runtime_files(
        self,
    ) -> None:
        """Verifica la presenza del Model Registry."""

        # Il registry deve essere disponibile.
        if not self._config.registry_path.exists():
            raise LiveMLProcessorError(
                f"Model Registry non trovato: {self._config.registry_path.resolve()}."
            )

        # Il percorso deve rappresentare un file.
        if not self._config.registry_path.is_file():
            raise LiveMLProcessorError("Il percorso del Model Registry non è un file.")

    def process(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """Elabora lo storico e restituisce il segnale corrente."""

        # Verifica il tipo dello storico ricevuto.
        if not isinstance(
            dataframe,
            pd.DataFrame,
        ):
            raise TypeError("Lo storico deve essere un pandas DataFrame.")

        # Lo storico non può essere vuoto.
        if dataframe.empty:
            raise LiveMLProcessorError("Lo storico OHLCV non può essere vuoto.")

        # Verifica il Model Registry.
        self.validate_runtime_files()

        # Esegue il processore già utilizzato dal Replay ML.
        result = process_ml_replay_snapshot(
            dataframe=dataframe,
            registry_path=(self._config.registry_path),
            replay_config=(self._replay_config),
            feature_config=(self._feature_config),
            confidence_config=(self._confidence_config),
            risk_config=(self._risk_config),
        )

        # Crea una copia indipendente del risultato.
        result = result.copy(deep=True)

        # Identifica il contesto Live Paper.
        result["operating_mode"] = "LIVE_PAPER"

        # Conferma che l'esecuzione è esclusivamente simulata.
        result["execution_mode"] = "PAPER_ONLY"

        # Restituisce una sola riga relativa alla candela corrente.
        return result.reset_index(drop=True)

    def __call__(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """Consente di usare l'istanza come Callable."""

        return self.process(dataframe)

    def safe_summary(
        self,
    ) -> dict[str, object]:
        """Restituisce un riepilogo operativo non sensibile."""

        return {
            "processor": ("REGISTERED_LIVE_ML_PROCESSOR"),
            "model_version": (self._config.model_version),
            "registry_path": str(self._config.registry_path),
            "timeframe_minutes": (self._config.timeframe_minutes),
            "allowed_model_statuses": list(self._config.allowed_model_statuses),
            "minimum_confidence": (self._config.minimum_confidence),
            "minimum_probability_margin": (self._config.minimum_probability_margin),
            "fallback_signal": (self._config.fallback_signal),
            "paper_trading_only": (self._config.paper_trading_only),
        }
