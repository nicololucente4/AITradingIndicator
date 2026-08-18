"""Backend FastAPI del sistema AI Trading Indicator."""

# Importa SQLite per leggere segnali ed esiti.
import sqlite3

# Importa dataclass per configurare l'applicazione.
from dataclasses import dataclass

# Importa Path per gestire i percorsi locali.
from pathlib import Path

# Importa Literal per limitare i timeframe accettati.
from typing import Annotated, Any, Literal

# Importa pandas per elaborare i dati.
import pandas as pd

# Importa FastAPI e gli errori HTTP.
from fastapi import FastAPI, HTTPException, Query

# Importa CORS per consentire il collegamento da Next.js.
from fastapi.middleware.cors import CORSMiddleware

# Importa il provider CSV validato.
from src.data.file_provider import FileDataProvider

# Importa l'aggregatore multi-timeframe.
from src.data.timeframe import (
    TimeframeAggregationError,
    resample_ohlcv,
)

# Importa il generatore delle statistiche Live Paper.
from src.monitoring.live_paper_report import (
    generate_live_paper_statistics,
)

# Definisce i timeframe direttamente supportati dall'endpoint candele.
SupportedTimeframe = Literal[
    "M15",
    "H1",
    "H4",
    "D1",
]


# Associa ogni timeframe alla relativa durata in minuti.
TIMEFRAME_MINUTES: dict[str, int] = {
    "M15": 15,
    "H1": 60,
    "H4": 240,
    "D1": 1440,
}


@dataclass(frozen=True)
class APIConfig:
    """Configurazione del backend FastAPI."""

    # Percorso del dataset OHLCV sorgente.
    market_data_path: str = "data/sample/EURUSD_M15_sample.csv"

    # Percorso del database Live Paper.
    database_path: str = "data/live_paper/coordinated_live_paper.db"

    # Simbolo gestito dalla prima versione.
    symbol: str = "EURUSD"

    # Timeframe nativo del dataset sorgente.
    timeframe: str = "M15"

    # Durata in minuti del timeframe sorgente.
    source_timeframe_minutes: int = 15

    # Modalità esclusivamente simulata.
    paper_trading_only: bool = True


def _table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    """Verifica la presenza di una tabella SQLite."""

    # Interroga il catalogo interno del database.
    cursor = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    )

    # Restituisce True se la tabella è presente.
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

    # Se il database non esiste, restituisce registri vuoti.
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

    # Restituisce i due registri.
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

    # Converte eventuali Timestamp nelle colonne object.
    for column in normalized.columns:
        normalized[column] = normalized[column].map(
            lambda value: value.isoformat() if isinstance(value, pd.Timestamp) else value
        )

    # Sostituisce NaN e NaT con None.
    normalized = normalized.astype(object).where(
        pd.notna(normalized),
        None,
    )

    # Restituisce una lista di dizionari.
    return normalized.to_dict(orient="records")


def _load_market_dataframe(
    market_data_path: Path,
) -> pd.DataFrame:
    """Carica e valida il dataset OHLCV sorgente."""

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


def _select_timeframe(
    dataframe: pd.DataFrame,
    selected_timeframe: SupportedTimeframe,
    source_minutes: int,
) -> pd.DataFrame:
    """Restituisce il dataset nel timeframe richiesto."""

    # M15 coincide con il dataset sorgente.
    if selected_timeframe == "M15":
        return dataframe.copy(deep=True)

    # Recupera la durata del timeframe richiesto.
    target_minutes = TIMEFRAME_MINUTES[selected_timeframe]

    try:
        # Aggrega solamente candele complete.
        return resample_ohlcv(
            dataframe=dataframe,
            source_minutes=source_minutes,
            target_minutes=target_minutes,
        )

    except TimeframeAggregationError as error:
        raise HTTPException(
            status_code=422,
            detail=(f"Impossibile generare il timeframe {selected_timeframe}: {error}"),
        ) from error


def create_app(
    config: APIConfig | None = None,
) -> FastAPI:
    """Crea e configura l'applicazione FastAPI."""

    # Usa la configurazione predefinita se non specificata.
    selected_config = config or APIConfig()

    # La prima versione deve restare PAPER_ONLY.
    if not selected_config.paper_trading_only:
        raise ValueError("Il backend API richiede paper_trading_only=true.")

    # Verifica il timeframe nativo.
    if selected_config.timeframe != "M15":
        raise ValueError("La prima versione API richiede un dataset sorgente M15.")

    # Verifica la durata sorgente.
    if selected_config.source_timeframe_minutes != 15:
        raise ValueError("Il timeframe sorgente deve essere pari a quindici minuti.")

    # Crea l'applicazione FastAPI.
    app = FastAPI(
        title="AI Trading Indicator API",
        description=(
            "API read-only per dati OHLCV multi-timeframe, segnali, esiti e statistiche Live Paper."
        ),
        version="0.2.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Abilita il collegamento dal frontend Next.js.
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
        """Restituisce le informazioni principali dell'API."""

        return {
            "application": "AI Trading Indicator API",
            "version": "0.2.0",
            "mode": "PAPER_ONLY",
            "symbol": selected_config.symbol,
            "source_timeframe": (selected_config.timeframe),
            "documentation": "/docs",
        }

    @app.get("/api/v1/health")
    def health() -> dict[str, object]:
        """Restituisce lo stato dei componenti locali."""

        # Controlla la disponibilità delle sorgenti.
        market_data_exists = Path(selected_config.market_data_path).exists()

        database_exists = Path(selected_config.database_path).exists()

        return {
            "status": "healthy",
            "mode": "PAPER_ONLY",
            "market_data_available": market_data_exists,
            "database_available": database_exists,
            "symbol": selected_config.symbol,
            "timeframe": selected_config.timeframe,
        }

    @app.get("/api/v1/market/timeframes")
    def get_timeframes() -> dict[str, object]:
        """Restituisce i timeframe disponibili e futuri."""

        return {
            "source_timeframe": (selected_config.timeframe),
            "timeframes": [
                {
                    "code": "M1",
                    "minutes": 1,
                    "available": False,
                    "native": False,
                    "reason": ("Richiede dati nativi M1 dal provider reale."),
                },
                {
                    "code": "M5",
                    "minutes": 5,
                    "available": False,
                    "native": False,
                    "reason": ("Richiede dati nativi M5 dal provider reale."),
                },
                {
                    "code": "M15",
                    "minutes": 15,
                    "available": True,
                    "native": True,
                    "reason": None,
                },
                {
                    "code": "H1",
                    "minutes": 60,
                    "available": True,
                    "native": False,
                    "reason": None,
                },
                {
                    "code": "H4",
                    "minutes": 240,
                    "available": True,
                    "native": False,
                    "reason": None,
                },
                {
                    "code": "D1",
                    "minutes": 1440,
                    "available": True,
                    "native": False,
                    "reason": None,
                },
            ],
        }

    @app.get("/api/v1/market/candles")
    def get_candles(
        timeframe: Annotated[
            SupportedTimeframe,
            Query(),
        ] = "M15",
        limit: int = Query(
            default=500,
            ge=1,
            le=5000,
        ),
    ) -> dict[str, object]:
        """Restituisce le candele nel timeframe richiesto."""

        # Carica il dataset sorgente M15.
        source_dataframe = _load_market_dataframe(Path(selected_config.market_data_path))

        # Genera il timeframe richiesto.
        timeframe_dataframe = _select_timeframe(
            dataframe=source_dataframe,
            selected_timeframe=timeframe,
            source_minutes=(selected_config.source_timeframe_minutes),
        )

        # Mantiene solamente le ultime righe richieste.
        selected_dataframe = timeframe_dataframe.tail(limit).reset_index(drop=True)

        return {
            "symbol": selected_config.symbol,
            "timeframe": timeframe,
            "source_timeframe": (selected_config.timeframe),
            "timezone": "UTC",
            "count": len(selected_dataframe),
            "candles": _dataframe_to_records(selected_dataframe),
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

        # Legge il database.
        signals, _ = _read_database(selected_config.database_path)

        # Mantiene solamente gli ultimi segnali.
        selected_signals = signals.tail(limit).reset_index(drop=True)

        return {
            "mode": "PAPER_ONLY",
            "count": len(selected_signals),
            "signals": _dataframe_to_records(selected_signals),
        }

    @app.get("/api/v1/outcomes")
    def get_outcomes(
        limit: int = Query(
            default=200,
            ge=1,
            le=5000,
        ),
    ) -> dict[str, object]:
        """Restituisce gli esiti conclusivi Live Paper."""

        # Legge il database.
        _, outcomes = _read_database(selected_config.database_path)

        # Mantiene solamente gli ultimi esiti.
        selected_outcomes = outcomes.tail(limit).reset_index(drop=True)

        return {
            "mode": "PAPER_ONLY",
            "count": len(selected_outcomes),
            "outcomes": _dataframe_to_records(selected_outcomes),
        }

    @app.get("/api/v1/statistics")
    def get_statistics() -> dict[str, object]:
        """Restituisce le statistiche aggregate Live Paper."""

        # Legge segnali ed esiti.
        signals, outcomes = _read_database(selected_config.database_path)

        # Restituisce uno stato iniziale senza segnali.
        if signals.empty:
            return {
                "mode": "PAPER_ONLY",
                "data_available": False,
                "statistics": None,
            }

        try:
            # Genera le statistiche aggregate.
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
            "statistics": statistics.to_dict(),
        }

    @app.get("/api/v1/system/status")
    def get_system_status() -> dict[str, object]:
        """Restituisce lo stato sintetico del sistema."""

        # Legge segnali ed esiti correnti.
        signals, outcomes = _read_database(selected_config.database_path)

        # Recupera l'ultimo timestamp disponibile.
        latest_signal_timestamp = None

        if not signals.empty:
            latest_signal_timestamp = str(signals.iloc[-1]["timestamp"])

        return {
            "api_status": "ONLINE",
            "engine_mode": "LIVE_PAPER",
            "paper_trading_only": True,
            "real_orders_enabled": False,
            "symbol": selected_config.symbol,
            "timeframe": selected_config.timeframe,
            "available_timeframes": [
                "M15",
                "H1",
                "H4",
                "D1",
            ],
            "signal_count": len(signals),
            "outcome_count": len(outcomes),
            "latest_signal_timestamp": (latest_signal_timestamp),
        }

    # Restituisce l'applicazione configurata.
    return app


# Crea l'istanza utilizzata da Uvicorn.
app = create_app()
