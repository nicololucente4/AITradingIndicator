"""Registro locale e verificabile dei modelli Machine Learning."""

# Importa hashlib per calcolare l'impronta SHA-256 dei modelli.
import hashlib

# Importa json per leggere e scrivere il registro locale.
import json

# Importa dataclass per rappresentare una voce del registro.
from dataclasses import asdict, dataclass

# Importa datetime e timezone per timestamp UTC espliciti.
from datetime import datetime, timezone

# Importa Path per gestire i percorsi dei file.
from pathlib import Path


class ModelRegistryError(ValueError):
    """Errore generato durante la gestione del Model Registry."""


@dataclass(frozen=True)
class ModelRegistryEntry:
    """Voce immutabile del registro locale dei modelli."""

    # Identificativo univoco della versione del modello.
    model_version: str

    # Tipo di algoritmo utilizzato.
    model_type: str

    # Stato del modello nel processo di selezione.
    status: str

    # Percorso locale del file serializzato.
    model_path: str

    # Hash SHA-256 del file del modello.
    model_sha256: str

    # Versione del set di feature.
    feature_set_version: str

    # Elenco ordinato delle feature.
    feature_columns: list[str]

    # Tipo di validazione utilizzata.
    validation_type: str

    # Numero di finestre Walk-Forward.
    fold_count: int

    # Macro F1 medio tra le finestre.
    mean_macro_f1: float

    # Macro F1 minimo tra le finestre.
    minimum_macro_f1: float

    # Accuracy media tra le finestre.
    mean_accuracy: float

    # Data e ora UTC di registrazione.
    registered_at_utc: str

    # Indica che il modello è limitato al paper trading.
    paper_trading_only: bool

    def to_dict(self) -> dict[str, object]:
        """Converte la voce in un dizionario serializzabile."""

        # Converte automaticamente tutti i campi.
        return asdict(self)


def calculate_file_sha256(file_path: str | Path) -> str:
    """Calcola l'hash SHA-256 di un file.

    Args:
        file_path: Percorso del file da verificare.

    Returns:
        Hash SHA-256 in formato esadecimale.

    Raises:
        ModelRegistryError: se il file non esiste.
    """

    # Converte il percorso in un oggetto Path.
    selected_path = Path(file_path)

    # Verifica che il file esista.
    if not selected_path.exists():
        raise ModelRegistryError(f"Il file del modello non esiste: {selected_path}.")

    # Verifica che il percorso rappresenti un file.
    if not selected_path.is_file():
        raise ModelRegistryError(f"Il percorso del modello non è un file: {selected_path}.")

    # Crea l'oggetto utilizzato per calcolare l'hash.
    sha256_hash = hashlib.sha256()

    # Legge il file a blocchi per supportare anche modelli voluminosi.
    with selected_path.open("rb") as model_file:
        while True:
            # Legge un blocco da un megabyte.
            file_chunk = model_file.read(1024 * 1024)

            # Interrompe il ciclo alla fine del file.
            if not file_chunk:
                break

            # Aggiorna l'hash con il blocco letto.
            sha256_hash.update(file_chunk)

    # Restituisce l'hash esadecimale.
    return sha256_hash.hexdigest()


def _validate_entry(entry: ModelRegistryEntry) -> None:
    """Verifica la coerenza di una voce del registro."""

    # Definisce gli stati supportati.
    allowed_statuses = {
        "CANDIDATE",
        "APPROVED",
        "REJECTED",
    }

    # La versione del modello non può essere vuota.
    if not entry.model_version.strip():
        raise ModelRegistryError("La versione del modello non può essere vuota.")

    # Il tipo del modello non può essere vuoto.
    if not entry.model_type.strip():
        raise ModelRegistryError("Il tipo del modello non può essere vuoto.")

    # Verifica lo stato del modello.
    if entry.status not in allowed_statuses:
        raise ModelRegistryError(f"Stato del modello non supportato: {entry.status}.")

    # Deve essere presente almeno una feature.
    if not entry.feature_columns:
        raise ModelRegistryError("Il modello deve contenere almeno una feature.")

    # Le feature duplicate non sono ammesse.
    if len(entry.feature_columns) != len(set(entry.feature_columns)):
        raise ModelRegistryError("La voce contiene feature duplicate.")

    # Il numero di finestre deve essere positivo.
    if entry.fold_count <= 0:
        raise ModelRegistryError("Il numero di finestre deve essere maggiore di zero.")

    # Le metriche devono essere comprese tra zero e uno.
    metric_values = {
        "mean_macro_f1": entry.mean_macro_f1,
        "minimum_macro_f1": entry.minimum_macro_f1,
        "mean_accuracy": entry.mean_accuracy,
    }

    for metric_name, metric_value in metric_values.items():
        if not 0.0 <= metric_value <= 1.0:
            raise ModelRegistryError(
                f"La metrica {metric_name} deve essere compresa tra zero e uno."
            )

    # In questa fase sono ammessi solamente modelli paper trading.
    if not entry.paper_trading_only:
        raise ModelRegistryError("Il Model Registry accetta solamente modelli PAPER_ONLY.")

    # Verifica che l'hash abbia la lunghezza prevista per SHA-256.
    if len(entry.model_sha256) != 64:
        raise ModelRegistryError("L'hash SHA-256 del modello non è valido.")


def load_registry(
    registry_path: str | Path,
) -> list[dict[str, object]]:
    """Carica il registro dal file JSON.

    Se il file non esiste, restituisce un registro vuoto.
    """

    # Converte il percorso in un oggetto Path.
    selected_path = Path(registry_path)

    # Un registro non ancora creato viene considerato vuoto.
    if not selected_path.exists():
        return []

    try:
        # Legge e converte il contenuto JSON.
        registry_data = json.loads(
            selected_path.read_text(
                encoding="utf-8",
            )
        )

    except json.JSONDecodeError as error:
        raise ModelRegistryError(f"Il registro JSON non è valido: {error}.") from error

    # Il contenuto principale deve essere una lista.
    if not isinstance(registry_data, list):
        raise ModelRegistryError("Il registro deve contenere una lista di modelli.")

    # Restituisce il contenuto caricato.
    return registry_data


def register_model(
    entry: ModelRegistryEntry,
    registry_path: str | Path,
) -> Path:
    """Registra una nuova versione del modello.

    Args:
        entry: Voce completa da registrare.
        registry_path: Percorso del registro JSON.

    Returns:
        Percorso del registro aggiornato.

    Raises:
        ModelRegistryError: se la versione è già presente.
    """

    # Verifica la voce prima del salvataggio.
    _validate_entry(entry)

    # Converte il percorso del registro.
    selected_path = Path(registry_path)

    # Carica le voci già esistenti.
    existing_entries = load_registry(selected_path)

    # Individua le versioni già registrate.
    existing_versions = {
        str(existing_entry.get("model_version")) for existing_entry in existing_entries
    }

    # Impedisce la sovrascrittura silenziosa di una versione.
    if entry.model_version in existing_versions:
        raise ModelRegistryError(f"La versione {entry.model_version} è già presente nel registro.")

    # Aggiunge la nuova voce.
    existing_entries.append(entry.to_dict())

    # Crea la cartella del registro se necessario.
    selected_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Salva il registro in formato JSON leggibile.
    selected_path.write_text(
        json.dumps(
            existing_entries,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Restituisce il percorso aggiornato.
    return selected_path


def create_registry_entry(
    model_version: str,
    model_type: str,
    status: str,
    model_path: str | Path,
    feature_set_version: str,
    feature_columns: list[str],
    validation_type: str,
    fold_count: int,
    mean_macro_f1: float,
    minimum_macro_f1: float,
    mean_accuracy: float,
) -> ModelRegistryEntry:
    """Crea una voce verificata calcolando automaticamente l'hash."""

    # Converte il percorso del modello.
    selected_model_path = Path(model_path)

    # Calcola l'hash del file serializzato.
    model_sha256 = calculate_file_sha256(selected_model_path)

    # Genera un timestamp UTC esplicito.
    registered_at_utc = datetime.now(timezone.utc).isoformat()

    # Costruisce la voce immutabile.
    entry = ModelRegistryEntry(
        model_version=model_version,
        model_type=model_type,
        status=status,
        model_path=str(selected_model_path),
        model_sha256=model_sha256,
        feature_set_version=feature_set_version,
        feature_columns=feature_columns,
        validation_type=validation_type,
        fold_count=fold_count,
        mean_macro_f1=mean_macro_f1,
        minimum_macro_f1=minimum_macro_f1,
        mean_accuracy=mean_accuracy,
        registered_at_utc=registered_at_utc,
        paper_trading_only=True,
    )

    # Valida la voce prima di restituirla.
    _validate_entry(entry)

    # Restituisce la voce pronta per il salvataggio.
    return entry
