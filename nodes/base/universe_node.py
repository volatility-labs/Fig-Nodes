from typing import Dict, Any, List
from abc import ABC, abstractmethod
from nodes.base.base_node import BaseNode
from core.types_registry import get_type

class UniverseNode(BaseNode, ABC):
    """
    Abstract base for nodes that provide lists of AssetSymbols (e.g., from exchanges).
    
    Subclasses must implement _fetch_symbols().
    """
    inputs = {"filter_symbols": get_type("AssetSymbolList")}
    outputs = {"symbols": get_type("AssetSymbolList")}
    optional_inputs = ["filter_symbols"]

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        symbols = await self._fetch_symbols()
        filter_symbols = inputs.get("filter_symbols", [])
        if filter_symbols:
            filter_set = {str(s) for s in filter_symbols}
            symbols = [s for s in symbols if str(s) in filter_set]
        return {"symbols": symbols}
    
    @abstractmethod
    async def _fetch_symbols(self) -> List[Any]:
        """Fetch the list of symbols from the data source."""
        pass

