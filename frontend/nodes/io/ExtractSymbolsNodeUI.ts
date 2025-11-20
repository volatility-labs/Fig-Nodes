import BaseCustomNode from '../base/BaseCustomNode';

export default class ExtractSymbolsNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [200, 90];
        this.displayResults = true; // Display extracted symbols
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
}
