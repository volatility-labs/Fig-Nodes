import BaseCustomNode from '../base/BaseCustomNode';

export default class SMACrossoverFilterNodeUI extends BaseCustomNode {
    constructor(title: string, data: any) {
        super(title, data);
        this.size = [360, 160];
        this.color = '#2c5530';  // Green theme for market data
        this.bgcolor = '#1a3320';

        // Add convenience buttons
        this.addWidget('button', 'Preview Filtered', '', () => {
            this.displayFilteredPreview();
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

    copySummary() {
        const filteredBundle = this.result?.filtered_ohlcv_bundle;
        if (!filteredBundle || Object.keys(filteredBundle).length === 0) {
            navigator.clipboard.writeText('No assets passed SMA crossover filter');
            return;
        }

        const symbolCount = Object.keys(filteredBundle).length;
        const shortPeriod = this.properties?.short_period || 20;
        const longPeriod = this.properties?.long_period || 50;

        let summary = 'SMA Crossover Filter Results:\n';
        summary += `${symbolCount} asset(s) passed filter\n`;
        summary += `Short SMA: ${shortPeriod} periods\n`;
        summary += `Long SMA: ${longPeriod} periods\n\n`;

        // Show symbols that passed
        const symbols = Object.keys(filteredBundle);
        summary += `Filtered Assets:\n${symbols.join(', ')}`;

        // Add data preview for first symbol
        if (symbols.length > 0) {
            const firstSymbol = symbols[0];
            const ohlcvData = filteredBundle[firstSymbol];
            if (Array.isArray(ohlcvData) && ohlcvData.length > 0) {
                summary += `\n\nSample data for ${firstSymbol}:`;
                const sampleBar = ohlcvData[ohlcvData.length - 1]; // Most recent bar
                if (sampleBar) {
                    const timestamp = new Date(sampleBar.timestamp).toLocaleDateString();
                    summary += `\nLatest: ${timestamp} | `;
                    summary += `O:${sampleBar.open?.toFixed(2)} H:${sampleBar.high?.toFixed(2)} `;
                    summary += `L:${sampleBar.low?.toFixed(2)} C:${sampleBar.close?.toFixed(2)}`;
                    if (sampleBar.volume) {
                        summary += ` V:${sampleBar.volume.toLocaleString()}`;
                    }
                }
            }
        }

        navigator.clipboard.writeText(summary);
    }

    displayFilteredPreview() {
        // Trigger execution to get fresh data for preview
        if (this.graph && this.graph.onExecuteStep) {
            this.graph.onExecuteStep();
        }
    }
}
