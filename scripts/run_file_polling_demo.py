"""Dimostrazione del provider Live Paper basato su file."""

from pathlib import Path

import pandas as pd

from src.data.live_provider import (
    FilePollingDataProvider,
)


def print_poll_result(
    poll_time: pd.Timestamp,
    new_closed_bars: pd.DataFrame,
) -> None:
    """Mostra il risultato di un singolo polling."""

    print(f"Polling UTC: {poll_time}")
    print(f"Nuove candele chiuse: {len(new_closed_bars)}")

    if not new_closed_bars.empty:
        print(
            new_closed_bars[
                [
                    "timestamp",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                ]
            ].to_string(index=False)
        )

    print("")


def main() -> None:
    """Simula più polling sul CSV di esempio."""

    # Definisce il CSV sorgente.
    csv_path = Path("data/sample/EURUSD_M15_sample.csv")

    # Crea il provider read-only.
    provider = FilePollingDataProvider(
        file_path=csv_path,
        timeframe_minutes=15,
    )

    # Simula momenti successivi.
    poll_times = [
        pd.Timestamp(
            "2026-08-13 08:30:00",
            tz="UTC",
        ),
        pd.Timestamp(
            "2026-08-13 08:35:00",
            tz="UTC",
        ),
        pd.Timestamp(
            "2026-08-13 09:00:00",
            tz="UTC",
        ),
        pd.Timestamp(
            "2026-08-13 09:30:00",
            tz="UTC",
        ),
    ]

    # Esegue i polling in sequenza.
    for poll_time in poll_times:
        result = provider.poll(current_time_utc=poll_time)

        print_poll_result(
            poll_time=result.polled_at_utc,
            new_closed_bars=result.new_closed_bars,
        )

    # Mostra lo stato finale.
    print("Polling dimostrativo completato.")
    print("Modalità: PAPER ONLY")
    print("Provider: FILE_POLLING")
    print(f"Ultima candela emessa: {provider.last_emitted_timestamp}")


if __name__ == "__main__":
    main()
