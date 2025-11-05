# Scanner Results

All your scanner results are saved here as CSV files!

## 📊 File Format

Files are named: `{scanner_name}_{date}_{time}.csv`

Examples:
- `ATRX_20251105_115327.csv`
- `momentum_scanner_20251105_120000.csv`

## 📄 CSV Contents

Each CSV file contains:

| Column | Description |
|--------|-------------|
| symbol | Asset symbol (e.g., BTCUSD, ICPUSD) |
| price | Latest closing price |
| bar_timestamp | When the price bar was created |
| age_minutes | How old the data is (in minutes) |
| open | Opening price |
| high | Highest price |
| low | Lowest price |
| volume | Trading volume |

## 🚀 How to View

### In Cursor
Just click any `.csv` file in this folder to view it!

### In Excel/Google Sheets
Double-click the CSV file or import it.

### In Terminal
```bash
# View a file
cat results/ATRX_20251105_115327.csv

# View all your scans
ls results/*.csv
```

## 💡 Tips

- **Each scan creates a new file** - no overwriting!
- **Timestamp in filename** - easy to track history
- **Scanner name included** - organize by strategy
- **Human-readable** - open anywhere, no special tools needed

## 🗂️ Organization

Example folder after a few runs:
```
results/
  ├── ATRX_20251105_115327.csv          (10 symbols)
  ├── ATRX_20251105_120000.csv          (8 symbols)
  ├── momentum_scanner_20251105_115500.csv  (5 symbols)
  ├── breakout_scanner_20251105_120100.csv  (12 symbols)
  └── README.md                         (this file)
```

Simple! No databases, no special viewers - just CSV files you can open anywhere. 🎉
