"use client";

// Importa gli hook React necessari.
import {
  useCallback,
  useEffect,
  useState,
  useTransition,
} from "react";

// Importa il router di Next.js.
import { useRouter } from "next/navigation";

// Definisce gli intervalli disponibili.
const REFRESH_OPTIONS = [
  {
    label: "Off",
    value: 0,
  },
  {
    label: "5s",
    value: 5,
  },
  {
    label: "10s",
    value: 10,
  },
  {
    label: "30s",
    value: 30,
  },
  {
    label: "60s",
    value: 60,
  },
] as const;

/**
 * Mostra i controlli per l'aggiornamento dei dati FastAPI.
 */
export default function AutoRefresh() {
  // Recupera il router Next.js.
  const router = useRouter();

  // Gestisce l'intervallo automatico selezionato.
  const [
    refreshInterval,
    setRefreshInterval,
  ] = useState(10);

  // Memorizza il momento dell'ultimo aggiornamento.
  const [
    lastRefresh,
    setLastRefresh,
  ] = useState<Date | null>(null);

  // Indica quando Next.js sta aggiornando i Server Components.
  const [
    isPending,
    startTransition,
  ] = useTransition();

  /**
   * Aggiorna i dati della pagina senza ricaricare il browser.
   *
   * useCallback mantiene stabile il riferimento alla funzione,
   * permettendo di usarla correttamente dentro useEffect.
   */
  const refreshData = useCallback(() => {
    // Registra il momento del refresh.
    setLastRefresh(new Date());

    // Ricarica i dati dei Server Components.
    startTransition(() => {
      router.refresh();
    });
  }, [router]);

  useEffect(() => {
    // Non crea il timer se il refresh automatico è disabilitato.
    if (refreshInterval === 0) {
      return;
    }

    // Crea il timer periodico.
    const intervalIdentifier =
      window.setInterval(
        refreshData,
        refreshInterval * 1000
      );

    // Elimina il timer quando cambia configurazione
    // oppure quando il componente viene smontato.
    return () => {
      window.clearInterval(
        intervalIdentifier
      );
    };
  }, [
    refreshData,
    refreshInterval,
  ]);

  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="flex items-center gap-2">
        <span className="text-xs text-slate-500">
          Auto refresh
        </span>

        <select
          value={refreshInterval}
          onChange={(event) => {
            setRefreshInterval(
              Number(event.target.value)
            );
          }}
          className="rounded-md border border-slate-700 bg-slate-900 px-2 py-1.5 text-xs text-slate-300 outline-none transition-colors hover:border-slate-600 focus:border-blue-500"
          aria-label="Intervallo di aggiornamento automatico"
        >
          {REFRESH_OPTIONS.map(
            (option) => (
              <option
                key={option.value}
                value={option.value}
              >
                {option.label}
              </option>
            )
          )}
        </select>
      </div>

      <button
        type="button"
        disabled={isPending}
        onClick={refreshData}
        className="rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:border-blue-500 hover:text-blue-300 disabled:cursor-wait disabled:opacity-50"
      >
        {isPending
          ? "Aggiornamento..."
          : "Aggiorna ora"}
      </button>

      <div className="text-xs text-slate-500">
        {lastRefresh === null
          ? "In attesa del primo refresh"
          : `Ultimo refresh: ${lastRefresh.toLocaleTimeString(
              "it-IT"
            )}`}
      </div>
    </div>
  );
}