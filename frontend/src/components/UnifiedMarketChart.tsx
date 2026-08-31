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
  HistogramSeries,
  LineSeries,
  LineStyle,
  type CandlestickData,
  type HistogramData,
  type IChartApi,
  type LineData,
  type MouseEventParams,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";

import {
  createTradeMarkerItems,
  TradeMarkersPrimitive,
} from "@/src/components/TradeMarkersPrimitive";

import {
  getLiveTick,
} from "@/src/services/api";

import type {
  AvailableTimeframe,
  Candle,
  LiveMarketTick,
  PaperTradeRecord,
} from "@/src/types/market";

// Proprietà ricevute dal componente.
type UnifiedMarketChartProps = {
  candles: Candle[];
  trades: PaperTradeRecord[];
  symbol: string;
  timeframe: AvailableTimeframe;
};

// Valori visualizzati nel pannello OHLCV.
type HoveredMarketData = {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

// Candela corrente costruita dai tick MT5.
type LiveCandleData = {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

// Intervallo logico visibile del grafico.
type SavedLogicalRange = {
  from: number;
  to: number;
};

// Memorizza la vista separatamente
// per ogni combinazione simbolo e timeframe.
const VISIBLE_RANGE_BY_MARKET =
  new Map<
    string,
    SavedLogicalRange
  >();

// Durata in minuti dei timeframe.
const TIMEFRAME_MINUTES: Record<
  AvailableTimeframe,
  number
> = {
  M1: 1,
  M2: 2,
  M3: 3,
  M5: 5,
  M10: 10,
  M15: 15,
  M30: 30,
  H1: 60,
  H2: 120,
  H4: 240,
  H8: 480,
  H12: 720,
  D1: 1440,
  W1: 10080,
};

// Frequenza di aggiornamento del tick.
const LIVE_TICK_INTERVAL_MS =
  1000;

/**
 * Converte un timestamp ISO in secondi Unix.
 */
function convertToUtcTimestamp(
  timestamp: string
): UTCTimestamp {
  const milliseconds =
    Date.parse(
      timestamp
    );

  if (
    Number.isNaN(
      milliseconds
    )
  ) {
    throw new Error(
      `Timestamp non valido: ${timestamp}`
    );
  }

  return Math.floor(
    milliseconds / 1000
  ) as UTCTimestamp;
}

/**
 * Ordina le candele cronologicamente.
 */
function orderCandles(
  candles: Candle[]
): Candle[] {
  return [...candles].sort(
    (
      firstCandle,
      secondCandle
    ) =>
      Date.parse(
        firstCandle.timestamp
      ) -
      Date.parse(
        secondCandle.timestamp
      )
  );
}

/**
 * Calcola l'inizio della candela corrente.
 */
function getLiveCandleTimestamp(
  timestamp: string,
  timeframe: AvailableTimeframe
): string {
  const selectedDate =
    new Date(
      timestamp
    );

  const timestampMilliseconds =
    selectedDate.getTime();

  if (
    Number.isNaN(
      timestampMilliseconds
    )
  ) {
    throw new Error(
      `Timestamp live non valido: ${timestamp}`
    );
  }

  // La candela settimanale parte dal lunedì UTC.
  if (
    timeframe === "W1"
  ) {
    const day =
      selectedDate.getUTCDay();

    const daysFromMonday =
      day === 0
        ? 6
        : day - 1;

    selectedDate.setUTCDate(
      selectedDate.getUTCDate() -
        daysFromMonday
    );

    selectedDate.setUTCHours(
      0,
      0,
      0,
      0
    );

    return selectedDate.toISOString();
  }

  const timeframeMilliseconds =
    TIMEFRAME_MINUTES[
      timeframe
    ] *
    60 *
    1000;

  const bucketMilliseconds =
    Math.floor(
      timestampMilliseconds /
        timeframeMilliseconds
    ) *
    timeframeMilliseconds;

  return new Date(
    bucketMilliseconds
  ).toISOString();
}

/**
 * Converte le candele nel formato Lightweight Charts.
 */
function prepareCandlestickData(
  candles: Candle[]
): CandlestickData<UTCTimestamp>[] {
  const uniqueCandles =
    new Map<
      number,
      CandlestickData<UTCTimestamp>
    >();

  for (
    const candle of candles
  ) {
    const time =
      convertToUtcTimestamp(
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

  const preparedCandles =
    Array.from(
      uniqueCandles.values()
    );

  preparedCandles.sort(
    (
      firstCandle,
      secondCandle
    ) =>
      Number(
        firstCandle.time
      ) -
      Number(
        secondCandle.time
      )
  );

  return preparedCandles;
}

/**
 * Converte le candele nella serie dei volumi.
 */
function prepareVolumeData(
  candles: Candle[]
): HistogramData<UTCTimestamp>[] {
  const uniqueVolumes =
    new Map<
      number,
      HistogramData<UTCTimestamp>
    >();

  for (
    const candle of candles
  ) {
    const time =
      convertToUtcTimestamp(
        candle.timestamp
      );

    uniqueVolumes.set(
      Number(time),
      {
        time,
        value: candle.volume,
        color:
          candle.close >=
          candle.open
            ? "rgba(8, 153, 129, 0.65)"
            : "rgba(242, 54, 69, 0.65)",
      }
    );
  }

  const preparedVolumes =
    Array.from(
      uniqueVolumes.values()
    );

  preparedVolumes.sort(
    (
      firstVolume,
      secondVolume
    ) =>
      Number(
        firstVolume.time
      ) -
      Number(
        secondVolume.time
      )
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
  if (
    candles.length === 0
  ) {
    return [];
  }

  const orderedCandles =
    orderCandles(
      candles
    );

  const multiplier =
    2 /
    (
      period + 1
    );

  let currentEma =
    orderedCandles[0].close;

  const emaData:
    LineData<UTCTimestamp>[] =
    [];

  for (
    const candle of orderedCandles
  ) {
    currentEma =
      candle.close *
        multiplier +
      currentEma *
        (
          1 - multiplier
        );

    emaData.push({
      time:
        convertToUtcTimestamp(
          candle.timestamp
        ),
      value:
        currentEma,
    });
  }

  return emaData;
}

/**
 * Restituisce un alias leggibile del trade.
 */
function getTradeAlias(
  trade: PaperTradeRecord,
  index: number
): string {
  const directionPrefix =
    trade.direction === "LONG"
      ? "L"
      : "S";

  return `${directionPrefix}-${String(
    index + 1
  ).padStart(
    2,
    "0"
  )}`;
}


/**
 * Recupera l'ultima posizione ancora aperta.
 */
function getLatestOpenTrade(
  trades: PaperTradeRecord[]
): {
  trade: PaperTradeRecord;
  alias: string;
} | null {
  const orderedTrades =
    [...trades].sort(
      (
        firstTrade,
        secondTrade
      ) =>
        Date.parse(
          firstTrade.opened_at_utc
        ) -
        Date.parse(
          secondTrade.opened_at_utc
        )
    );

  const openTradeIndex =
    orderedTrades.findIndex(
      (trade) =>
        trade.status ===
        "OPEN"
    );

  if (
    openTradeIndex ===
    -1
  ) {
    return null;
  }

  return {
    trade:
      orderedTrades[
        openTradeIndex
      ],
    alias:
      getTradeAlias(
        orderedTrades[
          openTradeIndex
        ],
        openTradeIndex
      ),
  };
}

/**
 * Converte il tempo del grafico in secondi Unix.
 */
function convertChartTimeToNumber(
  time: Time
): number | null {
  if (
    typeof time ===
    "number"
  ) {
    return time;
  }

  if (
    typeof time ===
    "string"
  ) {
    const parsedMilliseconds =
      Date.parse(
        time
      );

    if (
      Number.isNaN(
        parsedMilliseconds
      )
    ) {
      return null;
    }

    return Math.floor(
      parsedMilliseconds /
        1000
    );
  }

  return Math.floor(
    Date.UTC(
      time.year,
      time.month - 1,
      time.day
    ) /
      1000
  );
}

/**
 * Restituisce il numero di decimali appropriato.
 */
function getPricePrecision(
  symbol: string
): number {
  if (
    symbol.includes(
      "JPY"
    )
  ) {
    return 3;
  }

  if (
    symbol ===
    "XAUUSD"
  ) {
    return 2;
  }

  return 5;
}

/**
 * Restituisce il movimento minimo del prezzo.
 */
function getMinimumPriceMovement(
  symbol: string
): number {
  if (
    symbol.includes(
      "JPY"
    )
  ) {
    return 0.001;
  }

  if (
    symbol ===
    "XAUUSD"
  ) {
    return 0.01;
  }

  return 0.00001;
}

/**
 * Formatta un prezzo.
 */
function formatPrice(
  value: number,
  symbol: string
): string {
  return value.toFixed(
    getPricePrecision(
      symbol
    )
  );
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
  ).format(
    value
  );
}

/**
 * Converte una candela nei dati del pannello OHLCV.
 */
function candleToHoveredData(
  candle: Candle | LiveCandleData
): HoveredMarketData {
  return {
    timestamp:
      candle.timestamp,
    open:
      candle.open,
    high:
      candle.high,
    low:
      candle.low,
    close:
      candle.close,
    volume:
      candle.volume,
  };
}

/**
 * Costruisce o aggiorna la candela live.
 */
function updateLiveCandle(
  previousCandle: LiveCandleData | null,
  tick: LiveMarketTick,
  timeframe: AvailableTimeframe
): LiveCandleData {
  const candleTimestamp =
    getLiveCandleTimestamp(
      tick.timestamp,
      timeframe
    );

  const livePrice =
    tick.bid;

  if (
    previousCandle ===
      null ||
    previousCandle.timestamp !==
      candleTimestamp
  ) {
    return {
      timestamp:
        candleTimestamp,
      open:
        livePrice,
      high:
        livePrice,
      low:
        livePrice,
      close:
        livePrice,
      volume:
        0,
    };
  }

  return {
    timestamp:
      previousCandle.timestamp,
    open:
      previousCandle.open,
    high:
      Math.max(
        previousCandle.high,
        livePrice
      ),
    low:
      Math.min(
        previousCandle.low,
        livePrice
      ),
    close:
      livePrice,
    volume:
      previousCandle.volume,
  };
}

/**
 * Mostra candlestick, prezzo live,
 * indicatori, paper trade e volumi.
 */
export default function UnifiedMarketChart({
  candles,
  trades,
  symbol,
  timeframe,
}: UnifiedMarketChartProps) {
  const containerRef =
    useRef<
      HTMLDivElement | null
    >(
      null
    );

  const chartRef =
    useRef<
      IChartApi | null
    >(
      null
    );

  // Identifica la vista di ogni combinazione.
  const viewKey =
    `${symbol}:${timeframe}`;

  const [
    showEma,
    setShowEma,
  ] = useState(
    true
  );

  const [
    showLevels,
    setShowLevels,
  ] = useState(
    true
  );

  const [
    showVolume,
    setShowVolume,
  ] = useState(
    true
  );

  const [
    hoveredData,
    setHoveredData,
  ] = useState<
    HoveredMarketData | null
  >(
    () => {
      if (
        candles.length ===
        0
      ) {
        return null;
      }

      return candleToHoveredData(
        candles[
          candles.length - 1
        ]
      );
    }
  );

  const [
    liveTick,
    setLiveTick,
  ] = useState<
    LiveMarketTick | null
  >(
    null
  );

  const [
    liveTickError,
    setLiveTickError,
  ] = useState(
    false
  );

  useEffect(() => {
    if (
      containerRef.current ===
        null ||
      candles.length ===
        0
    ) {
      return;
    }

    const orderedCandles =
      orderCandles(
        candles
      );

    const candleData =
      prepareCandlestickData(
        orderedCandles
      );

    const volumeData =
      prepareVolumeData(
        orderedCandles
      );

    if (
      candleData.length ===
      0
    ) {
      return;
    }

    const candleLookup =
      new Map<
        number,
        Candle | LiveCandleData
      >();

    for (
      const candle of orderedCandles
    ) {
      candleLookup.set(
        Number(
          convertToUtcTimestamp(
            candle.timestamp
          )
        ),
        candle
      );
    }

    const chart =
      createChart(
        containerRef.current,
        {
          autoSize:
            true,
          layout: {
            background: {
              type:
                ColorType.Solid,
              color:
                "#0b1220",
            },
            textColor:
              "#94a3b8",
            fontFamily:
              "Inter, ui-sans-serif, system-ui, sans-serif",
            panes: {
              separatorColor:
                "#263449",
              separatorHoverColor:
                "#3b82f6",
              enableResize:
                true,
            },
          },
          grid: {
            vertLines: {
              color:
                "#162033",
            },
            horzLines: {
              color:
                "#162033",
            },
          },
          rightPriceScale: {
            borderColor:
              "#263449",
            scaleMargins: {
              top:
                0.08,
              bottom:
                0.08,
            },
          },
          timeScale: {
            borderColor:
              "#263449",
            timeVisible:
              true,
            secondsVisible:
              false,
            rightOffset:
              3,
            barSpacing:
              9,
            minBarSpacing:
              2,
            lockVisibleTimeRangeOnResize:
              true,
            rightBarStaysOnScroll:
              false,
          },
          crosshair: {
            vertLine: {
              color:
                "#64748b",
              width:
                1,
              style:
                LineStyle.Dashed,
              labelBackgroundColor:
                "#334155",
            },
            horzLine: {
              color:
                "#64748b",
              width:
                1,
              style:
                LineStyle.Dashed,
              labelBackgroundColor:
                "#334155",
            },
          },
          handleScroll: {
            mouseWheel:
              true,
            pressedMouseMove:
              true,
            horzTouchDrag:
              true,
            vertTouchDrag:
              false,
          },
          handleScale: {
            axisPressedMouseMove:
              true,
            mouseWheel:
              true,
            pinch:
              true,
          },
        }
      );

    chartRef.current =
      chart;

    const candlestickSeries =
      chart.addSeries(
        CandlestickSeries,
        {
          upColor:
            "#089981",
          wickUpColor:
            "#089981",
          borderUpColor:
            "#089981",
          downColor:
            "#f23645",
          wickDownColor:
            "#f23645",
          borderDownColor:
            "#f23645",
          priceLineVisible:
            false,
          lastValueVisible:
            true,
          priceFormat: {
            type:
              "price",
            precision:
              getPricePrecision(
                symbol
              ),
            minMove:
              getMinimumPriceMovement(
                symbol
              ),
          },
        },
        0
      );

    candlestickSeries.setData(
      candleData
    );

    // Crea la linea del prezzo BID live.
    const livePriceLine =
      candlestickSeries.createPriceLine({
        price:
          orderedCandles[
            orderedCandles.length - 1
          ].close,
        color:
          "#facc15",
        lineWidth:
          1,
        lineStyle:
          LineStyle.Dashed,
        axisLabelVisible:
          true,
        title:
          "LIVE BID",
      });

    // Crea i marker personalizzati ancorati
    // al prezzo effettivo di apertura e chiusura.
    const tradeMarkersPrimitive =
      new TradeMarkersPrimitive(
        createTradeMarkerItems(
          trades,
          timeframe
        )
      );

    // Collega la primitive alla serie candlestick.
    candlestickSeries.attachPrimitive(
      tradeMarkersPrimitive
    );

    if (
      showEma
    ) {
      const emaFastSeries =
        chart.addSeries(
          LineSeries,
          {
            color:
              "#2962ff",
            lineWidth:
              2,
            title:
              "EMA 10",
            priceLineVisible:
              false,
            lastValueVisible:
              false,
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
            color:
              "#ff9800",
            lineWidth:
              2,
            title:
              "EMA 30",
            priceLineVisible:
              false,
            lastValueVisible:
              false,
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

    const openTradeInformation =
      getLatestOpenTrade(
        trades
      );

    if (
      showLevels &&
      openTradeInformation !==
        null
    ) {
      const {
        trade,
        alias,
      } =
        openTradeInformation;

      candlestickSeries.createPriceLine({
        price:
          trade.entry_price,
        color:
          "#e2e8f0",
        lineWidth:
          1,
        lineStyle:
          LineStyle.Dashed,
        axisLabelVisible:
          true,
        title:
          `${alias} ENTRY`,
      });

      candlestickSeries.createPriceLine({
        price:
          trade.stop_loss,
        color:
          "#f23645",
        lineWidth:
          2,
        lineStyle:
          LineStyle.Dashed,
        axisLabelVisible:
          true,
        title:
          `${alias} SL`,
      });

      candlestickSeries.createPriceLine({
        price:
          trade.take_profit_1,
        color:
          "#22c55e",
        lineWidth:
          2,
        lineStyle:
          LineStyle.Dashed,
        axisLabelVisible:
          true,
        title:
          `${alias} TP`,
      });
    }

    let volumeSeries:
      ReturnType<
        typeof chart.addSeries
      > | null =
      null;

    if (
      showVolume
    ) {
      volumeSeries =
        chart.addSeries(
          HistogramSeries,
          {
            color:
              "rgba(8, 153, 129, 0.65)",
            priceFormat: {
              type:
                "volume",
            },
            priceLineVisible:
              false,
            lastValueVisible:
              true,
          },
          1
        );

      volumeSeries.setData(
        volumeData
      );

      window.requestAnimationFrame(
        () => {
          const panes =
            chart.panes();

          if (
            panes.length >
            1
          ) {
            panes[1].setHeight(
              160
            );
          }
        }
      );
    }
    const handleCrosshairMove = (
      parameter:
        MouseEventParams<Time>
    ): void => {
      if (
        parameter.time ===
        undefined
      ) {
        const latestCandle =
          liveCandle ??
          orderedCandles[
            orderedCandles.length - 1
          ];

        setHoveredData(
          candleToHoveredData(
            latestCandle
          )
        );

        return;
      }

      const timestamp =
        convertChartTimeToNumber(
          parameter.time
        );

      if (
        timestamp ===
        null
      ) {
        return;
      }

      const selectedCandle =
        candleLookup.get(
          timestamp
        );

      if (
        selectedCandle ===
        undefined
      ) {
        return;
      }

      setHoveredData(
        candleToHoveredData(
          selectedCandle
        )
      );
    };

    chart.subscribeCrosshairMove(
      handleCrosshairMove
    );

    const handleVisibleRangeChange = (
      logicalRange:
        | SavedLogicalRange
        | null
    ): void => {
      if (
        logicalRange ===
        null
      ) {
        return;
      }

      VISIBLE_RANGE_BY_MARKET.set(
        viewKey,
        {
          from:
            logicalRange.from,
          to:
            logicalRange.to,
        }
      );
    };

    const savedVisibleRange =
      VISIBLE_RANGE_BY_MARKET.get(
        viewKey
      );

    if (
      savedVisibleRange !==
      undefined
    ) {
      chart
        .timeScale()
        .setVisibleLogicalRange(
          savedVisibleRange
        );
    }

    chart
      .timeScale()
      .subscribeVisibleLogicalRangeChange(
        handleVisibleRangeChange
      );

    let liveCandle:
      LiveCandleData | null =
      null;

    let pollingActive =
      true;

    let requestRunning =
      false;

    /**
     * Aggiorna prezzo e candela live senza
     * ricreare il grafico o cambiare la vista.
     */
    const refreshLiveTick =
      async (): Promise<void> => {
        if (
          requestRunning ||
          !pollingActive
        ) {
          return;
        }

        requestRunning =
          true;

        try {
          const tick =
            await getLiveTick(
              symbol
            );

          if (
            !pollingActive
          ) {
            return;
          }

          setLiveTick(
            tick
          );

          setLiveTickError(
            false
          );

          liveCandle =
            updateLiveCandle(
              liveCandle,
              tick,
              timeframe
            );

          const liveTime =
            convertToUtcTimestamp(
              liveCandle.timestamp
            );

          candlestickSeries.update({
            time:
              liveTime,
            open:
              liveCandle.open,
            high:
              liveCandle.high,
            low:
              liveCandle.low,
            close:
              liveCandle.close,
          });

          candleLookup.set(
            Number(
              liveTime
            ),
            liveCandle
          );

          if (
            volumeSeries !==
            null
          ) {
            volumeSeries.update({
              time:
                liveTime,
              value:
                liveCandle.volume,
              color:
                liveCandle.close >=
                liveCandle.open
                  ? "rgba(8, 153, 129, 0.65)"
                  : "rgba(242, 54, 69, 0.65)",
            });
          }

          // Aggiorna la linea senza cambiare scala o vista.
          livePriceLine.applyOptions({
            price:
              tick.bid,
            title:
              "LIVE BID",
          });

          setHoveredData(
            candleToHoveredData(
              liveCandle
            )
          );
        } catch (error) {
          console.error(
            "Impossibile aggiornare il tick live sul grafico:",
            error
          );

          if (
            pollingActive
          ) {
            setLiveTickError(
              true
            );
          }
        } finally {
          requestRunning =
            false;
        }
      };

    void refreshLiveTick();

    const pollingInterval =
      window.setInterval(
        () => {
          void refreshLiveTick();
        },
        LIVE_TICK_INTERVAL_MS
      );

    return () => {
      pollingActive =
        false;

      window.clearInterval(
        pollingInterval
      );

      const currentVisibleRange =
        chart
          .timeScale()
          .getVisibleLogicalRange();

      if (
        currentVisibleRange !==
        null
      ) {
        VISIBLE_RANGE_BY_MARKET.set(
          viewKey,
          {
            from:
              currentVisibleRange.from,
            to:
              currentVisibleRange.to,
          }
        );
      }

      chart
        .timeScale()
        .unsubscribeVisibleLogicalRangeChange(
          handleVisibleRangeChange
        );

      chart.unsubscribeCrosshairMove(
        handleCrosshairMove
      );

      // Scollega i marker personalizzati
      // prima di eliminare il grafico.
      candlestickSeries.detachPrimitive(
        tradeMarkersPrimitive
      );

      chartRef.current =
        null;

      chart.remove();
    };
  }, [
    candles,
    trades,
    symbol,
    timeframe,
    viewKey,
    showEma,
    showLevels,
    showVolume,
  ]);

  /**
   * Adatta il grafico solo tramite clic manuale.
   */
  function fitChart(): void {
    const chart =
      chartRef.current;

    if (
      chart ===
      null
    ) {
      return;
    }

    chart
      .timeScale()
      .fitContent();

    const visibleRange =
      chart
        .timeScale()
        .getVisibleLogicalRange();

    if (
      visibleRange !==
      null
    ) {
      VISIBLE_RANGE_BY_MARKET.set(
        viewKey,
        {
          from:
            visibleRange.from,
          to:
            visibleRange.to,
        }
      );
    }
  }

  const openTradeInformation =
    getLatestOpenTrade(
      trades
    );

  const levelsButtonLabel =
    openTradeInformation ===
    null
      ? "Nessun trade aperto"
      : `Livelli ${openTradeInformation.alias}`;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => {
            setShowEma(
              (
                currentValue
              ) =>
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
          disabled={
            openTradeInformation ===
            null
          }
          onClick={() => {
            setShowLevels(
              (
                currentValue
              ) =>
                !currentValue
            );
          }}
          className={
            openTradeInformation ===
            null
              ? "cursor-not-allowed rounded-md border border-slate-800 px-3 py-1.5 text-xs font-medium text-slate-600"
              : showLevels
                ? "rounded-md border border-green-500 bg-green-500/10 px-3 py-1.5 text-xs font-medium text-green-300"
                : "rounded-md border border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-400"
          }
        >
          {levelsButtonLabel}
        </button>

        <button
          type="button"
          onClick={() => {
            setShowVolume(
              (
                currentValue
              ) =>
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
          onClick={
            fitChart
          }
          className="rounded-md border border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-400 transition-colors hover:border-slate-500 hover:text-white"
        >
          Adatta grafico
        </button>

        <div className="ml-auto flex items-center gap-2 rounded-md border border-yellow-500/30 bg-yellow-500/5 px-3 py-1.5 text-xs">
          <span
            className={
              liveTickError
                ? "h-2 w-2 rounded-full bg-red-500"
                : "h-2 w-2 rounded-full bg-yellow-400"
            }
          />

          <span className="text-slate-400">
            LIVE BID
          </span>

          <span className="font-mono font-semibold text-yellow-300">
            {liveTick === null
              ? "N/D"
              : formatPrice(
                  liveTick.bid,
                  symbol
                )}
          </span>
        </div>
      </div>

      {hoveredData !== null && (
        <div className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-md border border-slate-800 bg-slate-950/70 px-3 py-2 font-mono text-xs">
          <span className="text-slate-500">
            {new Date(
              hoveredData.timestamp
            ).toLocaleString(
              "it-IT",
              {
                timeZone:
                  "UTC",
                hour12:
                  false,
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
                hoveredData.open,
                symbol
              )}
            </span>
          </span>

          <span>
            <span className="text-slate-500">
              H
            </span>

            <span className="ml-1 text-[#089981]">
              {formatPrice(
                hoveredData.high,
                symbol
              )}
            </span>
          </span>

          <span>
            <span className="text-slate-500">
              L
            </span>

            <span className="ml-1 text-[#f23645]">
              {formatPrice(
                hoveredData.low,
                symbol
              )}
            </span>
          </span>

          <span>
            <span className="text-slate-500">
              C
            </span>

            <span className="ml-1 text-slate-300">
              {formatPrice(
                hoveredData.close,
                symbol
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
        ref={
          containerRef
        }
        className="h-[760px] w-full overflow-hidden rounded-lg bg-[#0b1220]"
      />
    </div>
  );
}
