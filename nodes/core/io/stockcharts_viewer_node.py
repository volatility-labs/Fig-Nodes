import logging
import webbrowser
from typing import Any, Union, List

from core.types_registry import NodeCategory, AssetSymbol
from nodes.base.base_node import Base

logger = logging.getLogger(__name__)


class StockChartsViewer(Base):
    """
    Node to view stock charts on StockCharts.com.

    Takes a stock symbol or list of symbols as input and opens the corresponding charts
    on StockCharts.com in new browser tabs.

    Input:
    - symbol: str | List[str] | AssetSymbol | List[AssetSymbol] - The stock symbol(s) to view

    Output:
    - urls: List[str] - The generated StockCharts URLs
    - status: str - Status message indicating success/failure
    - count: int - Number of charts opened

    Parameters:
    - auto_open: bool - Whether to automatically open the URLs in browser
    - chart_style: str - Chart style/theme to use
    - max_tabs: int - Maximum number of tabs to open at once (0 = unlimited)
    """

    inputs = {"symbol": Any}  # Can be str, List[str], AssetSymbol, or List[AssetSymbol]
    outputs = {"urls": List[str], "status": str, "count": int}

    default_params = {
        "auto_open": True,
        "chart_style": "c",  # c = candlestick, l = line, etc.
        "max_tabs": 10,  # Limit to prevent overwhelming browser
    }

    params_meta = [
        {
            "name": "auto_open",
            "type": "combo",
            "default": True,
            "options": [True, False],
            "label": "Auto Open in Browser",
            "description": "Automatically open chart URLs in your default web browser",
        },
        {
            "name": "chart_style",
            "type": "combo",
            "default": "c",
            "options": ["c", "l", "b", "a"],
            "label": "Chart Style",
            "description": "Chart style: c=candlestick, l=line, b=bar, a=area",
        },
        {
            "name": "max_tabs",
            "type": "number",
            "default": 10,
            "min": 0,
            "max": 50,
            "label": "Max Tabs",
            "description": "Maximum number of browser tabs to open (0 = unlimited, but not recommended)",
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

    def _extract_symbols(self, input_data: Any) -> list[str]:
        """
        Extract symbol strings from various input formats.

        Args:
            input_data: Can be str, List[str], AssetSymbol, or List[AssetSymbol]

        Returns:
            List of symbol strings
        """
        symbols = []

        if input_data is None:
            return symbols

        # Handle single symbol
        if isinstance(input_data, str):
            if input_data.strip():
                symbols.append(input_data.strip().upper())
        elif isinstance(input_data, AssetSymbol):
            symbols.append(str(input_data.ticker).upper())
        elif isinstance(input_data, list):
            # Handle list of symbols
            for item in input_data:
                if isinstance(item, str) and item.strip():
                    symbols.append(item.strip().upper())
                elif isinstance(item, AssetSymbol):
                    symbols.append(str(item.ticker).upper())
        else:
            # Try to convert to string as fallback
            symbol_str = str(input_data).strip()
            if symbol_str:
                symbols.append(symbol_str.upper())

        return symbols

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        input_data = inputs.get("symbol")

        # Extract symbols from input
        symbols = self._extract_symbols(input_data)

        if not symbols:
            error_msg = "No valid symbols provided"
            logger.error(f"StockChartsViewer {self.id}: {error_msg}")
            return {"urls": [], "status": error_msg, "count": 0}

        # Get parameters
        auto_open = self.params.get("auto_open", True)
        chart_style = self.params.get("chart_style", "c")
        max_tabs = self.params.get("max_tabs", 10)

        # Apply max tabs limit if set
        if max_tabs > 0 and len(symbols) > max_tabs:
            limited_symbols = symbols[:max_tabs]
            logger.warning(
                f"StockChartsViewer {self.id}: Limited to {max_tabs} tabs out of {len(symbols)} symbols"
            )
            symbols = limited_symbols

        # Generate URLs for all symbols
        urls = []
        try:
            for symbol in symbols:
                url = self._generate_stockcharts_url(symbol, chart_style)
                urls.append(url)
                logger.debug(f"StockChartsViewer {self.id}: Generated URL for {symbol}: {url}")

            # Auto-open in browser if enabled
            opened_count = 0
            if auto_open and urls:
                for i, url in enumerate(urls):
                    try:
                        webbrowser.open_new_tab(url)
                        opened_count += 1
                        # Small delay between openings to avoid overwhelming browser
                        if i < len(urls) - 1:
                            import asyncio
                            await asyncio.sleep(0.1)
                    except Exception as e:
                        logger.warning(
                            f"StockChartsViewer {self.id}: Failed to open tab for {symbols[i]}: {str(e)}"
                        )

                if opened_count == len(urls):
                    status = f"Successfully opened {opened_count} chart(s) in browser"
                else:
                    status = f"Opened {opened_count}/{len(urls)} charts in browser (some failed)"
                logger.info(f"StockChartsViewer {self.id}: {status}")
            else:
                status = f"Generated {len(urls)} chart URL(s) (auto-open disabled)"
                logger.info(f"StockChartsViewer {self.id}: {status}")

            return {
                "urls": urls,
                "status": status,
                "count": len(urls)
            }

        except Exception as e:
            error_msg = f"Failed to generate StockCharts URLs: {str(e)}"
            logger.error(f"StockChartsViewer {self.id}: {error_msg}")
            return {"urls": [], "status": error_msg, "count": 0}
