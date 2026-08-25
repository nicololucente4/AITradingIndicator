import type {
  AvailableTimeframe,
  CandlesResponse,
  HealthResponse,
  LiveMarketTick,
  OutcomesResponse,
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
  const response = await fetch(
    `${API_BASE_URL}${endpoint}`,
    {
      cache: "no-store",
    }
  );

  if (!response.ok) {
    throw new Error(
      `FastAPI request failed: ${endpoint}, status ${response.status}`
    );
  }

  return (await response.json()) as T;
}

/**
 * Recupera lo stato di salute.
 */
export function getHealth():
  Promise<HealthResponse> {
  return fetchFromApi<HealthResponse>(
    "/api/v1/health"
  );
}

/**
 * Recupera lo stato sintetico.
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
 * Recupera i timeframe dello strumento.
 */
export function getTimeframes(
  symbol: string
): Promise<TimeframesResponse> {
  const searchParameters =
    new URLSearchParams({
      symbol,
    });

  return fetchFromApi<TimeframesResponse>(
    `/api/v1/market/timeframes?${searchParameters.toString()}`
  );
}

/**
 * Recupera le candele richieste.
 */
export function getCandles(
  symbol: string,
  timeframe: AvailableTimeframe,
  limit = 500
): Promise<CandlesResponse> {
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
  const searchParameters =
    new URLSearchParams({
      symbol,
    });

  return fetchFromApi<LiveMarketTick>(
    `/api/v1/market/tick?${searchParameters.toString()}`
  );
}

/**
 * Recupera gli ultimi segnali.
 */
export function getSignals(
  limit = 200
): Promise<SignalsResponse> {
  return fetchFromApi<SignalsResponse>(
    `/api/v1/signals?limit=${limit}`
  );
}

/**
 * Recupera gli ultimi esiti.
 */
export function getOutcomes(
  limit = 200
): Promise<OutcomesResponse> {
  return fetchFromApi<OutcomesResponse>(
    `/api/v1/outcomes?limit=${limit}`
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