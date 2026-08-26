import type {
  PaperTradeRecord,
} from "@/src/types/market";

// Proprietà ricevute dal componente.
type CurrentTradeCardProps = {
  trade: PaperTradeRecord | null;
  symbol: string;
};

/**
 * Restituisce il numero di decimali appropriato.
 */
function getPricePrecision(
  symbol: string
): number {
  // Le coppie con JPY utilizzano tre decimali.
  if (
    symbol.includes("JPY")
  ) {
    return 3;
  }

  // L'oro viene mostrato con due decimali.
  if (
    symbol === "XAUUSD"
  ) {
    return 2;
  }

  // Le altre coppie Forex utilizzano cinque decimali.
  return 5;
}

/**
 * Formatta un prezzo in base allo strumento.
 */
function formatPrice(
  value: number,
  symbol: string
): string {
  return value.toFixed(
    getPricePrecision(
      symbol
    )
  );
}

/**
 * Formatta la confidenza come percentuale.
 */
function formatConfidence(
  value: number | null
): string {
  // Gestisce un valore non disponibile.
  if (
    value === null
  ) {
    return "N/D";
  }

  // Converte la probabilità in percentuale.
  return `${(
    value * 100
  ).toFixed(1)}%`;
}

/**
 * Formatta un timestamp in UTC.
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
 * Mostra la posizione paper attualmente aperta.
 */
export default function CurrentTradeCard({
  trade,
  symbol,
}: CurrentTradeCardProps) {
  // Mostra lo stato vuoto quando non esistono posizioni aperte.
  if (
    trade === null
  ) {
    return (
      <section className="rounded-xl border border-slate-800 bg-slate-900 p-5">
        <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Posizione paper corrente
        </div>

        <div className="mt-3 text-lg font-semibold text-slate-300">
          Nessuna posizione aperta
        </div>

        <p className="mt-2 text-xs text-slate-500">
          Una posizione viene aperta solamente con confidenza almeno 80%, margine probabilistico almeno 20% e livelli operativi validi.
        </p>
      </section>
    );
  }

  // Seleziona lo stile della direzione.
  const directionClassName =
    trade.direction === "LONG"
      ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
      : "border-red-500/40 bg-red-500/10 text-red-300";

  return (
    <section className="rounded-xl border border-blue-500/30 bg-slate-900 p-5">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Posizione paper corrente
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span
              className={`rounded-md border px-3 py-1 text-sm font-bold ${directionClassName}`}
            >
              OPEN {trade.direction}
            </span>

            <span className="rounded-md border border-blue-500/30 bg-blue-500/10 px-2 py-1 text-xs font-semibold text-blue-300">
              PAPER ONLY
            </span>
          </div>

          <div className="mt-3 font-mono text-xs text-slate-400">
            {trade.trade_id}
          </div>
        </div>

        <div className="text-left xl:text-right">
          <div className="text-[10px] uppercase text-slate-500">
            Apertura UTC
          </div>

          <div className="mt-1 text-xs text-slate-300">
            {formatTimestamp(
              trade.opened_at_utc
            )}
            {" UTC"}
          </div>
        </div>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
          <div className="text-[10px] uppercase text-slate-500">
            Strumento
          </div>

          <div className="mt-1 font-semibold text-white">
            {trade.symbol}
            {" "}
            {trade.timeframe}
          </div>
        </div>

        <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
          <div className="text-[10px] uppercase text-slate-500">
            Entry
          </div>

          <div className="mt-1 font-mono font-semibold text-white">
            {formatPrice(
              trade.entry_price,
              symbol
            )}
          </div>
        </div>

        <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-3">
          <div className="text-[10px] uppercase text-red-400/70">
            Stop Loss
          </div>

          <div className="mt-1 font-mono font-semibold text-red-300">
            {formatPrice(
              trade.stop_loss,
              symbol
            )}
          </div>
        </div>

        <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3">
          <div className="text-[10px] uppercase text-emerald-400/70">
            Take Profit
          </div>

          <div className="mt-1 font-mono font-semibold text-emerald-300">
            {formatPrice(
              trade.take_profit_1,
              symbol
            )}
          </div>
        </div>

        <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
          <div className="text-[10px] uppercase text-slate-500">
            Confidenza
          </div>

          <div className="mt-1 font-mono font-semibold text-purple-300">
            {formatConfidence(
              trade.prediction_confidence
            )}
          </div>
        </div>
      </div>
    </section>
  );
}