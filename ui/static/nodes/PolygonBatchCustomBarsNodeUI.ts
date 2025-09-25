import BaseCustomNode from './BaseCustomNode';

export default class PolygonBatchCustomBarsNodeUI extends BaseCustomNode {
    constructor(title: string, data: any) {
        super(title, data);
        this.size = [380, 200];
        this.color = '#2c5530';  // Green theme for market data
        this.bgcolor = '#1a3320';

        // Add convenience buttons for batch operations
        this.addWidget('button', 'Preview Bundle', '', () => {
            this.displayBundlePreview();
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
        const ohlcvBundle = this.result?.ohlcv_bundle;
        if (!ohlcvBundle || typeof ohlcvBundle !== 'object') {
            navigator.clipboard.writeText('No data available');
            return;
        }

        const symbols = Object.keys(ohlcvBundle);
        if (symbols.length === 0) {
            navigator.clipboard.writeText('No symbols fetched');
            return;
        }

        // Get lookback period from params for display
        const lookbackPeriod = this.properties?.lookback_period || '3 months';
        const totalBars = symbols.reduce((sum, sym) => sum + (ohlcvBundle[sym]?.length || 0), 0);

        const summary = `Batch OHLCV Data (${lookbackPeriod})\nSymbols: ${symbols.length}\nTotal Bars: ${totalBars.toLocaleString()}`;

        // Show summary for each symbol
        const symbolSummaries = symbols.slice(0, 10).map((sym, i) => {
            const bars = ohlcvBundle[sym] || [];
            const barCount = bars.length;
            const lastBar = bars[bars.length - 1];
            const lastClose = lastBar ? parseFloat(lastBar.close)?.toFixed(2) : 'N/A';
            return `${i + 1}. ${sym}: ${barCount} bars${lastClose !== 'N/A' ? ` (Last: $${lastClose})` : ''}`;
        }).join('\n');

        const remaining = symbols.length > 10 ? `\n... and ${symbols.length - 10} more symbols` : '';

        navigator.clipboard.writeText(`${summary}\n\n${symbolSummaries}${remaining}`);
    }

    private displayBundlePreview() {
        const ohlcvBundle = this.result?.ohlcv_bundle;
        if (!ohlcvBundle || typeof ohlcvBundle !== 'object') {
            alert('No bundle data to preview');
            return;
        }

        const symbols = Object.keys(ohlcvBundle);
        if (symbols.length === 0) {
            alert('No symbols in bundle');
            return;
        }

        // Create a modal to show bundle summary
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

        // Format bundle data for display
        const lookbackPeriod = this.properties?.lookback_period || '3 months';
        let displayData = `OHLCV Bundle Preview (${lookbackPeriod}):\n\n`;
        displayData += `Total Symbols: ${symbols.length}\n\n`;

        symbols.forEach((sym, idx) => {
            const bars = ohlcvBundle[sym] || [];
            displayData += `${idx + 1}. ${sym}: ${bars.length} bars\n`;
            if (bars.length > 0) {
                const lastBar = bars[bars.length - 1];
                if (lastBar) {
                    const timestamp = lastBar.timestamp || lastBar.index || 'Latest';
                    const ohlc = `O:${parseFloat(lastBar.open)?.toFixed(2) ?? 'N/A'} H:${parseFloat(lastBar.high)?.toFixed(2) ?? 'N/A'} L:${parseFloat(lastBar.low)?.toFixed(2) ?? 'N/A'} C:${parseFloat(lastBar.close)?.toFixed(2) ?? 'N/A'}`;
                    const volume = lastBar.volume ? ` V:${parseFloat(lastBar.volume).toLocaleString()}` : '';
                    displayData += `   Latest: ${timestamp} - ${ohlc}${volume}\n`;
                }
            }
            displayData += '\n';
        });

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
