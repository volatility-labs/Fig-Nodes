from typing import Dict, Any, List, AsyncGenerator
import asyncio
import websockets
import json
from nodes.base.streaming_node import StreamingNode
from core.types_registry import AssetSymbol


class WebSocketNode(StreamingNode):
    inputs = {"symbols": List[AssetSymbol]}
    outputs = {"ohlcv": Dict[AssetSymbol, Any]}

    def __init__(self, id: int, params: Dict[str, Any] = None):
        super().__init__(id, params)
        self._stopped = False
        self._ws = None  # Store websocket connection

    async def start(self, inputs: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        symbols = self.collect_multi_input("symbols", inputs)
        if not symbols:
            return
        try:
            async with websockets.connect("wss://example.com/ws") as ws:
                self._ws = ws
                await ws.send(json.dumps({"subscribe": [str(s) for s in symbols]}))
                while not self._stopped:
                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=0.1)  # Smaller timeout for frequent checks
                        ohlcv = {}  # Parse message to ohlcv
                        yield {"ohlcv": ohlcv}
                    except asyncio.TimeoutError:
                        if self._stopped:
                            break
                        continue
        except Exception as e:
            print(f"WebSocket error: {e}")
        finally:
            self._ws = None

    def stop(self):
        self._stopped = True

    def interrupt(self):
        if self._ws:
            asyncio.create_task(self._ws.close())  # Force close


