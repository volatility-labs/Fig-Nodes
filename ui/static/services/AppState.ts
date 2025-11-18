import { LGraph, LGraphCanvas } from '@comfyorg/litegraph';
import type { SerialisableGraph } from '@comfyorg/litegraph/dist/types/serialisation';

type GraphDataView = Pick<SerialisableGraph, 'nodes' | 'links' | 'config'>;

export class AppState {
    private static instance: AppState;
    private currentGraph: LGraph | null = null;
    private canvas: LGraphCanvas | null = null;
    private missingKeys: string[] = [];
    private nodeMetadata: any = null;

    static getInstance(): AppState {
        if (!AppState.instance) {
            AppState.instance = new AppState();
        }
        return AppState.instance;
    }

    setCurrentGraph(graph: LGraph): void {
        this.currentGraph = graph;
    }

    getCurrentGraph(): LGraph | null {
        return this.currentGraph;
    }

    setCanvas(canvas: LGraphCanvas): void {
        this.canvas = canvas;
    }

    getCanvas(): LGraphCanvas | null {
        return this.canvas;
    }

    getCurrentGraphData(): GraphDataView {
        try {
            const data = this.currentGraph?.asSerialisable({ sortNodes: true }) as any;
            if (data) {
                return {
                    nodes: Array.isArray(data.nodes) ? data.nodes : [],
                    links: Array.isArray(data.links) ? data.links : [],
                    config: data.config
                };
            }
            return { nodes: [], links: [] };
        } catch {
            return { nodes: [], links: [] };
        }
    }

    setMissingKeys(keys: string[]): void {
        try {
            this.missingKeys = Array.from(new Set(Array.isArray(keys) ? keys : []));
        } catch {
            this.missingKeys = [];
        }
    }

    getMissingKeys(): string[] {
        return this.missingKeys.slice();
    }

    async getNodeMetadata(): Promise<any> {
        if (!this.nodeMetadata) {
            const response = await fetch('/api/v1/nodes');
            if (!response.ok) throw new Error('Failed to fetch node metadata');
            this.nodeMetadata = (await response.json()).nodes;
        }
        return this.nodeMetadata;
    }

    async getRequiredKeysForGraph(graphData: Pick<SerialisableGraph, 'nodes'>): Promise<string[]> {
        const meta = await this.getNodeMetadata();
        const required = new Set<string>();
        for (const node of graphData.nodes || []) {
            const nodeType = node.type;
            const nodeMeta = meta[nodeType];
            if (nodeMeta && nodeMeta.required_keys) {
                nodeMeta.required_keys.forEach((key: string) => required.add(key));
            }
        }
        return Array.from(required);
    }

    async checkMissingKeys(requiredKeys: string[]): Promise<string[]> {
        const response = await fetch('/api/v1/api_keys');
        if (!response.ok) throw new Error('Failed to fetch current keys');
        const currentKeys = (await response.json()).keys;
        return requiredKeys.filter(key => !currentKeys[key] || currentKeys[key] === '');
    }
}
