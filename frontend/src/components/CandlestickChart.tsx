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
  type IChartApi,
  type LineData,
  type LogicalRange,
  type SeriesMarker,
  type UTCTimestamp,
} from "lightweight-charts";

import type {
  AvailableTimeframe,
  Candle,
  SignalRecord,
} from "@/src/types/market";

// Proprietà ricevute dal componente.
type CandlestickChartProps = {
  candles: Candle[];
  signals: SignalRecord[];
  timeframe: AvailableTimeframe;
};

// Prefisso usato per salvare una vista distinta per ogni timeframe.
const CHART_RANGE_STORAGE_PREFIX =
  "ai-trading-chart-logical-range";

// Numero iniziale di candele visualizzate per ogni timeframe.
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
  // Converte la data in millisecondi Unix.
  const milliseconds = Date.parse(timestamp);

  // Interrompe l'elaborazione se il timestamp non è valido.
  if (Number.isNaN(milliseconds)) {
    throw new Error(
      `Timestamp non valido: ${timestamp}`
    );
  }

  // Lightweight Charts utilizza secondi Unix.
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
  // Utilizza una Map per rimuovere eventuali duplicati temporali.
  const uniqueCandles = new Map<
    number,
    CandlestickData<UTCTimestamp>
  >();

  // Converte ogni candela nel formato Lightweight Charts.
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

  // Converte i valori della Map in un array.
  const preparedCandles = Array.from(
    uniqueCandles.values()
  );

  // Ordina cronologicamente le candele.
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
  // Non calcola la linea senza candele.
  if (candles.length === 0) {
    return [];
  }

  // Ordina una copia delle candele.
  const orderedCandles = [...candles].sort(
    (firstCandle, secondCandle) =>
      Date.parse(firstCandle.timestamp) -
      Date.parse(secondCandle.timestamp)
  );

  // Calcola il moltiplicatore dell'EMA.
  const multiplier = 2 / (period + 1);

  // Usa il primo Close come valore iniziale.
  let currentEma =
    orderedCandles[0].close;

  // Prepara il risultato finale.
  const emaData: LineData<UTCTimestamp>[] =
    [];

  // Calcola ricorsivamente l'EMA.
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
  // Prepara l'elenco dei marker.
  const markers: SeriesMarker<UTCTimestamp>[] =
    [];

  // Converte ogni segnale.
  for (const signal of signals) {
    const time = convertToUtcTimestamp(
      signal.timestamp
    );

    // Prepara la confidenza mostrata nel marker.
    const confidence =
      signal.prediction_confidence === null
        ? "N/D"
        : `${Math.round(
            signal.prediction_confidence * 100
          )}%`;

    // Crea il marker LONG.
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

    // Crea il marker SHORT.
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

    // Crea il marker NO_TRADE.
    markers.push({
      time,
      position: "inBar",
      color: "#94a3b8",
      shape: "circle",
      text: "NO TRADE",
    });
  }

  // Ordina cronologicamente i marker.
  markers.sort(
    (firstMarker, secondMarker) =>
      Number(firstMarker.time) -
      Number(secondMarker.time)
  );

  return markers;
}

/**
 * Verifica che il segnale abbia direzione e livelli completi.
 */
function hasDirectionalLevels(
  signal: SignalRecord
): boolean {
  // Verifica la direzione.
  const validDirection =
    signal.signal === "LONG" ||
    signal.signal === "SHORT";

  // Verifica i livelli minimi richiesti.
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
  // Filtra e ordina i segnali validi.
  const directionalSignals = signals
    .filter(hasDirectionalLevels)
    .sort(
      (firstSignal, secondSignal) =>
        Date.parse(secondSignal.timestamp) -
        Date.parse(firstSignal.timestamp)
    );

  // Restituisce null quando non esistono segnali validi.
  if (directionalSignals.length === 0) {
    return null;
  }

  return directionalSignals[0];
}

/**
 * Costruisce la chiave sessionStorage del timeframe.
 */
function buildStorageKey(
  timeframe: AvailableTimeframe
): string {
  return `${CHART_RANGE_STORAGE_PREFIX}-${timeframe}`;
}

/**
 * Verifica la validità di un intervallo logico.
 */
function isValidLogicalRange(
  value: unknown
): value is LogicalRange {
  // Il valore deve essere un oggetto.
  if (
    typeof value !== "object" ||
    value === null
  ) {
    return false;
  }

  // Recupera in modo sicuro i due limiti.
  const candidate = value as {
    from?: unknown;
    to?: unknown;
  };

  // Entrambi i limiti devono essere numeri validi.
  return (
    typeof candidate.from === "number" &&
    Number.isFinite(candidate.from) &&
    typeof candidate.to === "number" &&
    Number.isFinite(candidate.to) &&
    candidate.to > candidate.from
  );
}

/**
 * Legge la vista salvata per il timeframe.
 */
function loadStoredLogicalRange(
  storageKey: string
): LogicalRange | null {
  try {
    // Recupera il valore salvato.
    const storedValue =
      window.sessionStorage.getItem(
        storageKey
      );

    // Nessuna vista è ancora disponibile.
    if (storedValue === null) {
      return null;
    }

    // Converte il JSON.
    const parsedValue: unknown =
      JSON.parse(storedValue);

    // Elimina valori non validi.
    if (!isValidLogicalRange(parsedValue)) {
      window.sessionStorage.removeItem(
        storageKey
      );

      return null;
    }

    return parsedValue;
  } catch {
    // La dashboard continua a funzionare
    // anche senza sessionStorage.
    return null;
  }
}

/**
 * Salva la vista corrente del timeframe.
 */
function saveLogicalRange(
  storageKey: string,
  logicalRange: LogicalRange | null
): void {
  // Non salva intervalli nulli.
  if (logicalRange === null) {
    return;
  }

  try {
    // Salva l'intervallo come JSON.
    window.sessionStorage.setItem(
      storageKey,
      JSON.stringify(logicalRange)
    );
  } catch {
    // La dashboard continua a funzionare
    // anche se sessionStorage non è disponibile.
  }
}

/**
 * Applica la vista iniziale prevista per il timeframe.
 */
function applyInitialVisibleRange(
  chart: IChartApi,
  candleCount: number,
  timeframe: AvailableTimeframe
): void {
  // Recupera il numero desiderato di candele.
  const requestedBars =
    INITIAL_VISIBLE_BARS[timeframe];

  // Limita il valore alla quantità realmente disponibile.
  const visibleBars = Math.min(
    requestedBars,
    candleCount
  );

  // Calcola l'inizio della finestra.
  const fromValue = Math.max(
    0,
    candleCount - visibleBars
  );

  // Aggiunge spazio sulla destra dell'ultima candela.
  const toValue = candleCount + 3;

  // Applica la finestra iniziale.
  chart.timeScale().setVisibleLogicalRange({
    from: fromValue,
    to: toValue,
  });
}

/**
 * Visualizza candele, EMA, marker e livelli.
 */
export default function CandlestickChart({
  candles,
  signals,
  timeframe,
}: CandlestickChartProps) {
  // Mantiene il riferimento al contenitore.
  const containerRef =
    useRef<HTMLDivElement | null>(null);

  // Mantiene il riferimento al grafico corrente.
  const chartRef =
    useRef<IChartApi | null>(null);

  // Costruisce la chiave specifica del timeframe.
  const storageKey =
    buildStorageKey(timeframe);

  // Gestisce la visibilità delle EMA.
  const [showEma, setShowEma] =
    useState(true);

  // Gestisce la visibilità dei livelli.
  const [showLevels, setShowLevels] =
    useState(true);

  useEffect(() => {
    // Attende il contenitore HTML.
    if (!containerRef.current) {
      return;
    }

    // Non crea il grafico senza dati.
    if (candles.length === 0) {
      return;
    }

    // Prepara le candele.
    const chartData =
      prepareCandlestickData(candles);

    // Controllo difensivo.
    if (chartData.length === 0) {
      return;
    }

    // Recupera i limiti temporali disponibili.
    const firstCandleTime = Number(
      chartData[0].time
    );

    const lastCandleTime = Number(
      chartData[chartData.length - 1].time
    );

    // Mantiene solamente i segnali visibili.
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

    // Crea il grafico.
    const chart = createChart(
      containerRef.current,
      {
        // Adatta il grafico al contenitore.
        autoSize: true,

        // Configura il tema.
        layout: {
          background: {
            type: ColorType.Solid,
            color: "#0b1220",
          },
          textColor: "#94a3b8",
          fontFamily:
            "Inter, ui-sans-serif, system-ui, sans-serif",
        },

        // Configura una griglia più sottile.
        grid: {
          vertLines: {
            color: "#162033",
          },
          horzLines: {
            color: "#162033",
          },
        },

        // Configura la scala prezzi.
        rightPriceScale: {
          borderColor: "#263449",
          autoScale: true,
          scaleMargins: {
            top: 0.10,
            bottom: 0.10,
          },
        },

        // Configura la scala temporale.
        timeScale: {
          borderColor: "#263449",
          timeVisible: true,
          secondsVisible: false,
          rightOffset: 3,
          barSpacing: 9,
          minBarSpacing: 2,
          fixLeftEdge: false,
          fixRightEdge: false,
          lockVisibleTimeRangeOnResize: true,
          rightBarStaysOnScroll: true,
        },

        // Configura il crosshair.
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

        // Abilita lo scorrimento.
        handleScroll: {
          mouseWheel: true,
          pressedMouseMove: true,
          horzTouchDrag: true,
          vertTouchDrag: false,
        },

        // Abilita lo zoom.
        handleScale: {
          axisPressedMouseMove: true,
          mouseWheel: true,
          pinch: true,
        },
      }
    );

    // Salva il riferimento al grafico.
    chartRef.current = chart;

    // Crea la serie candlestick.
    const candlestickSeries =
      chart.addSeries(
        CandlestickSeries,
        {
          // Colore delle candele rialziste.
          upColor: "#089981",
          wickUpColor: "#089981",
          borderUpColor: "#089981",

          // Colore delle candele ribassiste.
          downColor: "#f23645",
          wickDownColor: "#f23645",
          borderDownColor: "#f23645",

          // Visualizza il prezzo corrente.
          priceLineVisible: true,
          lastValueVisible: true,

          // Configura EURUSD a cinque decimali.
          priceFormat: {
            type: "price",
            precision: 5,
            minMove: 0.00001,
          },
        }
      );

    // Carica le candele.
    candlestickSeries.setData(chartData);

    // Aggiunge i marker.
    if (visibleSignals.length > 0) {
      createSeriesMarkers(
        candlestickSeries,
        prepareSignalMarkers(
          visibleSignals
        )
      );
    }

    // Aggiunge le EMA.
    if (showEma) {
      // Crea EMA 10.
      const emaFastSeries =
        chart.addSeries(
          LineSeries,
          {
            color: "#2962ff",
            lineWidth: 2,
            title: "EMA 10",
            priceLineVisible: false,
            lastValueVisible: false,
          }
        );

      // Carica EMA 10.
      emaFastSeries.setData(
        calculateEma(candles, 10)
      );

      // Crea EMA 30.
      const emaSlowSeries =
        chart.addSeries(
          LineSeries,
          {
            color: "#ff9800",
            lineWidth: 2,
            title: "EMA 30",
            priceLineVisible: false,
            lastValueVisible: false,
          }
        );

      // Carica EMA 30.
      emaSlowSeries.setData(
        calculateEma(candles, 30)
      );
    }

    // Aggiunge i livelli dell'ultimo segnale.
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

        // Disegna Entry.
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

        // Disegna Stop Loss.
        if (
          typeof stopLoss === "number"
        ) {
          candlestickSeries.createPriceLine({
            price: stopLoss,
            color: "#f23645",
            lineWidth: 2,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: "SL",
          });
        }

        // Disegna TP1.
        if (
          typeof takeProfit1 === "number"
        ) {
          candlestickSeries.createPriceLine({
            price: takeProfit1,
            color: "#089981",
            lineWidth: 2,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: "TP1",
          });
        }

        // Disegna TP2.
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

        // Disegna TP3.
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
     * Salva ogni modifica di zoom o posizione.
     */
    const handleRangeChange = (
      logicalRange: LogicalRange | null
    ): void => {
      saveLogicalRange(
        storageKey,
        logicalRange
      );
    };

    // Registra il listener della scala temporale.
    chart
      .timeScale()
      .subscribeVisibleLogicalRangeChange(
        handleRangeChange
      );

    // Recupera la vista salvata del timeframe.
    const storedRange =
      loadStoredLogicalRange(
        storageKey
      );

    // Ripristina la vista oppure applica quella iniziale.
    if (storedRange !== null) {
      chart
        .timeScale()
        .setVisibleLogicalRange(
          storedRange
        );
    } else {
      applyInitialVisibleRange(
        chart,
        chartData.length,
        timeframe
      );
    }

    // Rimuove il grafico in modo sicuro.
    return () => {
      // Recupera e salva la vista corrente.
      const currentRange = chart
        .timeScale()
        .getVisibleLogicalRange();

      saveLogicalRange(
        storageKey,
        currentRange
      );

      // Rimuove il listener.
      chart
        .timeScale()
        .unsubscribeVisibleLogicalRangeChange(
          handleRangeChange
        );

      // Elimina il riferimento.
      chartRef.current = null;

      // Distrugge il grafico.
      chart.remove();
    };
  }, [
    candles,
    signals,
    showEma,
    showLevels,
    storageKey,
    timeframe,
  ]);

  /**
   * Adatta il grafico a tutte le candele.
   */
  function fitChart(): void {
    // Elimina la vista memorizzata.
    window.sessionStorage.removeItem(
      storageKey
    );

    // Adatta il grafico corrente.
    chartRef.current
      ?.timeScale()
      .fitContent();
  }

  /**
   * Mostra le ultime candele del timeframe.
   */
  function goToLatestCandles(): void {
    // Verifica che il grafico sia disponibile.
    if (chartRef.current === null) {
      return;
    }

    // Applica una nuova finestra sulle ultime candele.
    applyInitialVisibleRange(
      chartRef.current,
      candles.length,
      timeframe
    );

    // Salva la nuova vista.
    const currentRange = chartRef.current
      .timeScale()
      .getVisibleLogicalRange();

    saveLogicalRange(
      storageKey,
      currentRange
    );
  }

  /**
   * Ripristina solo la vista del timeframe corrente.
   */
  function resetSavedView(): void {
    // Elimina la vista corrente.
    window.sessionStorage.removeItem(
      storageKey
    );

    // Torna alle ultime candele.
    goToLatestCandles();
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

        <button
          type="button"
          onClick={resetSavedView}
          className="rounded-md border border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-400 transition-colors hover:border-slate-500 hover:text-white"
        >
          Ripristina vista
        </button>

        <div className="ml-auto flex items-center gap-4 text-xs">
          <span className="text-blue-500">
            EMA 10
          </span>

          <span className="text-orange-400">
            EMA 30
          </span>
        </div>
      </div>

      <div
        ref={containerRef}
        className="h-[600px] w-full overflow-hidden rounded-lg bg-[#0b1220]"
      />
    </div>
  );
}