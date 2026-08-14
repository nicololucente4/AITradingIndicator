"""Inferenza sicura tramite modelli registrati localmente."""

# Importa Path per gestire i percorsi del modello e del Registry.
from pathlib import Path

# Importa joblib per caricare il modello serializzato.
import joblib

# Importa NumPy per gestire le probabilità delle classi.
import numpy as np

# Importa pandas per elaborare feature e risultati.
import pandas as pd

# Importa funzioni per leggere il Registry e verificare l'hash.
from src.models.registry import (
    calculate_file_sha256,
    load_registry,
)


class ModelInferenceError(ValueError):
    """Errore generato durante il caricamento o l'inferenza."""


def _find_registry_entry(
    registry_path: str | Path,
    model_version: str,
) -> dict[str, object]:
    """Trova una versione specifica nel Model Registry."""

    # Carica tutte le voci presenti nel Registry.
    registry = load_registry(registry_path)

    # Cerca la versione richiesta.
    matching_entries = [entry for entry in registry if entry.get("model_version") == model_version]

    # Interrompe l'operazione se la versione non è registrata.
    if not matching_entries:
        raise ModelInferenceError(f"La versione {model_version} non è presente nel Model Registry.")

    # Una versione deve comparire una sola volta.
    if len(matching_entries) > 1:
        raise ModelInferenceError(
            f"La versione {model_version} compare più volte nel Model Registry."
        )

    # Restituisce la voce trovata.
    return matching_entries[0]


def _validate_registry_entry(
    entry: dict[str, object],
    allowed_statuses: set[str],
) -> None:
    """Verifica che la voce del Registry sia utilizzabile."""

    # Definisce i campi minimi richiesti.
    required_fields = {
        "model_version",
        "model_type",
        "status",
        "model_path",
        "model_sha256",
        "feature_columns",
        "paper_trading_only",
    }

    # Individua eventuali campi mancanti.
    missing_fields = sorted(required_fields.difference(entry))

    # Interrompe il caricamento se il Registry è incompleto.
    if missing_fields:
        missing_text = ", ".join(missing_fields)

        raise ModelInferenceError(f"Campi mancanti nella voce del Registry: {missing_text}.")

    # Recupera lo stato del modello.
    model_status = str(entry["status"])

    # Il modello deve avere uno degli stati esplicitamente ammessi.
    if model_status not in allowed_statuses:
        raise ModelInferenceError(
            f"Il modello ha stato {model_status}, non consentito per questa inferenza."
        )

    # L'inferenza è limitata ai modelli paper trading.
    if entry["paper_trading_only"] is not True:
        raise ModelInferenceError("Il modello non è dichiarato PAPER_ONLY.")

    # Deve essere registrata almeno una feature.
    feature_columns = entry["feature_columns"]

    if not isinstance(feature_columns, list) or not feature_columns:
        raise ModelInferenceError("La voce del Registry non contiene feature valide.")

    # Le feature duplicate non sono ammesse.
    if len(feature_columns) != len(set(feature_columns)):
        raise ModelInferenceError("La voce del Registry contiene feature duplicate.")


def load_registered_model(
    registry_path: str | Path,
    model_version: str,
    allowed_statuses: set[str] | None = None,
) -> tuple[object, dict[str, object]]:
    """Carica un modello registrato dopo aver verificato il suo hash.

    Args:
        registry_path: Percorso del Model Registry JSON.
        model_version: Versione esatta del modello da caricare.
        allowed_statuses: Stati ammessi per l'inferenza.

    Returns:
        Coppia composta dal modello caricato e dalla voce del Registry.

    Raises:
        ModelInferenceError: se versione, stato o hash non sono validi.
    """

    # In fase di sviluppo sono ammessi modelli candidati e approvati.
    selected_statuses = allowed_statuses or {
        "CANDIDATE",
        "APPROVED",
    }

    # Almeno uno stato deve essere consentito.
    if not selected_statuses:
        raise ModelInferenceError("Deve essere consentito almeno uno stato del modello.")

    # Cerca la versione nel Registry.
    entry = _find_registry_entry(
        registry_path=registry_path,
        model_version=model_version,
    )

    # Verifica contenuto e stato della voce.
    _validate_registry_entry(
        entry=entry,
        allowed_statuses=selected_statuses,
    )

    # Recupera il percorso del file modello.
    model_path = Path(str(entry["model_path"]))

    # Verifica che il modello esista ancora.
    if not model_path.exists():
        raise ModelInferenceError(f"Il file del modello non esiste: {model_path}.")

    # Calcola l'hash attuale del file.
    current_sha256 = calculate_file_sha256(model_path)

    # Recupera l'hash registrato.
    registered_sha256 = str(entry["model_sha256"])

    # Blocca il caricamento se il file è stato modificato.
    if current_sha256 != registered_sha256:
        raise ModelInferenceError(
            "La verifica SHA-256 del modello non è riuscita. "
            "Il file potrebbe essere stato modificato."
        )

    try:
        # Carica il modello solamente dopo la verifica dell'hash.
        model = joblib.load(model_path)

    except Exception as error:
        # Converte gli errori di deserializzazione in un errore leggibile.
        raise ModelInferenceError(f"Impossibile caricare il modello: {error}.") from error

    # Il modello deve supportare previsione e probabilità.
    if not hasattr(model, "predict"):
        raise ModelInferenceError("Il modello caricato non supporta predict.")

    if not hasattr(model, "predict_proba"):
        raise ModelInferenceError("Il modello caricato non supporta predict_proba.")

    # Restituisce modello e informazioni registrate.
    return model, entry


def _prepare_features(
    features: pd.DataFrame,
    expected_columns: list[str],
) -> pd.DataFrame:
    """Verifica e ordina le feature secondo il Registry."""

    # L'input deve essere un DataFrame.
    if not isinstance(features, pd.DataFrame):
        raise TypeError("Le feature devono essere un pandas DataFrame.")

    # Il dataset non può essere vuoto.
    if features.empty:
        raise ModelInferenceError("Il dataset delle feature è vuoto.")

    # Individua le feature richieste ma mancanti.
    missing_columns = sorted(set(expected_columns).difference(features.columns))

    if missing_columns:
        missing_text = ", ".join(missing_columns)

        raise ModelInferenceError(f"Feature richieste dal modello mancanti: {missing_text}.")

    # Seleziona esclusivamente le feature registrate
    # e le riordina nella sequenza corretta.
    prepared_features = features[expected_columns].copy()

    # Non sono ammessi valori mancanti.
    if prepared_features.isna().any().any():
        raise ModelInferenceError("Le feature di inferenza contengono valori mancanti.")

    # Tutte le feature devono essere numeriche.
    non_numeric_columns = [
        column
        for column in prepared_features.columns
        if not pd.api.types.is_numeric_dtype(prepared_features[column])
    ]

    if non_numeric_columns:
        non_numeric_text = ", ".join(non_numeric_columns)

        raise ModelInferenceError(f"Feature non numeriche rilevate: {non_numeric_text}.")

    # Restituisce la matrice pronta per il modello.
    return prepared_features


def run_registered_inference(
    features: pd.DataFrame,
    registry_path: str | Path,
    model_version: str,
    allowed_statuses: set[str] | None = None,
) -> pd.DataFrame:
    """Genera predizioni tramite un modello verificato nel Registry.

    Il modello viene solamente caricato e utilizzato. Non viene eseguito
    alcun fit o aggiornamento durante l'inferenza.

    Args:
        features: Matrice contenente le feature correnti.
        registry_path: Percorso del Model Registry.
        model_version: Versione esatta del modello.
        allowed_statuses: Stati ammessi per l'utilizzo.

    Returns:
        DataFrame con classe prevista, probabilità e informazioni audit.
    """

    # Carica e verifica il modello.
    model, registry_entry = load_registered_model(
        registry_path=registry_path,
        model_version=model_version,
        allowed_statuses=allowed_statuses,
    )

    # Recupera le feature nell'ordine registrato.
    expected_columns = [str(column) for column in registry_entry["feature_columns"]]

    # Prepara la matrice di inferenza.
    prepared_features = _prepare_features(
        features=features,
        expected_columns=expected_columns,
    )

    # Genera le classi previste.
    predicted_target = model.predict(prepared_features)

    # Genera le probabilità delle classi.
    predicted_probabilities = model.predict_proba(prepared_features)

    # Recupera l'ordine delle classi del modello.
    model_classes = [str(class_name) for class_name in model.classes_]

    # Crea il DataFrame delle predizioni.
    result = pd.DataFrame(
        {
            "predicted_target": predicted_target,
        },
        index=features.index,
    )

    # Aggiunge una probabilità per ogni classe prevista dal progetto.
    for class_name in [
        "LONG",
        "SHORT",
        "NO_TRADE",
    ]:
        probability_column = f"probability_{class_name.lower()}"

        # Una classe assente dal modello riceve probabilità zero.
        if class_name not in model_classes:
            result[probability_column] = 0.0
            continue

        # Individua la posizione della classe.
        class_index = int(np.where(np.asarray(model_classes) == class_name)[0][0])

        # Salva la probabilità.
        result[probability_column] = predicted_probabilities[:, class_index]

    # Calcola la confidenza massima.
    result["prediction_confidence"] = result[
        [
            "probability_long",
            "probability_short",
            "probability_no_trade",
        ]
    ].max(axis=1)

    # Aggiunge informazioni di audit.
    result["model_version"] = str(registry_entry["model_version"])

    result["model_type"] = str(registry_entry["model_type"])

    result["model_status"] = str(registry_entry["status"])

    result["model_sha256"] = str(registry_entry["model_sha256"])

    result["inference_mode"] = "PAPER_ONLY"

    # Restituisce le predizioni senza modificare le feature.
    return result.reset_index(drop=True)
