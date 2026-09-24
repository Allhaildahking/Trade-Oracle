# Trade Oracle data providers

Trade Oracle uses provider adapters so analysis never depends directly on one vendor.

## Active providers

1. Twelve Data: 4H / 1H / 15M / 5M price candles and quotes.
   Environment variable: `TWELVE_DATA_API_KEY`

2. Alpha Vantage: market news and forex-related sentiment.
   Environment variable: `ALPHA_VANTAGE_API_KEY`

3. FRED: historical macroeconomic observations.
   Environment variable: `FRED_API_KEY`

4. Groq: LLM reasoning, explanations, summaries, and report drafting after
   deterministic evidence has been calculated.
   Environment variable: `GROQ_API_KEY`

## Optional

Trading Economics can provide an economic calendar with actual / forecast /
previous values, importance, and release timing, but it is intentionally
optional while Trade Oracle evaluates lower-cost calendar alternatives.

Environment variable: `TRADING_ECONOMICS_API_KEY`

## Still needed

The core engine still needs a reliable economic-calendar source for scheduled
events, release times, forecasts/consensus, previous values, actual values,
and importance. Do not hard-code a vendor into the analysis layer.

## Architecture

Provider -> canonical model -> validation -> repository -> analysis.

The deterministic engine owns trading decisions and risk rules. Groq is an
interpretation layer and must not override hard risk constraints.

## Security

Never commit real API keys. Use environment variables or GitHub Actions secrets.
