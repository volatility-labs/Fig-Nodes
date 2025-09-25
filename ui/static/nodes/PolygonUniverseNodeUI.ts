import BaseCustomNode from './BaseCustomNode';

export default class PolygonUniverseNodeUI extends BaseCustomNode {
    constructor(title: string, data: any) {
        super(title, data);
        // Keep UI compact and do not render large lists in-node
        this.size = [300, 120];
        this.displayResults = false;
        this.color = '#2c3e50';
        this.bgcolor = '#1b2836';
    }

    updateDisplay(result: any) {
        // Only store result; avoid drawing huge ticker lists
        this.result = result;
        // Optionally show a short summary if present
        const count = Array.isArray(result?.symbols) ? result.symbols.length : (typeof result?.count === 'number' ? result.count : undefined);
        if (typeof count === 'number') {
            this.displayText = `Symbols: ${count.toLocaleString()}`;
        } else {
            this.displayText = '';
        }
        this.setDirtyCanvas(true, true);
    }
}


