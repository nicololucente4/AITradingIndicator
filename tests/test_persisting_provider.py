"""Test automatici del provider Live Paper con persistenza."""

# Importa Path per creare database temporanei.
from pathlib import Path

# Importa pandas per costruire candele e timestamp.
import pandas as pd

# Importa pytest per verificare gli errori attesi.
import pytest

# Importa interfaccia e risultato del provider.
from src.data.live_provider import (
    LiveDataProvider,
    PollResult,
)

# Importa l'archivio SQLite.
from src.data.market_data_store import (
    SQLiteMarketDataStore,
)

# Importa il decorator persistente.
from src.data.persisting_provider import (
    PersistingLiveDataProvider,
    PersistingProviderError,
)


def create_candles(
    row_count: int = 3,
) -> pd.DataFrame:
    """Crea un dataset M15 deterministico."""

    # Genera timestamp consecutivi.
    timestamps = pd.date_range(
        start="2026-08-20 10:00:00",
        periods=row_count,
        freq="15min",
        tz="UTC",
    )

    # Genera prezzi progressivi.
    open_prices = [1.1000 + index * 0.0010 for index in range(row_count)]

    # Costruisce il DataFrame OHLCV.
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_prices,
            "high": [price + 0.0020 for price in open_prices],
            "low": [price - 0.0010 for price in open_prices],
            "close": [price + 0.0010 for price in open_prices],
            "volume": [100 + index for index in range(row_count)],
        }
    )


class FakeLiveDataProvider(LiveDataProvider):
    """Simula un provider che emette candele una sola volta."""

    def __init__(
        self,
        dataframe: pd.DataFrame,
    ) -> None:
        """Inizializza il provider simulato."""

        # Salva una copia delle candele.
        self._dataframe = dataframe.copy(deep=True)

        # Indica se le candele sono già state emesse.
        self._already_emitted = False

        # Conta i reset.
        self.reset_calls = 0

        # Conta le connessioni.
        self.connect_calls = 0

        # Conta le disconnessioni.
        self.disconnect_calls = 0

    def poll(
        self,
        current_time_utc: pd.Timestamp,
    ) -> PollResult:
        """Restituisce le candele solo al primo polling."""

        # Normalizza il timestamp.
        selected_time = pd.Timestamp(current_time_utc)

        # Il primo polling restituisce tutte le candele.
        if not self._already_emitted:
            selected_dataframe = self._dataframe.copy(deep=True)

            self._already_emitted = True

        # I polling successivi restituiscono uno schema vuoto.
        else:
            selected_dataframe = self._dataframe.iloc[0:0].copy(deep=True)

        # Recupera l'ultimo timestamp quando disponibile.
        last_timestamp = None

        if not selected_dataframe.empty:
            last_timestamp = selected_dataframe.iloc[-1]["timestamp"]

        # Restituisce il risultato simulato.
        return PollResult(
            new_closed_bars=(selected_dataframe),
            total_source_bars=len(self._dataframe),
            last_emitted_timestamp=(last_timestamp),
            polled_at_utc=selected_time,
            provider_name="FAKE_M15",
        )

    def reset(self) -> None:
        """Azzera lo stato del provider."""

        self._already_emitted = False
        self.reset_calls += 1

    def connect(self) -> None:
        """Simula l'apertura del provider."""

        self.connect_calls += 1

    def disconnect(self) -> None:
        """Simula la chiusura del provider."""

        self.disconnect_calls += 1


def create_persisting_provider(
    tmp_path: Path,
) -> tuple[
    PersistingLiveDataProvider,
    FakeLiveDataProvider,
    SQLiteMarketDataStore,
]:
    """Crea provider, mock e storage temporaneo."""

    # Crea il provider simulato.
    fake_provider = FakeLiveDataProvider(create_candles())

    # Crea lo storage SQLite.
    store = SQLiteMarketDataStore(tmp_path / "market_data.db")

    # Crea il decorator persistente.
    provider = PersistingLiveDataProvider(
        provider=fake_provider,
        store=store,
        symbol="EURUSD",
        timeframe="M15",
    )

    return (
        provider,
        fake_provider,
        store,
    )


def test_provider_implements_live_interface(
    tmp_path: Path,
) -> None:
    """Verifica la compatibilità con LiveDataProvider."""

    # Crea il provider.
    provider, _, _ = create_persisting_provider(tmp_path)

    # Deve implementare l'interfaccia centrale.
    assert isinstance(
        provider,
        LiveDataProvider,
    )


def test_new_candles_are_persisted(
    tmp_path: Path,
) -> None:
    """Verifica il salvataggio delle nuove candele."""

    # Crea i componenti.
    provider, _, store = create_persisting_provider(tmp_path)

    # Esegue il primo polling.
    result = provider.poll(
        pd.Timestamp(
            "2026-08-20 11:00:00",
            tz="UTC",
        )
    )

    # Il risultato originale contiene tre candele.
    assert len(result.new_closed_bars) == 3

    # Lo storage deve contenere le stesse candele.
    assert (
        store.count_candles(
            symbol="EURUSD",
            timeframe="M15",
        )
        == 3
    )

    # Il report deve indicare tre inserimenti.
    assert provider.last_insert_report is not None

    assert provider.last_insert_report.inserted_rows == 3


def test_poll_result_is_not_modified(
    tmp_path: Path,
) -> None:
    """Verifica che il risultato originale rimanga invariato."""

    # Crea il provider.
    provider, _, _ = create_persisting_provider(tmp_path)

    # Esegue il polling.
    result = provider.poll(
        pd.Timestamp(
            "2026-08-20 11:00:00",
            tz="UTC",
        )
    )

    # Verifica i metadati originali.
    assert result.provider_name == "FAKE_M15"

    assert result.total_source_bars == 3

    assert str(result.new_closed_bars["timestamp"].dt.tz) == "UTC"


def test_empty_poll_is_not_persisted(
    tmp_path: Path,
) -> None:
    """Verifica che un polling vuoto non richiami lo storage."""

    # Crea il provider.
    provider, _, store = create_persisting_provider(tmp_path)

    # Il primo polling inserisce i dati.
    provider.poll(
        pd.Timestamp(
            "2026-08-20 11:00:00",
            tz="UTC",
        )
    )

    # Il secondo polling è vuoto.
    result = provider.poll(
        pd.Timestamp(
            "2026-08-20 11:05:00",
            tz="UTC",
        )
    )

    # Il risultato deve essere vuoto.
    assert result.new_closed_bars.empty

    # Il numero di candele deve restare invariato.
    assert (
        store.count_candles(
            symbol="EURUSD",
            timeframe="M15",
        )
        == 3
    )

    # Non deve esserci un report di inserimento per il ciclo vuoto.
    assert provider.last_insert_report is None


def test_reset_is_delegated(
    tmp_path: Path,
) -> None:
    """Verifica la delega del reset."""

    # Crea provider e mock.
    provider, fake_provider, _ = create_persisting_provider(tmp_path)

    # Esegue il polling iniziale.
    provider.poll(
        pd.Timestamp(
            "2026-08-20 11:00:00",
            tz="UTC",
        )
    )

    # Azzera il provider.
    provider.reset()

    # Verifica la delega.
    assert fake_provider.reset_calls == 1

    # Il report locale deve essere azzerato.
    assert provider.last_insert_report is None


def test_replayed_candles_are_ignored_by_store(
    tmp_path: Path,
) -> None:
    """Verifica che lo storage ignori le candele riprodotte."""

    # Crea il provider.
    provider, _, store = create_persisting_provider(tmp_path)

    # Primo inserimento.
    provider.poll(
        pd.Timestamp(
            "2026-08-20 11:00:00",
            tz="UTC",
        )
    )

    # Azzera la sorgente.
    provider.reset()

    # Riproduce le stesse candele.
    provider.poll(
        pd.Timestamp(
            "2026-08-20 11:05:00",
            tz="UTC",
        )
    )

    # Lo storage conserva solo tre candele.
    assert (
        store.count_candles(
            symbol="EURUSD",
            timeframe="M15",
        )
        == 3
    )

    # Il secondo inserimento deve rilevare tre duplicati.
    assert provider.last_insert_report is not None

    assert provider.last_insert_report.inserted_rows == 0

    assert provider.last_insert_report.duplicate_rows == 3


def test_context_manager_delegates_connection(
    tmp_path: Path,
) -> None:
    """Verifica apertura e chiusura del provider sottostante."""

    # Crea provider e mock.
    provider, fake_provider, _ = create_persisting_provider(tmp_path)

    # Utilizza il context manager.
    with provider as active_provider:
        assert active_provider is provider

    # Verifica apertura e chiusura.
    assert fake_provider.connect_calls == 1
    assert fake_provider.disconnect_calls == 1


def test_invalid_timeframe_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il rifiuto di timeframe sconosciuti."""

    # Crea provider e store.
    fake_provider = FakeLiveDataProvider(create_candles())

    store = SQLiteMarketDataStore(tmp_path / "market_data.db")

    # Tenta di usare M7.
    with pytest.raises(
        PersistingProviderError,
        match="non supportato",
    ):
        PersistingLiveDataProvider(
            provider=fake_provider,
            store=store,
            symbol="EURUSD",
            timeframe="M7",
        )


def test_empty_symbol_is_rejected(
    tmp_path: Path,
) -> None:
    """Verifica il rifiuto di un simbolo vuoto."""

    # Crea provider e store.
    fake_provider = FakeLiveDataProvider(create_candles())

    store = SQLiteMarketDataStore(tmp_path / "market_data.db")

    # Tenta di usare un simbolo vuoto.
    with pytest.raises(
        PersistingProviderError,
        match="non può essere vuoto",
    ):
        PersistingLiveDataProvider(
            provider=fake_provider,
            store=store,
            symbol=" ",
            timeframe="M15",
        )
