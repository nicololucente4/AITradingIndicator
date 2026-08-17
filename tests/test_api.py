"""Test automatici del backend FastAPI."""

# Importa SQLite per preparare database temporanei.
import sqlite3

# Importa Path per gestire i file temporanei.
from pathlib import Path

# Importa pandas per creare un CSV OHLCV.
import pandas as pd

# Importa TestClient per interrogare FastAPI.
from fastapi.testclient import TestClient

# Importa configurazione e factory dell'applicazione.
from src.api.app import APIConfig, create_app


def create_market_csv(
    file_path: Path,
) -> None:
    """Crea un CSV OHLCV valido."""

    # Costruisce quattro candele M15.
    dataframe = pd.DataFrame(
        {
            "timestamp": pd.date_range(
                start="2026-08-14 10:00:00",
                periods=4,
                freq="15min",
                tz="UTC",
            ),
            "open": [
                100.0,
                101.0,
                102.0,
                103.0,
            ],
            "high": [
                102.0,
                103.0,
                104.0,
                105.0,
            ],
            "low": [
                99.0,
                100.0,
                101.0,
                102.0,
            ],
            "close": [
                101.0,
                102.0,
                103.0,
                104.0,
            ],
            "volume": [
                100,
                110,
                120,
                130,
            ],
        }
    )

    # Salva il file CSV.
    dataframe.to_csv(
        file_path,
        index=False,
    )


def create_database(
    database_path: Path,
) -> None:
    """Crea un database con un segnale e un esito."""

    # Apre il database temporaneo.
    with sqlite3.connect(database_path) as connection:
        # Crea la tabella signals.
        connection.execute(
            """
            CREATE TABLE signals (
                signal_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                signal_available_at TEXT NOT NULL,
                signal TEXT NOT NULL,
                signal_status TEXT NOT NULL,
                signal_source TEXT NOT NULL,
                close_price REAL,
                entry_price REAL,
                stop_loss REAL,
                take_profit_1 REAL,
                take_profit_2 REAL,
                take_profit_3 REAL,
                prediction_confidence REAL,
                probability_margin REAL,
                model_version TEXT,
                model_sha256 TEXT,
                filter_reason TEXT,
                operating_mode TEXT NOT NULL,
                created_at_utc TEXT NOT NULL
            )
            """
        )

        # Inserisce un segnale LONG.
        connection.execute(
            """
            INSERT INTO signals (
                signal_id,
                timestamp,
                signal_available_at,
                signal,
                signal_status,
                signal_source,
                close_price,
                entry_price,
                stop_loss,
                take_profit_1,
                take_profit_2,
                take_profit_3,
                prediction_confidence,
                probability_margin,
                model_version,
                model_sha256,
                filter_reason,
                operating_mode,
                created_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "signal-001",
                "2026-08-14T10:00:00+00:00",
                "2026-08-14T10:15:00+00:00",
                "LONG",
                "CONFIRMED",
                "TEST",
                101.0,
                101.0,
                99.0,
                103.0,
                105.0,
                107.0,
                0.80,
                0.40,
                "test_model",
                "a" * 64,
                "PREDICTION_ACCEPTED",
                "LIVE_PAPER",
                "2026-08-14T10:15:00+00:00",
            ),
        )

        # Crea la tabella degli esiti.
        connection.execute(
            """
            CREATE TABLE signal_outcomes (
                signal_id TEXT PRIMARY KEY,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                exit_reason TEXT NOT NULL,
                exit_timestamp TEXT NOT NULL,
                holding_bars INTEGER NOT NULL,
                gross_return_percentage REAL NOT NULL,
                result_r REAL,
                evaluated_at_utc TEXT NOT NULL,
                outcome_mode TEXT NOT NULL
            )
            """
        )

        # Inserisce un esito positivo.
        connection.execute(
            """
            INSERT INTO signal_outcomes (
                signal_id,
                direction,
                entry_price,
                exit_price,
                exit_reason,
                exit_timestamp,
                holding_bars,
                gross_return_percentage,
                result_r,
                evaluated_at_utc,
                outcome_mode
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "signal-001",
                "LONG",
                101.0,
                103.0,
                "TAKE_PROFIT_1",
                "2026-08-14T10:30:00+00:00",
                1,
                0.01980198,
                1.0,
                "2026-08-14T10:30:00+00:00",
                "PAPER_ONLY",
            ),
        )

        # Conferma le operazioni.
        connection.commit()


def create_test_client(
    tmp_path: Path,
    create_db: bool = True,
) -> TestClient:
    """Crea un client API isolato."""

    # Prepara il CSV.
    csv_path = tmp_path / "market.csv"
    create_market_csv(csv_path)

    # Prepara il database.
    database_path = tmp_path / "live_paper.db"

    if create_db:
        create_database(database_path)

    # Crea l'applicazione con percorsi temporanei.
    application = create_app(
        APIConfig(
            market_data_path=str(csv_path),
            database_path=str(database_path),
            symbol="EURUSD",
            timeframe="M15",
            paper_trading_only=True,
        )
    )

    # Restituisce il client HTTP di test.
    return TestClient(application)


def test_root_endpoint(
    tmp_path: Path,
) -> None:
    """Verifica le informazioni principali dell'API."""

    client = create_test_client(tmp_path)

    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["mode"] == "PAPER_ONLY"
    assert response.json()["documentation"] == "/docs"


def test_health_endpoint(
    tmp_path: Path,
) -> None:
    """Verifica lo stato dell'API."""

    client = create_test_client(tmp_path)

    response = client.get("/api/v1/health")

    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "healthy"
    assert body["market_data_available"] is True
    assert body["database_available"] is True


def test_candles_endpoint(
    tmp_path: Path,
) -> None:
    """Verifica la restituzione delle candele."""

    client = create_test_client(tmp_path)

    response = client.get("/api/v1/market/candles?limit=2")

    body = response.json()

    assert response.status_code == 200
    assert body["count"] == 2
    assert len(body["candles"]) == 2
    assert body["symbol"] == "EURUSD"
    assert body["timeframe"] == "M15"


def test_signals_endpoint(
    tmp_path: Path,
) -> None:
    """Verifica la restituzione dei segnali."""

    client = create_test_client(tmp_path)

    response = client.get("/api/v1/signals")

    body = response.json()

    assert response.status_code == 200
    assert body["count"] == 1
    assert body["signals"][0]["signal"] == "LONG"
    assert body["mode"] == "PAPER_ONLY"


def test_outcomes_endpoint(
    tmp_path: Path,
) -> None:
    """Verifica la restituzione degli esiti."""

    client = create_test_client(tmp_path)

    response = client.get("/api/v1/outcomes")

    body = response.json()

    assert response.status_code == 200
    assert body["count"] == 1
    assert body["outcomes"][0]["exit_reason"] == "TAKE_PROFIT_1"


def test_statistics_endpoint(
    tmp_path: Path,
) -> None:
    """Verifica le statistiche aggregate."""

    client = create_test_client(tmp_path)

    response = client.get("/api/v1/statistics")

    body = response.json()

    assert response.status_code == 200
    assert body["data_available"] is True
    assert body["statistics"]["total_signals"] == 1
    assert body["statistics"]["winning_outcomes"] == 1
    assert body["statistics"]["win_rate_percentage"] == 100.0


def test_empty_database_is_supported(
    tmp_path: Path,
) -> None:
    """Verifica il comportamento senza database."""

    client = create_test_client(
        tmp_path,
        create_db=False,
    )

    response = client.get("/api/v1/signals")

    assert response.status_code == 200
    assert response.json()["count"] == 0

    statistics_response = client.get("/api/v1/statistics")

    assert statistics_response.status_code == 200
    assert statistics_response.json()["data_available"] is False


def test_system_status_endpoint(
    tmp_path: Path,
) -> None:
    """Verifica lo stato sintetico del sistema."""

    client = create_test_client(tmp_path)

    response = client.get("/api/v1/system/status")

    body = response.json()

    assert response.status_code == 200
    assert body["api_status"] == "ONLINE"
    assert body["engine_mode"] == "LIVE_PAPER"
    assert body["paper_trading_only"] is True
    assert body["real_orders_enabled"] is False
    assert body["signal_count"] == 1
    assert body["outcome_count"] == 1
