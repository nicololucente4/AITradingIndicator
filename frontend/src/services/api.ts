import type {
  AvailableTimeframe,
  CandlesResponse,
  HealthResponse,
  OutcomesResponse,
  SignalsResponse,
  StatisticsResponse,
  SystemStatusResponse,
  TimeframesResponse,
} from "@/src/types/market";

// URL del backend FastAPI.
const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://127.0.0.1:8000";

/**
 * Esegue una richiesta read-only verso FastAPI.
 */
async function fetchFromApi<T>(
  endpoint: string
): Promise<T> {
  // Esegue la richiesta senza cache.
  const response = await fetch(
    `${API_BASE_URL}${endpoint}`,
    {
      cache: "no-store",
    }
  );

  // Interrompe il caricamento in caso di errore HTTP.
  if (!response.ok) {
    throw new Error(
      `FastAPI request failed: ${endpoint}, status ${response.status}`
    );
  }

  // Converte la risposta nel tipo richiesto.
  return (await response.json()) as T;
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
 * Recupera il catalogo dei timeframe.
 */
export function getTimeframes():
  Promise<TimeframesResponse> {
  return fetchFromApi<TimeframesResponse>(
    "/api/v1/market/timeframes"
  );
}

/**
 * Recupera le candele del timeframe richiesto.
 */
export function getCandles(
  timeframe: AvailableTimeframe,
  limit = 500
): Promise<CandlesResponse> {
  // Prepara i parametri URL.
  const searchParameters =
    new URLSearchParams({
      timeframe,
      limit: String(limit),
    });

  return fetchFromApi<CandlesResponse>(
    `/api/v1/market/candles?${searchParameters.toString()}`
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