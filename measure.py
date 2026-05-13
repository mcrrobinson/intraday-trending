from pathlib import Path
import yfinance as yf

TICKERS = "^FTSE"
CSV_PATH = Path("ftse_hourly.csv")
def ensure_hourly_data() -> None:
	if CSV_PATH.exists():
		return
	data = yf.download(TICKERS, interval="1h", period="730d")
	data.to_csv(CSV_PATH)
 
def main():
    ensure_hourly_data()

if __name__ == "__main__":
    main()
    