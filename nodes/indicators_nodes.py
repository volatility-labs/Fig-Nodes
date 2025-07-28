from typing import Dict, Any, List
from abc import ABC, abstractmethod
import pandas as pd
from nodes.base_node import BaseNode
from indicators.indicators_service import IndicatorsService

class BaseIndicatorsNode(BaseNode, ABC):
    @property
    def inputs(self) -> List[str]:
        return ['data']

    @property
    def outputs(self) -> List[str]:
        return ['indicators']

    @abstractmethod
    def compute_indicators(self, data: pd.DataFrame, timeframe: str) -> Dict[str, Any]:
        """Abstract method to compute indicators from data."""
        pass

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        if not self.validate_inputs(inputs):
            raise ValueError(f"Missing inputs for node {self.id}: {self.inputs}")
        data = inputs['data']
        timeframe = self.params.get('timeframe', '1h')  # Default from params
        try:
            indicators = self.compute_indicators(data, timeframe)
            if not indicators:
                raise ValueError(f"No indicators computed for timeframe {timeframe}")
            return {'indicators': indicators}
        except Exception as e:
            raise RuntimeError(f"Error in {self.id} execution: {str(e)}") from e

class DefaultIndicatorsNode(BaseIndicatorsNode):
    default_params = {'timeframe': '1h'}

    def __init__(self, id: str, params: Dict[str, Any] = None, indicators_service: IndicatorsService = None):
        super().__init__(id, params)
        self.indicators_service = indicators_service or IndicatorsService()  # Default instance if not provided

    def compute_indicators(self, data: pd.DataFrame, timeframe: str) -> Dict[str, Any]:
        return self.indicators_service.compute_indicators(data, timeframe) 