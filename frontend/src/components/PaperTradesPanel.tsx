"use client";

import type {
  PaperTradeRecord,
} from "@/src/types/market";

import {
  getPaperTradesWithAliases,
} from "@/src/utils/tradeAlias";

// Proprietà ricevute dal componente.
type PaperTradesPanelProps = {
  // Elenco completo dei trade della combinazione visualizzata.
  trades: PaperTradeRecord[];

  // Identificativo del trade attualmente selezionato.
  selectedTradeId?: string | null;

  // Callback eseguita quando l'utente seleziona un trade.
  onSelectTrade?: (
    tradeId: string
  ) => void;

  // Callback eseguita per ripristinare tutti i trade.
  onShowAllTrades?: () => void;
};

/**
 * Restituisce il numero di decimali appropriato.
 */
function getPricePrecision(
  symbol: string
): number {
  // Le coppie con JPY utilizzano tre decimali.
  if (
    symbol.includes(
      "JPY"
    )
  ) {
    return 3;
  }

  // L'oro viene mostrato con due decimali.
  if (
    symbol ===
    "XAUUSD"
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
  // Un trade senza data di chiusura è ancora aperto.
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
      timeZone:
        "UTC",
      day:
        "2-digit",
      month:
        "2-digit",
      year:
        "numeric",
      hour:
        "2-digit",
      minute:
        "2-digit",
      hour12:
        false,
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

  // Traduce i motivi conosciuti.
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
    labels[
      exitReason
    ] ??
    exitReason
  );
}

/**
 * Restituisce lo stile dell'alias.
 */
function getAliasClassName(
  direction: "LONG" | "SHORT",
  selected: boolean
): string {
  // LONG utilizza verde ad alto contrasto.
  if (
    direction ===
    "LONG"
  ) {
    return selected
      ? "border-emerald-300 bg-emerald-500/20 text-emerald-100 ring-2 ring-emerald-400/30"
      : "border-emerald-500/50 bg-emerald-500/10 text-emerald-300";
  }

  // SHORT utilizza rosso ad alto contrasto.
  return selected
    ? "border-red-300 bg-red-500/20 text-red-100 ring-2 ring-red-400/30"
    : "border-red-500/50 bg-red-500/10 text-red-300";
}

/**
 * Restituisce lo stile del risultato R.
 */
function getResultClassName(
  resultR: number | null
): string {
  // Trade non ancora concluso.
  if (
    resultR === null
  ) {
    return "text-slate-500";
  }

  // Risultato positivo.
  if (
    resultR > 0
  ) {
    return "text-emerald-400";
  }

  // Risultato negativo.
  if (
    resultR < 0
  ) {
    return "text-red-400";
  }

  // Risultato neutro.
  return "text-slate-300";
}

/**
 * Restituisce lo stile della direzione.
 */
function getDirectionClassName(
  direction: "LONG" | "SHORT"
): string {
  return direction ===
    "LONG"
    ? "text-emerald-400"
    : "text-red-400";
}

/**
 * Mostra lo storico delle operazioni paper.
 */
export default function PaperTradesPanel({
  trades,
  selectedTradeId = null,
  onSelectTrade,
  onShowAllTrades,
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

  // Genera una volta sola alias e ordinamento condivisi.
  const tradesWithAliases =
    getPaperTradesWithAliases(
      trades
    );

  // Mostra per prime le operazioni più recenti.
  const displayedTrades =
    [...tradesWithAliases]
      .reverse()
      .slice(
        0,
        50
      );

  // Indica se il pannello è già collegato
  // alla selezione interattiva del grafico.
  const selectionAvailable =
    onSelectTrade !==
    undefined;

  // Indica se una posizione è selezionata.
  const tradeSelected =
    selectedTradeId !==
    null;

  return (
    <div>
      <div className="flex flex-col gap-3 border-b border-slate-800 px-5 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Analisi operazioni
          </div>

          <div className="mt-1 text-xs text-slate-400">
            {tradeSelected
              ? "Una singola posizione è isolata sul grafico."
              : "Il grafico mostra tutte le operazioni disponibili."}
          </div>
        </div>

        <button
          type="button"
          disabled={
            !tradeSelected ||
            onShowAllTrades ===
              undefined
          }
          onClick={() => {
            onShowAllTrades?.();
          }}
          className={
            tradeSelected &&
            onShowAllTrades !==
              undefined
              ? "rounded-md border border-blue-500/50 bg-blue-500/10 px-3 py-1.5 text-xs font-semibold text-blue-300 transition-colors hover:border-blue-300 hover:text-blue-100"
              : "cursor-not-allowed rounded-md border border-slate-800 px-3 py-1.5 text-xs font-medium text-slate-600"
          }
        >
          Mostra tutte
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[1350px] text-left text-sm">
          <thead className="border-b border-slate-800 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">
                Alias
              </th>

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

              <th className="px-4 py-3 text-right">
                Analisi
              </th>
            </tr>
          </thead>

          <tbody>
            {displayedTrades.map(
              (
                tradeInformation
              ) => {
                // Recupera record e alias condiviso.
                const {
                  trade,
                  alias,
                } =
                  tradeInformation;

                // Controlla se la riga è selezionata.
                const selected =
                  trade.trade_id ===
                  selectedTradeId;

                // Recupera gli stili dinamici.
                const aliasClassName =
                  getAliasClassName(
                    trade.direction,
                    selected
                  );

                const resultClassName =
                  getResultClassName(
                    trade.result_r
                  );

                const directionClassName =
                  getDirectionClassName(
                    trade.direction
                  );

                return (
                  <tr
                    key={
                      trade.trade_id
                    }
                    className={
                      selected
                        ? "border-b border-blue-500/30 bg-blue-500/10"
                        : "border-b border-slate-800/70 transition-colors hover:bg-slate-800/40"
                    }
                  >
                    <td className="whitespace-nowrap px-4 py-3">
                      <span
                        className={`inline-flex min-w-14 items-center justify-center rounded-md border px-2 py-1 font-mono text-xs font-bold ${aliasClassName}`}
                      >
                        {alias}
                      </span>
                    </td>

                    <td className="max-w-[220px] px-4 py-3">
                      <div
                        className="truncate font-mono text-xs text-slate-500"
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

                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        disabled={
                          !selectionAvailable
                        }
                        onClick={() => {
                          onSelectTrade?.(
                            trade.trade_id
                          );
                        }}
                        className={
                          !selectionAvailable
                            ? "cursor-not-allowed rounded-md border border-slate-800 px-3 py-1.5 text-xs font-medium text-slate-600"
                            : selected
                              ? "rounded-md border border-blue-300 bg-blue-500/20 px-3 py-1.5 text-xs font-semibold text-blue-100"
                              : "rounded-md border border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:border-blue-500 hover:bg-blue-500/10 hover:text-blue-300"
                        }
                      >
                        {selected
                          ? "Selezionata"
                          : "Analizza"}
                      </button>
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