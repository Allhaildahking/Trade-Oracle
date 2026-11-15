# Trade Oracle

**A Forex market-intelligence engine built around structured, auditable trade analysis.**

Trade Oracle evaluates market conditions and produces clearly defined trade opportunities. Broker execution remains experimental, disabled by default, and restricted to demo-account development.

## Project status

**Status: Analysis foundation + experimental Deriv MT5 integration + draft execution safeguards**

The `feat/deriv-mt5-market-data` work adds a read-only MT5 adapter, broker symbol specifications, account-equity access, and deterministic risk-based position sizing. The `feat/mt5-autonomous-execution` work adds a fail-closed approval gate. Neither branch has been validated against a connected Deriv demo terminal. The approval gate does not send orders or manage positions. Do not treat this project as a live trading system.

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

1. Validate the analysis pipeline and its deterministic inputs/outputs.
2. Build a realistic historical backtester that reuses the existing analysis pipeline.
3. Add out-of-sample and demo forward testing with execution-cost and failure simulation.
4. Validate broker data and execution safeguards on a Deriv demo terminal.
5. Consider live execution only after documented validation and explicit approval.

These are development priorities, not claims that the features are already complete.

## Deriv MT5 development setup

The MT5 Python package is an optional Windows-only dependency. On the Windows terminal machine, install the project and development tools with:

```powershell
py -3.13 -m venv .venv
.venv\\Scripts\\Activate.ps1
python -m pip install -e ".[dev,mt5]"
python scripts/check_mt5_demo.py
```

The diagnostic script refuses to continue if the connected account is not a demo account. It prints account equity/currency and broker-reported symbol values without placing orders.

The execution and historical backtest sizing policy uses a tiered per-trade risk rule: accounts with equity up to and including USD 15 have a maximum cash-loss budget of USD 3.50 (capped by available equity); accounts above USD 15 use 10% of current equity. Position sizing rounds volume down and rejects a trade if the broker minimum would exceed the applicable risk budget. The USD 3.50 amount is a hard ceiling for the lower balance tier, not a recommended amount to risk on every trade. Daily realized-loss protection is separate: 20% below USD 30 equity and 10% from USD 30 upward. Confirm actual symbol tick value, tick size, contract size, and volume limits from the connected Deriv demo terminal; test fixtures are not broker specifications.

## Boundaries

Trade Oracle is a development project. It does not provide guaranteed outcomes, execute orders, or replace independent risk management. Execution remains disabled by default. Any future broker order integration requires extensive backtesting, demo forward testing, reconciliation, safeguards, and explicit approval.

---

Built by [Allhaildahking](https://github.com/Allhaildahking).
