import type {
  PaperTradeRecord,
} from "@/src/types/market";

/**
 * Rappresenta un trade associato
 * al relativo alias grafico.
 */
export type PaperTradeWithAlias = {
  trade: PaperTradeRecord;
  alias: string;
};

/**
 * Converte una data in un valore numerico sicuro.
 */
function getTimestampValue(
  timestamp: string
): number {
  // Converte il timestamp in millisecondi.
  const timestampValue =
    Date.parse(
      timestamp
    );

  // I timestamp non validi vengono ordinati per ultimi.
  if (
    Number.isNaN(
      timestampValue
    )
  ) {
    return Number.MAX_SAFE_INTEGER;
  }

  return timestampValue;
}

/**
 * Ordina i trade in modo stabile.
 *
 * L'ordinamento utilizza:
 * 1. timestamp di apertura;
 * 2. identificativo completo del trade.
 *
 * Il secondo criterio garantisce risultati
 * deterministici anche con aperture simultanee.
 */
export function orderPaperTrades(
  trades: PaperTradeRecord[]
): PaperTradeRecord[] {
  return [...trades].sort(
    (
      firstTrade,
      secondTrade
    ) => {
      // Confronta prima il momento di apertura.
      const timestampDifference =
        getTimestampValue(
          firstTrade.opened_at_utc
        ) -
        getTimestampValue(
          secondTrade.opened_at_utc
        );

      if (
        timestampDifference !==
        0
      ) {
        return timestampDifference;
      }

      // Usa il Trade ID come secondo criterio stabile.
      return firstTrade.trade_id.localeCompare(
        secondTrade.trade_id
      );
    }
  );
}

/**
 * Crea l'alias leggibile di un trade.
 *
 * Esempi:
 * L-01
 * S-02
 * S-54
 */
export function createTradeAlias(
  trade: PaperTradeRecord,
  chronologicalIndex: number
): string {
  // LONG utilizza il prefisso L.
  const directionPrefix =
    trade.direction ===
    "LONG"
      ? "L"
      : "S";

  // La numerazione parte da uno.
  const progressiveNumber =
    chronologicalIndex + 1;

  // Mantiene almeno due cifre,
  // senza limitare numerazioni superiori a 99.
  const formattedNumber =
    String(
      progressiveNumber
    ).padStart(
      2,
      "0"
    );

  return `${directionPrefix}-${formattedNumber}`;
}

/**
 * Associa ogni trade al proprio alias stabile.
 *
 * La funzione deve ricevere l'elenco completo
 * delle operazioni della combinazione
 * simbolo e timeframe visualizzata.
 *
 * L'alias non deve essere calcolato dopo
 * aver filtrato una singola posizione,
 * altrimenti la numerazione cambierebbe.
 */
export function createTradeAliasMap(
  trades: PaperTradeRecord[]
): Map<string, string> {
  // Ordina prima l'elenco completo.
  const orderedTrades =
    orderPaperTrades(
      trades
    );

  // Prepara la mappa Trade ID -> alias.
  const aliasByTradeId =
    new Map<
      string,
      string
    >();

  // Assegna un alias a ogni trade.
  orderedTrades.forEach(
    (
      trade,
      index
    ) => {
      aliasByTradeId.set(
        trade.trade_id,
        createTradeAlias(
          trade,
          index
        )
      );
    }
  );

  return aliasByTradeId;
}

/**
 * Restituisce l'alias di un singolo trade.
 *
 * Se la mappa non contiene il Trade ID,
 * restituisce un alias neutro e leggibile.
 */
export function getTradeAlias(
  trade: PaperTradeRecord,
  aliasByTradeId: Map<
    string,
    string
  >
): string {
  const existingAlias =
    aliasByTradeId.get(
      trade.trade_id
    );

  if (
    existingAlias !==
    undefined
  ) {
    return existingAlias;
  }

  // Fallback difensivo.
  return trade.direction ===
    "LONG"
    ? "L-ND"
    : "S-ND";
}

/**
 * Restituisce i trade ordinati
 * insieme ai rispettivi alias.
 */
export function getPaperTradesWithAliases(
  trades: PaperTradeRecord[]
): PaperTradeWithAlias[] {
  // Ordina l'elenco completo.
  const orderedTrades =
    orderPaperTrades(
      trades
    );

  // Crea una sola mappa condivisa.
  const aliasByTradeId =
    createTradeAliasMap(
      orderedTrades
    );

  // Associa ogni record al proprio alias.
  return orderedTrades.map(
    (trade) => ({
      trade,
      alias:
        getTradeAlias(
          trade,
          aliasByTradeId
        ),
    })
  );
}

/**
 * Recupera un trade tramite alias.
 */
export function findTradeByAlias(
  trades: PaperTradeRecord[],
  selectedAlias: string
): PaperTradeRecord | null {
  // Normalizza l'alias ricevuto.
  const normalizedAlias =
    selectedAlias
      .trim()
      .toUpperCase();

  if (
    normalizedAlias ===
    ""
  ) {
    return null;
  }

  // Crea l'elenco condiviso trade e alias.
  const tradesWithAliases =
    getPaperTradesWithAliases(
      trades
    );

  // Cerca l'alias richiesto.
  const selectedTrade =
    tradesWithAliases.find(
      (
        tradeInformation
      ) =>
        tradeInformation.alias ===
        normalizedAlias
    );

  return (
    selectedTrade?.trade ??
    null
  );
}

/**
 * Recupera un alias tramite Trade ID.
 */
export function findAliasByTradeId(
  trades: PaperTradeRecord[],
  tradeId: string
): string | null {
  // Crea la mappa condivisa.
  const aliasByTradeId =
    createTradeAliasMap(
      trades
    );

  return (
    aliasByTradeId.get(
      tradeId
    ) ??
    null
  );
}