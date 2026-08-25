"""Test dell'endpoint API del prezzo tick live."""

# Importa pandas per creare timestamp UTC.
import pandas as pd

# Importa pytest per i confronti numerici.
import pytest

# Importa FastAPI e il client di test.
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Importa il modulo router per sostituire il servizio condiviso.
import src.api.tick_router as tick_router_module

# Importa router e reset del servizio.
from src.api.tick_router import (
    reset_tick_service,
    router,
)

# Importa modello ed errore del tick.
from src.data.mt5_tick_service import (
    LiveMarketTick,
    MetaTrader5TickServiceError,
)


class FakeTickService:
    """Simula il servizio tick usato dall'API."""

    def get_tick(
        self,
        symbol: str,
    ) -> LiveMarketTick:
        """Restituisce un tick deterministico."""

        return LiveMarketTick(
            symbol=(symbol.strip().upper()),
            bid=1.16755,
            ask=1.16757,
            mid=1.16756,
            spread=0.00002,
            timestamp=pd.Timestamp(
                "2026-08-25 09:00:01",
                tz="UTC",
            ),
        )

    def disconnect(
        self,
    ) -> None:
        """Simula la chiusura del servizio."""


class FailingTickService:
    """Simula un errore del terminale MT5."""

    def get_tick(
        self,
        symbol: str,
    ) -> LiveMarketTick:
        """Genera un errore controllato."""

        del symbol

        raise MetaTrader5TickServiceError("Terminale MT5 non disponibile.")

    def disconnect(
        self,
    ) -> None:
        """Simula la chiusura del servizio."""


def create_client(
    service: object,
) -> TestClient:
    """Crea un client API con servizio simulato."""

    # Chiude un eventuale servizio precedente.
    reset_tick_service()

    # Inserisce il servizio simulato.
    tick_router_module._tick_service = service

    # Crea un'applicazione FastAPI isolata.
    application = FastAPI()

    # Registra il router da verificare.
    application.include_router(router)

    # Restituisce il client HTTP.
    return TestClient(application)


def test_tick_endpoint_returns_live_price() -> None:
    """Verifica il tick restituito dall'API."""

    client = create_client(FakeTickService())

    response = client.get(
        "/api/v1/market/tick",
        params={
            "symbol": "EURUSD",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["symbol"] == "EURUSD"

    assert payload["bid"] == 1.16755
    assert payload["ask"] == 1.16757
    assert payload["mid"] == 1.16756

    assert payload["spread"] == pytest.approx(0.00002)

    assert payload["source"] == "MT5_LIVE_TICK"


def test_tick_symbol_is_normalized() -> None:
    """Verifica la normalizzazione del simbolo."""

    client = create_client(FakeTickService())

    response = client.get(
        "/api/v1/market/tick",
        params={
            "symbol": " xauusd ",
        },
    )

    assert response.status_code == 200

    assert response.json()["symbol"] == "XAUUSD"


def test_tick_error_returns_service_unavailable() -> None:
    """Verifica la risposta 503 quando MT5 non risponde."""

    client = create_client(FailingTickService())

    response = client.get(
        "/api/v1/market/tick",
        params={
            "symbol": "EURUSD",
        },
    )

    assert response.status_code == 503

    assert "Terminale MT5 non disponibile" in response.json()["detail"]
