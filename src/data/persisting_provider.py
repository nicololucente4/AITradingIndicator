"""Decorator che archivia le candele restituite da un provider Live Paper."""

# Importa pandas per gestire timestamp e DataFrame.
import pandas as pd

# Importa l'interfaccia comune dei provider.
from src.data.live_provider import (
    LiveDataProvider,
    PollResult,
)

# Importa l'archivio persistente delle candele.
from src.data.market_data_store import (
    MarketDataInsertReport,
    SQLiteMarketDataStore,
)

# Importa il catalogo centralizzato dei timeframe.
from src.data.market_timeframes import (
    MarketTimeframeError,
    get_timeframe_by_code,
)


class PersistingProviderError(ValueError):
    """Errore generato dal provider con persistenza."""


class PersistingLiveDataProvider(LiveDataProvider):
    """Archivia le nuove candele prima di restituirle al motore."""

    def __init__(
        self,
        provider: LiveDataProvider,
        store: SQLiteMarketDataStore,
        *,
        symbol: str,
        timeframe: str,
    ) -> None:
        """Inizializza il decorator persistente."""

        # Il provider deve implementare l'interfaccia centrale.
        if not isinstance(
            provider,
            LiveDataProvider,
        ):
            raise TypeError("provider deve implementare LiveDataProvider.")

        # Lo storage deve essere del tipo previsto.
        if not isinstance(
            store,
            SQLiteMarketDataStore,
        ):
            raise TypeError("store deve essere un'istanza di SQLiteMarketDataStore.")

        # Il simbolo deve essere una stringa.
        if not isinstance(
            symbol,
            str,
        ):
            raise PersistingProviderError("symbol deve essere una stringa.")

        # Normalizza il simbolo.
        selected_symbol = symbol.strip().upper()

        # Il simbolo non può essere vuoto.
        if not selected_symbol:
            raise PersistingProviderError("symbol non può essere vuoto.")

        # Il timeframe deve essere una stringa.
        if not isinstance(
            timeframe,
            str,
        ):
            raise PersistingProviderError("timeframe deve essere una stringa.")

        # Normalizza il timeframe.
        selected_timeframe = timeframe.strip().upper()

        # Verifica il timeframe nel catalogo centrale.
        try:
            get_timeframe_by_code(selected_timeframe)

        except MarketTimeframeError as error:
            raise PersistingProviderError(
                f"Timeframe non supportato: {selected_timeframe or '<VUOTO>'}."
            ) from error

        # Salva il provider originale.
        self._provider = provider

        # Salva l'archivio condiviso.
        self._store = store

        # Salva il simbolo normalizzato.
        self._symbol = selected_symbol

        # Salva il timeframe normalizzato.
        self._timeframe = selected_timeframe

        # Nessun report di persistenza è ancora disponibile.
        self._last_insert_report: MarketDataInsertReport | None = None

    @property
    def wrapped_provider(
        self,
    ) -> LiveDataProvider:
        """Restituisce il provider originale."""

        return self._provider

    @property
    def store(
        self,
    ) -> SQLiteMarketDataStore:
        """Restituisce l'archivio condiviso."""

        return self._store

    @property
    def symbol(self) -> str:
        """Restituisce il simbolo configurato."""

        return self._symbol

    @property
    def timeframe(self) -> str:
        """Restituisce il timeframe configurato."""

        return self._timeframe

    @property
    def last_insert_report(
        self,
    ) -> MarketDataInsertReport | None:
        """Restituisce il report dell'ultimo inserimento."""

        return self._last_insert_report

    def poll(
        self,
        current_time_utc: pd.Timestamp,
    ) -> PollResult:
        """Interroga il provider e archivia le nuove candele."""

        # Interroga il provider originale.
        poll_result = self._provider.poll(current_time_utc=(current_time_utc))

        # Non tenta l'inserimento senza nuove candele.
        if poll_result.new_closed_bars.empty:
            # Azzera il report dell'ultimo inserimento,
            # perché in questo ciclo non è avvenuta persistenza.
            self._last_insert_report = None

            # Restituisce il risultato originale.
            return poll_result

        # Archivia esclusivamente le nuove candele chiuse.
        insert_report = self._store.insert_candles(
            poll_result.new_closed_bars,
            symbol=self._symbol,
            timeframe=self._timeframe,
            provider_name=(poll_result.provider_name),
            received_at_utc=(poll_result.polled_at_utc),
        )

        # Memorizza il report dell'inserimento.
        self._last_insert_report = insert_report

        # Restituisce esattamente il PollResult originale.
        return poll_result

    def reset(self) -> None:
        """Azzera lo stato del provider originale."""

        # Delega il reset al provider sottostante.
        self._provider.reset()

        # Azzera anche il report locale.
        self._last_insert_report = None

    def disconnect(self) -> None:
        """Chiude il provider originale quando supportato."""

        # Recupera dinamicamente il metodo disconnect.
        disconnect_method = getattr(
            self._provider,
            "disconnect",
            None,
        )

        # Esegue la disconnessione solamente se disponibile.
        if callable(disconnect_method):
            disconnect_method()

    def __enter__(
        self,
    ) -> "PersistingLiveDataProvider":
        """Apre il provider sottostante quando supportato."""

        # Recupera dinamicamente il metodo connect.
        connect_method = getattr(
            self._provider,
            "connect",
            None,
        )

        # Apre il collegamento solamente se supportato.
        if callable(connect_method):
            connect_method()

        return self

    def __exit__(
        self,
        exception_type: object,
        exception_value: object,
        traceback: object,
    ) -> None:
        """Chiude il provider sottostante."""

        # I dettagli dell'eventuale eccezione non sono necessari.
        del exception_type
        del exception_value
        del traceback

        # Chiude il provider quando supportato.
        self.disconnect()
