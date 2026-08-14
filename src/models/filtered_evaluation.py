"""Valutazione delle predizioni ML dopo il filtro di confidenza."""

from dataclasses import asdict, dataclass

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)


class FilteredEvaluationError(ValueError):
    """Errore generato da predizioni filtrate non valide."""


@dataclass(frozen=True)
class FilteredEvaluationReport:
    """Metriche delle predizioni prima e dopo il filtro."""

    # Numero complessivo di predizioni analizzate.
    total_predictions: int

    # Numero di segnali LONG o SHORT mantenuti dopo il filtro.
    accepted_directional_signals: int

    # Percentuale di segnali direzionali sul totale.
    directional_coverage_percentage: float

    # Accuracy delle predizioni originali.
    raw_accuracy: float

    # Macro F1 delle predizioni originali.
    raw_macro_f1: float

    # Accuracy dopo la sostituzione dei segnali deboli con NO_TRADE.
    filtered_accuracy: float

    # Macro F1 dopo il filtro.
    filtered_macro_f1: float

    # Accuracy calcolata esclusivamente sui segnali LONG e SHORT accettati.
    accepted_directional_accuracy: float | None

    # Precisione dei segnali LONG accettati.
    long_precision: float

    # Recall della classe LONG.
    long_recall: float

    # F1 della classe LONG.
    long_f1: float

    # Precisione dei segnali SHORT accettati.
    short_precision: float

    # Recall della classe SHORT.
    short_recall: float

    # F1 della classe SHORT.
    short_f1: float

    # Matrice di confusione prima del filtro.
    raw_confusion_matrix: list[list[int]]

    # Matrice di confusione dopo il filtro.
    filtered_confusion_matrix: list[list[int]]

    # Ordine delle classi utilizzato nelle matrici.
    confusion_matrix_labels: list[str]

    def to_dict(self) -> dict[str, object]:
        """Converte il report in un dizionario serializzabile."""

        return asdict(self)


def _validate_predictions(predictions: pd.DataFrame) -> None:
    """Verifica struttura e contenuto delle predizioni filtrate."""

    # L'input deve essere un DataFrame.
    if not isinstance(predictions, pd.DataFrame):
        raise TypeError("Le predizioni devono essere un pandas DataFrame.")

    # Il dataset non può essere vuoto.
    if predictions.empty:
        raise FilteredEvaluationError("Il dataset delle predizioni filtrate è vuoto.")

    # Definisce le colonne necessarie.
    required_columns = {
        "actual_target",
        "raw_prediction",
        "filtered_signal",
        "prediction_accepted",
    }

    # Individua eventuali colonne mancanti.
    missing_columns = sorted(required_columns.difference(predictions.columns))

    if missing_columns:
        missing_text = ", ".join(missing_columns)

        raise FilteredEvaluationError(
            f"Colonne necessarie alla valutazione mancanti: {missing_text}."
        )

    # Le colonne principali non possono contenere valori mancanti.
    required_values = [
        "actual_target",
        "raw_prediction",
        "filtered_signal",
        "prediction_accepted",
    ]

    if predictions[required_values].isna().any().any():
        raise FilteredEvaluationError("Le predizioni contengono valori mancanti.")

    # Definisce le classi ammesse.
    allowed_classes = {
        "LONG",
        "SHORT",
        "NO_TRADE",
    }

    # Controlla target reale, previsione originale e segnale filtrato.
    for column in [
        "actual_target",
        "raw_prediction",
        "filtered_signal",
    ]:
        invalid_classes = sorted(set(predictions[column]).difference(allowed_classes))

        if invalid_classes:
            invalid_text = ", ".join(invalid_classes)

            raise FilteredEvaluationError(
                f"Classi non supportate nella colonna {column}: {invalid_text}."
            )


def evaluate_filtered_predictions(
    predictions: pd.DataFrame,
) -> FilteredEvaluationReport:
    """Valuta le predizioni originali e quelle filtrate.

    Args:
        predictions: Dataset contenente target reale, previsione originale
            e segnale risultante dal filtro di confidenza.

    Returns:
        Report completo delle prestazioni prima e dopo il filtro.
    """

    # Valida il dataset prima dei calcoli.
    _validate_predictions(predictions)

    # Definisce l'ordine fisso delle classi.
    class_order = [
        "LONG",
        "SHORT",
        "NO_TRADE",
    ]

    # Estrae target reale e predizioni.
    actual_target = predictions["actual_target"]
    raw_prediction = predictions["raw_prediction"]
    filtered_signal = predictions["filtered_signal"]

    # Identifica i segnali LONG o SHORT rimasti dopo il filtro.
    accepted_directional_mask = filtered_signal.isin(
        {
            "LONG",
            "SHORT",
        }
    )

    # Conta i segnali direzionali accettati.
    accepted_directional_signals = int(accepted_directional_mask.sum())

    # Calcola la copertura direzionale.
    directional_coverage_percentage = accepted_directional_signals / len(predictions) * 100.0

    # Calcola accuracy e Macro F1 delle predizioni originali.
    raw_accuracy = float(
        accuracy_score(
            actual_target,
            raw_prediction,
        )
    )

    raw_macro_f1 = float(
        f1_score(
            actual_target,
            raw_prediction,
            labels=class_order,
            average="macro",
            zero_division=0,
        )
    )

    # Calcola accuracy e Macro F1 dopo il filtro.
    filtered_accuracy = float(
        accuracy_score(
            actual_target,
            filtered_signal,
        )
    )

    filtered_macro_f1 = float(
        f1_score(
            actual_target,
            filtered_signal,
            labels=class_order,
            average="macro",
            zero_division=0,
        )
    )

    # Calcola la precisione direzionale solo sui segnali accettati.
    if accepted_directional_signals > 0:
        accepted_directional_accuracy = float(
            accuracy_score(
                actual_target.loc[accepted_directional_mask],
                filtered_signal.loc[accepted_directional_mask],
            )
        )
    else:
        accepted_directional_accuracy = None

    # Calcola le metriche delle singole classi direzionali.
    long_precision = float(
        precision_score(
            actual_target,
            filtered_signal,
            labels=["LONG"],
            average="macro",
            zero_division=0,
        )
    )

    long_recall = float(
        recall_score(
            actual_target,
            filtered_signal,
            labels=["LONG"],
            average="macro",
            zero_division=0,
        )
    )

    long_f1 = float(
        f1_score(
            actual_target,
            filtered_signal,
            labels=["LONG"],
            average="macro",
            zero_division=0,
        )
    )

    short_precision = float(
        precision_score(
            actual_target,
            filtered_signal,
            labels=["SHORT"],
            average="macro",
            zero_division=0,
        )
    )

    short_recall = float(
        recall_score(
            actual_target,
            filtered_signal,
            labels=["SHORT"],
            average="macro",
            zero_division=0,
        )
    )

    short_f1 = float(
        f1_score(
            actual_target,
            filtered_signal,
            labels=["SHORT"],
            average="macro",
            zero_division=0,
        )
    )

    # Costruisce le matrici di confusione.
    raw_confusion_matrix = confusion_matrix(
        actual_target,
        raw_prediction,
        labels=class_order,
    ).tolist()

    filtered_confusion_matrix = confusion_matrix(
        actual_target,
        filtered_signal,
        labels=class_order,
    ).tolist()

    # Genera anche il report dettagliato per controllo interno.
    classification_report(
        actual_target,
        filtered_signal,
        labels=class_order,
        output_dict=True,
        zero_division=0,
    )

    # Restituisce le metriche arrotondate.
    return FilteredEvaluationReport(
        total_predictions=len(predictions),
        accepted_directional_signals=accepted_directional_signals,
        directional_coverage_percentage=round(
            directional_coverage_percentage,
            6,
        ),
        raw_accuracy=round(raw_accuracy, 6),
        raw_macro_f1=round(raw_macro_f1, 6),
        filtered_accuracy=round(filtered_accuracy, 6),
        filtered_macro_f1=round(filtered_macro_f1, 6),
        accepted_directional_accuracy=(
            None
            if accepted_directional_accuracy is None
            else round(
                accepted_directional_accuracy,
                6,
            )
        ),
        long_precision=round(long_precision, 6),
        long_recall=round(long_recall, 6),
        long_f1=round(long_f1, 6),
        short_precision=round(short_precision, 6),
        short_recall=round(short_recall, 6),
        short_f1=round(short_f1, 6),
        raw_confusion_matrix=raw_confusion_matrix,
        filtered_confusion_matrix=filtered_confusion_matrix,
        confusion_matrix_labels=class_order,
    )
