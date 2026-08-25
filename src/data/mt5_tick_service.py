"""Servizio read-only per il prezzo tick live MetaTrader 5."""

# Importa dataclass per rappresentare un tick immutabile.
from dataclasses import dataclass

# Importa Protocol per descrivere il modulo MT5 richiesto.
from typing import Protocol

# Importa pandas per normalizzare il timestamp UTC.
import pandas as pd

# Importa la configurazione applicativa.
from src.config.settings import ApplicationSettings


class MetaTrader5TickModule(Protocol):
    """Interfaccia minima richiesta al modulo MetaTrader 5."""

    def initialize(
        self,
        *args: object,
        **kwargs: object,
    ) -> bool:
        """Inizializza MetaTrader 5."""

    def shutdown(
        self,
    ) -> None:
        """Chiude MetaTrader 5."""

    def last_error(
        self,
    ) -> object:
        """Restituisce l'ultimo errore MT5."""

    def terminal_info(
        self,
    ) -> object:
        """Restituisce le informazioni del terminale."""

    def account_info(
        self,
    ) -> object:
        """Restituisce le informazioni dell'account."""

    def symbol_info(
        self,
        symbol: str,
    ) -> object:
        """Restituisce le informazioni del simbolo."""

    def symbol_select(
        self,
        symbol: str,
        enable: bool,
    ) -> bool:
        """Abilita il simbolo nel Market Watch."""

    def symbol_info_tick(
        self,
        symbol: str,
    ) -> object:
        """Restituisce l'ultimo tick del simbolo."""


class MetaTrader5TickServiceError(RuntimeError):
    """Errore generato dal servizio tick MT5."""


@dataclass(frozen=True)
class LiveMarketTick:
    """Rappresenta un prezzo live ricevuto da MT5."""

    # Simbolo interrogato.
    symbol: str

    # Miglior prezzo di vendita disponibile.
    bid: float

    # Miglior prezzo di acquisto disponibile.
    ask: float

    # Prezzo medio tra bid e ask.
    mid: float

    # Differenza tra ask e bid.
    spread: float

    # Timestamp UTC del tick.
    timestamp: pd.Timestamp

    # Origine del dato.
    source: str = "MT5_LIVE_TICK"

    def to_dict(
        self,
    ) -> dict[str, object]:
        """Converte il tick in un record JSON."""

        return {
            "symbol": self.symbol,
            "bid": self.bid,
            "ask": self.ask,
            "mid": self.mid,
            "spread": self.spread,
            "timestamp": (self.timestamp.isoformat()),
            "source": self.source,
        }


def normalize_tick_symbol(
    symbol: str,
) -> str:
    """Normalizza e valida un simbolo."""

    # Il simbolo deve essere una stringa.
    if not isinstance(
        symbol,
        str,
    ):
        raise MetaTrader5TickServiceError("symbol deve essere una stringa.")

    # Elimina gli spazi e converte in maiuscolo.
    selected_symbol = symbol.strip().upper()

    # Rifiuta un simbolo vuoto.
    if not selected_symbol:
        raise MetaTrader5TickServiceError("symbol non può essere vuoto.")

    return selected_symbol


class MetaTrader5TickService:
    """Mantiene una connessione read-only per leggere tick live."""

    def __init__(
        self,
        *,
        settings: ApplicationSettings,
        mt5_module: MetaTrader5TickModule,
    ) -> None:
        """Inizializza il servizio tick."""

        # Il servizio richiede il provider MT5.
        if settings.data_provider != "MT5":
            raise MetaTrader5TickServiceError("Il servizio tick richiede DATA_PROVIDER=MT5.")

        # Il paper trading deve rimanere obbligatorio.
        if not settings.paper_trading_only:
            raise MetaTrader5TickServiceError("PAPER_TRADING_ONLY deve essere true.")

        # Gli ordini reali devono rimanere disabilitati.
        if settings.real_orders_enabled:
            raise MetaTrader5TickServiceError("REAL_ORDERS_ENABLED deve essere false.")

        # Verifica la configurazione MT5 obbligatoria.
        if (
            settings.mt5_login is None
            or settings.mt5_password is None
            or settings.mt5_server is None
        ):
            raise MetaTrader5TickServiceError("La configurazione MT5 è incompleta.")

        # Salva la configurazione validata.
        self._settings = settings

        # Salva il modulo MT5 reale oppure simulato.
        self._mt5 = mt5_module

        # Il collegamento inizialmente è chiuso.
        self._connected = False

    @property
    def connected(
        self,
    ) -> bool:
        """Indica se MT5 è collegato."""

        return self._connected

    def _last_error_text(
        self,
    ) -> str:
        """Restituisce l'ultimo errore MT5."""

        try:
            # Converte l'errore in testo.
            return str(self._mt5.last_error())

        except Exception:
            # Mantiene un messaggio sicuro.
            return "errore MT5 non disponibile"

    def connect(
        self,
    ) -> None:
        """Apre la connessione read-only a MT5."""

        # Evita inizializzazioni duplicate.
        if self._connected:
            return

        # Prepara gli argomenti di inizializzazione.
        initialize_arguments: dict[
            str,
            object,
        ] = {
            "login": (self._settings.mt5_login),
            "password": (self._settings.mt5_password),
            "server": (self._settings.mt5_server),
            "timeout": (self._settings.mt5_timeout_milliseconds),
        }

        # Aggiunge il percorso del terminale se configurato.
        if self._settings.mt5_terminal_path is not None:
            initialize_arguments["path"] = str(self._settings.mt5_terminal_path)

        try:
            # Inizializza MetaTrader 5.
            initialized = self._mt5.initialize(**initialize_arguments)

        except Exception as error:
            raise MetaTrader5TickServiceError("Errore durante l'inizializzazione MT5.") from error

        # Verifica l'esito dell'inizializzazione.
        if not initialized:
            raise MetaTrader5TickServiceError(
                f"Inizializzazione MT5 fallita: {self._last_error_text()}."
            )

        # Verifica il terminale.
        if self._mt5.terminal_info() is None:
            self._mt5.shutdown()

            raise MetaTrader5TickServiceError("Informazioni terminale MT5 non disponibili.")

        # Verifica l'account.
        if self._mt5.account_info() is None:
            self._mt5.shutdown()

            raise MetaTrader5TickServiceError("Informazioni account MT5 non disponibili.")

        # Registra la connessione riuscita.
        self._connected = True

    def disconnect(
        self,
    ) -> None:
        """Chiude la connessione MT5."""

        # Evita chiusure duplicate.
        if not self._connected:
            return

        # Chiude il collegamento.
        self._mt5.shutdown()

        # Aggiorna lo stato.
        self._connected = False

    def get_tick(
        self,
        symbol: str,
    ) -> LiveMarketTick:
        """Restituisce l'ultimo tick live del simbolo."""

        # Normalizza il simbolo richiesto.
        selected_symbol = normalize_tick_symbol(symbol)

        # Collega MT5 quando necessario.
        if not self._connected:
            self.connect()

        # Verifica la presenza del simbolo.
        if self._mt5.symbol_info(selected_symbol) is None:
            raise MetaTrader5TickServiceError(f"Simbolo MT5 non disponibile: {selected_symbol}.")

        # Abilita il simbolo nel Market Watch.
        if not self._mt5.symbol_select(
            selected_symbol,
            True,
        ):
            raise MetaTrader5TickServiceError(
                f"Impossibile abilitare il simbolo {selected_symbol}: {self._last_error_text()}."
            )

        try:
            # Recupera l'ultimo tick disponibile.
            tick = self._mt5.symbol_info_tick(selected_symbol)

        except Exception as error:
            # Chiude una connessione potenzialmente non valida.
            self.disconnect()

            raise MetaTrader5TickServiceError("Errore durante la lettura del tick MT5.") from error

        # None indica un errore dell'API MT5.
        if tick is None:
            error_text = self._last_error_text()

            self.disconnect()

            raise MetaTrader5TickServiceError(f"MT5 non ha restituito il tick: {error_text}.")

        try:
            # Legge direttamente il prezzo bid.
            bid = float(tick.bid)

            # Legge direttamente il prezzo ask.
            ask = float(tick.ask)

            # Preferisce il timestamp in millisecondi.
            time_milliseconds = getattr(
                tick,
                "time_msc",
                None,
            )

            if time_milliseconds is not None:
                timestamp = pd.to_datetime(
                    int(time_milliseconds),
                    unit="ms",
                    utc=True,
                )
            else:
                # Usa il timestamp in secondi come fallback.
                timestamp = pd.to_datetime(
                    int(tick.time),
                    unit="s",
                    utc=True,
                )

        except (
            AttributeError,
            TypeError,
            ValueError,
        ) as error:
            raise MetaTrader5TickServiceError("Il tick MT5 contiene valori non validi.") from error

        # Bid e ask devono essere positivi.
        if bid <= 0 or ask <= 0:
            raise MetaTrader5TickServiceError("Bid e ask devono essere maggiori di zero.")

        # L'ask non può essere inferiore al bid.
        if ask < bid:
            raise MetaTrader5TickServiceError("Il prezzo ask non può essere inferiore al bid.")

        # Calcola lo spread.
        spread = ask - bid

        # Calcola il prezzo medio.
        mid = (bid + ask) / 2

        # Restituisce il tick normalizzato.
        return LiveMarketTick(
            symbol=selected_symbol,
            bid=bid,
            ask=ask,
            mid=mid,
            spread=spread,
            timestamp=timestamp,
        )

    def __enter__(
        self,
    ) -> "MetaTrader5TickService":
        """Apre il servizio come context manager."""

        self.connect()

        return self

    def __exit__(
        self,
        exception_type: object,
        exception_value: object,
        traceback: object,
    ) -> None:
        """Chiude il servizio come context manager."""

        # I parametri non sono necessari.
        del exception_type
        del exception_value
        del traceback

        # Chiude la connessione.
        self.disconnect()
