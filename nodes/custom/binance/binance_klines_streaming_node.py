from typing import Dict, Any, AsyncGenerator, List
import asyncio
import websockets
import json
from nodes.base.streaming_node import StreamingNode
from core.types_registry import AssetSymbol, AssetClass, get_type, InstrumentType, OHLCVBar


class BinanceKlinesStreamingNode(StreamingNode):
    """
    Streaming node that subscribes to Binance kline updates for given symbols.
    Yields closed klines as OHLCVBundle (dict of AssetSymbol to list of OHLCVBar).
    """
    inputs = {"symbols": get_type("AssetSymbolList")}
    # Allow starting without symbols to gracefully end the stream immediately
    optional_inputs = ["symbols"]
    outputs = {"ohlcv": get_type("OHLCVBundle")}
    default_params = {"interval": "1m"}
    params_meta = [
        {"name": "interval", "type": "combo", "default": "1m", "options": ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"]}
    ]

    def __init__(self, id: int, params: Dict[str, Any] = None):
        super().__init__(id, params)
        self.ws = None

    async def _start_impl(self, inputs: Dict[str, Any]) -> AsyncGenerator[Dict[str, Dict[AssetSymbol, List[OHLCVBar]]], None]:
        symbols = self.collect_multi_input("symbols", inputs)
        if not symbols:
            return

        interval = self.params.get("interval")
        streams = [f"{sym.ticker.lower()}{sym.quote_currency.lower()}@kline_{interval}" for sym in symbols if sym.quote_currency]

        try:
            async with websockets.connect("wss://fstream.binance.com/ws") as ws:
                self.ws = ws
                subscribe_msg = {
                    "method": "SUBSCRIBE",
                    "params": streams,
                    "id": 1,
                }
                await ws.send(json.dumps(subscribe_msg))

                async for message in ws:
                    data = json.loads(message)
                    if "result" in data:
                        continue
                    if data.get("e") == "kline":
                        k = data["k"]
                        if k["x"]:
                            symbol_str = k["s"]
                            base, quote = symbol_str[:-4], symbol_str[-4:]
                            symbol = AssetSymbol(
                                ticker=base.upper(),
                                asset_class=AssetClass.CRYPTO,
                                quote_currency=quote.upper(),
                                instrument_type=InstrumentType.PERPETUAL,
                            )
                            bar = {
                                "timestamp": k["t"],
                                "open": float(k["o"]),
                                "high": float(k["h"]),
                                "low": float(k["l"]),
                                "close": float(k["c"]),
                                "volume": float(k["v"]),
                            }
                            yield {"ohlcv": {symbol: [bar]}}
        except Exception as e:
            raise ValueError(f"Binance kline stream failed: {e}") from e

    def stop(self):
        if self.ws:
            # Close websocket if available; in tests this may be a MagicMock
            close_fn = getattr(self.ws, "close", None)
            if close_fn:
                if asyncio.iscoroutinefunction(close_fn):
                    try:
                        asyncio.run(close_fn())
                    except RuntimeError:
                        # Fallback if loop is running or close_fn is not a coroutine in tests
                        try:
                            close_fn()
                        except Exception:
                            pass
                else:
                    try:
                        close_fn()
                    except Exception:
                        pass


