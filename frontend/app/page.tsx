import CandlestickChart from "@/src/components/CandlestickChart";
import Header from "@/src/components/Header";
import MarketStatus from "@/src/components/MarketStatus";

import {
  getCandles,
  getHealth,
  getSystemStatus,
} from "@/src/services/api";

// Rappresenta una singola candela restituita da FastAPI.
type Candle = {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

// Rappresenta la risposta dell'endpoint delle candele.
type CandlesResponse = {
  symbol: string;
  timeframe: string;
  timezone: string;
  count: number;
  candles: Candle[];
};

// Rappresenta la risposta dell'endpoint health.
type HealthResponse = {
  status: string;
  mode: string;
  market_data_available: boolean;
  database_available: boolean;
  symbol: string;
  timeframe: string;
};

// Rappresenta la risposta dello stato del sistema.
type SystemStatusResponse = {
  api_status: string;
  engine_mode: string;
  paper_trading_only: boolean;
  real_orders_enabled: boolean;
  symbol: string;
  timeframe: string;
  signal_count: number;
  outcome_count: number;
  latest_signal_timestamp: string | null;
};

export default async function Home() {
  // Imposta i valori iniziali mostrati se FastAPI non è disponibile.
  let online = false;
  let symbol = "EURUSD";
  let timeframe = "M15";
  let candles: Candle[] = [];

  try {
    // Interroga gli endpoint FastAPI.
    const health =
      (await getHealth()) as HealthResponse;

    const status =
      (await getSystemStatus()) as SystemStatusResponse;

    const market =
      (await getCandles(300)) as CandlesResponse;

    // Aggiorna lo stato del frontend.
    online = health.status === "healthy";
    symbol = status.symbol;
    timeframe = status.timeframe;
    candles = market.candles;
  } catch {
    // Mantiene il frontend utilizzabile anche con backend offline.
    online = false;
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <Header
        symbol={symbol}
        timeframe={timeframe}
      />

      <div className="space-y-6 p-6">
        <MarketStatus online={online} />

        <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
          <h2 className="mb-4 text-xl font-semibold">
            Market Chart
          </h2>

          {candles.length > 0 ? (
            <CandlestickChart candles={candles} />
          ) : (
            <div className="flex h-[600px] items-center justify-center rounded-lg border border-dashed border-slate-700 text-slate-500">
              Nessuna candela disponibile
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
            Signals
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
            Outcomes
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
            Statistics
          </div>
        </div>
      </div>
    </main>
  );
}