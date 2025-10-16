import { LiteGraph } from '@comfyorg/litegraph';
import { BaseCustomNode } from '../nodes';

export interface NodeRegistry {
    allItems: { name: string; category: string; description?: string }[];
    categorizedNodes: { [key: string]: string[] };
}

export class UIModuleLoader {
    private uiModules: { [key: string]: any } = {};
    private nodeMetadata: any = null;

    constructor() {
        this.initializeStaticModules();
    }

    private initializeStaticModules(): void {
        // Import all UI modules statically to ensure they're bundled
        import('../nodes/io/TextInputNodeUI').then(module => {
            this.uiModules['io/TextInputNodeUI'] = module.default;
        });
        import('../nodes/io/LoggingNodeUI').then(module => {
            this.uiModules['io/LoggingNodeUI'] = module.default;
        });
        import('../nodes/io/SaveOutputNodeUI').then(module => {
            this.uiModules['io/SaveOutputNodeUI'] = module.default;
        });
        import('../nodes/io/ExtractSymbolsNodeUI').then(module => {
            this.uiModules['io/ExtractSymbolsNodeUI'] = module.default;
        });
        import('../nodes/llm/LLMMessagesBuilderNodeUI').then(module => {
            this.uiModules['llm/LLMMessagesBuilderNodeUI'] = module.default;
        });
        import('../nodes/llm/OllamaChatNodeUI').then(module => {
            this.uiModules['llm/OllamaChatNodeUI'] = module.default;
        });
        import('../nodes/llm/OpenRouterChatNodeUI').then(module => {
            this.uiModules['llm/OpenRouterChatNodeUI'] = module.default;
        });
        import('../nodes/llm/SystemPromptLoaderNodeUI').then(module => {
            this.uiModules['llm/SystemPromptLoaderNodeUI'] = module.default;
        });
        import('../nodes/market/ADXFilterNodeUI').then(module => {
            this.uiModules['market/ADXFilterNodeUI'] = module.default;
        });
        import('../nodes/market/AtrXFilterNodeUI').then(module => {
            this.uiModules['market/AtrXFilterNodeUI'] = module.default;
        });
        import('../nodes/market/AtrXIndicatorNodeUI').then(module => {
            this.uiModules['market/AtrXIndicatorNodeUI'] = module.default;
        });
        import('../nodes/market/PolygonBatchCustomBarsNodeUI').then(module => {
            this.uiModules['market/PolygonBatchCustomBarsNodeUI'] = module.default;
        });
        import('../nodes/market/PolygonCustomBarsNodeUI').then(module => {
            this.uiModules['market/PolygonCustomBarsNodeUI'] = module.default;
        });
        import('../nodes/market/PolygonUniverseNodeUI').then(module => {
            this.uiModules['PolygonUniverseNodeUI'] = module.default;
        });
        import('../nodes/market/OHLCVPlotNodeUI').then(module => {
            this.uiModules['market/OHLCVPlotNodeUI'] = module.default;
        });
        import('../nodes/market/RSIFilterNodeUI').then(module => {
            this.uiModules['market/RSIFilterNodeUI'] = module.default;
        });
        import('../nodes/market/SMACrossoverFilterNodeUI').then(module => {
            this.uiModules['market/SMACrossoverFilterNodeUI'] = module.default;
        });
        import('../nodes/base/StreamingCustomNode').then(module => {
            this.uiModules['StreamingCustomNode'] = module.default;
        });
    }

    async loadUIModule(modulePath: string): Promise<any> {
        if (this.uiModules[modulePath]) {
            return this.uiModules[modulePath];
        }

        // Dynamic loading fallback
        try {
            // Handle different module path formats
            let importPath = modulePath;
            if (modulePath.includes('/')) {
                importPath = `../nodes/${modulePath}`;
            } else {
                // Try common locations for standalone module names
                const possiblePaths = [
                    `../nodes/base/${modulePath}`,
                    `../nodes/market/${modulePath}`,
                    `../nodes/io/${modulePath}`,
                    `../nodes/llm/${modulePath}`,
                    `../nodes/${modulePath}`
                ];

                for (const path of possiblePaths) {
                    try {
                        const module = await import(path);
                        this.uiModules[modulePath] = module.default;
                        return module.default;
                    } catch {
                        // Continue to next path
                    }
                }
                throw new Error('Module not found in any expected location');
            }

            const module = await import(importPath);
            this.uiModules[modulePath] = module.default;
            return module.default;
        } catch (error) {
            console.warn(`Failed to load UI module ${modulePath}:`, error);
            return BaseCustomNode;
        }
    }

    async registerNodes(): Promise<NodeRegistry> {
        const response = await fetch('/nodes');
        if (!response.ok) {
            throw new Error(`Failed to fetch nodes: ${response.statusText}`);
        }

        const meta = await response.json();
        this.nodeMetadata = meta.nodes;

        const categorizedNodes: { [key: string]: string[] } = {};
        const allItems: { name: string; category: string; description?: string }[] = [];

        for (const name in meta.nodes) {
            const data = meta.nodes[name];
            let NodeClass = BaseCustomNode;

            if (data.uiModule) {
                const uiClass = await this.loadUIModule(data.uiModule);
                if (uiClass) {
                    NodeClass = uiClass;
                } else {
                    console.warn(`UI module ${data.uiModule} not found`);
                }
            }

            const CustomClass = class extends NodeClass {
                constructor() {
                    super(name, data);
                }
            };
            const LG = ((globalThis as any).LiteGraph || LiteGraph);
            LG.registerNodeType(name, CustomClass as any);

            const category = data.category || 'Utilities';
            if (!categorizedNodes[category]) categorizedNodes[category] = [];
            categorizedNodes[category].push(name);
            allItems.push({ name, category, description: data.description });
        }

        return { allItems, categorizedNodes };
    }

    getNodeMetadata(): any {
        return this.nodeMetadata;
    }
}
