import BaseCustomNode from './BaseCustomNode';

export default class RSIFilterNodeUI extends BaseCustomNode {
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
            navigator.clipboard.writeText('No assets passed RSI filter');
            return;
        }

        const symbolCount = Object.keys(filteredBundle).length;
        const minRsi = this.properties?.min_rsi || 30.0;
        const maxRsi = this.properties?.max_rsi || 70.0;
        const timeperiod = this.properties?.timeperiod || 14;

        let summary = 'RSI Filter Results:\n';
        summary += `${symbolCount} asset(s) passed filter\n`;
        summary += `RSI Range: ${minRsi} - ${maxRsi}\n`;
        summary += `Time Period: ${timeperiod}\n\n`;

        // Show symbols that passed
        const symbols = Object.keys(filteredBundle);
        summary += `Filtered Assets:\n${symbols.join(', ')}`;

        // Add RSI interpretation
        if (maxRsi <= 30) {
            summary += `\n\nRSI ≤ ${maxRsi}: Oversold condition`;
        } else if (minRsi >= 70) {
            summary += `\n\nRSI ≥ ${minRsi}: Overbought condition`;
        } else {
            summary += `\n\nRSI ${minRsi}-${maxRsi}: Neutral range`;
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
