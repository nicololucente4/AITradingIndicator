"""Provider astratto e provider file per dati live paper in sola lettura."""

# Importa ABC e abstractmethod per definire l'interfaccia comune.
from abc import ABC, abstractmethod

# Importa dataclass per rappresentare il risultato del polling.
from dataclasses import dataclass

# Importa Path per gestire il percorso del file CSV.
from pathlib import Path

# Importa pandas per leggere e filtrare le candele.
import pandas as pd

# Importa il provider CSV già sviluppato.
from src.data.file_provider import FileDataProvider


class LiveDataProviderError(ValueError):
    """Errore generato durante l'acquisizione live paper."""


@dataclass(frozen=True)
class PollResult:
    """Risultato di una singola interrogazione del provider."""

    # Candele chiuse e non ancora emesse.
    new_closed_bars: pd.DataFrame

    # Numero complessivo di candele presenti nella sorgente.
    total_source_bars: int

    # Ultimo timestamp già emesso dal provider.
    last_emitted_timestamp: pd.Timestamp | None

    # Timestamp UTC utilizzato come riferimento del polling.
    polled_at_utc: pd.Timestamp

    # Nome del provider utilizzato.
    provider_name: str


class LiveDataProvider(ABC):
    """Interfaccia comune dei provider dati per il live paper."""

    @abstractmethod
    def poll(
        self,
        current_time_utc: pd.Timestamp,
    ) -> PollResult:
        """Restituisce le nuove candele confermate disponibili."""

    @abstractmethod
    def reset(self) -> None:
        """Azzera lo stato locale del provider."""


class FilePollingDataProvider(LiveDataProvider):
    """Simula un feed live leggendo periodicamente un file CSV."""

    def __init__(
        self,
        file_path: str | Path,
        timeframe_minutes: int,
    ) -> None:
        """Inizializza il provider locale.

        Args:
            file_path: Percorso del file CSV aggiornato nel tempo.
            timeframe_minutes: Durata della candela espressa in minuti.
        """

        # Converte il percorso in un oggetto Path.
        self._file_path = Path(file_path)

        # Verifica la durata del timeframe.
        if timeframe_minutes <= 0:
            raise LiveDataProviderError("Il timeframe deve essere maggiore di zero.")

        # Salva la durata del timeframe.
        self._timeframe_minutes = timeframe_minutes

        # Inizialmente nessuna candela è già stata emessa.
        self._last_emitted_timestamp: pd.Timestamp | None = None

        # Utilizza il provider CSV già validato dal progetto.
        self._file_provider = FileDataProvider()

    @property
    def last_emitted_timestamp(
        self,
    ) -> pd.Timestamp | None:
        """Restituisce l'ultimo timestamp emesso."""

        return self._last_emitted_timestamp

    def _validate_current_time(
        self,
        current_time_utc: pd.Timestamp,
    ) -> pd.Timestamp:
        """Valida e normalizza il timestamp del polling."""

        # Converte il valore ricevuto in Timestamp pandas.
        selected_time = pd.Timestamp(current_time_utc)

        # Il riferimento temporale deve includere una timezone.
        if selected_time.tzinfo is None:
            raise LiveDataProviderError("Il timestamp del polling deve includere una timezone.")

        # Converte esplicitamente il riferimento in UTC.
        return selected_time.tz_convert("UTC")

    def poll(
        self,
        current_time_utc: pd.Timestamp,
    ) -> PollResult:
        """Legge e restituisce solamente le nuove candele chiuse."""

        # Valida e normalizza il momento corrente.
        selected_time = self._validate_current_time(current_time_utc)

        # Carica e valida l'intero CSV.
        dataframe = self._file_provider.load_csv(self._file_path)

        # Calcola l'orario di chiusura di ogni candela.
        candle_close_times = dataframe["timestamp"] + pd.to_timedelta(
            self._timeframe_minutes,
            unit="minutes",
        )

        # Una candela è confermata quando il suo orario di chiusura
        # è minore o uguale al momento del polling.
        closed_mask = candle_close_times <= selected_time

        # Mantiene solamente le candele già chiuse.
        closed_dataframe = dataframe.loc[closed_mask].copy()

        # Se esiste uno stato precedente, elimina le candele già emesse.
        if self._last_emitted_timestamp is not None:
            closed_dataframe = closed_dataframe.loc[
                closed_dataframe["timestamp"] > self._last_emitted_timestamp
            ].copy()

        # Ripristina un indice progressivo.
        closed_dataframe = closed_dataframe.reset_index(drop=True)

        # Aggiorna lo stato solamente se esistono nuove candele.
        if not closed_dataframe.empty:
            self._last_emitted_timestamp = closed_dataframe.iloc[-1]["timestamp"]

        # Restituisce il risultato completo del polling.
        return PollResult(
            new_closed_bars=closed_dataframe,
            total_source_bars=len(dataframe),
            last_emitted_timestamp=self._last_emitted_timestamp,
            polled_at_utc=selected_time,
            provider_name="FILE_POLLING",
        )

    def reset(self) -> None:
        """Azzera il timestamp dell'ultima candela emessa."""

        self._last_emitted_timestamp = None
