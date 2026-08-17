import CandlestickChart from "@/src/components/CandlestickChart";
import Header from "@/src/components/Header";
import MarketStatus from "@/src/components/MarketStatus";

import {
  getCandles,
  getHealth,
  getSignals,
  getSystemStatus,
} from "@/src/services/api";

import type {
  Candle,
  SignalRecord,
} from "@/src/types/market";

// Forza il rendering dinamico della pagina.
//
// La dashboard legge dati aggiornati da FastAPI e non deve
// essere generata staticamente durante la build di Next.js.
export const dynamic = "force-dynamic";

// Impedisce la memorizzazione statica della pagina.
export const revalidate = 0;

export default async function Home() {
  // Valori utilizzati quando FastAPI non è disponibile.
  let online = false;
  let symbol = "EURUSD";
  let timeframe = "M15";
  let outcomeCount = 0;

  // Dati caricati dal backend FastAPI.
  let candles: Candle[] = [];
  let signals: SignalRecord[] = [];

  try {
    // Interroga gli endpoint FastAPI in parallelo.
    const [
      health,
      status,
      marketResponse,
      signalsResponse,
    ] = await Promise.all([
      getHealth(),
      getSystemStatus(),
      getCandles(300),
      getSignals(200),
    ]);

    // Aggiorna lo stato generale del terminale.
    online = health.status === "healthy";
    symbol = status.symbol;
    timeframe = status.timeframe;
    outcomeCount = status.outcome_count;

    // Memorizza i dati di mercato.
    candles = marketResponse.candles;
    signals = signalsResponse.signals;
  } catch (error) {
    // Mostra l'errore nel terminale Next.js.
    console.error(
      "Impossibile caricare i dati FastAPI:",
      error
    );

    // Mantiene disponibile l'interfaccia in modalità offline.
    online = false;
  }

  // Calcola il numero dei segnali LONG.
  const longCount = signals.filter(
    (signal) => signal.signal === "LONG"
  ).length;

  // Calcola il numero dei segnali SHORT.
  const shortCount = signals.filter(
    (signal) => signal.signal === "SHORT"
  ).length;

  // Calcola il numero dei segnali NO_TRADE.
  const noTradeCount = signals.filter(
    (signal) => signal.signal === "NO_TRADE"
  ).length;

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <Header
        symbol={symbol}
        timeframe={timeframe}
      />

      <div className="space-y-5 p-5">
        <section className="grid grid-cols-2 gap-4 md:grid-cols-5">
          <MarketStatus online={online} />

          <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
            <div className="text-sm text-slate-400">
              LONG
            </div>

            <div className="mt-2 text-lg font-bold text-green-400">
              {longCount}
            </div>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
            <div className="text-sm text-slate-400">
              SHORT
            </div>

            <div className="mt-2 text-lg font-bold text-red-400">
              {shortCount}
            </div>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
            <div className="text-sm text-slate-400">
              NO TRADE
            </div>

            <div className="mt-2 text-lg font-bold text-slate-300">
              {noTradeCount}
            </div>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
            <div className="text-sm text-slate-400">
              Outcomes
            </div>

            <div className="mt-2 text-lg font-bold text-blue-400">
              {outcomeCount}
            </div>
          </div>
        </section>

        <section className="rounded-xl border border-slate-800 bg-slate-900 p-5">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">
                {symbol} Chart
              </h2>

              <p className="mt-1 text-xs text-slate-400">
                {timeframe} · UTC · Live Paper
              </p>
            </div>

            <div className="text-xs text-slate-500">
              {candles.length} candele
            </div>
          </div>

          {candles.length > 0 ? (
            <CandlestickChart
              candles={candles}
              signals={signals}
            />
          ) : (
            <div className="flex h-[600px] items-center justify-center rounded-lg border border-dashed border-slate-700 text-slate-500">
              Nessuna candela disponibile
            </div>
          )}
        </section>

        <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
            <h3 className="font-semibold">
              Signals
            </h3>

            <p className="mt-2 text-sm text-slate-400">
              {signals.length} segnali registrati
            </p>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
            <h3 className="font-semibold">
              Outcomes
            </h3>

            <p className="mt-2 text-sm text-slate-400">
              {outcomeCount} esiti disponibili
            </p>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
            <h3 className="font-semibold">
              Statistics
            </h3>

            <p className="mt-2 text-sm text-slate-400">
              Metriche Live Paper
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}