import pytest
from unittest.mock import patch, MagicMock

from nodes.core.io.stockcharts_viewer_node import StockChartsViewer


class TestStockChartsViewer:
    """Test cases for StockChartsViewer node."""

    def test_node_attributes(self):
        """Test that node has correct inputs, outputs, and category."""
        from typing import Any, List
        assert StockChartsViewer.inputs == {"symbol": Any}  # Any type
        assert StockChartsViewer.outputs == {"urls": List[str], "status": str, "count": int}
        assert StockChartsViewer.CATEGORY.name == "IO"

    def test_default_params(self):
        """Test default parameters."""
        expected_defaults = {
            "auto_open": True,
            "chart_style": "c",
            "max_tabs": 10,
        }
        assert StockChartsViewer.default_params == expected_defaults

    def test_generate_stockcharts_url(self):
        """Test URL generation for different symbols."""
        node = StockChartsViewer(1, {})

        # Test basic symbol
        url = node._generate_stockcharts_url("AAPL")
        assert url == "https://stockcharts.com/sc3/ui/?s=AAPL"

        # Test lowercase symbol gets uppercased
        url = node._generate_stockcharts_url("aapl")
        assert url == "https://stockcharts.com/sc3/ui/?s=AAPL"

        # Test symbol with spaces gets stripped
        url = node._generate_stockcharts_url(" AAPL ")
        assert url == "https://stockcharts.com/sc3/ui/?s=AAPL"

        # Test non-string symbol gets converted
        url = node._generate_stockcharts_url(123)
        assert url == "https://stockcharts.com/sc3/ui/?s=123"

    @pytest.mark.asyncio
    async def test_execute_with_valid_symbol_auto_open(self):
        """Test execution with valid symbol and auto-open enabled."""
        node = StockChartsViewer(1, {"auto_open": True})

        with patch('webbrowser.open_new_tab') as mock_open_tab:
            result = await node._execute_impl({"symbol": "TSLA"})

            # Check that browser was opened
            mock_open_tab.assert_called_once_with("https://stockcharts.com/sc3/ui/?s=TSLA")

            # Check result
            assert result["urls"] == ["https://stockcharts.com/sc3/ui/?s=TSLA"]
            assert "Successfully opened 1 chart(s) in browser" in result["status"]
            assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_execute_with_valid_symbol_no_auto_open(self):
        """Test execution with valid symbol but auto-open disabled."""
        node = StockChartsViewer(1, {"auto_open": False})

        result = await node._execute_impl({"symbol": "AAPL"})

        # Check result
        assert result["urls"] == ["https://stockcharts.com/sc3/ui/?s=AAPL"]
        assert "Generated 1 chart URL(s) (auto-open disabled)" in result["status"]
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_execute_with_no_symbol(self):
        """Test execution with no symbol provided."""
        node = StockChartsViewer(1, {})

        result = await node._execute_impl({})

        assert result["urls"] == []
        assert result["status"] == "No valid symbols provided"
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_execute_with_empty_symbol(self):
        """Test execution with empty symbol."""
        node = StockChartsViewer(1, {})

        result = await node._execute_impl({"symbol": ""})

        assert result["urls"] == []
        assert result["status"] == "No valid symbols provided"
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_execute_browser_open_fails(self):
        """Test execution when browser open fails."""
        node = StockChartsViewer(1, {"auto_open": True})

        with patch('webbrowser.open_new_tab', side_effect=Exception("Browser error")):
            result = await node._execute_impl({"symbol": "MSFT"})

            assert result["urls"] == ["https://stockcharts.com/sc3/ui/?s=MSFT"]
            assert "Opened 0/1 charts in browser (some failed)" in result["status"]
            assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_execute_with_different_chart_styles(self):
        """Test execution with different chart styles."""
        # Note: Current implementation doesn't use chart_style in URL
        # This test ensures the parameter is accepted even if not used
        node = StockChartsViewer(1, {"chart_style": "l", "auto_open": False})

        result = await node._execute_impl({"symbol": "GOOGL"})

        assert result["urls"] == ["https://stockcharts.com/sc3/ui/?s=GOOGL"]
        assert "Generated 1 chart URL(s) (auto-open disabled)" in result["status"]
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_execute_with_multiple_symbols(self):
        """Test execution with multiple symbols."""
        node = StockChartsViewer(1, {"auto_open": False})

        with patch('webbrowser.open_new_tab') as mock_open_tab:
            result = await node._execute_impl({"symbol": ["TSLA", "AAPL", "GOOGL"]})

            # Should not open browser (auto_open=False)
            mock_open_tab.assert_not_called()

            # Check results
            expected_urls = [
                "https://stockcharts.com/sc3/ui/?s=TSLA",
                "https://stockcharts.com/sc3/ui/?s=AAPL",
                "https://stockcharts.com/sc3/ui/?s=GOOGL"
            ]
            assert result["urls"] == expected_urls
            assert "Generated 3 chart URL(s) (auto-open disabled)" in result["status"]
            assert result["count"] == 3

    @pytest.mark.asyncio
    async def test_execute_with_multiple_symbols_auto_open(self):
        """Test execution with multiple symbols and auto-open enabled."""
        node = StockChartsViewer(1, {"auto_open": True, "max_tabs": 5})

        with patch('webbrowser.open_new_tab') as mock_open_tab:
            result = await node._execute_impl({"symbol": ["TSLA", "AAPL"]})

            # Should open 2 tabs
            assert mock_open_tab.call_count == 2
            mock_open_tab.assert_any_call("https://stockcharts.com/sc3/ui/?s=TSLA")
            mock_open_tab.assert_any_call("https://stockcharts.com/sc3/ui/?s=AAPL")

            # Check results
            expected_urls = [
                "https://stockcharts.com/sc3/ui/?s=TSLA",
                "https://stockcharts.com/sc3/ui/?s=AAPL"
            ]
            assert result["urls"] == expected_urls
            assert "Successfully opened 2 chart(s) in browser" in result["status"]
            assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_execute_max_tabs_limit(self):
        """Test that max_tabs parameter limits the number of tabs opened."""
        node = StockChartsViewer(1, {"auto_open": False, "max_tabs": 2})

        result = await node._execute_impl({"symbol": ["TSLA", "AAPL", "GOOGL", "MSFT"]})

        # Should only process first 2 symbols due to max_tabs limit
        expected_urls = [
            "https://stockcharts.com/sc3/ui/?s=TSLA",
            "https://stockcharts.com/sc3/ui/?s=AAPL"
        ]
        assert result["urls"] == expected_urls
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_extract_symbols_from_asset_symbols(self):
        """Test extracting symbols from AssetSymbol objects."""
        from core.types_registry import AssetSymbol

        node = StockChartsViewer(1, {})

        # Create mock AssetSymbol objects
        asset1 = AssetSymbol(ticker="TSLA", asset_class="stocks", quote_currency="USD")
        asset2 = AssetSymbol(ticker="AAPL", asset_class="stocks", quote_currency="USD")

        symbols = node._extract_symbols([asset1, asset2])
        assert symbols == ["TSLA", "AAPL"]

    @pytest.mark.asyncio
    async def test_extract_symbols_mixed_input(self):
        """Test extracting symbols from mixed input types."""
        from core.types_registry import AssetSymbol

        node = StockChartsViewer(1, {})

        asset = AssetSymbol(ticker="TSLA", asset_class="stocks", quote_currency="USD")

        symbols = node._extract_symbols(["AAPL", asset, "GOOGL"])
        assert symbols == ["AAPL", "TSLA", "GOOGL"]
