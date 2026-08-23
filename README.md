# AI Trading Indicator

Piattaforma modulare per analisi quantitativa, machine learning e monitoraggio in **Live Paper Trading**, con acquisizione dati read-only da MetaTrader 5 e terminale web multi-timeframe.

> **PAPER ONLY**
>
> La release corrente non invia ordini a MetaTrader 5 e non contiene funzioni per l'esecuzione di operazioni reali.
> MetaTrader 5 viene utilizzato esclusivamente come sorgente read-only di dati di mercato.

## Stato del progetto

La release `v0.1.0-paper` include:

- validazione e normalizzazione dei dati OHLCV;
- provider CSV per sviluppo e simulazione;
- provider MetaTrader 5 read-only;
- esclusione automatica della candela corrente ancora aperta;
- riconnessione automatica dopo errori temporanei MT5;
- supporto multi-timeframe professionale;
- archivio SQLite persistente delle candele;
- separazione dei dati per simbolo e timeframe;
- protezione dai duplicati;
- feature engineering tecnico;
- inferenza tramite modello registrato;
- verifica SHA-256 del modello;
- filtro di confidenza;
- generazione LONG, SHORT e NO_TRADE;
- calcolo teorico di Entry, Stop Loss e Take Profit;
- Live Paper Engine continuo;
- Outcome Tracker;
- statistiche Live Paper;
- persistenza SQLite di segnali ed esiti;
- backend FastAPI read-only;
- frontend Next.js e React;
- grafico candlestick professionale;
- EMA 10 ed EMA 30;
- pannello volume sincronizzato;
- crosshair con dati OHLCV;
- marker dei segnali;
- livelli Entry, Stop Loss e Take Profit;
- selettore dinamico dei timeframe;
- preflight automatico;
- script Windows di avvio e arresto;
- test automatici Python;
- lint e build del frontend.

## Sicurezza operativa

La release impone sempre:

```text
APP_MODE=PAPER_ONLY
PAPER_TRADING_ONLY=true
REAL_ORDERS_ENABLED=false
```

Il progetto non implementa:

```text
order_send
apertura ordini
chiusura ordini
modifica ordini
gestione posizioni reali
trading automatico
```

MetaTrader 5 viene utilizzato soltanto per:

```text
lettura terminale
lettura account
verifica simboli
lettura candele
lettura timestamp
lettura tick volume
```

## Architettura

```text
                    MetaTrader 5 read-only
                              |
                              v
                 MetaTrader5PollingDataProvider
                              |
                              v
                  PersistingLiveDataProvider
                       |              |
                       |              v
                       |       market_data.db
                       |       market_candles
                       |
                       v
                   PollResult
                       |
                       v
                 Live Paper Engine
                       |
              +--------+---------+
              |                  |
              v                  v
      Inferenza ML       Outcome Tracker
              |                  |
              v                  v
         signals           signal_outcomes
              |                  |
              +--------+---------+
                       |
                       v
                 live_paper.db
                       |
                       v
                 FastAPI read-only
                       |
                       v
                Next.js / React
                       |
                       v
             Trading Terminal locale
```

Durante lo sviluppo può essere utilizzato anche il provider CSV:

```text
CSV M15
   |
   v
FilePollingDataProvider
   |
   v
stessa pipeline Live Paper
```

## Stack tecnologico

### Backend e data science

- Python 3.11
- pandas
- NumPy
- scikit-learn
- FastAPI
- Uvicorn
- SQLite
- MetaTrader5 Python Integration
- python-dotenv
- joblib
- PyYAML

### Qualità e test

- pytest
- pytest-cov
- Ruff
- test con provider simulati;
- test anti-duplicato;
- test di riconnessione MT5;
- test temporali e anti-look-ahead;
- test FastAPI;
- test dello storage SQLite.

### Frontend

- Next.js 16
- React
- TypeScript
- Tailwind CSS
- Lightweight Charts
- ESLint

### Strumenti di sviluppo

- Visual Studio Code
- Git
- GitHub
- PowerShell

## Timeframe professionali

Il sistema riconosce:

```text
Minuti:
M1
M2
M3
M5
M10
M15
M30

Ore:
H1
H2
H4
H8
H12

Superiori:
D1
W1
```

Il frontend visualizza le etichette:

```text
1m  2m  3m  5m  10m  15m  30m
1h  2h  4h  8h  12h
1D  1W
```

### Regole di disponibilità

- un timeframe nativo viene letto direttamente dall'archivio;
- un timeframe superiore può essere aggregato da una sorgente nativa compatibile;
- un timeframe inferiore non viene ricostruito artificialmente;
- M1 non può essere ricostruito da M15;
- il frontend abilita soltanto i timeframe realmente disponibili;
- i timeframe indisponibili rimangono visibili ma disabilitati;
- il pallino verde identifica un timeframe nativo;
- il badge `ML` identifica il timeframe operativo del modello.

## Timeframe del modello ML

Il modello corrente:

```text
gradient_boosting_0.1.0
```

opera esclusivamente su:

```text
M15
```

I marker LONG, SHORT, NO_TRADE e i livelli operativi vengono visualizzati solo su M15.

Gli altri timeframe sono disponibili per analisi grafica e contestuale, ma non vengono presentati come se il modello avesse generato segnali su quelle risoluzioni.

## Modello registrato

Il modello operativo è registrato in:

```text
models/registry.json
```

File del modello:

```text
models/gradient_boosting_0.1.0.joblib
```

Stato corrente:

```text
CANDIDATE
```

Prima dell'inferenza il sistema verifica:

- versione del modello;
- percorso del file;
- feature richieste;
- stato consentito;
- hash SHA-256;
- integrità del file.

Il modello `CANDIDATE` è utilizzabile esclusivamente per test tecnici e Live Paper Trading.

## Funzionamento Live Paper

1. Il provider recupera le candele.
2. La candela corrente ancora aperta viene esclusa.
3. I timestamp vengono normalizzati in UTC.
4. Le candele vengono validate.
5. I duplicati vengono eliminati.
6. Le nuove candele vengono archiviate in SQLite.
7. Il Live Paper Engine aggiorna lo storico.
8. Le feature tecniche vengono calcolate senza dati futuri.
9. Il modello registrato produce una previsione.
10. Il filtro di confidenza conferma LONG, SHORT oppure NO_TRADE.
11. Il Risk Engine calcola Entry, Stop Loss e Take Profit teorici.
12. Il segnale viene salvato senza sovrascrivere record esistenti.
13. L'Outcome Tracker rivaluta i segnali pendenti.
14. FastAPI espone candele, segnali, esiti e statistiche.
15. Next.js visualizza il terminale operativo.

## Persistenza SQLite

Il progetto utilizza due database separati.

### Dati di mercato

```text
data/live_paper/market_data.db
```

Tabella:

```text
market_candles
```

Chiave univoca:

```text
symbol + timeframe + timestamp
```

Dati principali:

```text
symbol
timeframe
timestamp
open
high
low
close
volume
provider_name
received_at_utc
```

### Segnali ed esiti

```text
data/live_paper/live_paper.db
```

Tabelle:

```text
signals
signal_outcomes
```

I record già salvati non vengono sovrascritti retroattivamente.

I database runtime non devono essere versionati su Git.

## Struttura principale

```text
AITradingIndicator/
|-- data/
|   |-- sample/
|   `-- live_paper/
|-- docs/
|   `-- PC_TEST_SETUP.md
|-- frontend/
|   |-- app/
|   `-- src/
|       |-- components/
|       |-- services/
|       `-- types/
|-- logs/
|-- models/
|   |-- gradient_boosting_0.1.0.joblib
|   `-- registry.json
|-- reports/
|-- scripts/
|   |-- check_mt5_connection.py
|   |-- preflight_check.py
|   |-- run_continuous_live_paper.py
|   `-- windows/
|       |-- start_system.ps1
|       `-- stop_system.ps1
|-- src/
|   |-- api/
|   |-- app/
|   |-- backtest/
|   |-- config/
|   |-- data/
|   |-- features/
|   |-- models/
|   |-- monitoring/
|   |-- risk/
|   `-- signals/
|-- tests/
|-- .env.example
|-- .gitignore
|-- pyproject.toml
|-- requirements-dev.txt
|-- requirements-mt5.txt
`-- README.md
```

## Prerequisiti

### PC di sviluppo

- Windows;
- Git;
- Python 3.11 a 64 bit;
- Node.js;
- npm;
- Visual Studio Code, consigliato.

### PC di test MT5

- Windows;
- Git;
- Python 3.11 a 64 bit;
- Node.js;
- npm;
- MetaTrader 5;
- profilo MT5 utilizzato per il test;
- accesso al repository GitHub privato.

Versioni utilizzate durante lo sviluppo:

```text
Python 3.11.9
Node.js 24.16.0
npm 11.13.0
```

## Installazione per sviluppo

Clonare il repository:

```powershell
git clone https://github.com/UTENTE_GITHUB/AITradingIndicator.git
cd AITradingIndicator
```

Creare l'ambiente Python:

```powershell
python -m venv .venv
```

Abilitare gli script nella sessione:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

Attivare l'ambiente:

```powershell
.\.venv\Scripts\Activate.ps1
```

Installare le dipendenze:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Installare il frontend:

```powershell
cd frontend
npm install
cd ..
```

## Installazione sul PC di test

La procedura completa è disponibile in:

```text
docs/PC_TEST_SETUP.md
```

La release deve essere clonata e fissata al tag:

```powershell
git clone https://github.com/UTENTE_GITHUB/AITradingIndicator.git
cd AITradingIndicator
git checkout v0.1.0-paper
```

Sul PC di test installare le dipendenze MT5:

```powershell
python -m pip install -r requirements-mt5.txt
```

## Configurazione locale

Copiare il modello:

```powershell
Copy-Item ".env.example" ".env"
```

Configurazione generale:

```dotenv
APP_MODE=PAPER_ONLY
DATA_PROVIDER=MT5

TRADING_SYMBOL=EURUSD
TIMEFRAME_MINUTES=15

POLL_INTERVAL_SECONDS=5
MINIMUM_HISTORY_BARS=30
MAXIMUM_HOLDING_BARS=12

LIVE_PAPER_DATABASE_PATH=data/live_paper/live_paper.db
MARKET_DATA_DATABASE_PATH=data/live_paper/market_data.db

FILE_PROVIDER_PATH=data/sample/EURUSD_M15_sample.csv

MT5_LOGIN=INSERIRE_LOGIN
MT5_PASSWORD=INSERIRE_PASSWORD
MT5_SERVER=INSERIRE_SERVER
MT5_TERMINAL_PATH=C:\Program Files\MetaTrader 5\terminal64.exe

MT5_BARS_PER_POLL=500
MT5_TIMEOUT_MILLISECONDS=60000

PAPER_TRADING_ONLY=true
REAL_ORDERS_ENABLED=false
```

Il file `.env`:

- non deve essere aggiunto a Git;
- non deve essere inviato ad altre persone;
- non deve essere incluso negli screenshot;
- deve rimanere esclusivamente sul computer locale.

## Preflight

Prima di ogni prima installazione o modifica della configurazione:

```powershell
python -m scripts.preflight_check
```

Il risultato richiesto è:

```text
ESITO: SISTEMA PRONTO
PAPER TRADING: OBBLIGATORIO
ORDINI REALI: DISABILITATI
```

Il preflight verifica:

- Python 3.11;
- configurazione `.env`;
- modalità PAPER_ONLY;
- blocco degli ordini reali;
- provider selezionato;
- database configurati;
- Model Registry;
- modello operativo;
- integrità SHA-256.

## Verifica read-only di MetaTrader 5

Con MetaTrader 5 aperto e il profilo collegato:

```powershell
python -m scripts.check_mt5_connection
```

Il controllo verifica:

- terminale raggiungibile;
- account disponibile;
- simbolo disponibile;
- timeframe disponibile;
- ricezione delle candele chiuse;
- timestamp UTC;
- chiusura della connessione.

Lo script non invia ordini.

## Primo test limitato

Prima dell'avvio continuo:

```powershell
python -m scripts.run_continuous_live_paper --max-cycles 10
```

Risultato richiesto:

```text
Cicli falliti: 0
ORDINI REALI: DISABILITATI
```

## Avvio completo su Windows

Dalla root del progetto:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\scripts\windows\start_system.ps1
```

Lo script esegue:

1. preflight;
2. avvio Live Paper Engine;
3. avvio FastAPI;
4. avvio frontend Next.js;
5. salvataggio dei PID runtime.

Indirizzi locali:

```text
Frontend: http://localhost:3000
FastAPI:  http://127.0.0.1:8000
API Docs: http://127.0.0.1:8000/docs
```

## Arresto completo su Windows

```powershell
.\scripts\windows\stop_system.ps1
```

Utilizzare lo script di arresto prima di:

- spegnere il PC;
- modificare `.env`;
- aggiornare il repository;
- aggiornare MetaTrader 5;
- intervenire sui database.

## Avvio manuale

### Terminale 1: Live Paper Engine

Dalla root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m scripts.run_continuous_live_paper
```

### Terminale 2: FastAPI

Dalla root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

### Terminale 3: Next.js

Dalla cartella `frontend`:

```powershell
npm run dev
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

Esempi:

```text
/api/v1/market/candles?timeframe=M15&limit=500
/api/v1/market/candles?timeframe=M30&limit=500
/api/v1/market/candles?timeframe=H1&limit=500
/api/v1/market/candles?timeframe=H4&limit=500
/api/v1/market/candles?timeframe=D1&limit=500
```

L'endpoint:

```text
/api/v1/market/timeframes
```

indica per ogni risoluzione:

- disponibilità;
- etichetta;
- durata;
- origine nativa o aggregata;
- timeframe sorgente;
- numero di candele archiviate;
- compatibilità con il modello ML;
- motivo dell'eventuale indisponibilità.

## Terminale web

Il frontend include:

- stato backend;
- simbolo e timeframe;
- selettore di risoluzione professionale;
- candlestick;
- EMA 10;
- EMA 30;
- volume sincronizzato;
- crosshair OHLCV;
- marker LONG e SHORT;
- marker NO_TRADE;
- livelli Entry, Stop Loss e Take Profit;
- statistiche;
- tabella segnali;
- tabella esiti;
- aggiornamento automatico;
- indicazione PAPER ONLY.

## Verifica qualità

### Backend

Dalla root:

```powershell
python -m ruff check src tests scripts
python -m pytest -q
```

La release deve completare tutta la suite senza errori.

### Frontend

Dalla cartella `frontend`:

```powershell
npm run lint
npm run build
```

Entrambi devono completarsi senza errori.

## Controllo dei database

### Candele disponibili

```powershell
python -c "import sqlite3; c=sqlite3.connect('data/live_paper/market_data.db'); print(c.execute('SELECT symbol, timeframe, COUNT(*) FROM market_candles GROUP BY symbol, timeframe').fetchall()); c.close()"
```

### Segnali ed esiti

```powershell
python -c "import sqlite3; c=sqlite3.connect('data/live_paper/live_paper.db'); print('Segnali:', c.execute('SELECT COUNT(*) FROM signals').fetchone()[0]); print('Esiti:', c.execute('SELECT COUNT(*) FROM signal_outcomes').fetchone()[0]); c.close()"
```

### Duplicati

```powershell
python -c "import sqlite3; c=sqlite3.connect('data/live_paper/market_data.db'); print('Duplicati:', c.execute('SELECT COUNT(*) FROM (SELECT symbol, timeframe, timestamp, COUNT(*) AS n FROM market_candles GROUP BY symbol, timeframe, timestamp HAVING n > 1)').fetchone()[0]); c.close()"
```

Risultato richiesto:

```text
Duplicati: 0
```

## Log

Log principale:

```text
logs/continuous_live_paper.log
```

Ultime righe:

```powershell
Get-Content "logs\continuous_live_paper.log" -Tail 100
```

I log non devono contenere:

- password;
- token;
- chiavi;
- informazioni riservate;
- credenziali MT5.

## Anteprima del terminale

Le immagini reali verranno aggiunte dopo il collaudo sul PC di test.

Cartella prevista:

```text
docs/images/
```

Screenshot pianificati:

```text
01-terminal-overview.png
02-professional-timeframes.png
03-candlestick-volume-ema.png
04-live-paper-signals.png
05-statistics.png
06-signals-outcomes.png
07-preflight.png
```

Le immagini non devono mostrare:

- login MT5;
- password;
- saldo;
- equity;
- nome completo del server;
- dati personali;
- percorsi riservati.

## Roadmap successiva

Dopo il collaudo tecnico con MT5 verranno aggiunte strategie configurabili come livello separato dal modello ML.

Architettura prevista:

```text
Previsione ML
      +
Strategie configurabili
      +
Filtro di contesto
      +
Risk management
      |
      v
LONG / SHORT / NO_TRADE
```

Ogni strategia dovrà avere:

- nome;
- versione;
- parametri configurabili;
- attivazione e disattivazione;
- priorità o peso;
- motivazione della decisione;
- test automatici;
- test anti-look-ahead;
- metriche separate;
- audit del contributo al segnale finale.

Il sistema dovrà poter confrontare:

```text
solo modello ML
solo strategia
modello ML + strategia
```

Le strategie non modificheranno retroattivamente i segnali già registrati.

## Limiti della release

- il modello corrente è ancora `CANDIDATE`;
- la validazione tecnica non dimostra redditività;
- accuracy e performance storiche non garantiscono risultati futuri;
- il sistema non è destinato al trading con denaro reale;
- le strategie configurabili non sono ancora incluse;
- gli screenshot reali saranno aggiunti dopo il test MT5;
- i timeframe inferiori richiedono dati nativi dal provider.

## Versionamento

Prima release destinata al collaudo MT5 read-only:

```text
v0.1.0-paper
```

## Disclaimer

AI Trading Indicator è un progetto destinato a ricerca, sviluppo software, analisi quantitativa e paper trading.

I segnali LONG, SHORT e NO_TRADE sono output sperimentali. Non costituiscono consulenza finanziaria e non garantiscono risultati futuri.

La release corrente non deve essere utilizzata per inviare ordini reali o operare con denaro reale.