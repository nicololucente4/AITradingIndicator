import type {
  PaperTradeRecord,
} from "@/src/types/market";

// Proprietà ricevute dal componente.
type PaperTradesPanelProps = {
  trades: PaperTradeRecord[];
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
 * Formatta un prezzo opzionale.
 */
function formatPrice(
  value: number | null,
  symbol: string
): string {
  // Gestisce un prezzo non ancora disponibile.
  if (
    value === null
  ) {
    return "N/D";
  }

  return value.toFixed(
    getPricePrecision(
      symbol
    )
  );
}

/**
 * Formatta un timestamp opzionale in UTC.
 */
function formatTimestamp(
  timestamp: string | null
): string {
  // Un trade senza chiusura è ancora aperto.
  if (
    timestamp === null
  ) {
    return "Posizione aperta";
  }

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
 * Formatta il risultato in multipli di rischio.
 */
function formatResultR(
  value: number | null
): string {
  // Gestisce un risultato non ancora disponibile.
  if (
    value === null
  ) {
    return "N/D";
  }

  // Evidenzia esplicitamente i risultati positivi.
  const prefix =
    value > 0
      ? "+"
      : "";

  return `${prefix}${value.toFixed(2)} R`;
}

/**
 * Restituisce un'etichetta leggibile del motivo di uscita.
 */
function getExitReasonLabel(
  exitReason: string | null
): string {
  // Un trade senza motivo di uscita è ancora aperto.
  if (
    exitReason === null
  ) {
    return "In monitoraggio";
  }

  const labels: Record<
    string,
    string
  > = {
    TAKE_PROFIT_1:
      "Take Profit raggiunto",
    STOP_LOSS:
      "Stop Loss raggiunto",
    STOP_LOSS_AMBIGUOUS:
      "Stop Loss, candela ambigua",
    TIME_EXPIRY:
      "Scadenza temporale",
  };

  return (
    labels[exitReason] ??
    exitReason
  );
}

/**
 * Mostra lo storico delle operazioni paper.
 */
export default function PaperTradesPanel({
  trades,
}: PaperTradesPanelProps) {
  // Mostra uno stato vuoto senza operazioni.
  if (
    trades.length === 0
  ) {
    return (
      <div className="flex min-h-40 items-center justify-center px-5 text-sm text-slate-500">
        Nessuna operazione paper disponibile
      </div>
    );
  }

  // Ordina le operazioni dalla più recente.
  const orderedTrades =
    [...trades]
      .sort(
        (
          firstTrade,
          secondTrade
        ) =>
          Date.parse(
            secondTrade.opened_at_utc
          ) -
          Date.parse(
            firstTrade.opened_at_utc
          )
      )
      .slice(
        0,
        50
      );

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1250px] text-left text-sm">
          <thead className="border-b border-slate-800 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">
                Trade ID
              </th>

              <th className="px-4 py-3">
                Strumento
              </th>

              <th className="px-4 py-3">
                Stato
              </th>

              <th className="px-4 py-3">
                Direzione
              </th>

              <th className="px-4 py-3">
                Apertura UTC
              </th>

              <th className="px-4 py-3">
                Chiusura UTC
              </th>

              <th className="px-4 py-3 text-right">
                Entry
              </th>

              <th className="px-4 py-3 text-right">
                Exit
              </th>

              <th className="px-4 py-3">
                Motivo uscita
              </th>

              <th className="px-4 py-3 text-right">
                Risultato R
              </th>
            </tr>
          </thead>

          <tbody>
            {orderedTrades.map(
              (trade) => {
                // Seleziona il colore del risultato.
                const resultClassName =
                  trade.result_r === null
                    ? "text-slate-500"
                    : trade.result_r > 0
                      ? "text-emerald-400"
                      : trade.result_r < 0
                        ? "text-red-400"
                        : "text-slate-300";

                // Seleziona il colore della direzione.
                const directionClassName =
                  trade.direction ===
                  "LONG"
                    ? "text-emerald-400"
                    : "text-red-400";

                return (
                  <tr
                    key={
                      trade.trade_id
                    }
                    className="border-b border-slate-800/70 transition-colors hover:bg-slate-800/40"
                  >
                    <td className="max-w-[240px] px-4 py-3">
                      <div
                        className="truncate font-mono text-xs text-blue-300"
                        title={
                          trade.trade_id
                        }
                      >
                        {trade.trade_id}
                      </div>
                    </td>

                    <td className="whitespace-nowrap px-4 py-3 font-semibold text-slate-300">
                      {trade.symbol}
                      {" "}
                      {trade.timeframe}
                    </td>

                    <td className="px-4 py-3">
                      <span
                        className={
                          trade.status ===
                          "OPEN"
                            ? "rounded border border-blue-500/30 bg-blue-500/10 px-2 py-1 text-xs font-bold text-blue-300"
                            : "rounded border border-slate-700 bg-slate-800 px-2 py-1 text-xs font-bold text-slate-300"
                        }
                      >
                        {trade.status}
                      </span>
                    </td>

                    <td
                      className={`px-4 py-3 font-semibold ${directionClassName}`}
                    >
                      {trade.direction}
                    </td>

                    <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-300">
                      {formatTimestamp(
                        trade.opened_at_utc
                      )}
                    </td>

                    <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-300">
                      {formatTimestamp(
                        trade.closed_at_utc
                      )}
                    </td>

                    <td className="px-4 py-3 text-right font-mono text-slate-300">
                      {formatPrice(
                        trade.entry_price,
                        trade.symbol
                      )}
                    </td>

                    <td className="px-4 py-3 text-right font-mono text-slate-300">
                      {formatPrice(
                        trade.exit_price,
                        trade.symbol
                      )}
                    </td>

                    <td className="px-4 py-3 text-xs text-slate-400">
                      {getExitReasonLabel(
                        trade.exit_reason
                      )}
                    </td>

                    <td
                      className={`px-4 py-3 text-right font-mono font-semibold ${resultClassName}`}
                    >
                      {formatResultR(
                        trade.result_r
                      )}
                    </td>
                  </tr>
                );
              }
            )}
          </tbody>
        </table>
      </div>

      <div className="border-t border-slate-800 px-5 py-3 text-xs text-slate-500">
        <span className="font-semibold text-slate-400">
          Risultato R:
        </span>
        {" "}
        misura il risultato rispetto al rischio iniziale tra Entry e Stop Loss. +1 R indica un guadagno pari al rischio iniziale, mentre -1 R indica la perdita completa del rischio previsto.
      </div>
    </div>
  );
}