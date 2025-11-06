#!/usr/bin/env python3
import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Literal

try:
    import websockets  # type: ignore
except Exception as e:
    print("Please install the 'websockets' package: uv add websockets", file=sys.stderr)
    raise

IntervalName = Literal["5m", "15m", "30m", "1h", "1d"]

INTERVAL_SECONDS: dict[IntervalName, int] = {
    "5m": 5 * 60,
    "15m": 15 * 60,
    "30m": 30 * 60,
    "1h": 60 * 60,
    "1d": 24 * 60 * 60,
}


async def run_once(ws_url: str, graph_json: dict) -> None:
    async with websockets.connect(ws_url, max_size=None) as ws:  # type: ignore
        # Connect
        await ws.send(json.dumps({"type": "connect"}))
        # Fire the graph
        await ws.send(json.dumps({"type": "graph", "graph_data": graph_json}))
        # Consume messages until we see a stopped or connection closes
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=60.0)  # type: ignore
                # Optional: print minimal status lines
                # You can extend this to parse and react to job states
                try:
                    data = json.loads(msg)
                    typ = data.get("type")
                    if typ in ("status", "error", "stopped"):
                        print(f"[{typ}] {data}")
                except Exception:
                    pass
        except asyncio.TimeoutError:
            # No messages for a minute; assume job finished or quiet
            pass
        except websockets.exceptions.ConnectionClosed:  # type: ignore
            pass


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Recurring Fig-Nodes graph runner")
    p.add_argument("--graph", required=True, help="Path to saved graph JSON (your workflow)")
    p.add_argument("--interval", required=True, choices=list(INTERVAL_SECONDS.keys()), help="Run cadence: 5m, 15m, 30m, 1h, 1d")
    p.add_argument("--host", default="localhost", help="Backend host (default: localhost)")
    p.add_argument("--port", type=int, default=8000, help="Backend port (default: 8000)")
    p.add_argument("--runs", type=int, default=0, help="Number of runs (0 = infinite)")
    return p.parse_args()


async def main() -> int:
    args = parse_args()
    graph_path = Path(args.graph)
    if not graph_path.exists():
        print(f"Graph file not found: {graph_path}", file=sys.stderr)
        return 1

    try:
        graph_json = json.loads(graph_path.read_text())
    except Exception as e:
        print(f"Failed to read graph JSON: {e}", file=sys.stderr)
        return 1

    ws_url = f"ws://{args.host}:{args.port}/execute"
    delay = INTERVAL_SECONDS[args.interval]

    count = 0
    print(f"Starting recurring runner → {graph_path} every {args.interval} (ws: {ws_url})")
    while True:
        count += 1
        print(f"Run #{count}...")
        try:
            await run_once(ws_url, graph_json)
        except Exception as e:
            print(f"Run failed: {type(e).__name__}: {e}")
        if args.runs > 0 and count >= args.runs:
            break
        await asyncio.sleep(delay)

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
