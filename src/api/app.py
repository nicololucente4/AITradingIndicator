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

# Importa il servizio dati multi-timeframe.
from src.api.market_service import (
    MarketDataQueryService,
    MarketDataServiceError,
)

# Importa il provider CSV validato.
from src.data.file_provider import FileDataProvider

# Importa lo storage persistente delle candele.
from src.data.market_data_store import (
    SQLiteMarketDataStore,
)

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

    # Percorso opzionale dell'archivio persistente delle candele.
    market_data_database_path: str | None = None

    # Percorso del database segnali ed esiti.
    database_path: str = "data/live_paper/coordinated_live_paper.db"

    # Simbolo gestito dall'API.
    symbol: str = "EURUSD"

    # Timeframe operativo del modello.
    timeframe: str = "M15"

    # Durata del timeframe CSV sorgente.
    source_timeframe_minutes: int = 15

    # Modalità esclusivamente simulata.
    paper_trading_only: bool = True


def _table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    """Verifica la presenza di una tabella SQLite."""

    # Interroga il catalogo SQLite.
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

    # Converte il percorso ricevuto.
    selected_path = Path(database_path)

    # Senza database restituisce registri vuoti.
    if not selected_path.exists():
        return (
            _empty_signals_dataframe(),
            _empty_outcomes_dataframe(),
        )

    # Apre il database.
    with sqlite3.connect(selected_path) as connection:
        # Carica i segnali se la tabella esiste.
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

        # Carica gli esiti se la tabella esiste.
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
) -> list[dict[str, Any]]:
    """Converte un DataFrame in record JSON compatibili."""

    # Crea una copia per non modificare l'originale.
    normalized = dataframe.copy(deep=True)

    # Converte le colonne datetime in stringhe ISO.
    for column in normalized.columns:
        if pd.api.types.is_datetime64_any_dtype(normalized[column]):
            normalized[column] = normalized[column].map(
                lambda value: value.isoformat() if pd.notna(value) else None
            )

    # Converte Timestamp presenti in colonne object.
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

    # Sostituisce NaN e NaT con None.
    normalized = normalized.astype(object).where(
        pd.notna(normalized),
        None,
    )

    return normalized.to_dict(orient="records")


def _load_csv_market_dataframe(
    market_data_path: Path,
) -> pd.DataFrame:
    """Carica e valida il dataset CSV di fallback."""

    # Verifica che il dataset esista.
    if not market_data_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(f"Dataset OHLCV non trovato: {market_data_path}."),
        )

    try:
        # Usa il provider CSV già validato.
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
        # Recupera la definizione centralizzata.
        timeframe = get_timeframe_by_code(timeframe_code)

    except MarketTimeframeError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    return timeframe.code


def _create_market_service(
    config: APIConfig,
) -> MarketDataQueryService | None:
    """Crea il servizio SQLite se contiene dati del simbolo."""

    # Senza percorso configurato usa il CSV.
    if config.market_data_database_path is None:
        return None

    # Converte il percorso.
    selected_path = Path(config.market_data_database_path)

    # Senza file utilizza il CSV di fallback.
    if not selected_path.exists():
        return None

    try:
        # Crea lo storage sul database esistente.
        store = SQLiteMarketDataStore(selected_path)

        # Crea il servizio di interrogazione.
        service = MarketDataQueryService(
            store,
            symbol=config.symbol,
        )

        # Verifica che il simbolo abbia almeno un dataset.
        availability = store.list_availability(symbol=config.symbol)

        if not availability:
            return None

        return service

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(f"Errore apertura archivio candele: {error}."),
        ) from error


def _build_csv_timeframe_catalog(
    config: APIConfig,
) -> list:
    """Costruisce il catalogo disponibile dal CSV M15."""

    # Prepara il catalogo pubblico.
    result = []

    # Valuta ogni timeframe professionale.
    for timeframe in MARKET_TIMEFRAMES:
        # Il CSV M15 è nativo.
        if timeframe.code == "M15":
            result.append(
                {
                    "code": timeframe.code,
                    "label": (timeframe.display_label),
                    "minutes": timeframe.minutes,
                    "available": True,
                    "native": True,
                    "model_enabled": (timeframe.model_enabled),
                    "source_timeframe": "M15",
                    "stored_candle_count": 0,
                    "reason": None,
                }
            )

            continue

        # I timeframe superiori divisibili per M15
        # possono essere aggregati.
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
                    "model_enabled": (timeframe.model_enabled),
                    "source_timeframe": "M15",
                    "stored_candle_count": 0,
                    "reason": None,
                }
            )

            continue

        # I timeframe inferiori richiedono dati nativi.
        result.append(
            {
                "code": timeframe.code,
                "label": (timeframe.display_label),
                "minutes": timeframe.minutes,
                "available": False,
                "native": False,
                "model_enabled": (timeframe.model_enabled),
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

    # Recupera la definizione del timeframe.
    target = get_timeframe_by_code(selected_timeframe)

    # Il timeframe nativo viene restituito direttamente.
    if target.minutes == source_minutes:
        return dataframe.copy(deep=True)

    # Non ricostruisce timeframe inferiori.
    if target.minutes < source_minutes:
        raise HTTPException(
            status_code=422,
            detail=(f"Timeframe non disponibile: {target.code}. Richiede candele native."),
        )

    # La durata target deve essere divisibile per la sorgente.
    if target.minutes % source_minutes != 0:
        raise HTTPException(
            status_code=422,
            detail=(f"Timeframe non aggregabile dal CSV: {target.code}."),
        )

    try:
        # Aggrega solamente bucket completi.
        return resample_ohlcv(
            dataframe=dataframe,
            source_minutes=source_minutes,
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

    # Usa la configurazione predefinita se necessario.
    selected_config = config or APIConfig()

    # La release deve restare PAPER_ONLY.
    if not selected_config.paper_trading_only:
        raise ValueError("Il backend API richiede paper_trading_only=true.")

    # Il modello corrente opera su M15.
    if selected_config.timeframe != "M15":
        raise ValueError("Il modello corrente richiede un timeframe operativo M15.")

    # Il CSV di fallback deve essere M15.
    if selected_config.source_timeframe_minutes != 15:
        raise ValueError("Il timeframe CSV sorgente deve essere pari a 15 minuti.")

    # Crea l'applicazione.
    app = FastAPI(
        title="AI Trading Indicator API",
        description=(
            "API read-only per dati OHLCV multi-timeframe, segnali, esiti e statistiche Live Paper."
        ),
        version="0.3.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Abilita il frontend Next.js.
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

    @app.get("/")
    def root() -> dict[str, object]:
        """Restituisce le informazioni principali."""

        return {
            "application": ("AI Trading Indicator API"),
            "version": "0.3.0",
            "mode": "PAPER_ONLY",
            "symbol": selected_config.symbol,
            "source_timeframe": (selected_config.timeframe),
            "documentation": "/docs",
        }

    @app.get("/api/v1/health")
    def health() -> dict[str, object]:
        """Restituisce lo stato dei componenti locali."""

        # Verifica il CSV di fallback.
        csv_available = Path(selected_config.market_data_path).exists()

        # Verifica il database delle candele.
        market_database_available = False

        if selected_config.market_data_database_path is not None:
            market_database_available = Path(selected_config.market_data_database_path).exists()

        # Verifica il database segnali.
        database_available = Path(selected_config.database_path).exists()

        return {
            "status": "healthy",
            "mode": "PAPER_ONLY",
            "market_data_available": (market_database_available or csv_available),
            "market_data_database_available": (market_database_available),
            "csv_fallback_available": (csv_available),
            "database_available": (database_available),
            "symbol": selected_config.symbol,
            "timeframe": selected_config.timeframe,
        }

    @app.get("/api/v1/market/timeframes")
    def get_timeframes() -> dict[str, object]:
        """Restituisce disponibilità e origine dei timeframe."""

        # Prova a utilizzare lo storage persistente.
        service = _create_market_service(selected_config)

        # Usa il database delle candele.
        if service is not None:
            items = [item.to_dict() for item in service.list_timeframes()]

            source_type = "SQLITE_MARKET_DATA"

        # Usa il CSV M15 di fallback.
        else:
            items = _build_csv_timeframe_catalog(selected_config)

            source_type = "CSV_FALLBACK"

        return {
            "source_timeframe": (selected_config.timeframe),
            "source_type": source_type,
            "model_timeframe": "M15",
            "timeframes": items,
        }

    @app.get("/api/v1/market/candles")
    def get_candles(
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

        # Normalizza e valida il timeframe.
        selected_timeframe = _validate_requested_timeframe(timeframe)

        # Prova a usare lo storage persistente.
        service = _create_market_service(selected_config)

        if service is not None:
            try:
                # Carica dati nativi o aggregati.
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
            source_type = "SQLITE_MARKET_DATA"

        else:
            # Carica il CSV M15 di fallback.
            source_dataframe = _load_csv_market_dataframe(Path(selected_config.market_data_path))

            # Genera il timeframe richiesto.
            selected_dataframe = _load_csv_timeframe(
                source_dataframe,
                selected_timeframe=(selected_timeframe),
                source_minutes=(selected_config.source_timeframe_minutes),
            )

            # Applica il limite.
            selected_dataframe = selected_dataframe.tail(limit).reset_index(drop=True)

            source_timeframe = "M15"

            native = selected_timeframe == "M15"

            source_type = "CSV_FALLBACK"

        return {
            "symbol": selected_config.symbol,
            "timeframe": selected_timeframe,
            "source_timeframe": (source_timeframe),
            "source_type": source_type,
            "native": native,
            "model_enabled": (selected_timeframe == "M15"),
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

        # Nessun dato disponibile.
        if signals.empty:
            return {
                "mode": "PAPER_ONLY",
                "data_available": False,
                "statistics": None,
            }

        try:
            # Genera le statistiche.
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

        # Legge segnali ed esiti.
        signals, outcomes = _read_database(selected_config.database_path)

        # Recupera l'ultimo segnale.
        latest_signal_timestamp = None

        if not signals.empty:
            latest_signal_timestamp = str(signals.iloc[-1]["timestamp"])

        # Determina i timeframe disponibili.
        service = _create_market_service(selected_config)

        if service is not None:
            available_timeframes = [
                item.code for item in service.list_timeframes() if item.available
            ]
        else:
            available_timeframes = [
                item["code"]
                for item in (_build_csv_timeframe_catalog(selected_config))
                if item["available"]
            ]

        return {
            "api_status": "ONLINE",
            "engine_mode": "LIVE_PAPER",
            "paper_trading_only": True,
            "real_orders_enabled": False,
            "symbol": selected_config.symbol,
            "timeframe": selected_config.timeframe,
            "model_timeframe": "M15",
            "supported_timeframes": list(get_supported_timeframe_codes()),
            "available_timeframes": (available_timeframes),
            "signal_count": len(signals),
            "outcome_count": len(outcomes),
            "latest_signal_timestamp": (latest_signal_timestamp),
        }

    return app


# L'istanza Uvicorn usa lo storage persistente operativo.
app = create_app(
    APIConfig(
        market_data_database_path=("data/live_paper/market_data.db"),
        database_path=("data/live_paper/live_paper.db"),
    )
)
