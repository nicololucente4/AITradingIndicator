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

import {
  getPaperTradesWithAliases,
} from "@/src/utils/tradeAlias";

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
  triangleBorderColor: string;
  glowColor: string;
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

// Dimensioni del marker.
const BOX_HEIGHT = 22;
const BOX_HORIZONTAL_PADDING = 7;
const BOX_TRIANGLE_GAP = 4;
const TRIANGLE_SIZE = 6;
const BORDER_RADIUS = 5;

// Configurazione del testo.
const FONT_SIZE = 10;
const FONT_FAMILY =
  "Inter, ui-sans-serif, system-ui, sans-serif";

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
 * Converte i paper trade nei marker personalizzati.
 *
 * Gli alias vengono calcolati sull'elenco completo.
 * Solo dopo viene applicato il filtro opzionale.
 *
 * Questo garantisce che S-54 resti S-54
 * anche quando viene isolato sul grafico.
 */
export function createTradeMarkerItems(
  trades: PaperTradeRecord[],
  timeframe: AvailableTimeframe,
  selectedTradeId: string | null = null
): TradeMarkerItem[] {
  // Genera ordinamento e alias condivisi.
  const tradesWithAliases =
    getPaperTradesWithAliases(
      trades
    );

  // Applica il filtro solo dopo avere calcolato gli alias.
  const visibleTrades =
    selectedTradeId ===
    null
      ? tradesWithAliases
      : tradesWithAliases.filter(
          (
            tradeInformation
          ) =>
            tradeInformation
              .trade
              .trade_id ===
            selectedTradeId
        );

  const markers:
    TradeMarkerItem[] =
    [];

  for (
    const tradeInformation of
    visibleTrades
  ) {
    const {
      trade,
      alias,
    } =
      tradeInformation;

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

  return markers;
}

/**
 * Restituisce colori ad alto contrasto.
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
        "#4ade80",
      backgroundColor:
        "rgba(5, 46, 22, 0.96)",
      textColor:
        "#f0fdf4",
      triangleColor:
        "#22c55e",
      triangleBorderColor:
        "#ffffff",
      glowColor:
        "rgba(0, 0, 0, 0.95)",
    };
  }

  return {
    borderColor:
      "#fb7185",
    backgroundColor:
      "rgba(69, 10, 10, 0.97)",
    textColor:
      "#fff1f2",
    triangleColor:
      "#ff3344",
    triangleBorderColor:
      "#ffffff",
    glowColor:
      "rgba(0, 0, 0, 0.95)",
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
 * Determina se il marker deve essere
 * visualizzato sotto il prezzo.
 */
function isMarkerBelowPrice(
  marker: TradeMarkerItem
): boolean {
  return (
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
    )
  );
}

/**
 * Crea il percorso geometrico del triangolo.
 *
 * La punta centrale coincide esattamente
 * con la coordinata del prezzo.
 */
function createTrianglePath(
  context:
    CanvasRenderingContext2D,
  x: number,
  y: number,
  marker: TradeMarkerItem,
  triangleSize: number
): void {
  const triangleBelowPrice =
    isMarkerBelowPrice(
      marker
    );

  context.beginPath();

  if (
    triangleBelowPrice
  ) {
    // Punta superiore sul prezzo esatto.
    context.moveTo(
      x,
      y
    );

    context.lineTo(
      x - triangleSize,
      y + triangleSize * 1.6
    );

    context.lineTo(
      x + triangleSize,
      y + triangleSize * 1.6
    );
  } else {
    // Punta inferiore sul prezzo esatto.
    context.moveTo(
      x,
      y
    );

    context.lineTo(
      x - triangleSize,
      y - triangleSize * 1.6
    );

    context.lineTo(
      x + triangleSize,
      y - triangleSize * 1.6
    );
  }

  context.closePath();
}

/**
 * Disegna il triangolo con alone scuro
 * e contorno bianco ad alto contrasto.
 */
function drawHighContrastTriangle(
  context:
    CanvasRenderingContext2D,
  x: number,
  y: number,
  marker: TradeMarkerItem,
  style: TradeMarkerStyle,
  horizontalPixelRatio: number,
  verticalPixelRatio: number
): void {
  const selectedPixelRatio =
    Math.max(
      horizontalPixelRatio,
      verticalPixelRatio
    );

  const triangleSize =
    TRIANGLE_SIZE *
    selectedPixelRatio;

  // Disegna prima un alone scuro più largo.
  context.save();

  context.shadowColor =
    style.glowColor;

  context.shadowBlur =
    5 *
    selectedPixelRatio;

  createTrianglePath(
    context,
    x,
    y,
    marker,
    triangleSize
  );

  context.fillStyle =
    style.triangleColor;

  context.fill();

  context.restore();

  // Ridisegna la forma con bordo bianco.
  createTrianglePath(
    context,
    x,
    y,
    marker,
    triangleSize
  );

  context.fillStyle =
    style.triangleColor;

  context.fill();

  context.strokeStyle =
    style.triangleBorderColor;

  context.lineWidth =
    Math.max(
      1.5,
      1.5 *
        selectedPixelRatio
    );

  context.stroke();
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

          const fontSize =
            FONT_SIZE *
            verticalPixelRatio;

          context.font =
            `700 ${fontSize}px ${FONT_FAMILY}`;

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

          const boxX =
            scaledX -
            boxWidth / 2;

          const boxBelowPrice =
            isMarkerBelowPrice(
              marker
            );

          const triangleHeight =
            TRIANGLE_SIZE *
            1.6 *
            verticalPixelRatio;

          const selectedGap =
            BOX_TRIANGLE_GAP *
            verticalPixelRatio;

          const boxY =
            boxBelowPrice
              ? scaledY +
                triangleHeight +
                selectedGap
              : scaledY -
                triangleHeight -
                selectedGap -
                boxHeight;

          // Disegna il triangolo con bordo bianco e alone scuro.
          drawHighContrastTriangle(
            context,
            scaledX,
            scaledY,
            marker,
            style,
            horizontalPixelRatio,
            verticalPixelRatio
          );

          // Crea il percorso del box.
          createRoundedRectanglePath(
            context,
            boxX,
            boxY,
            boxWidth,
            boxHeight,
            BORDER_RADIUS *
              verticalPixelRatio
          );

          // Disegna lo sfondo del box con alone scuro.
          context.save();

          context.shadowColor =
            style.glowColor;

          context.shadowBlur =
            4 *
            verticalPixelRatio;

          context.fillStyle =
            style.backgroundColor;

          context.fill();

          context.restore();

          // Ricrea il percorso per il bordo.
          createRoundedRectanglePath(
            context,
            boxX,
            boxY,
            boxWidth,
            boxHeight,
            BORDER_RADIUS *
              verticalPixelRatio
          );

          // Disegna il bordo coerente con la direzione.
          context.strokeStyle =
            style.borderColor;

          context.lineWidth =
            Math.max(
              1.5,
              1.5 *
                verticalPixelRatio
            );

          context.stroke();

          // Disegna il testo dell'alias.
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
  // Coordinate correnti dei marker.
  private coordinates:
    TradeMarkerCoordinates[] =
    [];

  public constructor(
    private readonly primitive:
      TradeMarkersPrimitive
  ) {}

  /**
   * Aggiorna le coordinate dopo zoom,
   * spostamento o modifica della scala.
   */
  public update(): void {
    this.coordinates =
      this.primitive
        .calculateCoordinates();
  }

  /**
   * Disegna i marker sopra candele e griglia.
   */
  public zOrder():
    "top" {
    return "top";
  }

  /**
   * Restituisce il renderer Canvas.
   */
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
  // Riferimento al grafico.
  private chart:
    IChartApiBase<Time> | null =
    null;

  // Riferimento alla serie candlestick.
  private series:
    ISeriesApi<
      "Candlestick",
      Time
    > | null =
    null;

  // Callback per richiedere il ridisegno.
  private requestUpdate:
    (() => void) | null =
    null;

  // Marker attualmente visualizzati.
  private markers:
    TradeMarkerItem[];

  // Vista Canvas principale.
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
   * Collega la primitive al grafico
   * e alla serie candlestick.
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
   * Rimuove tutti i riferimenti
   * quando la primitive viene scollegata.
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
   * Aggiorna i marker senza
   * ricreare la primitive.
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
   * Ricalcola tutte le coordinate visive.
   */
  public updateAllViews(): void {
    this.paneView.update();
  }

  /**
   * Converte tempo e prezzo
   * nelle coordinate del grafico.
   */
  public calculateCoordinates():
    TradeMarkerCoordinates[] {
    // Il calcolo richiede grafico e serie attivi.
    if (
      this.chart ===
        null ||
      this.series ===
        null
    ) {
      return [];
    }

    const coordinates:
      TradeMarkerCoordinates[] =
      [];

    // Converte ogni marker nelle coordinate X e Y.
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

      // Ignora marker esterni al range disponibile.
      if (
        x ===
          null ||
        y ===
          null
      ) {
        continue;
      }

      coordinates.push({
        marker,
        x:
          Number(
            x
          ),
        y:
          Number(
            y
          ),
      });
    }

    return coordinates;
  }
}