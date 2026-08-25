"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  getLiveTick,
} from "@/src/services/api";

import type {
  LiveMarketTick,
} from "@/src/types/market";

// Intervallo di aggiornamento del prezzo live.
const LIVE_TICK_INTERVAL_MS = 1000;

// Età massima oltre la quale il tick è considerato fermo.
const STALE_TICK_THRESHOLD_MS = 10000;

// Proprietà del componente.
type LivePriceProps = {
  symbol: string;
};

// Stato del feed tick.
type LiveTickStatus =
  | "LOADING"
  | "LIVE"
  | "STALE"
  | "UNAVAILABLE";

// Direzione dell'ultimo aggiornamento.
type TickDirection =
  | "UP"
  | "DOWN"
  | "UNCHANGED";

/**
 * Restituisce il numero di decimali appropriato.
 */
function getPricePrecision(
  symbol: string
): number {
  // Le coppie con JPY utilizzano normalmente tre decimali.
  if (
    symbol.includes("JPY")
  ) {
    return 3;
  }

  // L'oro viene mostrato con due decimali.
  if (
    symbol === "XAUUSD"
  ) {
    return 2;
  }

  // Le altre coppie Forex usano cinque decimali.
  return 5;
}

/**
 * Formatta un prezzo in base allo strumento.
 */
function formatPrice(
  value: number,
  symbol: string
): string {
  return value.toFixed(
    getPricePrecision(
      symbol
    )
  );
}

/**
 * Formatta il timestamp UTC del tick.
 */
function formatTickTime(
  timestamp: string
): string {
  return new Date(
    timestamp
  ).toLocaleTimeString(
    "it-IT",
    {
      timeZone: "UTC",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }
  );
}

/**
 * Mostra il prezzo tick live aggiornato ogni secondo.
 */
export default function LivePrice({
  symbol,
}: LivePriceProps) {
  // Tick live corrente.
  const [
    tick,
    setTick,
  ] = useState<LiveMarketTick | null>(
    null
  );

  // Stato della connessione tick.
  const [
    status,
    setStatus,
  ] = useState<LiveTickStatus>(
    "LOADING"
  );

  // Direzione dell'ultimo movimento.
  const [
    direction,
    setDirection,
  ] = useState<TickDirection>(
    "UNCHANGED"
  );

  // Evita richieste sovrapposte.
  const requestInProgressRef =
    useRef(false);

  // Conserva il prezzo precedente.
  const previousMidRef =
    useRef<number | null>(
      null
    );

  // Conserva il simbolo associato all'ultimo tick.
  const activeSymbolRef =
    useRef(symbol);

  /**
   * Recupera un tick dal backend FastAPI.
   */
  const refreshTick =
    useCallback(
      async (): Promise<void> => {
        // Evita l'avvio di una seconda richiesta.
        if (
          requestInProgressRef.current
        ) {
          return;
        }

        // Registra la richiesta in corso.
        requestInProgressRef.current =
          true;

        try {
          // Recupera il tick live.
          const receivedTick =
            await getLiveTick(
              symbol
            );

          // Ignora una risposta riferita a un simbolo precedente.
          if (
            activeSymbolRef.current !==
            symbol
          ) {
            return;
          }

          // Recupera il prezzo precedente.
          const previousMid =
            previousMidRef.current;

          // Determina la direzione del movimento.
          if (
            previousMid === null ||
            receivedTick.mid ===
              previousMid
          ) {
            setDirection(
              "UNCHANGED"
            );
          } else if (
            receivedTick.mid >
            previousMid
          ) {
            setDirection(
              "UP"
            );
          } else {
            setDirection(
              "DOWN"
            );
          }

          // Conserva il nuovo prezzo.
          previousMidRef.current =
            receivedTick.mid;

          // Aggiorna il tick mostrato.
          setTick(
            receivedTick
          );

          // Calcola l'età del tick.
          const tickAge =
            Date.now() -
            Date.parse(
              receivedTick.timestamp
            );

          // Distingue tick live e tick fermo.
          setStatus(
            tickAge >
              STALE_TICK_THRESHOLD_MS
              ? "STALE"
              : "LIVE"
          );
        } catch {
          // Indica che il feed non è disponibile.
          if (
            activeSymbolRef.current ===
            symbol
          ) {
            setStatus(
              "UNAVAILABLE"
            );
          }
        } finally {
          // Libera il controllo della richiesta.
          requestInProgressRef.current =
            false;
        }
      },
      [symbol]
    );

  useEffect(() => {
    // Collega il ciclo al simbolo corrente.
    activeSymbolRef.current =
      symbol;

    // Azzera solamente i riferimenti non React.
    previousMidRef.current =
      null;

    requestInProgressRef.current =
      false;

    // Il primo aggiornamento avviene in modo asincrono.
    const initialTimeout =
      window.setTimeout(
        () => {
          void refreshTick();
        },
        0
      );

    // Aggiorna il prezzo ogni secondo.
    const intervalIdentifier =
      window.setInterval(
        () => {
          void refreshTick();
        },
        LIVE_TICK_INTERVAL_MS
      );

    // Arresta timer e richieste obsolete al cambio simbolo.
    return () => {
      window.clearTimeout(
        initialTimeout
      );

      window.clearInterval(
        intervalIdentifier
      );

      activeSymbolRef.current =
        "";
    };
  }, [
    refreshTick,
    symbol,
  ]);

  // Determina il colore del prezzo.
  const priceColor =
    direction === "UP"
      ? "text-emerald-400"
      : direction === "DOWN"
        ? "text-red-400"
        : "text-white";

  // Visualizza lo stato prima del primo tick.
  if (
    tick === null ||
    tick.symbol !== symbol
  ) {
    return (
      <div className="min-w-[260px] rounded-lg border border-slate-800 bg-slate-900 px-4 py-3">
        <div className="flex items-center justify-between gap-4">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Prezzo live MT5
          </span>

          <span
            className={
              status ===
              "UNAVAILABLE"
                ? "text-[10px] font-bold text-amber-400"
                : "text-[10px] font-bold text-blue-400"
            }
          >
            {status ===
            "UNAVAILABLE"
              ? "NON DISPONIBILE"
              : "CONNESSIONE..."}
          </span>
        </div>

        <div className="mt-2 font-mono text-lg font-semibold text-slate-500">
          N/D
        </div>

        <div className="mt-2 text-[10px] text-slate-600">
          Il modello utilizza esclusivamente candele chiuse.
        </div>
      </div>
    );
  }

  return (
    <div className="min-w-[280px] rounded-lg border border-slate-800 bg-slate-900 px-4 py-3">
      <div className="flex items-center justify-between gap-4">
        <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
          Prezzo live MT5
        </span>

        <div className="flex items-center gap-1.5">
          <span
            className={
              status === "LIVE"
                ? "h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_7px_rgba(52,211,153,0.8)]"
                : "h-2 w-2 rounded-full bg-amber-400"
            }
          />

          <span
            className={
              status === "LIVE"
                ? "text-[10px] font-bold text-emerald-400"
                : "text-[10px] font-bold text-amber-400"
            }
          >
            {status === "LIVE"
              ? "LIVE"
              : status === "STALE"
                ? "DATO FERMO"
                : "NON DISPONIBILE"}
          </span>
        </div>
      </div>

      <div className="mt-2 flex items-end justify-between gap-4">
        <div>
          <div
            className={`font-mono text-2xl font-bold tabular-nums ${priceColor}`}
          >
            {formatPrice(
              tick.mid,
              symbol
            )}
          </div>

          <div className="mt-1 font-mono text-[11px] text-slate-500">
            {formatTickTime(
              tick.timestamp
            )}
            {" UTC"}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-right font-mono text-[11px]">
          <div>
            <span className="text-slate-500">
              BID
            </span>

            <span className="ml-1 text-slate-300">
              {formatPrice(
                tick.bid,
                symbol
              )}
            </span>
          </div>

          <div>
            <span className="text-slate-500">
              ASK
            </span>

            <span className="ml-1 text-slate-300">
              {formatPrice(
                tick.ask,
                symbol
              )}
            </span>
          </div>

          <div className="col-span-2">
            <span className="text-slate-500">
              SPREAD
            </span>

            <span className="ml-1 text-slate-300">
              {formatPrice(
                tick.spread,
                symbol
              )}
            </span>
          </div>
        </div>
      </div>

      <div className="mt-2 text-[10px] text-slate-600">
        Aggiornamento ogni 1 secondo. Decisioni solo su candele chiuse.
      </div>
    </div>
  );
}