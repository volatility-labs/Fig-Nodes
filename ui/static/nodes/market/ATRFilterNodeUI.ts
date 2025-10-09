
import BaseCustomNode from '../base/BaseCustomNode';

export default class ATRFilterNodeUI extends BaseCustomNode {
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
            navigator.clipboard.writeText('No assets passed ATR filter');
            return;
        }

        const symbolCount = Object.keys(filteredBundle).length;
        const minAtr = this.properties?.min_atr || 0.0;
        const window = this.properties?.window || 14;

        let summary = 'ATR Filter Results:\n';
        summary += `${symbolCount} asset(s) passed filter\n`;
        summary += `Minimum ATR: ${minAtr}\n`;
        summary += `Window: ${window}\n\n`;

        // Show symbols that passed
        const symbols = Object.keys(filteredBundle);
        summary += `Filtered Assets:\n${symbols.join(', ')}`;

        navigator.clipboard.writeText(summary);
    }

    displayFilteredPreview() {
        // Trigger execution to get fresh data for preview
        if (this.graph && this.graph.onExecuteStep) {
            this.graph.onExecuteStep();
        }
    }
}
