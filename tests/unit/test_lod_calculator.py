from services.indicator_calculators.lod_calculator import calculate_lod


def test_calculate_lod_happy_path():
    """Test LoD calculation with valid data."""
    # Create data with known volatility pattern
    highs = [100 + i * 0.5 for i in range(20)]
    lows = [95 + i * 0.5 for i in range(20)]
    closes = [102 + i * 0.5 for i in range(20)]

    result = calculate_lod(highs, lows, closes, atr_window=14)

    assert "lod_distance_pct" in result
    assert "current_price" in result
    assert "low_of_day" in result
    assert "atr" in result

    assert len(result["lod_distance_pct"]) == 20
    assert len(result["current_price"]) == 20
    assert len(result["low_of_day"]) == 20
    assert len(result["atr"]) == 20

    # First values should be None (insufficient data for ATR)
    assert result["lod_distance_pct"][0] is None
    assert result["atr"][0] is not None  # ATR calculator returns values from start

    # Last value should be valid
    assert result["lod_distance_pct"][-1] is not None
    assert result["lod_distance_pct"][-1] >= 0


def test_calculate_lod_with_distance_from_low():
    """Test LoD calculation where close is far from low."""
    # Create data where close is significantly higher than low
    highs = [120.0] * 20
    lows = [90.0] * 20
    closes = [115.0] * 20  # Close is 25 points above low

    result = calculate_lod(highs, lows, closes, atr_window=14)

    # Last LoD distance should be positive
    assert result["lod_distance_pct"][-1] is not None
    assert result["lod_distance_pct"][-1] > 0


def test_calculate_lod_close_to_low():
    """Test LoD calculation where close is close to low."""
    # Create data where close is very close to low
    highs = [105.0] * 20
    lows = [99.0] * 20
    closes = [99.5] * 20  # Close is only 0.5 points above low

    result = calculate_lod(highs, lows, closes, atr_window=14)

    # Last LoD distance should be small but positive
    assert result["lod_distance_pct"][-1] is not None
    assert result["lod_distance_pct"][-1] >= 0


def test_calculate_lod_empty_data():
    """Test LoD calculation with empty data."""
    result = calculate_lod([], [], [], atr_window=14)

    assert result["lod_distance_pct"] == []
    assert result["current_price"] == []
    assert result["low_of_day"] == []
    assert result["atr"] == []


def test_calculate_lod_insufficient_data():
    """Test LoD calculation with insufficient data for ATR."""
    # Less than atr_window bars
    highs = [100.0] * 10
    lows = [95.0] * 10
    closes = [102.0] * 10

    result = calculate_lod(highs, lows, closes, atr_window=14)

    assert len(result["lod_distance_pct"]) == 10
    # Should return values (ATR calculator handles this)
    assert result["lod_distance_pct"][-1] is not None


def test_calculate_lod_zero_atr():
    """Test LoD calculation with zero ATR (flat prices)."""
    # All prices are the same (should result in ATR of 0)
    highs = [100.0] * 20
    lows = [100.0] * 20
    closes = [100.0] * 20

    result = calculate_lod(highs, lows, closes, atr_window=14)

    # ATR might be zero or very small
    assert result["lod_distance_pct"][-1] is None or result["lod_distance_pct"][-1] >= 0


def test_calculate_lod_none_values():
    """Test LoD calculation with None values in data."""
    highs = [100.0, 105.0, None, 110.0] + [115.0] * 16
    lows = [95.0, 95.0, None, 100.0] + [105.0] * 16
    closes = [102.0, 100.0, None, 105.0] + [110.0] * 16

    result = calculate_lod(highs, lows, closes, atr_window=14)

    assert len(result["lod_distance_pct"]) == 20
    # Should handle None values gracefully
    assert result["lod_distance_pct"][2] is None


def test_calculate_lod_close_below_low():
    """Test LoD calculation when close is below low (edge case)."""
    # Edge case: close below low (should be clamped to 0)
    highs = [105.0] * 20
    lows = [95.0] * 20
    closes = [90.0] * 20  # Close is below low

    result = calculate_lod(highs, lows, closes, atr_window=14)

    # LoD distance should be clamped to 0
    assert result["lod_distance_pct"][-1] == 0.0


def test_calculate_lod_different_atr_windows():
    """Test LoD calculation with different ATR window sizes."""
    highs = [100 + i * 0.5 for i in range(20)]
    lows = [95 + i * 0.5 for i in range(20)]
    closes = [102 + i * 0.5 for i in range(20)]

    result_5 = calculate_lod(highs, lows, closes, atr_window=5)
    result_14 = calculate_lod(highs, lows, closes, atr_window=14)

    # Both should produce valid results
    assert result_5["lod_distance_pct"][-1] is not None
    assert result_14["lod_distance_pct"][-1] is not None

    # Different ATR windows should give different results
    assert result_5["atr"][-1] != result_14["atr"][-1]


def test_calculate_lod_mismatched_lengths():
    """Test LoD calculation with mismatched input lengths."""
    highs = [100.0] * 20
    lows = [95.0] * 15  # Different length
    closes = [102.0] * 20

    result = calculate_lod(highs, lows, closes, atr_window=14)

    # Should return all None values
    assert all(v is None for v in result["lod_distance_pct"])


def test_calculate_lod_zero_window():
    """Test LoD calculation with zero ATR window."""
    highs = [100.0] * 20
    lows = [95.0] * 20
    closes = [102.0] * 20

    result = calculate_lod(highs, lows, closes, atr_window=0)

    # Should return all None values
    assert all(v is None for v in result["lod_distance_pct"])


def test_calculate_lod_negative_window():
    """Test LoD calculation with negative ATR window."""
    highs = [100.0] * 20
    lows = [95.0] * 20
    closes = [102.0] * 20

    result = calculate_lod(highs, lows, closes, atr_window=-5)

    # Should return all None values
    assert all(v is None for v in result["lod_distance_pct"])


def test_calculate_lod_single_bar():
    """Test LoD calculation with single bar."""
    result = calculate_lod([100.0], [95.0], [102.0], atr_window=14)

    assert len(result["lod_distance_pct"]) == 1
    # Should return as ATR calculator handles single value
    assert result["lod_distance_pct"][0] is not None


def test_calculate_lod_returns_all_data():
    """Test that LoD calculator returns current_price, low_of_day, and atr."""
    highs = [100 + i * 0.5 for i in range(20)]
    lows = [95 + i * 0.5 for i in range(20)]
    closes = [102 + i * 0.5 for i in range(20)]

    result = calculate_lod(highs, lows, closes, atr_window=14)

    # Verify all required fields are present
    assert "lod_distance_pct" in result
    assert "current_price" in result
    assert "low_of_day" in result
    assert "atr" in result

    # Verify they are lists
    assert isinstance(result["lod_distance_pct"], list)
    assert isinstance(result["current_price"], list)
    assert isinstance(result["low_of_day"], list)
    assert isinstance(result["atr"], list)

    # Verify they have the same length
    assert len(result["lod_distance_pct"]) == len(result["current_price"])
    assert len(result["current_price"]) == len(result["low_of_day"])
    assert len(result["low_of_day"]) == len(result["atr"])


def test_calculate_lod_with_decreasing_prices():
    """Test LoD calculation with decreasing prices."""
    # Price declining trend
    highs = [110.0 - i * 0.5 for i in range(20)]
    lows = [105.0 - i * 0.5 for i in range(20)]
    closes = [108.0 - i * 0.5 for i in range(20)]

    result = calculate_lod(highs, lows, closes, atr_window=14)

    # Should still produce valid LoD distance
    assert result["lod_distance_pct"][-1] is not None
    assert result["lod_distance_pct"][-1] >= 0


def test_calculate_lod_with_volatile_prices():
    """Test LoD calculation with highly volatile prices."""
    # Highly volatile pattern
    highs = [100 + (i % 3) * 10 for i in range(20)]
    lows = [95 + (i % 3) * 10 for i in range(20)]
    closes = [97 + (i % 3) * 10 for i in range(20)]

    result = calculate_lod(highs, lows, closes, atr_window=14)

    # Should produce valid results
    assert result["lod_distance_pct"][-1] is not None
    assert result["atr"][-1] is not None
