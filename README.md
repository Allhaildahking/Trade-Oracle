# Trade Oracle

Trade Oracle is a Forex market-intelligence engine that generates actionable trade opportunities without broker access or automatic trade execution.

## V1 scope

- Core instruments: EURUSD, GBPUSD, USDJPY, USDCHF, XAUUSD
- Sixth-slot candidates: USDCAD, AUDUSD, NZDUSD
- Candidate evaluation: all three are monitored/traded under the same rules for 1–2 weeks, then the strongest validated candidate occupies the sixth active slot. The others remain in stasis as fallback candidates.
- Timeframes: 4H → 1H → 15M → 5M
- Fundamental influence: 51%
- Technical influence: 49%
- Minimum R:R: 1:2.5
- One TP per signal
- Exact entry and SL
- Signal lifecycle: WATCH → ACTIVE → BREAKEVEN → TP HIT / INVALIDATED / EXPIRED
- News mode includes an open-trade advisory before major events
- No-trade output is a valid and expected result
- Learning follows evidence-based validation before strategy changes are deployed

## Development principle

Build the intelligence engine before presentation or notification layers. Every analytical decision should be auditable, testable, versioned, and reproducible.

## Status

Foundation phase. No live trading, broker execution, or production data providers are connected yet.
