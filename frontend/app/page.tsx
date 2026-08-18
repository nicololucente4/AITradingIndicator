// Importa i componenti del terminale.
import CandlestickChart from "@/src/components/CandlestickChart";
import Header from "@/src/components/Header";
import MarketStatus from "@/src/components/MarketStatus";
import OutcomesTable from "@/src/components/OutcomesTable";
import SignalsTable from "@/src/components/SignalsTable";
import StatisticsPanel from "@/src/components/StatisticsPanel";

// Importa le funzioni che interrogano FastAPI.
import {
  getCandles,
  getHealth,
  getOutcomes,
  getSignals,
  getStatistics,
  getSystemStatus,
} from "@/src/services/api";

// Importa i tipi dei dati.
import type {
  Candle,
  LivePaperStatistics,
  OutcomeRecord,
  SignalRecord,
} from "@/src/types/market";

// Forza il rendering dinamico della dashboard.
export const dynamic = "force-dynamic";

// Disabilita la cache statica della pagina.
export const revalidate = 0;

/**
 * Visualizza il terminale AI Trading Indicator.
 */
export default async function Home() {
  // Definisce i valori di fallback.
  let online = false;
  let symbol = "EURUSD";
  let timeframe = "M15";

  // Inizializza i dataset.
  let candles: Candle[] = [];
  let signals: SignalRecord[] = [];
  let outcomes: OutcomeRecord[] = [];
  let statistics: LivePaperStatistics | null =
    null;

  try {
    // Interroga tutti gli endpoint FastAPI in parallelo.
    const [
      health,
      status,
      marketResponse,
      signalsResponse,
      outcomesResponse,
      statisticsResponse,
    ] = await Promise.all([
      getHealth(),
      getSystemStatus(),
      getCandles(300),
      getSignals(200),
      getOutcomes(200),
      getStatistics(),
    ]);

    // Aggiorna lo stato del terminale.
    online = health.status === "healthy";
    symbol = status.symbol;
    timeframe = status.timeframe;

    // Recupera i dati applicativi.
    candles = marketResponse.candles;
    signals = signalsResponse.signals;
    outcomes = outcomesResponse.outcomes;
    statistics = statisticsResponse.statistics;
  } catch (error) {
    // Registra l'errore sul terminale Next.js.
    console.error(
      "Impossibile caricare i dati FastAPI:",
      error
    );

    // Mantiene accessibile la pagina.
    online = false;
  }

  // Conta i segnali LONG.
  const longCount = signals.filter(
    (signal) => signal.signal === "LONG"
  ).length;

  // Conta i segnali SHORT.
  const shortCount = signals.filter(
    (signal) => signal.signal === "SHORT"
  ).length;

  // Conta i segnali NO_TRADE.
  const noTradeCount = signals.filter(
    (signal) => signal.signal === "NO_TRADE"
  ).length;

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <Header
        symbol={symbol}
        timeframe={timeframe}
        online={online}
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
              {outcomes.length}
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

        <section className="rounded-xl border border-slate-800 bg-slate-900 p-5">
          <h2 className="mb-4 text-lg font-semibold">
            Statistics
          </h2>

          <StatisticsPanel
            statistics={statistics}
          />
        </section>

        <section className="rounded-xl border border-slate-800 bg-slate-900">
          <div className="border-b border-slate-800 px-5 py-4">
            <h2 className="text-lg font-semibold">
              Signals
            </h2>
          </div>

          <SignalsTable signals={signals} />
        </section>

        <section className="rounded-xl border border-slate-800 bg-slate-900">
          <div className="border-b border-slate-800 px-5 py-4">
            <h2 className="text-lg font-semibold">
              Outcomes
            </h2>
          </div>

          <OutcomesTable outcomes={outcomes} />
        </section>
      </div>
    </main>
  );
}
