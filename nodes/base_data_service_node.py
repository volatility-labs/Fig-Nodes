
from typing import Dict, Any, List
from abc import ABC, abstractmethod
import pandas as pd
from nodes.base_node import BaseNode

class BaseDataServiceNode(BaseNode, ABC):
    @property
    def inputs(self) -> List[str]:
        return ['symbols', 'timeframes', 'action']  # e.g., 'prewarm', 'get_data'

    @property
    def outputs(self) -> List[str]:
        return ['result']  # Could be data dict or status

    @abstractmethod
    def perform_action(self, symbols: List[str], timeframes: List[str], action: str) -> Dict[str, Any]:
        """Abstract method to perform data service actions."""
        pass

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        if not self.validate_inputs(inputs):
            raise ValueError(f"Missing inputs for node {self.id}: {self.inputs}")
        symbols = inputs['symbols']
        timeframes = inputs['timeframes']
        action = inputs['action']
        try:
            result = self.perform_action(symbols, timeframes, action)
            return {'result': result}
        except Exception as e:
            raise RuntimeError(f"Error in {self.id} execution: {str(e)}") from e 