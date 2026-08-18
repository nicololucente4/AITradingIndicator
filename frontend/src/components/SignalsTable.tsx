// Importa il tipo dei segnali.
import type {
  SignalRecord,
} from "@/src/types/market";

// Definisce le proprietà del componente.
type SignalsTableProps = {
  signals: SignalRecord[];
};

/**
 * Formatta un prezzo mantenendo cinque decimali.
 */
function formatPrice(
  value: number | null
): string {
  if (value === null) {
    return "N/D";
  }

  return value.toFixed(5);
}

/**
 * Formatta la confidenza come percentuale.
 */
function formatConfidence(
  value: number | null
): string {
  if (value === null) {
    return "N/D";
  }

  return `${Math.round(value * 100)}%`;
}

/**
 * Restituisce il colore associato a un segnale.
 */
function getSignalColor(
  signal: SignalRecord["signal"]
): string {
  if (signal === "LONG") {
    return "text-green-400";
  }

  if (signal === "SHORT") {
    return "text-red-400";
  }

  return "text-slate-400";
}

/**
 * Mostra gli ultimi segnali del Live Paper Engine.
 */
export default function SignalsTable({
  signals,
}: SignalsTableProps) {
  // Mostra uno stato vuoto quando non esistono segnali.
  if (signals.length === 0) {
    return (
      <div className="flex min-h-40 items-center justify-center text-sm text-slate-500">
        Nessun segnale disponibile
      </div>
    );
  }

  // Ordina i segnali dal più recente.
  const orderedSignals = [...signals]
    .sort(
      (firstSignal, secondSignal) =>
        Date.parse(secondSignal.timestamp) -
        Date.parse(firstSignal.timestamp)
    )
    .slice(0, 20);

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[850px] text-left text-sm">
        <thead className="border-b border-slate-800 text-xs uppercase text-slate-500">
          <tr>
            <th className="px-4 py-3">
              Timestamp UTC
            </th>
            <th className="px-4 py-3">
              Segnale
            </th>
            <th className="px-4 py-3 text-right">
              Entry
            </th>
            <th className="px-4 py-3 text-right">
              Stop Loss
            </th>
            <th className="px-4 py-3 text-right">
              TP1
            </th>
            <th className="px-4 py-3 text-right">
              Confidenza
            </th>
            <th className="px-4 py-3">
              Modello
            </th>
          </tr>
        </thead>

        <tbody>
          {orderedSignals.map((signal) => (
            <tr
              key={signal.signal_id}
              className="border-b border-slate-800/70 transition-colors hover:bg-slate-800/40"
            >
              <td className="whitespace-nowrap px-4 py-3 text-slate-300">
                {new Date(
                  signal.timestamp
                ).toLocaleString("it-IT", {
                  timeZone: "UTC",
                })}
              </td>

              <td
                className={`px-4 py-3 font-semibold ${getSignalColor(
                  signal.signal
                )}`}
              >
                {signal.signal}
              </td>

              <td className="px-4 py-3 text-right font-mono text-slate-300">
                {formatPrice(
                  signal.entry_price
                )}
              </td>

              <td className="px-4 py-3 text-right font-mono text-red-300">
                {formatPrice(
                  signal.stop_loss
                )}
              </td>

              <td className="px-4 py-3 text-right font-mono text-green-300">
                {formatPrice(
                  signal.take_profit_1
                )}
              </td>

              <td className="px-4 py-3 text-right text-slate-300">
                {formatConfidence(
                  signal.prediction_confidence
                )}
              </td>

              <td className="px-4 py-3 text-xs text-slate-400">
                {signal.model_version ?? "N/D"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}