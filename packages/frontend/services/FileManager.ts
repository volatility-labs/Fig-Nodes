import { LGraph, LGraphCanvas } from '@fig-node/litegraph';
import type { SerialisableGraph } from '@fig-node/litegraph/dist/types/serialisation';
import { APIKeyManager } from './APIKeyManager';
import { updateStatus } from './EditorInitializer';

export class FileManager {
    private graph: LGraph;
    private canvas: LGraphCanvas;
    private apiKeyManager: APIKeyManager;
    private currentGraphName: string = 'untitled.json';
    private lastSavedGraphJson: string = '';

    constructor(graph: LGraph, canvas: LGraphCanvas) {
        this.graph = graph;
        this.canvas = canvas;
        this.apiKeyManager = new APIKeyManager();
    }

    // Enforce the LiteGraph.asSerialisable schema (new format) and reject legacy formats
    private isValidAsSerialisableGraph(data: any): data is SerialisableGraph {
        if (!data || typeof data !== 'object') return false;

        // Required top-level fields in asSerialisable
        if (typeof data.id !== 'string') return false;
        if (typeof data.revision !== 'number') return false;
        if (data.version !== 0 && data.version !== 1) return false;
        if (!data.state || typeof data.state !== 'object') return false;
        if (typeof data.state.lastNodeId !== 'number') return false;
        if (typeof data.state.lastLinkId !== 'number') return false;
        if (typeof data.state.lastGroupId !== 'number') return false;
        if (typeof data.state.lastRerouteId !== 'number') return false;

        // Required arrays: nodes, groups; required object: extra (can be empty object)
        if (!Array.isArray(data.nodes)) return false;
        if (!Array.isArray(data.groups)) return false;
        if (data.extra === undefined || typeof data.extra !== 'object') return false;

        // Minimal node checks per ISerialisedNode
        for (const node of data.nodes) {
            if (!node || typeof node !== 'object') return false;
            if (typeof node.id !== 'number') return false;
            if (typeof node.type !== 'string') return false;
            if (!Array.isArray(node.pos) || node.pos.length !== 2) return false;
            if (!Array.isArray(node.size) || node.size.length !== 2) return false;
            if (typeof node.order !== 'number') return false;
            if (typeof node.mode !== 'number') return false;
        }

        // Links: new format uses object-based links; allow missing or empty array
        if (data.links !== undefined) {
            if (!Array.isArray(data.links)) return false;
            for (const link of data.links) {
                if (!link || typeof link !== 'object') return false;
                if (typeof link.id !== 'number') return false;
                if (typeof link.origin_id !== 'number') return false;
                if (typeof link.origin_slot !== 'number') return false;
                if (typeof link.target_id !== 'number') return false;
                if (typeof link.target_slot !== 'number') return false;
                // link.type can be a string or number depending on slot system; accept any defined value
                if (link.type === undefined) return false;
            }
        }

        return true;
    }

    setupFileHandling(): void {
        this.setupSaveButton();
        this.setupLoadButton();
        this.setupFileInput();
    }

    private setupSaveButton(): void {
        document.getElementById('save')?.addEventListener('click', () => {
            this.saveGraph();
        });
    }

    private setupLoadButton(): void {
        document.getElementById('load')?.addEventListener('click', () => {
            const fileInput = document.getElementById('graph-file') as HTMLInputElement;
            fileInput.click();
        });
    }

    private setupFileInput(): void {
        const fileInput = document.getElementById('graph-file') as HTMLInputElement;
        fileInput.addEventListener('change', async (event) => {
            const file = (event.target as HTMLInputElement).files?.[0];
            if (file) {
                await this.loadGraph(file);
            }
        });
    }

    saveGraph(): void {
        const graphData = this.graph.asSerialisable({ sortNodes: true });

        const blob = new Blob([JSON.stringify(graphData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = this.currentGraphName;
        a.click();
        URL.revokeObjectURL(url);
    }

    async loadGraph(file: File): Promise<void> {
        const processContent = async (content: string) => {
            try {
                const graphData = JSON.parse(content);
                if (!this.isValidAsSerialisableGraph(graphData)) {
                    try { alert('Unsupported graph format. Please use a graph saved with the new format.'); } catch { /* ignore in tests */ }
                    return;
                }
                this.graph.configure(graphData);

                try {
                    this.lastSavedGraphJson = JSON.stringify(this.graph.asSerialisable({ sortNodes: true }));
                } catch {
                    this.lastSavedGraphJson = '';
                }

                this.canvas.draw(true);
                this.updateGraphName(file.name);

                // Proactive API key check after load
                const requiredKeys = await this.apiKeyManager.getRequiredKeysForGraph(graphData);
                if (requiredKeys.length > 0) {
                    const missing = await this.apiKeyManager.checkMissingKeys(requiredKeys);
                    if (missing.length > 0) {
                        alert(`Missing API keys for this graph: ${missing.join(', ')}. Please set them in the settings menu.`);
                        this.apiKeyManager.openSettings(missing);
                    }
                }
            } catch (_error) {
                try { alert('Invalid graph file'); } catch { /* ignore in tests */ }
            }
        };

        if (typeof file.text === 'function') {
            const content = await file.text();
            await processContent(content);
        } else {
            const reader = new FileReader();
            reader.onload = async (e) => {
                await processContent(e.target?.result as string);
            };
            reader.readAsText(file);
        }
    }

    updateGraphName(name: string): void {
        this.currentGraphName = name;
        const graphNameEl = document.getElementById('graph-name');
        if (graphNameEl) graphNameEl.textContent = name;
    }

    getCurrentGraphName(): string {
        return this.currentGraphName;
    }

    setLastSavedGraphJson(json: string): void {
        this.lastSavedGraphJson = json;
    }

    getLastSavedGraphJson(): string {
        return this.lastSavedGraphJson;
    }

    // Autosave functionality
    doAutosave(): void {
        try {
            const data = this.graph.asSerialisable({ sortNodes: true });

            const json = JSON.stringify(data);
            if (json !== this.lastSavedGraphJson) {
                const payload = { graph: data, name: this.getCurrentGraphName() };
                this.safeLocalStorageSet('fig-nodes:autosave:v1', JSON.stringify(payload));
                this.lastSavedGraphJson = json;
            }
        } catch { /* ignore */ }
    }

    async restoreFromAutosave(): Promise<boolean> {
        try {
            const saved = this.safeLocalStorageGet('fig-nodes:autosave:v1');
            if (saved) {
                const parsed = JSON.parse(saved);
                if (parsed && this.isValidAsSerialisableGraph(parsed.graph)) {
                    // Set name immediately so UI reflects autosave even if configure fails
                    this.updateGraphName(parsed.name || 'autosave.json');
                    try {
                        this.graph.configure(parsed.graph);
                    } catch (configError) {
                        console.error('Failed to configure graph from autosave:', configError);
                    }
                    try { this.canvas.draw(true); } catch { /* ignore */ }
                    try {
                        this.lastSavedGraphJson = JSON.stringify(this.graph.asSerialisable({ sortNodes: true }));
                    } catch {
                        this.lastSavedGraphJson = '';
                    }
                    return true;
                }
            }
        } catch {
            return false;
        }
        return false;
    }

    private safeLocalStorageSet(key: string, value: string): void {
        try {
            localStorage.setItem(key, value);
        } catch (err) {
            console.error('Autosave failed:', err);
            // Update status to show storage error
            updateStatus('disconnected', 'Autosave failed: Check storage settings');
        }
    }

    private safeLocalStorageGet(key: string): string | null {
        try {
            return localStorage.getItem(key);
        } catch {
            return null;
        }
    }
}
