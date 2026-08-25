"""Endpoint FastAPI read-only delle operazioni paper."""

# Importa SQLite per leggere il registro delle operazioni.
import sqlite3

# Importa Path per gestire il percorso del database.
from pathlib import Path

# Importa Literal per limitare i valori dello stato.
from typing import Literal

# Importa FastAPI.
from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

# Crea il router pubblico.
router = APIRouter(
    prefix="/api/v1",
    tags=["paper-trades"],
)

# Percorso operativo predefinito.
PAPER_TRADES_DATABASE_PATH = Path("data/live_paper/live_paper.db")


class PaperTradesAPIError(ValueError):
    """Errore generato dalla lettura dei paper trade."""


def normalize_optional_symbol(
    symbol: str | None,
) -> str | None:
    """Normalizza un simbolo opzionale."""

    # L'assenza del filtro mantiene tutti i simboli.
    if symbol is None:
        return None

    # Il simbolo deve essere testuale.
    if not isinstance(
        symbol,
        str,
    ):
        raise PaperTradesAPIError("symbol deve essere una stringa.")

    # Normalizza il valore.
    selected_symbol = symbol.strip().upper()

    # Una stringa vuota equivale a nessun filtro.
    if not selected_symbol:
        return None

    return selected_symbol


def _table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    """Verifica se una tabella SQLite esiste."""

    cursor = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        LIMIT 1
        """,
        (table_name,),
    )

    return cursor.fetchone() is not None


def _row_to_dict(
    row: sqlite3.Row,
) -> dict[str, object]:
    """Converte una riga SQLite in un record JSON."""

    return {key: row[key] for key in row.keys()}


def load_paper_trades(
    *,
    database_path: str | Path,
    symbol: str | None = None,
    status: Literal[
        "OPEN",
        "CLOSED",
    ]
    | None = None,
    limit: int = 200,
) -> list[dict[str, object]]:
    """Carica i paper trade applicando filtri opzionali."""

    # Il limite deve essere positivo.
    if limit <= 0:
        raise PaperTradesAPIError("limit deve essere maggiore di zero.")

    # Normalizza il simbolo.
    selected_symbol = normalize_optional_symbol(symbol)

    # Converte il percorso.
    selected_path = Path(database_path)

    # Un database assente equivale a un registro vuoto.
    if not selected_path.exists():
        return []

    try:
        # Apre il database in modalità read-only logica.
        with sqlite3.connect(selected_path) as connection:
            # Consente di leggere le colonne per nome.
            connection.row_factory = sqlite3.Row

            # Un database precedente può non avere la tabella.
            if not _table_exists(
                connection,
                "paper_trades",
            ):
                return []

            # Prepara filtri e valori SQL.
            conditions: list[str] = []
            parameters: list[object] = []

            # Applica il filtro del simbolo.
            if selected_symbol is not None:
                conditions.append("symbol = ?")

                parameters.append(selected_symbol)

            # Applica il filtro dello stato.
            if status is not None:
                conditions.append("status = ?")

                parameters.append(status)

            # Costruisce la clausola WHERE.
            where_clause = ""

            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

            # Aggiunge il limite come ultimo parametro.
            parameters.append(limit)

            # Legge prima le operazioni più recenti.
            cursor = connection.execute(
                f"""
                SELECT
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
                FROM paper_trades
                {where_clause}
                ORDER BY opened_at_utc DESC
                LIMIT ?
                """,
                tuple(parameters),
            )

            # Converte le righe in record serializzabili.
            return [_row_to_dict(row) for row in cursor.fetchall()]

    except sqlite3.Error as error:
        raise PaperTradesAPIError(
            f"Impossibile leggere il registro paper trade: {error}."
        ) from error


def count_trade_statuses(
    *,
    database_path: str | Path,
    symbol: str | None = None,
) -> dict[str, int]:
    """Conta operazioni aperte e chiuse."""

    # Carica tutti i trade necessari al riepilogo.
    trades = load_paper_trades(
        database_path=database_path,
        symbol=symbol,
        limit=5000,
    )

    # Conta le operazioni ancora aperte.
    open_count = sum(1 for trade in trades if trade["status"] == "OPEN")

    # Conta le operazioni concluse.
    closed_count = sum(1 for trade in trades if trade["status"] == "CLOSED")

    return {
        "total": len(trades),
        "open": open_count,
        "closed": closed_count,
    }


@router.get("/trades")
def get_paper_trades(
    symbol: str | None = Query(
        default=None,
        max_length=32,
    ),
    status: Literal[
        "OPEN",
        "CLOSED",
    ]
    | None = Query(
        default=None,
    ),
    limit: int = Query(
        default=200,
        ge=1,
        le=5000,
    ),
) -> dict[str, object]:
    """Restituisce lo storico delle operazioni paper."""

    try:
        # Normalizza il simbolo richiesto.
        selected_symbol = normalize_optional_symbol(symbol)

        # Carica i trade applicando tutti i filtri.
        trades = load_paper_trades(
            database_path=(PAPER_TRADES_DATABASE_PATH),
            symbol=selected_symbol,
            status=status,
            limit=limit,
        )

        # Calcola il riepilogo dei trade già filtrati.
        open_count = sum(1 for trade in trades if trade["status"] == "OPEN")

        closed_count = sum(1 for trade in trades if trade["status"] == "CLOSED")

        # Restituisce una risposta read-only.
        return {
            "mode": "PAPER_ONLY",
            "real_orders_enabled": False,
            "symbol": selected_symbol,
            "status": status,
            "count": len(trades),
            "summary": {
                "total": len(trades),
                "open": open_count,
                "closed": closed_count,
            },
            "trades": trades,
        }

    except PaperTradesAPIError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error
