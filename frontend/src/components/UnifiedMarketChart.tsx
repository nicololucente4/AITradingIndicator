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
  HistogramSeries,
  LineSeries,
  LineStyle,
  type CandlestickData,
  type HistogramData,
  type IChartApi,
  type LineData,
  type MouseEventParams,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";

import type {
  AvailableTimeframe,
  Candle,
  SignalRecord,
} from "@/src/types/market";

// Proprietà ricevute dal componente.
type UnifiedMarketChartProps = {
  candles: Candle[];
  signals: SignalRecord[];
  timeframe: AvailableTimeframe;
};

// Valori mostrati nel pannello OHLCV.
type HoveredMarketData = {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

// Numero iniziale di candele visibili per timeframe.
const INITIAL_VISIBLE_BARS: Record<
  AvailableTimeframe,
  number
> = {
  M15: 120,
  H1: 100,
  H4: 70,
  D1: 45,
};

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
 * Converte le candele nel formato Lightweight Charts.
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
 * Converte le candele nella serie dei volumi.
 */
function prepareVolumeData(
  candles: Candle[]
): HistogramData<UTCTimestamp>[] {
  const uniqueVolumes = new Map<
    number,
    HistogramData<UTCTimestamp>
  >();

  for (const candle of candles) {
    const time = convertToUtcTimestamp(
      candle.timestamp
    );

    const color =
      candle.close >= candle.open
        ? "rgba(8, 153, 129, 0.65)"
        : "rgba(242, 54, 69, 0.65)";

    uniqueVolumes.set(
      Number(time),
      {
        time,
        value: candle.volume,
        color,
      }
    );
  }

  const preparedVolumes = Array.from(
    uniqueVolumes.values()
  );

  preparedVolumes.sort(
    (firstVolume, secondVolume) =>
      Number(firstVolume.time) -
      Number(secondVolume.time)
  );

  return preparedVolumes;
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
 * Converte i segnali in marker.
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
        color: "#089981",
        shape: "arrowUp",
        text: `LONG ${confidence}`,
      });

      continue;
    }

    if (signal.signal === "SHORT") {
      markers.push({
        time,
        position: "aboveBar",
        color: "#f23645",
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
 * Recupera l'ultimo segnale direzionale completo.
 */
function getLatestDirectionalSignal(
  signals: SignalRecord[]
): SignalRecord | null {
  const directionalSignals = signals
    .filter(
      (signal) =>
        (
          signal.signal === "LONG" ||
          signal.signal === "SHORT"
        ) &&
        typeof signal.entry_price === "number" &&
        typeof signal.stop_loss === "number" &&
        typeof signal.take_profit_1 === "number"
    )
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
 * Converte il tempo Lightweight Charts in secondi Unix.
 */
function convertChartTimeToNumber(
  time: Time
): number | null {
  if (typeof time === "number") {
    return time;
  }

  if (typeof time === "string") {
    const parsedMilliseconds =
      Date.parse(time);

    if (
      Number.isNaN(parsedMilliseconds)
    ) {
      return null;
    }

    return Math.floor(
      parsedMilliseconds / 1000
    );
  }

  const milliseconds = Date.UTC(
    time.year,
    time.month - 1,
    time.day
  );

  return Math.floor(
    milliseconds / 1000
  );
}

/**
 * Formatta un prezzo EURUSD.
 */
function formatPrice(
  value: number
): string {
  return value.toFixed(5);
}

/**
 * Formatta il volume.
 */
function formatVolume(
  value: number
): string {
  return new Intl.NumberFormat(
    "it-IT",
    {
      maximumFractionDigits: 0,
    }
  ).format(value);
}

/**
 * Mostra candlestick e volumi in pannelli sincronizzati.
 */
export default function UnifiedMarketChart({
  candles,
  signals,
  timeframe,
}: UnifiedMarketChartProps) {
  const containerRef =
    useRef<HTMLDivElement | null>(null);

  const chartRef =
    useRef<IChartApi | null>(null);

  const [showEma, setShowEma] =
    useState(true);

  const [showLevels, setShowLevels] =
    useState(true);

  const [showVolume, setShowVolume] =
    useState(true);

  // Inizializza il pannello OHLCV con l'ultima candela disponibile.
  const [hoveredData, setHoveredData] =
    useState<HoveredMarketData | null>(
      () => {
        // Senza candele non esistono dati da mostrare.
        if (candles.length === 0) {
          return null;
        }

        // Recupera l'ultima candela ricevuta.
        const latestCandle =
          candles[candles.length - 1];

        // Restituisce i dati iniziali del pannello OHLCV.
        return {
          timestamp: latestCandle.timestamp,
          open: latestCandle.open,
          high: latestCandle.high,
          low: latestCandle.low,
          close: latestCandle.close,
          volume: latestCandle.volume,
        };
      }
    );

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }

    if (candles.length === 0) {
      return;
    }

    const orderedCandles = [...candles]
      .sort(
        (firstCandle, secondCandle) =>
          Date.parse(
            firstCandle.timestamp
          ) -
          Date.parse(
            secondCandle.timestamp
          )
      );

    const candleData =
      prepareCandlestickData(
        orderedCandles
      );

    const volumeData =
      prepareVolumeData(
        orderedCandles
      );

    if (candleData.length === 0) {
      return;
    }

    const candleLookup = new Map<
      number,
      Candle
    >();

    for (const candle of orderedCandles) {
      candleLookup.set(
        Number(
          convertToUtcTimestamp(
            candle.timestamp
          )
        ),
        candle
      );
    }

    const chart = createChart(
      containerRef.current,
      {
        autoSize: true,

        layout: {
          background: {
            type: ColorType.Solid,
            color: "#0b1220",
          },
          textColor: "#94a3b8",
          fontFamily:
            "Inter, ui-sans-serif, system-ui, sans-serif",
          panes: {
            separatorColor: "#263449",
            separatorHoverColor: "#3b82f6",
            enableResize: true,
          },
        },

        grid: {
          vertLines: {
            color: "#162033",
          },
          horzLines: {
            color: "#162033",
          },
        },

        rightPriceScale: {
          borderColor: "#263449",
          scaleMargins: {
            top: 0.08,
            bottom: 0.08,
          },
        },

        timeScale: {
          borderColor: "#263449",
          timeVisible: true,
          secondsVisible: false,
          rightOffset: 3,
          barSpacing: 9,
          minBarSpacing: 2,
          lockVisibleTimeRangeOnResize: true,
          rightBarStaysOnScroll: true,
        },

        crosshair: {
          vertLine: {
            color: "#64748b",
            width: 1,
            style: LineStyle.Dashed,
            labelBackgroundColor: "#334155",
          },
          horzLine: {
            color: "#64748b",
            width: 1,
            style: LineStyle.Dashed,
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

    chartRef.current = chart;

    // Il pane 0 contiene prezzi ed EMA.
    const candlestickSeries =
      chart.addSeries(
        CandlestickSeries,
        {
          upColor: "#089981",
          wickUpColor: "#089981",
          borderUpColor: "#089981",

          downColor: "#f23645",
          wickDownColor: "#f23645",
          borderDownColor: "#f23645",

          priceLineVisible: true,
          lastValueVisible: true,

          priceFormat: {
            type: "price",
            precision: 5,
            minMove: 0.00001,
          },
        },
        0
      );

    candlestickSeries.setData(
      candleData
    );

    if (signals.length > 0) {
      createSeriesMarkers(
        candlestickSeries,
        prepareSignalMarkers(signals)
      );
    }

    if (showEma) {
      const emaFastSeries =
        chart.addSeries(
          LineSeries,
          {
            color: "#2962ff",
            lineWidth: 2,
            title: "EMA 10",
            priceLineVisible: false,
            lastValueVisible: false,
          },
          0
        );

      emaFastSeries.setData(
        calculateEma(
          orderedCandles,
          10
        )
      );

      const emaSlowSeries =
        chart.addSeries(
          LineSeries,
          {
            color: "#ff9800",
            lineWidth: 2,
            title: "EMA 30",
            priceLineVisible: false,
            lastValueVisible: false,
          },
          0
        );

      emaSlowSeries.setData(
        calculateEma(
          orderedCandles,
          30
        )
      );
    }

    if (showLevels) {
      const latestSignal =
        getLatestDirectionalSignal(
          signals
        );

      if (latestSignal !== null) {
        if (
          typeof latestSignal.entry_price ===
          "number"
        ) {
          candlestickSeries.createPriceLine({
            price: latestSignal.entry_price,
            color: "#e2e8f0",
            lineWidth: 1,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: "ENTRY",
          });
        }

        if (
          typeof latestSignal.stop_loss ===
          "number"
        ) {
          candlestickSeries.createPriceLine({
            price: latestSignal.stop_loss,
            color: "#f23645",
            lineWidth: 2,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: "SL",
          });
        }

        if (
          typeof latestSignal.take_profit_1 ===
          "number"
        ) {
          candlestickSeries.createPriceLine({
            price:
              latestSignal.take_profit_1,
            color: "#089981",
            lineWidth: 2,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: "TP1",
          });
        }

        if (
          typeof latestSignal.take_profit_2 ===
          "number"
        ) {
          candlestickSeries.createPriceLine({
            price:
              latestSignal.take_profit_2,
            color: "#14b8a6",
            lineWidth: 1,
            lineStyle: LineStyle.Dotted,
            axisLabelVisible: true,
            title: "TP2",
          });
        }

        if (
          typeof latestSignal.take_profit_3 ===
          "number"
        ) {
          candlestickSeries.createPriceLine({
            price:
              latestSignal.take_profit_3,
            color: "#06b6d4",
            lineWidth: 1,
            lineStyle: LineStyle.Dotted,
            axisLabelVisible: true,
            title: "TP3",
          });
        }
      }
    }

    // Il pane 1 contiene i volumi.
    if (showVolume) {
      const volumeSeries =
        chart.addSeries(
          HistogramSeries,
          {
            color:
              "rgba(8, 153, 129, 0.65)",
            priceFormat: {
              type: "volume",
            },
            priceLineVisible: false,
            lastValueVisible: true,
          },
          1
        );

      volumeSeries.setData(volumeData);

      // Imposta un'altezza iniziale per il pannello volume.
      window.requestAnimationFrame(() => {
        const panes = chart.panes();

        if (panes.length > 1) {
          panes[1].setHeight(160);
        }
      });
    }

    /**
     * Aggiorna il pannello OHLCV quando il crosshair si sposta.
     */
    const handleCrosshairMove = (
      parameter: MouseEventParams<Time>
    ): void => {
      if (parameter.time === undefined) {
        const latestCandle =
          orderedCandles[
            orderedCandles.length - 1
          ];

        setHoveredData({
          timestamp:
            latestCandle.timestamp,
          open: latestCandle.open,
          high: latestCandle.high,
          low: latestCandle.low,
          close: latestCandle.close,
          volume: latestCandle.volume,
        });

        return;
      }

      const timestamp =
        convertChartTimeToNumber(
          parameter.time
        );

      if (timestamp === null) {
        return;
      }

      const selectedCandle =
        candleLookup.get(timestamp);

      if (selectedCandle === undefined) {
        return;
      }

      setHoveredData({
        timestamp:
          selectedCandle.timestamp,
        open: selectedCandle.open,
        high: selectedCandle.high,
        low: selectedCandle.low,
        close: selectedCandle.close,
        volume: selectedCandle.volume,
      });
    };

    chart.subscribeCrosshairMove(
      handleCrosshairMove
    );


    const requestedBars =
      INITIAL_VISIBLE_BARS[timeframe];

    const visibleBars = Math.min(
      requestedBars,
      candleData.length
    );

    chart.timeScale().setVisibleLogicalRange({
      from: Math.max(
        0,
        candleData.length - visibleBars
      ),
      to: candleData.length + 3,
    });

    return () => {
      chart.unsubscribeCrosshairMove(
        handleCrosshairMove
      );

      chartRef.current = null;

      chart.remove();
    };
  }, [
    candles,
    signals,
    timeframe,
    showEma,
    showLevels,
    showVolume,
  ]);

  /**
   * Mostra tutte le candele disponibili.
   */
  function fitChart(): void {
    chartRef.current
      ?.timeScale()
      .fitContent();
  }

  /**
   * Torna alle ultime candele.
   */
  function goToLatestCandles(): void {
    if (chartRef.current === null) {
      return;
    }

    const requestedBars =
      INITIAL_VISIBLE_BARS[timeframe];

    const visibleBars = Math.min(
      requestedBars,
      candles.length
    );

    chartRef.current
      .timeScale()
      .setVisibleLogicalRange({
        from: Math.max(
          0,
          candles.length - visibleBars
        ),
        to: candles.length + 3,
      });
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
          onClick={() => {
            setShowVolume(
              (currentValue) =>
                !currentValue
            );
          }}
          className={
            showVolume
              ? "rounded-md border border-purple-500 bg-purple-500/10 px-3 py-1.5 text-xs font-medium text-purple-300"
              : "rounded-md border border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-400"
          }
        >
          Volume
        </button>

        <button
          type="button"
          onClick={goToLatestCandles}
          className="rounded-md border border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-400 transition-colors hover:border-blue-500 hover:text-blue-300"
        >
          Ultime candele
        </button>

        <button
          type="button"
          onClick={fitChart}
          className="rounded-md border border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-400 transition-colors hover:border-slate-500 hover:text-white"
        >
          Adatta grafico
        </button>
      </div>

      {hoveredData !== null && (
        <div className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-md border border-slate-800 bg-slate-950/70 px-3 py-2 font-mono text-xs">
          <span className="text-slate-500">
            {new Date(
              hoveredData.timestamp
            ).toLocaleString(
              "it-IT",
              {
                timeZone: "UTC",
                hour12: false,
              }
            )}
            {" UTC"}
          </span>

          <span>
            <span className="text-slate-500">
              O
            </span>
            <span className="ml-1 text-slate-300">
              {formatPrice(
                hoveredData.open
              )}
            </span>
          </span>

          <span>
            <span className="text-slate-500">
              H
            </span>
            <span className="ml-1 text-[#089981]">
              {formatPrice(
                hoveredData.high
              )}
            </span>
          </span>

          <span>
            <span className="text-slate-500">
              L
            </span>
            <span className="ml-1 text-[#f23645]">
              {formatPrice(
                hoveredData.low
              )}
            </span>
          </span>

          <span>
            <span className="text-slate-500">
              C
            </span>
            <span className="ml-1 text-slate-300">
              {formatPrice(
                hoveredData.close
              )}
            </span>
          </span>

          <span>
            <span className="text-slate-500">
              Vol
            </span>
            <span className="ml-1 text-purple-300">
              {formatVolume(
                hoveredData.volume
              )}
            </span>
          </span>
        </div>
      )}

      <div
        ref={containerRef}
        className="h-[760px] w-full overflow-hidden rounded-lg bg-[#0b1220]"
      />
    </div>
  );
}