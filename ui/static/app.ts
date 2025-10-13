import { LGraph, LGraphCanvas, LiteGraph } from '@comfyorg/litegraph';
import { BaseCustomNode } from './nodes';
import { setupWebSocket } from './websocket';
import { setupResize, setupKeyboard, updateStatus } from '@utils/uiUtils';
import { setupPalette } from './utils/paletteUtils';

// Import all UI modules statically to ensure they're bundled
import TextInputNodeUI from './nodes/io/TextInputNodeUI';
import LoggingNodeUI from './nodes/io/LoggingNodeUI';
import SaveOutputNodeUI from './nodes/io/SaveOutputNodeUI';
import ExtractSymbolsNodeUI from './nodes/io/ExtractSymbolsNodeUI';
import LLMMessagesBuilderNodeUI from './nodes/llm/LLMMessagesBuilderNodeUI';
import OllamaChatNodeUI from './nodes/llm/OllamaChatNodeUI';
import SystemPromptLoaderNodeUI from './nodes/llm/SystemPromptLoaderNodeUI';
import ADXFilterNodeUI from './nodes/market/ADXFilterNodeUI';
import AtrXFilterNodeUI from './nodes/market/AtrXFilterNodeUI';
import AtrXIndicatorNodeUI from './nodes/market/AtrXIndicatorNodeUI';
import PolygonBatchCustomBarsNodeUI from './nodes/market/PolygonBatchCustomBarsNodeUI';
import PolygonCustomBarsNodeUI from './nodes/market/PolygonCustomBarsNodeUI';
import PolygonUniverseNodeUI from './nodes/market/PolygonUniverseNodeUI';
import RSIFilterNodeUI from './nodes/market/RSIFilterNodeUI';
import SMACrossoverFilterNodeUI from './nodes/market/SMACrossoverFilterNodeUI';

// Static map of UI modules
const UI_MODULES: { [key: string]: any } = {
    'io/TextInputNodeUI': TextInputNodeUI,
    'io/LoggingNodeUI': LoggingNodeUI,
    'io/SaveOutputNodeUI': SaveOutputNodeUI,
    'io/ExtractSymbolsNodeUI': ExtractSymbolsNodeUI,
    'llm/LLMMessagesBuilderNodeUI': LLMMessagesBuilderNodeUI,
    'llm/OllamaChatNodeUI': OllamaChatNodeUI,
    'llm/SystemPromptLoaderNodeUI': SystemPromptLoaderNodeUI,
    'market/ADXFilterNodeUI': ADXFilterNodeUI,
    'market/AtrXFilterNodeUI': AtrXFilterNodeUI,
    'market/AtrXIndicatorNodeUI': AtrXIndicatorNodeUI,
    'market/PolygonBatchCustomBarsNodeUI': PolygonBatchCustomBarsNodeUI,
    'market/PolygonCustomBarsNodeUI': PolygonCustomBarsNodeUI,
    'market/PolygonUniverseNodeUI': PolygonUniverseNodeUI,
    'market/RSIFilterNodeUI': RSIFilterNodeUI,
    'market/SMACrossoverFilterNodeUI': SMACrossoverFilterNodeUI,
};

async function openSettings(missingKeys: string[] = []) {
    try {
        // Use last known missing keys if none provided
        if ((!missingKeys || missingKeys.length === 0) && Array.isArray((window as any).getLastMissingKeys?.())) {
            try { missingKeys = (window as any).getLastMissingKeys(); } catch { /* ignore */ }
        }

        const response = await fetch('/api_keys');
        if (!response.ok) {
            throw new Error(`Failed to fetch API keys: ${response.status} ${response.statusText}`);
        }
        const data = await response.json();
        let keys = data.keys;

        // Filter out confusing 'NEW_KEY' if it's empty
        keys = Object.fromEntries(
            Object.entries(keys).filter(([key, value]) => !(key === 'NEW_KEY' && (!value || value === '')))
        );

        // If there are missing keys, ensure they are in the form (with empty value)
        missingKeys.forEach(key => {
            if (!Object.prototype.hasOwnProperty.call(keys, key)) {
                keys[key] = '';
            }
        });

        // Fetch known key metadata for tooltips (fallback to defaults if unavailable)
        let keyMeta: { [key: string]: { description?: string; docs_url?: string } } = {};
        try {
            const metaResp = await fetch('/api_keys/meta');
            if (metaResp.ok) {
                keyMeta = (await metaResp.json()).meta || {};
            }
        } catch { /* ignore */ }
        const keyDescriptions: { [key: string]: string } = {
            'POLYGON_API_KEY': keyMeta['POLYGON_API_KEY']?.description || 'API key for Polygon.io market data. Get one at polygon.io.',
            'TAVILY_API_KEY': keyMeta['TAVILY_API_KEY']?.description || 'API key for Tavily search. Sign up at tavily.com.',
            'OLLAMA_API_KEY': keyMeta['OLLAMA_API_KEY']?.description || 'Optional key for Ollama API access.'
        };

        // Sort entries: missing first, then alphabetical
        const entries = Object.entries(keys).sort((a, b) => {
            const aMissing = missingKeys.includes(a[0]) ? 0 : 1;
            const bMissing = missingKeys.includes(b[0]) ? 0 : 1;
            if (aMissing !== bMissing) return aMissing - bMissing;
            return a[0].localeCompare(b[0]);
        });

        // Missing banner
        const banner = (missingKeys && missingKeys.length > 0)
            ? `
        <div id="missing-keys-banner" style="margin:8px 0; padding:8px; border-radius:6px; background:#331; color:#f88; border:1px solid #633;">
            <div style="margin-bottom:6px; font-weight:bold;">Missing keys for this graph</div>
            <div>
                ${missingKeys.map(k => `<span class="missing-chip" style="display:inline-block; margin:2px; padding:2px 8px; border-radius:12px; background:#522; color:#fdd; font-size:12px;">${k}</span>`).join(' ')}
            </div>
            <div style="margin-top:6px; font-size:12px; opacity:0.9;">Fill the highlighted inputs below. You can add custom keys too.</div>
        </div>`
            : '';

        const privacyNote = `
            <div class="privacy-note">
                🔒 API keys are stored locally in your .env file and never sent to remote servers.
            </div>
        `;

        let formHtml = `<h2>API Key Settings</h2>${banner}${privacyNote}<form id="settings-form">`;
        for (const [key, value] of entries) {
            const isMissing = missingKeys.includes(key);
            const desc = keyDescriptions[key] || 'Custom API key';
            formHtml += `
            <div class="key-entry ${isMissing ? 'missing-key' : ''}" data-key="${key}">
                <div class="key-entry-header">
                    <span class="key-label" title="${desc}">${key}</span>
                    <button type="button" class="remove-key-btn" data-key="${key}">Remove</button>
                </div>
                <label>
                    <input type="password" name="${key}" value="${value || ''}" placeholder="Enter ${key}">
                </label>
            </div>`;
        }
        formHtml += `
        <div id="add-key-form" style="display: none;" class="add-key-inline">
            <div class="add-key-inputs">
                <input type="text" id="new-key-name" placeholder="KEY_NAME" class="new-key-input">
                <input type="password" id="new-key-value" placeholder="value" class="new-key-input">
            </div>
            <div class="add-key-actions">
                <button type="button" id="confirm-add-key" class="btn-confirm-add">Add</button>
                <button type="button" id="cancel-add-key" class="btn-cancel-add">Cancel</button>
            </div>
        </div>
        <div class="button-group">
            <div class="button-group-left">
                <button type="button" id="add-key">+ Add Key</button>
                <button type="button" id="validate-keys">Validate</button>
            </div>
            <div class="button-group-right">
                <button type="button" id="close-settings">Cancel</button>
                <button type="submit">Save</button>
            </div>
        </div>
    </form>`;

        const modal = document.createElement('div');
        modal.id = 'settings-modal';
        modal.innerHTML = formHtml;

        // Create backdrop
        const backdrop = document.createElement('div');
        backdrop.style.position = 'fixed';
        backdrop.style.top = '0';
        backdrop.style.left = '0';
        backdrop.style.right = '0';
        backdrop.style.bottom = '0';
        backdrop.style.background = 'rgba(0, 0, 0, 0.6)';
        backdrop.style.zIndex = '2999';
        backdrop.onclick = () => {
            modal.remove();
            backdrop.remove();
        };

        document.body.appendChild(backdrop);
        document.body.appendChild(modal);

        document.getElementById('close-settings')?.addEventListener('click', () => {
            modal.remove();
            backdrop.remove();
        });

        document.getElementById('settings-form')?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target as HTMLFormElement);
            for (const [key, value] of formData.entries()) {
                await fetch('/api_keys', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ key_name: key, value: value as string })
                });
            }
            // Re-validate required keys for current graph; keep dialog open if still missing
            try {
                const graphData = (window as any).getCurrentGraphData?.() || { nodes: [], links: [] };
                const required = await (window as any).getRequiredKeysForGraph?.(graphData);
                const missing = required && required.length ? await (window as any).checkMissingKeys?.(required) : [];
                if (missing && missing.length > 0) {
                    try { alert(`Still missing: ${missing.join(', ')}`); } catch { /* ignore */ }
                    (window as any).setLastMissingKeys?.(missing);
                    modal.remove();
                    backdrop.remove();
                    openSettings(missing);
                } else {
                    modal.remove();
                    backdrop.remove();
                }
            } catch {
                modal.remove();
                backdrop.remove();
            }
        });

        // Inline Add Key form logic
        const addKeyForm = document.getElementById('add-key-form');
        const addKeyBtn = document.getElementById('add-key');
        const confirmAddBtn = document.getElementById('confirm-add-key');
        const cancelAddBtn = document.getElementById('cancel-add-key');
        const newKeyNameInput = document.getElementById('new-key-name') as HTMLInputElement;
        const newKeyValueInput = document.getElementById('new-key-value') as HTMLInputElement;

        addKeyBtn?.addEventListener('click', () => {
            if (addKeyForm) {
                addKeyForm.style.display = 'flex';
                newKeyNameInput?.focus();
            }
            if (addKeyBtn) addKeyBtn.style.display = 'none';
        });

        cancelAddBtn?.addEventListener('click', () => {
            if (addKeyForm) addKeyForm.style.display = 'none';
            if (addKeyBtn) addKeyBtn.style.display = 'inline-block';
            if (newKeyNameInput) newKeyNameInput.value = '';
            if (newKeyValueInput) newKeyValueInput.value = '';
        });

        confirmAddBtn?.addEventListener('click', async () => {
            const keyName = newKeyNameInput?.value.trim().toUpperCase();
            const keyValue = newKeyValueInput?.value || '';

            if (!keyName) {
                try { alert('Key name is required'); } catch { /* ignore */ }
                return;
            }

            try {
                await fetch('/api_keys', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ key_name: keyName, value: keyValue })
                });
                modal.remove();
                backdrop.remove();
                openSettings(missingKeys);
            } catch (err) {
                console.error('Failed to add key:', err);
            }
        });

        // Enter key in inputs to confirm
        newKeyValueInput?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                confirmAddBtn?.click();
            } else if (e.key === 'Escape') {
                cancelAddBtn?.click();
            }
        });
        newKeyNameInput?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                newKeyValueInput?.focus();
            } else if (e.key === 'Escape') {
                cancelAddBtn?.click();
            }
        });

        // New: Remove Key button logic (per key)
        modal.querySelectorAll('.remove-key-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const keyToRemove = (e.target as HTMLElement).dataset.key;
                if (keyToRemove && confirm(`Remove ${keyToRemove}? This will delete it from .env.`)) {
                    fetch('/api_keys', {
                        method: 'DELETE',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ key_name: keyToRemove })
                    }).then(() => {
                        // Refresh modal
                        modal.remove();
                        backdrop.remove();
                        openSettings(missingKeys);
                    });
                }
            });
        });

        // Focus first missing key input, if any
        try {
            const firstMissing = modal.querySelector('.key-entry.missing-key input') as HTMLInputElement | null;
            if (firstMissing) firstMissing.focus();
        } catch { /* ignore */ }

        // Validate keys button
        document.getElementById('validate-keys')?.addEventListener('click', async () => {
            try {
                const graphData = (window as any).getCurrentGraphData?.() || { nodes: [], links: [] };
                const required = await (window as any).getRequiredKeysForGraph?.(graphData);
                const missing = required && required.length ? await (window as any).checkMissingKeys?.(required) : [];
                if (missing && missing.length > 0) {
                    (window as any).setLastMissingKeys?.(missing);
                    modal.remove();
                    backdrop.remove();
                    openSettings(missing);
                } else {
                    try { alert('All required keys present'); } catch { /* ignore */ }
                }
            } catch (err) {
                console.error('Validate keys failed:', err);
            }
        });
    } catch (error) {
        console.error('Failed to open settings:', error);
        alert(`Failed to open settings: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
}

// Make openSettings global for websocket.ts
(window as any).openSettings = openSettings;

// Track last missing keys to persist context across dialog sessions
let lastMissingKeys: string[] = [];
function setLastMissingKeys(keys: string[]) {
    try { lastMissingKeys = Array.from(new Set(Array.isArray(keys) ? keys : [])); } catch { lastMissingKeys = []; }
}
function getLastMissingKeys() { return lastMissingKeys.slice(); }
(window as any).setLastMissingKeys = setLastMissingKeys;
(window as any).getLastMissingKeys = getLastMissingKeys;

async function createEditor(container: HTMLElement) {
    try {
        updateStatus('loading', 'Initializing...');

        const graph = new LGraph();
        const canvasElement = container.querySelector('#litegraph-canvas') as HTMLCanvasElement;
        const canvas = new LGraphCanvas(canvasElement, graph);
        (canvas as unknown as { showSearchBox: () => void }).showSearchBox = () => { };

        let currentGraphName = 'untitled.json';
        const AUTOSAVE_KEY = 'fig-nodes:autosave:v1';
        let lastSavedGraphJson = '';
        let initialLoadCancelled = false;

        const getGraphName = () => currentGraphName;
        const updateGraphName = (name: string) => {
            currentGraphName = name;
            const graphNameEl = document.getElementById('graph-name');
            if (graphNameEl) graphNameEl.textContent = name;
        };

        const safeLocalStorageSet = (key: string, value: string) => {
            try {
                localStorage.setItem(key, value);
            } catch (err) {
                console.error('Autosave failed:', err);
                updateStatus('disconnected', 'Autosave failed: Check storage settings');
            }
        };
        const safeLocalStorageGet = (key: string): string | null => {
            try { return localStorage.getItem(key); } catch { return null; }
        };
        const doAutosave = () => {
            try {
                const data = graph.serialize();
                const json = JSON.stringify(data);
                if (json !== lastSavedGraphJson) {
                    const payload = { graph: data, name: getGraphName() }; // Removed timestamp
                    safeLocalStorageSet(AUTOSAVE_KEY, JSON.stringify(payload));
                    lastSavedGraphJson = json;
                }
            } catch { /* ignore */ }
        };

        let lastMouseEvent: MouseEvent | null = null;

        // Tooltip setup
        const tooltip = document.createElement('div');
        tooltip.className = 'litegraph-tooltip';
        tooltip.style.display = 'none';
        tooltip.style.position = 'absolute';
        tooltip.style.pointerEvents = 'none';
        tooltip.style.background = 'rgba(0, 0, 0, 0.85)';
        tooltip.style.color = 'white';
        tooltip.style.padding = '4px 8px';
        tooltip.style.borderRadius = '4px';
        tooltip.style.font = '12px Arial';
        tooltip.style.zIndex = '1000';
        document.body.appendChild(tooltip);

        canvasElement.addEventListener('mousemove', (e: MouseEvent) => {
            lastMouseEvent = e;
            // Check for slot hover and show tooltip
            const p = canvas.convertEventToCanvasOffset(e) as unknown as number[];
            let hoveringSlot = false;
            graph._nodes.forEach(node => {
                // Check inputs
                node.inputs?.forEach((input, i) => {
                    if (input.tooltip) {
                        const slotPos = node.getConnectionPos(true, i);
                        const dx = p[0] - slotPos[0];
                        const dy = p[1] - slotPos[1];
                        if (dx * dx + dy * dy < 8 * 8) {  // Within ~8px radius
                            tooltip.textContent = input.tooltip;
                            tooltip.style.left = `${e.clientX + 15}px`;
                            tooltip.style.top = `${e.clientY - 15}px`;
                            tooltip.style.display = 'block';
                            hoveringSlot = true;
                        }
                    }
                });
                // Check outputs similarly if needed
                node.outputs?.forEach((output, i) => {
                    if (output.tooltip) {
                        const slotPos = node.getConnectionPos(false, i);
                        const dx = p[0] - slotPos[0];
                        const dy = p[1] - slotPos[1];
                        if (dx * dx + dy * dy < 8 * 8) {
                            tooltip.textContent = output.tooltip;
                            tooltip.style.left = `${e.clientX + 15}px`;
                            tooltip.style.top = `${e.clientY - 15}px`;
                            tooltip.style.display = 'block';
                            hoveringSlot = true;
                        }
                    }
                });
            });
            if (!hoveringSlot) {
                tooltip.style.display = 'none';
            }
        });
        (canvas as unknown as { getLastMouseEvent: () => MouseEvent | null }).getLastMouseEvent = () => lastMouseEvent;

        const showQuickPrompt = (
            title: string,
            value: unknown,
            callback: (v: unknown) => void,
            options?: { type?: 'number' | 'text'; input?: 'number' | 'text'; step?: number; min?: number }
        ) => {
            const numericOnly = (options && (options.type === 'number' || options.input === 'number')) || typeof value === 'number';

            const overlay = document.createElement('div');
            overlay.className = 'quick-input-overlay';

            const dialog = document.createElement('div');
            dialog.className = 'quick-input-dialog';

            const label = document.createElement('div');
            label.className = 'quick-input-label';
            label.textContent = title || 'Value';

            const input = document.createElement('input');
            input.className = 'quick-input-field';
            input.type = numericOnly ? 'number' : 'text';
            input.value = (value !== undefined && value !== null) ? String(value) : '';
            if (numericOnly) {
                input.setAttribute('step', options?.step?.toString() || '1');
                input.setAttribute('min', options?.min?.toString() || '0');
            }

            const okButton = document.createElement('button');
            okButton.className = 'quick-input-ok';
            okButton.textContent = 'OK';

            const submit = () => {
                let out: string | number = input.value;
                if (numericOnly) {
                    const n = Number(out);
                    if (!Number.isFinite(n)) return;
                    out = Math.floor(n);
                }
                if (overlay.parentNode) document.body.removeChild(overlay);
                try { callback(out); } catch { /* ignore */ }
            };
            const cancel = () => { if (overlay.parentNode) document.body.removeChild(overlay); };

            okButton.addEventListener('click', submit);
            input.addEventListener('keydown', (ev) => {
                ev.stopPropagation();
                if (ev.key === 'Enter') submit();
                else if (ev.key === 'Escape') cancel();
            });
            overlay.addEventListener('click', (ev) => {
                if (ev.target === overlay) cancel();
            });

            dialog.appendChild(label);
            dialog.appendChild(input);
            dialog.appendChild(okButton);
            overlay.appendChild(dialog);
            document.body.appendChild(overlay);

            const ev = lastMouseEvent;
            if (ev) {
                dialog.style.position = 'absolute';
                dialog.style.left = `${ev.clientX}px`;
                dialog.style.top = `${ev.clientY - 28}px`;
                overlay.style.background = 'transparent';
                overlay.style.pointerEvents = 'none';
                dialog.style.pointerEvents = 'auto';
            }

            input.focus();
            input.select();
        };

        (canvas as unknown as { prompt: typeof showQuickPrompt }).prompt = showQuickPrompt;
        (LiteGraph as unknown as { prompt: typeof showQuickPrompt }).prompt = showQuickPrompt;

        const { allItems } = await registerNodes();

        const palette = setupPalette(allItems, canvas, graph);

        setupEventListeners(canvasElement, canvas, graph, palette);

        const progressRoot = document.getElementById('top-progress');
        const progressBar = document.getElementById('top-progress-bar');
        const progressText = document.getElementById('top-progress-text');
        if (progressRoot && progressBar && progressText) {
            // Keep the top bar visible to display status text; just reset the bar itself
            progressRoot.style.display = 'block';
            (progressBar as HTMLElement).style.width = '0%';
            progressBar.classList.remove('indeterminate');
            // Do not clear progressText here; it is used for status messages
        }

        setupWebSocket(graph, canvas);
        setupResize(canvasElement, canvas);
        setupKeyboard(graph);

        // Expose current graph data for validation flows
        (window as any).getCurrentGraphData = () => {
            try { return graph.serialize(); } catch { return { nodes: [], links: [] }; }
        };

        // Attempt to restore from autosave first; fallback to default graph
        let restoredFromAutosave = false;
        try {
            const saved = safeLocalStorageGet(AUTOSAVE_KEY);
            if (saved) {
                const parsed = JSON.parse(saved);
                if (parsed && Array.isArray(parsed.graph?.nodes) && Array.isArray(parsed.graph?.links)) {
                    // Set name immediately so UI reflects autosave even if configure fails
                    updateGraphName(parsed.name || 'autosave.json');
                    try {
                        graph.configure(parsed.graph);
                    } catch (configError) {
                        // Keep going without throwing; we still consider autosave restored to avoid overwriting with default graph
                        console.error('Failed to configure graph from autosave:', configError);
                    }
                    try { canvas.draw(true); } catch { /* ignore */ }
                    try { lastSavedGraphJson = JSON.stringify(graph.serialize()); } catch { lastSavedGraphJson = ''; }
                    restoredFromAutosave = true;
                }
            }
        } catch {
            restoredFromAutosave = false;
        }

        if (!restoredFromAutosave) {
            try {
                const resp = await fetch('/examples/default-graph.json', { cache: 'no-store' });
                if (!resp.ok) throw new Error('Response not OK');
                const json = await resp.json();
                if (initialLoadCancelled) {
                    // User initiated a new graph before default graph finished loading; skip applying default
                } else if (json && json.nodes && json.links) {
                    graph.configure(json);
                    canvas.draw(true);
                    updateGraphName('default-graph.json');
                    try { lastSavedGraphJson = JSON.stringify(graph.serialize()); } catch { lastSavedGraphJson = ''; }
                }
            } catch (e) { /* ignore */ }
        }

        // Autosave on interval and on unload
        const autosaveInterval = window.setInterval(doAutosave, 2000);
        window.addEventListener('beforeunload', () => {
            doAutosave();
            window.clearInterval(autosaveInterval);
        });

        // New graph handler
        const newBtn = document.getElementById('new');
        if (newBtn) {
            newBtn.addEventListener('click', () => {
                initialLoadCancelled = true;
                graph.clear();
                canvas.draw(true);
                updateGraphName('untitled.json');
                lastSavedGraphJson = '';
                doAutosave();
            });
        }

        const setupFileHandling = (graph: LGraph, canvas: LGraphCanvas, updateGraphName: (name: string) => void, getGraphName: () => string) => {
            document.getElementById('save')?.addEventListener('click', () => {
                const graphData = graph.serialize();
                const blob = new Blob([JSON.stringify(graphData, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = getGraphName();
                a.click();
                URL.revokeObjectURL(url);
            });

            const fileInput = document.getElementById('graph-file') as HTMLInputElement;
            document.getElementById('load')?.addEventListener('click', () => {
                fileInput.click();
            });

            fileInput.addEventListener('change', async (event) => {
                const file = (event.target as HTMLInputElement).files?.[0];
                if (file) {
                    const processContent = async (content: string) => {
                        try {
                            const graphData = JSON.parse(content);
                            graph.configure(graphData);
                            try { lastSavedGraphJson = JSON.stringify(graph.serialize()); } catch { lastSavedGraphJson = ''; }
                            canvas.draw(true);
                            updateGraphName(file.name);

                            // New: Proactive API key check after load
                            const requiredKeys = await getRequiredKeysForGraph(graphData);
                            if (requiredKeys.length > 0) {
                                const missing = await checkMissingKeys(requiredKeys);
                                if (missing.length > 0) {
                                    alert(`Missing API keys for this graph: ${missing.join(', ')}. Please set them in the settings menu.`);
                                    openSettings(missing);  // Pass missing keys
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
                        reader.onload = async (e) => { await processContent(e.target?.result as string); };
                        reader.readAsText(file);
                    }
                }
            });
        };

        setupFileHandling(graph, canvas, updateGraphName, getGraphName);

        // Add API Keys button to footer center (with file controls for logical grouping)
        const footerCenter = document.querySelector('.footer-center .file-controls');
        if (footerCenter) {
            const apiKeysBtn = document.createElement('button');
            apiKeysBtn.id = 'api-keys-btn';
            apiKeysBtn.innerHTML = '🔐 API Keys';
            apiKeysBtn.className = 'btn-secondary';
            apiKeysBtn.title = 'Manage API keys for external services';
            apiKeysBtn.addEventListener('click', () => openSettings());
            footerCenter.appendChild(apiKeysBtn);
        }

        graph.start();
        updateStatus('connected', 'Ready');
    } catch (error) {
        updateStatus('disconnected', 'Initialization failed');
    }
}

async function registerNodes() {
    const response = await fetch('/nodes');
    if (!response.ok) throw new Error(`Failed to fetch nodes: ${response.statusText}`);
    const meta = await response.json();

    const categorizedNodes: { [key: string]: string[] } = {};
    const allItems: { name: string; category: string; description?: string }[] = [];
    for (const name in meta.nodes) {
        const data = meta.nodes[name];
        let NodeClass = BaseCustomNode;

        if (data.uiModule) {
            const uiClass = UI_MODULES[data.uiModule];
            if (uiClass) {
                NodeClass = uiClass;
            } else {
                console.warn(`UI module ${data.uiModule} not found in static map`);
            }
        }

        const CustomClass = class extends NodeClass { constructor() { super(name, data); } };
        LiteGraph.registerNodeType(name, CustomClass as any);

        const category = data.category || 'Utilities';
        if (!categorizedNodes[category]) categorizedNodes[category] = [];
        categorizedNodes[category].push(name);
        allItems.push({ name, category, description: data.description });
    }
    return { allItems, categorizedNodes };
}

// Add these helper functions before setupFileHandling
let nodeMetadata: any = null;

async function getNodeMetadata() {
    if (!nodeMetadata) {
        const response = await fetch('/nodes');
        if (!response.ok) throw new Error('Failed to fetch node metadata');
        nodeMetadata = (await response.json()).nodes;
    }
    return nodeMetadata;
}

async function getRequiredKeysForGraph(graphData: any): Promise<string[]> {
    const meta = await getNodeMetadata();
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

async function checkMissingKeys(requiredKeys: string[]): Promise<string[]> {
    const response = await fetch('/api_keys');
    if (!response.ok) throw new Error('Failed to fetch current keys');
    const currentKeys = (await response.json()).keys;
    return requiredKeys.filter(key => !currentKeys[key] || currentKeys[key] === '');
}

// Expose helper functions globally for pre-execution checks
(window as any).getRequiredKeysForGraph = getRequiredKeysForGraph;
(window as any).checkMissingKeys = checkMissingKeys;

function setupEventListeners(canvasElement: HTMLCanvasElement, canvas: LGraphCanvas, graph: LGraph, palette: ReturnType<typeof setupPalette>) {
    document.addEventListener('keydown', (e: KeyboardEvent) => {
        if (!palette.paletteVisible && e.key === 'Tab' && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)) {
            e.preventDefault();
            palette.openPalette();
            return;
        }
        if (palette.paletteVisible) {
            if (e.key === 'Escape') {
                e.preventDefault();
                palette.closePalette();
                return;
            }
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (palette.filtered.length) palette.selectionIndex = (palette.selectionIndex + 1) % palette.filtered.length;
                palette.updateSelectionHighlight();
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                if (palette.filtered.length) palette.selectionIndex = (palette.selectionIndex - 1 + palette.filtered.length) % palette.filtered.length;
                palette.updateSelectionHighlight();
            } else if (e.key === 'Enter') {
                e.preventDefault();
                palette.addSelectedNode();
            }
            return;
        }

        if ((e.key === 'Delete' || e.key === 'Backspace') && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)) {
            e.preventDefault();
            const selectedNodes = (canvas as any).selected_nodes || {};
            const nodesToDelete = Object.values(selectedNodes);
            if (nodesToDelete.length > 0) {
                nodesToDelete.forEach((node: any) => {
                    graph.remove(node);
                });
                canvas.draw(true, true);
            }
        }
    });

    canvasElement.addEventListener('contextmenu', (_e: MouseEvent) => { });

    const findNodeUnderEvent = (e: MouseEvent): any | null => {
        const p = canvas.convertEventToCanvasOffset(e) as unknown as number[];
        const x = p[0];
        const y = p[1];
        const getNodeOnPos = (graph as any).getNodeOnPos?.bind(graph);
        if (typeof getNodeOnPos === 'function') {
            try {
                const nodeAtPos = getNodeOnPos(x, y);
                if (nodeAtPos) return nodeAtPos;
            } catch { }
        }
        const nodes = (graph as any)._nodes as any[] || [];
        for (let i = nodes.length - 1; i >= 0; i--) {
            const node = nodes[i];
            if (typeof node.isPointInside === 'function' && node.isPointInside(x, y)) return node;
        }
        return null;
    };

    canvasElement.addEventListener('dblclick', (e: MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();
        const node = findNodeUnderEvent(e);
        if (node) {
            if (typeof node.onDblClick === 'function') {
                try {
                    const canvasPos = canvas.convertEventToCanvasOffset(e) as unknown as number[];
                    const localPos = [canvasPos[0] - node.pos[0], canvasPos[1] - node.pos[1]];
                    const handled = node.onDblClick(e, localPos, canvas);
                    if (handled) return;
                } catch { }
            }
            return;
        }
        palette.openPalette(e);
    });

    canvasElement.addEventListener('click', () => {
        canvasElement.focus();
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const container = document.querySelector('.app-container') as HTMLElement;
    if (container) createEditor(container);
    else console.error('Canvas container not found');
});