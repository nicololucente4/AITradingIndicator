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
  getTimeframes,
} from "@/src/services/api";

// Importa i tipi condivisi.
import type {
  AvailableTimeframe,
  Candle,
  LivePaperStatistics,
  OutcomeRecord,
  SignalRecord,
  TimeframeInformation,
} from "@/src/types/market";

// Forza il rendering dinamico della dashboard.
export const dynamic = "force-dynamic";

// Disabilita la cache statica della pagina.
export const revalidate = 0;

// Elenca tutti i timeframe professionali riconosciuti.
const SUPPORTED_TIMEFRAMES:
  AvailableTimeframe[] = [
    "M1",
    "M2",
    "M3",
    "M5",
    "M10",
    "M15",
    "M30",
    "H1",
    "H2",
    "H4",
    "H8",
    "H12",
    "D1",
    "W1",
  ];

// Catalogo minimo usato se FastAPI non è raggiungibile.
const FALLBACK_TIMEFRAMES:
  TimeframeInformation[] =
  SUPPORTED_TIMEFRAMES.map(
    (timeframe) => ({
      code: timeframe,
      label: getTimeframeLabel(
        timeframe
      ),
      minutes:
        getTimeframeMinutes(
          timeframe
        ),
      available:
        timeframe === "M15",
      native:
        timeframe === "M15",
      model_enabled:
        timeframe === "M15",
      source_timeframe:
        timeframe === "M15"
          ? "M15"
          : null,
      stored_candle_count: 0,
      reason:
        timeframe === "M15"
          ? null
          : "Disponibilità non verificabile senza collegamento a FastAPI.",
    })
  );

// Rappresenta i parametri URL ricevuti dalla pagina.
type HomePageProps = {
  searchParams: Promise<{
    timeframe?:
      | string
      | string[];
  }>;
};

/**
 * Restituisce l'etichetta professionale del timeframe.
 */
function getTimeframeLabel(
  timeframe: AvailableTimeframe
): string {
  // Associa il codice interno all'etichetta grafica.
  const labels: Record<
    AvailableTimeframe,
    string
  > = {
    M1: "1m",
    M2: "2m",
    M3: "3m",
    M5: "5m",
    M10: "10m",
    M15: "15m",
    M30: "30m",
    H1: "1h",
    H2: "2h",
    H4: "4h",
    H8: "8h",
    H12: "12h",
    D1: "1D",
    W1: "1W",
  };

  return labels[timeframe];
}

/**
 * Restituisce la durata del timeframe in minuti.
 */
function getTimeframeMinutes(
  timeframe: AvailableTimeframe
): number {
  // Associa ogni codice alla relativa durata.
  const minutes: Record<
    AvailableTimeframe,
    number
  > = {
    M1: 1,
    M2: 2,
    M3: 3,
    M5: 5,
    M10: 10,
    M15: 15,
    M30: 30,
    H1: 60,
    H2: 120,
    H4: 240,
    H8: 480,
    H12: 720,
    D1: 1440,
    W1: 10080,
  };

  return minutes[timeframe];
}

/**
 * Controlla se una stringa rappresenta un timeframe supportato.
 */
function isSupportedTimeframe(
  value: string
): value is AvailableTimeframe {
  return SUPPORTED_TIMEFRAMES.includes(
    value as AvailableTimeframe
  );
}

/**
 * Recupera il valore timeframe dal parametro URL.
 */
function readRequestedTimeframe(
  value:
    | string
    | string[]
    | undefined
): AvailableTimeframe {
  // Se il parametro è ripetuto, usa il primo valore.
  const selectedValue =
    Array.isArray(value)
      ? value[0]
      : value;

  // Usa M15 se il parametro è assente.
  if (
    selectedValue === undefined
  ) {
    return "M15";
  }

  // Usa M15 se il codice non è supportato.
  if (
    !isSupportedTimeframe(
      selectedValue
    )
  ) {
    return "M15";
  }

  return selectedValue;
}

/**
 * Seleziona un timeframe realmente disponibile.
 */
function selectAvailableTimeframe(
  requestedTimeframe:
    AvailableTimeframe,
  timeframes:
    TimeframeInformation[]
): AvailableTimeframe {
  // Cerca il timeframe richiesto nel catalogo API.
  const requestedInformation =
    timeframes.find(
      (timeframe) =>
        timeframe.code ===
        requestedTimeframe
    );

  // Mantiene il timeframe se disponibile.
  if (
    requestedInformation
      ?.available === true
  ) {
    return requestedTimeframe;
  }

  // Preferisce M15 come fallback operativo.
  const m15Information =
    timeframes.find(
      (timeframe) =>
        timeframe.code === "M15"
    );

  if (
    m15Information?.available ===
    true
  ) {
    return "M15";
  }

  // Usa il primo timeframe disponibile.
  const firstAvailable =
    timeframes.find(
      (timeframe) =>
        timeframe.available
    );

  // Se non esistono dati, mantiene M15.
  return (
    firstAvailable?.code ??
    "M15"
  );
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

  // Recupera il timeframe richiesto dall'URL.
  const requestedTimeframe =
    readRequestedTimeframe(
      resolvedSearchParams.timeframe
    );

  // Definisce il catalogo di fallback.
  let timeframes =
    FALLBACK_TIMEFRAMES;

  // Indica la sorgente dei dati di mercato.
  let marketSource:
    | "SQLITE_MARKET_DATA"
    | "CSV_FALLBACK"
    | "UNAVAILABLE" =
    "UNAVAILABLE";

  try {
    // Recupera disponibilità e origine dei timeframe.
    const timeframeResponse =
      await getTimeframes();

    // Memorizza il catalogo restituito da FastAPI.
    timeframes =
      timeframeResponse.timeframes;

    // Memorizza la sorgente dei dati.
    marketSource =
      timeframeResponse.source_type;
  } catch (error) {
    // Mantiene disponibile il catalogo minimo locale.
    console.error(
      "Impossibile caricare il catalogo timeframe:",
      error
    );
  }

  // Seleziona una risoluzione realmente disponibile.
  const selectedTimeframe =
    selectAvailableTimeframe(
      requestedTimeframe,
      timeframes
    );

  // Recupera le informazioni del timeframe selezionato.
  const selectedTimeframeInformation =
    timeframes.find(
      (timeframe) =>
        timeframe.code ===
        selectedTimeframe
    ) ?? null;

  // Definisce i valori di fallback.
  let online = false;
  let symbol = "EURUSD";

  // Inizializza i dati applicativi.
  let candles: Candle[] = [];
  let signals: SignalRecord[] = [];
  let outcomes: OutcomeRecord[] =
    [];
  let statistics:
    | LivePaperStatistics
    | null = null;

  try {
    // Interroga gli endpoint FastAPI in parallelo.
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
    online =
      health.status ===
      "healthy";

    symbol = status.symbol;

    // Memorizza i dati ricevuti da FastAPI.
    candles =
      marketResponse.candles;

    signals =
      signalsResponse.signals;

    outcomes =
      outcomesResponse.outcomes;

    statistics =
      statisticsResponse.statistics;

    // Usa la sorgente effettiva della risposta candele.
    marketSource =
      marketResponse.source_type;
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
  const longCount =
    signals.filter(
      (signal) =>
        signal.signal ===
        "LONG"
    ).length;

  // Conta i segnali SHORT.
  const shortCount =
    signals.filter(
      (signal) =>
        signal.signal ===
        "SHORT"
    ).length;

  // Conta i segnali NO_TRADE.
  const noTradeCount =
    signals.filter(
      (signal) =>
        signal.signal ===
        "NO_TRADE"
    ).length;

  // Prepara la descrizione della sorgente del timeframe.
  const timeframeSourceText =
    selectedTimeframeInformation
      ?.native === true
      ? "Dati nativi"
      : selectedTimeframeInformation
            ?.source_timeframe !==
          null &&
        selectedTimeframeInformation
          ?.source_timeframe !==
          undefined
        ? `Aggregato da ${selectedTimeframeInformation.source_timeframe}`
        : "Sorgente non disponibile";

  // Prepara l'etichetta dello storage.
  const marketSourceText =
    marketSource ===
    "SQLITE_MARKET_DATA"
      ? "Archivio live"
      : marketSource ===
          "CSV_FALLBACK"
        ? "CSV demo"
        : "Dati non disponibili";

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <Header
        symbol={symbol}
        timeframe={
          selectedTimeframe
        }
        online={online}
      />

      <div className="space-y-5 p-5">
        <section className="grid grid-cols-2 gap-4 md:grid-cols-5">
          <MarketStatus
            online={online}
          />

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
                {
                  selectedTimeframeInformation
                    ?.label ??
                  selectedTimeframe
                }
                {
                  " · UTC · Live Paper · "
                }
                {candles.length}
                {" candele"}
              </p>

              <p className="mt-1 text-xs text-slate-500">
                {timeframeSourceText}
                {" · "}
                {marketSourceText}
              </p>
            </div>

            <TimeframeSelector
              selectedTimeframe={
                selectedTimeframe
              }
              timeframes={
                timeframes
              }
            />
          </div>

          {selectedTimeframe !==
            "M15" && (
            <div className="mb-3 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-300">
              I segnali ML sono
              attualmente generati
              esclusivamente sul
              timeframe 15m e non
              vengono sovrapposti a
              questa risoluzione.
            </div>
          )}

          <MarketSnapshot
            candles={candles}
            symbol={symbol}
            timeframe={
              selectedTimeframe
            }
          />

          {candles.length > 0 ? (
            <UnifiedMarketChart
              key={
                selectedTimeframe
              }
              candles={candles}
              signals={chartSignals}
              timeframe={
                selectedTimeframe
              }
            />
          ) : (
            <div className="flex h-[600px] items-center justify-center rounded-lg border border-dashed border-slate-700 text-slate-500">
              Nessuna candela
              disponibile per{" "}
              {
                selectedTimeframe
              }
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

          <SignalsTable
            signals={signals}
          />
        </section>

        <section className="rounded-xl border border-slate-800 bg-slate-900">
          <div className="border-b border-slate-800 px-5 py-4">
            <h2 className="text-lg font-semibold">
              Outcomes
            </h2>
          </div>

          <OutcomesTable
            outcomes={outcomes}
          />
        </section>
      </div>
    </main>
  );
}