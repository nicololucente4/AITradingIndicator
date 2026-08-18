// Importa il tipo degli esiti.
import type {
  OutcomeRecord,
} from "@/src/types/market";

// Definisce le proprietà del componente.
type OutcomesTableProps = {
  outcomes: OutcomeRecord[];
};

/**
 * Mostra gli ultimi esiti conclusivi del paper trading.
 */
export default function OutcomesTable({
  outcomes,
}: OutcomesTableProps) {
  // Mostra uno stato vuoto quando non sono presenti esiti.
  if (outcomes.length === 0) {
    return (
      <div className="flex min-h-40 items-center justify-center text-sm text-slate-500">
        Nessun esito conclusivo disponibile
      </div>
    );
  }

  // Ordina gli esiti dal più recente.
  const orderedOutcomes = [...outcomes]
    .sort(
      (firstOutcome, secondOutcome) =>
        Date.parse(
          secondOutcome.exit_timestamp
        ) -
        Date.parse(
          firstOutcome.exit_timestamp
        )
    )
    .slice(0, 20);

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[800px] text-left text-sm">
        <thead className="border-b border-slate-800 text-xs uppercase text-slate-500">
          <tr>
            <th className="px-4 py-3">
              Uscita UTC
            </th>
            <th className="px-4 py-3">
              Direzione
            </th>
            <th className="px-4 py-3">
              Motivo
            </th>
            <th className="px-4 py-3 text-right">
              Entry
            </th>
            <th className="px-4 py-3 text-right">
              Exit
            </th>
            <th className="px-4 py-3 text-right">
              Barre
            </th>
            <th className="px-4 py-3 text-right">
              Risultato R
            </th>
          </tr>
        </thead>

        <tbody>
          {orderedOutcomes.map((outcome) => {
            // Determina se l'esito è positivo.
            const isPositive =
              outcome.result_r !== null &&
              outcome.result_r > 0;

            return (
              <tr
                key={outcome.signal_id}
                className="border-b border-slate-800/70 transition-colors hover:bg-slate-800/40"
              >
                <td className="whitespace-nowrap px-4 py-3 text-slate-300">
                  {new Date(
                    outcome.exit_timestamp
                  ).toLocaleString("it-IT", {
                    timeZone: "UTC",
                  })}
                </td>

                <td className="px-4 py-3 font-semibold text-slate-300">
                  {outcome.direction}
                </td>

                <td className="px-4 py-3 text-slate-400">
                  {outcome.exit_reason}
                </td>

                <td className="px-4 py-3 text-right font-mono text-slate-300">
                  {outcome.entry_price.toFixed(5)}
                </td>

                <td className="px-4 py-3 text-right font-mono text-slate-300">
                  {outcome.exit_price.toFixed(5)}
                </td>

                <td className="px-4 py-3 text-right text-slate-300">
                  {outcome.holding_bars}
                </td>

                <td
                  className={
                    isPositive
                      ? "px-4 py-3 text-right font-semibold text-green-400"
                      : "px-4 py-3 text-right font-semibold text-red-400"
                  }
                >
                  {outcome.result_r === null
                    ? "N/D"
                    : `${outcome.result_r.toFixed(3)} R`}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}