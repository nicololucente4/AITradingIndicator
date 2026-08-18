"use client";

import {
  usePathname,
  useRouter,
  useSearchParams,
} from "next/navigation";

import type {
  AvailableTimeframe,
  MarketTimeframe,
} from "@/src/types/market";

// Elenco completo dei timeframe mostrati nel terminale.
const TIMEFRAME_OPTIONS: Array<{
  code: MarketTimeframe;
  available: boolean;
  description: string;
}> = [
  {
    code: "M1",
    available: false,
    description:
      "Richiede candele native M1 dal provider reale",
  },
  {
    code: "M5",
    available: false,
    description:
      "Richiede candele native M5 dal provider reale",
  },
  {
    code: "M15",
    available: true,
    description: "Timeframe nativo disponibile",
  },
  {
    code: "H1",
    available: true,
    description: "Aggregato da M15",
  },
  {
    code: "H4",
    available: true,
    description: "Aggregato da M15",
  },
  {
    code: "D1",
    available: true,
    description: "Aggregato da M15",
  },
];

// Proprietà ricevute dal componente.
type TimeframeSelectorProps = {
  selectedTimeframe: AvailableTimeframe;
};

/**
 * Visualizza e modifica il timeframe tramite il parametro URL.
 */
export default function TimeframeSelector({
  selectedTimeframe,
}: TimeframeSelectorProps) {
  // Recupera gli strumenti di navigazione Next.js.
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  /**
   * Seleziona un nuovo timeframe disponibile.
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
    <div className="flex flex-wrap items-center gap-1 rounded-md border border-slate-800 bg-slate-950 p-1">
      {TIMEFRAME_OPTIONS.map((option) => {
        // Verifica se il pulsante è selezionato.
        const isSelected =
          option.code === selectedTimeframe;

        // I timeframe disponibili possono essere convertiti
        // nel tipo accettato dal backend.
        const availableTimeframe =
          option.code as AvailableTimeframe;

        return (
          <button
            key={option.code}
            type="button"
            title={option.description}
            disabled={!option.available}
            onClick={() => {
              if (option.available) {
                selectTimeframe(
                  availableTimeframe
                );
              }
            }}
            className={
              isSelected
                ? "rounded bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white"
                : option.available
                  ? "rounded px-3 py-1.5 text-xs font-medium text-slate-400 transition-colors hover:bg-slate-800 hover:text-white"
                  : "cursor-not-allowed rounded px-3 py-1.5 text-xs font-medium text-slate-700"
            }
          >
            {option.code}
          </button>
        );
      })}
    </div>
  );
}