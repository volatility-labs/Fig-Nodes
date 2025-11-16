import BaseCustomNode from '../base/BaseCustomNode';
import { ServiceRegistry } from '../../services/ServiceRegistry';

export default class OpenRouterChatNodeUI extends BaseCustomNode {
    private allModels: string[] = [];  // All available models
    private visionModels: string[] = [];  // Filtered vision-capable models
    private serviceRegistry!: ServiceRegistry;

    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [280, 200];
        this.serviceRegistry = serviceRegistry;

        // Add tooltip to system input slot
        const systemSlotIndex = this.inputs?.findIndex(inp => inp.name === 'system');
        if (systemSlotIndex !== undefined && systemSlotIndex !== -1) {
            this.inputs[systemSlotIndex]!.tooltip = 'Accepts string or LLMChatMessage with role="system"';
        }

        // Ensure temperature widget properly handles decimal values
        // Do this after widgets are created but ensure options are set correctly
        if (this.widgets && Array.isArray(data?.params)) {
            data.params.forEach((param: any, index: number) => {
                const widget = this.widgets && index < this.widgets.length ? this.widgets[index] : null;
                if (!widget || widget.type !== 'number') return;

                // Specifically handle temperature parameter to ensure decimals work
                if (param.name === 'temperature') {
                    // Ensure all options are properly set - this is critical for decimal support
                    widget.options = widget.options || {};
                    if (param.step !== undefined) {
                        widget.options.step = param.step;
                    }
                    if (param.precision !== undefined) {
                        widget.options.precision = param.precision;
                    }
                    if (param.min !== undefined) {
                        widget.options.min = param.min;
                    }
                    if (param.max !== undefined) {
                        widget.options.max = param.max;
                    }
                    
                    // Ensure the initial value is set correctly
                    const initialValue = this.properties[param.name];
                    if (typeof initialValue === 'number' && !isNaN(initialValue)) {
                        widget.value = initialValue;
                    }
                    
                    // Replace the callback completely to ensure decimal values are preserved
                    // The original callback might be doing integer rounding or other transformations
                    const originalCallback = widget.callback;
                    if (originalCallback) {
                        widget.callback = (v: unknown) => {
                            // Convert to number if needed, preserving decimals
                            let numValue: number;
                            if (typeof v === 'number') {
                                numValue = v;
                            } else if (typeof v === 'string') {
                                const trimmed = v.trim();
                                // Don't update on empty or just "."
                                if (trimmed === '' || trimmed === '.') {
                                    return;
                                }
                                numValue = parseFloat(trimmed);
                            } else {
                                numValue = Number(v);
                            }
                            
                            // Validate range
                            if (!isNaN(numValue) && isFinite(numValue) && numValue >= 0 && numValue <= 2) {
                                // CRITICAL: Update property and widget.value ourselves
                                // Don't call originalCallback as it might be doing integer rounding
                                this.properties[param.name] = numValue;
                                widget.value = numValue;
                                
                                // Also update the HTML input element directly (the popup reads from this)
                                // Find the input element associated with this widget
                                setTimeout(() => {
                                    const nodeEl = document.querySelector(`[data-node-id="${this.id}"]`);
                                    if (nodeEl) {
                                        const inputs = nodeEl.querySelectorAll('input[type="number"]');
                                        inputs.forEach((inp: Element) => {
                                            const htmlInp = inp as HTMLInputElement;
                                            const widgetValue = typeof widget.value === 'number' ? widget.value : parseFloat(String(widget.value || '0'));
                                            // Check if this is the temperature input by comparing widget name/value
                                            if (Math.abs(parseFloat(htmlInp.value || '0') - widgetValue) < 0.01 || 
                                                htmlInp.getAttribute('data-widget-name') === widget.name) {
                                                htmlInp.value = String(numValue);
                                                htmlInp.setAttribute('value', String(numValue));
                                            }
                                        });
                                    }
                                }, 0);
                                
                                // Force canvas update
                                this.setDirtyCanvas(true, true);
                                
                                // Debug logging
                                console.log(`[Temperature Widget] Set ${param.name} to ${numValue} (property: ${this.properties[param.name]}, widget.value: ${widget.value})`);
                            } else {
                                // Invalid value - restore previous value
                                const prevValue = this.properties[param.name];
                                if (typeof prevValue === 'number' && !isNaN(prevValue)) {
                                    widget.value = prevValue;
                                    console.log(`[Temperature Widget] Invalid input ${v}, restored to ${prevValue}`);
                                }
                            }
                        };
                    }
                }
            });
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

    // Called when node is added to graph - HTML elements are created at this point
    onAdded(graph: any) {
        super.onAdded?.(graph);
        
        // After node is added, ensure temperature widget's HTML input element is configured correctly
        // This ensures the input element's step/min/max attributes are set for decimal support
        setTimeout(() => {
            const tempWidget = this.widgetManager.findWidgetByParamName('temperature') as any;
            if (tempWidget && tempWidget.type === 'number') {
                // Find the actual HTML input element
                const widgetElement = (tempWidget as any).last_y ? 
                    document.querySelector(`input[type="number"][data-widget-name="${tempWidget.name}"]`) as HTMLInputElement :
                    null;
                
                // Also try finding by widget's DOM element if available
                let inputEl: HTMLInputElement | null = null;
                if ((tempWidget as any).computeSize) {
                    // Widget might have a DOM reference
                    const nodeEl = document.querySelector(`[data-node-id="${this.id}"]`);
                    if (nodeEl) {
                        const inputs = nodeEl.querySelectorAll('input[type="number"]');
                        // Find the one that corresponds to temperature widget
                        inputs.forEach((inp: Element) => {
                            const htmlInp = inp as HTMLInputElement;
                            // Check if this input's value matches our widget value
                            if (Math.abs(parseFloat(htmlInp.value || '0') - (tempWidget.value || 0)) < 0.01) {
                                inputEl = htmlInp;
                            }
                        });
                    }
                }
                
                // Configure the input element if found
                if (inputEl || widgetElement) {
                    const input = inputEl || widgetElement;
                    if (input) {
                        input.step = '0.05';
                        input.min = '0';
                        input.max = '2';
                        // Ensure it accepts decimal values
                        input.setAttribute('step', '0.05');
                        input.setAttribute('min', '0');
                        input.setAttribute('max', '2');
                    }
                }
            }
        }, 100); // Small delay to ensure DOM is ready
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

    // Override to handle use_vision property changes and sync temperature widget
    onPropertyChanged(name: string, value: unknown, _prev_value?: unknown): boolean {
        if (name === 'use_vision') {
            // Update model combo when vision mode is toggled
            this.updateModelCombo();
        } else if (name === 'temperature') {
            // Ensure temperature widget value stays in sync with property
            const tempWidget = this.widgetManager.findWidgetByParamName('temperature') as any;
            if (tempWidget && typeof value === 'number' && !isNaN(value)) {
                tempWidget.value = value;
                // Debug logging to verify stored value
                console.log(`[Temperature Property Changed] Property: ${value}, Widget.value: ${tempWidget.value}`);
                this.setDirtyCanvas(true, true);
            }
        }
        return true; // Return true to indicate property change was handled
    }
    
    // Method to verify the actual stored temperature value (for debugging)
    getTemperatureValue(): number {
        const temp = this.properties.temperature;
        if (typeof temp === 'number') {
            return temp;
        }
        return 0.7; // default
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
