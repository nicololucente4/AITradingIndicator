// Tutti i timeframe professionali supportati dal sistema.
export type AvailableTimeframe =
  | "M1"
  | "M2"
  | "M3"
  | "M5"
  | "M10"
  | "M15"
  | "M30"
  | "H1"
  | "H2"
  | "H4"
  | "H8"
  | "H12"
  | "D1"
  | "W1";

// Alias mantenuto per compatibilità con i componenti esistenti.
export type MarketTimeframe =
  AvailableTimeframe;

// Rappresenta una candela OHLCV.
export type Candle = {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

// Segnali supportati dal sistema.
export type TradingSignal =
  | "LONG"
  | "SHORT"
  | "NO_TRADE";

// Rappresenta un segnale Live Paper.
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

// Rappresenta un esito conclusivo.
export type OutcomeRecord = {
  signal_id: string;
  direction: "LONG" | "SHORT";
  entry_price: number;
  exit_price: number;
  exit_reason: string;
  exit_timestamp: string;
  holding_bars: number;
  gross_return_percentage: number;
  result_r: number | null;
  evaluated_at_utc: string;
  outcome_mode: string;
};

// Statistiche aggregate Live Paper.
export type LivePaperStatistics = {
  total_signals: number;
  long_signals: number;
  short_signals: number;
  no_trade_signals: number;
  directional_signals: number;
  resolved_directional_signals: number;
  pending_directional_signals: number;
  resolution_rate_percentage: number;
  winning_outcomes: number;
  losing_outcomes: number;
  breakeven_outcomes: number;
  win_rate_percentage: number;
  expectancy_r: number;
  average_win_r: number;
  average_loss_r: number;
  profit_factor: number | null;
  cumulative_return_percentage: number;
  maximum_drawdown_percentage: number;
  take_profit_outcomes: number;
  stop_loss_outcomes: number;
  ambiguous_stop_outcomes: number;
  time_expiry_outcomes: number;
  average_holding_bars: number;
  average_directional_confidence: number | null;
  paper_trading_only: boolean;
};

// Informazioni restituite per ogni timeframe.
export type TimeframeInformation = {
  code: AvailableTimeframe;
  label: string;
  minutes: number;
  available: boolean;
  native: boolean;
  model_enabled: boolean;
  source_timeframe: AvailableTimeframe | null;
  stored_candle_count: number;
  reason: string | null;
};

// Risposta Health.
export type HealthResponse = {
  status: string;
  mode: string;
  market_data_available: boolean;
  market_data_database_available: boolean;
  csv_fallback_available: boolean;
  database_available: boolean;
  symbol: string;
  timeframe: AvailableTimeframe;
};

// Risposta System Status.
export type SystemStatusResponse = {
  api_status: string;
  engine_mode: string;
  paper_trading_only: boolean;
  real_orders_enabled: boolean;
  symbol: string;
  timeframe: AvailableTimeframe;
  model_timeframe: AvailableTimeframe;
  supported_timeframes: AvailableTimeframe[];
  available_timeframes: AvailableTimeframe[];
  signal_count: number;
  outcome_count: number;
  latest_signal_timestamp: string | null;
};

// Risposta Candles.
export type CandlesResponse = {
  symbol: string;
  timeframe: AvailableTimeframe;
  source_timeframe: AvailableTimeframe | null;
  source_type: "SQLITE_MARKET_DATA" | "CSV_FALLBACK";
  native: boolean;
  model_enabled: boolean;
  timezone: string;
  count: number;
  candles: Candle[];
};

// Risposta Timeframes.
export type TimeframesResponse = {
  source_timeframe: AvailableTimeframe;
  source_type: "SQLITE_MARKET_DATA" | "CSV_FALLBACK";
  model_timeframe: AvailableTimeframe;
  timeframes: TimeframeInformation[];
};

// Risposta Signals.
export type SignalsResponse = {
  mode: string;
  count: number;
  signals: SignalRecord[];
};

// Risposta Outcomes.
export type OutcomesResponse = {
  mode: string;
  count: number;
  outcomes: OutcomeRecord[];
};

// Risposta Statistics.
export type StatisticsResponse = {
  mode: string;
  data_available: boolean;
  statistics: LivePaperStatistics | null;
};