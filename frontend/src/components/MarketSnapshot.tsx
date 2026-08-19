import type {
  AvailableTimeframe,
  Candle,
} from "@/src/types/market";

// Proprietà ricevute dal componente.
type MarketSnapshotProps = {
  candles: Candle[];
  symbol: string;
  timeframe: AvailableTimeframe;
};

/**
 * Formatta un prezzo mantenendo cinque decimali.
 */
function formatPrice(value: number): string {
  return value.toFixed(5);
}

/**
 * Formatta il volume usando la localizzazione italiana.
 */
function formatVolume(value: number): string {
  return new Intl.NumberFormat(
    "it-IT",
    {
      maximumFractionDigits: 0,
    }
  ).format(value);
}

/**
 * Mostra i dati dell'ultima candela disponibile.
 */
export default function MarketSnapshot({
  candles,
  symbol,
  timeframe,
}: MarketSnapshotProps) {
  // Non visualizza il pannello senza candele.
  if (candles.length === 0) {
    return null;
  }

  // Recupera l'ultima candela.
  const latestCandle =
    candles[candles.length - 1];

  // Recupera la candela precedente, quando disponibile.
  const previousCandle =
    candles.length > 1
      ? candles[candles.length - 2]
      : null;

  // Calcola la variazione rispetto alla chiusura precedente.
  const absoluteChange =
    previousCandle === null
      ? 0
      : latestCandle.close -
        previousCandle.close;

  // Calcola la variazione percentuale.
  const percentageChange =
    previousCandle === null ||
    previousCandle.close === 0
      ? 0
      : (
          absoluteChange /
          previousCandle.close
        ) * 100;

  // Determina il colore della variazione.
  const changeColor =
    absoluteChange > 0
      ? "text-[#089981]"
      : absoluteChange < 0
        ? "text-[#f23645]"
        : "text-slate-400";

  // Formatta il timestamp in UTC.
  const timestampText =
    new Date(
      latestCandle.timestamp
    ).toLocaleString(
      "it-IT",
      {
        timeZone: "UTC",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }
    );

  return (
    <div className="mb-3 flex flex-col gap-3 border-b border-slate-800 pb-3 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-white">
            {symbol}
          </span>

          <span className="rounded bg-slate-800 px-2 py-1 text-xs font-medium text-slate-300">
            {timeframe}
          </span>
        </div>

        <div className="font-mono text-lg font-semibold text-white">
          {formatPrice(
            latestCandle.close
          )}
        </div>

        <div
          className={`font-mono text-sm font-medium ${changeColor}`}
        >
          {absoluteChange >= 0
            ? "+"
            : ""}
          {formatPrice(
            absoluteChange
          )}

          {" "}

          (
          {percentageChange >= 0
            ? "+"
            : ""}
          {percentageChange.toFixed(3)}
          %)
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 font-mono text-xs">
        <div>
          <span className="text-slate-500">
            O
          </span>

          <span className="ml-1 text-slate-300">
            {formatPrice(
              latestCandle.open
            )}
          </span>
        </div>

        <div>
          <span className="text-slate-500">
            H
          </span>

          <span className="ml-1 text-[#089981]">
            {formatPrice(
              latestCandle.high
            )}
          </span>
        </div>

        <div>
          <span className="text-slate-500">
            L
          </span>

          <span className="ml-1 text-[#f23645]">
            {formatPrice(
              latestCandle.low
            )}
          </span>
        </div>

        <div>
          <span className="text-slate-500">
            C
          </span>

          <span className="ml-1 text-slate-300">
            {formatPrice(
              latestCandle.close
            )}
          </span>
        </div>

        <div>
          <span className="text-slate-500">
            Vol
          </span>

          <span className="ml-1 text-slate-300">
            {formatVolume(
              latestCandle.volume
            )}
          </span>
        </div>

        <div className="text-slate-600">
          {timestampText} UTC
        </div>
      </div>
    </div>
  );
}