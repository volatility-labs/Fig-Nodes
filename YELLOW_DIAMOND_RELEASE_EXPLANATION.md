# Yellow Diamond "Release" Signal Explanation

## What It Means

The **Yellow Diamond** appears when the **Expansion line (`top`)** crosses **above** the **Squeeze line (`sq`)**. This signals a **"RELEASE"** - volatility is breaking out from compression.

## Visual Example

```
Lower Panel (Squeeze/Expansion Indicator):
─────────────────────────────────────────────────────────────

Time →     Bar 1    Bar 2    Bar 3    Bar 4    Bar 5
           ──────   ──────   ──────   ──────   ──────

-15 ────────────────────────────────────────────────────────
     │
     │                    ╱╲
     │                   ╱  ╲
-16 ─┼──────────────────╱────╲──────────────────────────────
     │                 ╱      ╲
     │                ╱        ╲
     │               ╱          ╲
     │              ╱            ╲
     │             ╱              ╲
     │            ╱                ╲
     │           ╱                  ╲
     │          ╱                    ╲
     │         ╱                      ╲
     │        ╱                        ╲
     │       ╱                          ╲
     │      ╱                            ╲
-17 ─┼─────╱──────────────────────────────╲──────────────────
     │    ╱                              ╲
     │   ╱                                ╲
     │  ╱                                  ╲
     │ ╱                                    ╲
     │╱                                      ╲
-18 ─┼────────────────────────────────────────╲──────────────
     │                                        ╲
     │                                         ╲
     │                                          ╲
     │                                           ╲
     │                                            ╲
     │                                             ╲
     │                                              ╲
     │                                               ╲
-19 ─┼────────────────────────────────────────────────╲───────
     │                                                ╲
     │                                                 ╲
     │                                                  ╲
     │                                                   ╲
-20 ─┼────────────────────────────────────────────────────╲───
     │                                                    ╲
     │                                                     ╲
     │                                                      ╲
     │                                                       ╲
-21 ─┼────────────────────────────────────────────────────────╲
     │
     │  Legend:
     │  ╱╲ = Expansion line (top) - GREEN/RED/ORANGE
     │  ╱╲ = Squeeze line (sq) - TEAL/BLUE
     │  ◇  = Yellow Diamond (RELEASE signal)
     │
     │  In Bar 3: Expansion crosses ABOVE Squeeze → ◇ Yellow Diamond appears!
```

## The Two Lines Explained

### 1. **Squeeze Line (`sq`)** - TEAL/BLUE
- **What it shows**: Volatility **COMPRESSION** (getting tighter)
- **Lower values** = More squeeze (volatility is compressed)
- **Higher values** = Less squeeze (volatility is expanding)
- **Think of it as**: A rubber band being squeezed tighter

### 2. **Expansion Line (`top`)** - GREEN/RED/ORANGE
- **What it shows**: Volatility **EXPANSION** (increasing)
- **Higher values** = More expansion (volatility is increasing)
- **Lower values** = Less expansion (volatility is decreasing)
- **Think of it as**: The rubber band being stretched

## What Happens When They Cross

### Before the Cross (Squeeze Active):
```
Expansion Line (top):  -18.5  (below)
Squeeze Line (sq):     -17.0  (above)
───────────────────────────────────────
Result: top < sq → Volatility is COMPRESSED (squeezed)
```

### At the Cross (Release Signal):
```
Previous Bar:
  Expansion Line (top):  -18.5  (below squeeze)
  Squeeze Line (sq):     -17.0  (above expansion)
  
Current Bar:
  Expansion Line (top):  -16.5  (crossed above!)
  Squeeze Line (sq):     -17.0  (now below expansion)
───────────────────────────────────────
Result: top[1] < sq[1] AND top >= sq → ◇ YELLOW DIAMOND!
```

### After the Cross (Volatility Released):
```
Expansion Line (top):  -16.0  (above)
Squeeze Line (sq):     -17.0  (below)
───────────────────────────────────────
Result: top > sq → Volatility has EXPANDED (released)
```

## Trading Interpretation

### Yellow Diamond (Release) = **Volatility Breakout**

**What it means:**
- Volatility was **compressed** (squeezed) → price was trading in a tight range
- Volatility is now **expanding** → price is breaking out of that range
- This often precedes **significant price moves**

**Trading implications:**
- ✅ **Potential for big moves**: After compression, expansion often leads to strong directional moves
- ✅ **Momentum building**: The release suggests momentum is building
- ⚠️ **Not directional**: The yellow diamond doesn't tell you UP or DOWN, just that volatility is expanding
- 💡 **Look for confirmation**: Combine with price action (green/red expansion line) to determine direction

### Purple Diamond (Contract) = **Back Into Squeeze**

**What it means:**
- Volatility was **expanded** → price was moving
- Volatility is now **compressing** → price is consolidating again
- This often precedes **periods of low volatility**

**Trading implications:**
- ⚠️ **Consolidation ahead**: Price may enter a tight trading range
- ⚠️ **Wait for next release**: May want to wait for the next yellow diamond before entering
- ⚠️ **Momentum fading**: The move may be losing steam
- 💡 **Exit signal**: Consider taking profits if you're in a trade

## Code Logic

```python
# Release: top[1] < sq[1] and top >= sq
# Meaning: Expansion was BELOW squeeze, now it's ABOVE squeeze

release = (
    top_prev < sq_prev    # Previous bar: expansion was below squeeze
    and top_curr >= sq_curr  # Current bar: expansion is now above squeeze
)
```

## Real-World Analogy

Think of it like a **spring**:

1. **Squeeze Active** (top < sq):
   - Spring is compressed → waiting for release
   - Price is trading in a tight range
   - Volatility is low

2. **Yellow Diamond** (top crosses above sq):
   - Spring is released! → BOOM!
   - Price breaks out of the range
   - Volatility expands rapidly

3. **After Release** (top > sq):
   - Spring has expanded → momentum in motion
   - Price is moving with increased volatility
   - Direction depends on whether expansion line is green (bullish) or red (bearish)

## Purple Diamond "Contract" Signal - Detailed Explanation

### What It Means

The **Purple Diamond** appears when the **Expansion line (`top`)** crosses **below** the **Squeeze line (`sq`)**. This signals a **"CONTRACT"** - volatility is compressing back into a squeeze.

### Visual Example

```
Lower Panel (Squeeze/Expansion Indicator):
─────────────────────────────────────────────────────────────

Time →     Bar 1    Bar 2    Bar 3    Bar 4    Bar 5
           ──────   ──────   ──────   ──────   ──────

-15 ────────────────────────────────────────────────────────
     │
     │  ╱╲
     │ ╱  ╲
-16 ─┼─╱────╲──────────────────────────────────────────────
     │╱      ╲
     │        ╲
     │         ╲
     │          ╲
     │           ╲
     │            ╲
     │             ╲
     │              ╲
     │               ╲
     │                ╲
     │                 ╲
-17 ─┼──────────────────╲──────────────────────────────────
     │                   ╲
     │                    ╲
     │                     ╲
     │                      ╲
     │                       ╲
     │                        ╲
     │                         ╲
     │                          ╲
     │                           ╲
     │                            ╲
     │                             ╲
     │                              ╲
     │                               ╲
     │                                ╲
     │                                 ╲
-18 ─┼───────────────────────────────────╲──────────────────
     │                                    ╲
     │                                     ╲
     │                                      ╲
     │                                       ╲
     │                                        ╲
     │                                         ╲
     │                                          ╲
     │                                           ╲
     │                                            ╲
-19 ─┼──────────────────────────────────────────────╲───────
     │                                               ╲
     │                                                ╲
     │                                                 ╲
     │                                                  ╲
-20 ─┼───────────────────────────────────────────────────╲─
     │
     │  ◇ Purple Diamond appears here!
     │  (when expansion crosses below squeeze)
```

### What Happens When They Cross (Contract)

### Before the Cross (Expansion Active):
```
Expansion Line (top):  -16.5  (above)
Squeeze Line (sq):     -17.0  (below)
───────────────────────────────────────
Result: top > sq → Volatility is EXPANDED
```

### At the Cross (Contract Signal):
```
Previous Bar:
  Expansion Line (top):  -16.5  (above squeeze)
  Squeeze Line (sq):     -17.0  (below expansion)
  
Current Bar:
  Expansion Line (top):  -17.5  (crossed below!)
  Squeeze Line (sq):     -17.0  (now above expansion)
───────────────────────────────────────
Result: top[1] > sq[1] AND top <= sq → ◇ PURPLE DIAMOND!
```

### After the Cross (Volatility Contracted):
```
Expansion Line (top):  -18.0  (below)
Squeeze Line (sq):     -17.0  (above)
───────────────────────────────────────
Result: top < sq → Volatility has COMPRESSED (contracted)
```

### Trading Interpretation - Purple Diamond

**Purple Diamond (Contract) = Volatility Compression**

**What it means:**
- Volatility was **expanded** → price was moving with high volatility
- Volatility is now **compressing** → price is consolidating into a tight range
- This often precedes **periods of low volatility** and sideways movement

**Trading implications:**
- ⚠️ **Consolidation ahead**: Price may enter a tight trading range (choppy/sideways)
- ⚠️ **Momentum fading**: The previous move may be losing steam
- ⚠️ **Wait for next release**: May want to wait for the next yellow diamond before entering new trades
- 💡 **Exit signal**: Consider taking profits if you're in a trade (the move may be ending)
- 💡 **Range trading**: Price may bounce between support/resistance levels
- ⚠️ **Avoid new entries**: Not ideal for entering new positions (wait for next release)

### Code Logic

```python
# Contract: top[1] > sq[1] and top <= sq
# Meaning: Expansion was ABOVE squeeze, now it's BELOW squeeze

contract = (
    top_prev > sq_prev    # Previous bar: expansion was above squeeze
    and top_curr <= sq_curr  # Current bar: expansion is now below squeeze
)
```

### Real-World Analogy - Purple Diamond

Think of it like a **spring** that was released:

1. **Expansion Active** (top > sq):
   - Spring was released → price was moving
   - Volatility was high
   - Momentum was strong

2. **Purple Diamond** (top crosses below sq):
   - Spring is being compressed again → consolidation
   - Price movement is slowing down
   - Volatility is decreasing

3. **After Contract** (top < sq):
   - Spring is compressed → waiting for next release
   - Price is trading in a tight range
   - Volatility is low
   - **Waiting for the next yellow diamond** to signal the next move

### Complete Cycle Example

```
1. Yellow Diamond (Release):
   ────────────────────────────────
   Expansion crosses ABOVE squeeze
   → Volatility expands
   → Price breaks out
   → Strong directional move

2. Expansion Active:
   ────────────────────────────────
   Expansion stays ABOVE squeeze
   → Volatility remains high
   → Price continues moving
   → Momentum continues

3. Purple Diamond (Contract):
   ────────────────────────────────
   Expansion crosses BELOW squeeze
   → Volatility compresses
   → Price consolidates
   → Move loses momentum

4. Squeeze Active:
   ────────────────────────────────
   Expansion stays BELOW squeeze
   → Volatility remains low
   → Price trades in tight range
   → Waiting for next release

5. Back to Step 1 (Yellow Diamond):
   ────────────────────────────────
   Cycle repeats!
```

## Summary

### Yellow Diamond = RELEASE
- Expansion line crosses **above** squeeze line
- Signals volatility **breakout** from compression
- Often precedes **significant price moves**
- Look for **green expansion line** for bullish moves, **red expansion line** for bearish moves
- **Good for entry signals** (when combined with price direction)

### Purple Diamond = CONTRACT
- Expansion line crosses **below** squeeze line
- Signals volatility **compression** back into squeeze
- Often precedes **consolidation** and sideways movement
- **Good for exit signals** (consider taking profits)
- **Not ideal for new entries** (wait for next yellow diamond)

