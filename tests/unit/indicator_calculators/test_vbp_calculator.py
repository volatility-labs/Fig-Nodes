import pytest

from core.types_registry import OHLCVBar
from services.indicator_calculators.vbp_calculator import calculate_vbp


@pytest.fixture
def sample_bars() -> list[OHLCVBar]:
    """Create realistic OHLCV bars for testing VBP."""
    return [
        {
            "timestamp": 1000,
            "open": 100.0,
            "high": 105.0,
            "low": 95.0,
            "close": 102.0,
            "volume": 1000.0,
        },
        {
            "timestamp": 2000,
            "open": 102.0,
            "high": 108.0,
            "low": 100.0,
            "close": 106.0,
            "volume": 1500.0,
        },
        {
            "timestamp": 3000,
            "open": 106.0,
            "high": 110.0,
            "low": 104.0,
            "close": 109.0,
            "volume": 2000.0,
        },
        {
            "timestamp": 4000,
            "open": 109.0,
            "high": 112.0,
            "low": 107.0,
            "close": 111.0,
            "volume": 1200.0,
        },
        {
            "timestamp": 5000,
            "open": 111.0,
            "high": 115.0,
            "low": 109.0,
            "close": 113.0,
            "volume": 1800.0,
        },
    ]


@pytest.fixture
def bars_with_concentrated_volume() -> list[OHLCVBar]:
    """Create bars with volume concentrated in middle price range."""
    return [
        {
            "timestamp": 1000,
            "open": 100.0,
            "high": 105.0,
            "low": 95.0,
            "close": 102.0,
            "volume": 100.0,
        },
        {
            "timestamp": 2000,
            "open": 102.0,
            "high": 108.0,
            "low": 100.0,
            "close": 106.0,
            "volume": 5000.0,
        },
        {
            "timestamp": 3000,
            "open": 106.0,
            "high": 110.0,
            "low": 104.0,
            "close": 109.0,
            "volume": 5000.0,
        },
        {
            "timestamp": 4000,
            "open": 109.0,
            "high": 112.0,
            "low": 107.0,
            "close": 111.0,
            "volume": 100.0,
        },
        {
            "timestamp": 5000,
            "open": 111.0,
            "high": 115.0,
            "low": 109.0,
            "close": 113.0,
            "volume": 100.0,
        },
    ]


class TestCalculateVBP:
    """Tests for VBP calculation."""

    def test_vbp_basic_happy_path(self, sample_bars):
        """Test basic VBP calculation with valid data."""
        result = calculate_vbp(sample_bars, number_of_bins=10)

        # Should return dictionary with histogram, POC, VAH, VAL
        assert isinstance(result, dict)
        assert "histogram" in result
        assert "pointOfControl" in result
        assert "valueAreaHigh" in result
        assert "valueAreaLow" in result

        # Histogram should be a list
        assert isinstance(result["histogram"], list)
        assert len(result["histogram"]) == 10

        # Check histogram bin structure
        for bin in result["histogram"]:
            assert "priceLow" in bin
            assert "priceHigh" in bin
            assert "priceLevel" in bin
            assert "volume" in bin
            assert isinstance(bin["volume"], float)

        # POC should be a number
        assert isinstance(result["pointOfControl"], float)

    def test_vbp_with_concentrated_volume(self, bars_with_concentrated_volume):
        """Test VBP with volume concentrated in middle."""
        result = calculate_vbp(bars_with_concentrated_volume, number_of_bins=10)

        # Value area should be around middle bins
        vah = result["valueAreaHigh"]
        val = result["valueAreaLow"]
        poc = result["pointOfControl"]

        # POC should be within value area
        assert val <= poc <= vah

    def test_vbp_empty_data(self):
        """Test VBP with empty data."""
        result = calculate_vbp([], number_of_bins=10)

        assert result == {
            "histogram": [],
            "pointOfControl": None,
            "valueAreaHigh": None,
            "valueAreaLow": None,
        }

    def test_vbp_zero_bins(self, sample_bars):
        """Test VBP with zero bins."""
        result = calculate_vbp(sample_bars, number_of_bins=0)

        assert result == {
            "histogram": [],
            "pointOfControl": None,
            "valueAreaHigh": None,
            "valueAreaLow": None,
        }

    def test_vbp_negative_bins(self, sample_bars):
        """Test VBP with negative bins."""
        result = calculate_vbp(sample_bars, number_of_bins=-5)

        assert result == {
            "histogram": [],
            "pointOfControl": None,
            "valueAreaHigh": None,
            "valueAreaLow": None,
        }

    def test_vbp_histogram_bins_cover_price_range(self, sample_bars):
        """Test that histogram bins cover the entire price range."""
        result = calculate_vbp(sample_bars, number_of_bins=10)

        histogram = result["histogram"]
        if len(histogram) > 0:
            first_bin = histogram[0]
            last_bin = histogram[-1]

            # First bin should start at min price, last bin should end at max price
            assert first_bin["priceLow"] == pytest.approx(95.0, abs=0.01)
            assert last_bin["priceHigh"] == pytest.approx(115.0, abs=0.01)

    def test_vbp_bins_are_sequential(self, sample_bars):
        """Test that histogram bins are sequential."""
        result = calculate_vbp(sample_bars, number_of_bins=10)

        histogram = result["histogram"]
        for i in range(len(histogram) - 1):
            current_bin = histogram[i]
            next_bin = histogram[i + 1]

            # Current bin's high should equal next bin's low
            assert current_bin["priceHigh"] == pytest.approx(next_bin["priceLow"], abs=0.01)

    def test_vbp_price_level_is_midpoint(self, sample_bars):
        """Test that priceLevel is the midpoint of each bin."""
        result = calculate_vbp(sample_bars, number_of_bins=10)

        for bin in result["histogram"]:
            expected_midpoint = (bin["priceLow"] + bin["priceHigh"]) / 2
            assert bin["priceLevel"] == pytest.approx(expected_midpoint, abs=0.01)

    def test_vbp_total_volume_matches(self, sample_bars):
        """Test that total volume in histogram matches input volume."""
        result = calculate_vbp(sample_bars, number_of_bins=10)

        histogram_volume = sum(bin["volume"] for bin in result["histogram"])
        input_volume = sum(bar["volume"] for bar in sample_bars)

        assert histogram_volume == pytest.approx(input_volume, abs=0.01)

    def test_vbp_single_price_range(self):
        """Test VBP when all prices are the same."""
        bars: list[OHLCVBar] = [
            {
                "timestamp": 1000,
                "open": 100.0,
                "high": 100.0,
                "low": 100.0,
                "close": 100.0,
                "volume": 1000.0,
            },
            {
                "timestamp": 2000,
                "open": 100.0,
                "high": 100.0,
                "low": 100.0,
                "close": 100.0,
                "volume": 2000.0,
            },
        ]

        result = calculate_vbp(bars, number_of_bins=10)

        # Should return empty histogram when min == max
        assert result == {
            "histogram": [],
            "pointOfControl": None,
            "valueAreaHigh": None,
            "valueAreaLow": None,
        }

    def test_vbp_zero_volume(self):
        """Test VBP with zero volume."""
        bars: list[OHLCVBar] = [
            {
                "timestamp": 1000,
                "open": 100.0,
                "high": 105.0,
                "low": 95.0,
                "close": 102.0,
                "volume": 0.0,
            },
            {
                "timestamp": 2000,
                "open": 102.0,
                "high": 108.0,
                "low": 100.0,
                "close": 106.0,
                "volume": 0.0,
            },
        ]

        result = calculate_vbp(bars, number_of_bins=10)

        # Should return empty histogram when total volume is 0
        assert result == {
            "histogram": [],
            "pointOfControl": None,
            "valueAreaHigh": None,
            "valueAreaLow": None,
        }

    def test_vbp_consistent_results(self, sample_bars):
        """Test that VBP gives consistent results for same input."""
        result1 = calculate_vbp(sample_bars, number_of_bins=10)
        result2 = calculate_vbp(sample_bars, number_of_bins=10)

        # Results should be identical
        assert result1 == result2

    def test_vbp_different_bin_counts(self, sample_bars):
        """Test VBP with different bin counts."""
        result_5 = calculate_vbp(sample_bars, number_of_bins=5)
        result_20 = calculate_vbp(sample_bars, number_of_bins=20)

        assert len(result_5["histogram"]) == 5
        assert len(result_20["histogram"]) == 20

        # Should both have valid POC
        assert result_5["pointOfControl"] is not None
        assert result_20["pointOfControl"] is not None


class TestVBPEdgeCases:
    """Edge case tests for VBP calculation."""

    def test_vbp_single_bar(self):
        """Test VBP with single bar."""
        bars: list[OHLCVBar] = [
            {
                "timestamp": 1000,
                "open": 100.0,
                "high": 105.0,
                "low": 95.0,
                "close": 102.0,
                "volume": 1000.0,
            }
        ]

        result = calculate_vbp(bars, number_of_bins=10)

        # Should return valid result
        assert len(result["histogram"]) == 10
        assert result["pointOfControl"] is not None

    def test_vbp_very_large_bin_count(self, sample_bars):
        """Test VBP with very large bin count."""
        result = calculate_vbp(sample_bars, number_of_bins=100)

        assert len(result["histogram"]) == 100
        assert result["pointOfControl"] is not None

    def test_vbp_minimum_bin_count(self, sample_bars):
        """Test VBP with minimum bin count."""
        result = calculate_vbp(sample_bars, number_of_bins=1)

        assert len(result["histogram"]) == 1
        assert result["pointOfControl"] is not None

    def test_vbp_extreme_price_values(self):
        """Test VBP with extreme price values."""
        bars: list[OHLCVBar] = [
            {
                "timestamp": 1000,
                "open": 1000000.0,
                "high": 1000100.0,
                "low": 999900.0,
                "close": 1000050.0,
                "volume": 1000.0,
            },
            {
                "timestamp": 2000,
                "open": 1000050.0,
                "high": 1000150.0,
                "low": 999950.0,
                "close": 1000100.0,
                "volume": 2000.0,
            },
        ]

        result = calculate_vbp(bars, number_of_bins=10)

        # Should handle large values without error
        assert len(result["histogram"]) == 10
        assert result["pointOfControl"] is not None
