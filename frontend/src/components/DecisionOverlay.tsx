import type {
  SignalRecord,
} from "@/src/types/market";

// Proprietà del componente.
type DecisionOverlayProps = {
  signal: SignalRecord | null;
  symbol: string;
  timeframe: string;
};

/**
 * Formatta una percentuale.
 */
function formatPercentage(
  value: number | null
): string {
  if (value === null) {
    return "N/D";
  }

  return `${(
    value * 100
  ).toFixed(1)}%`;
}

/**
 * Formatta un prezzo in base allo strumento.
 */
function formatPrice(
  value: number | null,
  symbol: string
): string {
  if (value === null) {
    return "N/D";
  }

  if (
    symbol === "XAUUSD"
  ) {
    return value.toFixed(2);
  }

  if (
    symbol.endsWith("JPY")
  ) {
    return value.toFixed(3);
  }

  return value.toFixed(5);
}

/**
 * Formatta il timestamp della candela in UTC.
 */
function formatTimestamp(
  timestamp: string
): string {
  return new Date(
    timestamp
  ).toLocaleString(
    "it-IT",
    {
      timeZone: "UTC",
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }
  );
}

/**
 * Restituisce colori e testo della decisione.
 */
function getDecisionStyle(
  decision:
    | "LONG"
    | "SHORT"
    | "NO_TRADE"
) {
  if (decision === "LONG") {
    return {
      container:
        "border-emerald-500/50 bg-emerald-950/90",
      badge:
        "bg-emerald-500/20 text-emerald-300",
      indicator:
        "bg-emerald-400",
      label: "LONG",
    };
  }

  if (decision === "SHORT") {
    return {
      container:
        "border-red-500/50 bg-red-950/90",
      badge:
        "bg-red-500/20 text-red-300",
      indicator:
        "bg-red-400",
      label: "SHORT",
    };
  }

  return {
    container:
      "border-slate-600/60 bg-slate-950/90",
    badge:
      "bg-slate-700/70 text-slate-300",
    indicator:
      "bg-slate-400",
    label: "NO TRADE",
  };
}

/**
 * Mostra l'ultima decisione come overlay compatto.
 *
 * Il riquadro descrive una decisione del modello.
 * Non rappresenta un ordine reale.
 */
export default function DecisionOverlay({
  signal,
  symbol,
  timeframe,
}: DecisionOverlayProps) {
  // Senza modello o segnale mostra uno stato neutrale.
  if (signal === null) {
    return (
      <div className="pointer-events-none absolute left-3 top-3 z-20 max-w-[260px] rounded-lg border border-slate-700/70 bg-slate-950/90 px-3 py-2 shadow-lg backdrop-blur-sm">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          Ultima decisione
        </div>

        <div className="mt-1 text-xs text-slate-400">
          Nessuna decisione ML disponibile per{" "}
          {symbol}
          {" "}
          {timeframe}.
        </div>
      </div>
    );
  }

  // Recupera lo stile della decisione.
  const style = getDecisionStyle(
    signal.signal
  );

  return (
    <div
      className={`pointer-events-none absolute left-3 top-3 z-20 w-[260px] max-w-[calc(100%-24px)] rounded-lg border px-3 py-2 shadow-xl backdrop-blur-sm ${style.container}`}
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            Ultima decisione ML
          </div>

          <div className="mt-1 flex items-center gap-2">
            <span
              className={`h-2 w-2 rounded-full ${style.indicator}`}
            />

            <span
              className={`rounded px-2 py-0.5 text-sm font-bold ${style.badge}`}
            >
              {style.label}
            </span>
          </div>
        </div>

        <div className="text-right">
          <div className="text-[10px] uppercase text-slate-500">
            Confidenza
          </div>

          <div className="font-mono text-sm font-semibold text-white">
            {formatPercentage(
              signal.prediction_confidence
            )}
          </div>
        </div>
      </div>

      <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 border-t border-white/10 pt-2 text-[11px]">
        <div className="text-slate-500">
          Strumento
        </div>

        <div className="text-right font-medium text-slate-200">
          {symbol}
        </div>

        <div className="text-slate-500">
          Timeframe
        </div>

        <div className="text-right font-medium text-slate-200">
          {timeframe}
        </div>

        <div className="text-slate-500">
          Candela
        </div>

        <div className="text-right text-slate-300">
          {formatTimestamp(
            signal.timestamp
          )}
        </div>

        <div className="text-slate-500">
          Entry teorica
        </div>

        <div className="text-right font-mono text-slate-300">
          {formatPrice(
            signal.entry_price,
            symbol
          )}
        </div>
      </div>

      <div className="mt-2 truncate border-t border-white/10 pt-2 text-[10px] text-slate-500">
        {signal.filter_reason ??
          "Motivazione non disponibile"}
      </div>

      <div className="mt-1 text-[9px] font-semibold uppercase tracking-wide text-amber-400/80">
        Decisione storica, nessun ordine reale
      </div>
    </div>
  );
}