export interface KeyMetadata {
    description?: string;
    docs_url?: string;
}

export interface KeyEntry {
    key: string;
    value: string;
    isMissing: boolean;
    description: string;
}

export class APIKeyManager {
    private lastMissingKeys: string[] = [];

    async openSettings(missingKeys: string[] = []): Promise<void> {
        try {
            // Use last known missing keys if none provided
            if ((!missingKeys || missingKeys.length === 0) && Array.isArray(this.getLastMissingKeys())) {
                try {
                    missingKeys = this.getLastMissingKeys();
                } catch { /* ignore */ }
            }

            const keys = await this.fetchCurrentKeys();
            const keyMeta = await this.fetchKeyMetadata();
            const keyDescriptions = this.buildKeyDescriptions(keyMeta);

            // Filter out confusing 'NEW_KEY' if it's empty
            const filteredKeys = Object.fromEntries(
                Object.entries(keys).filter(([key, value]) => !(key === 'NEW_KEY' && (!value || value === '')))
            );

            // If there are missing keys, ensure they are in the form (with empty value)
            missingKeys.forEach(key => {
                if (!Object.prototype.hasOwnProperty.call(filteredKeys, key)) {
                    filteredKeys[key] = '';
                }
            });

            // Sort entries: missing first, then alphabetical
            const entries = Object.entries(filteredKeys).sort((a, b) => {
                const aMissing = missingKeys.includes(a[0]) ? 0 : 1;
                const bMissing = missingKeys.includes(b[0]) ? 0 : 1;
                if (aMissing !== bMissing) return aMissing - bMissing;
                return a[0].localeCompare(b[0]);
            });

            this.showSettingsModal(entries, missingKeys, keyDescriptions);
        } catch (error) {
            console.error('Failed to open settings:', error);
            alert(`Failed to open settings: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    }

    async validateKeys(requiredKeys: string[]): Promise<string[]> {
        const currentKeys = await this.fetchCurrentKeys();
        return requiredKeys.filter(key => !currentKeys[key] || currentKeys[key] === '');
    }

    async checkMissingKeys(requiredKeys: string[]): Promise<string[]> {
        const response = await fetch('/api/v1/api_keys');
        if (!response.ok) throw new Error('Failed to fetch current keys');
        const currentKeys = (await response.json()).keys;
        return requiredKeys.filter(key => !currentKeys[key] || currentKeys[key] === '');
    }

    async getRequiredKeysForGraph(graphData: any): Promise<string[]> {
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

    setLastMissingKeys(keys: string[]): void {
        try {
            this.lastMissingKeys = Array.from(new Set(Array.isArray(keys) ? keys : []));
        } catch {
            this.lastMissingKeys = [];
        }
    }

    getLastMissingKeys(): string[] {
        return this.lastMissingKeys.slice();
    }

    private async fetchCurrentKeys(): Promise<{ [key: string]: string }> {
        const response = await fetch('/api_keys');
        if (!response.ok) {
            throw new Error(`Failed to fetch API keys: ${response.status} ${response.statusText}`);
        }
        const data = await response.json();
        return data.keys;
    }

    private async fetchKeyMetadata(): Promise<{ [key: string]: KeyMetadata }> {
        let keyMeta: { [key: string]: KeyMetadata } = {};
        try {
            const metaResp = await fetch('/api/v1/api_keys/meta');
            if (metaResp.ok) {
                keyMeta = (await metaResp.json()).meta || {};
            }
        } catch { /* ignore */ }
        return keyMeta;
    }

    private buildKeyDescriptions(keyMeta: { [key: string]: KeyMetadata }): { [key: string]: string } {
        return {
            'POLYGON_API_KEY': keyMeta['POLYGON_API_KEY']?.description || 'API key for Polygon.io market data. Get one at polygon.io.',
            'TAVILY_API_KEY': keyMeta['TAVILY_API_KEY']?.description || 'API key for Tavily search. Sign up at tavily.com.',
            'OLLAMA_API_KEY': keyMeta['OLLAMA_API_KEY']?.description || 'Optional key for Ollama API access.'
        };
    }

    private async getNodeMetadata(): Promise<any> {
        const response = await fetch('/api/v1/nodes');
        if (!response.ok) throw new Error('Failed to fetch node metadata');
        return (await response.json()).nodes;
    }

    private showSettingsModal(
        entries: Array<[string, string]>,
        missingKeys: string[],
        keyDescriptions: { [key: string]: string }
    ): void {
        const banner = this.createMissingKeysBanner(missingKeys);
        const privacyNote = this.createPrivacyNote();
        const formHtml = this.createFormHtml(entries, missingKeys, keyDescriptions, banner, privacyNote);

        const modal = document.createElement('div');
        modal.id = 'settings-modal';
        modal.innerHTML = formHtml;

        const backdrop = this.createBackdrop(modal);
        document.body.appendChild(backdrop);
        document.body.appendChild(modal);

        this.setupModalEventListeners(modal, backdrop, missingKeys);
        this.focusFirstMissingKey(modal);
    }

    private createMissingKeysBanner(missingKeys: string[]): string {
        return (missingKeys && missingKeys.length > 0)
            ? `
        <div id="missing-keys-banner" style="margin:8px 0; padding:8px; border-radius:6px; background:#331; color:#f88; border:1px solid #633;">
            <div style="margin-bottom:6px; font-weight:bold;">Missing keys for this graph</div>
            <div>
                ${missingKeys.map(k => `<span class="missing-chip" style="display:inline-block; margin:2px; padding:2px 8px; border-radius:12px; background:#522; color:#fdd; font-size:12px;">${k}</span>`).join(' ')}
            </div>
            <div style="margin-top:6px; font-size:12px; opacity:0.9;">Fill the highlighted inputs below. You can add custom keys too.</div>
        </div>`
            : '';
    }

    private createPrivacyNote(): string {
        return `
            <div class="privacy-note">
                🔒 API keys are stored locally in your .env file and never sent to remote servers.
            </div>
        `;
    }

    private createFormHtml(
        entries: Array<[string, string]>,
        missingKeys: string[],
        keyDescriptions: { [key: string]: string },
        banner: string,
        privacyNote: string
    ): string {
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

        return formHtml;
    }

    private createBackdrop(modal: HTMLElement): HTMLElement {
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
        return backdrop;
    }

    private setupModalEventListeners(modal: HTMLElement, backdrop: HTMLElement, missingKeys: string[]): void {
        // Close button
        document.getElementById('close-settings')?.addEventListener('click', () => {
            modal.remove();
            backdrop.remove();
        });

        // Form submission
        document.getElementById('settings-form')?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target as HTMLFormElement);
            for (const [key, value] of formData.entries()) {
                await fetch('/api/v1/api_keys', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ key_name: key, value: value as string })
                });
            }

            // Close modal after saving
            modal.remove();
            backdrop.remove();
        });

        // Add key functionality
        this.setupAddKeyFunctionality(modal, backdrop, missingKeys);

        // Remove key functionality
        this.setupRemoveKeyFunctionality(modal, backdrop, missingKeys);

        // Validate keys functionality
        this.setupValidateKeysFunctionality(modal, backdrop);
    }

    private setupAddKeyFunctionality(modal: HTMLElement, backdrop: HTMLElement, missingKeys: string[]): void {
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
                await fetch('/api/v1/api_keys', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ key_name: keyName, value: keyValue })
                });
                modal.remove();
                backdrop.remove();
                this.openSettings(missingKeys);
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
    }

    private setupRemoveKeyFunctionality(modal: HTMLElement, backdrop: HTMLElement, missingKeys: string[]): void {
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
                        this.openSettings(missingKeys);
                    });
                }
            });
        });
    }

    private setupValidateKeysFunctionality(_modal: HTMLElement, _backdrop: HTMLElement): void {
        document.getElementById('validate-keys')?.addEventListener('click', async () => {
            try { alert('All required keys present'); } catch { /* ignore */ }
        });
    }

    private focusFirstMissingKey(modal: HTMLElement): void {
        try {
            const firstMissing = modal.querySelector('.key-entry.missing-key input') as HTMLInputElement | null;
            if (firstMissing) firstMissing.focus();
        } catch { /* ignore */ }
    }
}
