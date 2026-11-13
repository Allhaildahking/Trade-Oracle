"""Read-only MetaTrader 5 market-data adapter.

This adapter deliberately does not submit, modify, or close orders. Broker
execution will be added behind a separate, risk-gated interface.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from importlib import import_module
from typing import Any

from app.data.base import MarketDataProvider
from app.models.account import AccountSnapshot
from app.models.market import Candle, Quote, Timeframe
from app.models.symbol import SymbolSpec

_TIMEFRAME_MINUTES: dict[Timeframe, int] = {
    "4H": 240,
    "1H": 60,
    "15M": 15,
    "5M": 5,
}


class MetaTrader5MarketDataProvider(MarketDataProvider):
    """Fetch completed candles and current bid/ask quotes from an MT5 terminal."""

    name = "metatrader5"

    def __init__(self, mt5_module: Any | None = None) -> None:
        # Lazy import keeps the core analysis package usable away from Windows.
        self._mt5 = mt5_module
        self._connected = False

    def connect(self, terminal_path: str | None = None) -> None:
        """Connect to the already-installed and logged-in MT5 desktop terminal."""
        if self._mt5 is None:
            try:
                self._mt5 = import_module("MetaTrader5")
            except ImportError as exc:
                raise RuntimeError(
                    "MetaTrader5 package is not installed in this Python environment"
                ) from exc

        initialized = (
            self._mt5.initialize(path=terminal_path)
            if terminal_path
            else self._mt5.initialize()
        )
        if not initialized:
            error = self._mt5.last_error()
            raise RuntimeError(f"Could not initialize MetaTrader 5: {error}")
        self._connected = True

    def close(self) -> None:
        """Release the terminal connection."""
        if self._mt5 is not None and self._connected:
            self._mt5.shutdown()
        self._connected = False

    def get_account_snapshot(self) -> AccountSnapshot:
        """Read non-sensitive account details from the connected terminal."""
        self._require_connection()
        account = self._mt5.account_info()
        if account is None:
            raise RuntimeError(
                f"MT5 account information unavailable: {self._mt5.last_error()}"
            )
        equity = _decimal(account.equity)
        if equity <= 0:
            raise RuntimeError("MT5 account equity must be positive")
        demo_mode = getattr(self._mt5, "ACCOUNT_TRADE_MODE_DEMO", 0)
        return AccountSnapshot(
            equity=equity,
            currency=str(account.currency),
            is_demo=account.trade_mode == demo_mode,
            leverage=int(account.leverage),
        )

    def get_account_equity(self) -> Decimal:
        """Read account equity from the connected terminal."""
        return self.get_account_snapshot().equity

    def get_symbol_spec(self, instrument: str) -> SymbolSpec:
        """Return broker-reported contract, tick economics, and volume limits."""
        self._require_connection()
        self._ensure_symbol(instrument)
        info = self._mt5.symbol_info(instrument)
        if info is None:
            raise RuntimeError(f"MT5 symbol metadata unavailable for {instrument}")
        tick_value_loss = getattr(info, "trade_tick_value_loss", 0) or getattr(
            info, "trade_tick_value", 0
        )
        return SymbolSpec(
            instrument=instrument,
            trade_tick_size=_decimal(info.trade_tick_size),
            trade_tick_value_loss=_decimal(tick_value_loss),
            volume_min=_decimal(info.volume_min),
            volume_max=_decimal(info.volume_max),
            volume_step=_decimal(info.volume_step),
            contract_size=_decimal(info.trade_contract_size),
        )

    def get_quote(self, instrument: str) -> Quote:
        self._require_connection()
        self._ensure_symbol(instrument)
        tick = self._mt5.symbol_info_tick(instrument)
        if tick is None:
            raise RuntimeError(f"No current tick available for {instrument}")

        bid = _decimal(tick.bid)
        ask = _decimal(tick.ask)
        if bid <= 0 or ask < bid:
            raise RuntimeError(f"Invalid bid/ask returned for {instrument}")

        timestamp = _tick_timestamp(tick)
        return Quote(
            instrument=instrument,
            timestamp=timestamp,
            bid=bid,
            ask=ask,
            mid=(bid + ask) / Decimal("2"),
            source=self.name,
        )

    def get_candles(
        self,
        instrument: str,
        timeframe: Timeframe,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 500,
    ) -> list[Candle]:
        self._require_connection()
        if timeframe not in _TIMEFRAME_MINUTES:
            raise ValueError(f"Unsupported Trade Oracle timeframe: {timeframe}")
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if end is not None and start is None:
            raise ValueError("start is required when end is supplied")
        if start is not None and start.tzinfo is None:
            raise ValueError("start must be timezone-aware")
        if end is not None and end.tzinfo is None:
            raise ValueError("end must be timezone-aware")

        self._ensure_symbol(instrument)
        mt5_timeframe = getattr(self._mt5, f"TIMEFRAME_{timeframe}")
        if start is not None and end is not None:
            rates = self._mt5.copy_rates_range(
                instrument, mt5_timeframe, start, end
            )
        elif start is not None:
            rates = self._mt5.copy_rates_from(
                instrument, mt5_timeframe, start, limit
            )
        else:
            # Position zero is the still-forming bar. Start at one so Oracle
            # only analyses closed candles.
            rates = self._mt5.copy_rates_from_pos(
                instrument, mt5_timeframe, 1, limit
            )

        if rates is None:
            raise RuntimeError(
                f"MT5 candle request failed for {instrument} {timeframe}: "
                f"{self._mt5.last_error()}"
            )

        interval = timedelta(minutes=_TIMEFRAME_MINUTES[timeframe])
        now = datetime.now(UTC)
        candles = [
            Candle(
                instrument=instrument,
                timeframe=timeframe,
                timestamp=datetime.fromtimestamp(int(_field(row, "time")), UTC),
                open=_decimal(_field(row, "open")),
                high=_decimal(_field(row, "high")),
                low=_decimal(_field(row, "low")),
                close=_decimal(_field(row, "close")),
                volume=_decimal(_field(row, "tick_volume")),
                source=self.name,
                is_complete=(
                    datetime.fromtimestamp(int(_field(row, "time")), UTC)
                    + interval
                    <= now
                ),
            )
            for row in rates
        ]
        return candles[-limit:]

    def get_candles_with_spread(
        self,
        instrument: str,
        timeframe: Timeframe,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 500,
    ) -> list[Candle]:
        """Fetch candles enriched with the first valid bid/ask tick in each bar.

        MT5 OHLC rates do not contain historical bid/ask. This method uses
        historical quote ticks and stores the first valid quote in each candle.
        It is a bar-open spread snapshot, not tick-by-tick execution replay.
        """
        self._require_connection()
        candles = self.get_candles(
            instrument, timeframe, start=start, end=end, limit=limit
        )
        if not candles:
            return []

        copy_ticks_range = getattr(self._mt5, "copy_ticks_range", None)
        tick_flag = getattr(self._mt5, "COPY_TICKS_INFO", None)
        if copy_ticks_range is None or tick_flag is None:
            raise RuntimeError("MT5 terminal does not support historical quote-tick retrieval")

        interval = timedelta(minutes=_TIMEFRAME_MINUTES[timeframe])
        first = candles[0].timestamp
        last = candles[-1].timestamp + interval
        ticks = copy_ticks_range(instrument, first, last, tick_flag)
        if ticks is None:
            raise RuntimeError(
                f"MT5 historical tick request failed for {instrument}: "
                f"{self._mt5.last_error()}"
            )

        by_time: list[tuple[datetime, Decimal, Decimal]] = []
        for tick in ticks:
            bid = _decimal(_field(tick, "bid"))
            ask = _decimal(_field(tick, "ask"))
            if bid <= 0 or ask < bid:
                continue
            time_msc = _field(tick, "time_msc")
            timestamp = (
                datetime.fromtimestamp(int(time_msc) / 1000, UTC)
                if time_msc
                else datetime.fromtimestamp(int(_field(tick, "time")), UTC)
            )
            by_time.append((timestamp, bid, ask))
        by_time.sort(key=lambda item: item[0])

        enriched: list[Candle] = []
        tick_index = 0
        for candle in candles:
            bar_end = candle.timestamp + interval
            while tick_index < len(by_time) and by_time[tick_index][0] < candle.timestamp:
                tick_index += 1
            cursor = tick_index
            quote = None
            while cursor < len(by_time) and by_time[cursor][0] < bar_end:
                quote = by_time[cursor]
                break
            if quote is not None:
                enriched.append(
                    Candle(
                        instrument=candle.instrument,
                        timeframe=candle.timeframe,
                        timestamp=candle.timestamp,
                        open=candle.open,
                        high=candle.high,
                        low=candle.low,
                        close=candle.close,
                        volume=candle.volume,
                        bid=quote[1],
                        ask=quote[2],
                        source=candle.source,
                        is_complete=candle.is_complete,
                    )
                )
            else:
                enriched.append(candle)
        return enriched

    def _ensure_symbol(self, instrument: str) -> None:
        info = self._mt5.symbol_info(instrument)
        if info is None:
            raise ValueError(f"MT5 symbol does not exist: {instrument}")
        if not info.visible and not self._mt5.symbol_select(instrument, True):
            raise RuntimeError(f"Could not enable {instrument} in Market Watch")

    def _require_connection(self) -> None:
        if not self._connected:
            raise RuntimeError("MetaTrader 5 provider is not connected")


def _field(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value[name]
    return value[name]


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _tick_timestamp(tick: Any) -> datetime:
    time_msc = getattr(tick, "time_msc", 0)
    if time_msc:
        return datetime.fromtimestamp(time_msc / 1000, UTC)
    return datetime.fromtimestamp(tick.time, UTC)
