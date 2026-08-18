// Importa i tipi delle risposte FastAPI.
import type {
  CandlesResponse,
  HealthResponse,
  OutcomesResponse,
  SignalsResponse,
  StatisticsResponse,
  SystemStatusResponse,
} from "@/src/types/market";

// Definisce l'indirizzo del backend FastAPI.
const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://127.0.0.1:8000";

/**
 * Esegue una richiesta GET tipizzata al backend FastAPI.
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

  // Interrompe l'operazione in caso di risposta HTTP non valida.
  if (!response.ok) {
    throw new Error(
      `FastAPI request failed: ${endpoint}, status ${response.status}`
    );
  }

  // Converte la risposta JSON nel tipo richiesto.
  return (await response.json()) as T;
}

/**
 * Recupera lo stato di salute del backend.
 */
export function getHealth(): Promise<HealthResponse> {
  return fetchFromApi<HealthResponse>(
    "/api/v1/health"
  );
}

/**
 * Recupera lo stato generale del sistema.
 */
export function getSystemStatus():
  Promise<SystemStatusResponse> {
  return fetchFromApi<SystemStatusResponse>(
    "/api/v1/system/status"
  );
}

/**
 * Recupera le ultime candele OHLCV.
 */
export function getCandles(
  limit = 500
): Promise<CandlesResponse> {
  return fetchFromApi<CandlesResponse>(
    `/api/v1/market/candles?limit=${limit}`
  );
}

/**
 * Recupera gli ultimi segnali Live Paper.
 */
export function getSignals(
  limit = 200
): Promise<SignalsResponse> {
  return fetchFromApi<SignalsResponse>(
    `/api/v1/signals?limit=${limit}`
  );
}

/**
 * Recupera gli ultimi esiti conclusivi.
 */
export function getOutcomes(
  limit = 200
): Promise<OutcomesResponse> {
  return fetchFromApi<OutcomesResponse>(
    `/api/v1/outcomes?limit=${limit}`
  );
}

/**
 * Recupera le statistiche aggregate Live Paper.
 */
export function getStatistics():
  Promise<StatisticsResponse> {
  return fetchFromApi<StatisticsResponse>(
    "/api/v1/statistics"
  );
}