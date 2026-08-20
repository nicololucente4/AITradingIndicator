"use client";

import {
  usePathname,
  useRouter,
  useSearchParams,
} from "next/navigation";

import type {
  AvailableTimeframe,
  TimeframeInformation,
} from "@/src/types/market";

// Proprietà ricevute dal componente.
type TimeframeSelectorProps = {
  selectedTimeframe: AvailableTimeframe;
  timeframes: TimeframeInformation[];
};

/**
 * Visualizza il selettore professionale dei timeframe.
 */
export default function TimeframeSelector({
  selectedTimeframe,
  timeframes,
}: TimeframeSelectorProps) {
  // Recupera gli strumenti di navigazione Next.js.
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  /**
   * Aggiorna il timeframe tramite il parametro URL.
   */
  function selectTimeframe(
    timeframe: AvailableTimeframe
  ): void {
    // Copia i parametri URL correnti.
    const updatedSearchParams =
      new URLSearchParams(
        searchParams.toString()
      );

    // Aggiorna il timeframe.
    updatedSearchParams.set(
      "timeframe",
      timeframe
    );

    // Aggiorna l'URL senza riportare la pagina in alto.
    router.replace(
      `${pathname}?${updatedSearchParams.toString()}`,
      {
        scroll: false,
      }
    );
  }

  return (
    <div className="flex max-w-full flex-wrap items-center gap-1 rounded-md border border-slate-800 bg-slate-950 p-1">
      {timeframes.map((option) => {
        // Verifica se il pulsante è selezionato.
        const isSelected =
          option.code === selectedTimeframe;

        // Prepara una descrizione completa.
        const sourceDescription =
          option.native
            ? "Dati nativi"
            : option.source_timeframe !== null
              ? `Aggregato da ${option.source_timeframe}`
              : option.reason ??
                "Timeframe non disponibile";

        return (
          <button
            key={option.code}
            type="button"
            title={
              option.model_enabled
                ? `${sourceDescription}. Timeframe del modello ML.`
                : sourceDescription
            }
            disabled={!option.available}
            onClick={() => {
              if (option.available) {
                selectTimeframe(
                  option.code
                );
              }
            }}
            className={
              isSelected
                ? "relative rounded bg-blue-600 px-2.5 py-1.5 text-xs font-semibold text-white"
                : option.available
                  ? "relative rounded px-2.5 py-1.5 text-xs font-medium text-slate-400 transition-colors hover:bg-slate-800 hover:text-white"
                  : "relative cursor-not-allowed rounded px-2.5 py-1.5 text-xs font-medium text-slate-700"
            }
          >
            {option.label}

            {option.model_enabled && (
              <span className="ml-1 rounded bg-purple-500/20 px-1 py-0.5 text-[9px] font-bold text-purple-300">
                ML
              </span>
            )}

            {option.native && option.available && (
              <span className="absolute right-0.5 top-0.5 h-1 w-1 rounded-full bg-green-400" />
            )}
          </button>
        );
      })}
    </div>
  );
}