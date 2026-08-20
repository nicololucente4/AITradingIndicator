"""Test automatici del processore ML per Live Paper."""

# Importa Path per gestire percorsi temporanei.
from pathlib import Path

# Importa pandas per costruire lo storico OHLCV.
import pandas as pd

# Importa pytest per verificare gli errori attesi.
import pytest

# Importa il processore e la relativa configurazione.
from src.monitoring.live_processor import (
    LiveMLProcessorConfig,
    LiveMLProcessorError,
    RegisteredLiveMLProcessor,
    validate_live_ml_processor_config,
)


def create_history(
    row_count: int = 80,
) -> pd.DataFrame:
    """Crea uno storico M15 deterministico."""

    # Genera timestamp M15 consecutivi.
    timestamps = pd.date_range(
        start="2026-08-01 00:00:00",
        periods=row_count,
        freq="15min",
        tz="UTC",
    )

    # Genera prezzi progressivi.
    close_prices = [1.1000 + index * 0.0001 for index in range(row_count)]

    # Il primo Open precede il primo Close.
    open_prices = [
        close_prices[0] - 0.0001,
        *close_prices[:-1],
    ]

    # Costruisce il dataset OHLCV.
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_prices,
            "high": [
                max(
                    open_price,
                    close_price,
                )
                + 0.0003
                for (
                    open_price,
                    close_price,
                ) in zip(
                    open_prices,
                    close_prices,
                    strict=True,
                )
            ],
            "low": [
                min(
                    open_price,
                    close_price,
                )
                - 0.0003
                for (
                    open_price,
                    close_price,
                ) in zip(
                    open_prices,
                    close_prices,
                    strict=True,
                )
            ],
            "close": close_prices,
            "volume": [100 + index for index in range(row_count)],
        }
    )


def test_default_configuration_is_paper_only() -> None:
    """Verifica i valori predefiniti sicuri."""

    # Crea il processore con la configurazione predefinita.
    processor = RegisteredLiveMLProcessor()

    # Verifica modello e modalità.
    assert processor.config.model_version == "gradient_boosting_0.1.0"

    assert processor.config.paper_trading_only is True


def test_non_m15_timeframe_is_rejected() -> None:
    """Verifica il blocco di timeframe incompatibili col modello."""

    # Il modello corrente è stato preparato su M15.
    with pytest.raises(
        LiveMLProcessorError,
        match="M15",
    ):
        validate_live_ml_processor_config(
            LiveMLProcessorConfig(
                timeframe_minutes=5,
            )
        )


def test_real_mode_is_rejected() -> None:
    """Verifica il blocco della modalità non simulata."""

    with pytest.raises(
        LiveMLProcessorError,
        match="paper_trading_only",
    ):
        validate_live_ml_processor_config(
            LiveMLProcessorConfig(
                paper_trading_only=False,
            )
        )


def test_empty_model_version_is_rejected() -> None:
    """Verifica il rifiuto di una versione vuota."""

    with pytest.raises(
        LiveMLProcessorError,
        match="versione",
    ):
        validate_live_ml_processor_config(
            LiveMLProcessorConfig(
                model_version="",
            )
        )


def test_unsupported_model_status_is_rejected() -> None:
    """Verifica il rifiuto di stati modello non supportati."""

    with pytest.raises(
        LiveMLProcessorError,
        match="non supportati",
    ):
        validate_live_ml_processor_config(
            LiveMLProcessorConfig(
                allowed_model_statuses=("REJECTED",),
            )
        )


def test_missing_registry_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il rifiuto di un registry assente."""

    # Configura un percorso inesistente.
    processor = RegisteredLiveMLProcessor(
        LiveMLProcessorConfig(
            registry_path=(tmp_path / "missing_registry.json"),
        )
    )

    # Il controllo deve interrompersi.
    with pytest.raises(
        LiveMLProcessorError,
        match="non trovato",
    ):
        processor.validate_runtime_files()


def test_safe_summary_contains_no_sensitive_data() -> None:
    """Verifica il riepilogo operativo."""

    # Crea il processore.
    processor = RegisteredLiveMLProcessor()

    # Genera il riepilogo.
    summary = processor.safe_summary()

    # Verifica i valori principali.
    assert summary["processor"] == "REGISTERED_LIVE_ML_PROCESSOR"

    assert summary["model_version"] == "gradient_boosting_0.1.0"

    assert summary["paper_trading_only"] is True


def test_processor_rejects_empty_history() -> None:
    """Verifica il rifiuto di uno storico vuoto."""

    # Crea il processore.
    processor = RegisteredLiveMLProcessor()

    # Il processore non deve elaborare un DataFrame vuoto.
    with pytest.raises(
        LiveMLProcessorError,
        match="non può essere vuoto",
    ):
        processor.process(pd.DataFrame())


def test_registered_model_generates_live_paper_signal() -> None:
    """Verifica l'inferenza tramite il modello registrato reale."""

    # Crea il processore.
    processor = RegisteredLiveMLProcessor()

    # Elabora uno storico sufficiente al warm-up.
    result = processor.process(create_history())

    # Deve essere restituita una sola riga.
    assert len(result) == 1

    # Il segnale deve appartenere alle classi previste.
    assert result.loc[
        0,
        "signal",
    ] in {
        "LONG",
        "SHORT",
        "NO_TRADE",
    }

    # Il segnale deve essere confermato.
    assert (
        result.loc[
            0,
            "signal_status",
        ]
        == "CONFIRMED"
    )

    # Verifica sorgente e versione.
    assert (
        result.loc[
            0,
            "signal_source",
        ]
        == "REGISTERED_ML_MODEL"
    )

    assert (
        result.loc[
            0,
            "model_version",
        ]
        == "gradient_boosting_0.1.0"
    )

    # La modalità deve essere esclusivamente simulata.
    assert (
        result.loc[
            0,
            "operating_mode",
        ]
        == "LIVE_PAPER"
    )

    assert (
        result.loc[
            0,
            "execution_mode",
        ]
        == "PAPER_ONLY"
    )
