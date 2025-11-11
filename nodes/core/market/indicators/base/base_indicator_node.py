import logging
from abc import ABC, abstractmethod
from typing import Any

from core.types_registry import IndicatorResult, IndicatorType, IndicatorValue, get_type
from nodes.base.base_node import Base

logger = logging.getLogger(__name__)


class BaseIndicator(Base, ABC):
    """
    Base class for nodes that compute technical indicators from OHLCV data.
    Subclasses should implement _map_to_indicator_value for specific indicator handling.
    """

    inputs = {"ohlcv": get_type("OHLCV")}
    outputs = {"results": list[IndicatorResult]}
    default_params = {
        "timeframe": "1d",
    }
    params_meta = [
        {
            "name": "indicators",
            "type": "combo",
            "default": [IndicatorType.MACD.name, IndicatorType.RSI.name, IndicatorType.ADX.name],
            "options": [e.name for e in IndicatorType],
        },
        {
            "name": "timeframe",
            "type": "combo",
            "default": "1d",
            "options": ["1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"],
        },
    ]

    def __init__(
        self,
        id: int,
        params: dict[str, Any] | None = None,
        graph_context: dict[str, Any] | None = None,
    ):
        super().__init__(id, params or {}, graph_context)

    @abstractmethod
    def _map_to_indicator_value(
        self, ind_type: IndicatorType, raw: dict[str, Any]
    ) -> IndicatorValue:
        """
        Maps raw indicator values to IndicatorValue format.
        Handles heterogeneous outputs per indicator type.
        Subclasses must implement this for specific mappings.
        """
        raise NotImplementedError("Subclasses must implement _map_to_indicator_value")
