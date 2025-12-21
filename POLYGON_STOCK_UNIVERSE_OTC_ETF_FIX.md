# Polygon Stock Universe Node - OTC & ETF Filtering Fix

## 🐛 Problem

The `PolygonStockUniverse` node had confusing and broken filtering for OTC stocks and ETFs:

**Old Parameters (Confusing):**
- `include_otc` (True/False) - unclear behavior
- `exclude_etfs` (True/False) - double negative, confusing

**Issues:**
- ❌ Could not get **ONLY OTC stocks**
- ❌ Could not get **ONLY ETFs**
- ❌ `include_otc=True` wasn't working properly
- ❌ Confusing parameter names

---

## ✅ Solution

Replaced with **two clear dropdown parameters** with multiple options:

### New Parameter 1: `market_filter`

**Options:**
- `stocks_only` (default) - Regular exchange stocks ONLY (no OTC)
- `include_otc` - Regular exchange stocks + OTC stocks
- `otc_only` - **ONLY OTC stocks** (e.g., TCEHY, NTDOY, DANOY)
- `all` - Everything (regular + OTC)

### New Parameter 2: `asset_type_filter`

**Options:**
- `stocks_no_etf` (default) - Regular stocks, exclude ETFs
- `etf_only` - **ONLY ETFs** (e.g., SPY, QQQ, IWM)
- `all` - Both stocks and ETFs

---

## 📊 Usage Examples

### Example 1: Regular Stocks Only (Default)
```
market_filter: stocks_only
asset_type_filter: stocks_no_etf

Result: ✅ AAPL, TSLA, NVDA (regular stocks)
        ❌ SPY, QQQ (ETFs)
        ❌ TCEHY, NTDOY (OTC stocks)
```

### Example 2: Only OTC Stocks
```
market_filter: otc_only
asset_type_filter: stocks_no_etf

Result: ✅ TCEHY (Tencent ADR), NTDOY (Nintendo), DANOY (Danone)
        ❌ AAPL, TSLA (regular exchange)
        ❌ SPY (ETF)
```

### Example 3: Only ETFs
```
market_filter: stocks_only
asset_type_filter: etf_only

Result: ✅ SPY, QQQ, IWM, VOO (ETFs)
        ❌ AAPL, TSLA (regular stocks)
        ❌ TCEHY (OTC)
```

### Example 4: OTC ETFs Only
```
market_filter: otc_only
asset_type_filter: etf_only

Result: ✅ OTC-traded ETFs (if any exist)
        ❌ Regular exchange ETFs
        ❌ OTC stocks
```

### Example 5: Everything (Regular + OTC + ETFs)
```
market_filter: all
asset_type_filter: all

Result: ✅ Everything: AAPL, TSLA, SPY, TCEHY, NTDOY, QQQ
```

### Example 6: Regular Stocks + OTC Stocks (No ETFs)
```
market_filter: include_otc
asset_type_filter: stocks_no_etf

Result: ✅ AAPL, TSLA (regular), TCEHY, NTDOY (OTC)
        ❌ SPY, QQQ (ETFs)
```

---

## 🔧 Technical Changes

### 1. Parameter Schema Updated

**Before:**
```python
{
    "name": "include_otc",
    "type": "combo",
    "default": False,
    "options": [True, False],
},
{
    "name": "exclude_etfs",  # Confusing!
    "type": "combo",
    "default": True,
    "options": [True, False],
}
```

**After:**
```python
{
    "name": "market_filter",
    "type": "combo",
    "default": "stocks_only",
    "options": ["stocks_only", "include_otc", "otc_only", "all"],
    "description": "Filter by market type (exchange vs OTC)",
},
{
    "name": "asset_type_filter",
    "type": "combo",
    "default": "stocks_no_etf",
    "options": ["stocks_no_etf", "etf_only", "all"],
    "description": "Filter by asset type (stocks vs ETFs)",
}
```

### 2. Filtering Logic Updated

**Now properly filters in two dimensions:**

```python
# Check asset type (ETF or stock)
if asset_type_filter == "stocks_no_etf" and is_etf:
    continue  # Skip ETFs
elif asset_type_filter == "etf_only" and not is_etf:
    continue  # Skip non-ETFs

# Check market type (OTC or regular exchange)
if market_filter == "stocks_only" and is_otc:
    continue  # Skip OTC
elif market_filter == "otc_only" and not is_otc:
    continue  # Skip non-OTC
```

### 3. API Endpoint Optimization

When `market_filter="otc_only"`, now queries the OTC market directly:

```python
if market_filter == "otc_only":
    ref_params["market"] = "otc"  # Query OTC market directly
```

This is more efficient and aligns with [Massive API docs](https://polygon.io/docs/rest/stocks/tickers/all-tickers).

---

## 📖 Massive.com API Reference

Based on [Massive.com API documentation](https://polygon.io/docs/rest/stocks/tickers/all-tickers):

### Snapshot API
- **Endpoint:** `/v2/snapshot/locale/us/markets/stocks/tickers`
- **Parameter:** `include_otc` (boolean) - Include OTC tickers in results
- **Default:** `false` (opt-in per [Massive blog](https://massive.com/blog/otc-stocks))

### Reference Tickers API
- **Endpoint:** `/v3/reference/tickers`
- **Parameter:** `market` - Filter by market type
- **Values:** `stocks`, `otc`, `crypto`, `fx`, `indices`
- **Parameter:** `type` - Filter by ticker type (CS, ETF, ETN, etc.)

---

## 🎯 How to Use

### In Fig Nodes UI:

1. **Add `PolygonStockUniverse` node**
2. **Click on node** to see properties
3. **Set `market_filter` dropdown:**
   - `stocks_only` - Regular stocks (default)
   - `include_otc` - Include OTC with regular
   - `otc_only` - **ONLY OTC** (TenCent, Nintendo, etc.)
   - `all` - Everything

4. **Set `asset_type_filter` dropdown:**
   - `stocks_no_etf` - Exclude ETFs (default)
   - `etf_only` - **ONLY ETFs** (SPY, QQQ, etc.)
   - `all` - Include everything

5. **Execute graph** - Get filtered symbols!

---

## 🔍 Validation

### Test Case 1: Only OTC Stocks
```
market_filter: otc_only
asset_type_filter: stocks_no_etf
min_volume: 100000

Expected: TCEHY, NTDOY, DANOY (OTC ADRs with volume)
```

### Test Case 2: Only ETFs
```
market_filter: stocks_only
asset_type_filter: etf_only
min_volume: 1000000

Expected: SPY, QQQ, IWM, VOO (high-volume ETFs)
```

### Test Case 3: Everything
```
market_filter: all
asset_type_filter: all
min_volume: 100000

Expected: Mix of regular stocks, OTC, and ETFs
```

---

## 🚨 Breaking Changes

### Old Workflows (Before Fix):
- Used `include_otc` (True/False)
- Used `exclude_etfs` (True/False)

### New Workflows (After Fix):
- Use `market_filter` dropdown
- Use `asset_type_filter` dropdown

**Migration Guide:**

| Old Setting | New Setting |
|-------------|-------------|
| `include_otc=False, exclude_etfs=True` | `market_filter="stocks_only", asset_type_filter="stocks_no_etf"` |
| `include_otc=True, exclude_etfs=True` | `market_filter="include_otc", asset_type_filter="stocks_no_etf"` |
| `include_otc=False, exclude_etfs=False` | `market_filter="stocks_only", asset_type_filter="all"` |
| **New: Only OTC** | `market_filter="otc_only", asset_type_filter="stocks_no_etf"` |
| **New: Only ETFs** | `market_filter="stocks_only", asset_type_filter="etf_only"` |

---

## 📚 OTC Stocks Background

From [Massive.com OTC blog post](https://massive.com/blog/otc-stocks):

**What is OTC?**
- Over-the-counter trading (not on major exchanges)
- Includes ADRs of major international companies (TenCent, Nintendo, Danone)
- Delisted stocks that moved from exchanges
- Penny stocks (volatile, risky)

**Why OTC Data is Important:**
- Access to international firms via ADRs
- Trading opportunities in delisted securities
- Alternative markets analysis

**Massive.com OTC Features:**
- ✅ Real-time trade data from FINRA feed
- ✅ All US OTC venues (OTC Markets, Global OTC)
- ✅ Available in Aggregates, Trades, and Reference APIs
- ❌ Quotes API (not available for OTC)

---

## 🎉 Summary

**Fixed:**
- ✅ Can now get **ONLY OTC stocks** (`market_filter="otc_only"`)
- ✅ Can now get **ONLY ETFs** (`asset_type_filter="etf_only"`)
- ✅ Clear, intuitive parameter names
- ✅ Proper filtering in reference API
- ✅ Optimized API queries (query OTC market directly when needed)

**No Backend Restart Needed:**
The backend auto-reloads Python files! Just:
1. Execute your graph again
2. New parameters should appear in node properties
3. Set `market_filter="otc_only"` to get OTC stocks

---

## 🧪 Testing Steps

1. **Reload browser** (Cmd+R) to refresh node definitions
2. **Add `PolygonStockUniverse` node**
3. **Check parameters** - should see `market_filter` and `asset_type_filter`
4. **Set to `otc_only`**
5. **Set min_volume** (e.g., 100000) to filter for liquid OTC stocks
6. **Execute** - should see OTC symbols like TCEHY, NTDOY

---

**Try it now! The changes are live!** 🚀

Per the [Massive.com documentation](https://polygon.io/docs/rest/stocks/tickers/all-tickers), OTC data is now fully integrated and should work correctly with the new filtering options.
