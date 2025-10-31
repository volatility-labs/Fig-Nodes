import pytest
from unittest.mock import patch, MagicMock

from nodes.core.io.stockcharts_viewer_node import StockChartsViewer


class TestStockChartsViewer:
    """Test cases for StockChartsViewer node."""

    def test_node_attributes(self):
        """Test that node has correct inputs, outputs, and category."""
        assert StockChartsViewer.inputs == {"symbol": str}
        assert StockChartsViewer.outputs == {"url": str, "status": str}
        assert StockChartsViewer.CATEGORY.name == "IO"

    def test_default_params(self):
        """Test default parameters."""
        expected_defaults = {
            "auto_open": True,
            "chart_style": "c",
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
            assert result["url"] == "https://stockcharts.com/sc3/ui/?s=TSLA"
            assert "Successfully opened chart for TSLA in browser" in result["status"]

    @pytest.mark.asyncio
    async def test_execute_with_valid_symbol_no_auto_open(self):
        """Test execution with valid symbol but auto-open disabled."""
        node = StockChartsViewer(1, {"auto_open": False})

        result = await node._execute_impl({"symbol": "AAPL"})

        # Check result
        assert result["url"] == "https://stockcharts.com/sc3/ui/?s=AAPL"
        assert "Generated chart URL for AAPL (auto-open disabled)" in result["status"]

    @pytest.mark.asyncio
    async def test_execute_with_no_symbol(self):
        """Test execution with no symbol provided."""
        node = StockChartsViewer(1, {})

        result = await node._execute_impl({})

        assert result["url"] == ""
        assert result["status"] == "No symbol provided"

    @pytest.mark.asyncio
    async def test_execute_with_empty_symbol(self):
        """Test execution with empty symbol."""
        node = StockChartsViewer(1, {})

        result = await node._execute_impl({"symbol": ""})

        assert result["url"] == ""
        assert result["status"] == "No symbol provided"

    @pytest.mark.asyncio
    async def test_execute_browser_open_fails(self):
        """Test execution when browser open fails."""
        node = StockChartsViewer(1, {"auto_open": True})

        with patch('webbrowser.open_new_tab', side_effect=Exception("Browser error")):
            result = await node._execute_impl({"symbol": "MSFT"})

            assert result["url"] == "https://stockcharts.com/sc3/ui/?s=MSFT"
            assert "Generated URL but failed to open browser: Browser error" in result["status"]

    @pytest.mark.asyncio
    async def test_execute_with_different_chart_styles(self):
        """Test execution with different chart styles."""
        # Note: Current implementation doesn't use chart_style in URL
        # This test ensures the parameter is accepted even if not used
        node = StockChartsViewer(1, {"chart_style": "l", "auto_open": False})

        result = await node._execute_impl({"symbol": "GOOGL"})

        assert result["url"] == "https://stockcharts.com/sc3/ui/?s=GOOGL"
        assert "Generated chart URL for GOOGL" in result["status"]
