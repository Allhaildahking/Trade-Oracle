# Trade Oracle data providers

Trade Oracle uses provider adapters so analysis never depends directly on one vendor.

## Required now

1. Twelve Data: 4H / 1H / 15M / 5M price candles and quotes.
   Environment variable: TWELVE_DATA_API_KEY

2. Trading Economics: economic calendar, actual / forecast / previous values,
   importance and release timing.
   Environment variable: TRADING_ECONOMICS_API_KEY

3. Alpha Vantage: market news and forex-related sentiment.
   Environment variable: ALPHA_VANTAGE_API_KEY

## Later

TELEGRAM_BOT_TOKEN is only needed when the intelligence engine is ready to send
validated outputs. Telegram is not part of the analysis engine.

## Security

Never commit real API keys. Use environment variables or GitHub Actions secrets.

## Architecture

Provider -> canonical model -> validation -> repository -> analysis.

A provider can therefore be replaced without rewriting technical analysis,
fundamental analysis, backtesting, or reporting.
