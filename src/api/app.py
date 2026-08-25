"""Backend FastAPI del sistema AI Trading Indicator."""

# Importa SQLite per leggere segnali ed esiti.
import sqlite3

# Importa dataclass per configurare l'applicazione.
from dataclasses import dataclass

# Importa Path per gestire i percorsi locali.
from pathlib import Path

# Importa Annotated e Any per tipizzare endpoint e record.
from typing import Annotated, Any

# Importa pandas per elaborare i dati.
import pandas as pd

# Importa FastAPI e gli errori HTTP.
from fastapi import FastAPI, HTTPException, Query

# Importa CORS per consentire il collegamento da Next.js.
from fastapi.middleware.cors import CORSMiddleware

# Importa il servizio dati multi-strumento e multi-timeframe.
from src.api.market_service import (
    MarketDataQueryService,
    MarketDataServiceError,
    list_available_symbols,
    normalize_market_symbol,
)

# Importa il router del prezzo live MT5.
from src.api.tick_router import (
    router as tick_router,
)

# Importa il provider CSV validato.
from src.data.file_provider import FileDataProvider

# Importa lo storage persistente delle candele.
from src.data.market_data_store import SQLiteMarketDataStore

# Importa il catalogo professionale dei timeframe.
from src.data.market_timeframes import (
    MARKET_TIMEFRAMES,
    MarketTimeframeError,
    get_supported_timeframe_codes,
    get_timeframe_by_code,
)

# Importa l'aggregatore multi-timeframe.
from src.data.timeframe import (
    TimeframeAggregationError,
    resample_ohlcv,
)

# Importa il generatore delle statistiche Live Paper.
from src.monitoring.live_paper_report import (
    generate_live_paper_statistics,
)


@dataclass(frozen=True)
class APIConfig:
    """Configurazione del backend FastAPI."""

    # Percorso del dataset CSV usato come fallback locale.
    market_data_path: str = "data/sample/EURUSD_M15_sample.csv"

    # Percorso opzionale dell'archivio delle candele.
    market_data_database_path: str | None = None

    # Percorso del database segnali ed esiti.
    database_path: str = "data/live_paper/coordinated_live_paper.db"

    # Simbolo predefinito gestito dall'API.
    symbol: str = "EURUSD"

    # Timeframe operativo predefinito del modello.
    timeframe: str = "M15"

    # Durata del timeframe sorgente del CSV.
    source_timeframe_minutes: int = 15

    # Simboli per i quali esiste un modello validato.
    model_symbols: tuple[str, ...] = ("EURUSD",)

    # Modalità esclusivamente simulata.
    paper_trading_only: bool = True


def _table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    """Verifica la presenza di una tabella SQLite."""

    cursor = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    )

    return cursor.fetchone() is not None


def _empty_signals_dataframe() -> pd.DataFrame:
    """Crea un registro segnali vuoto compatibile."""

    return pd.DataFrame(
        columns=[
            "signal_id",
            "timestamp",
            "signal_available_at",
            "signal",
            "signal_status",
            "signal_source",
            "close_price",
            "entry_price",
            "stop_loss",
            "take_profit_1",
            "take_profit_2",
            "take_profit_3",
            "prediction_confidence",
            "probability_margin",
            "model_version",
            "model_sha256",
            "filter_reason",
            "operating_mode",
            "created_at_utc",
        ]
    )


def _empty_outcomes_dataframe() -> pd.DataFrame:
    """Crea un registro esiti vuoto compatibile."""

    return pd.DataFrame(
        columns=[
            "signal_id",
            "direction",
            "entry_price",
            "exit_price",
            "exit_reason",
            "exit_timestamp",
            "holding_bars",
            "gross_return_percentage",
            "result_r",
            "evaluated_at_utc",
            "outcome_mode",
        ]
    )


def _read_database(
    database_path: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Legge segnali ed esiti dal database SQLite."""

    selected_path = Path(database_path)

    if not selected_path.exists():
        return (
            _empty_signals_dataframe(),
            _empty_outcomes_dataframe(),
        )

    with sqlite3.connect(selected_path) as connection:
        if _table_exists(
            connection,
            "signals",
        ):
            signals = pd.read_sql_query(
                """
                SELECT *
                FROM signals
                ORDER BY timestamp ASC
                """,
                connection,
            )
        else:
            signals = _empty_signals_dataframe()

        if _table_exists(
            connection,
            "signal_outcomes",
        ):
            outcomes = pd.read_sql_query(
                """
                SELECT *
                FROM signal_outcomes
                ORDER BY exit_timestamp ASC
                """,
                connection,
            )
        else:
            outcomes = _empty_outcomes_dataframe()

    return signals, outcomes


def _dataframe_to_records(
    dataframe: pd.DataFrame,
):
    """Converte un DataFrame in record JSON compatibili."""

    normalized = dataframe.copy(deep=True)

    for column in normalized.columns:
        if pd.api.types.is_datetime64_any_dtype(normalized[column]):
            normalized[column] = normalized[column].map(
                lambda value: value.isoformat() if pd.notna(value) else None
            )

    for column in normalized.columns:
        normalized[column] = normalized[column].map(
            lambda value: (
                value.isoformat()
                if isinstance(
                    value,
                    pd.Timestamp,
                )
                else value
            )
        )

    normalized = normalized.astype(object).where(
        pd.notna(normalized),
        None,
    )

    records: list[dict[str, Any]] = normalized.to_dict(orient="records")

    return records


def _load_csv_market_dataframe(
    market_data_path: Path,
) -> pd.DataFrame:
    """Carica e valida il dataset CSV di fallback."""

    if not market_data_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(f"Dataset OHLCV non trovato: {market_data_path}."),
        )

    try:
        provider = FileDataProvider()

        return provider.load_csv(market_data_path)

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(f"Errore caricamento OHLCV: {error}."),
        ) from error


def _validate_requested_timeframe(
    timeframe_code: str,
) -> str:
    """Normalizza e valida un timeframe richiesto."""

    try:
        timeframe = get_timeframe_by_code(timeframe_code)

    except MarketTimeframeError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    return timeframe.code


def _validate_requested_symbol(
    symbol: str,
) -> str:
    """Normalizza e valida un simbolo richiesto."""

    try:
        return normalize_market_symbol(symbol)

    except MarketDataServiceError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error


def _is_model_enabled(
    config: APIConfig,
    symbol: str,
) -> bool:
    """Verifica se il simbolo ha un modello registrato."""

    normalized_model_symbols = {
        normalize_market_symbol(model_symbol) for model_symbol in config.model_symbols
    }

    return symbol in normalized_model_symbols


def _open_market_store(
    config: APIConfig,
) -> SQLiteMarketDataStore | None:
    """Apre lo storage delle candele quando disponibile."""

    if config.market_data_database_path is None:
        return None

    selected_path = Path(config.market_data_database_path)

    if not selected_path.exists():
        return None

    try:
        return SQLiteMarketDataStore(selected_path)

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(f"Errore apertura archivio candele: {error}."),
        ) from error


def _create_market_service(
    config: APIConfig,
    *,
    symbol: str,
) -> MarketDataQueryService | None:
    """Crea il servizio SQLite per il simbolo richiesto."""

    store = _open_market_store(config)

    if store is None:
        return None

    availability = store.list_availability(symbol=symbol)

    if not availability:
        return None

    return MarketDataQueryService(
        store,
        symbol=symbol,
        model_enabled=(
            _is_model_enabled(
                config,
                symbol,
            )
        ),
    )


def _list_symbols(
    config: APIConfig,
):
    """Restituisce gli strumenti disponibili."""

    store = _open_market_store(config)

    if store is not None:
        symbols = list_available_symbols(
            store,
            model_symbols=(config.model_symbols),
        )

        if symbols:
            return (
                [item.to_dict() for item in symbols],
                "SQLITE_MARKET_DATA",
            )

    # Il CSV di fallback contiene solo il simbolo predefinito.
    fallback_symbol = normalize_market_symbol(config.symbol)

    return (
        [
            {
                "symbol": fallback_symbol,
                "native_timeframe_count": 1,
                "stored_candle_count": 0,
                "model_enabled": (
                    _is_model_enabled(
                        config,
                        fallback_symbol,
                    )
                ),
            }
        ],
        "CSV_FALLBACK",
    )


def _build_csv_timeframe_catalog(
    config: APIConfig,
    *,
    symbol: str,
):
    """Costruisce il catalogo disponibile dal CSV M15."""

    result = []

    # Il CSV può essere utilizzato solo per il simbolo predefinito.
    csv_symbol = normalize_market_symbol(config.symbol)

    if symbol != csv_symbol:
        return [
            {
                "code": timeframe.code,
                "label": (timeframe.display_label),
                "minutes": timeframe.minutes,
                "available": False,
                "native": False,
                "model_enabled": False,
                "source_timeframe": None,
                "stored_candle_count": 0,
                "reason": (f"Nessun dato disponibile per {symbol}."),
            }
            for timeframe in MARKET_TIMEFRAMES
        ]

    symbol_model_enabled = _is_model_enabled(
        config,
        symbol,
    )

    for timeframe in MARKET_TIMEFRAMES:
        timeframe_model_enabled = symbol_model_enabled and timeframe.code == "M15"

        if timeframe.code == "M15":
            result.append(
                {
                    "code": timeframe.code,
                    "label": (timeframe.display_label),
                    "minutes": timeframe.minutes,
                    "available": True,
                    "native": True,
                    "model_enabled": (timeframe_model_enabled),
                    "source_timeframe": "M15",
                    "stored_candle_count": 0,
                    "reason": None,
                }
            )

            continue

        if (
            timeframe.minutes > config.source_timeframe_minutes
            and timeframe.minutes % config.source_timeframe_minutes == 0
        ):
            result.append(
                {
                    "code": timeframe.code,
                    "label": (timeframe.display_label),
                    "minutes": timeframe.minutes,
                    "available": True,
                    "native": False,
                    "model_enabled": (timeframe_model_enabled),
                    "source_timeframe": "M15",
                    "stored_candle_count": 0,
                    "reason": None,
                }
            )

            continue

        result.append(
            {
                "code": timeframe.code,
                "label": (timeframe.display_label),
                "minutes": timeframe.minutes,
                "available": False,
                "native": False,
                "model_enabled": (timeframe_model_enabled),
                "source_timeframe": None,
                "stored_candle_count": 0,
                "reason": ("Richiede candele native dal provider reale."),
            }
        )

    return result


def _load_csv_timeframe(
    dataframe: pd.DataFrame,
    *,
    selected_timeframe: str,
    source_minutes: int,
) -> pd.DataFrame:
    """Restituisce il timeframe richiesto dal CSV M15."""

    target = get_timeframe_by_code(selected_timeframe)

    if target.minutes == source_minutes:
        return dataframe.copy(deep=True)

    if target.minutes < source_minutes:
        raise HTTPException(
            status_code=422,
            detail=(f"Timeframe non disponibile: {target.code}. Richiede candele native."),
        )

    if target.minutes % source_minutes != 0:
        raise HTTPException(
            status_code=422,
            detail=(f"Timeframe non aggregabile dal CSV: {target.code}."),
        )

    try:
        return resample_ohlcv(
            dataframe=dataframe,
            source_minutes=(source_minutes),
            target_minutes=(target.minutes),
        )

    except TimeframeAggregationError as error:
        raise HTTPException(
            status_code=422,
            detail=(f"Impossibile generare il timeframe {target.code}: {error}"),
        ) from error


def create_app(
    config: APIConfig | None = None,
) -> FastAPI:
    """Crea e configura l'applicazione FastAPI."""

    selected_config = config or APIConfig()

    if not selected_config.paper_trading_only:
        raise ValueError("Il backend API richiede paper_trading_only=true.")

    if selected_config.timeframe != "M15":
        raise ValueError("Il modello corrente richiede un timeframe operativo M15.")

    if selected_config.source_timeframe_minutes != 15:
        raise ValueError("Il timeframe CSV sorgente deve essere pari a 15 minuti.")

    app = FastAPI(
        title=("AI Trading Indicator API"),
        description=(
            "API read-only per dati OHLCV "
            "multi-strumento e multi-timeframe, "
            "segnali, esiti e statistiche."
        ),
        version="0.4.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=[
            "GET",
        ],
        allow_headers=[
            "*",
        ],
    )

    # Espone il prezzo tick live MT5.
    app.include_router(tick_router)

    @app.get("/")
    def root() -> dict[str, object]:
        """Restituisce le informazioni principali."""

        return {
            "application": ("AI Trading Indicator API"),
            "version": "0.4.0",
            "mode": "PAPER_ONLY",
            "symbol": (selected_config.symbol),
            "source_timeframe": (selected_config.timeframe),
            "documentation": "/docs",
        }

    @app.get("/api/v1/health")
    def health() -> dict[str, object]:
        """Restituisce lo stato dei componenti locali."""

        csv_available = Path(selected_config.market_data_path).exists()

        market_database_available = False

        if selected_config.market_data_database_path is not None:
            market_database_available = Path(selected_config.market_data_database_path).exists()

        database_available = Path(selected_config.database_path).exists()

        return {
            "status": "healthy",
            "mode": "PAPER_ONLY",
            "market_data_available": (market_database_available or csv_available),
            "market_data_database_available": (market_database_available),
            "csv_fallback_available": (csv_available),
            "database_available": (database_available),
            "symbol": (selected_config.symbol),
            "timeframe": (selected_config.timeframe),
        }

    @app.get("/api/v1/market/symbols")
    def get_symbols() -> dict[str, object]:
        """Restituisce gli strumenti disponibili."""

        symbols, source_type = _list_symbols(selected_config)

        return {
            "source_type": source_type,
            "default_symbol": (normalize_market_symbol(selected_config.symbol)),
            "count": len(symbols),
            "symbols": symbols,
        }

    @app.get("/api/v1/market/timeframes")
    def get_timeframes(
        symbol: Annotated[
            str,
            Query(),
        ] = "",
    ) -> dict[str, object]:
        """Restituisce i timeframe del simbolo richiesto."""

        requested_symbol = symbol or selected_config.symbol

        selected_symbol = _validate_requested_symbol(requested_symbol)

        service = _create_market_service(
            selected_config,
            symbol=selected_symbol,
        )

        if service is not None:
            items = [item.to_dict() for item in service.list_timeframes()]

            source_type = "SQLITE_MARKET_DATA"

        else:
            items = _build_csv_timeframe_catalog(
                selected_config,
                symbol=selected_symbol,
            )

            source_type = "CSV_FALLBACK"

        return {
            "symbol": selected_symbol,
            "source_timeframe": (selected_config.timeframe),
            "source_type": source_type,
            "model_timeframe": "M15",
            "model_enabled": (
                _is_model_enabled(
                    selected_config,
                    selected_symbol,
                )
            ),
            "timeframes": items,
        }

    @app.get("/api/v1/market/candles")
    def get_candles(
        symbol: Annotated[
            str,
            Query(),
        ] = "",
        timeframe: Annotated[
            str,
            Query(),
        ] = "M15",
        limit: int = Query(
            default=500,
            ge=1,
            le=5000,
        ),
    ) -> dict[str, object]:
        """Restituisce le candele richieste."""

        requested_symbol = symbol or selected_config.symbol

        selected_symbol = _validate_requested_symbol(requested_symbol)

        selected_timeframe = _validate_requested_timeframe(timeframe)

        service = _create_market_service(
            selected_config,
            symbol=selected_symbol,
        )

        if service is not None:
            try:
                selected_dataframe = service.load_candles(
                    timeframe_code=(selected_timeframe),
                    limit=limit,
                )

                availability = service.get_timeframe_availability(selected_timeframe)

            except MarketDataServiceError as error:
                raise HTTPException(
                    status_code=422,
                    detail=str(error),
                ) from error

            source_timeframe = availability.source_timeframe

            native = availability.native

            model_enabled = availability.model_enabled

            source_type = "SQLITE_MARKET_DATA"

        else:
            csv_symbol = normalize_market_symbol(selected_config.symbol)

            if selected_symbol != csv_symbol:
                raise HTTPException(
                    status_code=404,
                    detail=(f"Nessun dato disponibile per {selected_symbol}."),
                )

            source_dataframe = _load_csv_market_dataframe(Path(selected_config.market_data_path))

            selected_dataframe = _load_csv_timeframe(
                source_dataframe,
                selected_timeframe=(selected_timeframe),
                source_minutes=(selected_config.source_timeframe_minutes),
            )

            selected_dataframe = selected_dataframe.tail(limit).reset_index(drop=True)

            source_timeframe = "M15"

            native = selected_timeframe == "M15"

            model_enabled = (
                _is_model_enabled(
                    selected_config,
                    selected_symbol,
                )
                and selected_timeframe == "M15"
            )

            source_type = "CSV_FALLBACK"

        return {
            "symbol": selected_symbol,
            "timeframe": (selected_timeframe),
            "source_timeframe": (source_timeframe),
            "source_type": source_type,
            "native": native,
            "model_enabled": (model_enabled),
            "timezone": "UTC",
            "count": len(selected_dataframe),
            "candles": (_dataframe_to_records(selected_dataframe)),
        }

    @app.get("/api/v1/signals")
    def get_signals(
        limit: int = Query(
            default=200,
            ge=1,
            le=5000,
        ),
    ) -> dict[str, object]:
        """Restituisce gli ultimi segnali Live Paper."""

        signals, _ = _read_database(selected_config.database_path)

        selected_signals = signals.tail(limit).reset_index(drop=True)

        return {
            "mode": "PAPER_ONLY",
            "count": len(selected_signals),
            "signals": (_dataframe_to_records(selected_signals)),
        }

    @app.get("/api/v1/outcomes")
    def get_outcomes(
        limit: int = Query(
            default=200,
            ge=1,
            le=5000,
        ),
    ) -> dict[str, object]:
        """Restituisce gli esiti Live Paper."""

        _, outcomes = _read_database(selected_config.database_path)

        selected_outcomes = outcomes.tail(limit).reset_index(drop=True)

        return {
            "mode": "PAPER_ONLY",
            "count": len(selected_outcomes),
            "outcomes": (_dataframe_to_records(selected_outcomes)),
        }

    @app.get("/api/v1/statistics")
    def get_statistics() -> dict[str, object]:
        """Restituisce le statistiche Live Paper."""

        signals, outcomes = _read_database(selected_config.database_path)

        if signals.empty:
            return {
                "mode": "PAPER_ONLY",
                "data_available": False,
                "statistics": None,
            }

        try:
            statistics = generate_live_paper_statistics(
                signals=signals,
                outcomes=outcomes,
            )

        except Exception as error:
            raise HTTPException(
                status_code=500,
                detail=(f"Errore generazione statistiche: {error}."),
            ) from error

        return {
            "mode": "PAPER_ONLY",
            "data_available": True,
            "statistics": (statistics.to_dict()),
        }

    @app.get("/api/v1/system/status")
    def get_system_status() -> dict[str, object]:
        """Restituisce lo stato sintetico del sistema."""

        signals, outcomes = _read_database(selected_config.database_path)

        latest_signal_timestamp = None

        if not signals.empty:
            latest_signal_timestamp = str(signals.iloc[-1]["timestamp"])

        symbols, _ = _list_symbols(selected_config)

        default_symbol = normalize_market_symbol(selected_config.symbol)

        service = _create_market_service(
            selected_config,
            symbol=default_symbol,
        )

        if service is not None:
            available_timeframes = [
                item.code for item in service.list_timeframes() if item.available
            ]
        else:
            available_timeframes = [
                item["code"]
                for item in _build_csv_timeframe_catalog(
                    selected_config,
                    symbol=default_symbol,
                )
                if item["available"]
            ]

        return {
            "api_status": "ONLINE",
            "engine_mode": "LIVE_PAPER",
            "paper_trading_only": True,
            "real_orders_enabled": False,
            "symbol": default_symbol,
            "symbols": [item["symbol"] for item in symbols],
            "timeframe": (selected_config.timeframe),
            "model_timeframe": "M15",
            "model_symbols": list(selected_config.model_symbols),
            "supported_timeframes": list(get_supported_timeframe_codes()),
            "available_timeframes": (available_timeframes),
            "signal_count": len(signals),
            "outcome_count": len(outcomes),
            "latest_signal_timestamp": (latest_signal_timestamp),
        }

    return app


# L'istanza Uvicorn usa lo storage operativo.
app = create_app(
    APIConfig(
        market_data_database_path=("data/live_paper/market_data.db"),
        database_path=("data/live_paper/live_paper.db"),
        model_symbols=("EURUSD",),
    )
)
