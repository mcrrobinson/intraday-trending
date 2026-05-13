from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yfinance as yf

INITIAL_CAPITAL = 10_000.0
ONE_TIME_BUY_DATE = pd.Timestamp("2023-05-12", tz="UTC")
EVAL_DATE = pd.Timestamp("2026-03-27 23:59:59", tz="UTC")
LONDON_TZ = "Europe/London"
TICKER = "^FTSE"
DATA_PERIOD = "730d"
DATA_INTERVAL = "1h"
CSV_PATH = Path("ftse_hourly.csv")

# Tuned simple weekly timing rule for this historical window.
WEEKLY_BUY_DAY = 0  # Monday
WEEKLY_BUY_HOUR = 10
WEEKLY_SELL_DAY = 4  # Friday
WEEKLY_SELL_HOUR = 8

WEEKDAY_NAMES = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}


@dataclass
class PortfolioResult:
    method: str
    value: float
    total_return_pct: float


@dataclass
class StrategyCandidate:
    buy_day: int
    buy_hour: int
    sell_day: int
    sell_hour: int
    trades: int
    final_value: float
    total_return_pct: float
    edge_vs_hold_pct: float


def get_local_window(close: pd.Series) -> pd.Series:
    # Raw hourly timestamps are UTC; convert once so weekday/hour filters use London clock time.
    local = close.tz_convert(LONDON_TZ)
    start_local = ONE_TIME_BUY_DATE.tz_convert(LONDON_TZ)
    end_local = EVAL_DATE.tz_convert(LONDON_TZ)
    return local.loc[(local.index >= start_local) & (local.index <= end_local)]


def load_close_series() -> pd.Series:
    if CSV_PATH.exists():
        data = pd.read_csv(CSV_PATH, header=[0, 1], index_col=0)
    else:
        data = yf.download(TICKER, interval=DATA_INTERVAL, period=DATA_PERIOD)
        if data is None or data.empty:
            raise ValueError("Failed to download close price data.")
        data.to_csv(CSV_PATH)

    data = data.copy()
    data.index = pd.to_datetime(data.index, utc=True)

    close_prices = data["Close"]
    if isinstance(close_prices, pd.Series):
        close = close_prices.astype(float).dropna().sort_index()
        close.name = "close"
        return close

    if close_prices.empty:
        raise ValueError("No close price data found in downloaded data.")

    close = close_prices.iloc[:, 0].astype(float).dropna().sort_index()
    close.name = str(close_prices.columns[0])
    return close


def first_price_on_or_after(series: pd.Series, when: pd.Timestamp) -> tuple[pd.Timestamp, float]:
    filtered = series.loc[series.index >= when]
    if filtered.empty:
        raise ValueError(f"No price found on or after {when}.")
    ts = filtered.index[0]
    return ts, float(filtered.iloc[0])


def last_price_on_or_before(series: pd.Series, when: pd.Timestamp) -> tuple[pd.Timestamp, float]:
    filtered = series.loc[series.index <= when]
    if filtered.empty:
        raise ValueError(f"No price found on or before {when}.")
    ts = filtered.index[-1]
    return ts, float(filtered.iloc[-1])


def simulate_one_time_investment(close: pd.Series) -> PortfolioResult:
    buy_ts, buy_price = first_price_on_or_after(close, ONE_TIME_BUY_DATE)
    eval_ts, eval_price = last_price_on_or_before(close, EVAL_DATE)

    units = INITIAL_CAPITAL / buy_price
    final_value = units * eval_price
    total_return_pct = (final_value / INITIAL_CAPITAL - 1.0) * 100.0

    print("One-time strategy")
    print(f"  Buy datetime (UTC): {buy_ts}")
    print(f"  Buy price: {buy_price:.4f}")
    print(f"  Evaluation datetime (UTC): {eval_ts}")
    print(f"  Evaluation price: {eval_price:.4f}")

    return PortfolioResult(
        method="One-time buy and hold",
        value=final_value,
        total_return_pct=total_return_pct,
    )


def simulate_weekly_strategy(close: pd.Series) -> PortfolioResult:
    local = get_local_window(close)
    local_index = pd.DatetimeIndex(local.index)

    buy_mask = (
        (local_index.dayofweek == WEEKLY_BUY_DAY)
        & (local_index.hour == WEEKLY_BUY_HOUR)
    )
    sell_mask = (
        (local_index.dayofweek == WEEKLY_SELL_DAY)
        & (local_index.hour == WEEKLY_SELL_HOUR)
    )

    buy_points = local.loc[buy_mask]
    sell_points = local.loc[sell_mask]

    if buy_points.empty:
        raise ValueError("No buy prices found for the configured weekly schedule.")
    if sell_points.empty:
        raise ValueError("No sell prices found for the configured weekly schedule.")

    capital = INITIAL_CAPITAL
    trades = 0
    buy_index = pd.DatetimeIndex(buy_points.index)
    sell_index = pd.DatetimeIndex(sell_points.index)

    for i in range(len(buy_points)):
        buy_ts = buy_index[i]
        buy_price = float(buy_points.iloc[i])
        sell_pos = int(sell_index.searchsorted(buy_ts, side="right"))
        if sell_pos >= len(sell_index):
            break

        sell_ts = sell_index[sell_pos]
        if sell_ts.tz_convert("UTC") > EVAL_DATE:
            break

        sell_price = float(sell_points.iloc[sell_pos])
        capital *= sell_price / float(buy_price)
        trades += 1

    total_return_pct = (capital / INITIAL_CAPITAL - 1.0) * 100.0

    buy_label = f"{WEEKDAY_NAMES[WEEKLY_BUY_DAY]} {WEEKLY_BUY_HOUR}:00"
    sell_label = f"{WEEKDAY_NAMES[WEEKLY_SELL_DAY]} {WEEKLY_SELL_HOUR}:00"
    print(
        "Weekly strategy "
        f"(buy {buy_label}, sell {sell_label}, London time)"
    )
    print(f"  Completed trades: {trades}")

    return PortfolioResult(
        method=f"Weekly {buy_label} to {sell_label}",
        value=capital,
        total_return_pct=total_return_pct,
    )


def evaluate_weekly_pair(
    local: pd.Series,
    buy_day: int,
    buy_hour: int,
    sell_day: int,
    sell_hour: int,
) -> tuple[float, int]:
    local_index = pd.DatetimeIndex(local.index)
    buy_points = local.loc[(local_index.dayofweek == buy_day) & (local_index.hour == buy_hour)]
    sell_points = local.loc[(local_index.dayofweek == sell_day) & (local_index.hour == sell_hour)]
    if buy_points.empty or sell_points.empty:
        return INITIAL_CAPITAL, 0

    capital = INITIAL_CAPITAL
    trades = 0
    buy_index = pd.DatetimeIndex(buy_points.index)
    sell_index = pd.DatetimeIndex(sell_points.index)
    for i in range(len(buy_points)):
        buy_ts = buy_index[i]
        buy_price = float(buy_points.iloc[i])
        sell_pos = int(sell_index.searchsorted(buy_ts, side="right"))
        if sell_pos >= len(sell_index):
            break
        sell_price = float(sell_points.iloc[sell_pos])
        capital *= sell_price / float(buy_price)
        trades += 1

    return capital, trades


def run_weekly_grid_search(close: pd.Series, hold: PortfolioResult, top_n: int = 10) -> pd.DataFrame:
    local = get_local_window(close)

    candidates: list[StrategyCandidate] = []
    hours = list(range(8, 17))

    for buy_day in range(5):
        for buy_hour in hours:
            for sell_day in range(5):
                for sell_hour in hours:
                    final_value, trades = evaluate_weekly_pair(
                        local, buy_day, buy_hour, sell_day, sell_hour
                    )
                    if trades < 30:
                        continue
                    total_return_pct = (final_value / INITIAL_CAPITAL - 1.0) * 100.0
                    edge_vs_hold_pct = total_return_pct - hold.total_return_pct
                    candidates.append(
                        StrategyCandidate(
                            buy_day=buy_day,
                            buy_hour=buy_hour,
                            sell_day=sell_day,
                            sell_hour=sell_hour,
                            trades=trades,
                            final_value=final_value,
                            total_return_pct=total_return_pct,
                            edge_vs_hold_pct=edge_vs_hold_pct,
                        )
                    )

    if not candidates:
        return pd.DataFrame()

    rows = [
        {
            "buy_day": WEEKDAY_NAMES[c.buy_day],
            "buy_hour": c.buy_hour,
            "sell_day": WEEKDAY_NAMES[c.sell_day],
            "sell_hour": c.sell_hour,
            "trades": c.trades,
            "final_value": c.final_value,
            "total_return_pct": c.total_return_pct,
            "edge_vs_buy_hold_pct": c.edge_vs_hold_pct,
        }
        for c in candidates
    ]
    result = pd.DataFrame(rows).sort_values(
        by=["edge_vs_buy_hold_pct", "total_return_pct"], ascending=False
    )
    return result.head(top_n).reset_index(drop=True)


def main() -> None:
    close = load_close_series()
    one_time = simulate_one_time_investment(close)
    weekly = simulate_weekly_strategy(close)

    print("\nPortfolio comparison on 2026-03-27")
    print("=" * 42)
    print(
        f"{one_time.method:34s} value={one_time.value:10.2f}  "
        f"return={one_time.total_return_pct:7.2f}%"
    )
    print(
        f"{weekly.method:34s} value={weekly.value:10.2f}  "
        f"return={weekly.total_return_pct:7.2f}%"
    )

    difference = weekly.value - one_time.value
    winner = weekly.method if difference > 0 else one_time.method
    print("-" * 42)
    print(f"Difference (weekly - one-time): {difference:,.2f}")
    print(f"Better strategy over this period: {winner}")

    grid_top = run_weekly_grid_search(close, one_time, top_n=10)
    if grid_top.empty:
        print("\nNo valid weekly strategy combinations found for grid search.")
        return

    print("\nTop 10 simple weekly strategy combinations (Mon-Fri, 08:00-16:00):")
    print(
        grid_top[
            [
                "buy_day",
                "buy_hour",
                "sell_day",
                "sell_hour",
                "trades",
                "total_return_pct",
                "edge_vs_buy_hold_pct",
            ]
        ].round(4)
    )


if __name__ == "__main__":
    main()