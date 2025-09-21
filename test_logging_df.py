#!/usr/bin/env python3
import asyncio
import pandas as pd
from nodes.core.io.logging_node import LoggingNode

async def test_logging_node_with_dataframe():
    # Create a LoggingNode
    logging_node = LoggingNode("test_logging", {"format": "auto"})

    # Create a sample DataFrame like what PolygonCustomBarsNode returns
    df = pd.DataFrame({
        "open": [150.0, 152.0],
        "high": [155.0, 158.0],
        "low": [148.0, 150.0],
        "close": [152.0, 155.0],
        "volume": [1000000, 1200000]
    })
    df.index = pd.to_datetime([1672531200000, 1672617600000], unit="ms", utc=True)
    df.index.name = "timestamp"

    print("DataFrame:")
    print(df)
    print(f"DataFrame type: {type(df)}")

    # Execute the LoggingNode with the DataFrame
    result = await logging_node.execute({"input": df})

    print(f"LoggingNode result: {result}")

if __name__ == "__main__":
    asyncio.run(test_logging_node_with_dataframe())
