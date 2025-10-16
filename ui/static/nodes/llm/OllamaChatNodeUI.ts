import BaseCustomNode from '../base/BaseCustomNode';

export default class OllamaChatNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [320, 300];  // Extra space for host and model selector
        this.color = '#1f2a44';
        this.bgcolor = '#0b1220';

        // Model refresh before convenience buttons
        this.addWidget('button', 'Refresh Models', '', async () => {
            try { await this.fetchAndPopulateModels(); } catch { }
        }, {});

        // Add tooltip to system input slot
        const systemSlotIndex = this.inputs?.findIndex(inp => inp.name === 'system');
        if (systemSlotIndex !== undefined && systemSlotIndex !== -1) {
            this.inputs[systemSlotIndex]!.tooltip = 'Accepts string or LLMChatMessage with role="system"';
        }
    }

    onAdded(graph: any) {
        super.onAdded?.(graph);
        this.fetchAndPopulateModels().catch(() => { });
    }

    async fetchAndPopulateModels() {
        const host = (this.properties['host'] as string) || 'http://localhost:11434';
        try {
            const res = await fetch(`${host.replace(/\/$/, '')}/api/tags`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            const models = (data.models || []).map((m: any) => m.name).filter(Boolean);
            const selectedWidget = this.widgets?.find((w: any) => w.name.startsWith('selected_model:'));
            if (selectedWidget) {
                selectedWidget.options = selectedWidget.options || {};
                selectedWidget.options.values = models;
            }
            // Ensure the property reflects a valid selection
            if (!models.includes(this.properties['selected_model'])) {
                this.properties['selected_model'] = models[0] || '';
            }
            // Update the widget name to show the current selection
            if (selectedWidget) {
                const current = this.properties['selected_model'] || '';
                selectedWidget.name = `selected_model: ${current}`;
            }
            this.setDirtyCanvas(true, true);
        } catch {
            // Keep existing options on failure
        }
    }

    onStreamUpdate(_data: any) {
        const error = _data?.metrics?.error;
        const msg = _data?.message;
        let text: string | undefined;

        if (typeof msg === 'string') {
            text = msg;
        } else if (msg && typeof msg.content === 'string') {
            text = msg.content;
        }

        if (error) {
            this.displayText = `❌ Error: ${error}`;
            this.color = '#722f37';
            this.bgcolor = '#2d1b1e';
        } else if (typeof text === 'string') {
            this.displayText = text;
            this.color = '#1f2a44';
            this.bgcolor = '#0b1220';
        }
        this.setDirtyCanvas(true, true);
    }

    updateDisplay(result: any) {
        // Check for errors first
        const error = result?.metrics?.error;
        if (error) {
            this.displayText = `❌ Error: ${error}`;
            this.color = '#722f37';
            this.bgcolor = '#2d1b1e';
            this.setDirtyCanvas(true, true);
            return;
        }

        // Message is now directly a string or object with content
        const msg = result?.message;
        let text: string;
        if (typeof msg === 'string') {
            text = msg;
        } else if (msg && typeof msg.content === 'string') {
            text = msg.content;
        } else if (typeof result === 'string') {
            text = result;
        } else {
            text = JSON.stringify(result, null, 2);
        }
        this.displayText = text || '';
        this.color = '#1f2a44';
        this.bgcolor = '#0b1220';
        this.setDirtyCanvas(true, true);
    }
}


