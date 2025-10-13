import logging
import pandas as pd
from typing import Dict, Any, List
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilterNode
from core.types_registry import AssetSymbol, OHLCVBar, IndicatorResult, IndicatorType, get_type, IndicatorValue

logger = logging.getLogger(__name__)

class AtrXFilterNode(BaseIndicatorFilterNode):
    ui_module = "market/AtrXFilterNodeUI"
    """
    Filters OHLCV bundle based on ATRX indicator thresholds.
    """
    outputs = {
        "filtered_ohlcv_bundle": Dict[AssetSymbol, List[OHLCVBar]]
    }
    default_params = {
        "length": 14,
        "smoothing": "RMA",
        "price": "Close",
        "ma_length": 50,
        "upper_threshold": 6.0,
        "lower_threshold": -4.0,
        "filter_condition": "outside"  # "outside" or "inside"
    }
    params_meta = [
        {"name": "length", "type": "integer", "default": 14},
        {"name": "smoothing", "type": "combo", "default": "RMA", "options": ["RMA", "EMA", "SMA"]},
        {"name": "price", "type": "string", "default": "Close"},
        {"name": "ma_length", "type": "integer", "default": 50},
        {"name": "upper_threshold", "type": "float", "default": 6.0},
        {"name": "lower_threshold", "type": "float", "default": -4.0},
        {"name": "filter_condition", "type": "combo", "default": "outside", "options": ["outside", "inside"]},
    ]

    def _calculate_indicator(self, ohlcv_data: List[OHLCVBar]) -> IndicatorResult:
        if not ohlcv_data:
            raise ValueError("Empty OHLCV data")
        df_data = [
            {
                'timestamp': pd.to_datetime(bar['timestamp'], unit='ms'),
                'Open': bar['open'],
                'High': bar['high'],
                'Low': bar['low'],
                'Close': bar['close'],
                'Volume': bar['volume']
            } for bar in ohlcv_data
        ]
        df = pd.DataFrame(df_data).set_index('timestamp')
        atrx_value = self.indicators_service.calculate_atrx(
            df,
            length=self.params.get("length", 14),
            ma_length=self.params.get("ma_length", 50),
            smoothing=self.params.get("smoothing", "RMA"),
            price=self.params.get("price", "Close"),
        )
        return IndicatorResult(
            indicator_type=IndicatorType.ATRX,
            timestamp=ohlcv_data[-1]['timestamp'],
            values=IndicatorValue(single=atrx_value),
            params=self.params
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        if indicator_result.error:
            return False
        value = indicator_result.values.single
        upper = self.params.get("upper_threshold", 6.0)
        lower = self.params.get("lower_threshold", -4.0)
        condition = self.params.get("filter_condition", "outside")
        if condition == "outside":
            return value > upper or value < lower
        else:
            return lower < value < upper

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        ohlcv_bundle: Dict[AssetSymbol, List[OHLCVBar]] = inputs.get("ohlcv_bundle", {})

        if not ohlcv_bundle:
            return {"filtered_ohlcv_bundle": {}}

        filtered_bundle = {}

        for symbol, ohlcv_data in ohlcv_bundle.items():
            if not ohlcv_data:
                continue

            try:
                # Calculate using subclass method
                indicator_result = self._calculate_indicator(ohlcv_data)

                # Filter
                if self._should_pass_filter(indicator_result):
                    filtered_bundle[symbol] = ohlcv_data

            except Exception as e:
                logger.warning(f"Failed to process indicator for {symbol}: {e}")
                continue

        return {"filtered_ohlcv_bundle": filtered_bundle}
