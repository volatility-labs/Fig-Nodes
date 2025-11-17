# Improved Chart Analysis Prompt

Please analyze the provided cryptocurrency chart images which include:
- Most recent price action with candlesticks
- Volume bars
- EMA lines (10, 30, and 100 periods) with numeric value annotations
- Hurst Spectral Analysis Oscillator data
- MESA Stochastic Multi Length indicators
- Cycle Channel Oscillator (CCO) - Fast and Slow oscillators
- Longer-term historical Hurst, MESA, CCO, and OHLCV data

## ANALYSIS INSTRUCTIONS:

**All indicators carry equal weight** - Do not prioritize one indicator over others. Look for symbols where multiple indicators align positively.

### EMA Relationship Verification (Important - Use Numeric Values):
1. **Always check the RIGHT SIDE of each chart** (most recent data) to determine current EMA relationships
2. **Verify EMA relationships using the NUMERIC VALUES** shown in the annotations at the end of each EMA line:
   - Look for labels like "EMA 10: $X.XX", "EMA 30: $X.XX", "EMA 100: $X.XX"
   - Compare these numeric values directly - higher value = higher position on chart
3. **A "butterfly pattern" requires ALL THREE conditions to be true:**
   - EMA 10 value > EMA 30 value
   - EMA 30 value > EMA 100 value
   - EMA 10 value > EMA 100 value
4. **Do NOT assume EMAs are above the 100 EMA just because:**
   - Price is rising
   - The chart looks bullish visually
   - Short-term EMAs appear to be trending up
5. **Always verify by explicitly comparing the numeric values** from the annotations

### Analysis Criteria:

**For each symbol, provide equal analysis weight to all indicators:**

1. **EMA Analysis** (Equal Weight):
   - Current EMA Values (from annotations): EMA 10: $X.XX, EMA 30: $X.XX, EMA 100: $X.XX
   - EMA Relationship: "EMA 10 is [above/below] EMA 30, EMA 30 is [above/below] EMA 100"
   - EMA Stage: [Convergence/Recent Crosses/Butterfly/Spread-Expansion]
   - Recent Crosses: [Note any recent crosses of shorter-term EMAs over longer-term EMAs]
   - Butterfly pattern status: Only if EMA 10 > EMA 30 > EMA 100 (all true)
   - Note: EMAs can still be bullish even if below 100 EMA if other indicators support

2. **Price Action** (Equal Weight):
   - Recent trend direction and momentum strength
   - Current price relative to EMAs
   - Price pattern formations

3. **Volume Analysis** (Equal Weight):
   - Volume trends and spikes
   - Volume supporting price movement
   - Volume relative to recent averages

4. **Hurst Analysis** (Equal Weight):
   - Composite oscillator direction and strength
   - Period-specific signals (5, 10, 20, 40, 80 day)
   - Oscillator position relative to zero
   - Multiple period alignments

5. **MESA Stochastic** (Equal Weight):
   - Multi-length indicator positions (MESA1, MESA2, MESA3, MESA4)
   - Trigger line relationships
   - Momentum direction and strength
   - Stochastic position and trend

6. **Cycle Channel Oscillator - CCO** (Equal Weight):
   - Fast Oscillator: Price position within medium-term channel (0.0 to 1.0 range)
   - Slow Oscillator: Short cycle midline position within medium-term channel (0.0 to 1.0 range)
   - Oscillator relationships: **Fast Osc ABOVE Slow Osc = BULLISH** (positive momentum), **Fast Osc BELOW Slow Osc = BEARISH** (negative momentum)
   - Both oscillators trending upward = bullish signal, both trending downward = bearish signal
   - Extreme conditions: Values above 1.0 (overbought) or below 0.0 (oversold) - highlighted in purple
   - Position relative to key levels (0.0, 0.5, 1.0)
   - Note: Similar to %b oscillator - Fast Osc shows price location, Slow Osc acts as signal line

### Ranking Criteria (Equal Weight - All Indicators Matter):

**1. EMA Analysis (Equal Weight):**
   - EMA progression stages (all are positive signals):
     * Convergence: Shorter-term EMAs (10, 30) coming together
     * Crosses: Recent crosses of shorter-term EMAs over longer-term EMAs (e.g., EMA 10 crossing above EMA 30, EMA 30 crossing above EMA 100)
     * Butterfly: EMAs "butterflying" above longer-term EMA (100) - meaning EMA 10 > EMA 30 > EMA 100
     * Spread/Expansion: Butterfly pattern expanding (butterfly in early stages preferred, not over-extended)
   - Look for symbols in any of these stages, with recent crosses being particularly positive
   - Verify using numeric values from annotations
   - Note: EMAs below 100 EMA can still be bullish if other indicators align

**2. Price Action & Volume (Equal Weight):**
   - Recent upward price movement and momentum
   - Increasing volume supporting the move
   - Price breaking above key EMAs (verify with values)
   - Volume spikes indicating strong interest

**3. Hurst Analysis (Equal Weight):**
   - Composite oscillator trending upward
   - Period-specific signals showing momentum
   - Oscillator position relative to zero line
   - Multiple period alignments

**4. MESA Stochastic (Equal Weight):**
   - Multi-length indicator showing upward momentum
   - Shorter MESA lengths above longer lengths
   - Trigger line relationships
   - Stochastic position and trend direction

**5. Cycle Channel Oscillator - CCO (Equal Weight):**
   - **Fast Osc ABOVE Slow Osc = BULLISH** (positive momentum signal)
   - **Fast Osc BELOW Slow Osc = BEARISH** (negative momentum signal)
   - Both oscillators trending upward = bullish signal
   - Both oscillators trending downward = bearish signal
   - Both oscillators above 0.5 (midline) indicating bullish channel position
   - Avoid extreme conditions (above 1.0 overbought, below 0.0 oversold) unless showing reversal
   - Early-stage upward trends preferred over over-extended conditions

**6. Overall Momentum & Convergence (Equal Weight):**
   - Multiple indicators aligning in the same direction
   - Early-stage patterns (not over-extended)
   - Strong confirmation across all indicators
   - Divergences or conflicts between indicators should be noted

### Output Format:

For each symbol in your top 3 predictions, provide:

**Symbol: [SYMBOL]**

**EMA Analysis** (Equal Weight):
- EMA 10: $X.XX, EMA 30: $X.XX, EMA 100: $X.XX
- Relationship: EMA 10 [above/below] EMA 30 [above/below] EMA 100
- EMA Stage: [Convergence/Recent Crosses/Butterfly/Spread-Expansion]
- Recent Crosses: [Note any recent crosses of shorter-term EMAs over longer-term EMAs - this is a positive signal]
- Butterfly Pattern: [Yes/No - only Yes if all three EMAs are in ascending order]
- Assessment: [Bullish/Neutral/Bearish signal strength]

**Price Action** (Equal Weight):
- [Recent trend direction, momentum strength, pattern formations]

**Volume Analysis** (Equal Weight):
- [Volume trends, spikes, support for price movement]

**Hurst Analysis** (Equal Weight):
- [Composite oscillator direction, period-specific signals, alignment]

**MESA Stochastic** (Equal Weight):
- [Multi-length positions, trigger relationships, momentum direction]

**Cycle Channel Oscillator - CCO** (Equal Weight):
- Fast Osc: [Current value, position in channel (0.0-1.0), trend direction]
- Slow Osc: [Current value, position in channel (0.0-1.0), trend direction]
- Relationship: [Fast Osc ABOVE Slow Osc = BULLISH, Fast Osc BELOW Slow Osc = BEARISH]
- Trend: [Both oscillators trending upward = bullish, both trending downward = bearish]
- Extreme Conditions: [Any values above 1.0 (overbought) or below 0.0 (oversold) - highlighted in purple]
- Assessment: [Bullish/Neutral/Bearish signal strength based on oscillator positions and relationship]

**Overall Assessment** (Equal Weight to All Indicators):
- [Synthesis of all indicators - why this symbol ranks in top 3]
- [Indicator alignment: Strong/Moderate/Weak]
- [Any conflicting signals between indicators]

**Risk Considerations:**
- [Any concerns, limitations, or conflicting signals]

---

**Final Ranking:**
1. [Top symbol] - [Brief reason]
2. [Second symbol] - [Brief reason]
3. [Third symbol] - [Brief reason]

**Important Disclaimers:**
- These are predictions based on technical analysis only
- Cryptocurrency markets are highly volatile
- Always use proper risk management
- This is not financial advice

