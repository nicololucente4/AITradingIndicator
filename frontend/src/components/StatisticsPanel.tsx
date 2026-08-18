// Importa il tipo delle statistiche.
import type {
  LivePaperStatistics,
} from "@/src/types/market";

// Definisce le proprietà del componente.
type StatisticsPanelProps = {
  statistics: LivePaperStatistics | null;
};

/**
 * Mostra una singola metrica.
 */
function MetricCard({
  label,
  value,
  valueColor = "text-white",
}: {
  label: string;
  value: string;
  valueColor?: string;
}) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
      <div className="text-xs uppercase tracking-wide text-slate-500">
        {label}
      </div>

      <div
        className={`mt-2 text-xl font-semibold ${valueColor}`}
      >
        {value}
      </div>
    </div>
  );
}

/**
 * Mostra le metriche aggregate Live Paper.
 */
export default function StatisticsPanel({
  statistics,
}: StatisticsPanelProps) {
  // Mostra uno stato vuoto quando le metriche non sono disponibili.
  if (statistics === null) {
    return (
      <div className="flex min-h-40 items-center justify-center text-sm text-slate-500">
        Statistiche non ancora disponibili
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <MetricCard
        label="Win rate"
        value={`${statistics.win_rate_percentage.toFixed(
          2
        )}%`}
        valueColor="text-green-400"
      />

      <MetricCard
        label="Expectancy"
        value={`${statistics.expectancy_r.toFixed(
          3
        )} R`}
      />

      <MetricCard
        label="Profit Factor"
        value={
          statistics.profit_factor === null
            ? "N/D"
            : statistics.profit_factor.toFixed(3)
        }
      />

      <MetricCard
        label="Maximum Drawdown"
        value={`${statistics.maximum_drawdown_percentage.toFixed(
          3
        )}%`}
        valueColor="text-red-400"
      />

      <MetricCard
        label="Conclusi"
        value={String(
          statistics.resolved_directional_signals
        )}
      />

      <MetricCard
        label="Pendenti"
        value={String(
          statistics.pending_directional_signals
        )}
      />

      <MetricCard
        label="Take Profit"
        value={String(
          statistics.take_profit_outcomes
        )}
        valueColor="text-green-400"
      />

      <MetricCard
        label="Stop Loss"
        value={String(
          statistics.stop_loss_outcomes +
            statistics.ambiguous_stop_outcomes
        )}
        valueColor="text-red-400"
      />
    </div>
  );
}