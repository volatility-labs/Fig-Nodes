import BaseCustomNode from './BaseCustomNode';
import { LiteGraph } from '@comfyorg/litegraph';

export default class PolygonCustomBarsNodeUI extends BaseCustomNode {
    constructor(title: string, data: any) {
        super(title, data);
        this.size = [360, 180];
        this.color = '#2c5530';  // Green theme for market data
        this.bgcolor = '#1a3320';

        // Display results for OHLCV data summary
        this.displayResults = true;

        // Add convenience buttons
        this.addWidget('button', 'Preview Data', '', () => {
            this.displayDataPreview();
        }, {});
        this.addWidget('button', 'Copy Summary', '', () => {
            if (this.displayText) navigator.clipboard.writeText(this.displayText);
        }, {});
    }

    updateDisplay(result: any) {
        const ohlcv = result?.ohlcv;
        if (!ohlcv || !(ohlcv instanceof Array) && Object.keys(ohlcv).length === 0) {
            this.displayText = 'No data available';
            this.setDirtyCanvas(true, true);
            return;
        }

        // Handle both DataFrame (from pandas) and plain object/array formats
        let df = ohlcv;
        if (!(df instanceof Array) && typeof df === 'object') {
            // Convert object to array of rows for summary
            df = Object.values(df);
        }

        if (Array.isArray(df) && df.length > 0) {
            const rowCount = df.length;
            const columns = Object.keys(df[0] || {});
            const summary = `OHLCV Data: ${rowCount} bars\nColumns: ${columns.join(', ')}`;

            // Show first few bars as preview
            const previewBars = df.slice(0, 3).map((bar: any, i: number) => {
                const timestamp = bar.timestamp || bar.index || `Bar ${i + 1}`;
                const ohlc = `O:${bar.open?.toFixed(2) || 'N/A'} H:${bar.high?.toFixed(2) || 'N/A'} L:${bar.low?.toFixed(2) || 'N/A'} C:${bar.close?.toFixed(2) || 'N/A'}`;
                const volume = bar.volume ? ` V:${bar.volume.toLocaleString()}` : '';
                return `${timestamp}: ${ohlc}${volume}`;
            }).join('\n');

            this.displayText = `${summary}\n\n${previewBars}${rowCount > 3 ? `\n... and ${rowCount - 3} more bars` : ''}`;
        } else {
            this.displayText = 'No bars data';
        }

        this.setDirtyCanvas(true, true);
    }

    private displayDataPreview() {
        const ohlcv = this.result?.ohlcv;
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

        // Format data for display
        let displayData = 'OHLCV Data Preview:\n\n';
        if (Array.isArray(ohlcv) && ohlcv.length > 0) {
            // Show column headers
            const headers = Object.keys(ohlcv[0]).join('\t');
            displayData += headers + '\n';
            displayData += '-'.repeat(headers.length) + '\n';

            // Show first 20 rows
            const rowsToShow = Math.min(20, ohlcv.length);
            for (let i = 0; i < rowsToShow; i++) {
                const row = ohlcv[i];
                const values = Object.values(row).map(v =>
                    typeof v === 'number' ? v.toFixed(4) : String(v)
                ).join('\t');
                displayData += values + '\n';
            }

            if (ohlcv.length > 20) {
                displayData += `\n... and ${ohlcv.length - 20} more rows`;
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
