"use client";

import {
  useState,
} from "react";

import type {
  AvailableTimeframe,
  SignalRecord,
  TradingSignal,
} from "@/src/types/market";

// Proprietà ricevute dal componente.
type ProjectionPanelProps = {
  signal: SignalRecord | null;
  symbol: string;
  timeframe: AvailableTimeframe;
};

// Proprietà della singola riga di probabilità.
type ProbabilityRowProps = {
  label: string;
  probability: number | null;
  signal: TradingSignal;
};

// Stile associato a uno scenario.
type ScenarioStyle = {
  badge: string;
  border: string;
  bar: string;
  text: string;
};

// Numero di candele usato come orizzonte descrittivo.
const PROJECTION_HORIZON_BARS = 4;

/**
 * Formatta una probabilità.
 */
function formatProbability(
  value: number | null
): string {
  if (value === null) {
    return "N/D";
  }

  return `${(
    value * 100
  ).toFixed(1)}%`;
}

/**
 * Restituisce l'etichetta leggibile della decisione.
 */
function getSignalLabel(
  signal: TradingSignal
): string {
  if (
    signal === "NO_TRADE"
  ) {
    return "NO TRADE";
  }

  return signal;
}

/**
 * Restituisce lo stile dello scenario.
 */
function getScenarioStyle(
  signal: TradingSignal
): ScenarioStyle {
  if (
    signal === "LONG"
  ) {
    return {
      badge:
        "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
      border:
        "border-emerald-500/30",
      bar:
        "bg-emerald-500",
      text:
        "text-emerald-300",
    };
  }

  if (
    signal === "SHORT"
  ) {
    return {
      badge:
        "border-red-500/40 bg-red-500/10 text-red-300",
      border:
        "border-red-500/30",
      bar:
        "bg-red-500",
      text:
        "text-red-300",
    };
  }

  return {
    badge:
      "border-slate-600 bg-slate-800 text-slate-300",
    border:
      "border-slate-700",
    bar:
      "bg-slate-500",
    text:
      "text-slate-300",
  };
}

/**
 * Restituisce la probabilità dello scenario indicato.
 */
function getScenarioProbability(
  signal: SignalRecord,
  scenario: TradingSignal
): number | null {
  if (
    scenario === "LONG"
  ) {
    return signal.probability_long;
  }

  if (
    scenario === "SHORT"
  ) {
    return signal.probability_short;
  }

  return signal.probability_no_trade;
}

/**
 * Restituisce lo scenario con probabilità maggiore.
 */
function getLeadingScenario(
  signal: SignalRecord
): TradingSignal {
  const scenarios: Array<{
    signal: TradingSignal;
    probability: number;
  }> = [
    {
      signal: "LONG",
      probability:
        signal.probability_long ??
        0,
    },
    {
      signal: "SHORT",
      probability:
        signal.probability_short ??
        0,
    },
    {
      signal: "NO_TRADE",
      probability:
        signal.probability_no_trade ??
        0,
    },
  ];

  scenarios.sort(
    (
      firstScenario,
      secondScenario
    ) =>
      secondScenario.probability -
      firstScenario.probability
  );

  return scenarios[0].signal;
}

/**
 * Verifica se il segnale contiene le tre probabilità.
 */
function hasProjectionData(
  signal: SignalRecord
): boolean {
  return (
    signal.probability_long !==
      null &&
    signal.probability_short !==
      null &&
    signal.probability_no_trade !==
      null
  );
}

/**
 * Formatta il timestamp della decisione.
 */
function formatTimestamp(
  timestamp: string
): string {
  return new Date(
    timestamp
  ).toLocaleString(
    "it-IT",
    {
      timeZone: "UTC",
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }
  );
}

/**
 * Visualizza una singola probabilità.
 */
function ProbabilityRow({
  label,
  probability,
  signal,
}: ProbabilityRowProps) {
  // Recupera lo stile dello scenario.
  const style =
    getScenarioStyle(
      signal
    );

  // Limita il valore all'intervallo da zero a uno.
  const normalizedProbability =
    probability === null
      ? 0
      : Math.max(
          0,
          Math.min(
            1,
            probability
          )
        );

  return (
    <div>
      <div className="mb-1 flex items-center justify-between gap-3 text-xs">
        <span
          className={
            style.text
          }
        >
          {label}
        </span>

        <span className="font-mono font-semibold text-slate-200">
          {formatProbability(
            probability
          )}
        </span>
      </div>

      <div className="h-1.5 overflow-hidden rounded-full bg-slate-800">
        <div
          className={`h-full rounded-full transition-all ${style.bar}`}
          style={{
            width:
              `${normalizedProbability * 100}%`,
          }}
        />
      </div>
    </div>
  );
}

/**
 * Mostra la proiezione probabilistica del modello.
 *
 * La proiezione descrive scenari probabilistici.
 * Non genera prezzi futuri e non rappresenta un ordine.
 */
export default function ProjectionPanel({
  signal,
  symbol,
  timeframe,
}: ProjectionPanelProps) {
  // Gestisce l'apertura del dettaglio.
  const [
    projectionVisible,
    setProjectionVisible,
  ] = useState(false);

  // Senza segnale non esistono dati da proiettare.
  if (
    signal === null
  ) {
    return (
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <button
          type="button"
          disabled
          className="cursor-not-allowed rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs font-medium text-slate-500"
        >
          Proiezione non disponibile
        </button>

        <span className="text-xs text-slate-500">
          Nessuna decisione ML disponibile per{" "}
          {symbol}
          {" "}
          {timeframe}.
        </span>
      </div>
    );
  }

  // I segnali precedenti alla migrazione
  // possono non contenere le tre probabilità.
  const projectionDataAvailable =
    hasProjectionData(
      signal
    );

  // Recupera lo scenario prevalente.
  const leadingScenario =
    projectionDataAvailable
      ? getLeadingScenario(
          signal
        )
      : signal.signal;

  // Recupera lo stile dello scenario prevalente.
  const leadingStyle =
    getScenarioStyle(
      leadingScenario
    );

  return (
    <div className="mb-3">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => {
            setProjectionVisible(
              (
                currentValue
              ) =>
                !currentValue
            );
          }}
          className={
            projectionVisible
              ? "rounded-md border border-blue-500 bg-blue-500/10 px-3 py-1.5 text-xs font-semibold text-blue-300"
              : "rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:border-blue-500 hover:text-blue-300"
          }
        >
          {projectionVisible
            ? "Nascondi proiezione"
            : "Proiezione"}
        </button>

        <span className="text-xs text-slate-500">
          Scenario probabilistico per le prossime{" "}
          {PROJECTION_HORIZON_BARS}
          {" "}
          candele{" "}
          {timeframe}.
        </span>
      </div>

      {projectionVisible && (
        <section
          className={`mt-3 rounded-xl border bg-slate-950/80 p-4 ${leadingStyle.border}`}
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                Proiezione probabilistica
              </div>

              <div className="mt-2 flex flex-wrap items-center gap-2">
                <span
                  className={`rounded-md border px-3 py-1 text-sm font-bold ${leadingStyle.badge}`}
                >
                  Scenario prevalente:{" "}
                  {getSignalLabel(
                    leadingScenario
                  )}
                </span>

                <span className="text-xs text-slate-500">
                  {symbol}
                  {" · "}
                  {timeframe}
                </span>
              </div>
            </div>

            <div className="text-left sm:text-right">
              <div className="text-[10px] uppercase text-slate-500">
                Candela analizzata
              </div>

              <div className="mt-1 text-xs text-slate-300">
                {formatTimestamp(
                  signal.timestamp
                )}
                {" UTC"}
              </div>
            </div>
          </div>

          {projectionDataAvailable ? (
            <div className="mt-4 grid gap-3 lg:grid-cols-3">
              <ProbabilityRow
                label="Scenario LONG"
                probability={
                  getScenarioProbability(
                    signal,
                    "LONG"
                  )
                }
                signal="LONG"
              />

              <ProbabilityRow
                label="Scenario SHORT"
                probability={
                  getScenarioProbability(
                    signal,
                    "SHORT"
                  )
                }
                signal="SHORT"
              />

              <ProbabilityRow
                label="Scenario NO TRADE"
                probability={
                  getScenarioProbability(
                    signal,
                    "NO_TRADE"
                  )
                }
                signal="NO_TRADE"
              />
            </div>
          ) : (
            <div className="mt-4 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-300">
              Questo segnale è precedente all&apos;aggiunta delle probabilità dettagliate. Le nuove decisioni mostreranno LONG, SHORT e NO TRADE separatamente.
            </div>
          )}

          <div className="mt-4 grid gap-3 border-t border-slate-800 pt-3 text-xs sm:grid-cols-3">
            <div>
              <div className="text-slate-500">
                Decisione filtrata
              </div>

              <div className="mt-1 font-semibold text-slate-200">
                {getSignalLabel(
                  signal.signal
                )}
              </div>
            </div>

            <div>
              <div className="text-slate-500">
                Confidenza
              </div>

              <div className="mt-1 font-mono font-semibold text-slate-200">
                {formatProbability(
                  signal.prediction_confidence
                )}
              </div>
            </div>

            <div>
              <div className="text-slate-500">
                Margine probabilistico
              </div>

              <div className="mt-1 font-mono font-semibold text-slate-200">
                {formatProbability(
                  signal.probability_margin
                )}
              </div>
            </div>
          </div>

          <div className="mt-4 rounded-md border border-blue-500/20 bg-blue-500/5 px-3 py-2 text-[11px] text-slate-400">
            Orizzonte descrittivo: prossime{" "}
            {PROJECTION_HORIZON_BARS}
            {" "}
            candele{" "}
            {timeframe}.
            {" "}
            La proiezione non genera candele o prezzi futuri e non rappresenta un ordine reale.
          </div>
        </section>
      )}
    </div>
  );
}