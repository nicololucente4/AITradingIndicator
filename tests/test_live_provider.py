"""Test automatici del provider dati Live Paper."""

from pathlib import Path

import pandas as pd
import pytest

from src.data.live_provider import (
    FilePollingDataProvider,
    LiveDataProvider,
    LiveDataProviderError,
)


def create_csv(
    file_path: Path,
    candle_count: int = 4,
) -> None:
    """Crea un CSV M15 deterministico."""

    timestamps = pd.date_range(
        start="2026-08-14 10:00:00",
        periods=candle_count,
        freq="15min",
        tz="UTC",
    )

    dataframe = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0 + index for index in range(candle_count)],
            "high": [102.0 + index for index in range(candle_count)],
            "low": [99.0 + index for index in range(candle_count)],
            "close": [101.0 + index for index in range(candle_count)],
            "volume": [100 + index for index in range(candle_count)],
        }
    )

    dataframe.to_csv(
        file_path,
        index=False,
    )


def test_provider_implements_live_interface(
    tmp_path: Path,
) -> None:
    """Verifica l'implementazione dell'interfaccia astratta."""

    csv_path = tmp_path / "market.csv"
    create_csv(csv_path)

    provider = FilePollingDataProvider(
        file_path=csv_path,
        timeframe_minutes=15,
    )

    assert isinstance(
        provider,
        LiveDataProvider,
    )


def test_only_closed_candles_are_returned(
    tmp_path: Path,
) -> None:
    """Verifica che la candela aperta non venga restituita."""

    csv_path = tmp_path / "market.csv"
    create_csv(csv_path)

    provider = FilePollingDataProvider(
        file_path=csv_path,
        timeframe_minutes=15,
    )

    # Alle 10:37 sono chiuse le candele delle 10:00 e 10:15.
    # La candela delle 10:30 è ancora aperta fino alle 10:45.
    result = provider.poll(
        pd.Timestamp(
            "2026-08-14 10:37:00",
            tz="UTC",
        )
    )

    assert len(result.new_closed_bars) == 2

    assert result.new_closed_bars.iloc[-1]["timestamp"] == pd.Timestamp(
        "2026-08-14 10:15:00",
        tz="UTC",
    )


def test_closed_candle_is_available_at_exact_close(
    tmp_path: Path,
) -> None:
    """Verifica la disponibilità esatta alla chiusura."""

    csv_path = tmp_path / "market.csv"
    create_csv(csv_path)

    provider = FilePollingDataProvider(
        file_path=csv_path,
        timeframe_minutes=15,
    )

    result = provider.poll(
        pd.Timestamp(
            "2026-08-14 10:45:00",
            tz="UTC",
        )
    )

    # Alle 10:45 è appena terminata anche la candela delle 10:30.
    assert len(result.new_closed_bars) == 3


def test_same_candle_is_not_emitted_twice(
    tmp_path: Path,
) -> None:
    """Verifica che il provider non ripeta i dati già emessi."""

    csv_path = tmp_path / "market.csv"
    create_csv(csv_path)

    provider = FilePollingDataProvider(
        file_path=csv_path,
        timeframe_minutes=15,
    )

    first_result = provider.poll(
        pd.Timestamp(
            "2026-08-14 10:30:00",
            tz="UTC",
        )
    )

    second_result = provider.poll(
        pd.Timestamp(
            "2026-08-14 10:35:00",
            tz="UTC",
        )
    )

    assert len(first_result.new_closed_bars) == 2
    assert second_result.new_closed_bars.empty


def test_new_candle_is_emitted_on_next_poll(
    tmp_path: Path,
) -> None:
    """Verifica l'emissione di una nuova candela chiusa."""

    csv_path = tmp_path / "market.csv"
    create_csv(csv_path)

    provider = FilePollingDataProvider(
        file_path=csv_path,
        timeframe_minutes=15,
    )

    provider.poll(
        pd.Timestamp(
            "2026-08-14 10:30:00",
            tz="UTC",
        )
    )

    next_result = provider.poll(
        pd.Timestamp(
            "2026-08-14 10:45:00",
            tz="UTC",
        )
    )

    assert len(next_result.new_closed_bars) == 1

    assert next_result.new_closed_bars.loc[
        0,
        "timestamp",
    ] == pd.Timestamp(
        "2026-08-14 10:30:00",
        tz="UTC",
    )


def test_reset_replays_closed_candles(
    tmp_path: Path,
) -> None:
    """Verifica l'azzeramento dello stato locale."""

    csv_path = tmp_path / "market.csv"
    create_csv(csv_path)

    provider = FilePollingDataProvider(
        file_path=csv_path,
        timeframe_minutes=15,
    )

    selected_time = pd.Timestamp(
        "2026-08-14 10:30:00",
        tz="UTC",
    )

    first_result = provider.poll(selected_time)

    provider.reset()

    second_result = provider.poll(selected_time)

    assert len(first_result.new_closed_bars) == 2
    assert len(second_result.new_closed_bars) == 2


def test_timezone_naive_poll_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il rifiuto di un timestamp senza timezone."""

    csv_path = tmp_path / "market.csv"
    create_csv(csv_path)

    provider = FilePollingDataProvider(
        file_path=csv_path,
        timeframe_minutes=15,
    )

    with pytest.raises(
        LiveDataProviderError,
        match="timezone",
    ):
        provider.poll(pd.Timestamp("2026-08-14 10:30:00"))


def test_invalid_timeframe_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il rifiuto di un timeframe non positivo."""

    csv_path = tmp_path / "market.csv"
    create_csv(csv_path)

    with pytest.raises(
        LiveDataProviderError,
        match="timeframe",
    ):
        FilePollingDataProvider(
            file_path=csv_path,
            timeframe_minutes=0,
        )
