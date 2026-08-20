// Importa i componenti del terminale.
import Header from "@/src/components/Header";
import MarketSnapshot from "@/src/components/MarketSnapshot";
import MarketStatus from "@/src/components/MarketStatus";
import OutcomesTable from "@/src/components/OutcomesTable";
import SignalsTable from "@/src/components/SignalsTable";
import StatisticsPanel from "@/src/components/StatisticsPanel";
import TimeframeSelector from "@/src/components/TimeframeSelector";
import UnifiedMarketChart from "@/src/components/UnifiedMarketChart";

// Importa le funzioni che interrogano FastAPI.
import {
  getCandles,
  getHealth,
  getOutcomes,
  getSignals,
  getStatistics,
  getSystemStatus,
} from "@/src/services/api";

// Importa i tipi condivisi.
import type {
  AvailableTimeframe,
  Candle,
  LivePaperStatistics,
  OutcomeRecord,
  SignalRecord,
} from "@/src/types/market";

// Forza il rendering dinamico della dashboard.
export const dynamic = "force-dynamic";

// Disabilita la cache statica della pagina.
export const revalidate = 0;

// Elenca i timeframe attualmente disponibili.
const AVAILABLE_TIMEFRAMES: AvailableTimeframe[] = [
  "M15",
  "H1",
  "H4",
  "D1",
];

// Rappresenta i parametri URL ricevuti dalla pagina.
type HomePageProps = {
  searchParams: Promise<{
    timeframe?: string | string[];
  }>;
};

/**
 * Controlla e normalizza il timeframe ricevuto dall'URL.
 */
function selectTimeframe(
  value: string | string[] | undefined
): AvailableTimeframe {
  // Se il parametro è ripetuto, utilizza il primo valore.
  const selectedValue = Array.isArray(value)
    ? value[0]
    : value;

  // Utilizza M15 quando il valore è assente o non supportato.
  if (
    selectedValue === undefined ||
    !AVAILABLE_TIMEFRAMES.includes(
      selectedValue as AvailableTimeframe
    )
  ) {
    return "M15";
  }

  // Restituisce il timeframe validato.
  return selectedValue as AvailableTimeframe;
}

/**
 * Visualizza il terminale AI Trading Indicator.
 */
export default async function Home({
  searchParams,
}: HomePageProps) {
  // Legge i parametri URL asincroni di Next.js.
  const resolvedSearchParams =
    await searchParams;

  // Determina il timeframe selezionato.
  const selectedTimeframe =
    selectTimeframe(
      resolvedSearchParams.timeframe
    );

  // Definisce i valori di fallback.
  let online = false;
  let symbol = "EURUSD";

  // Inizializza i dati applicativi.
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
      getCandles(
        selectedTimeframe,
        500
      ),
      getSignals(200),
      getOutcomes(200),
      getStatistics(),
    ]);

    // Aggiorna lo stato del terminale.
    online = health.status === "healthy";
    symbol = status.symbol;

    // Memorizza i dati ricevuti da FastAPI.
    candles = marketResponse.candles;
    signals = signalsResponse.signals;
    outcomes = outcomesResponse.outcomes;
    statistics =
      statisticsResponse.statistics;
  } catch (error) {
    // Registra l'errore nel terminale Next.js.
    console.error(
      "Impossibile caricare i dati FastAPI:",
      error
    );

    // Mantiene la dashboard disponibile in modalità offline.
    online = false;
  }

  // I segnali attuali sono prodotti solamente sul timeframe M15.
  const chartSignals =
    selectedTimeframe === "M15"
      ? signals
      : [];

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
    (signal) =>
      signal.signal === "NO_TRADE"
  ).length;

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <Header
        symbol={symbol}
        timeframe={selectedTimeframe}
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
          <div className="mb-4 flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            <div>
              <h2 className="text-lg font-semibold">
                {symbol} Chart
              </h2>

              <p className="mt-1 text-xs text-slate-400">
                {selectedTimeframe}
                {" · UTC · Live Paper · "}
                {candles.length}
                {" candele"}
              </p>
            </div>

            <TimeframeSelector
              selectedTimeframe={
                selectedTimeframe
              }
            />
          </div>

          {selectedTimeframe !== "M15" && (
            <div className="mb-3 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-300">
              I segnali ML sono attualmente generati
              sul timeframe M15 e non vengono
              sovrapposti alle candele aggregate.
            </div>
          )}

          <MarketSnapshot
            candles={candles}
            symbol={symbol}
            timeframe={selectedTimeframe}
          />

          {candles.length > 0 ? (
            <UnifiedMarketChart
              key={selectedTimeframe}
              candles={candles}
              signals={chartSignals}
              timeframe={selectedTimeframe}
            />
          ) : (
            <div className="flex h-[600px] items-center justify-center rounded-lg border border-dashed border-slate-700 text-slate-500">
              Nessuna candela disponibile per{" "}
              {selectedTimeframe}
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