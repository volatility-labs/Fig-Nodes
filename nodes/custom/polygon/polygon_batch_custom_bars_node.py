import logging
from typing import Any

from core.api_key_vault import APIKeyVault
from core.types_registry import AssetSymbol, OHLCVBar, get_type
from nodes.base.base_node import Base
from services.polygon_service import fetch_bars
from services.rate_limiter import RateLimiter, process_with_worker_pool

logger = logging.getLogger(__name__)


class PolygonBatchCustomBars(Base):
    """
    Fetches custom aggregate bars (OHLCV) for multiple symbols from Massive.com API (formerly Polygon.io) in batch.
    Outputs a bundle (dict of symbol to list of bars).

    Note: Polygon.io has rebranded to Massive.com. The API endpoints have been updated
    to use api.massive.com, but the API routes remain unchanged.

    For crypto symbols, the ticker is automatically prefixed with "X:" (e.g., BTCUSD -> X:BTCUSD)
    as required by the Massive.com crypto aggregates API.
    """

    required_keys = ["POLYGON_API_KEY"]
    inputs = {"symbols": get_type("AssetSymbolList")}
    outputs = {
        "ohlcv_bundle": get_type("OHLCVBundle")
    }  # Changed from Dict[AssetSymbol, List[OHLCVBar]]
    default_params = {
        "multiplier": 1,
        "timespan": "day",
        "lookback_period": "3 months",
        "adjusted": True,
        "sort": "asc",
        "limit": 5000,
        "max_concurrent": 10,  # For concurrency limiting - increased for better throughput
        "rate_limit_per_second": 95,  # Stay under Polygon's recommended 100/sec
    }
    params_meta = [
        {"name": "multiplier", "type": "number", "default": 1, "min": 1, "step": 1},
        {
            "name": "timespan",
            "type": "combo",
            "default": "day",
            "options": ["minute", "hour", "day", "week", "month", "quarter", "year"],
        },
        {
            "name": "lookback_period",
            "type": "combo",
            "default": "3 months",
            "options": [
                "1 day",
                "3 days",
                "1 week",
                "2 weeks",
                "1 month",
                "2 months",
                "3 months",
                "4 months",
                "6 months",
                "9 months",
                "1 year",
                "18 months",
                "2 years",
                "3 years",
                "5 years",
                "10 years",
            ],
        },
        {"name": "adjusted", "type": "combo", "default": True, "options": [True, False]},
        {"name": "sort", "type": "combo", "default": "asc", "options": ["asc", "desc"]},
        {"name": "limit", "type": "number", "default": 5000, "min": 1, "max": 50000, "step": 1},
        # Internal execution controls are not exposed to UI
    ]

    def __init__(
        self, id: int, params: dict[str, Any], graph_context: dict[str, Any] | None = None
    ):
        super().__init__(id, params, graph_context)
        # Ensure multiplier is always an integer (API requirement)
        if "multiplier" in self.params:
            multiplier_raw = self.params["multiplier"]
            if isinstance(multiplier_raw, (int, float)):
                self.params["multiplier"] = max(1, int(round(multiplier_raw)))
            else:
                self.params["multiplier"] = 1
        # Conservative cap to avoid event loop thrashing and ensure predictable batching in tests
        self._max_safe_concurrency = 5

    async def _execute_impl(
        self, inputs: dict[str, Any]
    ) -> dict[str, dict[AssetSymbol, list[OHLCVBar]]]:
        symbols: list[AssetSymbol] = inputs.get("symbols", [])
        if not symbols:
            return {"ohlcv_bundle": {}}

        vault = APIKeyVault()
        api_key = vault.get("POLYGON_API_KEY")
        if not api_key:
            raise ValueError("Polygon API key not found in vault")

        max_concurrent_raw = self.params.get("max_concurrent", 10)
        rate_limit_raw = self.params.get("rate_limit_per_second", 95)

        # Type guards to ensure correct types
        if not isinstance(max_concurrent_raw, int):
            max_concurrent = 10
        else:
            max_concurrent = max_concurrent_raw

        if not isinstance(rate_limit_raw, int):
            rate_limit = 95
        else:
            rate_limit = rate_limit_raw

        rate_limiter = RateLimiter(max_per_second=rate_limit)
        effective_concurrency = min(max_concurrent, self._max_safe_concurrency)

        # Track statuses as they come in
        status_tracker: dict[str, int] = {
            "real-time": 0,
            "delayed": 0,
            "market-closed": 0,
        }

        async def fetch_bars_worker(
            sym: AssetSymbol,
        ) -> tuple[AssetSymbol, list[OHLCVBar], dict[str, Any]] | None:
            """Worker function that fetches bars for a symbol."""
            bars, metadata = await fetch_bars(sym, api_key, self.params)
            if bars:
                # Update status tracker and send incremental status update
                data_status = metadata.get("data_status", "unknown")
                if data_status in status_tracker:
                    status_tracker[data_status] += 1

                # Determine current overall status
                overall_status = "real-time"
                if status_tracker["market-closed"] > 0:
                    overall_status = "market-closed"
                elif status_tracker["delayed"] > 0:
                    overall_status = "delayed"

                # Send incremental status update
                from nodes.base.base_node import ProgressState

                self._emit_progress(
                    ProgressState.UPDATE,
                    progress=None,
                    text="Fetching symbols...",
                    meta={"polygon_data_status": overall_status},
                )

            return (sym, bars, metadata) if bars else None

        # Use shared worker pool to process symbols concurrently
        results = await process_with_worker_pool(
            items=symbols,
            worker_func=fetch_bars_worker,
            rate_limiter=rate_limiter,
            max_concurrent=effective_concurrency,
            progress_callback=self.report_progress,
            stop_flag=lambda: self._is_stopped,
            logger_instance=logger,
        )

        # Build bundle from results (filter out None results)
        bundle: dict[AssetSymbol, list[OHLCVBar]] = {}
        for result in results:
            if result is not None:
                sym, bars, _metadata = result
                bundle[sym] = bars

        # Determine overall status from tracker (prefer most severe: market-closed > delayed > real-time)
        overall_status = "real-time"
        if status_tracker["market-closed"] > 0:
            overall_status = "market-closed"
        elif status_tracker["delayed"] > 0:
            overall_status = "delayed"

        # Send final status update
        from nodes.base.base_node import ProgressState

        self._emit_progress(
            ProgressState.UPDATE,
            progress=None,
            text=f"Fetched {len(bundle)} symbols",
            meta={"polygon_data_status": overall_status},
        )

        return {"ohlcv_bundle": bundle}
