"""Test automatici del report statistico Live Paper."""

import pandas as pd
import pytest

from src.monitoring.live_paper_report import (
    LivePaperReportError,
    generate_live_paper_statistics,
)


def create_signals() -> pd.DataFrame:
    """Crea un registro deterministico di segnali."""

    return pd.DataFrame(
        {
            "signal_id": [
                "signal-001",
                "signal-002",
                "signal-003",
                "signal-004",
                "signal-005",
            ],
            "signal": [
                "LONG",
                "SHORT",
                "NO_TRADE",
                "LONG",
                "SHORT",
            ],
            "signal_status": [
                "CONFIRMED",
                "CONFIRMED",
                "CONFIRMED",
                "CONFIRMED",
                "CONFIRMED",
            ],
            "prediction_confidence": [
                0.80,
                0.70,
                0.65,
                0.90,
                0.60,
            ],
        }
    )


def create_outcomes() -> pd.DataFrame:
    """Crea tre esiti conclusivi e un segnale pendente."""

    return pd.DataFrame(
        {
            "signal_id": [
                "signal-001",
                "signal-002",
                "signal-004",
            ],
            "exit_reason": [
                "TAKE_PROFIT_1",
                "STOP_LOSS",
                "TIME_EXPIRY",
            ],
            "holding_bars": [
                2,
                1,
                4,
            ],
            "gross_return_percentage": [
                0.02,
                -0.01,
                0.005,
            ],
            "result_r": [
                1.0,
                -1.0,
                0.25,
            ],
        }
    )


def test_signal_counts_are_correct() -> None:
    """Verifica i conteggi dei segnali."""

    report = generate_live_paper_statistics(
        signals=create_signals(),
        outcomes=create_outcomes(),
    )

    assert report.total_signals == 5
    assert report.long_signals == 2
    assert report.short_signals == 2
    assert report.no_trade_signals == 1
    assert report.directional_signals == 4


def test_resolved_and_pending_counts_are_correct() -> None:
    """Verifica segnali conclusi e pendenti."""

    report = generate_live_paper_statistics(
        signals=create_signals(),
        outcomes=create_outcomes(),
    )

    assert report.resolved_directional_signals == 3
    assert report.pending_directional_signals == 1
    assert report.resolution_rate_percentage == 75.0


def test_win_rate_and_expectancy_are_correct() -> None:
    """Verifica win rate ed expectancy."""

    report = generate_live_paper_statistics(
        signals=create_signals(),
        outcomes=create_outcomes(),
    )

    assert report.winning_outcomes == 2
    assert report.losing_outcomes == 1
    assert report.breakeven_outcomes == 0

    assert report.win_rate_percentage == pytest.approx(66.666667)

    assert report.expectancy_r == pytest.approx(
        round(
            (1.0 - 1.0 + 0.25) / 3,
            6,
        )
    )


def test_profit_factor_is_correct() -> None:
    """Verifica il Profit Factor in R."""

    report = generate_live_paper_statistics(
        signals=create_signals(),
        outcomes=create_outcomes(),
    )

    # Profitti R: 1,25. Perdite R: 1.
    assert report.profit_factor == 1.25


def test_exit_reason_counts_are_correct() -> None:
    """Verifica la distribuzione delle uscite."""

    report = generate_live_paper_statistics(
        signals=create_signals(),
        outcomes=create_outcomes(),
    )

    assert report.take_profit_outcomes == 1
    assert report.stop_loss_outcomes == 1
    assert report.ambiguous_stop_outcomes == 0
    assert report.time_expiry_outcomes == 1


def test_drawdown_and_compounded_return_are_generated() -> None:
    """Verifica rendimento composto e drawdown."""

    report = generate_live_paper_statistics(
        signals=create_signals(),
        outcomes=create_outcomes(),
    )

    assert report.cumulative_return_percentage == pytest.approx(
        round(
            (1.02 * 0.99 * 1.005 - 1.0) * 100.0,
            6,
        )
    )

    assert report.maximum_drawdown_percentage > 0.0


def test_average_confidence_is_directional_only() -> None:
    """Verifica che NO_TRADE non influenzi la confidenza media."""

    report = generate_live_paper_statistics(
        signals=create_signals(),
        outcomes=create_outcomes(),
    )

    expected_confidence = (0.80 + 0.70 + 0.90 + 0.60) / 4

    assert report.average_directional_confidence == (pytest.approx(expected_confidence))


def test_unknown_outcome_signal_is_rejected() -> None:
    """Verifica il rifiuto di un esito senza segnale."""

    outcomes = create_outcomes()

    outcomes.loc[
        0,
        "signal_id",
    ] = "unknown-signal"

    with pytest.raises(
        LivePaperReportError,
        match="segnali inesistenti",
    ):
        generate_live_paper_statistics(
            signals=create_signals(),
            outcomes=outcomes,
        )
