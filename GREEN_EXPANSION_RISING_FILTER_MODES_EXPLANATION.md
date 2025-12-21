# Green Expansion Rising Filter Modes - Detailed Explanation

## Overview

The Green Expansion Rising Filter has two modes that determine which green expansion signals to filter for. The difference lies in **which type of green expansion line** triggers the filter.

## Understanding Green Expansion Lines

In TradingView's Squeeze-Expansion indicator, the expansion line (`top`) can appear in **two shades of green**:

### 1. **Bright Green (Strong Bullish Expansion)**
- **Color**: Bright green/lime (`color.lime, 0` in Pine Script)
- **Condition**: `rising(top,1) AND top > sq AND price >= 0`
- **Meaning**: 
  - Expansion line is **rising** (volatility increasing)
  - Expansion is **above** squeeze line (volatility has broken out)
  - Normalized price is **above zero** (bullish price action)
- **Signal Strength**: **STRONG** - Active bullish momentum with volatility expansion

### 2. **Dim Green (Weak Bullish Expansion)**
- **Color**: Dim green (`color.green, 25` in Pine Script)
- **Condition**: `falling(sq,1) AND price >= 0`
- **Meaning**:
  - Squeeze line is **falling** (volatility compression easing)
  - Normalized price is **above zero** (bullish price action)
  - Expansion line may be flat or not rising strongly
- **Signal Strength**: **WEAK** - Passive bullish (squeeze relaxing, but not strong expansion)

## Filter Mode Comparison

### Mode 1: `green_expansion_rising` (All Green Rising)

**What it catches:**
- ✅ **Bright green** expansion line that's rising (strong bullish)
- ✅ **Dim green** expansion line that's rising (weak bullish, but still rising)

**Logic:**
```python
# Any green expansion (bright OR dim) AND top is rising
expansion_bullish_rising_any = expansion_bull and top_rising
```

**Use Case:**
- More **sensitive** filter
- Catches **more signals** (both strong and weak)
- Good for catching **early** bullish expansion signals
- Includes dim green that's rising (like TRUMP coin example)

**Example Scenario:**
```
Time 1: Dim green appears (squeeze falling, price >= 0)
Time 2: Dim green starts rising → ✅ TRIGGERS green_expansion_rising
Time 3: Dim green continues rising → ✅ Still triggers
Time 4: Becomes bright green (top > sq) → ✅ Still triggers
```

### Mode 2: `green_expansion_rising_strong_only` (Strong Green Only)

**What it catches:**
- ✅ **Bright green** expansion line that's rising (strong bullish)
- ❌ **Dim green** expansion line (excluded, even if rising)

**Logic:**
```python
# Only bright green: rising(top,1) AND top>sq AND price>=0
expansion_bullish_rising = (
    top_rising
    and top_curr > sq_curr
    and p >= 0
)
```

**Use Case:**
- More **selective** filter
- Catches **fewer signals** (only strong ones)
- Good for **high-quality** bullish expansion signals only
- Excludes weak/dim green signals

**Example Scenario:**
```
Time 1: Dim green appears (squeeze falling, price >= 0)
Time 2: Dim green starts rising → ❌ Does NOT trigger (dim green excluded)
Time 3: Dim green continues rising → ❌ Still doesn't trigger
Time 4: Becomes bright green (top > sq) → ✅ TRIGGERS green_expansion_rising_strong_only
```

## Visual Comparison

### TradingView Chart Representation:

```
Lower Panel (Squeeze/Expansion Indicator):
─────────────────────────────────────────────────────────────

-15 ────────────────────────────────────────────────────────
     │
     │  ╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲
     │ ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱
-16 ─┼─╲───╱─╲───╱─╲───╱─╲───╱─╲───╱─╲───╱─╲─── (Expansion Line)
     │  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲
     │   ╲╱    ╲╱    ╲╱    ╲╱    ╲╱    ╲╱    ╲╱
-17 ─┼───────────────────────────────────────────────────────
     │
     │  ╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲
     │ ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱
-18 ─┼─╲───╱─╲───╱─╲───╱─╲───╱─╲───╱─╲───╱─╲─── (Squeeze Line)
     │  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲
     │   ╲╱    ╲╱    ╲╱    ╲╱    ╲╱    ╲╱    ╲╱
-19 ─┼───────────────────────────────────────────────────────

Color Legend:
🟢 Bright Green: top rising + top > sq + price >= 0 (STRONG)
🟢 Dim Green: sq falling + price >= 0 (WEAK)
🟠 Orange: Other conditions
```

## When to Use Each Mode

### Use `green_expansion_rising` when:
- ✅ You want to catch **early** bullish expansion signals
- ✅ You want **more signals** (higher sensitivity)
- ✅ You're okay with some **weaker** signals mixed in
- ✅ You want to catch dim green that's starting to rise (like TRUMP coin)
- ✅ You're doing **exploratory** analysis

### Use `green_expansion_rising_strong_only` when:
- ✅ You want **high-quality** signals only
- ✅ You want **fewer, stronger** signals (higher precision)
- ✅ You want to avoid **false positives** from weak signals
- ✅ You're looking for **confirmed** bullish momentum (top > sq)
- ✅ You're doing **production** trading/filtering

## Real-World Example

### Scenario: UNI token showing green expansion rising

**Timeline:**
1. **Bar 1**: Dim green appears (squeeze falling, price >= 0)
   - `green_expansion_rising`: ❌ Not triggered (dim green not rising yet)
   - `green_expansion_rising_strong_only`: ❌ Not triggered

2. **Bar 2**: Dim green starts rising
   - `green_expansion_rising`: ✅ **TRIGGERED** (dim green rising)
   - `green_expansion_rising_strong_only`: ❌ Not triggered (dim green excluded)

3. **Bar 3**: Expansion crosses above squeeze (top > sq), becomes bright green
   - `green_expansion_rising`: ✅ **TRIGGERED** (bright green rising)
   - `green_expansion_rising_strong_only`: ✅ **TRIGGERED** (bright green rising)

4. **Bar 4**: Bright green continues rising
   - `green_expansion_rising`: ✅ **TRIGGERED**
   - `green_expansion_rising_strong_only`: ✅ **TRIGGERED**

## Summary Table

| Aspect | `green_expansion_rising` | `green_expansion_rising_strong_only` |
|--------|-------------------------|--------------------------------------|
| **Bright Green** | ✅ Included | ✅ Included |
| **Dim Green Rising** | ✅ Included | ❌ Excluded |
| **Signal Count** | More signals | Fewer signals |
| **Sensitivity** | Higher (more sensitive) | Lower (more selective) |
| **Precision** | Lower (includes weak signals) | Higher (only strong signals) |
| **Use Case** | Early detection, exploration | Production filtering, quality focus |
| **Best For** | Catching early moves | Confirmed momentum only |

## Code Reference

**Mode 1 (`green_expansion_rising`):**
```python
# Uses: expansion_bullish_rising_any
# Catches: Any green (bright OR dim) AND top is rising
expansion_bullish_rising_any = expansion_bull and top_rising
```

**Mode 2 (`green_expansion_rising_strong_only`):**
```python
# Uses: expansion_bullish_rising
# Catches: Only bright green (rising + top > sq + price >= 0)
expansion_bullish_rising = (
    top_rising
    and top_curr > sq_curr
    and p >= 0
)
```

