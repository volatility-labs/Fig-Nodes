import { LGraph, LGraphCanvas } from '@comfyorg/litegraph';
import { AppState } from './AppState';
import { APIKeyManager } from './APIKeyManager';
import { updateStatus } from '../utils/uiUtils';

export class FileManager {
    private graph: LGraph;
    private canvas: LGraphCanvas;
    private appState: AppState;
    private apiKeyManager: APIKeyManager;
    private currentGraphName: string = 'untitled.json';
    private lastSavedGraphJson: string = '';

    constructor(graph: LGraph, canvas: LGraphCanvas) {
        this.graph = graph;
        this.canvas = canvas;
        this.appState = AppState.getInstance();
        this.apiKeyManager = new APIKeyManager();
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
        const graphData = this.graph.serialize();

        // Save link mode to graph config
        const linkModeManager = (window as any).linkModeManager;
        if (linkModeManager && typeof linkModeManager.saveToGraphConfig === 'function') {
            linkModeManager.saveToGraphConfig(graphData);
        }

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
                this.graph.configure(graphData);

                // Restore link mode if saved
                const linkModeManager = (window as any).linkModeManager;
                if (linkModeManager) {
                    linkModeManager.restoreFromGraphConfig(graphData);
                }

                try {
                    this.lastSavedGraphJson = JSON.stringify(this.graph.serialize());
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
            const data = this.graph.serialize();

            // Save link mode to graph config
            const linkModeManager = (window as any).linkModeManager;
            if (linkModeManager && typeof linkModeManager.saveToGraphConfig === 'function') {
                linkModeManager.saveToGraphConfig(data);
            }

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
                if (parsed && Array.isArray(parsed.graph?.nodes) && Array.isArray(parsed.graph?.links)) {
                    // Set name immediately so UI reflects autosave even if configure fails
                    this.updateGraphName(parsed.name || 'autosave.json');
                    try {
                        this.graph.configure(parsed.graph);
                        // Restore link mode if saved
                        const linkModeManager = (window as any).linkModeManager;
                        if (linkModeManager) {
                            linkModeManager.restoreFromGraphConfig(parsed.graph);
                        }
                    } catch (configError) {
                        // Keep going without throwing; we still consider autosave restored to avoid overwriting with default graph
                        console.error('Failed to configure graph from autosave:', configError);
                    }
                    try { this.canvas.draw(true); } catch { /* ignore */ }
                    try {
                        this.lastSavedGraphJson = JSON.stringify(this.graph.serialize());
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
