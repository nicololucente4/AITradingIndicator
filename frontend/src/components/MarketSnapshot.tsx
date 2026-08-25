"use client";

// Importa gli hook React.
import {
  useEffect,
  useState,
} from "react";

import type {
  AvailableTimeframe,
  Candle,
} from "@/src/types/market";

// Proprietà ricevute dal componente.
type MarketSnapshotProps = {
  candles: Candle[];
  symbol: string;
  timeframe: AvailableTimeframe;
};

// Risposta dell'endpoint tick MT5.
type LiveMarketTick = {
  symbol: string;
  bid: number;
  ask: number;
  mid: number;
  spread: number;
  timestamp: string;
  source: string;
};

// Stato del prezzo live.
type LiveTickState = {
  tick: LiveMarketTick | null;
  loading: boolean;
  available: boolean;
};

// URL del backend FastAPI.
const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://127.0.0.1:8000";

// Intervallo di aggiornamento del tick.
const LIVE_TICK_INTERVAL_MILLISECONDS =
  2000;

/**
 * Formatta un prezzo in base allo strumento.
 */
function formatPrice(
  value: number,
  symbol: string
): string {
  // L'oro viene mostrato con due decimali.
  if (
    symbol.toUpperCase() ===
    "XAUUSD"
  ) {
    return value.toFixed(2);
  }

  // Le coppie con JPY vengono mostrate con tre decimali.
  if (
    symbol
      .toUpperCase()
      .endsWith("JPY")
  ) {
    return value.toFixed(3);
  }

  // Le altre coppie Forex usano cinque decimali.
  return value.toFixed(5);
}

/**
 * Formatta il volume.
 */
function formatVolume(
  value: number
): string {
  return new Intl.NumberFormat(
    "it-IT",
    {
      maximumFractionDigits: 0,
    }
  ).format(value);
}

/**
 * Formatta un timestamp in UTC.
 */
function formatUtcTimestamp(
  timestamp: string
): string {
  return new Date(
    timestamp
  ).toLocaleString(
    "it-IT",
    {
      timeZone: "UTC",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }
  );
}

/**
 * Mostra prezzo live MT5 e ultima candela chiusa.
 */
export default function MarketSnapshot({
  candles,
  symbol,
  timeframe,
}: MarketSnapshotProps) {
  // Memorizza il tick live ricevuto da FastAPI.
  const [
    liveTickState,
    setLiveTickState,
  ] = useState<LiveTickState>({
    tick: null,
    loading: true,
    available: false,
  });

  useEffect(() => {
    // Impedisce aggiornamenti dopo lo smontaggio.
    let componentMounted = true;

    /**
     * Recupera il tick live senza aggiornare la pagina.
     */
    async function loadLiveTick():
      Promise<void> {
      try {
        // Prepara il simbolo per l'URL.
        const searchParameters =
          new URLSearchParams({
            symbol,
          });

        // Interroga l'endpoint MT5 live.
        const response = await fetch(
          `${API_BASE_URL}/api/v1/market/tick?${searchParameters.toString()}`,
          {
            cache: "no-store",
          }
        );

        // MT5 può non essere disponibile sul PC di sviluppo.
        if (!response.ok) {
          if (componentMounted) {
            setLiveTickState({
              tick: null,
              loading: false,
              available: false,
            });
          }

          return;
        }

        // Converte la risposta.
        const tick =
          (await response.json()) as
            LiveMarketTick;

        // Aggiorna il pannello se ancora montato.
        if (componentMounted) {
          setLiveTickState({
            tick,
            loading: false,
            available: true,
          });
        }
      } catch {
        // Mantiene il frontend operativo senza MT5.
        if (componentMounted) {
          setLiveTickState({
            tick: null,
            loading: false,
            available: false,
          });
        }
      }
    }

    // Carica immediatamente il primo tick.
    void loadLiveTick();

    // Aggiorna il tick ogni due secondi.
    const intervalIdentifier =
      window.setInterval(
        () => {
          void loadLiveTick();
        },
        LIVE_TICK_INTERVAL_MILLISECONDS
      );

    // Interrompe il polling quando cambia simbolo
    // oppure il componente viene smontato.
    return () => {
      componentMounted = false;

      window.clearInterval(
        intervalIdentifier
      );
    };
  }, [symbol]);

  // Recupera l'ultima candela chiusa.
  const latestCandle =
    candles.length > 0
      ? candles[
          candles.length - 1
        ]
      : null;

  // Recupera la candela precedente.
  const previousCandle =
    candles.length > 1
      ? candles[
          candles.length - 2
        ]
      : null;

  // Calcola la variazione tra le ultime due chiusure.
  const absoluteChange =
    latestCandle !== null &&
    previousCandle !== null
      ? latestCandle.close -
        previousCandle.close
      : 0;

  // Calcola la variazione percentuale.
  const percentageChange =
    previousCandle === null ||
    previousCandle.close === 0
      ? 0
      : (
          absoluteChange /
          previousCandle.close
        ) * 100;

  // Determina il colore della variazione.
  const changeColor =
    absoluteChange > 0
      ? "text-[#089981]"
      : absoluteChange < 0
        ? "text-[#f23645]"
        : "text-slate-400";

  return (
    <div className="mb-4 grid gap-3 lg:grid-cols-2">
      <section className="rounded-lg border border-blue-500/30 bg-blue-500/5 p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-white">
              Prezzo live MT5
            </h3>

            <p className="mt-1 text-xs text-slate-500">
              Tick corrente, separato dalle candele chiuse.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span
              className={
                liveTickState.available
                  ? "h-2 w-2 rounded-full bg-green-400"
                  : liveTickState.loading
                    ? "h-2 w-2 rounded-full bg-amber-400"
                    : "h-2 w-2 rounded-full bg-slate-600"
              }
            />

            <span className="text-xs text-slate-400">
              {liveTickState.available
                ? "Live"
                : liveTickState.loading
                  ? "Connessione..."
                  : "Non disponibile"}
            </span>
          </div>
        </div>

        {liveTickState.tick !== null ? (
          <>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div>
                <div className="text-xs text-slate-500">
                  Bid
                </div>

                <div className="mt-1 font-mono text-base font-semibold text-red-300">
                  {formatPrice(
                    liveTickState.tick.bid,
                    symbol
                  )}
                </div>
              </div>

              <div>
                <div className="text-xs text-slate-500">
                  Ask
                </div>

                <div className="mt-1 font-mono text-base font-semibold text-green-300">
                  {formatPrice(
                    liveTickState.tick.ask,
                    symbol
                  )}
                </div>
              </div>

              <div>
                <div className="text-xs text-slate-500">
                  Mid
                </div>

                <div className="mt-1 font-mono text-base font-semibold text-white">
                  {formatPrice(
                    liveTickState.tick.mid,
                    symbol
                  )}
                </div>
              </div>

              <div>
                <div className="text-xs text-slate-500">
                  Spread
                </div>

                <div className="mt-1 font-mono text-base font-semibold text-amber-300">
                  {formatPrice(
                    liveTickState.tick.spread,
                    symbol
                  )}
                </div>
              </div>
            </div>

            <div className="mt-3 text-xs text-slate-500">
              Ultimo tick:{" "}
              {formatUtcTimestamp(
                liveTickState.tick.timestamp
              )}
              {" UTC"}
            </div>
          </>
        ) : (
          <div className="flex min-h-16 items-center text-sm text-slate-500">
            Il prezzo live sarà disponibile sul PC di test con MT5 collegato.
          </div>
        )}
      </section>

      <section className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-white">
              Ultima candela chiusa
            </h3>

            <p className="mt-1 text-xs text-slate-500">
              Dato utilizzabile per grafico e modello ML.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-white">
              {symbol}
            </span>

            <span className="rounded bg-slate-800 px-2 py-1 text-xs font-medium text-slate-300">
              {timeframe}
            </span>
          </div>
        </div>

        {latestCandle !== null ? (
          <>
            <div className="mb-3 flex flex-wrap items-baseline gap-3">
              <div className="font-mono text-xl font-semibold text-white">
                {formatPrice(
                  latestCandle.close,
                  symbol
                )}
              </div>

              <div
                className={`font-mono text-sm font-medium ${changeColor}`}
              >
                {absoluteChange >= 0
                  ? "+"
                  : ""}
                {formatPrice(
                  absoluteChange,
                  symbol
                )}

                {" ("}

                {percentageChange >= 0
                  ? "+"
                  : ""}
                {percentageChange.toFixed(
                  3
                )}
                {"%)"}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 font-mono text-xs sm:grid-cols-5">
              <div>
                <span className="text-slate-500">
                  O
                </span>

                <span className="ml-1 text-slate-300">
                  {formatPrice(
                    latestCandle.open,
                    symbol
                  )}
                </span>
              </div>

              <div>
                <span className="text-slate-500">
                  H
                </span>

                <span className="ml-1 text-[#089981]">
                  {formatPrice(
                    latestCandle.high,
                    symbol
                  )}
                </span>
              </div>

              <div>
                <span className="text-slate-500">
                  L
                </span>

                <span className="ml-1 text-[#f23645]">
                  {formatPrice(
                    latestCandle.low,
                    symbol
                  )}
                </span>
              </div>

              <div>
                <span className="text-slate-500">
                  C
                </span>

                <span className="ml-1 text-slate-300">
                  {formatPrice(
                    latestCandle.close,
                    symbol
                  )}
                </span>
              </div>

              <div>
                <span className="text-slate-500">
                  Vol
                </span>

                <span className="ml-1 text-purple-300">
                  {formatVolume(
                    latestCandle.volume
                  )}
                </span>
              </div>
            </div>

            <div className="mt-3 text-xs text-slate-600">
              Apertura candela:{" "}
              {formatUtcTimestamp(
                latestCandle.timestamp
              )}
              {" UTC"}
            </div>
          </>
        ) : (
          <div className="flex min-h-16 items-center text-sm text-slate-500">
            Nessuna candela chiusa disponibile.
          </div>
        )}
      </section>
    </div>
  );
}