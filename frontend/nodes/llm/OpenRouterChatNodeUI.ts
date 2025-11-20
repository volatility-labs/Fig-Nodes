import BaseCustomNode from '../base/BaseCustomNode';
import { ServiceRegistry } from '../../services/ServiceRegistry';

export default class OpenRouterChatNodeUI extends BaseCustomNode {
    private allModels: string[] = [];  // All available models
    private visionModels: string[] = [];  // Filtered vision-capable models
    private serviceRegistry!: ServiceRegistry;

    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [280, 220];
        this.displayResults = false; // Don't display results in node UI
        this.serviceRegistry = serviceRegistry;

        // Add tooltip to system input slot
        const systemSlotIndex = this.inputs?.findIndex(inp => inp.name === 'system');
        if (systemSlotIndex !== undefined && systemSlotIndex !== -1) {
            this.inputs[systemSlotIndex]!.tooltip = 'Accepts string or LLMChatMessage with role="system"';
        }

        // Customize model dropdown to position near mouse click
        const modelParamName = 'model';
        const widget = this.widgetManager.findWidgetByParamName(modelParamName) as any;
        if (widget) {
            widget.callback = () => {
                const useVisionRaw = this.properties.use_vision;
                const useVision = useVisionRaw === true || useVisionRaw === 'true';
                let modelsToUse = useVision ? this.visionModels : this.allModels;

                // Fallback if not loaded yet
                if (modelsToUse.length === 0) {
                    modelsToUse = useVision ? ['google/gemini-2.0-flash-001'] : ['z-ai/glm-4.6'];
                }

                const dialogManager = this.serviceRegistry.get('dialogManager');
                if (dialogManager && typeof dialogManager.showCustomDropdown === 'function') {
                    dialogManager.showCustomDropdown(
                        modelParamName,
                        modelsToUse,
                        (selectedValue: unknown) => {
                            this.properties.model = selectedValue as string;
                            const currentUseVision = this.properties.use_vision === true || this.properties.use_vision === 'true';
                            const displayLabel = currentUseVision
                                ? `model: ${String(selectedValue)} (Vision)`
                                : `model: ${String(selectedValue)}`;
                            this.widgetManager.setWidgetLabel(modelParamName, displayLabel);
                            this.setDirtyCanvas(true, true);
                        },
                        undefined // No position, use mouse
                    );
                } else {
                    // Simple fallback
                    const selectedIndex = prompt(`Select model index (0-${modelsToUse.length - 1}):`);
                    if (selectedIndex !== null) {
                        const index = parseInt(selectedIndex);
                        if (index >= 0 && index < modelsToUse.length) {
                            const selectedValue = modelsToUse[index];
                            this.properties.model = selectedValue as string;
                            const currentUseVision = this.properties.use_vision === true || this.properties.use_vision === 'true';
                            const displayLabel = currentUseVision
                                ? `model: ${String(selectedValue)} (Vision)`
                                : `model: ${String(selectedValue)}`;
                            this.widgetManager.setWidgetLabel(modelParamName, displayLabel);
                            this.setDirtyCanvas(true, true);
                        }
                    }
                }
            };
        }

        // Fetch available models and populate combos
        this.fetchModels();
    }

    private async fetchModels() {
        try {
            // Fetch all models from OpenRouter API
            // Note: API key not required for public model list, but can be included if available
            const response = await fetch('https://openrouter.ai/api/v1/models');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: Failed to fetch models`);
            }
            const data = await response.json();

            if (Array.isArray(data?.data)) {
                // Extract all model IDs
                this.allModels = data.data
                    .map((m: any) => m.id)
                    .filter((id: string) => typeof id === 'string')
                    .sort((a: string, b: string) => a.localeCompare(b));

                // Filter vision-capable: Check input_modalities includes "image"
                this.visionModels = data.data
                    .filter((m: any) => {
                        const modalities = m.architecture?.input_modalities || [];
                        return Array.isArray(modalities) && modalities.includes('image');
                    })
                    .map((m: any) => m.id)
                    .filter((id: string) => typeof id === 'string')
                    .sort((a: string, b: string) => a.localeCompare(b));

                console.log(`Fetched ${this.allModels.length} total models, ${this.visionModels.length} vision-capable`);
            } else {
                console.warn('Unexpected models response format');
                this.allModels = [];
                this.visionModels = [];
            }
        } catch (error) {
            console.error('Failed to fetch OpenRouter models:', error);
            // Fallback to known models
            this.allModels = ['z-ai/glm-4.6'];
            this.visionModels = ['google/gemini-2.0-flash-001'];
        }

        // Update combo based on current use_vision setting
        this.updateModelCombo();
    }

    private updateModelCombo() {
        // Handle combo value: can be string "true"/"false" or boolean
        const useVisionRaw = this.properties.use_vision;
        const useVision = useVisionRaw === true || useVisionRaw === "true";
        const modelsToUse = useVision ? this.visionModels : this.allModels;
        
        if (modelsToUse.length > 0) {
            this.widgetManager.setComboValues('model', modelsToUse);
            const currentModel = String(this.properties.model || (useVision ? 'google/gemini-2.0-flash-001' : 'z-ai/glm-4.6'));
            
            // If current model not in filtered list, select first available
            if (!modelsToUse.includes(currentModel)) {
                this.properties.model = modelsToUse[0];
            }
            
            const currentDisplayModel = String(this.properties.model || modelsToUse[0]);
            const label = useVision ? `model: ${currentDisplayModel} (Vision)` : `model: ${currentDisplayModel}`;
            this.widgetManager.setWidgetLabel('model', label);
            this.setDirtyCanvas(true, true);
        }
    }

    // Override to handle use_vision property changes
    onPropertyChanged(name: string, _value: unknown, _prev_value?: unknown): boolean {
        if (name === 'use_vision') {
            // Update model combo when vision mode is toggled
            this.updateModelCombo();
        }
        return true; // Return true to indicate property change was handled
    }

    updateDisplay(result: any) {
        // Check for errors first
        const error = result?.metrics?.error;
        if (error) {
            this.displayText = `❌ Error: ${error}`;
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

        // Web search is always enabled
        text = `🔍 Web Search\n\n${text}`;

        this.displayText = text || '';
        this.setDirtyCanvas(true, true);
    }
}
