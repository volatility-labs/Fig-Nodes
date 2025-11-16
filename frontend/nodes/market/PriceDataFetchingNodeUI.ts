import BaseCustomNode from '../base/BaseCustomNode';

export default class PriceDataFetchingNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        
        this.size = [500, 300];
        
        // Enable default text display
        this.displayResults = true;
    }

    updateDisplay(result: any) {
        // Extract formatted_output from result
        if (result && typeof result === 'object' && result.formatted_output) {
            this.displayText = result.formatted_output;
        } else if (typeof result === 'string') {
            this.displayText = result;
        } else if (result && typeof result === 'object' && result.csv_file) {
            // If only csv_file is present, show that
            this.displayText = `✅ CSV saved: ${result.csv_file.split('/').pop() || result.csv_file}`;
        } else {
            this.displayText = 'Waiting for price data...';
        }
        
        this.setDirtyCanvas(true, true);
    }
}


