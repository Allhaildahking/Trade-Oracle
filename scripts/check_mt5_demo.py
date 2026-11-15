"""Read-only diagnostics for a logged-in Deriv MT5 demo terminal."""

from __future__ import annotations

import os
import sys

from app.core.config import settings
from app.execution.mt5_market_data import MetaTrader5MarketDataProvider


def main() -> int:
    provider = MetaTrader5MarketDataProvider()
    try:
        provider.connect(os.getenv("MT5_TERMINAL_PATH") or None)
        account = provider.get_account_snapshot()
        if not account.is_demo:
            print(
                "STOP: connected account is not a demo account. "
                "No checks beyond account info."
            )
            return 2

        symbol = settings.mt5_default_symbol
        spec = provider.get_symbol_spec(symbol)
        quote = provider.get_quote(symbol)

        print("DERIV MT5 DEMO CONNECTION: OK")
        print(f"Account equity: {account.equity} {account.currency}")
        print(f"Leverage: 1:{account.leverage}")
        print(f"Symbol: {spec.instrument}")
        print(f"Bid / Ask: {quote.bid} / {quote.ask}")
        print(f"Spread: {quote.ask - quote.bid}")
        print(f"Tick size: {spec.trade_tick_size}")
        print(f"Tick value (loss): {spec.trade_tick_value_loss} {account.currency}")
        print(f"Contract size: {spec.contract_size}")
        print(
            "Volume min / step / max: "
            f"{spec.volume_min} / {spec.volume_step} / {spec.volume_max}"
        )
        print("READ-ONLY CHECK COMPLETE. No orders were submitted.")
        return 0
    except Exception as exc:
        print(f"MT5 diagnostic failed: {exc}", file=sys.stderr)
        return 1
    finally:
        provider.close()


if __name__ == "__main__":
    raise SystemExit(main())
