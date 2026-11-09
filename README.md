# Trade Oracle

**A Forex market-intelligence engine built around structured, auditable trade analysis.**

Trade Oracle is designed to evaluate market conditions and produce clearly defined trade opportunities. It does not connect to a broker, place orders, or manage live positions.

## Project status

**Status: Foundation phase**

The analytical foundation is being developed. Production market-data providers and broker integrations are not connected, and the project should not be treated as a live signal service.

## V1 scope

| Area | Current design |
|---|---|
| Core instruments | EURUSD, GBPUSD, USDJPY, USDCHF, XAUUSD |
| Sixth-slot candidates | USDCAD, AUDUSD, NZDUSD |
| Timeframe sequence | 4H → 1H → 15M → 5M |
| Fundamental influence | 51% |
| Technical influence | 49% |
| Minimum risk-to-reward | 1:2.5 |
| Take-profit | One TP per signal |
| Trade levels | Exact entry and stop-loss |
| News mode | Open-trade advisory before major events |

### Instrument selection

The three sixth-slot candidates are evaluated under the same rules over a 1–2 week observation period. The strongest validated candidate is intended to take the sixth active slot. The remaining candidates stay in reserve.

### Signal lifecycle

`WATCH → ACTIVE → BREAKEVEN → TP HIT / INVALIDATED / EXPIRED`

A no-trade result is valid. The system should not force a setup when market conditions do not meet its criteria.

## Analytical principles

- **Top-down analysis:** use the higher timeframes to establish context before lower-timeframe confirmation and entry evaluation.
- **Evidence before changes:** strategy adjustments should follow documented validation, not isolated wins or losses.
- **Auditable decisions:** analytical outputs should be testable, versioned, and reproducible.
- **Risk before activity:** enforce the minimum risk-to-reward requirement and allow the system to stand aside.
- **News awareness:** account for major scheduled events and communicate relevant risk to an open-trade workflow.

## Development priorities

1. Build and test the core analysis pipeline.
2. Define consistent data structures for market context and trade candidates.
3. Validate the instrument-selection process against recorded evidence.
4. Add reliable market-data providers.
5. Build reporting and notification layers after the analytical foundation is stable.

These are development priorities, not claims that the features are already complete.

## Boundaries

Trade Oracle is currently a development project. It does not provide guaranteed outcomes, execute trades, or replace independent risk management. Any future live integration will require separate testing, safeguards, and explicit controls.

---

Built by [Allhaildahking](https://github.com/Allhaildahking).
