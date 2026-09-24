# Trade Oracle V1 Specification

## Mission

Trade Oracle is a Forex market-intelligence engine that understands the macro
environment, establishes directional bias, detects technical opportunities,
produces exact trade plans, monitors active ideas, explains market changes,
reviews its own forecasts, and improves through validated testing.

It does not hold funds or place broker trades.

## Instruments

### Core
- EURUSD
- GBPUSD
- USDJPY
- USDCHF
- XAUUSD

### Sixth-slot candidate pool
- USDCAD
- AUDUSD
- NZDUSD

All three candidates are initially evaluated under identical rules for roughly
1–2 weeks. The strongest validated candidate becomes the active sixth instrument.
The remaining candidates enter STASIS and continue to be monitored as fallback
candidates. Replacement requires evidence of sustained deterioration, not a
single losing streak.

## Timeframes

4H → 1H → 15M → 5M.

## Decision philosophy

Fundamentals have 51% influence and technicals have 49% influence.

Fundamentals establish directional authority. Technicals establish timing and
entry confirmation. Neither layer alone is an automatic trade trigger.

## Fundamental engine

The engine should evaluate, where relevant:
- central-bank policy and guidance
- interest-rate expectations
- inflation
- employment
- GDP
- PMI
- retail sales
- wages
- bond yields and rate differentials
- economic surprises
- major speeches
- material macro/geopolitical developments
- market expectations versus actual outcomes

Every fundamental conclusion requires a concise reason trail.

## Technical vocabulary

V1 starts with:
- BOS
- CHoCH
- liquidity sweeps
- previous day/week highs and lows
- session highs and lows
- displacement
- break and retest

These are features, not standalone trade triggers.

## Market regimes

At minimum:
- trending
- ranging
- high volatility
- low volatility
- unstable/news-driven

Performance must be measurable by regime.

## Decision outputs

- TRADE
- WATCH
- WAIT
- NO_TRADE
- BLOCKED

NO_TRADE is a valid and expected outcome.

## Signal requirements

Every actionable signal contains:
- instrument
- direction
- exact entry
- exact stop loss
- one take-profit
- risk distance
- reward distance
- R:R
- confidence score
- fundamental rationale
- technical rationale
- invalidation condition
- expiry
- breakeven instruction when applicable
- profit-protection instruction when applicable

Minimum R:R is 1:2.5.

Position sizing is left to the trader.

## Signal lifecycle

WATCH → ACTIVE → BREAKEVEN → TP_HIT

Alternative terminal states:
- INVALIDATED
- EXPIRED

## News mode

Before major scheduled or detected market-moving news, Oracle must evaluate
known open trades before switching into news mode.

For each open trade it should assess:
- original thesis
- current fundamental bias
- technical structure
- entry/current price
- SL/TP
- current R
- news relevance
- expected volatility

Possible advice:
- HOLD
- PROTECT
- REDUCE
- EXIT
- NO_CHANGE

News mode then evaluates:
Expected → Actual → Market reaction → Rate-expectation reaction → Technical
reaction.

After the event, the market is reassessed rather than blindly continuing the
pre-news thesis.

## Confidence

Confidence is an internal score, not a claimed win probability. It can only be
translated into calibrated probability after sufficient historical evidence.

## Performance protection

Oracle monitors its own signal performance, not a user's account.

If performance deteriorates:
PAUSE → INVESTIGATE → TEST → VALIDATE → RESUME.

Investigation should include pair, setup, regime, session, fundamentals,
news conditions, data quality, execution assumptions, and strategy degradation.

## Learning

Record both accepted and rejected candidate setups.

Learning evaluates:
- setup combinations
- pair behaviour
- sessions
- market regimes
- fundamental/technical alignment
- news conditions
- forecast accuracy
- strategy degradation

Production changes follow:
Discover → Hypothesis → Backtest → realistic costs/slippage → out-of-sample →
walk-forward → stress test → shadow test → deploy → monitor → rollback.

No unvalidated self-modification.

## Reporting

### Weekly outlook
Concise:
- macro environment
- currency biases
- major events
- important levels
- pairs to watch
- primary scenario
- alternative scenario
- invalidation
- major risks

### During week
- signals
- market updates
- news mode
- fundamental changes
- why-this-move explanations
- signal status

### Friday report
- forecast versus reality
- major moves and drivers
- signal performance
- missed opportunities
- failed assumptions
- learning discoveries
- early next-week watchlist

Occasional educational tips should be short and useful.

## Non-goals for foundation

- broker execution
- fund access
- automatic trading
- uncontrolled self-modification
- large indicator libraries
- mobile application
- complex UI before the engine exists
