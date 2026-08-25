"""Router FastAPI per prezzo live MT5 e paper trade."""

# Importa importlib per caricare MetaTrader5 dinamicamente.
import importlib

# Importa Lock per proteggere la connessione condivisa.
from threading import Lock

# Importa cast per tipizzare il modulo MT5.
from typing import cast

# Importa gli strumenti FastAPI.
from fastapi import APIRouter, HTTPException, Query

# Importa il router delle operazioni paper.
from src.api.trades_router import (
    router as trades_router,
)

# Importa il caricatore della configurazione locale.
from src.config.environment import (
    EnvironmentFileError,
    load_application_settings_from_env,
)

# Importa gli errori della configurazione.
from src.config.settings import SettingsError

# Importa servizio, protocollo ed errore tick.
from src.data.mt5_tick_service import (
    MetaTrader5TickModule,
    MetaTrader5TickService,
    MetaTrader5TickServiceError,
)

# Crea il router principale aggiunto da app.py.
router = APIRouter()

# Registra il router read-only delle operazioni paper.
router.include_router(
    trades_router
)

# Protegge la connessione MT5 condivisa.
_service_lock = Lock()

# Memorizza il servizio tick tra richieste successive.
_tick_service: MetaTrader5TickService | None = None


def _import_metatrader5_module() -> MetaTrader5TickModule:
    """Importa il pacchetto ufficiale MetaTrader5."""

    try:
        # Carica dinamicamente il modulo ufficiale.
        imported_module = importlib.import_module(
            "MetaTrader5"
        )

    except ModuleNotFoundError as error:
        raise MetaTrader5TickServiceError(
            "Pacchetto MetaTrader5 non installato."
        ) from error

    # Restituisce il modulo con il protocollo previsto.
    return cast(
        MetaTrader5TickModule,
        imported_module,
    )


def _create_tick_service() -> MetaTrader5TickService:
    """Crea il servizio tick dalla configurazione locale."""

    try:
        # Carica il file .env locale.
        settings = load_application_settings_from_env(
            environment_file=".env",
            require_file=True,
            override_existing=True,
        )

    except (
        EnvironmentFileError,
        SettingsError,
    ) as error:
        raise MetaTrader5TickServiceError(
            "Configurazione tick non disponibile: "
            f"{error}"
        ) from error

    # Il prezzo live richiede il provider MT5.
    if settings.data_provider != "MT5":
        raise MetaTrader5TickServiceError(
            "Prezzo live disponibile solamente "
            "con DATA_PROVIDER=MT5."
        )

    # Crea il servizio usando il modulo ufficiale.
    return MetaTrader5TickService(
        settings=settings,
        mt5_module=(
            _import_metatrader5_module()
        ),
    )


def get_tick_service() -> MetaTrader5TickService:
    """Restituisce il servizio tick condiviso."""

    global _tick_service

    # Protegge la creazione del servizio.
    with _service_lock:
        if _tick_service is None:
            _tick_service = (
                _create_tick_service()
            )

        return _tick_service


def reset_tick_service() -> None:
    """Chiude e rimuove il servizio tick condiviso."""

    global _tick_service

    # Protegge la chiusura del servizio.
    with _service_lock:
        if _tick_service is not None:
            _tick_service.disconnect()

        _tick_service = None


@router.get(
    "/api/v1/market/tick",
    tags=["market"],
)
def get_live_tick(
    symbol: str = Query(
        default="EURUSD",
        min_length=1,
        max_length=32,
    ),
) -> dict[str, object]:
    """Restituisce il tick live del simbolo richiesto."""

    try:
        # Recupera o crea il servizio condiviso.
        service = get_tick_service()

        # Serializza la lettura effettiva da MT5.
        with _service_lock:
            tick = service.get_tick(
                symbol
            )

        # Converte il risultato in JSON.
        return tick.to_dict()

    except MetaTrader5TickServiceError as error:
        # Restituisce 503 quando MT5 non è disponibile.
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error