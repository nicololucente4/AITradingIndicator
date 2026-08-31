"use client";

import {
  useMemo,
  useState,
} from "react";

import PaperTradesPanel from "@/src/components/PaperTradesPanel";
import UnifiedMarketChart from "@/src/components/UnifiedMarketChart";

import type {
  AvailableTimeframe,
  Candle,
  PaperTradeRecord,
} from "@/src/types/market";

import {
  findAliasByTradeId,
} from "@/src/utils/tradeAlias";

// Proprietà ricevute dal componente.
type TradeAnalysisWorkspaceProps = {
  // Candele della combinazione visualizzata.
  candles: Candle[];

  // Elenco completo dei paper trade.
  trades: PaperTradeRecord[];

  // Simbolo finanziario selezionato.
  symbol: string;

  // Timeframe selezionato.
  timeframe: AvailableTimeframe;
};

/**
 * Collega grafico e tabella delle operazioni.
 *
 * Il grafico riceve sempre l'elenco completo
 * dei trade, così gli alias restano stabili.
 *
 * selectedTradeId indica solamente quale
 * posizione deve essere isolata visivamente.
 */
export default function TradeAnalysisWorkspace({
  candles,
  trades,
  symbol,
  timeframe,
}: TradeAnalysisWorkspaceProps) {
  // Conserva il Trade ID richiesto dall'utente.
  const [
    requestedTradeId,
    setRequestedTradeId,
  ] = useState<
    string | null
  >(
    null
  );

  /**
   * Considera valida la selezione solamente
   * se il Trade ID è ancora presente nei dati.
   *
   * Non aggiorna lo stato dentro un useEffect,
   * evitando render aggiuntivi non necessari.
   */
  const selectedTradeId =
    useMemo(
      () => {
        // Nessuna selezione richiesta.
        if (
          requestedTradeId ===
          null
        ) {
          return null;
        }

        // Verifica che il trade esista ancora.
        const selectedTradeExists =
          trades.some(
            (trade) =>
              trade.trade_id ===
              requestedTradeId
          );

        return selectedTradeExists
          ? requestedTradeId
          : null;
      },
      [
        requestedTradeId,
        trades,
      ]
    );

  /**
   * Recupera l'alias condiviso
   * della posizione selezionata.
   */
  const selectedTradeAlias =
    useMemo(
      () => {
        // Nessun alias senza selezione.
        if (
          selectedTradeId ===
          null
        ) {
          return null;
        }

        return findAliasByTradeId(
          trades,
          selectedTradeId
        );
      },
      [
        selectedTradeId,
        trades,
      ]
    );

  /**
   * Seleziona una singola posizione.
   */
  function handleSelectTrade(
    tradeId: string
  ): void {
    setRequestedTradeId(
      tradeId
    );
  }

  /**
   * Ripristina la visualizzazione
   * di tutte le operazioni.
   */
  function handleShowAllTrades():
    void {
    setRequestedTradeId(
      null
    );
  }

  return (
    <div className="space-y-5">
      <section className="rounded-xl border border-slate-800 bg-slate-900 p-5">
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-white">
              Analisi grafica operazioni
            </h2>

            <p className="mt-1 text-xs text-slate-500">
              La selezione modifica solamente marker e livelli visualizzati. Zoom e posizione del grafico restano invariati.
            </p>
          </div>

          <div
            className={
              selectedTradeAlias ===
              null
                ? "rounded-md border border-slate-700 bg-slate-950/60 px-3 py-2 text-xs font-medium text-slate-500"
                : "rounded-md border border-blue-500/40 bg-blue-500/10 px-3 py-2 text-xs font-semibold text-blue-200"
            }
          >
            {selectedTradeAlias ===
            null
              ? "Tutte le operazioni"
              : `Posizione isolata: ${selectedTradeAlias}`}
          </div>
        </div>

        {candles.length > 0 ? (
          <UnifiedMarketChart
            candles={
              candles
            }
            trades={
              trades
            }
            selectedTradeId={
              selectedTradeId
            }
            symbol={
              symbol
            }
            timeframe={
              timeframe
            }
          />
        ) : (
          <div className="flex h-[600px] items-center justify-center rounded-lg border border-dashed border-slate-700 text-slate-500">
            Nessuna candela disponibile per{" "}
            {symbol}
            {" "}
            {timeframe}
          </div>
        )}
      </section>

      <section className="rounded-xl border border-slate-800 bg-slate-900">
        <div className="border-b border-slate-800 px-5 py-4">
          <h2 className="text-lg font-semibold text-white">
            Operazioni paper
          </h2>

          <p className="mt-1 text-xs text-slate-500">
            Usa Analizza per isolare una posizione sul grafico. Usa Mostra tutte per ripristinare tutti i marker.
          </p>
        </div>

        <PaperTradesPanel
          trades={
            trades
          }
          selectedTradeId={
            selectedTradeId
          }
          onSelectTrade={
            handleSelectTrade
          }
          onShowAllTrades={
            handleShowAllTrades
          }
        />
      </section>
    </div>
  );
}