# Deviation Magnet Indicator - Visual Guide

## Main Indicator Panel (Normalized Price)

```
Y-Axis (Deviation Levels)
│
│  +3.0 ──────────────────────────────────────── (Green line - Strong bullish)
│    ↑
│    │  ╱╲
│    │ ╱  ╲
│    │╱    ╲
│  +2.0 ──────────────────────────────────────── (Lime line)
│    │      ╱╲
│    │     ╱  ╲
│    │    ╱    ╲
│  +1.0 ──────────────────────────────────────── (Green line)
│    │         ╱╲
│    │        ╱  ╲
│    │       ╱    ╲
│    │      ╱      ╲
│    │     ╱        ╲
│    │    ╱          ╲
│    │   ╱            ╲
│    │  ╱              ╲
│    │ ╱                ╲
│    │╱                  ╲
│   0.0 ──────────────────────────────────────── (Gray line - BASIS/ZERO)
│    │                    ╲
│    │                     ╲
│    │                      ╲
│    │                       ╲
│    │                        ╲
│    │                         ╲
│    │                          ╲
│    │                           ╲
│    │                            ╲
│    │                             ╲
│    │                              ╲
│    │                               ╲
│    │                                ╲
│    │                                 ╲
│    │                                  ╲
│    │                                   ╲
│  -1.0 ──────────────────────────────────────── (Red line)
│    │                                    ╲
│    │                                     ╲
│    │                                      ╲
│    │                                       ╲
│    │                                        ╲
│    │                                         ╲
│  -2.0 ──────────────────────────────────────── (Fuchsia line)
│    │                                          ╲
│    │                                           ╲
│    │                                            ╲
│  -3.0 ──────────────────────────────────────── (Red line - Strong bearish)
│
│  Legend:
│  ╱╲ = Normalized Price Line (Green when >0, Red when <0)
│  ▓▓ = Green filled area (price >= +1 deviation)
│  ▒▒ = Red filled area (price <= -1 deviation)
│  ▲  = Magnet Up Triangle (at Y=7)
│  ▼  = Magnet Down Triangle (at Y=-7.5)
│  ↑  = Magnet Up Label (at Y=9)
│  ↓  = Magnet Down Label (at Y=-9)
│  ↗  = Explosion Up Arrow (large, lime)
│  ↘  = Explosion Down Arrow (large, fuchsia)
│  →  = Bounce Arrow (small, red/green)
│  ↘  = Bounce Down Arrow (small, fuchsia)
│  ↗  = Bounce Up Arrow (small, lime)
```

## Visual Components Breakdown

### 1. Normalized Price Calculation
```
If ohlc4 > basis (SMA/EMA):
    price = (high - basis) × 2 / dev
    → Shows how many deviations ABOVE the basis
    
If ohlc4 <= basis:
    price = (low - basis) × 2 / dev  
    → Shows how many deviations BELOW the basis
```

### 2. Deviation Reference Lines

```
+3.0 ────────────────────────  Strong Bullish Zone
+2.0 ────────────────────────  Moderate Bullish Zone
+1.0 ────────────────────────  Mild Bullish Zone
 0.0 ────────────────────────  BASIS (SMA/EMA) - Neutral
-1.0 ────────────────────────  Mild Bearish Zone
-2.0 ────────────────────────  Moderate Bearish Zone
-3.0 ────────────────────────  Strong Bearish Zone
```

### 3. Filled Areas (Intensity Indicators)

```
Price >= +3:  ████████████████  Bright Lime (100% opacity)
Price >= +2:  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  Lime (30% opacity)
Price >= +1:  ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒  Green (60% opacity)
Price =  0:   ─────────────────  Gray (no fill)
Price <= -1:  ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒  Red (60% opacity)
Price <= -2:  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  Fuchsia (30% opacity)
Price <= -3:  ████████████████  Bright Fuchsia (100% opacity)
```

### 4. Magnet Signals (Price Sticking to Deviations)

```
MAGNET UP SIGNALS:
─────────────────────────────────────────────
Y=10  ↑  Lime Label    (up_break3 >= 0)  Strongest
Y=9   ↑  Green Label   (up_break >= 0)   Strong
Y=7   ▲  Green Triangle (up_break1 >= 0) Moderate

MAGNET DOWN SIGNALS:
─────────────────────────────────────────────
Y=-7.5 ▼  Red Triangle (low_break1 <= 0) Moderate
Y=-9  ↓  Red Label    (low_break <= 0)  Strong
Y=-10 ↓  Fuchsia Label (low_break3 <= 0) Strongest
```

### 5. Bounce/Resistance Arrows (when show_bounce=true)

```
CONDITIONS:
- Price breaks half deviation (up_break1 or low_break1)
- Squeeze conditions present (bounce1 or bounce2)

SIGNALS:
─────────────────────────────────────────────
↘  Fuchsia Down Arrow  (upper falling)     → Resistance/Bounce Down
↗  Lime Up Arrow       (lower rising)      → Support/Bounce Up
→  Red Right Arrow     (upper not falling) → Resistance Holding
→  Green Right Arrow   (lower not rising)  → Support Holding
```

### 6. Explosion Signals (Breakouts)

```
CONDITIONS:
- Price breaks FULL deviation (up_break or low_break)
- Had bounce conditions PREVIOUSLY (bounce1[1] or bounce2[1])
- NO bounce conditions NOW (not bounce1 and not bounce2)

SIGNALS:
─────────────────────────────────────────────
↗  Large Lime Arrow (up)    → EXPLOSION UP (breakout)
↘  Large Fuchsia Arrow (down) → EXPLOSION DOWN (breakdown)
```

### 7. Squeeze/Expansion Indicator (Lower Panel)

**There are TWO lines in the bottom panel, showing THREE colors:**

#### **TEAL/BLUE Line** (Squeeze Line - `sq`)
```pinescript
sq_color logic:
- Teal (bright): When squeeze is RISING AND top < sq
- Teal (dim): When squeeze is RISING AND top is FALLING  
- Olive: Otherwise (default/neutral state)

Meaning: Shows volatility COMPRESSION (squeeze)
- Lower values = More squeeze (volatility getting tighter)
- Higher values = Less squeeze (volatility expanding)
```

#### **GREEN/RED/ORANGE Line** (Expansion Line - `top`)
```pinescript
top_color logic:
- GREEN: When expansion is RISING AND top > sq AND price >= 0 (bullish expansion)
- RED: When expansion is RISING AND top > sq AND price < 0 (bearish expansion)
- GREEN (dim): When expansion is FALLING AND squeeze is FALLING AND price >= 0
- RED (dim): When expansion is FALLING AND squeeze is FALLING AND price < 0
- ORANGE: Otherwise (neutral/transition state)

Meaning: Shows volatility EXPANSION
- Higher values = More expansion (volatility increasing)
- Lower values = Less expansion (volatility decreasing)
```

#### Visual Representation:
```
Y-Axis (Squeeze/Expansion Scale)
│
│  -15 ────────────────────────────────────────
│    │
│    │  ╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲
│    │ ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱
│  -16 ──────────────────────────────────────── GREEN/RED/ORANGE Line (Expansion/Top)
│    │  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲
│    │   ╲╱    ╲╱    ╲╱    ╲╱    ╲╱    ╲╱    ╲╱
│  -17 ────────────────────────────────────────
│    │
│    │  ╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲
│    │ ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱
│  -18 ──────────────────────────────────────── TEAL/BLUE Line (Squeeze/sq)
│    │  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲
│    │   ╲╱    ╲╱    ╲╱    ╲╱    ╲╱    ╲╱    ╲╱
│  -19 ────────────────────────────────────────
│    │
│    │  ◇ Yellow Diamond = RELEASE (green/red/orange crosses above teal)
│    │  ◇ Purple Diamond = CONTRACT (green/red/orange crosses below teal)
│    │
│  -20 ────────────────────────────────────────
│
│  Color Meanings Summary:
│  ────────────────────────────────────────────
│  🔵 TEAL/BLUE (sq line):
│     • Shows volatility COMPRESSION (squeeze)
│     • Teal = Active squeeze conditions
│     • Olive = Neutral/default state
│
│  🟢 GREEN (top line):
│     • Bullish volatility EXPANSION
│     • Appears when: expansion rising + top > sq + price >= 0
│
│  🔴 RED (top line):
│     • Bearish volatility EXPANSION  
│     • Appears when: expansion rising + top > sq + price < 0
│
│  🟠 ORANGE (top line):
│     • Neutral/transition state
│     • Appears when conditions don't match green or red
│
│  💡 Key Insight:
│     When GREEN/RED line crosses above TEAL line = RELEASE (volatility breakout)
│     When GREEN/RED line crosses below TEAL line = CONTRACT (back into squeeze)
```

### 8. Background Colors

```
Green Background (95% transparent):
─────────────────────────────────────────────
When: price > 0 (normalized price above zero)
Meaning: Bullish/Bullish zone

Red Background (95% transparent):
─────────────────────────────────────────────
When: price < 0 (normalized price below zero)
Meaning: Bearish/Bearish zone
```

### 9. Bar Colors (when color_bars=true)

```
Sensitivity = 3 (Strongest signals only):
  Lime bars:    up_break3 >= 0 (1.5x deviation break)
  Fuchsia bars: low_break3 <= 0 (1.5x deviation break)

Sensitivity = 2 (Strong signals):
  Green bars:   up_break >= 0 (full deviation break)
  Red bars:     low_break <= 0 (full deviation break)

Sensitivity = 1 (Moderate signals):
  Green bars:   up_break1 >= 0 (half deviation break)
  Red bars:     low_break1 <= 0 (half deviation break)

Sensitivity = 0 (All signals):
  Green bars:   price >= 0 (any positive price)
  Red bars:     price < 0 (any negative price)
```

## Filter Conditions Explained

### Simple Filters:
```
price_above_zero / price_green:
  ✅ price > 0  → Green background/area
  ❌ price <= 0 → Filtered out

price_below_zero / price_red:
  ✅ price < 0  → Red background/area
  ❌ price >= 0 → Filtered out
```

### Pine Script Bar Coloring Filter:
```
bullish_pinescript:
  Uses boost1/boost2 conditions + sensitivity
  More selective than simple price > 0
  
  Sensitivity 3: Only 1.5x deviation breaks
  Sensitivity 2: Full deviation breaks
  Sensitivity 1: Half deviation breaks
  Sensitivity 0: Any price >= 0

bearish_pinescript:
  Same logic but for bearish conditions
```

### Signal-Based Filters:
```
magnet_up:        ▲ or ↑ appears (price sticking to upper deviation)
magnet_down:      ▼ or ↓ appears (price sticking to lower deviation)
explosion_up:     ↗ Large lime arrow (breakout upward)
explosion_down:   ↘ Large fuchsia arrow (breakdown downward)
bounce_up:        ↗ Small lime arrow (support bounce)
bounce_down:      ↘ Small fuchsia arrow (resistance bounce)
```

### Expansion-Based Filters:
```
expansion_bullish:              Green expansion line active (any green)
expansion_bullish_rising:       Bright green expansion rising (strong bullish)
expansion_bullish_rising_any:   Green line rising (dim or bright - includes all green rising)
expansion_bullish_rising_green_only: Green rising WITHOUT yellow/release (excludes late signals - BEST for early entries)

💡 Key Difference:
- expansion_bullish_rising_any: May include yellow/release signals (late)
- expansion_bullish_rising_green_only: Only green rising, excludes yellow (early signal)
```

## Complete Visual Example

```
MAIN PANEL:
─────────────────────────────────────────────────────────────
+3.0 ────────────────────────────────────────────────────────
      │
      │  ╱╲                    ▲ (Magnet Up)
      │ ╱  ╲                  ↗ (Explosion)
+2.0 ─┼─╱────╲──────────────────────────────────────────────
      │╱      ╲
+1.0 ─┼────────╲──────────────────────────────────────────────
      │         ╲
      │          ╲
      │           ╲
 0.0 ─┼────────────╲──────────────────────────────────────────────
      │             ╲
      │              ╲
      │               ╲
      │                ╲
-1.0 ─┼─────────────────╲──────────────────────────────────────────────
      │                  ╲
      │                   ╲
      │                    ╲
      │                     ╲
-2.0 ─┼──────────────────────╲──────────────────────────────────────────────
      │                       ╲
      │                        ╲
      │                         ▼ (Magnet Down)
-3.0 ─┼──────────────────────────╲──────────────────────────────────────────────
      │                            ↘ (Explosion Down)

LOWER PANEL (Squeeze/Expansion):
─────────────────────────────────────────────────────────────
-15 ────────────────────────────────────────────────────────
     │
     │  ╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲
     │ ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱
-16 ─┼─╲───╱─╲───╱─╲───╱─╲───╱─╲───╱─╲───╱─╲─── (Orange - Expansion)
     │  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲
     │   ╲╱    ╲╱    ╲╱    ╲╱    ╲╱    ╲╱    ╲╱
-17 ─┼───────────────────────────────────────────────────────
     │
     │  ╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲
     │ ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱
-18 ─┼─╲───╱─╲───╱─╲───╱─╲───╱─╲───╱─╲───╱─╲─── (Blue - Squeeze)
     │  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲  ╱  ╲
     │   ╲╱    ╲╱    ╲╱    ╲╱    ╲╱    ╲╱    ╲╱
-19 ─┼───────────────────────────────────────────────────────
     │
     │  ◇ Yellow Diamond = RELEASE
-20 ─┼───────────────────────────────────────────────────────
```

## Key Concepts

1. **Magnet Effect**: Price "sticks" to deviation levels rather than bouncing off them
2. **Normalized Price**: Shows price position relative to standard deviations (not absolute price)
3. **Squeeze/Expansion**: Measures volatility compression and expansion
4. **Release**: When volatility breaks out from squeeze (yellow diamond)
5. **Explosion**: Strong breakout signals when bounce conditions end

## Filter Usage Guide

- **Simple filtering**: Use `price_above_zero` or `price_below_zero` for basic green/red filtering
- **Advanced filtering**: Use `bullish_pinescript` or `bearish_pinescript` with sensitivity for Pine Script matching
- **Signal filtering**: Use `magnet_up`, `explosion_up`, etc. for specific signal types

