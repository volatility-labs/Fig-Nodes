import BaseCustomNode from '../base/BaseCustomNode';

export default class PolygonBatchCustomBarsNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [200, 180];
        this.displayResults = false; // Store results but don't display in node
    }

    // Custom override to prevent display of results in node
    updateDisplay(result: any) {
        this.result = result;
        this.displayText = '';
        this.setDirtyCanvas(true, true);
    }

    setProgress(progress: number, text?: string) {
        super.setProgress(progress, text);
        this.setDirtyCanvas(true, true);  // Force immediate redraw to reflect progress updates
    }

    // Override syncWidgetValues to show computed bar interval
    syncWidgetValues() {
        super.syncWidgetValues();
        
        // Compute and display the effective bar interval
        const multiplier = this.properties.multiplier ?? 1;
        const timespan = this.properties.timespan ?? 'day';
        
        // Format the interval display (e.g., "5 minutes", "1 day", "1 hour")
        let intervalDisplay = '';
        if (multiplier === 1) {
            intervalDisplay = `1 ${timespan}`;
        } else {
            // Handle pluralization
            const pluralTimespan = timespan === 'minute' ? 'minutes' :
                                  timespan === 'hour' ? 'hours' :
                                  timespan === 'day' ? 'days' :
                                  timespan === 'week' ? 'weeks' :
                                  timespan === 'month' ? 'months' :
                                  timespan === 'quarter' ? 'quarters' :
                                  timespan === 'year' ? 'years' : `${timespan}s`;
            intervalDisplay = `${multiplier} ${pluralTimespan}`;
        }
        
        // Update the timespan widget to show the computed interval
        if (this.widgets) {
            const timespanWidget = this.widgets.find((w: any) => w.paramName === 'timespan');
            if (timespanWidget) {
                // Show both the timespan value and the computed bar interval
                timespanWidget.name = `timespan: ${this.formatComboValue(timespan)} (Bar Interval: ${intervalDisplay})`;
            }
        }
    }

    // Helper to format combo values (copied from BaseCustomNode pattern)
    formatComboValue(value: any): string {
        if (value === null || value === undefined) return '';
        return String(value);
    }
}
