import BaseCustomNode from '../base/BaseCustomNode';

export default class PolygonCustomBarsNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [360, 180];
        this.displayResults = false; // Store results but don't display in node

        // Add convenience buttons
        this.addWidget('button', 'Preview Data', '', () => {
            this.displayDataPreview();
        }, {});
        this.addWidget('button', 'Copy Summary', '', () => {
            this.copySummary();
        }, {});
    }

    updateDisplay(result: any) {
        // Store result for other functionality but don't display in node
        this.result = result;
        this.displayText = '';
        this.setDirtyCanvas(true, true);
    }

    private copySummary() {
        const ohlcv = (this.result as { ohlcv?: unknown })?.ohlcv;
        if (!ohlcv) {
            navigator.clipboard.writeText('No data available');
            return;
        }

        // Handle OHLCVBundle format (dict[AssetSymbol, list[OHLCVBar]])
        let bars: any[] = [];
        let symbolCount = 0;
        
        if (Array.isArray(ohlcv)) {
            // Legacy format: array of bars (shouldn't happen but handle gracefully)
            bars = ohlcv;
        } else if (typeof ohlcv === 'object' && ohlcv !== null) {
            // Bundle format: extract bars from all symbols
            const bundle = ohlcv as Record<string, any[]>;
            const symbolKeys = Object.keys(bundle);
            symbolCount = symbolKeys.length;
            
            // Get bars from first symbol (or all symbols if needed)
            if (symbolKeys.length > 0) {
                const firstSymbolBars = bundle[symbolKeys[0]];
                if (Array.isArray(firstSymbolBars)) {
                    bars = firstSymbolBars;
                }
            }
        }

        if (bars.length === 0) {
            navigator.clipboard.writeText('No bars data');
            return;
        }

        const rowCount = bars.length;
        const columns = Object.keys(bars[0] || {});
        const lookbackPeriod = this.properties?.lookback_period || '3 months';
        const symbolInfo = symbolCount > 0 ? ` (${symbolCount} symbol${symbolCount > 1 ? 's' : ''})` : '';
        const summary = `OHLCV Data${symbolInfo}: ${rowCount} bars (${lookbackPeriod})\nColumns: ${columns.join(', ')}`;

        // Show first few bars as preview
        const previewBars = bars.slice(0, 3).map((bar: any, i: number) => {
            const timestamp = bar.timestamp || bar.index || `Bar ${i + 1}`;
            const ohlc = `O:${parseFloat(bar.open)?.toFixed(2) ?? 'N/A'} H:${parseFloat(bar.high)?.toFixed(2) ?? 'N/A'} L:${parseFloat(bar.low)?.toFixed(2) ?? 'N/A'} C:${parseFloat(bar.close)?.toFixed(2) ?? 'N/A'}`;
            const volume = bar.volume ? ` V:${bar.volume.toLocaleString()}` : '';
            return `${timestamp}: ${ohlc}${volume}`;
        }).join('\n');

        navigator.clipboard.writeText(`${summary}\n\n${previewBars}${rowCount > 3 ? `\n... and ${rowCount - 3} more bars` : ''}`);
    }

    private displayDataPreview() {
        const ohlcv = (this.result as { ohlcv?: unknown })?.ohlcv;
        if (!ohlcv) {
            alert('No data to preview');
            return;
        }

        // Create a simple modal to show more detailed data
        const modal = document.createElement('div');
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.8);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10000;
            font-family: monospace;
        `;

        const content = document.createElement('div');
        content.style.cssText = `
            background: #1a1a1a;
            color: #fff;
            padding: 20px;
            border-radius: 8px;
            max-width: 90%;
            max-height: 80%;
            overflow: auto;
            white-space: pre-wrap;
        `;

        // Handle OHLCVBundle format (dict[AssetSymbol, list[OHLCVBar]])
        let bars: any[] = [];
        let symbolKeys: string[] = [];
        
        if (Array.isArray(ohlcv)) {
            // Legacy format: array of bars (shouldn't happen but handle gracefully)
            bars = ohlcv;
        } else if (typeof ohlcv === 'object' && ohlcv !== null) {
            // Bundle format: extract bars from all symbols
            const bundle = ohlcv as Record<string, any[]>;
            symbolKeys = Object.keys(bundle);
            
            // Get bars from first symbol for display
            if (symbolKeys.length > 0) {
                const firstSymbolBars = bundle[symbolKeys[0]];
                if (Array.isArray(firstSymbolBars)) {
                    bars = firstSymbolBars;
                }
            }
        }

        // Format data for display
        const lookbackPeriod = this.properties?.lookback_period || '3 months';
        let displayData = `OHLCV Data Preview (${lookbackPeriod})`;
        if (symbolKeys.length > 0) {
            displayData += `\nSymbol: ${symbolKeys[0]}${symbolKeys.length > 1 ? ` (+${symbolKeys.length - 1} more)` : ''}`;
        }
        displayData += '\n\n';
        
        if (Array.isArray(bars) && bars.length > 0) {
            // Show column headers
            const headers = Object.keys(bars[0]).join('\t');
            displayData += headers + '\n';
            displayData += '-'.repeat(headers.length) + '\n';

            // Show first 20 rows
            const rowsToShow = Math.min(20, bars.length);
            for (let i = 0; i < rowsToShow; i++) {
                const row = bars[i];
                const values = Object.values(row).map(v =>
                    typeof v === 'number' ? v.toFixed(4) : String(v)
                ).join('\t');
                displayData += values + '\n';
            }

            if (bars.length > 20) {
                displayData += `\n... and ${bars.length - 20} more rows`;
            }
        } else {
            displayData += 'No data available or unsupported format';
        }

        content.textContent = displayData;

        const closeBtn = document.createElement('button');
        closeBtn.textContent = 'Close';
        closeBtn.style.cssText = `
            margin-top: 10px;
            padding: 5px 10px;
            background: #444;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        `;
        closeBtn.onclick = () => document.body.removeChild(modal);

        content.appendChild(closeBtn);
        modal.appendChild(content);

        // Close on background click
        modal.onclick = (e) => {
            if (e.target === modal) document.body.removeChild(modal);
        };

        document.body.appendChild(modal);
    }
}
