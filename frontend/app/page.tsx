// Importa i componenti del terminale.
import CurrentTradeCard from "@/src/components/CurrentTradeCard";
import Header from "@/src/components/Header";
import MarketSnapshot from "@/src/components/MarketSnapshot";
import MarketStatus from "@/src/components/MarketStatus";
import OutcomesTable from "@/src/components/OutcomesTable";
import PaperTradesPanel from "@/src/components/PaperTradesPanel";
import ProjectionPanel from "@/src/components/ProjectionPanel";
import SignalsTable from "@/src/components/SignalsTable";
import StatisticsPanel from "@/src/components/StatisticsPanel";
import SymbolSelector from "@/src/components/SymbolSelector";
import TimeframeSelector from "@/src/components/TimeframeSelector";
import UnifiedMarketChart from "@/src/components/UnifiedMarketChart";

// Importa le funzioni che interrogano FastAPI.
import {
  getCandles,
  getHealth,
  getOutcomes,
  getPaperTrades,
  getSignals,
  getStatistics,
  getSymbols,
  getSystemStatus,
  getTimeframes,
} from "@/src/services/api";

// Importa i tipi condivisi.
import type {
  AvailableTimeframe,
  Candle,
  LivePaperStatistics,
  MarketSymbolInformation,
  OutcomeRecord,
  PaperTradeRecord,
  SignalRecord,
  TimeframeInformation,
} from "@/src/types/market";

// Forza il rendering dinamico della dashboard.
export const dynamic = "force-dynamic";

// Disabilita la cache statica della pagina.
export const revalidate = 0;

// Elenca tutti i timeframe riconosciuti.
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

// Strumento disponibile in modalità fallback.
const FALLBACK_SYMBOLS:
  MarketSymbolInformation[] = [
    {
      symbol: "EURUSD",
      native_timeframe_count: 1,
      stored_candle_count: 0,
      model_enabled: true,
    },
  ];

// Rappresenta i parametri URL della pagina.
type HomePageProps = {
  searchParams: Promise<{
    symbol?:
      | string
      | string[];
    timeframe?:
      | string
      | string[];
  }>;
};

/**
 * Restituisce l'etichetta grafica del timeframe.
 */
function getTimeframeLabel(
  timeframe: AvailableTimeframe
): string {
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

  return labels[
    timeframe
  ];
}

/**
 * Restituisce la durata del timeframe in minuti.
 */
function getTimeframeMinutes(
  timeframe: AvailableTimeframe
): number {
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

  return minutes[
    timeframe
  ];
}

/**
 * Crea il catalogo timeframe di fallback.
 */
function createFallbackTimeframes():
  TimeframeInformation[] {
  return SUPPORTED_TIMEFRAMES.map(
    (timeframe) => ({
      code: timeframe,
      label:
        getTimeframeLabel(
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
          : "Disponibilità non verificabile senza FastAPI.",
    })
  );
}

/**
 * Recupera il primo valore di un parametro URL.
 */
function readSearchParameter(
  value:
    | string
    | string[]
    | undefined
): string | undefined {
  if (
    Array.isArray(value)
  ) {
    return value[0];
  }

  return value;
}

/**
 * Normalizza il simbolo richiesto.
 */
function normalizeRequestedSymbol(
  value:
    | string
    | string[]
    | undefined
): string {
  const selectedValue =
    readSearchParameter(
      value
    );

  if (
    selectedValue ===
    undefined
  ) {
    return "EURUSD";
  }

  const normalizedValue =
    selectedValue
      .trim()
      .toUpperCase();

  return (
    normalizedValue ||
    "EURUSD"
  );
}

/**
 * Verifica un codice timeframe.
 */
function isSupportedTimeframe(
  value: string
): value is AvailableTimeframe {
  return SUPPORTED_TIMEFRAMES.includes(
    value as AvailableTimeframe
  );
}

/**
 * Recupera il timeframe richiesto.
 */
function readRequestedTimeframe(
  value:
    | string
    | string[]
    | undefined
): AvailableTimeframe {
  const selectedValue =
    readSearchParameter(
      value
    );

  if (
    selectedValue ===
    undefined
  ) {
    return "M15";
  }

  const normalizedValue =
    selectedValue
      .trim()
      .toUpperCase();

  if (
    !isSupportedTimeframe(
      normalizedValue
    )
  ) {
    return "M15";
  }

  return normalizedValue;
}

/**
 * Seleziona uno strumento disponibile.
 */
function selectAvailableSymbol(
  requestedSymbol: string,
  symbols: MarketSymbolInformation[],
  defaultSymbol: string
): string {
  const requestedInformation =
    symbols.find(
      (item) =>
        item.symbol ===
        requestedSymbol
    );

  if (
    requestedInformation !==
    undefined
  ) {
    return requestedInformation.symbol;
  }

  const defaultInformation =
    symbols.find(
      (item) =>
        item.symbol ===
        defaultSymbol
    );

  if (
    defaultInformation !==
    undefined
  ) {
    return defaultInformation.symbol;
  }

  return (
    symbols[0]?.symbol ??
    defaultSymbol
  );
}

/**
 * Seleziona un timeframe disponibile.
 */
function selectAvailableTimeframe(
  requestedTimeframe:
    AvailableTimeframe,
  timeframes:
    TimeframeInformation[]
): AvailableTimeframe {
  const requestedInformation =
    timeframes.find(
      (timeframe) =>
        timeframe.code ===
        requestedTimeframe
    );

  if (
    requestedInformation
      ?.available === true
  ) {
    return requestedTimeframe;
  }

  const m15Information =
    timeframes.find(
      (timeframe) =>
        timeframe.code ===
        "M15"
    );

  if (
    m15Information
      ?.available === true
  ) {
    return "M15";
  }

  const firstAvailable =
    timeframes.find(
      (timeframe) =>
        timeframe.available
    );

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
  // Legge i parametri URL.
  const resolvedSearchParams =
    await searchParams;

  const requestedSymbol =
    normalizeRequestedSymbol(
      resolvedSearchParams.symbol
    );

  const requestedTimeframe =
    readRequestedTimeframe(
      resolvedSearchParams.timeframe
    );

  // Inizializza strumenti e fallback.
  let symbols =
    FALLBACK_SYMBOLS;

  let defaultSymbol =
    "EURUSD";

  let marketSource:
    | "SQLITE_MARKET_DATA"
    | "CSV_FALLBACK"
    | "UNAVAILABLE" =
    "UNAVAILABLE";

  try {
    const symbolsResponse =
      await getSymbols();

    if (
      symbolsResponse
        .symbols.length > 0
    ) {
      symbols =
        symbolsResponse.symbols;
    }

    defaultSymbol =
      symbolsResponse
        .default_symbol;

    marketSource =
      symbolsResponse
        .source_type;
  } catch (error) {
    console.error(
      "Impossibile caricare gli strumenti:",
      error
    );
  }

  // Seleziona uno strumento disponibile.
  const selectedSymbol =
    selectAvailableSymbol(
      requestedSymbol,
      symbols,
      defaultSymbol
    );

  // Carica i timeframe dello strumento.
  let timeframes =
    createFallbackTimeframes();

  let symbolModelEnabled =
    false;

  try {
    const timeframeResponse =
      await getTimeframes(
        selectedSymbol
      );

    timeframes =
      timeframeResponse
        .timeframes;

    symbolModelEnabled =
      timeframeResponse
        .model_enabled;

    marketSource =
      timeframeResponse
        .source_type;
  } catch (error) {
    console.error(
      "Impossibile caricare i timeframe:",
      error
    );
  }

  const selectedTimeframe =
    selectAvailableTimeframe(
      requestedTimeframe,
      timeframes
    );

  const selectedTimeframeInformation =
    timeframes.find(
      (timeframe) =>
        timeframe.code ===
        selectedTimeframe
    ) ?? null;

  const selectedModelEnabled =
    symbolModelEnabled &&
    selectedTimeframeInformation
      ?.model_enabled === true;

  // Inizializza i dati della dashboard.
  let online = false;

  let candles: Candle[] = [];

  let signals: SignalRecord[] =
    [];

  let outcomes: OutcomeRecord[] =
    [];

  let trades: PaperTradeRecord[] =
    [];

  let statistics:
    | LivePaperStatistics
    | null = null;

  try {
    // Recupera in parallelo dati di mercato, segnali e trade.
    const [
      health,
      status,
      marketResponse,
      signalsResponse,
      outcomesResponse,
      tradesResponse,
      statisticsResponse,
    ] = await Promise.all([
      getHealth(),
      getSystemStatus(),
      getCandles(
        selectedSymbol,
        selectedTimeframe,
        500
      ),
      getSignals(200),
      getOutcomes(200),
      getPaperTrades(
        selectedSymbol,
        undefined,
        200
      ),
      getStatistics(),
    ]);

    // Determina lo stato generale del backend.
    online =
      health.status ===
        "healthy" &&
      status.api_status ===
        "ONLINE";

    // Memorizza le candele ricevute.
    candles =
      marketResponse.candles;

    // Memorizza la sorgente effettiva.
    marketSource =
      marketResponse
        .source_type;

    // Mantiene i paper trade del simbolo selezionato.
    trades =
      tradesResponse.trades;

    // Mostra segnali, esiti e statistiche solo
    // se la combinazione possiede un modello valido.
    if (
      selectedModelEnabled
    ) {
      signals =
        signalsResponse.signals;

      outcomes =
        outcomesResponse.outcomes;

      statistics =
        statisticsResponse
          .statistics;
    }
  } catch (error) {
    console.error(
      "Impossibile caricare i dati FastAPI:",
      error
    );

    online = false;
  }

  // Recupera l'ultima decisione diagnostica disponibile.
  const latestDecision =
    selectedModelEnabled &&
    signals.length > 0
      ? [...signals].sort(
          (
            firstSignal,
            secondSignal
          ) =>
            Date.parse(
              secondSignal.timestamp
            ) -
            Date.parse(
              firstSignal.timestamp
            )
        )[0]
      : null;

  // Mantiene i trade della combinazione visualizzata.
  const selectedTrades =
    trades.filter(
      (trade) =>
        trade.symbol ===
          selectedSymbol &&
        trade.timeframe ===
          selectedTimeframe
    );

  // Recupera l'eventuale posizione aperta.
  const currentTrade =
    selectedTrades.find(
      (trade) =>
        trade.status ===
        "OPEN"
    ) ?? null;

  // Conta le decisioni diagnostiche.
  const longCount =
    signals.filter(
      (signal) =>
        signal.signal ===
        "LONG"
    ).length;

  const shortCount =
    signals.filter(
      (signal) =>
        signal.signal ===
        "SHORT"
    ).length;

  const noTradeCount =
    signals.filter(
      (signal) =>
        signal.signal ===
        "NO_TRADE"
    ).length;

  // Descrive la sorgente del timeframe.
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

  // Descrive lo storage.
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
        symbol={
          selectedSymbol
        }
        timeframe={
          selectedTimeframe
        }
        online={online}
      />

      <div className="space-y-5 p-5">
        <section className="rounded-xl border border-slate-800 bg-slate-900 p-4">
          <div className="mb-3 flex flex-col gap-1">
            <h2 className="text-sm font-semibold text-white">
              Strumento
            </h2>

            <p className="text-xs text-slate-500">
              Seleziona la coppia Forex o l&apos;oro da analizzare.
            </p>
          </div>

          <SymbolSelector
            selectedSymbol={
              selectedSymbol
            }
            symbols={symbols}
          />
        </section>

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
              Paper trade
            </div>

            <div className="mt-2 text-lg font-bold text-blue-400">
              {selectedTrades.length}
            </div>
          </div>
        </section>

        <CurrentTradeCard
          trade={currentTrade}
          symbol={selectedSymbol}
        />

        <section className="rounded-xl border border-slate-800 bg-slate-900 p-5">
          <div className="mb-4 flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            <div>
              <h2 className="text-lg font-semibold">
                {selectedSymbol}
                {" Chart"}
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

          {!selectedModelEnabled && (
            <div className="mb-3 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-300">
              Dati disponibili per l&apos;analisi grafica. Un modello ML validato per{" "}
              {selectedSymbol}
              {" "}
              {selectedTimeframe}
              {" "}
              non è ancora registrato.
            </div>
          )}

          <MarketSnapshot
            candles={candles}
            symbol={
              selectedSymbol
            }
            timeframe={
              selectedTimeframe
            }
          />

          <ProjectionPanel
            signal={
              latestDecision
            }
            symbol={
              selectedSymbol
            }
            timeframe={
              selectedTimeframe
            }
          />

          {candles.length > 0 ? (
            <div className="relative">
              <UnifiedMarketChart
                candles={candles}
                trades={
                  selectedTrades
                }
                symbol={
                  selectedSymbol
                }
                timeframe={
                  selectedTimeframe
                }
              />
            </div>
          ) : (
            <div className="flex h-[600px] items-center justify-center rounded-lg border border-dashed border-slate-700 text-slate-500">
              Nessuna candela disponibile per{" "}
              {selectedSymbol}
              {" "}
              {selectedTimeframe}
            </div>
          )}
        </section>

        <section className="rounded-xl border border-slate-800 bg-slate-900">
          <div className="border-b border-slate-800 px-5 py-4">
            <h2 className="text-lg font-semibold">
              Operazioni paper
            </h2>

            <p className="mt-1 text-xs text-slate-500">
              Aperture e chiusure persistenti collegate dallo stesso Trade ID.
            </p>
          </div>

          <PaperTradesPanel
            trades={
              selectedTrades
            }
          />
        </section>

        <section className="rounded-xl border border-slate-800 bg-slate-900 p-5">
          <h2 className="mb-4 text-lg font-semibold">
            Statistics
          </h2>

          <StatisticsPanel
            statistics={
              statistics
            }
          />
        </section>

        <section className="rounded-xl border border-slate-800 bg-slate-900">
          <div className="border-b border-slate-800 px-5 py-4">
            <h2 className="text-lg font-semibold">
              Signals
            </h2>

            <p className="mt-1 text-xs text-slate-500">
              Decisioni diagnostiche del modello. Non tutte generano un&apos;operazione paper.
            </p>
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

            <p className="mt-1 text-xs text-slate-500">
              Esiti conclusivi delle decisioni direzionali monitorate.
            </p>
          </div>

          <OutcomesTable
            outcomes={outcomes}
          />
        </section>
      </div>
    </main>
  );
}