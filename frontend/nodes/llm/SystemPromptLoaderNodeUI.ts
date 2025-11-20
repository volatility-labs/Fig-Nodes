import BaseCustomNode from '../base/BaseCustomNode';

export default class SystemPromptLoaderNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [360, 220];
        this.displayResults = true; // Display loaded system prompt content

        // Wipe auto-generated widgets and add our own controls
        this.widgets = [];

        // File upload button
        this.addWidget('button', 'Upload .md/.txt', '', async () => {
            try { await this.pickFile(); } catch { }
        }, {});

        // Copy and Clear
        this.addWidget('button', 'Copy', '', () => {
            const text = (this.properties['content'] as string) || '';
            if (text) navigator.clipboard.writeText(text);
        }, {});
        this.addWidget('button', 'Clear', '', () => {
            this.properties['content'] = '';
            this.displayText = '';
            this.setDirtyCanvas(true, true);
        }, {});
    }

    async pickFile() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.txt,.md,text/plain,application/octet-stream';
        return new Promise<void>((resolve) => {
            input.onchange = () => {
                const file = input.files?.[0];
                if (!file) { resolve(); return; }
                const reader = new FileReader();
                reader.onload = () => {
                    const text = (reader.result as string) || '';
                    this.properties['content'] = text;
                    this.displayText = text;
                    this.setDirtyCanvas(true, true);
                    resolve();
                };
                reader.readAsText(file);
            };
            input.click();
        });
    }

    updateDisplay(result: any) {
        // Mirrors backend output if routed here; otherwise use properties
        const text = (result && (result.system || result.output)) || this.properties['content'] || '';
        this.displayText = typeof text === 'string' ? text : JSON.stringify(text, null, 2);
        this.setDirtyCanvas(true, true);
    }
}


