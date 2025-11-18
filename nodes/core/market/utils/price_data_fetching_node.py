import csv
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from core.types_registry import AssetSymbol, NodeCategory, OHLCVBar, get_type
from nodes.base.base_node import Base

logger = logging.getLogger(__name__)


class PriceDataFetching(Base):
    """
    Extracts the most recent closing prices from an OHLCV bundle and saves to CSV.

    This node takes an OHLCV bundle (filtered symbols) as input, displays formatted output,
    and automatically saves results to a CSV file organized by scan name.

    Perfect for logging current prices and easy viewing in Excel/Cursor.
    """

    CATEGORY = NodeCategory.MARKET

    inputs = {"ohlcv_bundle": get_type("OHLCVBundle")}

    outputs = {
        "formatted_output": str,  # Formatted string display
        "csv_file": str,  # Path to saved CSV file
    }

    default_params = {
        "scan_name": "default_scan",
        "save_to_csv": True,
    }

    params_meta = [
        {
            "name": "scan_name",
            "type": "text",
            "default": "default_scan",
            "label": "Scanner Name",
            "description": "Name for this scanner (e.g., 'momentum_scanner', 'breakout_scanner'). Used to organize CSV files.",
        },
        {
            "name": "save_to_csv",
            "type": "combo",
            "default": True,
            "options": [True, False],
            "label": "Save to CSV",
            "description": "Whether to save results to CSV file. Files are saved to results/ folder and easy to open in Excel or Cursor.",
        },
    ]

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        ohlcv_bundle: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("ohlcv_bundle", {})
        logger.info(f"PriceDataFetching node received bundle with {len(ohlcv_bundle)} symbols")

        if not ohlcv_bundle:
            logger.warning("PriceDataFetching node received empty OHLCV bundle")
            return {
                "formatted_output": "⚠️ No price data available - check if OHLCV bundle is connected",
                "csv_file": "",
            }

        scan_name = self.params.get("scan_name", "default_scan")
        save_to_csv = self.params.get("save_to_csv", True)

        current_time_ms = int(time.time() * 1000)
        current_datetime = datetime.now()

        output_lines: list[str] = []
        output_lines.append(f"=== {scan_name} - Price Data for {len(ohlcv_bundle)} Symbols ===\n")
        # Collect results for CSV
        csv_rows: list[dict[str, Any]] = []

        for symbol, ohlcv_data in ohlcv_bundle.items():
            if not ohlcv_data or len(ohlcv_data) == 0:
                logger.warning(f"PriceDataFetching node received invalid OHLCV data for {symbol}")
                continue

            # Get the most recent bar (last in the list)
            latest_bar = ohlcv_data[-1]

            # Extract price
            price_raw = latest_bar.get("close", 0.0)
            price = float(price_raw)

            # Calculate delay in minutes
            bar_timestamp_ms = latest_bar.get("timestamp", 0)
            delay_ms = current_time_ms - bar_timestamp_ms
            delay_minutes = delay_ms / (1000 * 60)  # Convert to minutes

            # Format timestamp
            bar_datetime = datetime.fromtimestamp(bar_timestamp_ms / 1000)
            timestamp_str = bar_datetime.strftime("%Y-%m-%d %H:%M:%S")

            # Format delay for readability
            if delay_minutes < 60:
                age_str = f"{delay_minutes:.1f} min"
            elif delay_minutes < 1440:
                age_str = f"{delay_minutes / 60:.1f} hrs"
            else:
                age_str = f"{delay_minutes / 1440:.1f} days"

            # Create formatted line: SYMBOL: $PRICE @ TIMESTAMP (age)
            output_lines.append(
                f"{str(symbol):15} ${price:>10.4f}  @  {timestamp_str}  ({age_str} old)"
            )

            # Collect for CSV
            csv_rows.append(
                {
                    "symbol": str(symbol),
                    "price": float(price),
                    "bar_timestamp": timestamp_str,
                    "age_minutes": round(delay_minutes, 2),
                    "open": latest_bar.get("open", ""),
                    "high": latest_bar.get("high", ""),
                    "low": latest_bar.get("low", ""),
                    "volume": latest_bar.get("volume", ""),
                }
            )

        formatted_output = "\n".join(output_lines)
        csv_file = ""

        # Save to CSV if enabled
        if save_to_csv and csv_rows:
            try:
                # Create output directory if it doesn't exist
                output_dir = Path(__file__).resolve().parent.parent.parent.parent.parent / "output"
                output_dir.mkdir(exist_ok=True)

                # Generate filename: scan_name_YYYYMMDD_HHMMSS.csv
                filename = f"{scan_name}_{current_datetime.strftime('%Y%m%d_%H%M%S')}.csv"
                csv_path = output_dir / filename

                # Write CSV file
                with open(csv_path, "w", newline="") as csvfile:
                    fieldnames = [
                        "symbol",
                        "price",
                        "bar_timestamp",
                        "age_minutes",
                        "open",
                        "high",
                        "low",
                        "volume",
                    ]
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                    writer.writeheader()
                    writer.writerows(csv_rows)

                csv_file = str(csv_path)
                output_lines.append(f"\n✅ Saved to CSV: output/{filename}")
                formatted_output = "\n".join(output_lines)
                logger.info(f"PriceDataFetching saved scan '{scan_name}' to {csv_path}")
            except Exception as e:
                logger.error(f"Failed to save to CSV: {e}")
                output_lines.append(f"\n⚠️ CSV save failed: {e}")
                formatted_output = "\n".join(output_lines)

        logger.info(f"PriceDataFetching node extracted prices for {len(ohlcv_bundle)} symbols")

        return {
            "formatted_output": formatted_output,
            "csv_file": csv_file,
        }
