import { LiteGraph } from '@fig-node/litegraph';
import { BaseCustomNode } from '../nodes';

export interface NodeRegistry {
    allItems: { name: string; category: string; description?: string }[];
    categorizedNodes: { [key: string]: string[] };
}

export type NodeCategory = 'io' | 'llm' | 'market' | 'base';

type ModuleFactory = () => Promise<{ default: any }>;

const UI_GLOB = {
    ...import.meta.glob('../nodes/**/*NodeUI.ts'),
    ...import.meta.glob('../nodes/**/*NodeUI.tsx'),
    ...import.meta.glob('../nodes/**/*NodeUI.js'),
} as Record<string, ModuleFactory>;

function resolveGlobKey(modulePath: string): string | null {
    // modulePath is now just the filename without extension (e.g., "OllamaChatNodeUI")
    // Search through all glob keys to find a match regardless of folder structure
    const extensions = ['.ts', '.tsx', '.js'];

    for (const ext of extensions) {
        const targetName = modulePath + ext;
        // Find any key that ends with the target filename
        for (const key in UI_GLOB) {
            if (key.endsWith(targetName)) {
                return key;
            }
        }
    }
    return null;
}

export class UIModuleLoader {
    private uiModules: { [key: string]: any } = {};
    private nodeMetadata: any = null;
    private serviceRegistry: any = null;

    constructor(serviceRegistry: any) {
        this.serviceRegistry = serviceRegistry;
    }

    private validateNodeMetadata(meta: any): void {
        if (!meta || typeof meta !== 'object') {
            throw new Error('Invalid node metadata: expected object');
        }
    }

    private async loadUIModuleByPath(modulePath: string): Promise<any> {
        if (this.uiModules[modulePath]) return this.uiModules[modulePath];
        const key = resolveGlobKey(modulePath);
        if (!key) {
            console.warn(`[UIModuleLoader] No UI module found for path: ${modulePath}`);
            return BaseCustomNode;
        }
        try {
            const factory = UI_GLOB[key];
            if (!factory) {
                console.warn(`[UIModuleLoader] No factory for key: ${key}`);
                return BaseCustomNode;
            }
            const mod = await factory();
            const cls = mod.default || BaseCustomNode;
            this.uiModules[modulePath] = cls;
            return cls;
        } catch (error) {
            console.error(`[UIModuleLoader] Failed to load module ${modulePath}:`, error);
            return BaseCustomNode;
        }
    }

    async registerNodes(): Promise<NodeRegistry> {
        const response = await fetch('/api/v1/nodes');
        if (!response.ok) {
            throw new Error(`Failed to fetch nodes: ${response.statusText}`);
        }

        const meta = await response.json();
        this.nodeMetadata = meta.nodes;
        this.validateNodeMetadata(this.nodeMetadata);

        const categorizedNodes: { [key: string]: string[] } = {};
        const allItems: { name: string; category: string; description?: string }[] = [];

        for (const name in meta.nodes) {
            const data = meta.nodes[name] as { category?: NodeCategory; description?: string };
            const category = (data.category ?? 'base') as NodeCategory;

            // Construct module path as just the filename: {ClassName}NodeUI
            const modulePath = `${name}NodeUI`;
            const NodeClass = await this.loadUIModuleByPath(modulePath);

            const serviceRegistry = this.serviceRegistry;
            const CustomClass = class extends NodeClass {
                constructor() {
                    super(name, data, serviceRegistry);
                }
            };
            const LG = ((globalThis as any).LiteGraph || LiteGraph);
            LG.registerNodeType(name, CustomClass);

            if (!categorizedNodes[category]) categorizedNodes[category] = [];
            categorizedNodes[category].push(name);
            const description = (data.description ?? '') as string;
            allItems.push({ name, category, description });
        }

        return { allItems, categorizedNodes };
    }

    getNodeMetadata(): any {
        return this.nodeMetadata;
    }
}
