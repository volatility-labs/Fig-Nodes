# Ollama Vision Mode Guide

## ✅ Features Available (From Commits 678de92 & 681cc91)

Your `OllamaChat` node has **advanced vision capabilities**:

### 1. **Auto-Detection & Model Selection**
- ✅ Automatically detects when images are connected
- ✅ Auto-switches to vision-capable models (qwen3-vl, llava, moondream)
- ✅ Warns if no vision model available

### 2. **Multi-Image Processing**
- ✅ Sequential processing for multiple images with JSON mode
- ✅ Ensures ALL images are processed (not just first one)
- ✅ Returns JSON array with exact count matching images

### 3. **Trading Analysis Ranking**
- ✅ Post-processes trading analysis results
- ✅ Ranks by bullish or bearish sentiment
- ✅ `ranking_mode` parameter (bullish/bearish)
- ✅ Top 3 summary extraction

### 4. **Smart Display**
- ✅ Shows vision responses on node (with smart truncation)
- ✅ Prevents UI freeze from large responses
- ✅ Shows first 1500 chars + "connect to LoggingNode for full output"

---

## 🎯 How to Use Vision Mode

### Basic Setup:

```
[ImageNode] → images → [OllamaChat] → message → [LoggingNode]
                            ↑
                       prompt: "Describe this chart"
```

### Multi-Image Trading Analysis:

```
[StockUniverse] → [MultiIndicatorChart] → images → [OllamaChat]
                                                        ↑
                                            prompt: "Analyze these charts..."
                                            ranking_mode: bullish
                                                        ↓
                                                   [LoggingNode]
```

---

## 📋 Parameters

### Vision-Related:
- **`images` input** - Connect images here (auto-activates vision)
- **`selected_model`** - Auto-selects vision model when images connected
- **`json_mode`** - Enable for structured trading analysis

### Trading Analysis:
- **`ranking_mode`** - "bullish" or "bearish"
  - `bullish`: Ranks most bullish stocks first
  - `bearish`: Ranks most bearish stocks first

### Other:
- **`temperature`** - 0.0-1.5 (creativity)
- **`max_tool_iters`** - Max tool calling iterations
- **`think`** - Enable thinking mode
- **`seed_mode`** - fixed/random/increment

---

## 🖼️ Multi-Image Processing (Automatic!)

When you connect **multiple images**, the node automatically:

1. **Detects count** (e.g., 5 images)
2. **Prepends instruction:**
   ```
   ⚠️ CRITICAL INSTRUCTION: You are receiving 5 images total.
   
   YOU MUST:
   1. Process ALL 5 images - do not skip any
   2. Analyze EACH image separately
   3. Return a JSON array with EXACTLY 5 objects
   4. Format: [{...}, {...}, {...}, {...}, {...}]
   ```

3. **Processes sequentially** (if JSON mode + multiple images)
4. **Validates** all images were analyzed
5. **Returns** JSON array with exact count

**This solves the common problem:** Vision models sometimes only process the first image!

---

## 🎨 Trading Analysis Example

### Input:
```
prompt: "Analyze these stock charts and rank by bullish potential"
images: {
  "AAPL": "data:image/png;base64,...",
  "TSLA": "data:image/png;base64,...",
  "NVDA": "data:image/png;base64,...",
}
ranking_mode: bullish
json_mode: true
```

### Output:
```json
[
  {
    "symbol": "NVDA",
    "bullish_rank": 1,
    "analysis": "Strong uptrend with volume..."
  },
  {
    "symbol": "AAPL",
    "bullish_rank": 2,
    "analysis": "Consolidating near highs..."
  },
  {
    "symbol": "TSLA",
    "bullish_rank": 3,
    "analysis": "Downtrend, waiting for support..."
  }
]

📊 Top 3 Most Bullish:
1. NVDA - Strong uptrend
2. AAPL - Consolidating
3. TSLA - Downtrend
```

---

## 🔧 What I Just Fixed

### Issue: "Vision mode not working"

**Problem:** I set `displayResults = false`, so you couldn't see vision responses!

**Fix Applied:**
1. ✅ **Re-enabled** `displayResults = true` for OllamaChat
2. ✅ **Smart truncation** in BaseCustomNode:
   - LLM messages: Show up to 1500 chars
   - Arrays (trading analysis): Show first 2 items + count
   - Large objects: Show up to 1500 chars
3. ✅ **Prevents UI freeze** while still showing useful output

---

## 🚀 Try It Now

The fixes are **live** (auto-reloaded). Just:

1. **Refresh browser** (click 🔄 button)
2. **Add nodes:**
   ```
   [PolygonStockUniverse]
   → [MultiIndicatorChart] 
   → images → [OllamaChat]
   ```
3. **Set OllamaChat params:**
   - `prompt`: "Analyze these charts"
   - `ranking_mode`: "bullish"
   - `json_mode`: true
   - Click "Refresh Models" (should auto-select qwen3-vl:8b)
4. **Execute graph**
5. **Check output:**
   - ✅ Should see vision analysis on node (first 1500 chars)
   - ✅ Shows "connect to LoggingNode for full output" if truncated
   - ✅ No freezing!

---

## 📊 Display Behavior

### On OllamaChat Node:
```
[OllamaChat]
selected_model: qwen3-vl:8b

Output preview (first 1500 chars):
[
  {"symbol": "AAPL", "bullish_rank": 1, ...},
  {"symbol": "TSLA", "bullish_rank": 2, ...}
]
... (truncated, connect to LoggingNode for full output)
```

### On LoggingNode:
```
[LoggingNode]

Full output (all data):
[Complete JSON array with all symbols, analysis, and rankings]

📊 Top 3 Most Bullish:
1. NVDA - ...
2. AAPL - ...
3. TSLA - ...
```

---

## 🐛 Troubleshooting Vision Mode

### Problem: "Images connected but response ignores them"

**Check 1:** Vision model selected?
```
selected_model should be: qwen3-vl:8b (or other vision model)
```

**Check 2:** Images input actually connected?
```
Blue line should go into "images" slot
```

**Check 3:** Console logs (F12)?
```
Should see: "Auto-selected vision-capable model 'qwen3-vl:8b' (images detected)"
```

### Problem: "Only processes first image"

**Check:** Are you using JSON mode with multiple images?
```
Should see: "Detected 5 images with JSON mode - using sequential processing"
```

If yes → Sequential processing is active (good!)

### Problem: "Response doesn't return array"

**Check prompt:** The CRITICAL INSTRUCTION should be prepended automatically.

Console should show:
```
Detected 5 images - prepended CRITICAL instruction to process all images
```

---

## 💡 Pro Tips

### Tip 1: Use JSON Mode for Trading Analysis
```
json_mode: true
ranking_mode: bullish
```
→ Get structured, ranked results

### Tip 2: Sequential Processing is Automatic
When you have:
- Multiple images (>1)
- JSON mode enabled
→ Processes images one-by-one for reliability

### Tip 3: Check Console for Debug Info
Press F12 → Console → See:
- Image count detected
- Vision model auto-selection
- Sequential processing status
- Ranking mode

### Tip 4: Connect LoggingNode for Full Output
```
[OllamaChat] → message → [LoggingNode]
```
→ See complete, formatted output

---

## 📚 Related Features

### Symbol Tracking (From Commit 681cc91)
- Preserves image keys as symbols
- Corrects misidentified symbols in vision responses
- Example: Image key "AAPL" → ensures response has "symbol": "AAPL"

### Top 3 Summary (From Commit 681cc91)
When ranking mode is active:
```
📊 Top 3 Most Bullish:
1. NVDA - Strong momentum
2. AAPL - Consolidating
3. MSFT - Uptrend intact
```

---

## 🎉 Summary

**Vision mode IS working** - your code has all the features from commits 678de92 and 681cc91!

**What I fixed:**
- ✅ Re-enabled `displayResults` for OllamaChat
- ✅ Smart truncation (shows up to 1500 chars)
- ✅ Prevents UI freeze
- ✅ Shows useful preview on node
- ✅ Shows full output in LoggingNode

**What you have:**
- ✅ Auto-detect images
- ✅ Auto-select vision models
- ✅ Sequential multi-image processing
- ✅ Trading analysis ranking (bullish/bearish)
- ✅ Top 3 summary
- ✅ Symbol tracking

---

**Refresh browser (🔄) and try vision mode now!** Connect images to the `images` slot, set a prompt, and execute. You should see vision analysis with smart truncation! 🖼️

If it's still not working, tell me **exactly** what you see (or don't see) and I'll debug it further!

