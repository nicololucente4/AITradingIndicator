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

// Intervallo logico visibile del grafico.
type SavedLogicalRange = {
  from: number;
  to: number;
};

// Memorizza zoom e posizione separatamente
// per ogni combinazione strumento e timeframe.
const VISIBLE_RANGE_BY_MARKET =
  new Map<
    string,
    SavedLogicalRange
  >();

// Numero di barre usato solamente
// alla prima apertura di una combinazione.
const INITIAL_VISIBLE_BARS: Record<
  AvailableTimeframe,
  number
> = {
  M1: 180,
  M2: 180,
  M3: 160,
  M5: 150,
  M10: 130,
  M15: 120,
  M30: 110,
  H1: 100,
  H2: 90,
  H4: 70,
  H8: 60,
  H12: 55,
  D1: 45,
  W1: 35,
};

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

    const color =
      candle.close >=
      candle.open
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
    2 / (
      period + 1
    );

  let currentEma =
    orderedCandles[0].close;

  const emaData:
    LineData<UTCTimestamp>[] =
    [];

  for (
    const candle of
    orderedCandles
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
 * Restituisce una versione compatta del Trade ID.
 */
function getCompactTradeId(
  tradeId: string
): string {
  const tradeIdParts =
    tradeId.split(
      "-"
    );

  return (
    tradeIdParts.at(
      -1
    ) ??
    tradeId
  );
}

/**
 * Converte aperture e chiusure paper
 * in marker visualizzati sul grafico.
 */
function prepareTradeMarkers(
  trades: PaperTradeRecord[]
): SeriesMarker<UTCTimestamp>[] {
  const markers:
    SeriesMarker<UTCTimestamp>[] =
    [];

  for (
    const trade of trades
  ) {
    const compactTradeId =
      getCompactTradeId(
        trade.trade_id
      );

    // Mostra l'apertura del paper trade.
    markers.push({
      time:
        convertToUtcTimestamp(
          trade.opened_at_utc
        ),
      position:
        trade.direction ===
        "LONG"
          ? "belowBar"
          : "aboveBar",
      color:
        trade.direction ===
        "LONG"
          ? "#22c55e"
          : "#ef4444",
      shape:
        trade.direction ===
        "LONG"
          ? "arrowUp"
          : "arrowDown",
      text:
        `OPEN ${trade.direction} ${compactTradeId}`,
    });

    // Mostra la chiusura solamente
    // quando il trade è realmente concluso.
    if (
      trade.status ===
        "CLOSED" &&
      trade.closed_at_utc !==
        null
    ) {
      markers.push({
        time:
          convertToUtcTimestamp(
            trade.closed_at_utc
          ),
        position:
          trade.direction ===
          "LONG"
            ? "aboveBar"
            : "belowBar",
        color:
          "#38bdf8",
        shape:
          "circle",
        text:
          `CLOSE ${compactTradeId}`,
      });
    }
  }

  markers.sort(
    (
      firstMarker,
      secondMarker
    ) =>
      Number(
        firstMarker.time
      ) -
      Number(
        secondMarker.time
      )
  );

  return markers;
}

/**
 * Recupera l'ultima operazione ancora aperta.
 */
function getLatestOpenTrade(
  trades: PaperTradeRecord[]
): PaperTradeRecord | null {
  const openTrades =
    trades
      .filter(
        (trade) =>
          trade.status ===
          "OPEN"
      )
      .sort(
        (
          firstTrade,
          secondTrade
        ) =>
          Date.parse(
            secondTrade.opened_at_utc
          ) -
          Date.parse(
            firstTrade.opened_at_utc
          )
      );

  return (
    openTrades[0] ??
    null
  );
}

/**
 * Converte il tempo Lightweight Charts
 * in secondi Unix.
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

  const milliseconds =
    Date.UTC(
      time.year,
      time.month - 1,
      time.day
    );

  return Math.floor(
    milliseconds / 1000
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
 * Converte una candela nei dati
 * del pannello OHLCV.
 */
function candleToHoveredData(
  candle: Candle
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
 * Mostra candlestick, indicatori,
 * paper trade e volumi.
 */
export default function UnifiedMarketChart({
  candles,
  trades,
  symbol,
  timeframe,
}: UnifiedMarketChartProps) {
  // Contenitore HTML del grafico.
  const containerRef =
    useRef<
      HTMLDivElement | null
    >(
      null
    );

  // Istanza attiva del grafico.
  const chartRef =
    useRef<
      IChartApi | null
    >(
      null
    );

  // Identifica la vista in modo univoco.
  const viewKey =
    `${symbol}:${timeframe}`;

  // Controlla la visualizzazione delle EMA.
  const [
    showEma,
    setShowEma,
  ] = useState(
    true
  );

  // Controlla Entry, Stop Loss e Take Profit.
  const [
    showLevels,
    setShowLevels,
  ] = useState(
    true
  );

  // Controlla il pannello volume.
  const [
    showVolume,
    setShowVolume,
  ] = useState(
    true
  );

  // Inizializza il pannello OHLCV.
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

  useEffect(() => {
    // Il contenitore deve esistere.
    if (
      containerRef.current ===
      null
    ) {
      return;
    }

    // Non crea il grafico senza candele.
    if (
      candles.length ===
      0
    ) {
      return;
    }

    // Ordina e prepara i dati.
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

    // Indicizza le candele tramite timestamp.
    const candleLookup =
      new Map<
        number,
        Candle
      >();

    for (
      const candle of
      orderedCandles
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

    // Crea il grafico.
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
              true,
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

    // Memorizza l'istanza.
    chartRef.current =
      chart;

    // Aggiunge la serie candlestick.
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
            true,
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

    // Carica le candele.
    candlestickSeries.setData(
      candleData
    );

    // Mostra marker solo
    // per paper trade persistenti.
    if (
      trades.length >
      0
    ) {
      createSeriesMarkers(
        candlestickSeries,
        prepareTradeMarkers(
          trades
        )
      );
    }

    // Aggiunge EMA 10 ed EMA 30.
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

    // Mostra i livelli solamente
    // del trade effettivamente aperto.
    if (
      showLevels
    ) {
      const latestOpenTrade =
        getLatestOpenTrade(
          trades
        );

      if (
        latestOpenTrade !==
        null
      ) {
        candlestickSeries.createPriceLine({
          price:
            latestOpenTrade.entry_price,
          color:
            "#e2e8f0",
          lineWidth:
            1,
          lineStyle:
            LineStyle.Dashed,
          axisLabelVisible:
            true,
          title:
            "ENTRY",
        });

        candlestickSeries.createPriceLine({
          price:
            latestOpenTrade.stop_loss,
          color:
            "#f23645",
          lineWidth:
            2,
          lineStyle:
            LineStyle.Dashed,
          axisLabelVisible:
            true,
          title:
            "SL",
        });

        candlestickSeries.createPriceLine({
          price:
            latestOpenTrade.take_profit_1,
          color:
            "#089981",
          lineWidth:
            2,
          lineStyle:
            LineStyle.Dashed,
          axisLabelVisible:
            true,
          title:
            "TP1",
        });
      }
    }

    // Aggiunge il volume nel secondo pannello.
    if (
      showVolume
    ) {
      const volumeSeries =
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

      // Imposta l'altezza del volume.
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

    /**
     * Aggiorna il pannello OHLCV
     * quando il crosshair si sposta.
     */
    const handleCrosshairMove = (
      parameter:
        MouseEventParams<Time>
    ): void => {
      if (
        parameter.time ===
        undefined
      ) {
        setHoveredData(
          candleToHoveredData(
            orderedCandles[
              orderedCandles.length -
                1
            ]
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

    // Registra il crosshair.
    chart.subscribeCrosshairMove(
      handleCrosshairMove
    );

    /**
     * Memorizza ogni variazione manuale
     * dello zoom e della posizione.
     */
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

    // Recupera la vista salvata
    // per lo specifico asset e timeframe.
    const savedVisibleRange =
      VISIBLE_RANGE_BY_MARKET.get(
        viewKey
      );

    if (
      savedVisibleRange !==
      undefined
    ) {
      // Ripristina esattamente la precedente vista.
      chart
        .timeScale()
        .setVisibleLogicalRange(
          savedVisibleRange
        );
    } else {
      // Imposta la vista iniziale solamente
      // la prima volta che la combinazione viene aperta.
      const requestedBars =
        INITIAL_VISIBLE_BARS[
          timeframe
        ];

      const visibleBars =
        Math.min(
          requestedBars,
          candleData.length
        );

      const initialRange:
        SavedLogicalRange = {
          from:
            Math.max(
              0,
              candleData.length -
                visibleBars
            ),
          to:
            candleData.length +
            3,
        };

      VISIBLE_RANGE_BY_MARKET.set(
        viewKey,
        initialRange
      );

      chart
        .timeScale()
        .setVisibleLogicalRange(
          initialRange
        );
    }

    // Registra le successive variazioni manuali.
    chart
      .timeScale()
      .subscribeVisibleLogicalRangeChange(
        handleVisibleRangeChange
      );

    // Cleanup prima della ricreazione.
    return () => {
      // Salva sempre la vista corrente.
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
   * Adatta il grafico solamente
   * tramite comando manuale esplicito.
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

    // Questa è l'unica chiamata consentita a fitContent.
    chart
      .timeScale()
      .fitContent();

    // Memorizza la vista scelta manualmente.
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
          onClick={() => {
            setShowLevels(
              (
                currentValue
              ) =>
                !currentValue
            );
          }}
          className={
            showLevels
              ? "rounded-md border border-green-500 bg-green-500/10 px-3 py-1.5 text-xs font-medium text-green-300"
              : "rounded-md border border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-400"
          }
        >
          Trade Entry / SL / TP
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