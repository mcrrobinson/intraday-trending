# Intraday FTSE Analysis

This repo focuses on a lightweight analysis of FTSE hourly data.

## Python Files

- `weekday_analysis.py`
	- Downloads hourly FTSE data only if `ftse_hourly.csv` is missing; otherwise uses the local cached file.
	- Computes weekday averages for:
		- `start_of_day` (today open vs previous close)
		- `end_of_day` (today close vs today open)
		- `full_day` (today close vs previous close)
	- Prints weekday averages and confidence interval stats to the console.

- `strategy_comparison.py`
	- Downloads hourly FTSE data only if `ftse_hourly.csv` is missing; otherwise uses the local cached file.
	- Compares:
		- one-time buy-and-hold
		- weekly timed entry/exit strategy
	- Runs a weekly schedule grid search and prints the top combinations to the console.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install pandas yfinance
```

## Run

```bash
python weekday_analysis.py
python strategy_comparison.py
```

## Outputs

- `ftse_hourly.csv`: cached hourly FTSE input data from Yahoo Finance
- Console output from `weekday_analysis.py`: weekday average moves and 95% confidence intervals
- Console output from `strategy_comparison.py`: strategy comparison and top weekly timing combinations

## Notes

- Values are percentages, not decimal returns.
- Results are descriptive and period-dependent, not a guarantee of future performance.
