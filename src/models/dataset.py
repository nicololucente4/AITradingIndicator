"""Preparazione sicura del dataset per il Machine Learning."""

# Importa dataclass per rappresentare il dataset ML.
from dataclasses import dataclass

# Importa pandas per selezionare e controllare i dati.
import pandas as pd


class MLDatasetError(ValueError):
    """Errore generato durante la preparazione del dataset ML."""


@dataclass(frozen=True)
class MLDataset:
    """Contiene feature, target e metadati separati."""

    # Matrice contenente esclusivamente le feature del modello.
    features: pd.DataFrame

    # Serie contenente il target LONG, SHORT o NO_TRADE.
    target: pd.Series

    # Metadati temporali esclusi dal training.
    metadata: pd.DataFrame


# Feature esplicitamente autorizzate nella prima versione.
DEFAULT_FEATURE_COLUMNS: tuple[str, ...] = (
    "return_1",
    "ema_fast",
    "ema_slow",
    "ema_distance_pct",
    "true_range",
    "atr",
    "atr_pct",
    "volatility",
)

# Colonne che utilizzano informazioni future e non devono mai
# essere fornite al modello come feature.
FORBIDDEN_FEATURE_COLUMNS: frozenset[str] = frozenset(
    {
        "target",
        "target_upper_barrier",
        "target_lower_barrier",
        "target_bars_to_event",
        "target_available",
        "target_uses_future_data",
    }
)


def _validate_input_columns(
    dataframe: pd.DataFrame,
    feature_columns: tuple[str, ...],
) -> None:
    """Verifica la presenza delle colonne richieste."""

    # Definisce tutte le colonne necessarie.
    required_columns = {
        "timestamp",
        "target",
        "target_available",
        *feature_columns,
    }

    # Individua le colonne mancanti.
    missing_columns = sorted(required_columns.difference(dataframe.columns))

    # Interrompe la preparazione se manca almeno una colonna.
    if missing_columns:
        missing_text = ", ".join(missing_columns)

        raise MLDatasetError(f"Colonne necessarie al dataset ML mancanti: {missing_text}.")


def _validate_feature_selection(
    feature_columns: tuple[str, ...],
) -> None:
    """Impedisce l'utilizzo di informazioni future come feature."""

    # La lista delle feature non può essere vuota.
    if not feature_columns:
        raise MLDatasetError("Deve essere selezionata almeno una feature.")

    # Non sono ammesse feature duplicate.
    if len(feature_columns) != len(set(feature_columns)):
        raise MLDatasetError("La selezione contiene feature duplicate.")

    # Individua eventuali colonne future selezionate per errore.
    forbidden_selected = sorted(set(feature_columns).intersection(FORBIDDEN_FEATURE_COLUMNS))

    # Blocca immediatamente qualsiasi tentativo di leakage.
    if forbidden_selected:
        forbidden_text = ", ".join(forbidden_selected)

        raise MLDatasetError(
            f"Feature vietate perché contengono informazioni future: {forbidden_text}."
        )


def build_ml_dataset(
    dataframe: pd.DataFrame,
    feature_columns: tuple[str, ...] = DEFAULT_FEATURE_COLUMNS,
) -> MLDataset:
    """Prepara feature, target e metadati per il training.

    Vengono eliminate solamente:

    - righe di warm-up con feature mancanti;
    - righe senza target disponibile;
    - righe finali prive dell'orizzonte futuro completo.

    Args:
        dataframe: Dataset contenente feature tecniche e target.
        feature_columns: Feature esplicitamente autorizzate.

    Returns:
        Oggetto MLDataset con feature, target e metadati separati.
    """

    # Verifica che l'input sia un DataFrame.
    if not isinstance(dataframe, pd.DataFrame):
        raise TypeError("Il dato ricevuto deve essere un pandas DataFrame.")

    # Impedisce l'elaborazione di dataset vuoti.
    if dataframe.empty:
        raise MLDatasetError("Il dataset ricevuto è vuoto.")

    # Valida la selezione e la presenza delle colonne.
    _validate_feature_selection(feature_columns)
    _validate_input_columns(
        dataframe=dataframe,
        feature_columns=feature_columns,
    )

    # Crea una copia per non modificare il dataset originale.
    working_dataframe = dataframe.copy(deep=True)

    # Mantiene solamente le righe con target disponibile.
    valid_rows = working_dataframe["target_available"].eq(True)

    # Richiede un target effettivamente valorizzato.
    valid_rows &= working_dataframe["target"].notna()

    # Richiede tutte le feature valorizzate dopo il warm-up.
    valid_rows &= working_dataframe[list(feature_columns)].notna().all(axis=1)

    # Filtra e normalizza l'indice.
    filtered_dataframe = working_dataframe.loc[valid_rows].reset_index(drop=True)

    # Il dataset finale deve contenere almeno una riga valida.
    if filtered_dataframe.empty:
        raise MLDatasetError("Nessuna riga valida disponibile dopo warm-up e controllo del target.")

    # Definisce le sole classi supportate.
    allowed_targets = {
        "LONG",
        "SHORT",
        "NO_TRADE",
    }

    # Individua eventuali target sconosciuti.
    invalid_targets = sorted(set(filtered_dataframe["target"]).difference(allowed_targets))

    # Interrompe la preparazione se esistono classi non supportate.
    if invalid_targets:
        invalid_text = ", ".join(invalid_targets)

        raise MLDatasetError(f"Target ML non supportati: {invalid_text}.")

    # Estrae esclusivamente le feature autorizzate.
    features = filtered_dataframe[list(feature_columns)].copy()

    # Estrae il target separatamente.
    target = filtered_dataframe["target"].copy()
    target.name = "target"

    # Mantiene il timestamp come metadato non utilizzabile dal modello.
    metadata = filtered_dataframe[["timestamp"]].copy()

    # Aggiunge un identificativo progressivo della riga ML.
    metadata.insert(
        loc=0,
        column="sample_id",
        value=range(len(metadata)),
    )

    # Verifica difensiva contro un eventuale leakage residuo.
    leaked_columns = set(features.columns).intersection(FORBIDDEN_FEATURE_COLUMNS)

    if leaked_columns:
        leaked_text = ", ".join(sorted(leaked_columns))

        raise MLDatasetError(f"Rilevato data leakage nelle feature: {leaked_text}.")

    # Restituisce le tre componenti rigorosamente separate.
    return MLDataset(
        features=features,
        target=target,
        metadata=metadata,
    )
