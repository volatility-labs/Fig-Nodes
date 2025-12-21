# Deviation Magnet vs TradingView Squeeze-Expansion Indicator Comparison

## Summary

**YES, the Deviation Magnet node is very similar to the TradingView Squeeze-Expansion (SE) indicator**, particularly in the squeeze portion and the rising green line expansion section. The core mathematical concepts are identical, with some differences in scaling and additional features.

## Core Calculations Comparison

### Squeeze Calculation (`sq`)

**TradingView SE Indicator:**
```pinescript
sq = 5 - dev / highest(dev, 50) * 5
```
- Range: 0 to 5
- Higher values = more squeeze (volatility compression)
- When `dev = highest`: `sq = 0` (no squeeze)
- When `dev = 0`: `sq = 5` (maximum squeeze)

**Deviation Magnet:**
```python
sq_val = -15 - (d / d_highest) * 5.0
```
- Range: -20 to -15 (negative offset)
- Lower values = more squeeze (same concept, inverted scale)
- When `dev = highest`: `sq = -20` (no squeeze)
- When `dev = 0`: `sq = -15` (maximum squeeze)

**Key Insight:** Both use `dev / highest(dev, 50)` - the mathematical relationship is identical, just with different scaling/offset.

### Expansion Calculation (`top`)

**TradingView SE Indicator:**
```pinescript
top = dev / lowest(dev, 50) - 1
```
- Range: 0 to positive infinity
- Higher values = more expansion (volatility increasing)
- When `dev = lowest`: `top = 0` (no expansion)
- When `dev >> lowest`: `top >> 0` (strong expansion)

**Deviation Magnet:**
```python
top_val = (d / d_lowest) - 21.0
```
- Range: -21 to positive infinity (negative offset)
- Higher values = more expansion (same concept)
- When `dev = lowest`: `top = -20` (no expansion)
- When `dev >> lowest`: `top >> -20` (strong expansion)

**Key Insight:** Both use `dev / lowest(dev, 50)` - the mathematical relationship is identical, just with different offset.

## Color Logic Comparison

### Squeeze Line Color (`sq_color`)

**TradingView SE Indicator:**
```pinescript
sq_color = rising(sq, 1) ? top < sq ? color_1 : falling_1 ? color_2 : color.olive : color.olive
```
- **Teal (bright)**: When squeeze is RISING AND top < sq
- **Teal (dim)**: When squeeze is RISING AND top is FALLING
- **Olive**: Otherwise (default/neutral)

**Deviation Magnet:**
- **Teal (bright)**: When squeeze is RISING AND top < sq ✅ **MATCHES**
- **Teal (dim)**: When squeeze is RISING AND top is FALLING ✅ **MATCHES**
- **Olive**: Otherwise ✅ **MATCHES**

**Result:** ✅ **IDENTICAL LOGIC**

### Expansion Line Color (`top_color`) - The Rising Green Line

**TradingView SE Indicator:**
```pinescript
top_color = rising(top, 1) ? top > sq ? price >= 0 ? color_3 : color_4 : 
   falling_2 ? price >= 0 ? color_5 : color_6 : color.orange : color.orange
```
- **GREEN (bright)**: `rising(top,1) AND top>sq AND price>=0` → Strong bullish expansion
- **RED (bright)**: `rising(top,1) AND top>sq AND price<0` → Strong bearish expansion
- **GREEN (dim)**: `falling(sq,1) AND price>=0` → Weak bullish (squeeze falling)
- **RED (dim)**: `falling(sq,1) AND price<0` → Weak bearish (squeeze falling)
- **ORANGE**: Otherwise (neutral/transition)

**Deviation Magnet:**
```python
# Case 1: Strong bullish - expansion rising + top > sq + price >= 0 (bright green)
expansion_bull_strong = (
    top_rising
    and top_curr > sq_curr
    and p >= 0
)

# Case 2: Weak bullish - squeeze falling + price >= 0 (dim green)
expansion_bull_weak = (
    sq_falling
    and p >= 0
)
```

- **GREEN (bright)**: `rising(top,1) AND top>sq AND price>=0` ✅ **MATCHES**
- **RED (bright)**: `rising(top,1) AND top>sq AND price<0` ✅ **MATCHES**
- **GREEN (dim)**: `falling(sq,1) AND price>=0` ✅ **MATCHES**
- **RED (dim)**: `falling(sq,1) AND price<0` ✅ **MATCHES**
- **ORANGE**: Otherwise ✅ **MATCHES**

**Result:** ✅ **IDENTICAL LOGIC**

## Release/Contract Signals

**TradingView SE Indicator:**
```pinescript
// Release: top[1] < sq[1] and top >= sq
plotshape(top[1] < sq[1] and top >= sq ? top : na, title="release", style=shape.diamond, color=color.yellow)

// Contract: top[1] > sq[1] and top <= sq
plotshape(top[1] > sq[1] and top <= sq ? top : na, title="contract", style=shape.diamond, color=color.purple)
```

**Deviation Magnet:**
```python
# Release: top[1] < sq[1] and top >= sq (expansion crosses above squeeze)
release = (
    top_prev < sq_prev
    and top_curr >= sq_curr
)

# Contract: top[1] > sq[1] and top <= sq (expansion crosses below squeeze)
contract = (
    top_prev > sq_prev
    and top_curr <= sq_curr
)
```

**Result:** ✅ **IDENTICAL LOGIC**

## Key Similarities

1. ✅ **Same core calculations**: Both use `dev / highest(dev, 50)` for squeeze and `dev / lowest(dev, 50)` for expansion
2. ✅ **Same color logic**: Identical conditions for teal/blue squeeze line and green/red/orange expansion line
3. ✅ **Same release signals**: Yellow diamond when expansion crosses above squeeze
4. ✅ **Same contract signals**: Purple diamond when expansion crosses below squeeze
5. ✅ **Same rising green line logic**: Green appears when `rising(top,1) AND top>sq AND price>=0`

## Key Differences

1. **Scaling/Offset**: 
   - TradingView uses 0-5 range for squeeze
   - Deviation Magnet uses -20 to -15 range (negative offset for visualization)

2. **Additional Features in Deviation Magnet**:
   - Magnet signals (price sticking to deviations)
   - Bounce signals (support/resistance bounces)
   - Explosion signals (breakouts after bounces)
   - More granular filter conditions

3. **Normalized Price Display**:
   - Deviation Magnet shows normalized price in main panel (price relative to deviations)
   - TradingView SE focuses on squeeze/expansion in lower panel

## Conclusion

**The Deviation Magnet node IS similar to the TradingView Squeeze-Expansion indicator**, especially:

1. ✅ **Squeeze portion**: Uses identical calculation (`dev / highest(dev, 50)`) and color logic
2. ✅ **Rising green line expansion**: Uses identical logic (`rising(top,1) AND top>sq AND price>=0`)

The Deviation Magnet is essentially an **enhanced version** of the SE indicator, adding:
- Normalized price visualization
- Magnet effect detection
- Bounce/explosion signals
- More filter options

But the **core squeeze/expansion mechanics are mathematically and logically identical** to the TradingView script you provided.

