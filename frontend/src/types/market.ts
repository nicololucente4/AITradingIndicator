// Rappresenta una candela OHLCV restituita da FastAPI.
export type Candle = {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

// Definisce i segnali supportati dal sistema.
export type TradingSignal =
  | "LONG"
  | "SHORT"
  | "NO_TRADE";

// Rappresenta un segnale salvato dal Live Paper Engine.
export type SignalRecord = {
  signal_id: string;
  timestamp: string;
  signal_available_at: string;
  signal: TradingSignal;
  signal_status: string;
  signal_source: string;
  close_price: number | null;
  entry_price: number | null;
  stop_loss: number | null;
  take_profit_1: number | null;
  take_profit_2: number | null;
  take_profit_3: number | null;
  prediction_confidence: number | null;
  probability_margin: number | null;
  model_version: string | null;
  model_sha256: string | null;
  filter_reason: string | null;
  operating_mode: string;
  created_at_utc: string;
};

// Risposta dell'endpoint Health.
export type HealthResponse = {
  status: string;
  mode: string;
  market_data_available: boolean;
  database_available: boolean;
  symbol: string;
  timeframe: string;
};

// Risposta dell'endpoint System Status.
export type SystemStatusResponse = {
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

// Risposta dell'endpoint Candles.
export type CandlesResponse = {
  symbol: string;
  timeframe: string;
  timezone: string;
  count: number;
  candles: Candle[];
};

// Risposta dell'endpoint Signals.
export type SignalsResponse = {
  mode: string;
  count: number;
  signals: SignalRecord[];
};