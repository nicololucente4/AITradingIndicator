"""Test API dei timeframe M15, H1, H4 e D1."""

# Importa Path per gestire i file temporanei.
from pathlib import Path

# Importa pandas per creare il dataset OHLCV.
import pandas as pd

# Importa il client HTTP di test FastAPI.
from fastapi.testclient import TestClient

# Importa configurazione e factory dell'API.
from src.api.app import APIConfig, create_app


def create_complete_m15_csv(
    file_path: Path,
) -> None:
    """Crea ventiquattro ore complete di candele M15."""

    # Novantasei candele M15 equivalgono a un giorno completo.
    candle_count = 96

    # Genera timestamp allineati alla mezzanotte UTC.
    timestamps = pd.date_range(
        start="2026-08-14 00:00:00",
        periods=candle_count,
        freq="15min",
        tz="UTC",
    )

    # Genera prezzi progressivi.
    open_prices = [1.10000 + index * 0.00001 for index in range(candle_count)]

    # Costruisce il dataset OHLCV valido.
    dataframe = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_prices,
            "high": [price + 0.00020 for price in open_prices],
            "low": [price - 0.00020 for price in open_prices],
            "close": [price + 0.00005 for price in open_prices],
            "volume": [100 + index for index in range(candle_count)],
        }
    )

    # Salva il dataset.
    dataframe.to_csv(
        file_path,
        index=False,
    )


def create_timeframe_client(
    tmp_path: Path,
) -> TestClient:
    """Crea un client FastAPI isolato."""

    # Crea il dataset temporaneo.
    csv_path = tmp_path / "market.csv"

    create_complete_m15_csv(csv_path)

    # Configura l'applicazione.
    application = create_app(
        APIConfig(
            market_data_path=str(csv_path),
            database_path=str(tmp_path / "missing.db"),
            symbol="EURUSD",
            timeframe="M15",
            source_timeframe_minutes=15,
            paper_trading_only=True,
        )
    )

    # Restituisce il client.
    return TestClient(application)


def test_timeframes_endpoint_lists_availability(
    tmp_path: Path,
) -> None:
    """Verifica timeframe disponibili e disabilitati."""

    client = create_timeframe_client(tmp_path)

    response = client.get("/api/v1/market/timeframes")

    assert response.status_code == 200

    timeframes = {item["code"]: item for item in response.json()["timeframes"]}

    assert timeframes["M1"]["available"] is False
    assert timeframes["M5"]["available"] is False
    assert timeframes["M15"]["available"] is True
    assert timeframes["M15"]["native"] is True
    assert timeframes["H1"]["available"] is True
    assert timeframes["H4"]["available"] is True
    assert timeframes["D1"]["available"] is True


def test_m15_returns_native_candles(
    tmp_path: Path,
) -> None:
    """Verifica il timeframe nativo M15."""

    client = create_timeframe_client(tmp_path)

    response = client.get("/api/v1/market/candles?timeframe=M15&limit=500")

    body = response.json()

    assert response.status_code == 200
    assert body["timeframe"] == "M15"
    assert body["source_timeframe"] == "M15"
    assert body["count"] == 96


def test_h1_returns_twenty_four_candles(
    tmp_path: Path,
) -> None:
    """Verifica l'aggregazione M15 verso H1."""

    client = create_timeframe_client(tmp_path)

    response = client.get("/api/v1/market/candles?timeframe=H1&limit=500")

    body = response.json()

    assert response.status_code == 200
    assert body["timeframe"] == "H1"
    assert body["count"] == 24


def test_h4_returns_six_candles(
    tmp_path: Path,
) -> None:
    """Verifica l'aggregazione M15 verso H4."""

    client = create_timeframe_client(tmp_path)

    response = client.get("/api/v1/market/candles?timeframe=H4&limit=500")

    body = response.json()

    assert response.status_code == 200
    assert body["timeframe"] == "H4"
    assert body["count"] == 6


def test_d1_returns_one_candle(
    tmp_path: Path,
) -> None:
    """Verifica l'aggregazione M15 verso D1."""

    client = create_timeframe_client(tmp_path)

    response = client.get("/api/v1/market/candles?timeframe=D1&limit=500")

    body = response.json()

    assert response.status_code == 200
    assert body["timeframe"] == "D1"
    assert body["count"] == 1


def test_unsupported_lower_timeframe_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il rifiuto di M1 nell'endpoint candele."""

    client = create_timeframe_client(tmp_path)

    response = client.get("/api/v1/market/candles?timeframe=M1&limit=500")

    assert response.status_code == 422
