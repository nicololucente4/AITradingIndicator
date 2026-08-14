"""Test automatici della preparazione del dataset ML."""

# Importa pandas per creare dataset deterministici.
import pandas as pd

# Importa pytest per verificare gli errori attesi.
import pytest

# Importa preparatore, configurazione e protezioni anti-leakage.
from src.models.dataset import (
    DEFAULT_FEATURE_COLUMNS,
    MLDatasetError,
    build_ml_dataset,
)


def create_labeled_dataframe() -> pd.DataFrame:
    """Crea un dataset già arricchito con feature e target."""

    # Genera sei timestamp consecutivi.
    timestamps = pd.date_range(
        start="2026-08-13 08:00:00",
        periods=6,
        freq="15min",
        tz="UTC",
    )

    # Costruisce un dataset con warm-up e righe finali escluse.
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "return_1": [
                float("nan"),
                0.001,
                0.002,
                -0.001,
                0.001,
                -0.002,
            ],
            "ema_fast": [
                float("nan"),
                100.1,
                100.2,
                100.1,
                100.3,
                100.0,
            ],
            "ema_slow": [
                float("nan"),
                100.0,
                100.1,
                100.2,
                100.2,
                100.1,
            ],
            "ema_distance_pct": [
                float("nan"),
                0.001,
                0.001,
                -0.001,
                0.001,
                -0.001,
            ],
            "true_range": [
                1.0,
                1.0,
                1.1,
                1.2,
                1.1,
                1.2,
            ],
            "atr": [
                float("nan"),
                1.0,
                1.0,
                1.1,
                1.1,
                1.2,
            ],
            "atr_pct": [
                float("nan"),
                0.01,
                0.01,
                0.011,
                0.011,
                0.012,
            ],
            "volatility": [
                float("nan"),
                0.01,
                0.02,
                0.02,
                0.01,
                0.03,
            ],
            "target": [
                None,
                "LONG",
                "SHORT",
                "NO_TRADE",
                None,
                None,
            ],
            "target_upper_barrier": [
                None,
                101.0,
                101.2,
                101.1,
                None,
                None,
            ],
            "target_lower_barrier": [
                None,
                99.0,
                99.2,
                98.9,
                None,
                None,
            ],
            "target_bars_to_event": [
                None,
                2,
                1,
                None,
                None,
                None,
            ],
            "target_available": [
                False,
                True,
                True,
                True,
                False,
                False,
            ],
            "target_uses_future_data": [True] * 6,
        }
    )


def test_feature_target_and_metadata_are_separated() -> None:
    """Verifica la separazione delle componenti ML."""

    # Prepara il dataset.
    dataset = build_ml_dataset(create_labeled_dataframe())

    # Verifica le colonne delle feature.
    assert tuple(dataset.features.columns) == (DEFAULT_FEATURE_COLUMNS)

    # Il target non deve apparire nelle feature.
    assert "target" not in dataset.features.columns

    # Il timestamp deve restare solamente nei metadati.
    assert "timestamp" not in dataset.features.columns
    assert "timestamp" in dataset.metadata.columns


def test_warmup_and_unavailable_targets_are_removed() -> None:
    """Verifica l'eliminazione controllata delle righe non valide."""

    # Prepara il dataset.
    dataset = build_ml_dataset(create_labeled_dataframe())

    # Devono restare solamente LONG, SHORT e NO_TRADE validi.
    assert len(dataset.features) == 3
    assert list(dataset.target) == [
        "LONG",
        "SHORT",
        "NO_TRADE",
    ]


def test_future_based_columns_are_not_features() -> None:
    """Verifica che le colonne future non entrino nel modello."""

    # Prepara il dataset.
    dataset = build_ml_dataset(create_labeled_dataframe())

    # Definisce le colonne che causerebbero leakage.
    forbidden_columns = {
        "target_upper_barrier",
        "target_lower_barrier",
        "target_bars_to_event",
        "target_available",
        "target_uses_future_data",
    }

    # Nessuna colonna futura deve apparire nelle feature.
    assert forbidden_columns.isdisjoint(dataset.features.columns)


def test_forbidden_feature_selection_is_rejected() -> None:
    """Verifica il blocco di una feature basata sul futuro."""

    # Crea una selezione intenzionalmente pericolosa.
    invalid_features = (
        "return_1",
        "target_bars_to_event",
    )

    # Verifica che la selezione venga rifiutata.
    with pytest.raises(
        MLDatasetError,
        match="informazioni future",
    ):
        build_ml_dataset(
            dataframe=create_labeled_dataframe(),
            feature_columns=invalid_features,
        )


def test_original_dataframe_is_not_modified() -> None:
    """Verifica che la preparazione non modifichi l'input."""

    # Crea il dataset originale.
    dataframe = create_labeled_dataframe()

    # Crea una copia completa.
    original_dataframe = dataframe.copy(deep=True)

    # Prepara il dataset ML.
    build_ml_dataset(dataframe)

    # Verifica che l'input sia rimasto invariato.
    pd.testing.assert_frame_equal(
        dataframe,
        original_dataframe,
    )


def test_unsupported_target_is_rejected() -> None:
    """Verifica il rifiuto di una classe target sconosciuta."""

    # Crea il dataset.
    dataframe = create_labeled_dataframe()

    # Inserisce una classe non supportata in una riga valida.
    dataframe.loc[1, "target"] = "BUY_NOW"

    # Verifica che venga prodotto un errore.
    with pytest.raises(
        MLDatasetError,
        match="non supportati",
    ):
        build_ml_dataset(dataframe)


def test_missing_feature_column_is_rejected() -> None:
    """Verifica il rifiuto di una feature mancante."""

    # Crea il dataset senza ATR percentuale.
    dataframe = create_labeled_dataframe().drop(columns=["atr_pct"])

    # Verifica che venga segnalata la colonna mancante.
    with pytest.raises(
        MLDatasetError,
        match="atr_pct",
    ):
        build_ml_dataset(dataframe)


def test_sample_ids_are_progressive() -> None:
    """Verifica la creazione degli identificativi ML."""

    # Prepara il dataset.
    dataset = build_ml_dataset(create_labeled_dataframe())

    # Gli identificativi devono essere progressivi.
    assert list(dataset.metadata["sample_id"]) == [
        0,
        1,
        2,
    ]
