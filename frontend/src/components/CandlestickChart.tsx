"use client";

import {
  useEffect,
  useRef,
  useState,
} from "react";

import {
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  LineSeries,
  LineStyle,
  type CandlestickData,
  type LineData,
  type LogicalRange,
  type SeriesMarker,
  type UTCTimestamp,
} from "lightweight-charts";

import type {
  Candle,
  SignalRecord,
} from "@/src/types/market";

type CandlestickChartProps = {
  candles: Candle[];
  signals: SignalRecord[];
};

// Chiave usata per conservare zoom e posizione
// durante i refresh della pagina Next.js.
const CHART_RANGE_STORAGE_KEY =
  "ai-trading-chart-logical-range";

/**
 * Converte un timestamp ISO in secondi Unix.
 */
function convertToUtcTimestamp(
  timestamp: string
): UTCTimestamp {
  const milliseconds = Date.parse(timestamp);

  if (Number.isNaN(milliseconds)) {
    throw new Error(
      `Timestamp non valido: ${timestamp}`
    );
  }

  return Math.floor(
    milliseconds / 1000
  ) as UTCTimestamp;
}

/**
 * Converte e ordina le candele.
 */
function prepareCandlestickData(
  candles: Candle[]
): CandlestickData<UTCTimestamp>[] {
  const uniqueCandles = new Map<
    number,
    CandlestickData<UTCTimestamp>
  >();

  for (const candle of candles) {
    const time = convertToUtcTimestamp(
      candle.timestamp
    );

    uniqueCandles.set(
      Number(time),
      {
        time,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
      }
    );
  }

  const preparedCandles = Array.from(
    uniqueCandles.values()
  );

  preparedCandles.sort(
    (firstCandle, secondCandle) =>
      Number(firstCandle.time) -
      Number(secondCandle.time)
  );

  return preparedCandles;
}

/**
 * Calcola una media mobile esponenziale.
 */
function calculateEma(
  candles: Candle[],
  period: number
): LineData<UTCTimestamp>[] {
  if (candles.length === 0) {
    return [];
  }

  const orderedCandles = [...candles].sort(
    (firstCandle, secondCandle) =>
      Date.parse(firstCandle.timestamp) -
      Date.parse(secondCandle.timestamp)
  );

  const multiplier = 2 / (period + 1);

  let currentEma =
    orderedCandles[0].close;

  const emaData: LineData<UTCTimestamp>[] =
    [];

  for (const candle of orderedCandles) {
    currentEma =
      candle.close * multiplier +
      currentEma * (1 - multiplier);

    emaData.push({
      time: convertToUtcTimestamp(
        candle.timestamp
      ),
      value: currentEma,
    });
  }

  return emaData;
}

/**
 * Converte i segnali in marker grafici.
 */
function prepareSignalMarkers(
  signals: SignalRecord[]
): SeriesMarker<UTCTimestamp>[] {
  const markers: SeriesMarker<UTCTimestamp>[] =
    [];

  for (const signal of signals) {
    const time = convertToUtcTimestamp(
      signal.timestamp
    );

    const confidence =
      signal.prediction_confidence === null
        ? "N/D"
        : `${Math.round(
            signal.prediction_confidence * 100
          )}%`;

    if (signal.signal === "LONG") {
      markers.push({
        time,
        position: "belowBar",
        color: "#22c55e",
        shape: "arrowUp",
        text: `LONG ${confidence}`,
      });

      continue;
    }

    if (signal.signal === "SHORT") {
      markers.push({
        time,
        position: "aboveBar",
        color: "#ef4444",
        shape: "arrowDown",
        text: `SHORT ${confidence}`,
      });

      continue;
    }

    markers.push({
      time,
      position: "inBar",
      color: "#94a3b8",
      shape: "circle",
      text: "NO TRADE",
    });
  }

  markers.sort(
    (firstMarker, secondMarker) =>
      Number(firstMarker.time) -
      Number(secondMarker.time)
  );

  return markers;
}

/**
 * Verifica che il segnale abbia direzione
 * e livelli operativi completi.
 */
function hasDirectionalLevels(
  signal: SignalRecord
): boolean {
  const validDirection =
    signal.signal === "LONG" ||
    signal.signal === "SHORT";

  const validLevels =
    typeof signal.entry_price === "number" &&
    typeof signal.stop_loss === "number" &&
    typeof signal.take_profit_1 === "number";

  return validDirection && validLevels;
}

/**
 * Recupera il segnale direzionale più recente.
 */
function getLatestDirectionalSignal(
  signals: SignalRecord[]
): SignalRecord | null {
  const directionalSignals = signals
    .filter(hasDirectionalLevels)
    .sort(
      (firstSignal, secondSignal) =>
        Date.parse(secondSignal.timestamp) -
        Date.parse(firstSignal.timestamp)
    );

  if (directionalSignals.length === 0) {
    return null;
  }

  return directionalSignals[0];
}

/**
 * Verifica la validità di un intervallo logico.
 */
function isValidLogicalRange(
  value: unknown
): value is LogicalRange {
  if (
    typeof value !== "object" ||
    value === null
  ) {
    return false;
  }

  const candidate = value as {
    from?: unknown;
    to?: unknown;
  };

  return (
    typeof candidate.from === "number" &&
    Number.isFinite(candidate.from) &&
    typeof candidate.to === "number" &&
    Number.isFinite(candidate.to) &&
    candidate.to > candidate.from
  );
}

/**
 * Legge zoom e posizione salvati nella sessione.
 */
function loadStoredLogicalRange():
  LogicalRange | null {
  try {
    const storedValue =
      window.sessionStorage.getItem(
        CHART_RANGE_STORAGE_KEY
      );

    if (storedValue === null) {
      return null;
    }

    const parsedValue: unknown =
      JSON.parse(storedValue);

    if (!isValidLogicalRange(parsedValue)) {
      window.sessionStorage.removeItem(
        CHART_RANGE_STORAGE_KEY
      );

      return null;
    }

    return parsedValue;
  } catch {
    return null;
  }
}

/**
 * Salva zoom e posizione nella sessione.
 */
function saveLogicalRange(
  logicalRange: LogicalRange | null
): void {
  if (logicalRange === null) {
    return;
  }

  try {
    window.sessionStorage.setItem(
      CHART_RANGE_STORAGE_KEY,
      JSON.stringify(logicalRange)
    );
  } catch {
    // La dashboard continua a funzionare anche
    // se sessionStorage non fosse disponibile.
  }
}

/**
 * Visualizza candele, EMA, marker e livelli.
 */
export default function CandlestickChart({
  candles,
  signals,
}: CandlestickChartProps) {
  const containerRef =
    useRef<HTMLDivElement | null>(null);

  const [showEma, setShowEma] =
    useState(true);

  const [showLevels, setShowLevels] =
    useState(true);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }

    if (candles.length === 0) {
      return;
    }

    const chartData =
      prepareCandlestickData(candles);

    if (chartData.length === 0) {
      return;
    }

    const firstCandleTime = Number(
      chartData[0].time
    );

    const lastCandleTime = Number(
      chartData[chartData.length - 1].time
    );

    const visibleSignals = signals.filter(
      (signal) => {
        const signalTime = Number(
          convertToUtcTimestamp(
            signal.timestamp
          )
        );

        return (
          signalTime >= firstCandleTime &&
          signalTime <= lastCandleTime
        );
      }
    );

    const chart = createChart(
      containerRef.current,
      {
        autoSize: true,

        layout: {
          background: {
            type: ColorType.Solid,
            color: "#0f172a",
          },
          textColor: "#94a3b8",
          fontFamily:
            "Inter, ui-sans-serif, system-ui, sans-serif",
        },

        grid: {
          vertLines: {
            color: "#1e293b",
          },
          horzLines: {
            color: "#1e293b",
          },
        },

        rightPriceScale: {
          borderColor: "#334155",
          autoScale: true,
          scaleMargins: {
            top: 0.12,
            bottom: 0.12,
          },
        },

        timeScale: {
          borderColor: "#334155",
          timeVisible: true,
          secondsVisible: false,
          rightOffset: 4,
          barSpacing: 12,
          minBarSpacing: 3,
          fixLeftEdge: false,
          fixRightEdge: false,
          lockVisibleTimeRangeOnResize: true,
        },

        crosshair: {
          vertLine: {
            color: "#64748b",
            labelBackgroundColor: "#334155",
          },
          horzLine: {
            color: "#64748b",
            labelBackgroundColor: "#334155",
          },
        },

        handleScroll: {
          mouseWheel: true,
          pressedMouseMove: true,
          horzTouchDrag: true,
          vertTouchDrag: false,
        },

        handleScale: {
          axisPressedMouseMove: true,
          mouseWheel: true,
          pinch: true,
        },
      }
    );

    const candlestickSeries =
      chart.addSeries(
        CandlestickSeries,
        {
          upColor: "#22c55e",
          wickUpColor: "#22c55e",
          borderUpColor: "#22c55e",

          downColor: "#ef4444",
          wickDownColor: "#ef4444",
          borderDownColor: "#ef4444",

          priceLineVisible: true,
          lastValueVisible: true,

          priceFormat: {
            type: "price",
            precision: 5,
            minMove: 0.00001,
          },
        }
      );

    candlestickSeries.setData(chartData);

    if (visibleSignals.length > 0) {
      createSeriesMarkers(
        candlestickSeries,
        prepareSignalMarkers(
          visibleSignals
        )
      );
    }

    if (showEma) {
      const emaFastSeries =
        chart.addSeries(
          LineSeries,
          {
            color: "#3b82f6",
            lineWidth: 2,
            title: "EMA 10",
            priceLineVisible: false,
            lastValueVisible: false,
          }
        );

      emaFastSeries.setData(
        calculateEma(candles, 10)
      );

      const emaSlowSeries =
        chart.addSeries(
          LineSeries,
          {
            color: "#f59e0b",
            lineWidth: 2,
            title: "EMA 30",
            priceLineVisible: false,
            lastValueVisible: false,
          }
        );

      emaSlowSeries.setData(
        calculateEma(candles, 30)
      );
    }

    if (showLevels) {
      const latestSignal =
        getLatestDirectionalSignal(
          visibleSignals
        );

      if (latestSignal !== null) {
        const entryPrice =
          latestSignal.entry_price;

        const stopLoss =
          latestSignal.stop_loss;

        const takeProfit1 =
          latestSignal.take_profit_1;

        const takeProfit2 =
          latestSignal.take_profit_2;

        const takeProfit3 =
          latestSignal.take_profit_3;

        if (
          typeof entryPrice === "number"
        ) {
          candlestickSeries.createPriceLine({
            price: entryPrice,
            color: "#e2e8f0",
            lineWidth: 1,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: "ENTRY",
          });
        }

        if (
          typeof stopLoss === "number"
        ) {
          candlestickSeries.createPriceLine({
            price: stopLoss,
            color: "#ef4444",
            lineWidth: 2,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: "SL",
          });
        }

        if (
          typeof takeProfit1 === "number"
        ) {
          candlestickSeries.createPriceLine({
            price: takeProfit1,
            color: "#22c55e",
            lineWidth: 2,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: "TP1",
          });
        }

        if (
          typeof takeProfit2 === "number"
        ) {
          candlestickSeries.createPriceLine({
            price: takeProfit2,
            color: "#14b8a6",
            lineWidth: 1,
            lineStyle: LineStyle.Dotted,
            axisLabelVisible: true,
            title: "TP2",
          });
        }

        if (
          typeof takeProfit3 === "number"
        ) {
          candlestickSeries.createPriceLine({
            price: takeProfit3,
            color: "#06b6d4",
            lineWidth: 1,
            lineStyle: LineStyle.Dotted,
            axisLabelVisible: true,
            title: "TP3",
          });
        }
      }
    }

    /**
     * Salva immediatamente ogni modifica effettuata
     * dall'utente sulla scala temporale.
     */
    const handleRangeChange = (
      logicalRange: LogicalRange | null
    ): void => {
      saveLogicalRange(logicalRange);
    };

    chart
      .timeScale()
      .subscribeVisibleLogicalRangeChange(
        handleRangeChange
      );

    // Ripristina lo zoom salvato.
    const storedRange =
      loadStoredLogicalRange();

    if (storedRange !== null) {
      chart
        .timeScale()
        .setVisibleLogicalRange(
          storedRange
        );
    } else {
      // fitContent viene eseguito solo quando
      // la sessione non contiene una vista salvata.
      chart.timeScale().fitContent();
    }

    return () => {
      // Salva nuovamente la vista prima della distruzione.
      const currentRange = chart
        .timeScale()
        .getVisibleLogicalRange();

      saveLogicalRange(currentRange);

      chart
        .timeScale()
        .unsubscribeVisibleLogicalRangeChange(
          handleRangeChange
        );

      chart.remove();
    };
  }, [
    candles,
    signals,
    showEma,
    showLevels,
  ]);

  /**
   * Ripristina manualmente la vista iniziale.
   */
  function resetSavedView(): void {
    window.sessionStorage.removeItem(
      CHART_RANGE_STORAGE_KEY
    );

    window.location.reload();
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => {
            setShowEma(
              (currentValue) =>
                !currentValue
            );
          }}
          className={
            showEma
              ? "rounded-md border border-blue-500 bg-blue-500/10 px-3 py-1.5 text-xs font-medium text-blue-300"
              : "rounded-md border border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-400"
          }
        >
          EMA 10 / 30
        </button>

        <button
          type="button"
          onClick={() => {
            setShowLevels(
              (currentValue) =>
                !currentValue
            );
          }}
          className={
            showLevels
              ? "rounded-md border border-green-500 bg-green-500/10 px-3 py-1.5 text-xs font-medium text-green-300"
              : "rounded-md border border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-400"
          }
        >
          Entry / SL / TP
        </button>

        <button
          type="button"
          onClick={resetSavedView}
          className="rounded-md border border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-400 transition-colors hover:border-slate-500 hover:text-white"
        >
          Ripristina vista
        </button>

        <div className="ml-auto flex items-center gap-4 text-xs">
          <span className="text-blue-400">
            EMA 10
          </span>

          <span className="text-amber-400">
            EMA 30
          </span>
        </div>
      </div>

      <div
        ref={containerRef}
        className="h-[600px] w-full overflow-hidden rounded-lg bg-slate-900"
      />
    </div>
  );
}