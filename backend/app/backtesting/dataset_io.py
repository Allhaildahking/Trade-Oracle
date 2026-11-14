"""JSON persistence for reusable, reproducible historical MT5 datasets."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
from typing import Any

from app.backtesting.mt5_dataset import DatasetQuality, HistoricalDataset
from app.models.market import Candle
from app.models.symbol import SymbolSpec

_SCHEMA_VERSION = 1


def save_historical_dataset(dataset: HistoricalDataset, path: str | Path) -> Path:
    """Persist a collected dataset without converting financial values to floats."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": _SCHEMA_VERSION,
        "instrument": dataset.instrument,
        "start": dataset.start.isoformat(),
        "end": dataset.end.isoformat(),
        "symbol_spec": {
            "instrument": dataset.symbol_spec.instrument,
            "trade_tick_size": str(dataset.symbol_spec.trade_tick_size),
            "trade_tick_value_loss": str(dataset.symbol_spec.trade_tick_value_loss),
            "volume_min": str(dataset.symbol_spec.volume_min),
            "volume_max": str(dataset.symbol_spec.volume_max),
            "volume_step": str(dataset.symbol_spec.volume_step),
            "contract_size": str(dataset.symbol_spec.contract_size),
        },
        "candles": {
            timeframe: [_candle_to_dict(candle) for candle in rows]
            for timeframe, rows in dataset.candles.items()
        },
        "quality": {
            "candle_counts": [list(item) for item in dataset.quality.candle_counts],
            "five_minute_spread_coverage_percent": str(
                dataset.quality.five_minute_spread_coverage_percent
            ),
            "missing_five_minute_spreads": dataset.quality.missing_five_minute_spreads,
            "first_five_minute_bar": dataset.quality.first_five_minute_bar.isoformat(),
            "last_five_minute_bar": dataset.quality.last_five_minute_bar.isoformat(),
        },
    }
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return destination


def load_historical_dataset(path: str | Path) -> HistoricalDataset:
    """Load a saved dataset and reconstruct exact Decimal/timezone values."""
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != _SCHEMA_VERSION:
        raise ValueError("unsupported historical dataset schema version")

    spec_data = payload["symbol_spec"]
    symbol_spec = SymbolSpec(
        instrument=spec_data["instrument"],
        trade_tick_size=Decimal(spec_data["trade_tick_size"]),
        trade_tick_value_loss=Decimal(spec_data["trade_tick_value_loss"]),
        volume_min=Decimal(spec_data["volume_min"]),
        volume_max=Decimal(spec_data["volume_max"]),
        volume_step=Decimal(spec_data["volume_step"]),
        contract_size=Decimal(spec_data["contract_size"]),
    )
    candles = {
        timeframe: tuple(_candle_from_dict(item) for item in rows)
        for timeframe, rows in payload["candles"].items()
    }
    quality_data = payload["quality"]
    quality = DatasetQuality(
        candle_counts=tuple(
            (str(item[0]), int(item[1])) for item in quality_data["candle_counts"]
        ),
        five_minute_spread_coverage_percent=Decimal(
            quality_data["five_minute_spread_coverage_percent"]
        ),
        missing_five_minute_spreads=int(
            quality_data["missing_five_minute_spreads"]
        ),
        first_five_minute_bar=datetime.fromisoformat(
            quality_data["first_five_minute_bar"]
        ),
        last_five_minute_bar=datetime.fromisoformat(
            quality_data["last_five_minute_bar"]
        ),
    )
    dataset = HistoricalDataset(
        instrument=payload["instrument"],
        start=datetime.fromisoformat(payload["start"]),
        end=datetime.fromisoformat(payload["end"]),
        symbol_spec=symbol_spec,
        candles=candles,
        quality=quality,
    )
    if symbol_spec.instrument != dataset.instrument:
        raise ValueError("saved symbol specification does not match dataset instrument")
    return dataset


def _candle_to_dict(candle: Candle) -> dict[str, Any]:
    return {
        "instrument": candle.instrument,
        "timeframe": candle.timeframe,
        "timestamp": candle.timestamp.isoformat(),
        "open": str(candle.open),
        "high": str(candle.high),
        "low": str(candle.low),
        "close": str(candle.close),
        "volume": str(candle.volume) if candle.volume is not None else None,
        "bid": str(candle.bid) if candle.bid is not None else None,
        "ask": str(candle.ask) if candle.ask is not None else None,
        "source": candle.source,
        "is_complete": candle.is_complete,
    }


def _candle_from_dict(data: dict[str, Any]) -> Candle:
    return Candle(
        instrument=data["instrument"],
        timeframe=data["timeframe"],
        timestamp=datetime.fromisoformat(data["timestamp"]),
        open=Decimal(data["open"]),
        high=Decimal(data["high"]),
        low=Decimal(data["low"]),
        close=Decimal(data["close"]),
        volume=Decimal(data["volume"]) if data["volume"] is not None else None,
        bid=Decimal(data["bid"]) if data["bid"] is not None else None,
        ask=Decimal(data["ask"]) if data["ask"] is not None else None,
        source=data["source"],
        is_complete=bool(data["is_complete"]),
    )
