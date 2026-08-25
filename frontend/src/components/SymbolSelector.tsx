"use client";

import {
  usePathname,
  useRouter,
  useSearchParams,
} from "next/navigation";

import type {
  MarketSymbolInformation,
} from "@/src/types/market";

// Proprietà del selettore.
type SymbolSelectorProps = {
  selectedSymbol: string;
  symbols: MarketSymbolInformation[];
};

/**
 * Visualizza gli strumenti disponibili.
 */
export default function SymbolSelector({
  selectedSymbol,
  symbols,
}: SymbolSelectorProps) {
  // Recupera gli strumenti di navigazione.
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  /**
   * Aggiorna simbolo e timeframe nell'URL.
   */
  function selectSymbol(
    symbol: string
  ): void {
    const updatedSearchParams =
      new URLSearchParams(
        searchParams.toString()
      );

    // Aggiorna lo strumento.
    updatedSearchParams.set(
      "symbol",
      symbol
    );

    // Riparte da M15 quando cambia strumento.
    updatedSearchParams.set(
      "timeframe",
      "M15"
    );

    router.replace(
      `${pathname}?${updatedSearchParams.toString()}`,
      {
        scroll: false,
      }
    );
  }

  return (
    <div className="flex max-w-full flex-wrap items-center gap-1 rounded-md border border-slate-800 bg-slate-950 p-1">
      {symbols.map((item) => {
        const isSelected =
          item.symbol ===
          selectedSymbol;

        return (
          <button
            key={item.symbol}
            type="button"
            onClick={() => {
              selectSymbol(
                item.symbol
              );
            }}
            title={
              item.model_enabled
                ? `${item.native_timeframe_count} timeframe nativi. Modello ML disponibile.`
                : `${item.native_timeframe_count} timeframe nativi. Modello ML non ancora disponibile.`
            }
            className={
              isSelected
                ? "rounded bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white"
                : "rounded px-3 py-1.5 text-xs font-medium text-slate-400 transition-colors hover:bg-slate-800 hover:text-white"
            }
          >
            {item.symbol}

            {item.model_enabled && (
              <span className="ml-1.5 rounded bg-purple-500/20 px-1 py-0.5 text-[9px] font-bold text-purple-300">
                ML
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}