# Intraday FTSE Analysis

This repo is a lightweight set of scripts for exploring intraday/hourly index
data, looking for weekday return patterns and testing simple weekly timing
strategies. It downloads hourly data from Yahoo Finance (via `yfinance`), caches
it to CSV, and prints its results to the console (one script also saves a plot).

> Note on tickers: the scripts do not all use the same index. `weekday_analysis.py`
> and `portfolio_performance.py` analyse the S&P 500 (`^GSPC`), while
> `strategy_comparison.py` and `measure.py` use the FTSE 100 (`^FTSE`). Each
> ticker is cached to its own CSV (`gspc_hourly.csv`, `ftse_hourly.csv`).

## Scripts / modules

### Analysis

- `weekday_analysis.py`
	- The core analysis script. Loads hourly data for `^GSPC` from
	  `gspc_hourly.csv`, downloading it (730 days) if the cache is missing.
	- Converts timestamps to the exchange timezone and computes per-weekday
	  average percentage moves for three sessions:
		- `start_of_day` (today's first price vs previous day's last price)
		- `end_of_day` (today's last price vs today's first price)
		- `full_day` (today's last price vs previous day's last price)
	- Reports mean, standard deviation, standard error and 95% confidence
	  intervals per weekday, and flags weekdays whose CI excludes zero as
	  statistically significant.
	- Saves a three-panel confidence-interval plot to
	  `^GSPC_trading_intervals.png` and prints the tables to the console.
	- Main entry point: `analyze_patterns()`.

- `display.py`
	- Thin entry-point wrapper that imports and runs
	  `analyze_patterns()` from `weekday_analysis.py`. Running it is equivalent
	  to running `weekday_analysis.py` directly.

### Backtests

- `strategy_comparison.py`
	- Backtest for `^FTSE`. Loads/downloads hourly FTSE data into
	  `ftse_hourly.csv`.
	- Compares, with £10,000 of initial capital over a fixed window
	  (buy 2023-05-12, evaluate 2026-03-27):
		- a one-time buy-and-hold, and
		- a tuned weekly timing rule (buy Monday 10:00, sell Friday 08:00,
		  London time).
	- Then runs a brute-force grid search over every buy/sell weekday+hour
	  combination (Mon-Fri, 08:00-16:00, keeping only schedules with at least
	  30 completed trades) and prints the top 10 ranked by edge over
	  buy-and-hold.

- `portfolio_performance.py`
	- Similar backtest for `^GSPC`, using $10,000 of initial capital.
	- Reads close prices from `gspc_hourly.csv` via `load_close_series()`; the
	  CSV must already exist (when run as a script, `load_or_download_hourly_data()`
	  will download it first if needed). Uses the ticker's exchange timezone,
	  looked up from Yahoo Finance.
	- Compares a one-time buy-and-hold against a weekly timing rule (buy
	  Thursday 10:00, sell Monday 10:00, exchange-local time) and prints the
	  resulting values, returns and their difference.

### Data fetching

- `measure.py`
	- Minimal data fetcher. Downloads `^FTSE` hourly data (730 days) to
	  `ftse_hourly.csv` only if that file does not already exist. Performs no
	  analysis; useful for pre-populating the FTSE cache.

### Placeholders

- `controller.py`, `find_gap.py`, `debug_trades.py`
	- Currently empty placeholder files with no code.

## How they fit together

1. The analysis and backtest scripts each lazily download and cache their own
   hourly CSV on first run, so no separate data step is strictly required.
   `measure.py` can be run up front to pre-fetch the FTSE cache.
2. `weekday_analysis.py` (or its wrapper `display.py`) produces the descriptive
   weekday-pattern statistics and the CI plot.
3. `strategy_comparison.py` and `portfolio_performance.py` turn the timing idea
   into simple weekly buy/sell backtests and compare them against buy-and-hold.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install pandas yfinance matplotlib
```

(`matplotlib` is only needed for `weekday_analysis.py` / `display.py`.)

## Run

```bash
python weekday_analysis.py        # or: python display.py
python strategy_comparison.py
python measure.py                 # pre-fetch ftse_hourly.csv (optional)
python portfolio_performance.py
```

## Outputs

- `gspc_hourly.csv`: cached hourly S&P 500 data (used by `weekday_analysis.py`
  and `portfolio_performance.py`).
- `ftse_hourly.csv`: cached hourly FTSE data (used by `strategy_comparison.py`
  and `measure.py`).
- `^GSPC_trading_intervals.png`: three-panel 95% confidence-interval plot from
  `weekday_analysis.py`.
- Console output: weekday averages and 95% confidence intervals
  (`weekday_analysis.py`); strategy comparisons and top weekly timing
  combinations (`strategy_comparison.py`, `portfolio_performance.py`).

CSV and PNG artifacts are gitignored and regenerated on demand.

## Notes

- Percentage change values are percentages, not decimal returns.
- Results are descriptive and period-dependent, not a guarantee of future
  performance.
