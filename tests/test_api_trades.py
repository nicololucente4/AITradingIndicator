"""Test dell'endpoint API delle operazioni paper."""

# Importa SQLite per creare il database temporaneo.
import sqlite3

# Importa Path per gestire il database.
from pathlib import Path

# Importa FastAPI e TestClient.
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Importa il modulo per sostituire il percorso operativo.
import src.api.trades_router as trades_router_module

# Importa funzioni e router da verificare.
from src.api.trades_router import (
    load_paper_trades,
    normalize_optional_symbol,
    router,
)


def create_database(
    database_path: Path,
) -> None:
    """Crea un registro paper trade di test."""

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE paper_trades (
                trade_id TEXT PRIMARY KEY,
                signal_id TEXT NOT NULL UNIQUE,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                direction TEXT NOT NULL,
                status TEXT NOT NULL,
                opened_at_utc TEXT NOT NULL,
                entry_price REAL NOT NULL,
                stop_loss REAL NOT NULL,
                take_profit_1 REAL NOT NULL,
                prediction_confidence REAL,
                model_version TEXT,
                closed_at_utc TEXT,
                exit_price REAL,
                exit_reason TEXT,
                holding_bars INTEGER,
                gross_return_percentage REAL,
                result_r REAL,
                created_at_utc TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL
            )
            """
        )

        connection.executemany(
            """
            INSERT INTO paper_trades (
                trade_id,
                signal_id,
                symbol,
                timeframe,
                direction,
                status,
                opened_at_utc,
                entry_price,
                stop_loss,
                take_profit_1,
                prediction_confidence,
                model_version,
                closed_at_utc,
                exit_price,
                exit_reason,
                holding_bars,
                gross_return_percentage,
                result_r,
                created_at_utc,
                updated_at_utc
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                (
                    "TRD-EURUSD-M15-AAA111",
                    "signal-001",
                    "EURUSD",
                    "M15",
                    "LONG",
                    "CLOSED",
                    "2026-08-25T08:00:00+00:00",
                    1.1000,
                    1.0950,
                    1.1100,
                    0.91,
                    "model-eurusd",
                    "2026-08-25T09:00:00+00:00",
                    1.1100,
                    "TAKE_PROFIT_1",
                    4,
                    0.009090909,
                    2.0,
                    "2026-08-25T08:01:00+00:00",
                    "2026-08-25T09:01:00+00:00",
                ),
                (
                    "TRD-XAUUSD-M15-BBB222",
                    "signal-002",
                    "XAUUSD",
                    "M15",
                    "SHORT",
                    "OPEN",
                    "2026-08-25T10:00:00+00:00",
                    3375.00,
                    3385.00,
                    3355.00,
                    0.88,
                    "model-xauusd",
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "2026-08-25T10:01:00+00:00",
                    "2026-08-25T10:01:00+00:00",
                ),
            ],
        )

        connection.commit()


def create_client(
    database_path: Path,
) -> TestClient:
    """Crea un client API isolato."""

    # Imposta il database temporaneo.
    trades_router_module.PAPER_TRADES_DATABASE_PATH = database_path

    # Crea l'applicazione di test.
    application = FastAPI()

    # Registra il router delle operazioni.
    application.include_router(router)

    return TestClient(application)


def test_symbol_is_normalized() -> None:
    """Verifica la normalizzazione del simbolo."""

    assert normalize_optional_symbol(" xauusd ") == "XAUUSD"

    assert normalize_optional_symbol(None) is None


def test_trades_are_loaded_from_database(
    tmp_path: Path,
) -> None:
    """Verifica la lettura del registro completo."""

    database_path = tmp_path / "live_paper.db"

    create_database(database_path)

    trades = load_paper_trades(
        database_path=database_path,
        limit=200,
    )

    assert len(trades) == 2

    # Il trade più recente deve essere il primo.
    assert trades[0]["trade_id"] == "TRD-XAUUSD-M15-BBB222"


def test_endpoint_filters_symbol_and_status(
    tmp_path: Path,
) -> None:
    """Verifica i filtri per simbolo e stato."""

    database_path = tmp_path / "live_paper.db"

    create_database(database_path)

    client = create_client(database_path)

    response = client.get(
        "/api/v1/trades",
        params={
            "symbol": "XAUUSD",
            "status": "OPEN",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["symbol"] == "XAUUSD"
    assert payload["count"] == 1
    assert payload["summary"] == {
        "total": 1,
        "open": 1,
        "closed": 0,
    }

    assert payload["trades"][0]["trade_id"] == "TRD-XAUUSD-M15-BBB222"


def test_missing_database_returns_empty_response(
    tmp_path: Path,
) -> None:
    """Verifica il comportamento senza database."""

    client = create_client(tmp_path / "missing.db")

    response = client.get("/api/v1/trades")

    assert response.status_code == 200

    payload = response.json()

    assert payload["count"] == 0
    assert payload["trades"] == []

    assert payload["summary"] == {
        "total": 0,
        "open": 0,
        "closed": 0,
    }
