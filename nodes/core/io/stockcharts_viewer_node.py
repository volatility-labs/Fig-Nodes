import logging
import webbrowser
from typing import Any

from core.types_registry import NodeCategory
from nodes.base.base_node import Base

logger = logging.getLogger(__name__)


class StockChartsViewer(Base):
    """
    Node to view stock charts on StockCharts.com.

    Takes a stock symbol as input and opens the corresponding chart
    on StockCharts.com in a new browser tab.

    Input:
    - symbol: str - The stock symbol to view (e.g., "AAPL", "TSLA", "VLTLF")

    Output:
    - url: str - The generated StockCharts URL
    - status: str - Status message indicating success/failure

    Parameters:
    - auto_open: bool - Whether to automatically open the URL in browser
    - chart_style: str - Chart style/theme to use
    """

    inputs = {"symbol": str}
    outputs = {"url": str, "status": str}

    default_params = {
        "auto_open": True,
        "chart_style": "c",  # c = candlestick, l = line, etc.
    }

    params_meta = [
        {
            "name": "auto_open",
            "type": "combo",
            "default": True,
            "options": [True, False],
            "label": "Auto Open in Browser",
            "description": "Automatically open the chart URL in your default web browser",
        },
        {
            "name": "chart_style",
            "type": "combo",
            "default": "c",
            "options": ["c", "l", "b", "a"],
            "label": "Chart Style",
            "description": "Chart style: c=candlestick, l=line, b=bar, a=area",
        },
    ]

    CATEGORY = NodeCategory.IO

    def _generate_stockcharts_url(self, symbol: str, chart_style: str = "c") -> str:
        """
        Generate a StockCharts URL for the given symbol.

        Args:
            symbol: Stock symbol (e.g., "AAPL", "TSLA")
            chart_style: Chart style parameter (c=candlestick, l=line, etc.)

        Returns:
            Complete StockCharts URL
        """
        # Clean and uppercase the symbol
        clean_symbol = str(symbol).strip().upper()

        # Base URL format: https://stockcharts.com/sc3/ui/?s={SYMBOL}
        # We can add chart style and other parameters
        base_url = f"https://stockcharts.com/sc3/ui/?s={clean_symbol}"

        # Add chart style if specified
        if chart_style and chart_style != "c":
            # Note: StockCharts URL format may vary, this is the basic format
            pass  # For now, keep it simple with just the symbol

        return base_url

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        symbol = inputs.get("symbol")

        if not symbol:
            error_msg = "No symbol provided"
            logger.error(f"StockChartsViewer {self.id}: {error_msg}")
            return {"url": "", "status": error_msg}

        # Convert symbol to string if it's not already
        if not isinstance(symbol, str):
            symbol = str(symbol)

        # Get parameters
        auto_open = self.params.get("auto_open", True)
        chart_style = self.params.get("chart_style", "c")

        # Generate the URL
        try:
            url = self._generate_stockcharts_url(symbol, chart_style)
            logger.info(f"StockChartsViewer {self.id}: Generated URL for {symbol}: {url}")

            # Auto-open in browser if enabled
            if auto_open:
                try:
                    webbrowser.open_new_tab(url)
                    status = f"Successfully opened chart for {symbol} in browser"
                    logger.info(f"StockChartsViewer {self.id}: {status}")
                except Exception as e:
                    status = f"Generated URL but failed to open browser: {str(e)}"
                    logger.warning(f"StockChartsViewer {self.id}: {status}")
            else:
                status = f"Generated chart URL for {symbol} (auto-open disabled)"
                logger.info(f"StockChartsViewer {self.id}: {status}")

            return {"url": url, "status": status}

        except Exception as e:
            error_msg = f"Failed to generate StockCharts URL for {symbol}: {str(e)}"
            logger.error(f"StockChartsViewer {self.id}: {error_msg}")
            return {"url": "", "status": error_msg}
