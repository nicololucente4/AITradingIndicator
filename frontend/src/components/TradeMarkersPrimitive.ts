import type {
  CanvasRenderingTarget2D,
} from "fancy-canvas";

import type {
  IChartApiBase,
  IPrimitivePaneRenderer,
  IPrimitivePaneView,
  ISeriesApi,
  ISeriesPrimitive,
  SeriesAttachedParameter,
  Time,
  UTCTimestamp,
} from "lightweight-charts";

import type {
  AvailableTimeframe,
  PaperTradeRecord,
} from "@/src/types/market";

// Evento operativo rappresentato sul grafico.
export type TradeMarkerEvent =
  | "OPEN"
  | "CLOSE";

// Direzione del paper trade.
export type TradeMarkerDirection =
  | "LONG"
  | "SHORT";

// Informazioni necessarie per disegnare un marker.
export type TradeMarkerItem = {
  tradeId: string;
  alias: string;
  direction: TradeMarkerDirection;
  event: TradeMarkerEvent;
  time: UTCTimestamp;
  price: number;
};

// Coordinate calcolate sul grafico.
type TradeMarkerCoordinates = {
  marker: TradeMarkerItem;
  x: number;
  y: number;
};

// Configurazione grafica del marker.
type TradeMarkerStyle = {
  borderColor: string;
  backgroundColor: string;
  textColor: string;
  triangleColor: string;
};

// Parametri forniti da Lightweight Charts.
type CandlestickAttachedParameter =
  SeriesAttachedParameter<
    Time,
    "Candlestick"
  >;

// Durata dei timeframe in minuti.
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

// Dimensioni del box grafico.
const BOX_HEIGHT = 24;
const BOX_HORIZONTAL_PADDING = 8;
const BOX_TRIANGLE_GAP = 5;
const TRIANGLE_SIZE = 7;
const BORDER_RADIUS = 5;
const FONT =
  "600 11px Inter, ui-sans-serif, system-ui, sans-serif";

/**
 * Converte un timestamp ISO in millisecondi.
 */
function parseTimestamp(
  timestamp: string
): number {
  const timestampMilliseconds =
    Date.parse(
      timestamp
    );

  if (
    Number.isNaN(
      timestampMilliseconds
    )
  ) {
    throw new Error(
      `Timestamp trade non valido: ${timestamp}`
    );
  }

  return timestampMilliseconds;
}

/**
 * Allinea un timestamp al bucket del timeframe.
 */
function alignTimestampToTimeframe(
  timestamp: string,
  timeframe: AvailableTimeframe
): UTCTimestamp {
  const timestampMilliseconds =
    parseTimestamp(
      timestamp
    );

  // La candela settimanale inizia il lunedì UTC.
  if (
    timeframe === "W1"
  ) {
    const selectedDate =
      new Date(
        timestampMilliseconds
      );

    const utcDay =
      selectedDate.getUTCDay();

    const daysFromMonday =
      utcDay === 0
        ? 6
        : utcDay - 1;

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

    return Math.floor(
      selectedDate.getTime() /
        1000
    ) as UTCTimestamp;
  }

  const timeframeMilliseconds =
    TIMEFRAME_MINUTES[
      timeframe
    ] *
    60 *
    1000;

  const alignedMilliseconds =
    Math.floor(
      timestampMilliseconds /
        timeframeMilliseconds
    ) *
    timeframeMilliseconds;

  return Math.floor(
    alignedMilliseconds /
      1000
  ) as UTCTimestamp;
}

/**
 * Crea un alias progressivo leggibile.
 */
function createTradeAlias(
  trade: PaperTradeRecord,
  index: number
): string {
  const prefix =
    trade.direction === "LONG"
      ? "L"
      : "S";

  return `${prefix}-${String(
    index + 1
  ).padStart(
    2,
    "0"
  )}`;
}

/**
 * Converte i paper trade nei marker personalizzati.
 */
export function createTradeMarkerItems(
  trades: PaperTradeRecord[],
  timeframe: AvailableTimeframe
): TradeMarkerItem[] {
  // Ordina i trade dalla prima apertura alla più recente.
  const orderedTrades =
    [...trades].sort(
      (
        firstTrade,
        secondTrade
      ) =>
        parseTimestamp(
          firstTrade.opened_at_utc
        ) -
        parseTimestamp(
          secondTrade.opened_at_utc
        )
    );

  const markers:
    TradeMarkerItem[] =
    [];

  orderedTrades.forEach(
    (
      trade,
      index
    ) => {
      const alias =
        createTradeAlias(
          trade,
          index
        );

      // Aggiunge il marker di apertura.
      markers.push({
        tradeId:
          trade.trade_id,
        alias,
        direction:
          trade.direction,
        event:
          "OPEN",
        time:
          alignTimestampToTimeframe(
            trade.opened_at_utc,
            timeframe
          ),
        price:
          trade.entry_price,
      });

      // Aggiunge il marker di chiusura.
      if (
        trade.status ===
          "CLOSED" &&
        trade.closed_at_utc !==
          null &&
        trade.exit_price !==
          null
      ) {
        markers.push({
          tradeId:
            trade.trade_id,
          alias,
          direction:
            trade.direction,
          event:
            "CLOSE",
          time:
            alignTimestampToTimeframe(
              trade.closed_at_utc,
              timeframe
            ),
          price:
            trade.exit_price,
        });
      }
    }
  );

  return markers;
}

/**
 * Restituisce colori coerenti con la direzione.
 */
function getMarkerStyle(
  marker: TradeMarkerItem
): TradeMarkerStyle {
  if (
    marker.direction ===
    "LONG"
  ) {
    return {
      borderColor:
        "#22c55e",
      backgroundColor:
        "rgba(6, 78, 59, 0.94)",
      textColor:
        "#dcfce7",
      triangleColor:
        "#22c55e",
    };
  }

  return {
    borderColor:
      "#ef4444",
    backgroundColor:
      "rgba(127, 29, 29, 0.94)",
    textColor:
      "#fee2e2",
    triangleColor:
      "#ef4444",
  };
}

/**
 * Crea un percorso rettangolare arrotondato.
 */
function createRoundedRectanglePath(
  context:
    CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number
): void {
  const selectedRadius =
    Math.min(
      radius,
      width / 2,
      height / 2
    );

  context.beginPath();

  context.moveTo(
    x + selectedRadius,
    y
  );

  context.lineTo(
    x + width -
      selectedRadius,
    y
  );

  context.quadraticCurveTo(
    x + width,
    y,
    x + width,
    y + selectedRadius
  );

  context.lineTo(
    x + width,
    y + height -
      selectedRadius
  );

  context.quadraticCurveTo(
    x + width,
    y + height,
    x + width -
      selectedRadius,
    y + height
  );

  context.lineTo(
    x + selectedRadius,
    y + height
  );

  context.quadraticCurveTo(
    x,
    y + height,
    x,
    y + height -
      selectedRadius
  );

  context.lineTo(
    x,
    y + selectedRadius
  );

  context.quadraticCurveTo(
    x,
    y,
    x + selectedRadius,
    y
  );

  context.closePath();
}

/**
 * Disegna un triangolo con punta sul prezzo.
 */
function drawTriangle(
  context:
    CanvasRenderingContext2D,
  x: number,
  y: number,
  marker: TradeMarkerItem,
  color: string
): void {
  context.beginPath();

  // LONG OPEN e SHORT CLOSE vengono mostrati sotto il prezzo.
  const triangleBelowPrice =
    (
      marker.direction ===
        "LONG" &&
      marker.event ===
        "OPEN"
    ) ||
    (
      marker.direction ===
        "SHORT" &&
      marker.event ===
        "CLOSE"
    );

  if (
    triangleBelowPrice
  ) {
    // La punta superiore indica esattamente il prezzo.
    context.moveTo(
      x,
      y
    );

    context.lineTo(
      x - TRIANGLE_SIZE,
      y + TRIANGLE_SIZE * 1.5
    );

    context.lineTo(
      x + TRIANGLE_SIZE,
      y + TRIANGLE_SIZE * 1.5
    );
  } else {
    // La punta inferiore indica esattamente il prezzo.
    context.moveTo(
      x,
      y
    );

    context.lineTo(
      x - TRIANGLE_SIZE,
      y - TRIANGLE_SIZE * 1.5
    );

    context.lineTo(
      x + TRIANGLE_SIZE,
      y - TRIANGLE_SIZE * 1.5
    );
  }

  context.closePath();

  context.fillStyle =
    color;

  context.fill();
}

/**
 * Renderer Canvas dei marker dei trade.
 */
class TradeMarkersRenderer
  implements IPrimitivePaneRenderer
{
  public constructor(
    private readonly coordinates:
      TradeMarkerCoordinates[]
  ) {}

  public draw(
    target:
      CanvasRenderingTarget2D
  ): void {
    target.useBitmapCoordinateSpace(
      (
        renderingScope
      ) => {
        const context =
          renderingScope.context;

        const horizontalPixelRatio =
          renderingScope
            .horizontalPixelRatio;

        const verticalPixelRatio =
          renderingScope
            .verticalPixelRatio;

        context.save();

        context.font =
          FONT;

        context.textBaseline =
          "middle";

        for (
          const {
            marker,
            x,
            y,
          } of this.coordinates
        ) {
          const style =
            getMarkerStyle(
              marker
            );

          const scaledX =
            x *
            horizontalPixelRatio;

          const scaledY =
            y *
            verticalPixelRatio;

          const label =
            `${marker.alias} ${marker.event}`;

          context.font =
            FONT.replace(
              "11px",
              `${11 * verticalPixelRatio}px`
            );

          const textWidth =
            context.measureText(
              label
            ).width;

          const boxWidth =
            textWidth +
            BOX_HORIZONTAL_PADDING *
              2 *
              horizontalPixelRatio;

          const boxHeight =
            BOX_HEIGHT *
            verticalPixelRatio;

          const triangleBelowPrice =
            (
              marker.direction ===
                "LONG" &&
              marker.event ===
                "OPEN"
            ) ||
            (
              marker.direction ===
                "SHORT" &&
              marker.event ===
                "CLOSE"
            );

          const boxX =
            scaledX -
            boxWidth / 2;

          const boxY =
            triangleBelowPrice
              ? scaledY +
                (
                  TRIANGLE_SIZE *
                    1.5 +
                  BOX_TRIANGLE_GAP
                ) *
                  verticalPixelRatio
              : scaledY -
                (
                  TRIANGLE_SIZE *
                    1.5 +
                  BOX_TRIANGLE_GAP
                ) *
                  verticalPixelRatio -
                boxHeight;

          drawTriangle(
            context,
            scaledX,
            scaledY,
            marker,
            style.triangleColor
          );

          createRoundedRectanglePath(
            context,
            boxX,
            boxY,
            boxWidth,
            boxHeight,
            BORDER_RADIUS *
              verticalPixelRatio
          );

          context.fillStyle =
            style.backgroundColor;

          context.fill();

          context.strokeStyle =
            style.borderColor;

          context.lineWidth =
            Math.max(
              1,
              verticalPixelRatio
            );

          context.stroke();

          context.fillStyle =
            style.textColor;

          context.textAlign =
            "center";

          context.fillText(
            label,
            scaledX,
            boxY +
              boxHeight / 2
          );
        }

        context.restore();
      }
    );
  }
}

/**
 * Vista del pannello principale del grafico.
 */
class TradeMarkersPaneView
  implements IPrimitivePaneView
{
  private coordinates:
    TradeMarkerCoordinates[] =
    [];

  public constructor(
    private readonly primitive:
      TradeMarkersPrimitive
  ) {}

  /**
   * Aggiorna le coordinate dopo zoom o spostamento.
   */
  public update(): void {
    this.coordinates =
      this.primitive
        .calculateCoordinates();
  }

  public zOrder():
    "top" {
    return "top";
  }

  public renderer():
    IPrimitivePaneRenderer {
    return new TradeMarkersRenderer(
      this.coordinates
    );
  }
}

/**
 * Primitive personalizzata dei marker operativi.
 */
export class TradeMarkersPrimitive
  implements ISeriesPrimitive<Time>
{
  private chart:
    IChartApiBase<Time> | null =
    null;

  private series:
    ISeriesApi<
      "Candlestick",
      Time
    > | null =
    null;

  private requestUpdate:
    (() => void) | null =
    null;

  private markers:
    TradeMarkerItem[];

  private readonly paneView:
    TradeMarkersPaneView;

  public constructor(
    markers:
      TradeMarkerItem[]
  ) {
    this.markers =
      markers;

    this.paneView =
      new TradeMarkersPaneView(
        this
      );
  }

  /**
   * Collega la primitive al grafico.
   */
  public attached(
    parameters:
      CandlestickAttachedParameter
  ): void {
    this.chart =
      parameters.chart;

    this.series =
      parameters.series;

    this.requestUpdate =
      parameters.requestUpdate;

    this.updateAllViews();
  }

  /**
   * Rimuove i riferimenti al grafico.
   */
  public detached(): void {
    this.chart =
      null;

    this.series =
      null;

    this.requestUpdate =
      null;
  }

  /**
   * Aggiorna i marker senza ricreare la primitive.
   */
  public setMarkers(
    markers:
      TradeMarkerItem[]
  ): void {
    this.markers =
      markers;

    this.updateAllViews();

    this.requestUpdate?.();
  }

  /**
   * Restituisce la vista Canvas principale.
   */
  public paneViews():
    readonly IPrimitivePaneView[] {
    return [
      this.paneView,
    ];
  }

  /**
   * Ricalcola le coordinate dopo zoom e pan.
   */
  public updateAllViews(): void {
    this.paneView.update();
  }

  /**
   * Converte tempo e prezzo in coordinate grafiche.
   */
  public calculateCoordinates():
    TradeMarkerCoordinates[] {
    if (
      this.chart === null ||
      this.series === null
    ) {
      return [];
    }

    const coordinates:
      TradeMarkerCoordinates[] =
      [];

    for (
      const marker of
      this.markers
    ) {
      const x =
        this.chart
          .timeScale()
          .timeToCoordinate(
            marker.time
          );

      const y =
        this.series
          .priceToCoordinate(
            marker.price
          );

      if (
        x === null ||
        y === null
      ) {
        continue;
      }

      coordinates.push({
        marker,
        x:
          Number(x),
        y:
          Number(y),
      });
    }

    return coordinates;
  }
}