"""Dashboard professionale del sistema AI Trading Indicator."""

# Importa SQLite per leggere segnali ed esiti.
import sqlite3

# Importa Path per gestire i percorsi locali.
from pathlib import Path

# Importa pandas per elaborare dati tabellari e serie temporali.
import pandas as pd

# Importa Plotly per i grafici finanziari interattivi.
import plotly.graph_objects as go

# Importa Streamlit per costruire la dashboard web.
import streamlit as st

# Importa la configurazione e la pipeline delle feature tecniche.
from src.features.technical import (
    TechnicalFeatureConfig,
    build_technical_features,
)

# Importa il generatore delle statistiche Live Paper.
from src.monitoring.live_paper_report import (
    generate_live_paper_statistics,
)

# Configura la pagina Streamlit.
st.set_page_config(
    page_title="AI Trading Indicator",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Applica lo stile grafico personalizzato.
st.markdown(
    """
    <style>
        /* Colore generale della pagina. */
        .stApp {
            background:
                radial-gradient(
                    circle at top right,
                    rgba(48, 79, 254, 0.10),
                    transparent 30%
                ),
                #070b14;
            color: #e8edf7;
        }

        /* Barra superiore Streamlit. */
        header[data-testid="stHeader"] {
            background: rgba(7, 11, 20, 0.85);
            backdrop-filter: blur(10px);
        }

        /* Barra laterale. */
        section[data-testid="stSidebar"] {
            background: #0b1020;
            border-right: 1px solid #1d2940;
        }

        /* Contenitore principale. */
        .block-container {
            max-width: 1600px;
            padding-top: 1.3rem;
            padding-bottom: 2rem;
        }

        /* Header personalizzato. */
        .dashboard-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 18px 22px;
            margin-bottom: 18px;
            border: 1px solid #1d2940;
            border-radius: 16px;
            background: linear-gradient(
                135deg,
                rgba(17, 25, 45, 0.96),
                rgba(9, 14, 27, 0.96)
            );
            box-shadow: 0 12px 30px rgba(0, 0, 0, 0.22);
        }

        .dashboard-title {
            margin: 0;
            font-size: 1.65rem;
            font-weight: 700;
            color: #f5f7ff;
        }

        .dashboard-subtitle {
            margin-top: 5px;
            color: #8794ad;
            font-size: 0.88rem;
        }

        .paper-badge {
            padding: 8px 13px;
            border: 1px solid rgba(255, 193, 7, 0.50);
            border-radius: 10px;
            background: rgba(255, 193, 7, 0.10);
            color: #ffd54f;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.08em;
        }

        /* Card delle metriche Streamlit. */
        div[data-testid="stMetric"] {
            min-height: 104px;
            padding: 15px 17px;
            border: 1px solid #1d2940;
            border-radius: 14px;
            background: rgba(13, 20, 36, 0.94);
            box-shadow: 0 8px 22px rgba(0, 0, 0, 0.18);
        }

        div[data-testid="stMetricLabel"] {
            color: #8794ad;
        }

        div[data-testid="stMetricValue"] {
            color: #f4f7ff;
            font-size: 1.55rem;
        }

        /* Schede Streamlit. */
        button[data-baseweb="tab"] {
            color: #8794ad;
            font-weight: 600;
        }

        button[data-baseweb="tab"][aria-selected="true"] {
            color: #7ca5ff;
        }

        /* DataFrame. */
        div[data-testid="stDataFrame"] {
            border: 1px solid #1d2940;
            border-radius: 12px;
            overflow: hidden;
        }

        /* Titoli di sezione. */
        .section-title {
            margin-top: 12px;
            margin-bottom: 12px;
            color: #dce5f7;
            font-size: 1.05rem;
            font-weight: 650;
        }

        /* Stato feed. */
        .feed-online {
            color: #00d68f;
            font-weight: 700;
        }

        .feed-offline {
            color: #ff5c77;
            font-weight: 700;
        }

        /* Nasconde il footer predefinito. */
        footer {
            visibility: hidden;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    """Verifica se una tabella esiste nel database SQLite."""

    # Interroga il catalogo interno di SQLite.
    cursor = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    )

    # Restituisce True se la tabella è presente.
    return cursor.fetchone() is not None


@st.cache_data
def load_market_data(
    csv_path_text: str,
) -> pd.DataFrame:
    """Carica e normalizza il dataset OHLCV."""

    # Converte il percorso in un oggetto Path.
    csv_path = Path(csv_path_text)

    # Verifica che il file esista.
    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset OHLCV non trovato: {csv_path}.")

    # Legge il CSV.
    dataframe = pd.read_csv(csv_path)

    # Converte il timestamp in UTC.
    dataframe["timestamp"] = pd.to_datetime(
        dataframe["timestamp"],
        utc=True,
        errors="raise",
    )

    # Ordina cronologicamente il dataset.
    return dataframe.sort_values("timestamp").reset_index(drop=True)


@st.cache_data
def load_database_data(
    database_path_text: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Carica segnali ed esiti dal database Live Paper."""

    # Converte il percorso ricevuto.
    database_path = Path(database_path_text)

    # Restituisce due DataFrame vuoti se il database non esiste.
    if not database_path.exists():
        return pd.DataFrame(), pd.DataFrame()

    # Apre il database SQLite.
    with sqlite3.connect(database_path) as connection:
        # Carica i segnali quando la tabella è presente.
        if table_exists(connection, "signals"):
            signals = pd.read_sql_query(
                """
                SELECT *
                FROM signals
                ORDER BY timestamp ASC
                """,
                connection,
            )
        else:
            signals = pd.DataFrame()

        # Carica gli esiti quando la tabella è presente.
        if table_exists(
            connection,
            "signal_outcomes",
        ):
            outcomes = pd.read_sql_query(
                """
                SELECT *
                FROM signal_outcomes
                ORDER BY exit_timestamp ASC
                """,
                connection,
            )
        else:
            outcomes = pd.DataFrame()

    # Converte i timestamp dei segnali.
    if not signals.empty:
        signals["timestamp"] = pd.to_datetime(
            signals["timestamp"],
            utc=True,
            errors="coerce",
        )

        signals["signal_available_at"] = pd.to_datetime(
            signals["signal_available_at"],
            utc=True,
            errors="coerce",
        )

    # Converte il timestamp degli esiti.
    if not outcomes.empty:
        outcomes["exit_timestamp"] = pd.to_datetime(
            outcomes["exit_timestamp"],
            utc=True,
            errors="coerce",
        )

    # Restituisce i registri caricati.
    return signals, outcomes


def create_empty_outcomes() -> pd.DataFrame:
    """Crea un registro vuoto compatibile con il report."""

    # Definisce lo schema minimo richiesto.
    return pd.DataFrame(
        columns=[
            "signal_id",
            "exit_reason",
            "holding_bars",
            "gross_return_percentage",
            "result_r",
        ]
    )


def calculate_statistics(
    signals: pd.DataFrame,
    outcomes: pd.DataFrame,
):
    """Calcola le statistiche quando sono disponibili segnali."""

    # Senza segnali non è possibile creare le statistiche.
    if signals.empty:
        return None

    # Usa uno schema vuoto quando non esistono ancora esiti.
    selected_outcomes = outcomes if not outcomes.empty else create_empty_outcomes()

    # Genera il report statistico.
    return generate_live_paper_statistics(
        signals=signals,
        outcomes=selected_outcomes,
    )


def create_market_chart(
    market_data: pd.DataFrame,
    signals: pd.DataFrame,
    show_ema: bool,
    show_levels: bool,
) -> go.Figure:
    """Crea il grafico candlestick con EMA, segnali e livelli."""

    # Crea la figura Plotly.
    figure = go.Figure()

    # Aggiunge le candele.
    figure.add_trace(
        go.Candlestick(
            x=market_data["timestamp"],
            open=market_data["open"],
            high=market_data["high"],
            low=market_data["low"],
            close=market_data["close"],
            name="OHLC",
            increasing_line_color="#00d68f",
            decreasing_line_color="#ff5c77",
            increasing_fillcolor="#00b77a",
            decreasing_fillcolor="#e7425f",
        )
    )

    # Aggiunge le EMA.
    if show_ema:
        figure.add_trace(
            go.Scatter(
                x=market_data["timestamp"],
                y=market_data["ema_fast"],
                mode="lines",
                name="EMA veloce",
                line={
                    "color": "#4ea1ff",
                    "width": 1.6,
                },
            )
        )

        figure.add_trace(
            go.Scatter(
                x=market_data["timestamp"],
                y=market_data["ema_slow"],
                mode="lines",
                name="EMA lenta",
                line={
                    "color": "#ffb74d",
                    "width": 1.6,
                },
            )
        )

    # Aggiunge marker e livelli dei segnali.
    if not signals.empty:
        # Seleziona i segnali direzionali.
        long_signals = signals.loc[signals["signal"] == "LONG"]

        short_signals = signals.loc[signals["signal"] == "SHORT"]

        # Aggiunge i marker LONG.
        if not long_signals.empty:
            figure.add_trace(
                go.Scatter(
                    x=long_signals["timestamp"],
                    y=long_signals["close_price"],
                    mode="markers",
                    name="LONG",
                    marker={
                        "symbol": "triangle-up",
                        "size": 16,
                        "color": "#00e096",
                        "line": {
                            "color": "#d8fff1",
                            "width": 1,
                        },
                    },
                    customdata=long_signals[
                        [
                            "prediction_confidence",
                            "model_version",
                        ]
                    ].to_numpy(),
                    hovertemplate=(
                        "<b>LONG</b><br>"
                        "Prezzo: %{y:.5f}<br>"
                        "Confidenza: %{customdata.2%}<br>"
                        "Modello: %{customdata[1]}"
                        "<extra></extra>"
                    ),
                )
            )

        # Aggiunge i marker SHORT.
        if not short_signals.empty:
            figure.add_trace(
                go.Scatter(
                    x=short_signals["timestamp"],
                    y=short_signals["close_price"],
                    mode="markers",
                    name="SHORT",
                    marker={
                        "symbol": "triangle-down",
                        "size": 16,
                        "color": "#ff4664",
                        "line": {
                            "color": "#ffe1e6",
                            "width": 1,
                        },
                    },
                    customdata=short_signals[
                        [
                            "prediction_confidence",
                            "model_version",
                        ]
                    ].to_numpy(),
                    hovertemplate=(
                        "<b>SHORT</b><br>"
                        "Prezzo: %{y:.5f}<br>"
                        "Confidenza: %{customdata.2%}<br>"
                        "Modello: %{customdata[1]}"
                        "<extra></extra>"
                    ),
                )
            )

        # Aggiunge i livelli operativi teorici.
        if show_levels:
            directional_signals = signals.loc[
                signals["signal"].isin(
                    {
                        "LONG",
                        "SHORT",
                    }
                )
            ]

            for _, signal_row in directional_signals.iterrows():
                # Definisce un breve intervallo per le linee.
                start_time = signal_row["timestamp"]
                end_time = start_time + pd.Timedelta(minutes=45)

                # Linea Entry.
                figure.add_trace(
                    go.Scatter(
                        x=[
                            start_time,
                            end_time,
                        ],
                        y=[
                            signal_row["entry_price"],
                            signal_row["entry_price"],
                        ],
                        mode="lines",
                        line={
                            "color": "#dce5f7",
                            "width": 1,
                            "dash": "dot",
                        },
                        name="Entry",
                        legendgroup="entry",
                        showlegend=False,
                        hovertemplate=("Entry: %{y:.5f}<extra></extra>"),
                    )
                )

                # Linea Stop Loss.
                figure.add_trace(
                    go.Scatter(
                        x=[
                            start_time,
                            end_time,
                        ],
                        y=[
                            signal_row["stop_loss"],
                            signal_row["stop_loss"],
                        ],
                        mode="lines",
                        line={
                            "color": "#ff4664",
                            "width": 1.2,
                            "dash": "dash",
                        },
                        name="Stop Loss",
                        legendgroup="stop",
                        showlegend=False,
                        hovertemplate=("Stop Loss: %{y:.5f}<extra></extra>"),
                    )
                )

                # Linea Take Profit.
                figure.add_trace(
                    go.Scatter(
                        x=[
                            start_time,
                            end_time,
                        ],
                        y=[
                            signal_row["take_profit_1"],
                            signal_row["take_profit_1"],
                        ],
                        mode="lines",
                        line={
                            "color": "#00d68f",
                            "width": 1.2,
                            "dash": "dash",
                        },
                        name="TP1",
                        legendgroup="tp",
                        showlegend=False,
                        hovertemplate=("TP1: %{y:.5f}<extra></extra>"),
                    )
                )

    # Configura il tema del grafico.
    figure.update_layout(
        height=650,
        paper_bgcolor="#0d1424",
        plot_bgcolor="#0d1424",
        font={
            "color": "#a9b5cc",
        },
        margin={
            "l": 15,
            "r": 15,
            "t": 25,
            "b": 15,
        },
        hovermode="x unified",
        xaxis={
            "title": "",
            "gridcolor": "#1b2941",
            "showgrid": True,
            "rangeslider": {
                "visible": False,
            },
        },
        yaxis={
            "title": "Prezzo",
            "side": "right",
            "gridcolor": "#1b2941",
            "showgrid": True,
            "fixedrange": False,
        },
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.01,
            "xanchor": "left",
            "x": 0,
        },
    )

    # Restituisce il grafico.
    return figure


def create_equity_chart(
    outcomes: pd.DataFrame,
) -> go.Figure:
    """Crea la curva cumulativa degli esiti paper."""

    # Crea una copia ordinata.
    equity_data = outcomes.sort_values("exit_timestamp").copy()

    # Calcola una curva a capitale unitario.
    equity_data["equity"] = (1.0 + equity_data["gross_return_percentage"]).cumprod()

    # Calcola il massimo storico.
    equity_data["running_maximum"] = equity_data["equity"].cummax()

    # Calcola il drawdown.
    equity_data["drawdown_percentage"] = (
        equity_data["equity"] / equity_data["running_maximum"] - 1.0
    ) * 100.0

    # Crea la figura.
    figure = go.Figure()

    # Aggiunge la curva cumulativa.
    figure.add_trace(
        go.Scatter(
            x=equity_data["exit_timestamp"],
            y=equity_data["equity"],
            mode="lines+markers",
            name="Equity paper",
            line={
                "color": "#4ea1ff",
                "width": 2,
            },
            fill="tozeroy",
            fillcolor="rgba(78, 161, 255, 0.08)",
        )
    )

    # Configura il grafico.
    figure.update_layout(
        height=310,
        paper_bgcolor="#0d1424",
        plot_bgcolor="#0d1424",
        font={
            "color": "#a9b5cc",
        },
        margin={
            "l": 15,
            "r": 15,
            "t": 20,
            "b": 15,
        },
        xaxis={
            "gridcolor": "#1b2941",
        },
        yaxis={
            "title": "Equity",
            "side": "right",
            "gridcolor": "#1b2941",
        },
        showlegend=False,
    )

    # Restituisce il grafico.
    return figure


def main() -> None:
    """Visualizza la dashboard professionale."""

    # Sidebar delle impostazioni.
    st.sidebar.markdown("## Control Center")

    # Seleziona il simbolo informativo.
    symbol = st.sidebar.selectbox(
        "Mercato",
        options=[
            "EURUSD",
        ],
    )

    # Seleziona il timeframe informativo.
    timeframe = st.sidebar.selectbox(
        "Timeframe",
        options=[
            "M15",
        ],
    )

    # Percorso del dataset OHLCV.
    csv_path_text = st.sidebar.text_input(
        "Dataset OHLCV",
        value="data/sample/EURUSD_M15_sample.csv",
    )

    # Percorso del database.
    database_path_text = st.sidebar.text_input(
        "Database Live Paper",
        value=("data/live_paper/coordinated_live_paper.db"),
    )

    # Opzioni del grafico.
    st.sidebar.markdown("### Visualizzazione")

    show_ema = st.sidebar.toggle(
        "EMA veloce e lenta",
        value=True,
    )

    show_levels = st.sidebar.toggle(
        "Entry, Stop Loss e TP1",
        value=True,
    )

    maximum_bars = st.sidebar.slider(
        "Candele visualizzate",
        min_value=20,
        max_value=500,
        value=200,
        step=10,
    )

    # Pulsante manuale di aggiornamento.
    if st.sidebar.button(
        "Aggiorna dati",
        width="stretch",
        type="primary",
    ):
        st.cache_data.clear()
        st.rerun()

    # Mostra avviso laterale.
    st.sidebar.warning("Modalità PAPER ONLY\n\nNessun ordine viene inviato.")

    # Carica tutti i dati.
    try:
        market_data = load_market_data(csv_path_text)

        feature_config = TechnicalFeatureConfig(
            ema_fast_period=2,
            ema_slow_period=4,
            atr_period=3,
            volatility_period=3,
        )

        market_data = build_technical_features(
            dataframe=market_data,
            config=feature_config,
        )

        market_data = market_data.tail(maximum_bars).reset_index(drop=True)

        signals, outcomes = load_database_data(database_path_text)

        statistics = calculate_statistics(
            signals=signals,
            outcomes=outcomes,
        )

    except Exception as error:
        st.exception(error)
        st.stop()

    # Determina lo stato del database.
    database_connected = Path(database_path_text).exists()

    feed_status_class = "feed-online" if database_connected else "feed-offline"

    feed_status_text = "ONLINE" if database_connected else "OFFLINE"

    # Mostra l'header professionale.
    st.markdown(
        f"""
        <div class="dashboard-header">
            <div>
                <div class="dashboard-title">
                    {symbol} · {timeframe}
                </div>
                <div class="dashboard-subtitle">
                    AI Trading Indicator ·
                    Feed <span class="{feed_status_class}">
                    {feed_status_text}</span> · UTC
                </div>
            </div>
            <div class="paper-badge">
                PAPER ONLY
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Mostra i KPI principali.
    metric_columns = st.columns(6)

    metric_columns[0].metric(
        "Ultimo prezzo",
        f"{market_data.iloc[-1]['close']:.5f}",
    )

    metric_columns[1].metric(
        "Segnali",
        0 if statistics is None else statistics.total_signals,
    )

    metric_columns[2].metric(
        "LONG",
        0 if statistics is None else statistics.long_signals,
    )

    metric_columns[3].metric(
        "SHORT",
        0 if statistics is None else statistics.short_signals,
    )

    metric_columns[4].metric(
        "Win rate",
        ("0.00%" if statistics is None else f"{statistics.win_rate_percentage:.2f}%"),
    )

    metric_columns[5].metric(
        "Expectancy",
        ("0.000 R" if statistics is None else f"{statistics.expectancy_r:.3f} R"),
    )

    # Mostra il titolo della sezione mercato.
    st.markdown(
        '<div class="section-title">Market overview</div>',
        unsafe_allow_html=True,
    )

    # Crea e mostra il grafico principale.
    market_figure = create_market_chart(
        market_data=market_data,
        signals=signals,
        show_ema=show_ema,
        show_levels=show_levels,
    )

    st.plotly_chart(
        market_figure,
        width="stretch",
        config={
            "displaylogo": False,
            "scrollZoom": True,
        },
    )

    # Sezione Analytics.
    st.markdown(
        '<div class="section-title">Analytics</div>',
        unsafe_allow_html=True,
    )

    analytics_left, analytics_right = st.columns(
        [
            1.5,
            1,
        ]
    )

    # Mostra curva cumulativa oppure stato vuoto.
    with analytics_left:
        if outcomes.empty:
            st.info("La curva cumulativa apparirà dopo il primo esito conclusivo.")
        else:
            st.plotly_chart(
                create_equity_chart(outcomes),
                width="stretch",
                config={
                    "displaylogo": False,
                },
            )

    # Mostra metriche di rischio.
    with analytics_right:
        risk_columns = st.columns(2)

        risk_columns[0].metric(
            "Conclusi",
            (0 if statistics is None else statistics.resolved_directional_signals),
        )

        risk_columns[1].metric(
            "Pendenti",
            (0 if statistics is None else statistics.pending_directional_signals),
        )

        risk_columns[0].metric(
            "Profit Factor",
            (
                "N/D"
                if statistics is None or statistics.profit_factor is None
                else f"{statistics.profit_factor:.3f}"
            ),
        )

        risk_columns[1].metric(
            "Max Drawdown",
            (
                "0.000%"
                if statistics is None
                else (f"{statistics.maximum_drawdown_percentage:.3f}%")
            ),
        )

    # Schede di dettaglio.
    st.markdown(
        '<div class="section-title">Operations</div>',
        unsafe_allow_html=True,
    )

    signals_tab, outcomes_tab, model_tab = st.tabs(
        [
            "Segnali",
            "Esiti",
            "Model audit",
        ]
    )

    # Tabella segnali.
    with signals_tab:
        if signals.empty:
            st.info("Nessun segnale disponibile.")
        else:
            selected_columns = [
                "timestamp",
                "signal",
                "close_price",
                "entry_price",
                "stop_loss",
                "take_profit_1",
                "take_profit_2",
                "take_profit_3",
                "prediction_confidence",
                "filter_reason",
            ]

            available_columns = [column for column in selected_columns if column in signals.columns]

            st.dataframe(
                signals[available_columns].sort_values(
                    "timestamp",
                    ascending=False,
                ),
                width="stretch",
                hide_index=True,
            )

    # Tabella esiti.
    with outcomes_tab:
        if outcomes.empty:
            st.info("Nessun esito conclusivo disponibile.")
        else:
            st.dataframe(
                outcomes.sort_values(
                    "exit_timestamp",
                    ascending=False,
                ),
                width="stretch",
                hide_index=True,
            )

    # Audit del modello.
    with model_tab:
        if signals.empty:
            st.info("Nessun modello ancora associato ai segnali.")
        else:
            audit_columns = [
                "timestamp",
                "signal",
                "signal_source",
                "model_version",
                "model_sha256",
                "prediction_confidence",
                "probability_margin",
                "filter_reason",
                "operating_mode",
            ]

            available_audit_columns = [
                column for column in audit_columns if column in signals.columns
            ]

            st.dataframe(
                signals[available_audit_columns].sort_values(
                    "timestamp",
                    ascending=False,
                ),
                width="stretch",
                hide_index=True,
            )

    # Nota finale.
    st.caption(
        "AI Trading Indicator · Dashboard locale · "
        "Uso educativo e paper trading · Nessun ordine reale"
    )


if __name__ == "__main__":
    # Avvia la dashboard.
    main()
