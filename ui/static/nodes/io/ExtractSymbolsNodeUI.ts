import BaseCustomNode from '../base/BaseCustomNode';

export default class ExtractSymbolsNodeUI extends BaseCustomNode {
    constructor(title: string, data: any) {
        super(title, data);
        this.size = [300, 120];
        this.color = '#2c5530';  // Green theme for market data
        this.bgcolor = '#1a3320';

        // Add convenience button for copying symbols
        this.addWidget('button', 'Copy Symbols', '', () => {
            this.copySymbols();
        }, {});
    }

    updateDisplay(result: any) {
        this.result = result;
        if (result?.symbols && Array.isArray(result.symbols)) {
            const symbols = result.symbols;
            if (symbols.length === 0) {
                this.displayText = 'No symbols found';
            } else {
                // Show up to 10 symbols, with count if more
                const displaySymbols = symbols.slice(0, 10);
                let text = `Extracted ${symbols.length} symbol(s):\n`;
                text += displaySymbols.map((s: any) => s.ticker || s).join(', ');
                if (symbols.length > 10) {
                    text += `... (+${symbols.length - 10} more)`;
                }
                this.displayText = text;
            }
        } else {
            this.displayText = 'No symbols extracted';
        }
        this.setDirtyCanvas(true, true);
    }

    copySymbols() {
        const symbols = this.result?.symbols;
        if (!symbols || !Array.isArray(symbols) || symbols.length === 0) {
            navigator.clipboard.writeText('No symbols to copy');
            return;
        }

        // Format symbols for copying
        const symbolStrings = symbols.map((s: any) =>
            typeof s === 'string' ? s : (s.ticker || JSON.stringify(s))
        );

        const text = `Extracted Symbols (${symbols.length}):\n${symbolStrings.join('\n')}`;
        navigator.clipboard.writeText(text);
    }
}
