from typing import Dict, Any, List
from abc import ABC, abstractmethod
from nodes.base_node import BaseNode
from services.scoring_service import ScoringService
from indicators.indicators_service import IndicatorsService  # Required for ScoringService init

class BaseScoringNode(BaseNode, ABC):
    @property
    def inputs(self) -> List[str]:
        return ['indicators']

    @property
    def outputs(self) -> List[str]:
        return ['score']

    @abstractmethod
    def compute_score(self, indicators: Dict[str, Any]) -> float:
        """Abstract method to compute score from indicators."""
        pass

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        if not self.validate_inputs(inputs):
            raise ValueError(f"Missing inputs for node {self.id}: {self.inputs}")
        indicators = inputs['indicators']
        try:
            score = self.compute_score(indicators)
            return {'score': score}
        except Exception as e:
            raise RuntimeError(f"Error in {self.id} execution: {str(e)}") from e

class DefaultScoringNode(BaseScoringNode):
    def __init__(self, id: str, params: Dict[str, Any] = None, scoring_service: ScoringService = None):
        super().__init__(id, params)
        # Initialize with default if not provided; assumes IndicatorsService is available
        self.scoring_service = scoring_service or ScoringService(IndicatorsService())

    def compute_score(self, indicators: Dict[str, Any]) -> float:
        return self.scoring_service.compute_score(indicators) 