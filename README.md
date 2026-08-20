# AI Trading Indicator

Piattaforma modulare per analisi quantitativa, generazione di segnali tramite machine learning e monitoraggio in **Live Paper Trading**.

> **PAPER ONLY**  
> Il progetto non invia ordini reali. Il collegamento al provider o a MetaTrader 5 deve essere utilizzato esclusivamente per acquisire dati e simulare segnali, ingressi ed esiti.

## Stato del progetto

La prima versione include:

- validazione dei dati OHLCV;
- aggregazione multi-timeframe;
- feature engineering tecnico;
- generazione di segnali baseline e ML;
- filtri di confidenza;
- livelli teorici Entry, Stop Loss e Take Profit;
- backtest e metriche;
- walk-forward evaluation;
- model registry e controllo hash dei modelli;
- replay temporale senza uso di dati futuri;
- Live Paper Engine;
- Outcome Tracker;
- statistiche Live Paper;
- persistenza SQLite;
- backend FastAPI read-only;
- dashboard tecnica Streamlit;
- frontend Next.js ispirato a un terminale TradingView;
- grafico candlestick, EMA, volumi, marker dei segnali e livelli operativi;
- timeframe M15, H1, H4 e D1;
- test automatici Python e controlli frontend.

## Architettura

```text
Provider CSV / futuro connettore MetaTrader 5
                    |
                    v
         Validazione e normalizzazione OHLCV
                    |
                    v
        Feature engineering e inferenza ML
                    |
                    v
             Live Paper Engine
                    |
          +---------+----------+
          |                    |
          v                    v
    Tabella signals     Outcome Tracker
                               |
                               v
                    Tabella signal_outcomes
          |                    |
          +---------+----------+
                    |
                    v
                  SQLite
                    |
                    v
             FastAPI read-only
                    |
                    v
        Next.js / React Trading Terminal
```

Streamlit rimane una dashboard tecnica temporanea. Il frontend principale è sviluppato in React e Next.js.

## Stack tecnologico

### Backend e data science

- Python 3.11
- pandas
- NumPy
- scikit-learn
- FastAPI
- Uvicorn
- SQLite
- pytest
- Ruff

### Frontend

- Next.js 16
- React
- TypeScript
- Tailwind CSS
- Lightweight Charts
- ESLint

### Persistenza

SQLite contiene due registri separati:

- `signals`: segnali immutabili prodotti dal Live Paper Engine;
- `signal_outcomes`: esiti conclusivi valutati dall'Outcome Tracker.

I database locali non devono essere versionati su Git.

## Struttura principale

```text
AITradingIndicator/
├── data/
│   ├── sample/                 # Dataset dimostrativi versionati
│   └── live_paper/             # Database e stato runtime non versionati
├── frontend/                   # Applicazione Next.js
│   ├── app/
│   └── src/
│       ├── components/
│       ├── services/
│       └── types/
├── reports/                    # Report JSON generati
├── scripts/                    # Demo, generatori e utility operative
├── src/
│   ├── api/                    # Backend FastAPI
│   ├── app/                    # Dashboard Streamlit tecnica
│   ├── data/                   # Provider, validazione e timeframe
│   ├── features/               # Feature engineering
│   ├── models/                 # Training, inferenza e registry
│   ├── monitoring/             # Live Paper, outcome e statistiche
│   └── ...
├── tests/                      # Test automatici Python
├── pyproject.toml
├── requirements-dev.txt
└── README.md
```

## Prerequisiti

### Backend

- Python 3.11
- Git

### Frontend

- Node.js
- npm

Le versioni usate nell'ambiente di sviluppo corrente sono:

```text
Python 3.11.9
Node.js 24.16.0
npm 11.13.0
```

## Installazione locale

### 1. Clonare il repository

```powershell
git clone https://github.com/UTENTE/AITradingIndicator.git
cd AITradingIndicator
```

### 2. Creare l'ambiente Python

Eseguire nella **root del progetto**:

```powershell
python -m venv .venv
```

Attivare l'ambiente in PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

Installare le dipendenze:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

### 3. Installare il frontend

Eseguire nella cartella `frontend`:

```powershell
cd frontend
npm install
cd ..
```

## Verifica dell'installazione

### Backend

Eseguire nella **root del progetto**:

```powershell
python -m ruff check src tests scripts
python -m pytest -v
```

La release corrente deve completare tutti i test senza errori.

### Frontend

Eseguire nella cartella `frontend`:

```powershell
npm run lint
npm run build
```

## Generazione dei dati dimostrativi

Per creare lo storico sintetico M15 usato dal frontend:

```powershell
python -m scripts.generate_frontend_demo_market
```

Per rigenerare il database dimostrativo coordinato:

```powershell
Remove-Item "data\live_paper\coordinated_live_paper.db" -ErrorAction SilentlyContinue
python -m scripts.run_coordinated_live_paper
```

I dati generati sono sintetici e servono esclusivamente allo sviluppo e alla verifica dell'interfaccia.

## Avvio del sistema

Il sistema richiede due terminali. Un terzo terminale è necessario quando viene eseguito separatamente il motore Live Paper.

### Terminale 1: FastAPI

Eseguire nella **root del progetto**:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000 --reload
```

Indirizzi:

```text
API:  http://127.0.0.1:8000
Docs: http://127.0.0.1:8000/docs
```

### Terminale 2: Next.js

Eseguire nella cartella `frontend`:

```powershell
npm run dev
```

Frontend:

```text
http://localhost:3000
```

### Dashboard tecnica Streamlit

Streamlit è mantenuto solo come strumento tecnico interno:

```powershell
python -m streamlit run src/app/dashboard.py --server.address localhost --server.port 8501
```

Indirizzo:

```text
http://localhost:8501
```

## Endpoint FastAPI

```text
GET /
GET /api/v1/health
GET /api/v1/system/status
GET /api/v1/market/timeframes
GET /api/v1/market/candles
GET /api/v1/signals
GET /api/v1/outcomes
GET /api/v1/statistics
```

Esempi multi-timeframe:

```text
/api/v1/market/candles?timeframe=M15&limit=500
/api/v1/market/candles?timeframe=H1&limit=500
/api/v1/market/candles?timeframe=H4&limit=500
/api/v1/market/candles?timeframe=D1&limit=500
```

M1 e M5 richiedono dati nativi dal provider reale e non possono essere ricostruiti correttamente da candele M15.

## Funzionamento Live Paper

1. Il provider restituisce esclusivamente candele chiuse.
2. I dati vengono validati e ordinati temporalmente.
3. Il processore calcola feature e previsione.
4. Il filtro di confidenza conferma LONG, SHORT o NO_TRADE.
5. Il sistema calcola Entry, Stop Loss e Take Profit teorici.
6. Il Live Paper Engine salva il segnale in SQLite senza sovrascrivere record esistenti.
7. L'Outcome Tracker controlla le candele successive.
8. L'esito viene registrato come Take Profit, Stop Loss, scadenza temporale o evento ambiguo conservativo.
9. FastAPI espone candele, segnali, esiti e statistiche.
10. Next.js visualizza il terminale operativo.

## Sicurezza operativa

La release deve mantenere sempre queste condizioni:

```text
paper_trading_only = true
real_orders_enabled = false
```

Non inserire nel repository:

- password;
- credenziali MetaTrader 5;
- token;
- API key;
- file `.env` reali;
- database SQLite runtime;
- log contenenti dati sensibili;
- file di configurazione specifici del broker.

Usare esclusivamente un file `.env.example` privo di valori sensibili come modello di configurazione.

## Collegamento futuro a MetaTrader 5

Il connettore MetaTrader 5 dovrà essere completato e testato inizialmente sul PC di sviluppo usando mock o controlli senza ordini. Sul secondo PC verranno eseguite soltanto:

1. installazione di MetaTrader 5;
2. accesso al profilo di test;
3. configurazione locale delle credenziali;
4. verifica del simbolo e del timeframe;
5. acquisizione read-only delle candele;
6. avvio del Live Paper Engine;
7. test continuativo senza invio di ordini.

Il collegamento deve inizialmente consentire solo:

```text
lettura account
lettura simboli
lettura candele
lettura timestamp
```

L'invio di ordini deve rimanere disabilitato.

## Procedura prevista sul PC di test

Quando la release sarà dichiarata pronta:

```powershell
git clone https://github.com/UTENTE/AITradingIndicator.git
cd AITradingIndicator
git checkout v0.1.0-paper
```

Successivamente verranno eseguiti:

```text
creazione ambiente Python
installazione requirements
installazione npm
creazione configurazione locale
verifica MetaTrader 5
avvio connettore read-only
avvio Live Paper
avvio FastAPI
avvio Next.js
```

## Criteri minimi prima del test sul secondo PC

Il trasferimento può iniziare solo quando sono disponibili:

- repository GitHub privato aggiornato;
- tag di release `v0.1.0-paper`;
- test Python completi;
- lint e build frontend completati;
- `.gitignore` verificato;
- `.env.example` senza credenziali;
- connettore MetaTrader 5 read-only;
- test automatici del connettore con mock;
- script di avvio del motore continuo;
- checklist di installazione e collaudo;
- procedura di arresto e ripristino;
- conferma esplicita che nessun ordine può essere inviato.

## Limiti attuali

- il feed dimostrativo usa dati sintetici;
- M1 e M5 non sono disponibili senza feed nativo;
- i segnali demo non rappresentano performance reali;
- il frontend è ancora in evoluzione;
- il motore continuo e il connettore MetaTrader 5 devono essere completati prima del test sul secondo PC;
- il progetto non è pronto per operatività con denaro reale.

## Roadmap immediata

1. completare il connettore MetaTrader 5 read-only;
2. aggiungere `.env.example` e validazione configurazione;
3. aggiungere test mock del provider MT5;
4. creare script di avvio continuo e logging;
5. creare checklist di installazione sul PC di test;
6. eseguire test locale completo;
7. pubblicare la release privata su GitHub;
8. installare la release sul secondo PC;
9. collegare il profilo MT5 di test;
10. eseguire paper trading continuativo e raccogliere evidenze.

## Versionamento

La prima release destinata al test con feed reale sarà:

```text
v0.1.0-paper
```

## Disclaimer

Il progetto è destinato a ricerca, sviluppo software, analisi quantitativa e paper trading. I risultati ottenuti su dati storici, sintetici o simulati non garantiscono risultati futuri. La piattaforma non costituisce consulenza finanziaria e non deve essere utilizzata per inviare ordini reali nella release corrente.
