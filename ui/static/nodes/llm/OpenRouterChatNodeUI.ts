import BaseCustomNode from '../base/BaseCustomNode';
import type { ExtendedWidget } from '../../types/litegraph-extensions';

export default class OpenRouterChatNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [320, 280];
        this.color = '#2a4a2a';  // Greenish for OpenRouter
        this.bgcolor = '#0f1f0f';

        // Add tooltip to system input slot
        const systemSlotIndex = this.inputs?.findIndex(inp => inp.name === 'system');
        if (systemSlotIndex !== undefined && systemSlotIndex !== -1) {
            this.inputs[systemSlotIndex]!.tooltip = 'Accepts string or LLMChatMessage with role="system"';
        }

        // Fetch available models and populate combo widget created by BaseCustomNode/NodeWidgetManager
        fetch('https://openrouter.ai/api/v1/models')
            .then(res => res.json())
            .then(data => {
                const models = Array.isArray(data?.data) ? data.data.map((m: any) => m.id).filter((x: any) => typeof x === 'string') : [];
                models.sort((a: string, b: string) => a.localeCompare(b));
                const widgets: ExtendedWidget[] = this.widgets || [];
                const modelWidget = widgets.find(w => w.paramName === 'model');
                if (modelWidget) {
                    modelWidget.options = { values: models };
                    const current = this.properties.model || 'z-ai/glm-4.6';
                    if (!models.includes(current) && models.length > 0) {
                        this.properties.model = models[0];
                    }
                    // Update label to reflect current value
                    modelWidget.name = `model: ${this.properties.model}`;
                    this.setDirtyCanvas(true, true);
                }
            })
            .catch(error => {
                console.error('Failed to fetch OpenRouter models:', error);
            });
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

        // Add web search indicator if enabled
        const webSearchEnabled = this.properties?.web_search_enabled;
        if (webSearchEnabled) {
            const webSearchEngine = this.properties?.web_search_engine || 'exa';
            const maxResults = this.properties?.web_search_max_results || 5;
            text = `🔍 Web Search (${webSearchEngine}, ${maxResults} results)\n\n${text}`;
        }

        this.displayText = text || '';
        this.color = '#2a4a2a';
        this.bgcolor = '#0f1f0f';
        this.setDirtyCanvas(true, true);
    }
}
