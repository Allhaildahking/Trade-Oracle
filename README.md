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

Set `MT5_DEFAULT_SYMBOL=XAUUSDmicro` and `MT5_DEFAULT_RISK_PERCENT=1.0` for the conservative standalone sizing default. The experimental execution policy separately caps risk at 10% per trade: 10% below USD 30 equity and 5% from USD 30 upward, with daily realized-loss cutoffs of 20% and 10% respectively. Position sizing rounds volume down and rejects a trade if the broker minimum would exceed the risk budget. These percentages are aggressive and are not a recommendation. Confirm actual symbol tick value, tick size, contract size, and volume limits from the connected Deriv demo terminal; test fixtures are not broker specifications.

## Boundaries

Trade Oracle is a development project. It does not provide guaranteed outcomes, execute orders, or replace independent risk management. Execution remains disabled by default. Any future broker order integration requires extensive backtesting, demo forward testing, reconciliation, safeguards, and explicit approval.

---

Built by [Allhaildahking](https://github.com/Allhaildahking).
