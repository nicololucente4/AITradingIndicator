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

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://127.0.0.1:8000";

async function fetchFromApi<T>(endpoint: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(
      `FastAPI request failed: ${endpoint}, status ${response.status}`
    );
  }

  return (await response.json()) as T;
}

export function getHealth(): Promise<HealthResponse> {
  return fetchFromApi<HealthResponse>("/api/v1/health");
}

export function getSystemStatus(): Promise<SystemStatusResponse> {
  return fetchFromApi<SystemStatusResponse>(
    "/api/v1/system/status"
  );
}

export function getTimeframes(): Promise<TimeframesResponse> {
  return fetchFromApi<TimeframesResponse>(
    "/api/v1/market/timeframes"
  );
}

export function getCandles(
  timeframe: AvailableTimeframe,
  limit = 500
): Promise<CandlesResponse> {
  const searchParameters = new URLSearchParams({
    timeframe,
    limit: String(limit),
  });

  return fetchFromApi<CandlesResponse>(
    `/api/v1/market/candles?${searchParameters.toString()}`
  );
}

export function getSignals(limit = 200): Promise<SignalsResponse> {
  return fetchFromApi<SignalsResponse>(
    `/api/v1/signals?limit=${limit}`
  );
}

export function getOutcomes(limit = 200): Promise<OutcomesResponse> {
  return fetchFromApi<OutcomesResponse>(
    `/api/v1/outcomes?limit=${limit}`
  );
}

export function getStatistics(): Promise<StatisticsResponse> {
  return fetchFromApi<StatisticsResponse>(
    "/api/v1/statistics"
  );
}
