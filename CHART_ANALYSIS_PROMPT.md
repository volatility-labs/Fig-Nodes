# Chart Analysis Prompt - Bullish Setup Identification

## CRITICAL: DATA ANALYSIS FIRST

**PRIMARY ANALYSIS METHOD**: You will receive structured numeric data values for each symbol, formatted as text. This data includes:
- **Most recent indicator values** (Hurst Composite, MESA Stochastic values, CCO Fast/Slow Oscillators, EMA values, Volume, VBP levels)
- **Historical data** (batched summaries and recent detailed bars)
- **Time-series data** showing trends and recent changes

**ANALYZE THE NUMERIC DATA VALUES FIRST** - Use the structured data to determine indicator values, trends, crossovers, and signal strength. The numeric values are the PRIMARY source of truth.

**Chart images are supplementary** - Charts can help visualize patterns, but your analysis MUST be based on the actual numeric data values provided in the formatted text data. Do NOT rely solely on visual chart interpretation.

**For each symbol, you will have:**
- Structured indicator data with numeric values (Hurst, MESA, CCO, EMAs, Volume, VBP)
- Most recent values (last 1-50 bars depending on configuration)
- Historical summaries (batched data for longer-term context)
- Chart images (for visual reference, but analyze data values first)

**CRITICAL**: When analyzing indicators, use the ACTUAL NUMERIC VALUES from the data, not just visual chart patterns. For example:
- Check MESA Stochastic VALUES (0.0-1.0) from the data, not just chart position
- Check CCO Fast/Slow Oscillator VALUES from the data, not just chart lines
- Check Hurst Composite VALUE (positive/negative) from the data, not just chart direction
- Compare EMA VALUES numerically, not just visually
- Use VBP price levels and volume percentages from the data, not just bar thickness

Please analyze ALL symbols provided. Each symbol includes structured numeric data with the most recent volume, EMAs, Hurst data, MESA stochastics, Cycle Channel Oscillator (CCO), and Volume-by-Price (VBP) data. Also included is longer-term Hurst, MESA, CCO, and OHLCV data. Chart images are provided for visual reference but analyze the numeric data values first.

## CRITICAL OBJECTIVE
After analyzing all symbols, select and report ONLY the TOP 3 BEST BULLISH (LONG) setups for short-term trading (next few hours to 1-2 days maximum).

**CRITICAL: Look ONLY for BULLISH (LONG) setups. Focus on signals indicating upward price movement. Rank the top 3 best bullish opportunities based on signal strength.**

**CRITICAL: Focus on VERY SHORT-TERM signals (next few hours to 1-2 days maximum). Prioritize immediate momentum, recent crosses, and current price action over longer-term patterns.**

## PRIMARY INDICATORS (Required - Use These to Determine Bullish/Bearish)

These three indicators are REQUIRED and carry PRIMARY WEIGHT in determining if a symbol is bullish or bearish. **PRIMARY INDICATORS determine the overall direction. Secondary indicators provide confirmation only.**

### 1. Hurst Spectral Analysis Oscillator (Composite) - PRIMARY INDICATOR

- **Assessment**: Above zero = Bullish momentum, Below zero = Bearish momentum
- **Multiple short-period alignments** (5, 10, 20 day) = Stronger signal than long-period alignments
- **Recent trend direction** (last 1-5 bars) = Most important for short-term signals
- **Composite value**: Positive = Bullish, Negative = Bearish

### 2. MESA Stochastic Multi Length - PRIMARY INDICATOR

**CHECK MOST RECENT DATA VALUES (last 1-3 bars) - this is what matters for next few hours**

**CRITICAL**: Use the ACTUAL NUMERIC VALUES from the structured data, not just visual chart patterns. Look at the most recent MESA1, MESA2, MESA3, MESA4 values and their trigger line values from the data.

- **MESA Stochastic values range from 0.0 to 1.0** (similar to standard stochastic oscillator)
- **IMMEDIATE CROSSOVER SIGNALS (Bullish - HIGHEST PRIORITY):**
  * Crossover in TOP HALF (above 0.5) = "PUMP" signal - STRONG BULLISH momentum for NEXT FEW HOURS
  * When MESA lines cross ABOVE their trigger lines in the upper half RIGHT NOW = Immediate buy signal
  * Recent crossovers (last 1-3 bars) are STRONGEST signals

- **AVOID BEARISH SIGNALS:**
  * Crossunder in BOTTOM HALF (below 0.5) = "DUMP" signal - STRONG BEARISH momentum
  * When MESA lines cross BELOW their trigger lines in the lower half RIGHT NOW = Bearish signal - AVOID
  * Recent crossunders (last 1-3 bars) = Bearish - DO NOT SELECT

- **GOOD ENTRY SIGNALS (IMMEDIATE ACTION):**
  * MESA lines turning UPWARD from LOW points (near 0.0 or in lower half) RIGHT NOW = Buy signal
  * Multiple MESA lines aligning and turning upward together in last 1-3 bars = STRONG BUY signal
  * Best entries: Lines oversold (low values) and beginning to reverse upward NOW

- **AVOID THESE:**
  * MESA lines turning DOWNWARD from HIGH points (near 1.0 or in upper half) RIGHT NOW = Bearish - AVOID
  * Multiple MESA lines aligning and turning downward together in last 1-3 bars = STRONG BEARISH - DO NOT SELECT
  * Lines overbought (high values) and beginning to reverse downward NOW = Bearish reversal - AVOID

- **CURRENT OVERBOUGHT/OVERSOLD (IMMEDIATE REVERSAL RISK):**
  * Values approaching or above 1.0 RIGHT NOW = Overbought - potential pullback in next few hours
  * Values approaching or below 0.0 RIGHT NOW = Oversold - potential bounce in next few hours

- **Multi-Length Alignment (CURRENT STATE):**
  * When MESA1, MESA2, MESA3, and MESA4 all align in same direction RIGHT NOW = STRONGEST immediate signal
  * Divergence between different MESA lengths = Weaker signal, potential reversal soon

- **Assessment**: Bullish crossovers in top half = Strong bullish, Bearish crossunders in bottom half = Strong bearish

### 3. Cycle Channel Oscillator (CCO) - PRIMARY INDICATOR

**CHECK MOST RECENT DATA VALUES (current values) - this determines next few hours direction**

**CRITICAL**: Use the ACTUAL NUMERIC VALUES from the structured data. Look at the most recent Fast Osc and Slow Osc values from the data and compare them numerically.

- **Fast Oscillator**: Price position within medium-term channel (0.0 to 1.0 range) - CURRENT value matters most
- **Slow Oscillator**: Short cycle midline position within medium-term channel (0.0 to 1.0 range) - CURRENT value matters most

- **IMMEDIATE RELATIONSHIP (RIGHT NOW):**
  * Fast Osc ABOVE Slow Osc RIGHT NOW = BULLISH momentum for next few hours
  * Fast Osc BELOW Slow Osc RIGHT NOW = BEARISH momentum for next few hours
  * Recent crossover (Fast crossing above Slow) = Strong buy signal
  * Recent crossunder (Fast crossing below Slow) = Strong sell signal

- **CURRENT TREND:**
  * Both oscillators trending upward RIGHT NOW = Bullish for next few hours
  * Both oscillators trending downward RIGHT NOW = Bearish for next few hours

- **IMMEDIATE EXTREME CONDITIONS:**
  * Values above 1.0 RIGHT NOW = Overbought - potential pullback in next few hours
  * Values below 0.0 RIGHT NOW = Oversold - potential bounce in next few hours

- **Assessment**: Fast Osc > Slow Osc = Bullish, Fast Osc < Slow Osc = Bearish

## SECONDARY INDICATORS (Use at Discretion Only - For Confirmation)

**SECONDARY INDICATORS provide confirmation and context but do NOT override PRIMARY indicators. Use them to strengthen or weaken confidence in PRIMARY indicator signals.**

### 4. EMA Analysis (Secondary - Use at Discretion)

**PREFERRED BUT NOT MANDATORY: EMA relationships are helpful for confirmation but not required for bullish signals.**

- **PREFERRED EMA Relationships (in order of preference):**
  * **Butterfly Pattern** (EMA 10 > EMA 30 > EMA 100) = Strong bullish confirmation - PREFERRED but not required
  * **Recent Crosses** (last 1-5 bars) = Strong short-term signals:
    - EMA 10 crossing above EMA 30 = Immediate bullish momentum
    - EMA 30 crossing above EMA 100 = Strong bullish confirmation
    - EMA 10 crossing above EMA 100 = Very strong bullish signal
  * **Convergence**: Shorter-term EMAs (10, 30) coming together = Potential for immediate breakout

- **Current Price vs EMAs**: Price above all EMAs = Bullish confirmation, Price below all EMAs = Bearish (for next few hours)

- **IMPORTANT**: 
  * EMA relationships are PREFERRED for confirmation but NOT mandatory
  * A symbol can be bullish even if EMAs are not perfectly aligned (10 > 30 > 100)
  * Focus on the BIG PICTURE: Do PRIMARY indicators align bullishly? That's what matters most
  * Use EMAs to confirm direction suggested by PRIMARY indicators, not as primary determinant
  * Recent crosses are MORE VALUABLE than perfect butterfly patterns for short-term trading

- **Verify using numeric values** from the structured data - focus on MOST RECENT VALUES (last 1-5 bars) from the data

### 5. Volume Analysis (Secondary - Use at Discretion)

- **RECENT VOLUME SPIKES**: Volume spikes in last 1-5 bars = Strong immediate signal
- **Volume supporting CURRENT price movement** (most recent bars from data) = Confirmation for next few hours
- **Volume relative to recent averages** (last 20 bars) - above average = stronger signal
- **Volume divergence**: Decreasing volume on price moves = weakening momentum (bearish for continuation)
- **Current volume vs price**: High volume + price up = Strong buy signal, High volume + price down = Strong sell signal
- **Use volume only to confirm momentum** suggested by primary indicators

### 6. Volume-by-Price (VBP) Analysis (Secondary - Use at Discretion)

- **VBP data includes**: Price levels, volume percentages, Point of Control (POC), Value Area High/Low, and volume distribution
- **CURRENT PRICE POSITION (RIGHT NOW) - MOST IMPORTANT:**

**CRITICAL**: Use the ACTUAL NUMERIC VALUES from the VBP data:
- Check POC (Point of Control) price level from the data
- Check Value Area High/Low levels from the data  
- Check volume percentages at each price level from the data
- Compare current price (from OHLCV data) to VBP price levels numerically
  * Price ABOVE big VBP bars RIGHT NOW = Strong support below, bullish for next few hours
  * Price BELOW big VBP bars RIGHT NOW = Strong resistance above, bearish for next few hours
  * Price IN low-volume zone RIGHT NOW = Easy movement potential (can go either direction quickly)
  * Price approaching big VBP bar (within 1-2%) = Likely to encounter support/resistance SOON

- **IMMEDIATE SUPPORT/RESISTANCE:**
  * BIG BARS near current price = Strong support/resistance that will affect next few hours
  * Thick VBP bars directly above current price = Resistance level to watch
  * Thick VBP bars directly below current price = Support level to watch

- **FREE FLOW ZONES (IMMEDIATE MOVEMENT):**
  * NARROW BARS or NO BARS near current price = Price can move quickly in either direction
  * Gaps between VBP bars near current price = Minimal resistance, fast movement potential

- **Use VBP only to identify support/resistance levels**, not as primary determinant

## CRITICAL WORKFLOW

Follow these steps in order. Do NOT skip ahead or analyze symbols that don't pass the filter.

### STEP 1: QUICK SCREENING

Review ALL symbols present in the provided data. For each symbol, quickly check PRIMARY indicators using the ACTUAL NUMERIC VALUES from the structured data:

**BULLISH SIGNALS (must have these PRIMARY indicators to pass filter):**
- **Hurst Composite**: Above zero = BULLISH momentum (or trending upward)
- **CCO**: Fast Osc > Slow Osc = BULLISH (or Fast Osc crossing above Slow Osc)
- **MESA Stochastic**: Lines above triggers AND trending up = BULLISH (or bullish crossovers in top half)

**BEARISH SIGNALS (these PRIMARY indicators mean SKIP the symbol):**
- **Hurst Composite**: Below zero = BEARISH momentum (or trending downward, SKIP)
- **CCO**: Fast Osc < Slow Osc = BEARISH (SKIP)
- **MESA Stochastic**: Lines below triggers AND trending down = BEARISH (or bearish crossunders in bottom half, SKIP)

**CRITICAL FILTER RULE**: A symbol must have **AT LEAST 2 of the 3 PRIMARY indicators** showing bullish signals to pass the filter. If 2 or more PRIMARY indicators are bearish, SKIP the symbol regardless of secondary indicators.

**IMPORTANT**: 
- EMA relationships are NOT part of the filter - they are secondary confirmation only
- A symbol can pass the filter even if EMAs are not perfectly aligned (10 > 30 > 100)
- Focus on PRIMARY indicator alignment - that's what determines bullish/bearish

**COMMON MISTAKES TO AVOID:**
- DO NOT confuse "oversold" with "bullish setup" - oversold means price is low, but if PRIMARY indicators (Hurst, CCO, MESA) are bearish, it's still a bearish setup
- DO NOT filter out symbols based on EMA relationships alone - EMAs are secondary
- DO NOT use secondary indicators (EMAs, Volume, VBP) to override PRIMARY indicators - PRIMARY indicators determine bullish/bearish
- DO NOT say "about to cross" or "potential reversal" - only analyze symbols that ALREADY show bullish signals in PRIMARY indicators
- DO NOT fill the top 3 with bearish symbols just because they're "oversold" or "might reverse"

### STEP 2: FILTER

After quick screening, identify ONLY symbols that show STRONG BULLISH signals in PRIMARY indicators.

- Symbols with bearish Hurst Composite (below zero or trending down) = SKIP (DO NOT ANALYZE - this is bearish)
- Symbols with bearish CCO (Fast Osc < Slow Osc) = SKIP (DO NOT ANALYZE - this is bearish, not bullish)
- Symbols with bearish MESA crossunders = SKIP (DO NOT ANALYZE - these are bearish, not bullish)
- Symbols with overall bearish momentum in PRIMARY indicators = SKIP (DO NOT ANALYZE - these are bearish, not bullish)

**CRITICAL**: A symbol must have **AT LEAST 2 of these 3 PRIMARY indicators** showing bullish signals to be considered bullish:
* Bullish Hurst Composite (above zero or trending upward)
* Bullish CCO (Fast Osc > Slow Osc) OR Fast Osc crossing above Slow Osc
* Bullish MESA (lines above triggers, trending up, or bullish crossovers in top half)

- Secondary indicators (EMAs, Volume, VBP) can provide confirmation but do NOT override PRIMARY indicators
- Only proceed to detailed analysis for symbols that pass this PRIMARY indicator bullish filter

### STEP 3: DETAILED ANALYSIS

Only provide complete analysis for symbols that passed the bullish filter in STEP 2.

**CRITICAL DECISION POINT:**
- **FIRST**: Count how many symbols passed the bullish filter in STEP 2
- **IF ZERO symbols passed the filter**: State "No strong bullish setups found. All analyzed symbols show weak, mixed, or bearish signals." and STOP IMMEDIATELY - DO NOT provide any detailed analysis for any symbols
- **IF 1-2 symbols passed the filter**: Provide complete analysis ONLY for those symbols that passed
- **IF 3+ symbols passed the filter**: Provide complete analysis for the TOP 3 BEST symbols that passed

**CRITICAL RULES:**
- Do NOT provide detailed analysis for symbols that are bearish, neutral, or should be avoided
- Do NOT analyze symbols that failed the filter in STEP 2
- Do NOT analyze symbols "just to fill the top 3" - if only 1 symbol passed, analyze only that 1 symbol

For each symbol that passed the bullish filter, provide complete analysis:

---

**Symbol: [SYMBOL]**

**PRIMARY INDICATORS (Required Analysis):**

**Hurst Spectral Analysis Oscillator (PRIMARY):**
- Composite value: [value]
- Assessment: [Bullish/Neutral/Bearish signal strength based on composite direction and period alignment]
- Recent trend: [Direction in last 1-5 bars]

**MESA Stochastic Multi Length (PRIMARY):**
- MESA1: [Current VALUE from data (0.0-1.0), trigger VALUE, trend direction from recent values]
- MESA2: [Current VALUE from data (0.0-1.0), trigger VALUE, trend direction from recent values]
- MESA3: [Current VALUE from data (0.0-1.0), trigger VALUE, trend direction from recent values]
- MESA4: [Current VALUE from data (0.0-1.0), trigger VALUE, trend direction from recent values]
- Crossovers/Crossunders: [Compare MESA values to trigger values numerically - any crossovers above 0.5 (PUMP) or crossunders below 0.5 (DUMP)?]
- Good Entry Signals: [Are MESA VALUES increasing from low points (<0.5)? Multiple lines VALUES aligning upward?]
- Bad Entry Signals: [Are MESA VALUES decreasing from high points (>0.5)? Multiple lines VALUES aligning downward?]
- Overbought/Oversold: [Any VALUES near 1.0 (overbought) or 0.0 (oversold) from the data?]
- Multi-Length Alignment: [Compare all MESA VALUES (1-4) - are they all aligned in same direction? Any divergence?]
- Assessment: [Bullish/Neutral/Bearish signal strength based on numeric crossover positions, entry signals, and alignment]

**Cycle Channel Oscillator - CCO (PRIMARY):**
- Fast Osc: [Current VALUE from data (0.0-1.0 range), trend direction from recent values]
- Slow Osc: [Current VALUE from data (0.0-1.0 range), trend direction from recent values]
- Relationship: [Compare Fast Osc VALUE to Slow Osc VALUE numerically - Fast Osc > Slow Osc = BULLISH, Fast Osc < Slow Osc = BEARISH]
- Trend: [Compare recent Fast/Slow Osc VALUES - both trending upward = bullish, both trending downward = bearish]
- Extreme Conditions: [Any VALUES above 1.0 (overbought) or below 0.0 (oversold) from the data?]
- Assessment: [Bullish/Neutral/Bearish signal strength based on numeric oscillator positions and relationship]

**SECONDARY INDICATORS (Use at Discretion - For Confirmation Only):**

**EMA Analysis (Secondary - Use at Discretion):**
- EMA 10: $X.XX, EMA 30: $X.XX, EMA 100: $X.XX
- Relationship: EMA 10 [above/below] EMA 30 [above/below] EMA 100
- **Note**: EMA relationships are PREFERRED but NOT mandatory. Focus on the big picture - do PRIMARY indicators align?
- EMA Stage: [Convergence/Recent Crosses/Butterfly/Spread-Expansion]
- Recent Crosses: [Note any recent crosses of shorter-term EMAs over longer-term EMAs - this is a positive signal]
- Butterfly Pattern: [Yes/No - Yes if EMA 10 > EMA 30 > EMA 100 - PREFERRED but not required]
- Assessment: [Use EMAs only to confirm direction suggested by PRIMARY indicators - not as primary determinant]

**Volume Analysis (Secondary - Use at Discretion):**
- [Volume trends, spikes, support for price movement]
- [Use volume only to confirm momentum suggested by PRIMARY indicators]

**Volume-by-Price (VBP) Analysis (Secondary - Use at Discretion):**
- POC (Point of Control): [Price level VALUE from VBP data - highest volume price level]
- Value Area High: [Price level VALUE from VBP data]
- Value Area Low: [Price level VALUE from VBP data]
- Top Volume Levels: [List price levels with highest volume percentages from VBP data]
- Current Price Position: [Compare current price VALUE (from OHLCV) to POC and Value Area levels numerically - above/below? In low-volume zone?]
- Support/Resistance Assessment: [Strong support below / Strong resistance above / Free flow zone / Approaching key level - based on numeric price comparisons]
- Assessment: [Use VBP numeric price levels and volume percentages to identify support/resistance levels, not as primary determinant]

**Overall Assessment (PRIMARY Indicators First - BULLISH ONLY):**
- **Direction**: This MUST be a STRONG BULLISH (LONG) setup based on PRIMARY indicators
- **PRIMARY Indicator Alignment**: How many PRIMARY indicators (Hurst, MESA, CCO) align bullishly? ALL THREE must align bullishly for strongest signal. At least 2 of 3 must be bullish to pass filter
- **Signal Strength**: Count how many PRIMARY indicators show bullish signals. For a symbol to be ranked, at least 2 of 3 PRIMARY indicators must show bullish signals
- **Secondary Indicator Confirmation**: Do secondary indicators (EMAs, Volume, VBP) confirm the PRIMARY indicator direction? This provides additional confidence but does NOT override PRIMARY indicators
- **Conflicts**: Note any conflicts between PRIMARY indicators - if PRIMARY indicators conflict, this is NOT a strong setup. If secondary indicators conflict with PRIMARY indicators, rely on PRIMARY indicators
- **Recent signals (last 1-5 bars)**: What signals just happened that indicate immediate movement?
- **Convergence**: Do multiple indicators confirm the same direction?
- **Entry timing**: Is this a good time to enter NOW based on indicator alignment, or wait for better convergence?

**Risk Considerations:**
- [Any concerns, limitations, or conflicting signals]

---

[REPEAT THE ABOVE FORMAT FOR SYMBOL #2]

---

[REPEAT THE ABOVE FORMAT FOR SYMBOL #3]

---

## FINAL RANKING SECTION

**CRITICAL**: Only provide Final Ranking if you actually analyzed symbols in STEP 3. If you stated "No strong bullish setups found" and did not analyze any symbols, skip this entire Final Ranking section.

**CRITICAL**: Before creating the Final Ranking, verify that each symbol's "Overall Assessment" explicitly states BULLISH direction.

**Final Ranking (Ranked by PRIMARY Indicator Bullish Signal Strength - ONLY include STRONG BULLISH symbols):**

1. [Top symbol] - LONG - [Brief reason focusing on PRIMARY indicators (Hurst, MESA, CCO) - how many PRIMARY indicators align bullishly]

2. [Second symbol] - LONG - [Brief reason focusing on PRIMARY indicators (Hurst, MESA, CCO) - how many PRIMARY indicators align bullishly]

3. [Third symbol] - LONG - [Brief reason focusing on PRIMARY indicators (Hurst, MESA, CCO) - how many PRIMARY indicators align bullishly]

**NOTE**: Only include STRONG BULLISH (LONG) setups where PRIMARY indicators (Hurst, MESA, CCO) align positively. Rank by PRIMARY indicator bullish signal strength. Secondary indicators (EMAs, Volume, VBP) can provide confirmation but PRIMARY indicators determine ranking. If fewer than 3 symbols qualify, only rank those that qualify. If no symbols qualify, state "No strong bullish setups found."

**CRITICAL RANKING RULES:**
- If fewer than 3 symbols show STRONG bullish signals in PRIMARY indicators, only rank those that are STRONGLY bullish
- If NO symbols show strong bullish signals in PRIMARY indicators, state: "No strong bullish setups found. All analyzed symbols show weak, mixed, or bearish signals in PRIMARY indicators." and STOP - do NOT provide any ranking
- Do NOT include symbols with weak, mixed, or bearish PRIMARY indicators just to fill the ranking
- Do NOT rank symbols where PRIMARY indicators conflict or show bearish signals
- A symbol must have STRONG alignment across PRIMARY indicators (at least 2 of 3 bullish) to be ranked
- The more PRIMARY indicators that align bullishly, the stronger the signal
- Secondary indicators (EMAs, Volume, VBP) can provide confirmation but do NOT override PRIMARY indicators

**IMPORTANT**: Only rank symbols that show STRONG BULLISH signals with clear alignment across multiple indicators. Weak or mixed signals should NOT be ranked.

---

## KEY CHANGES FROM PREVIOUS VERSION

1. **EMA Relationships are PREFERRED but NOT MANDATORY**: Removed strict requirement for EMA 10 > EMA 30 > EMA 100. EMAs are now clearly secondary indicators for confirmation only.

2. **Focus on Big Picture**: Emphasized that PRIMARY indicators (Hurst, MESA, CCO) determine direction. EMA relationships provide confirmation but don't override PRIMARY signals.

3. **Relaxed Filtering**: Symbols can pass the filter based on PRIMARY indicator alignment alone, even if EMAs are not perfectly aligned.

4. **Recent Crosses More Valuable**: Emphasized that recent EMA crosses (last 1-5 bars) are more valuable than perfect butterfly patterns for short-term trading.

5. **Clearer Secondary Indicator Role**: Made it explicit that secondary indicators (EMAs, Volume, VBP) provide confirmation only and do NOT override PRIMARY indicators.

