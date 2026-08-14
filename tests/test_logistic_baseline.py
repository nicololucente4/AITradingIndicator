"""Test automatici del modello ML baseline."""

# Importa pandas per creare dataset deterministici.
import pandas as pd

# Importa pytest per verificare gli errori attesi.
import pytest

# Importa la struttura del dataset ML.
from src.models.dataset import MLDataset

# Importa configurazione, errore e training del modello.
from src.models.logistic_baseline import (
    LogisticBaselineConfig,
    LogisticBaselineError,
    train_logistic_baseline,
)


def create_ml_dataset(
    row_count: int = 90,
) -> MLDataset:
    """Crea un dataset ML ordinato con tre classi."""

    # Genera timestamp consecutivi.
    timestamps = pd.date_range(
        start="2025-01-01 00:00:00",
        periods=row_count,
        freq="15min",
        tz="UTC",
    )

    # Costruisce feature deterministiche.
    features = pd.DataFrame(
        {
            "return_1": [((index % 9) - 4) / 1000 for index in range(row_count)],
            "ema_fast": [100.0 + index * 0.01 for index in range(row_count)],
            "ema_slow": [100.0 + index * 0.008 for index in range(row_count)],
            "ema_distance_pct": [((index % 7) - 3) / 1000 for index in range(row_count)],
            "true_range": [1.0 + (index % 5) * 0.1 for index in range(row_count)],
            "atr": [1.0 + (index % 4) * 0.1 for index in range(row_count)],
            "atr_pct": [0.01 + (index % 4) * 0.001 for index in range(row_count)],
            "volatility": [0.01 + (index % 6) * 0.002 for index in range(row_count)],
        }
    )

    # Alterna le tre classi lungo tutta la sequenza.
    targets = [["LONG", "SHORT", "NO_TRADE"][index % 3] for index in range(row_count)]

    # Costruisce la serie target.
    target = pd.Series(
        targets,
        name="target",
    )

    # Costruisce i metadati temporali.
    metadata = pd.DataFrame(
        {
            "sample_id": range(row_count),
            "timestamp": timestamps,
        }
    )

    # Restituisce il dataset completo.
    return MLDataset(
        features=features,
        target=target,
        metadata=metadata,
    )


def test_temporal_split_sizes_are_correct() -> None:
    """Verifica le dimensioni dello split temporale."""

    # Addestra il modello su novanta righe con test al 20%.
    result = train_logistic_baseline(
        dataset=create_ml_dataset(),
        config=LogisticBaselineConfig(
            test_size_percentage=0.20,
        ),
    )

    # Il training deve contenere settantadue righe.
    assert result.training_rows == 72

    # Il test deve contenere diciotto righe.
    assert result.test_rows == 18


def test_test_set_is_after_training_set() -> None:
    """Verifica l'ordine cronologico dello split."""

    # Addestra il modello.
    result = train_logistic_baseline(dataset=create_ml_dataset())

    # Converte i confini temporali in Timestamp.
    training_end = pd.Timestamp(result.training_end_timestamp)
    test_start = pd.Timestamp(result.test_start_timestamp)

    # Il test deve iniziare dopo la fine del training.
    assert test_start > training_end

    # Verifica la dichiarazione salvata nelle metriche.
    assert bool(result.metrics["test_is_chronologically_after_training"])


def test_predictions_contain_all_probability_columns() -> None:
    """Verifica le probabilità LONG, SHORT e NO_TRADE."""

    # Addestra il modello.
    result = train_logistic_baseline(dataset=create_ml_dataset())

    # Definisce le colonne di probabilità attese.
    probability_columns = {
        "probability_long",
        "probability_short",
        "probability_no_trade",
        "prediction_confidence",
    }

    # Verifica che tutte le colonne siano presenti.
    assert probability_columns.issubset(result.predictions.columns)


def test_probabilities_sum_to_one() -> None:
    """Verifica che le probabilità sommino a uno."""

    # Addestra il modello.
    result = train_logistic_baseline(dataset=create_ml_dataset())

    # Somma le probabilità delle tre classi.
    probability_sum = result.predictions[
        [
            "probability_long",
            "probability_short",
            "probability_no_trade",
        ]
    ].sum(axis=1)

    # Verifica ogni riga con tolleranza numerica.
    assert all(value == pytest.approx(1.0) for value in probability_sum)


def test_predictions_keep_test_metadata() -> None:
    """Verifica che sample ID e timestamp restino disponibili."""

    # Addestra il modello.
    result = train_logistic_baseline(dataset=create_ml_dataset())

    # Verifica le colonne dei metadati.
    assert "sample_id" in result.predictions.columns
    assert "timestamp" in result.predictions.columns

    # I timestamp delle predizioni devono essere ordinati.
    assert result.predictions["timestamp"].is_monotonic_increasing


def test_metrics_are_generated() -> None:
    """Verifica la presenza delle metriche principali."""

    # Addestra il modello.
    result = train_logistic_baseline(dataset=create_ml_dataset())

    # Verifica l'accuracy.
    assert "accuracy" in result.metrics

    # Verifica la metrica F1 macro.
    assert "macro_f1" in result.metrics

    # Verifica la matrice di confusione.
    assert "confusion_matrix" in result.metrics

    # Verifica il report dettagliato.
    assert "classification_report" in result.metrics

    # Verifica che non sia stato usato shuffle.
    assert result.metrics["shuffle_used"] is False


def test_scaler_is_inside_pipeline() -> None:
    """Verifica che scaler e classificatore siano nella pipeline."""

    # Addestra il modello.
    result = train_logistic_baseline(dataset=create_ml_dataset())

    # Verifica la presenza dello scaler.
    assert "scaler" in result.model.named_steps

    # Verifica la presenza del classificatore.
    assert "classifier" in result.model.named_steps

    # Verifica la protezione dichiarata nelle metriche.
    assert bool(result.metrics["scaler_fitted_on_training_only"])


def test_unordered_timestamps_are_rejected() -> None:
    """Verifica il rifiuto di metadati non ordinati."""

    # Crea il dataset.
    dataset = create_ml_dataset()

    # Inverte l'ordine dei metadati.
    invalid_metadata = dataset.metadata.iloc[::-1].reset_index(drop=True)

    # Ricostruisce un dataset non valido.
    invalid_dataset = MLDataset(
        features=dataset.features,
        target=dataset.target,
        metadata=invalid_metadata,
    )

    # Verifica che venga generato un errore.
    with pytest.raises(
        LogisticBaselineError,
        match="non sono ordinati",
    ):
        train_logistic_baseline(invalid_dataset)


def test_missing_feature_values_are_rejected() -> None:
    """Verifica il rifiuto di feature con valori mancanti."""

    # Crea il dataset.
    dataset = create_ml_dataset()

    # Copia le feature e inserisce un valore mancante.
    invalid_features = dataset.features.copy()
    invalid_features.loc[5, "atr"] = float("nan")

    # Costruisce il dataset non valido.
    invalid_dataset = MLDataset(
        features=invalid_features,
        target=dataset.target,
        metadata=dataset.metadata,
    )

    # Verifica che venga prodotto l'errore previsto.
    with pytest.raises(
        LogisticBaselineError,
        match="valori mancanti",
    ):
        train_logistic_baseline(invalid_dataset)


def test_dataset_with_too_few_rows_is_rejected() -> None:
    """Verifica il rifiuto di dataset troppo piccoli."""

    # Crea solamente nove righe.
    dataset = create_ml_dataset(row_count=9)

    # Verifica che il dataset venga rifiutato.
    with pytest.raises(
        LogisticBaselineError,
        match="almeno dieci",
    ):
        train_logistic_baseline(dataset)


def test_invalid_test_percentage_is_rejected() -> None:
    """Verifica il rifiuto di una percentuale test non valida."""

    # Crea una configurazione con test pari al 100%.
    invalid_config = LogisticBaselineConfig(
        test_size_percentage=1.0,
    )

    # Verifica che venga prodotto l'errore previsto.
    with pytest.raises(
        LogisticBaselineError,
        match="compresa",
    ):
        train_logistic_baseline(
            dataset=create_ml_dataset(),
            config=invalid_config,
        )
