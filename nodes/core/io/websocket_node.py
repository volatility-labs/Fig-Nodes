from typing import Dict, Any, List, AsyncGenerator
import asyncio
import websockets
import json
from nodes.base.streaming_node import StreamingNode
from core.types_registry import AssetSymbol


class WebSocketNode(StreamingNode):
    inputs = {"symbols": List[AssetSymbol]}
    outputs = {"ohlcv": Dict[AssetSymbol, Any]}

    async def start(self, inputs: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        symbols = inputs.get("symbols", [])
        if not symbols:
            return
        async with websockets.connect("wss://example.com/ws") as ws:
            await ws.send(json.dumps({"subscribe": [str(s) for s in symbols]}))
            while True:
                message = await ws.recv()
                data = json.loads(message)  # Placeholder: assume data is OHLCV
                ohlcv = {sym: data.get(sym, {}) for sym in symbols}  # Placeholder parsing
                yield {"ohlcv": ohlcv}
                await asyncio.sleep(0)

    def stop(self):
        pass


