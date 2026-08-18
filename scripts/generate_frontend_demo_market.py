"""Genera uno storico sintetico esteso per il frontend Next.js."""

# Importa math per creare oscillazioni deterministiche.
import math

# Importa Path per gestire il percorso del CSV.
from pathlib import Path

# Importa pandas per costruire il dataset OHLCV.
import pandas as pd

# Importa il validatore centrale del progetto.
from src.data.validator import validate_ohlcv


def create_demo_market_data(
    candle_count: int = 320,
) -> pd.DataFrame:
    """Crea uno storico EURUSD M15 con diversi regimi di mercato."""

    # Genera timestamp consecutivi da quindici minuti.
    timestamps = pd.date_range(
        start="2026-08-10 06:00:00",
        periods=candle_count,
        freq="15min",
        tz="UTC",
    )

    # Inizializza il prezzo di partenza.
    current_price = 1.10000

    # Conterrà i prezzi di chiusura.
    close_prices: list[float] = []

    # Genera regimi rialzisti, ribassisti e laterali.
    for index in range(candle_count):
        # Prima fase moderatamente rialzista.
        if index < 80:
            trend_movement = 0.00008

        # Seconda fase ribassista.
        elif index < 160:
            trend_movement = -0.00010

        # Terza fase laterale.
        elif index < 240:
            trend_movement = 0.00001

        # Quarta fase nuovamente rialzista.
        else:
            trend_movement = 0.00009

        # Aggiunge un'oscillazione periodica deterministica.
        cyclic_movement = math.sin(index / 4.0) * 0.00007

        # Aggiunge una seconda oscillazione più lenta.
        secondary_movement = math.sin(index / 17.0) * 0.00003

        # Aggiorna il prezzo corrente.
        current_price += trend_movement + cyclic_movement + secondary_movement

        # Salva il Close con precisione coerente con EURUSD.
        close_prices.append(round(current_price, 5))

    # Il primo Open precede leggermente il primo Close.
    # Gli Open successivi coincidono con il Close precedente.
    open_prices = [
        round(
            close_prices[0] - 0.00005,
            5,
        ),
        *close_prices[:-1],
    ]

    # Costruisce High validi con volatilità variabile.
    high_prices = [
        round(
            max(open_price, close_price) + 0.00018 + (index % 5) * 0.00002,
            5,
        )
        for index, (
            open_price,
            close_price,
        ) in enumerate(
            zip(
                open_prices,
                close_prices,
                strict=True,
            )
        )
    ]

    # Costruisce Low validi con volatilità variabile.
    low_prices = [
        round(
            min(open_price, close_price) - 0.00018 - (index % 4) * 0.00002,
            5,
        )
        for index, (
            open_price,
            close_price,
        ) in enumerate(
            zip(
                open_prices,
                close_prices,
                strict=True,
            )
        )
    ]

    # Costruisce volumi sintetici deterministici.
    volumes = [
        1000 + (index % 40) * 25 + int(abs(math.sin(index / 6.0)) * 500)
        for index in range(candle_count)
    ]

    # Costruisce il DataFrame OHLCV completo.
    dataframe = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volumes,
        }
    )

    # Valida matematicamente e temporalmente il dataset.
    return validate_ohlcv(dataframe)


def main() -> None:
    """Genera e salva il dataset demo esteso."""

    # Definisce il file letto attualmente da FastAPI.
    output_path = Path("data/sample/EURUSD_M15_sample.csv")

    # Genera lo storico sintetico.
    dataframe = create_demo_market_data(candle_count=320)

    # Crea la cartella di destinazione se necessario.
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Sovrascrive il piccolo CSV precedente.
    dataframe.to_csv(
        output_path,
        index=False,
    )

    # Mostra il riepilogo.
    print("Storico frontend generato correttamente.")
    print("Tipo dati: SYNTHETIC DEMO")
    print(f"Candele: {len(dataframe)}")
    print(f"Prima candela: {dataframe.iloc[0]['timestamp']}")
    print(f"Ultima candela: {dataframe.iloc[-1]['timestamp']}")
    print(f"Prezzo iniziale: {dataframe.iloc[0]['close']:.5f}")
    print(f"Prezzo finale: {dataframe.iloc[-1]['close']:.5f}")
    print(f"File: {output_path.resolve()}")


if __name__ == "__main__":
    # Avvia lo script solamente se eseguito direttamente.
    main()
