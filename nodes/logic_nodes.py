from typing import Dict, Any
from services.scoring_service import ScoringService
from .base_node import BaseNode

class ScoreNode(BaseNode):
    """
    Computes a score based on a dictionary of indicators.
    """
    inputs = {"indicators": Dict[str, Any]}
    outputs = {"score": float}
    default_params = {}

    def __init__(self, node_id: str, params: Dict[str, Any]):
        super().__init__(node_id, params)
        self.scoring_service = ScoringService(indicators_service=None)

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        indicators = inputs.get("indicators", {})
        if not indicators:
            return {"score": 0.0}
            
        score = self.scoring_service.compute_score(indicators)
        
        return {"score": score} 