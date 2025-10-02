import BaseCustomNode from './BaseCustomNode';

export default class OllamaModelSelectorNodeUI extends BaseCustomNode {

    constructor(title: string, data: any) {
        super(title, data);
        this.size = [280, 140];
        this.color = '#1f2a44';
        this.bgcolor = '#0f172a';
        // Do not render result text inside this selector node
        this.displayResults = false;

        this.addWidget('button', 'Refresh', '', async () => {
            try { await this.fetchAndPopulateModels(); } catch { }
        }, {});
    }

    onAdded() {
        // Populate model list once the node is added
        this.fetchAndPopulateModels().catch(() => { });
    }

    async fetchAndPopulateModels() {
        const host = (this.properties['host'] as string) || 'http://localhost:11434';
        try {
            const res = await fetch(`${host.replace(/\/$/, '')}/api/tags`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            const models = (data.models || []).map((m: any) => m.name).filter(Boolean);
            const selectedWidget = (this as any).widgets?.find((w: any) => String(w.name).startsWith('selected'));
            if (selectedWidget) {
                selectedWidget.options = selectedWidget.options || {};
                selectedWidget.options.values = models;
            }
            // Ensure the property reflects a valid selection
            if (!models.includes(this.properties['selected'])) {
                this.properties['selected'] = models[0] || '';
            }
            // Update the button label to show the current selection
            if (selectedWidget && typeof selectedWidget.name === 'string') {
                const labelBase = 'selected';
                const current = this.properties['selected'] || '';
                selectedWidget.name = `${labelBase}: ${current}`;
            }
            this.setDirtyCanvas(true, true);
        } catch {
            // Keep existing options on failure
        }
    }

    updateDisplay(_result: any) {
        // Intentionally no-op to avoid in-node logging
        this.result = _result;
        this.displayText = '';
    }
}


