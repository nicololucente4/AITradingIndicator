// Importa il controllo di aggiornamento della dashboard.
import AutoRefresh from "@/src/components/AutoRefresh";

// Importa il prezzo tick live indipendente.
import LivePrice from "@/src/components/LivePrice";

// Proprietà dell'header.
type HeaderProps = {
  symbol: string;
  timeframe: string;
  online: boolean;
};

/**
 * Mostra la barra superiore del terminale.
 */
export default function Header({
  symbol,
  timeframe,
  online,
}: HeaderProps) {
  return (
    <header className="border-b border-slate-800 bg-slate-950">
      <div className="flex flex-col gap-4 px-5 py-4 2xl:flex-row 2xl:items-center 2xl:justify-between">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center">
          <div className="flex items-center gap-6">
            <div>
              <h1 className="text-xl font-bold text-white">
                AI Trading Indicator
              </h1>

              <p className="mt-1 text-xs text-slate-500">
                Trading terminal
              </p>
            </div>

            <div className="hidden h-10 w-px bg-slate-800 sm:block" />

            <div>
              <div className="flex items-center gap-3">
                <span className="text-lg font-semibold text-white">
                  {symbol}
                </span>

                <span className="rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-xs font-medium text-slate-300">
                  {timeframe}
                </span>
              </div>

              <div className="mt-1 flex items-center gap-2 text-xs">
                <span
                  className={
                    online
                      ? "h-2 w-2 rounded-full bg-green-400 shadow-[0_0_8px_rgba(74,222,128,0.8)]"
                      : "h-2 w-2 rounded-full bg-red-400"
                  }
                />

                <span
                  className={
                    online
                      ? "text-green-400"
                      : "text-red-400"
                  }
                >
                  {online
                    ? "Backend online"
                    : "Backend offline"}
                </span>

                <span className="text-slate-600">
                  · UTC
                </span>
              </div>
            </div>
          </div>

          <LivePrice
            symbol={symbol}
          />
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <AutoRefresh />

          <div className="rounded-md border border-amber-500/60 bg-amber-500/10 px-3 py-2 text-center text-xs font-bold tracking-wide text-amber-400">
            PAPER ONLY
          </div>
        </div>
      </div>
    </header>
  );
}