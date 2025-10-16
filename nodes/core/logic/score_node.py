from typing import Dict, Any
from nodes.base.base_node import Base


class Score(Base):
    """
    Computes a score based on a dictionary of indicators.
    """
    inputs = {"indicators": Dict[Any, Any]}
    outputs = {"score": float}
    default_params = {}

    def __init__(self, id: int, params: Dict[str, Any] = None):
        super().__init__(id, params)

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        indicators = inputs.get("indicators", {})
        if not indicators:
            return {"score": 0.0}

        score = 0.0
        return {"score": score}


