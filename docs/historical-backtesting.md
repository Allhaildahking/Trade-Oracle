# Historical MT5 datasets

Trade Oracle can collect reusable historical datasets from a logged-in MetaTrader 5
terminal. Collection is read-only: it does not submit, modify, or close orders.

## Requirements

- Windows PC or Windows VPS with the broker's MT5 desktop terminal installed.
- The terminal is logged in to the intended broker account.
- Python environment with the project and optional MT5 dependency installed:
  `pip install -e ".[dev,mt5]"`
- The broker terminal has enough chart history available. Increase the terminal's
  **Max bars in chart** setting if the requested period is incomplete.

## Collect a dataset

Use timezone-aware ISO 8601 dates. UTC is recommended so datasets from different
brokers and symbols can be compared consistently.

```powershell
python scripts/collect_mt5_history.py `
  --symbol XAUUSDmicro `
  --start "2026-01-01T00:00:00+00:00" `
  --end "2026-06-01T00:00:00+00:00" `
  --output "data/historical/XAUUSDmicro-2026H1.json"
```

Use the exact symbol name shown by the broker. Standard `XAUUSD`, micro gold
symbols, forex pairs, indices, and other instruments must use their own broker
symbol metadata; do not assume contract sizes or tick values are interchangeable.

The collector downloads completed 4H, 1H, 15M, and 5M candles in bounded chunks.
It also requests historical MT5 quote ticks and records a bid/ask snapshot for
each 5M candle where one is available. By default, it refuses to save a dataset
with less than 95% 5M spread coverage. The threshold can be changed explicitly
with `--min-spread-coverage`.

The JSON file stores exact decimal strings, candle timestamps, broker symbol
specification, and a quality summary. It can be loaded later with
`load_historical_dataset(path)`, so backtests do not need to download the same
market history repeatedly.

## Important limitations

- The stored spread is a bar-level quote snapshot, not tick-by-tick execution
  replay. It does not reconstruct the exact bid/ask path inside each candle.
- Historical candle and quote availability depends on the broker and MT5
  terminal's retained/downloaded history.
- Commission, swap, slippage, and execution behavior still need broker-specific
  calibration. A dataset alone does not validate profitability.
- This collector does not create historical news, fundamentals, or economic
  calendar snapshots. Those must be supplied separately with point-in-time
  timestamps before the Oracle backtester can claim a fundamentals-aware
  historical result.
- A successful collection means the data passed structural and spread-coverage
  checks. It does not mean a strategy passed backtesting or is ready for demo
  execution.
