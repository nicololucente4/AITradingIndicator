import type {
  AvailableTimeframe,
  CandlesResponse,
  HealthResponse,
  LiveMarketTick,
  OutcomesResponse,
  PaperTradesResponse,
  PaperTradeStatus,
  SignalsResponse,
  StatisticsResponse,
  SymbolsResponse,
  SystemStatusResponse,
  TimeframesResponse,
} from "@/src/types/market";

// URL del backend FastAPI.
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://127.0.0.1:8000";

/**
 * Esegue una richiesta read-only verso FastAPI.
 */
async function fetchFromApi<T>(
  endpoint: string
): Promise<T> {
  // Esegue la richiesta senza utilizzare la cache.
  const response = await fetch(
    `${API_BASE_URL}${endpoint}`,
    {
      cache: "no-store",
    }
  );

  // Interrompe l'elaborazione in caso di errore HTTP.
  if (
    !response.ok
  ) {
    throw new Error(
      `FastAPI request failed: ${endpoint}, status ${response.status}`
    );
  }

  // Converte la risposta JSON nel tipo richiesto.
  return (
    await response.json()
  ) as T;
}

/**
 * Recupera lo stato di salute del backend.
 */
export function getHealth():
  Promise<HealthResponse> {
  return fetchFromApi<HealthResponse>(
    "/api/v1/health"
  );
}

/**
 * Recupera lo stato sintetico del sistema.
 */
export function getSystemStatus():
  Promise<SystemStatusResponse> {
  return fetchFromApi<SystemStatusResponse>(
    "/api/v1/system/status"
  );
}

/**
 * Recupera gli strumenti disponibili.
 */
export function getSymbols():
  Promise<SymbolsResponse> {
  return fetchFromApi<SymbolsResponse>(
    "/api/v1/market/symbols"
  );
}

/**
 * Recupera i timeframe disponibili per lo strumento.
 */
export function getTimeframes(
  symbol: string
): Promise<TimeframesResponse> {
  // Prepara i parametri URL.
  const searchParameters =
    new URLSearchParams({
      symbol,
    });

  return fetchFromApi<TimeframesResponse>(
    `/api/v1/market/timeframes?${searchParameters.toString()}`
  );
}

/**
 * Recupera le candele dello strumento e del timeframe.
 */
export function getCandles(
  symbol: string,
  timeframe: AvailableTimeframe,
  limit = 500
): Promise<CandlesResponse> {
  // Prepara i parametri URL.
  const searchParameters =
    new URLSearchParams({
      symbol,
      timeframe,
      limit: String(limit),
    });

  return fetchFromApi<CandlesResponse>(
    `/api/v1/market/candles?${searchParameters.toString()}`
  );
}

/**
 * Recupera l'ultimo tick live direttamente da MT5.
 */
export function getLiveTick(
  symbol: string
): Promise<LiveMarketTick> {
  // Prepara il simbolo richiesto.
  const searchParameters =
    new URLSearchParams({
      symbol,
    });

  return fetchFromApi<LiveMarketTick>(
    `/api/v1/market/tick?${searchParameters.toString()}`
  );
}

/**
 * Recupera gli ultimi segnali diagnostici.
 */
export function getSignals(
  limit = 200
): Promise<SignalsResponse> {
  // Prepara il limite richiesto.
  const searchParameters =
    new URLSearchParams({
      limit: String(limit),
    });

  return fetchFromApi<SignalsResponse>(
    `/api/v1/signals?${searchParameters.toString()}`
  );
}

/**
 * Recupera gli esiti conclusivi dei segnali.
 */
export function getOutcomes(
  limit = 200
): Promise<OutcomesResponse> {
  // Prepara il limite richiesto.
  const searchParameters =
    new URLSearchParams({
      limit: String(limit),
    });

  return fetchFromApi<OutcomesResponse>(
    `/api/v1/outcomes?${searchParameters.toString()}`
  );
}

/**
 * Recupera le operazioni paper persistenti.
 */
export function getPaperTrades(
  symbol?: string,
  status?: PaperTradeStatus,
  limit = 200
): Promise<PaperTradesResponse> {
  // Prepara il limite obbligatorio.
  const searchParameters =
    new URLSearchParams({
      limit: String(limit),
    });

  // Aggiunge il simbolo solamente quando valorizzato.
  if (
    symbol !== undefined &&
    symbol.trim() !== ""
  ) {
    searchParameters.set(
      "symbol",
      symbol.trim().toUpperCase()
    );
  }

  // Aggiunge il filtro di stato quando richiesto.
  if (
    status !== undefined
  ) {
    searchParameters.set(
      "status",
      status
    );
  }

  return fetchFromApi<PaperTradesResponse>(
    `/api/v1/trades?${searchParameters.toString()}`
  );
}

/**
 * Recupera le statistiche Live Paper.
 */
export function getStatistics():
  Promise<StatisticsResponse> {
  return fetchFromApi<StatisticsResponse>(
    "/api/v1/statistics"
  );
}