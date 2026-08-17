"use client";

// Importa gli hook necessari per creare e distruggere il grafico.
import { useEffect, useRef } from "react";

// Importa la serie candlestick e i tipi di Lightweight Charts.
import {
  CandlestickSeries,
  ColorType,
  createChart,
  type CandlestickData,
  type UTCTimestamp,
} from "lightweight-charts";

// Rappresenta una candela ricevuta dal backend FastAPI.
type Candle = {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
};

// Definisce le proprietà ricevute dal componente.
type CandlestickChartProps = {
  candles: Candle[];
};

/**
 * Converte un timestamp ISO nel formato Unix richiesto da Lightweight Charts.
 *
 * Lightweight Charts richiede:
 * - una BusinessDay per dati giornalieri;
 * - un UTCTimestamp in secondi per dati intraday.
 */
function convertToUtcTimestamp(
  timestamp: string
): UTCTimestamp {
  // Converte il timestamp ricevuto in millisecondi Unix.
  const milliseconds = Date.parse(timestamp);

  // Blocca timestamp non validi prima di passarli al grafico.
  if (Number.isNaN(milliseconds)) {
    throw new Error(
      `Timestamp candela non valido: ${timestamp}`
    );
  }

  // Lightweight Charts utilizza secondi Unix, non millisecondi.
  return Math.floor(
    milliseconds / 1000
  ) as UTCTimestamp;
}

/**
 * Prepara e ordina le candele nel formato corretto.
 */
function prepareCandlestickData(
  candles: Candle[]
): CandlestickData<UTCTimestamp>[] {
  // Converte ogni candela nel formato Lightweight Charts.
  const convertedCandles = candles.map(
    (candle) => ({
      time: convertToUtcTimestamp(
        candle.timestamp
      ),
      open: candle.open,
      high: candle.high,
      low: candle.low,
      close: candle.close,
    })
  );

  // Ordina le candele cronologicamente.
  convertedCandles.sort(
    (firstCandle, secondCandle) =>
      Number(firstCandle.time) -
      Number(secondCandle.time)
  );

  // Rimuove eventuali timestamp duplicati.
  const uniqueCandles = new Map<
    number,
    CandlestickData<UTCTimestamp>
  >();

  for (const candle of convertedCandles) {
    uniqueCandles.set(
      Number(candle.time),
      candle
    );
  }

  // Restituisce una sequenza cronologica e priva di duplicati.
  return Array.from(
    uniqueCandles.values()
  );
}

/**
 * Mostra il grafico candlestick del mercato.
 */
export default function CandlestickChart({
  candles,
}: CandlestickChartProps) {
  // Mantiene il riferimento al contenitore HTML del grafico.
  const containerRef =
    useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    // Non crea il grafico finché il contenitore non è disponibile.
    if (!containerRef.current) {
      return;
    }

    // Non crea una serie vuota se non sono presenti candele.
    if (candles.length === 0) {
      return;
    }

    // Prepara e valida le candele prima della visualizzazione.
    const chartData =
      prepareCandlestickData(candles);

    // Crea il grafico all'interno del contenitore.
    const chart = createChart(
      containerRef.current,
      {
        // Adatta automaticamente il grafico al contenitore.
        autoSize: true,

        // Configura il tema scuro principale.
        layout: {
          background: {
            type: ColorType.Solid,
            color: "#0f172a",
          },
          textColor: "#94a3b8",
          fontFamily:
            "Inter, ui-sans-serif, system-ui, sans-serif",
        },

        // Configura la griglia del grafico.
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
            top: 0.10,
            bottom: 0.10,
          },
        },

        // Configura la scala temporale M15.
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

        // Consente scorrimento e zoom.
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

    // Aggiunge la serie delle candele.
    const candlestickSeries = chart.addSeries(
      CandlestickSeries,
      {
        // Configura le candele rialziste.
        upColor: "#22c55e",
        wickUpColor: "#22c55e",
        borderUpColor: "#22c55e",

        // Configura le candele ribassiste.
        downColor: "#ef4444",
        wickDownColor: "#ef4444",
        borderDownColor: "#ef4444",

        // Visualizza il prezzo corrente.
        priceLineVisible: true,
        lastValueVisible: true,

        // Imposta la precisione per EURUSD.
        priceFormat: {
          type: "price",
          precision: 5,
          minMove: 0.00001,
        },
      }
    );

    // Carica le candele convertite in timestamp Unix.
    candlestickSeries.setData(chartData);

    // Adatta inizialmente il grafico a tutte le candele disponibili.
    chart.timeScale().fitContent();

    // Distrugge il grafico quando il componente viene rimosso
    // o quando cambia il dataset.
    return () => {
      chart.remove();
    };
  }, [candles]);

  // Mostra il contenitore utilizzato da Lightweight Charts.
  return (
    <div
      ref={containerRef}
      className="h-[600px] w-full overflow-hidden rounded-lg bg-slate-900"
    />
  );
}