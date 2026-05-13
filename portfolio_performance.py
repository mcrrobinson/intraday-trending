from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast
import yfinance as yf

import pandas as pd

def csv_path_for_ticker(ticker: str) -> Path:
    safe_ticker = "".join(ch.lower() if ch.isalnum() else "_" for ch in ticker).strip("_")
    return Path(f"{safe_ticker}_hourly.csv")


def get_ticker_timezone(ticker: str) -> str:
    ticker_obj = yf.Ticker(ticker)
    timezone = None

    try:
        fast_info = getattr(ticker_obj, "fast_info", None)
        if fast_info is not None:
            timezone = fast_info.get("timezone")
    except Exception:
        timezone = None

    if not timezone:
        try:
            info = getattr(ticker_obj, "info", {})
            timezone = info.get("exchangeTimezoneName")
        except Exception:
            timezone = None

    if not timezone:
        raise ValueError(f"Could not determine timezone for ticker {ticker}.")

    return str(timezone)


TICKER = "^GSPC"
CSV_PATH = csv_path_for_ticker(TICKER)
INITIAL_CAPITAL = 10_000.0

def load_or_download_hourly_data() -> pd.DataFrame:
    if CSV_PATH.exists():
        data = pd.read_csv(CSV_PATH, header=[0, 1], index_col=0)
    else:
        data = yf.download(TICKER, interval="1h", period="730d")
        if data is None:
            raise ValueError("Failed to download data. Please check your internet connection and try again.")
        if data.empty:
            raise ValueError("Downloaded data is empty.")
        data.to_csv(CSV_PATH)

    return data

@dataclass
class PortfolioResult:
    strategy: str
    final_value: float
    total_return_pct: float
    trades: int


def load_close_series(csv_path: Path = CSV_PATH) -> pd.Series:
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Missing {csv_path}. Run an existing downloader script first or add the CSV to this folder."
        )

    data = pd.read_csv(csv_path, header=[0, 1], index_col=0)
    data.index = pd.to_datetime(data.index, utc=True)

    close_prices = data["Close"]
    if isinstance(close_prices, pd.Series):
        close = close_prices.astype(float)
    else:
        close = close_prices.iloc[:, 0].astype(float)

    return close.dropna().sort_index()


def first_price_on_or_after(series: pd.Series, when: pd.Timestamp) -> tuple[pd.Timestamp, float]:
    filtered = series.loc[series.index >= when]
    if filtered.empty:
        raise ValueError(f"No prices available on or after {when}.")
    ts = filtered.index[0]
    return ts, float(filtered.iloc[0])


def simulate_one_time_buy_hold(close: pd.Series, initial_capital: float) -> PortfolioResult:
    buy_ts = close.index[0]
    buy_price = float(close.iloc[0])
    end_ts = close.index[-1]
    end_price = float(close.iloc[-1])

    units = initial_capital / buy_price
    final_value = units * end_price
    total_return_pct = (final_value / initial_capital - 1.0) * 100.0

    print("One-time portfolio")
    print(f"  Buy timestamp (UTC): {buy_ts}")
    print(f"  Buy price: {buy_price:.2f}")
    print(f"  Final timestamp (UTC): {end_ts}")
    print(f"  Final price: {end_price:.2f}")

    return PortfolioResult(
        strategy="Buy fixed amount on first timestamp and hold",
        final_value=final_value,
        total_return_pct=total_return_pct,
        trades=1,
    )


def simulate_friday_to_wednesday(
    close: pd.Series, initial_capital: float, timezone: str
) -> PortfolioResult:
    local = close.tz_convert(timezone)
    idx = pd.DatetimeIndex(local.index)

    buy_points = local.loc[(idx.dayofweek == 3) & (idx.hour == 10)]  # Thursday 10:00
    sell_points = local.loc[(idx.dayofweek == 0) & (idx.hour == 10)]  # Monday 11:00

    if buy_points.empty:
        raise ValueError("No Friday 15:00 prices found in the dataset.")
    if sell_points.empty:
        raise ValueError("No Wednesday 11:00 prices found in the dataset.")

    capital = initial_capital
    trades = 0
    sell_index = pd.DatetimeIndex(sell_points.index)
    next_sell_pos = 0

    for buy_ts, buy_price in buy_points.items():
        buy_ts = cast(pd.Timestamp, buy_ts)
        search_start = max(next_sell_pos, 0)
        relative_pos = int(sell_index[search_start:].searchsorted(buy_ts, side="right"))
        sell_pos = search_start + relative_pos

        if sell_pos >= len(sell_index):
            break

        sell_ts = sell_index[sell_pos]
        sell_price = float(sell_points.iloc[sell_pos])
        capital *= sell_price / float(buy_price)
        trades += 1

        next_sell_pos = sell_pos + 1

    total_return_pct = (capital / initial_capital - 1.0) * 100.0

    print("Timed portfolio")
    print(f"  Rule: buy Friday 15:00, sell Wednesday 11:00 ({timezone} time)")
    print(f"  Completed trades: {trades}")

    return PortfolioResult(
        strategy="Buy Friday 3pm, sell Wednesday 11am (weekly)",
        final_value=capital,
        total_return_pct=total_return_pct,
        trades=trades,
    )


def main() -> None:
    ticker_timezone = get_ticker_timezone(TICKER)
    close = load_close_series()

    one_time = simulate_one_time_buy_hold(close, INITIAL_CAPITAL)
    timed = simulate_friday_to_wednesday(close, INITIAL_CAPITAL, ticker_timezone)

    print("\nPortfolio performance comparison")
    print("=" * 45)
    print(
        f"{one_time.strategy:45s} "
        f"value={one_time.final_value:10.2f} return={one_time.total_return_pct:8.2f}%"
    )
    print(
        f"{timed.strategy:45s} "
        f"value={timed.final_value:10.2f} return={timed.total_return_pct:8.2f}%"
    )
    print("-" * 45)
    print(f"Difference (timed - one-time): {timed.final_value - one_time.final_value:,.2f}")


if __name__ == "__main__":
    load_or_download_hourly_data()
    main()