import BaseCustomNode from '../base/BaseCustomNode';

export default class DeviationMagnetFilterNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [360, 160];
        // CRITICAL: Set displayResults to false BEFORE any other initialization
        // This prevents the base class from displaying results
        this.displayResults = false;
        // Ensure displayText is always empty
        this.displayText = '';
    }

    updateDisplay(result: any) {
        // Store result for other functionality but don't display in node
        // This prevents JSON output from cluttering the UI
        // Completely override base class behavior to prevent any display
        this.result = result;
        // CRITICAL: Always clear displayText to prevent any rendering
        this.displayText = '';
        // Ensure displayResults stays false (in case something tries to change it)
        this.displayResults = false;
        // Don't call super.updateDisplay() to prevent base class from processing
        // Use setDirtyCanvas directly like other filter nodes
        this.setDirtyCanvas(true, true);
    }

    // Override onDrawForeground to ensure nothing is rendered even if displayText gets set
    onDrawForeground(ctx: CanvasRenderingContext2D) {
        // Temporarily clear displayText before calling super to prevent rendering
        const originalDisplayText = this.displayText;
        this.displayText = '';
        this.displayResults = false;
        super.onDrawForeground(ctx);
        // Restore original (empty) displayText
        this.displayText = '';
    }
}

