"""Test iniziali dell'ambiente di sviluppo."""

# Importa sys per leggere la versione dell'interprete Python.
import sys


def test_python_version() -> None:
    """Verifica che il progetto utilizzi Python 3.11."""

    # Controlla la versione principale di Python.
    assert sys.version_info.major == 3

    # Controlla la versione secondaria richiesta dal progetto.
    assert sys.version_info.minor == 11


def test_basic_calculation() -> None:
    """Verifica che Pytest riesca a eseguire correttamente un test."""

    # Esegue una semplice operazione deterministica.
    result = 2 + 2

    # Controlla che il risultato sia quello atteso.
    assert result == 4