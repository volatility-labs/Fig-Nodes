import BaseCustomNode from '../base/BaseCustomNode';

export default class PriceDataFetchingNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        
        this.size = [500, 300];
        
        // Disable default text display to prevent lag with large datasets
        this.displayResults = false;
    }

    updateDisplay(result: any) {
        // Store result but don't display large JSONs
        this.result = result;
        
        // Only show simple status messages
        if (result && typeof result === 'object' && result.csv_file) {
             this.displayText = `✅ CSV saved: ${result.csv_file.split('/').pop() || result.csv_file}`;
        } else if (typeof result === 'string' && result.length < 100) {
             this.displayText = result;
        } else {
             this.displayText = '';
        }
        
        this.setDirtyCanvas(true, true);
    }
}


