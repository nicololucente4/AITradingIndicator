"use client";

// Importa gli hook React necessari.
import { useEffect, useRef } from "react";

// Importa Lightweight Charts.
import {
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  type CandlestickData,
  type SeriesMarker,
  type UTCTimestamp,
} from "lightweight-charts";

// Importa i tipi condivisi del progetto.
import type {
  Candle,
  SignalRecord,
} from "@/src/types/market";

// Definisce le proprietà del componente.
type CandlestickChartProps = {
  candles: Candle[];
  signals: SignalRecord[];
};

/**
 * Converte un timestamp ISO in Unix timestamp espresso in secondi.
 */
function convertToUtcTimestamp(
  timestamp: string
): UTCTimestamp {
  // Converte il timestamp in millisecondi Unix.
  const milliseconds = Date.parse(timestamp);

  // Blocca eventuali timestamp non validi.
  if (Number.isNaN(milliseconds)) {
    throw new Error(
      `Timestamp non valido: ${timestamp}`
    );
  }

  // Lightweight Charts richiede secondi Unix.
  return Math.floor(
    milliseconds / 1000
  ) as UTCTimestamp;
}

/**
 * Converte e ordina le candele ricevute da FastAPI.
 */
function prepareCandlestickData(
  candles: Candle[]
): CandlestickData<UTCTimestamp>[] {
  // Usa una Map per eliminare eventuali timestamp duplicati.
  const uniqueCandles = new Map<
    number,
    CandlestickData<UTCTimestamp>
  >();

  for (const candle of candles) {
    // Converte il timestamp della candela.
    const candleTime = convertToUtcTimestamp(
      candle.timestamp
    );

    // Salva la candela nel formato richiesto dal grafico.
    uniqueCandles.set(
      Number(candleTime),
      {
        time: candleTime,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
      }
    );
  }

  // Converte la Map in array.
  const preparedCandles = Array.from(
    uniqueCandles.values()
  );

  // Ordina cronologicamente le candele.
  preparedCandles.sort(
    (firstCandle, secondCandle) =>
      Number(firstCandle.time) -
      Number(secondCandle.time)
  );

  // Restituisce le candele pronte per il grafico.
  return preparedCandles;
}

/**
 * Converte i segnali Live Paper in marker grafici.
 */
function prepareSignalMarkers(
  signals: SignalRecord[]
): SeriesMarker<UTCTimestamp>[] {
  // Crea un marker per ogni segnale.
  const markers: SeriesMarker<UTCTimestamp>[] =
    signals.map((signal) => {
      // Converte il timestamp del segnale.
      const signalTime = convertToUtcTimestamp(
        signal.timestamp
      );

      // Prepara la confidenza da visualizzare.
      const confidenceText =
        signal.prediction_confidence === null
          ? "N/D"
          : `${Math.round(
              signal.prediction_confidence * 100
            )}%`;

      // Restituisce un marker LONG.
      if (signal.signal === "LONG") {
        return {
          time: signalTime,
          position: "belowBar",
          color: "#22c55e",
          shape: "arrowUp",
          text: `LONG ${confidenceText}`,
        };
      }

      // Restituisce un marker SHORT.
      if (signal.signal === "SHORT") {
        return {
          time: signalTime,
          position: "aboveBar",
          color: "#ef4444",
          shape: "arrowDown",
          text: `SHORT ${confidenceText}`,
        };
      }

      // Restituisce un marker NO_TRADE.
      return {
        time: signalTime,
        position: "inBar",
        color: "#94a3b8",
        shape: "circle",
        text: "NO TRADE",
      };
    });

  // Ordina cronologicamente i marker.
  markers.sort(
    (firstMarker, secondMarker) =>
      Number(firstMarker.time) -
      Number(secondMarker.time)
  );

  // Restituisce i marker pronti per il grafico.
  return markers;
}

/**
 * Visualizza il grafico candlestick e i marker dei segnali.
 */
export default function CandlestickChart({
  candles,
  signals,
}: CandlestickChartProps) {
  // Mantiene il riferimento al contenitore HTML.
  const containerRef =
    useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    // Non crea il grafico senza contenitore.
    if (!containerRef.current) {
      return;
    }

    // Non crea il grafico senza candele.
    if (candles.length === 0) {
      return;
    }

    // Prepara le candele.
    const chartData =
      prepareCandlestickData(candles);

    // Recupera il primo e l'ultimo timestamp visibili.
    const firstCandleTime = Number(
      chartData[0].time
    );

    const lastCandleTime = Number(
      chartData[chartData.length - 1].time
    );

    // Mantiene solamente i segnali presenti nell'intervallo del grafico.
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
        // Adatta automaticamente larghezza e altezza.
        autoSize: true,

        // Configura il tema scuro.
        layout: {
          background: {
            type: ColorType.Solid,
            color: "#0f172a",
          },
          textColor: "#94a3b8",
          fontFamily:
            "Inter, ui-sans-serif, system-ui, sans-serif",
        },

        // Configura la griglia.
        grid: {
          vertLines: {
            color: "#1e293b",
          },
          horzLines: {
            color: "#1e293b",
          },
        },

        // Configura la scala dei prezzi.
        rightPriceScale: {
          borderColor: "#334155",
          scaleMargins: {
            top: 0.12,
            bottom: 0.12,
          },
        },

        // Configura la scala temporale intraday.
        timeScale: {
          borderColor: "#334155",
          timeVisible: true,
          secondsVisible: false,
          rightOffset: 4,
          barSpacing: 18,
          minBarSpacing: 4,
        },

        // Configura il cursore a croce.
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

    // Aggiunge la serie candlestick.
    const candlestickSeries = chart.addSeries(
      CandlestickSeries,
      {
        // Colori delle candele rialziste.
        upColor: "#22c55e",
        wickUpColor: "#22c55e",
        borderUpColor: "#22c55e",

        // Colori delle candele ribassiste.
        downColor: "#ef4444",
        wickDownColor: "#ef4444",
        borderDownColor: "#ef4444",

        // Mostra il prezzo corrente.
        priceLineVisible: true,
        lastValueVisible: true,

        // Configura la precisione di EURUSD.
        priceFormat: {
          type: "price",
          precision: 5,
          minMove: 0.00001,
        },
      }
    );

    // Carica i dati sul grafico.
    candlestickSeries.setData(chartData);

    // Aggiunge i marker solo quando esistono segnali visibili.
    if (visibleSignals.length > 0) {
      const signalMarkers =
        prepareSignalMarkers(
          visibleSignals
        );

      createSeriesMarkers(
        candlestickSeries,
        signalMarkers
      );
    }

    // Adatta la visualizzazione ai dati disponibili.
    chart.timeScale().fitContent();

    // Distrugge il grafico durante lo smontaggio del componente.
    return () => {
      chart.remove();
    };
  }, [candles, signals]);

  // Restituisce il contenitore del grafico.
  return (
    <div
      ref={containerRef}
      className="h-[600px] w-full overflow-hidden rounded-lg bg-slate-900"
    />
  );
}