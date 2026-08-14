"""Test automatici del Model Registry locale."""

import json
from pathlib import Path

import pytest

from src.models.registry import (
    ModelRegistryEntry,
    ModelRegistryError,
    calculate_file_sha256,
    create_registry_entry,
    load_registry,
    register_model,
)


def create_model_file(
    directory_path: Path,
) -> Path:
    """Crea un file modello dimostrativo."""

    model_path = directory_path / "model.joblib"

    model_path.write_bytes(b"demo-model-content")

    return model_path


def create_entry(
    model_path: Path,
    version: str = "model_0.1.0",
) -> ModelRegistryEntry:
    """Crea una voce valida del registro."""

    return create_registry_entry(
        model_version=version,
        model_type="HIST_GRADIENT_BOOSTING",
        status="CANDIDATE",
        model_path=model_path,
        feature_set_version="0.1.0",
        feature_columns=[
            "return_1",
            "ema_fast",
            "ema_slow",
        ],
        validation_type="EXPANDING_WALK_FORWARD",
        fold_count=3,
        mean_macro_f1=0.55,
        minimum_macro_f1=0.40,
        mean_accuracy=0.60,
    )


def test_sha256_is_generated() -> None:
    """Verifica la generazione dell'hash SHA-256."""

    temporary_directory = Path.cwd()

    # Il test utilizza un file temporaneo tramite monkeypatch manuale.
    test_file = temporary_directory / "temporary_hash_test.bin"

    try:
        test_file.write_bytes(b"test-content")

        file_hash = calculate_file_sha256(test_file)

        assert len(file_hash) == 64

        assert file_hash == calculate_file_sha256(test_file)

    finally:
        if test_file.exists():
            test_file.unlink()


def test_missing_model_file_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il rifiuto di un file inesistente."""

    with pytest.raises(
        ModelRegistryError,
        match="non esiste",
    ):
        calculate_file_sha256(tmp_path / "missing.joblib")


def test_new_registry_is_initially_empty(
    tmp_path: Path,
) -> None:
    """Verifica un registro non ancora creato."""

    registry = load_registry(tmp_path / "registry.json")

    assert registry == []


def test_model_is_registered(
    tmp_path: Path,
) -> None:
    """Verifica il salvataggio di una voce."""

    model_path = create_model_file(tmp_path)
    registry_path = tmp_path / "registry.json"

    entry = create_entry(model_path)

    saved_path = register_model(
        entry=entry,
        registry_path=registry_path,
    )

    assert saved_path.exists()

    registry = load_registry(registry_path)

    assert len(registry) == 1
    assert registry[0]["model_version"] == "model_0.1.0"
    assert registry[0]["status"] == "CANDIDATE"
    assert registry[0]["paper_trading_only"] is True


def test_duplicate_version_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il blocco delle versioni duplicate."""

    model_path = create_model_file(tmp_path)
    registry_path = tmp_path / "registry.json"

    entry = create_entry(model_path)

    register_model(
        entry=entry,
        registry_path=registry_path,
    )

    with pytest.raises(
        ModelRegistryError,
        match="già presente",
    ):
        register_model(
            entry=entry,
            registry_path=registry_path,
        )


def test_multiple_versions_are_supported(
    tmp_path: Path,
) -> None:
    """Verifica il salvataggio di versioni differenti."""

    model_path = create_model_file(tmp_path)
    registry_path = tmp_path / "registry.json"

    register_model(
        entry=create_entry(
            model_path,
            version="model_0.1.0",
        ),
        registry_path=registry_path,
    )

    register_model(
        entry=create_entry(
            model_path,
            version="model_0.2.0",
        ),
        registry_path=registry_path,
    )

    registry = load_registry(registry_path)

    assert len(registry) == 2


def test_invalid_status_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il rifiuto di uno stato sconosciuto."""

    model_path = create_model_file(tmp_path)

    valid_entry = create_entry(model_path)

    invalid_entry = ModelRegistryEntry(
        **{
            **valid_entry.to_dict(),
            "status": "LIVE_REAL",
        }
    )

    with pytest.raises(
        ModelRegistryError,
        match="non supportato",
    ):
        register_model(
            entry=invalid_entry,
            registry_path=tmp_path / "registry.json",
        )


def test_invalid_metric_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il rifiuto di metriche fuori intervallo."""

    model_path = create_model_file(tmp_path)

    valid_entry = create_entry(model_path)

    invalid_entry = ModelRegistryEntry(
        **{
            **valid_entry.to_dict(),
            "mean_macro_f1": 1.5,
        }
    )

    with pytest.raises(
        ModelRegistryError,
        match="mean_macro_f1",
    ):
        register_model(
            entry=invalid_entry,
            registry_path=tmp_path / "registry.json",
        )


def test_invalid_json_registry_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il rifiuto di un registro JSON corrotto."""

    registry_path = tmp_path / "registry.json"

    registry_path.write_text(
        "{invalid-json",
        encoding="utf-8",
    )

    with pytest.raises(
        ModelRegistryError,
        match="JSON non è valido",
    ):
        load_registry(registry_path)


def test_registry_contains_valid_json(
    tmp_path: Path,
) -> None:
    """Verifica che il registro prodotto sia JSON valido."""

    model_path = create_model_file(tmp_path)
    registry_path = tmp_path / "registry.json"

    register_model(
        entry=create_entry(model_path),
        registry_path=registry_path,
    )

    registry_data = json.loads(
        registry_path.read_text(
            encoding="utf-8",
        )
    )

    assert isinstance(registry_data, list)
    assert len(registry_data) == 1
