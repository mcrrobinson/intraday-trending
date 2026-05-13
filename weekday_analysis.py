import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from pathlib import Path

WEEKDAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TICKER = "^GSPC"


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


CSV_PATH = csv_path_for_ticker(TICKER)
PLOT_PATH = Path(f"{TICKER}_trading_intervals.png")

CHANGE_TYPE_ORDER = ("start_of_day", "end_of_day", "full_day")
CHANGE_TYPE_COLORS = {
    "start_of_day": "tab:blue",
    "end_of_day": "tab:green",
    "full_day": "tab:red",
}

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

def load_close_prices(data: pd.DataFrame) -> pd.DataFrame:
    data = data.copy()
    data.index = pd.to_datetime(data.index, utc=True)

    if "Close" not in data.columns.get_level_values(0):
        raise ValueError("No Close price columns found in the data.")

    close_prices = data["Close"]
    if isinstance(close_prices, pd.Series):
        close_prices = close_prices.to_frame(name="Close")

    close_prices = close_prices.dropna(how="all")
    if close_prices.empty:
        raise ValueError("Close-price columns are empty.")

    return close_prices


def compute_session_changes(close_prices: pd.DataFrame, timezone: str) -> dict[str, pd.DataFrame]:
    localized = close_prices.tz_convert(timezone)
    day_index = pd.DatetimeIndex(localized.index).floor("D")
    daily_first = localized.groupby(day_index).first()
    daily_last = localized.groupby(day_index).last()

    return {
        "start_of_day": daily_first.divide(daily_last.shift(1)).sub(1.0).mul(100.0),
        "end_of_day": daily_last.divide(daily_first).sub(1.0).mul(100.0),
        "full_day": daily_last.divide(daily_last.shift(1)).sub(1.0).mul(100.0),
    }


def weekday_mean_series(change_df: pd.DataFrame) -> pd.Series:
    daily_avg = change_df.mean(axis=1).dropna()
    weekday_avg = daily_avg.groupby(pd.DatetimeIndex(daily_avg.index).day_name()).mean()
    return weekday_avg.reindex(WEEKDAY_ORDER).dropna()


def weekday_stats_frame(change_df: pd.DataFrame, change_type: str) -> pd.DataFrame:
    daily_avg = change_df.mean(axis=1).dropna().to_frame(name="change_pct")
    daily_avg["weekday"] = pd.DatetimeIndex(daily_avg.index).day_name()

    stats = (
        daily_avg.groupby("weekday")["change_pct"]
        .agg(n="count", mean_pct="mean", std_pct="std")
        .reindex(WEEKDAY_ORDER)
        .dropna(how="all")
    )
    stats["se_pct"] = stats["std_pct"] / stats["n"].pow(0.5)
    stats["ci95_low_pct"] = stats["mean_pct"] - 1.96 * stats["se_pct"]
    stats["ci95_high_pct"] = stats["mean_pct"] + 1.96 * stats["se_pct"]
    stats["change_type"] = change_type
    return stats.reset_index().rename(columns={"index": "weekday"})


def build_weekday_outputs(change_frames: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    weekday_export = pd.DataFrame(
        {
            "start_of_day_avg_pct": weekday_mean_series(change_frames["start_of_day"]),
            "end_of_day_avg_pct": weekday_mean_series(change_frames["end_of_day"]),
            "full_day_avg_pct": weekday_mean_series(change_frames["full_day"]),
        }
    )

    weekday_stats_export = pd.concat(
        [
            weekday_stats_frame(change_frames["start_of_day"], "start_of_day"),
            weekday_stats_frame(change_frames["end_of_day"], "end_of_day"),
            weekday_stats_frame(change_frames["full_day"], "full_day"),
        ],
        ignore_index=True,
    )
    return weekday_export, weekday_stats_export


def plot_confidence_intervals(weekday_stats_export: pd.DataFrame) -> pd.DataFrame:
    fig, axes = plt.subplots(3, 1, figsize=(10, 15), sharex=True)

    for idx, change_type in enumerate(CHANGE_TYPE_ORDER):
        axis = axes[idx]
        subset = weekday_stats_export[weekday_stats_export["change_type"] == change_type]
        if subset.empty:
            axis.set_visible(False)
            continue

        mean = subset["mean_pct"]
        low = subset["ci95_low_pct"]
        high = subset["ci95_high_pct"]

        axis.errorbar(
            subset["weekday"],
            mean,
            yerr=[mean - low, high - mean],
            fmt="o",
            capsize=5,
            color=CHANGE_TYPE_COLORS[change_type],
            label=change_type,
        )
        axis.axhline(0, color="black", linestyle="--", alpha=0.5)
        axis.set_title(f"95% CI for {change_type.replace('_', ' ').title()} Returns (%)")
        axis.set_ylabel("Avg Pct Change (%)")
        axis.legend()

    plt.tight_layout()
    plt.savefig(PLOT_PATH)
    plt.close(fig)

    return weekday_stats_export[
        (weekday_stats_export["ci95_low_pct"] > 0) | (weekday_stats_export["ci95_high_pct"] < 0)
    ]


def analyze_patterns() -> None:
    try:
        ticker_timezone = get_ticker_timezone(TICKER)
        hourly_data = load_or_download_hourly_data()
        close_prices = load_close_prices(hourly_data)
    except ValueError as exc:
        print(exc)
        return

    change_frames = compute_session_changes(close_prices, ticker_timezone)
    weekday_export, weekday_stats_export = build_weekday_outputs(change_frames)
    significant_results = plot_confidence_intervals(weekday_stats_export)

    print("Weekday average changes (%):")
    print(weekday_export.round(4))
    print("\n95% confidence intervals (%):")
    print(
        weekday_stats_export[
            ["change_type", "weekday", "n", "mean_pct", "ci95_low_pct", "ci95_high_pct"]
        ].round(4)
    )
    print(f"\nSaved CI plot: {PLOT_PATH}")
    print("\nStatistically significant results:")
    if significant_results.empty:
        print("None")
    else:
        print(
            significant_results[
                ["change_type", "weekday", "n", "mean_pct", "ci95_low_pct", "ci95_high_pct"]
            ].round(4)
        )


if __name__ == "__main__":
    analyze_patterns()
