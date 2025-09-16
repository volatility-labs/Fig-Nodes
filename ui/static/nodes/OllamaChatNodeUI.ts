import BaseCustomNode from './BaseCustomNode';

export default class OllamaChatNodeUI extends BaseCustomNode {
    constructor(title: string, data: any) {
        super(title, data);
        this.size = [320, 160];
        this.color = '#1f2a44';
        this.bgcolor = '#0b1220';

        // Replace boolean params (stream, think) with explicit toggles for reliability
        try {
            const widgets = (this as any).widgets as any[] | undefined;
            if (widgets && Array.isArray(widgets)) {
                // Remove auto-generated widgets for these params and any hidden ones
                const namesToReplace = new Set(['Title', 'stream', 'think', 'keep_alive', 'options', 'seed', 'seed_mode', 'temperature']);
                for (let i = widgets.length - 1; i >= 0; i--) {
                    const w = widgets[i];
                    if (w && namesToReplace.has(w.name)) {
                        widgets.splice(i, 1);
                    }
                }
            }
        } catch { /* no-op */ }

        // Add robust boolean toggles bound to node properties
        const currentStream = typeof this.properties['stream'] === 'boolean' ? this.properties['stream'] : true;
        const currentThink = typeof this.properties['think'] === 'boolean' ? this.properties['think'] : false;
        // Keep internal defaults for hidden params
        if (!this.properties['keep_alive']) this.properties['keep_alive'] = '1h';
        if (this.properties['options'] === undefined) this.properties['options'] = '';
        if (this.properties['temperature'] === undefined) this.properties['temperature'] = 0.7;
        if (!this.properties['seed_mode']) this.properties['seed_mode'] = 'fixed';
        if (this.properties['seed'] === undefined) this.properties['seed'] = 0;

        this.properties['stream'] = currentStream;
        this.properties['think'] = currentThink;

        this.addWidget('toggle', 'stream', currentStream, (v: boolean) => {
            this.properties['stream'] = !!v;
        }, {});
        this.addWidget('toggle', 'think', currentThink, (v: boolean) => {
            this.properties['think'] = !!v;
        }, {});

        // Temperature control
        this.addWidget('slider', 'temperature', this.properties['temperature'], (v: number) => {
            this.properties['temperature'] = v;
        }, { min: 0.0, max: 1.5, step: 0.05 });

        // Seed controls (ComfyUI-like): mode + value + helpers
        this.addWidget('combo', 'seed_mode', this.properties['seed_mode'], (v: string) => {
            this.properties['seed_mode'] = v;
        }, { values: ['fixed', 'random', 'increment'] });
        this.addWidget('number', 'seed', this.properties['seed'], (v: number) => {
            this.properties['seed'] = Math.max(0, Math.floor(Number(v) || 0));
        }, { min: 0, step: 1 });

        // JSON mode toggle (boolean). Server derives Ollama format from this.
        const currentJsonMode = typeof this.properties['json_mode'] === 'boolean' ? this.properties['json_mode'] : false;
        this.properties['json_mode'] = currentJsonMode;
        this.addWidget('toggle', 'json_mode', currentJsonMode, (v: boolean) => {
            this.properties['json_mode'] = !!v;
        }, {});

        // Convenience buttons (optional UX helpers)
        this.addWidget('button', 'Clear Stream', '', () => {
            this.displayText = '';
            this.setDirtyCanvas(true, true);
        }, {});
        this.addWidget('button', 'Copy Last', '', () => {
            const text = this.displayText || '';
            if (text) navigator.clipboard.writeText(text);
        }, {});
    }

    onStreamUpdate(_data: any) {
        const text = _data?.assistant_text;
        const finalMsg = _data?.assistant_message;
        const error = _data?.metrics?.error;

        if (error) {
            this.displayText = `❌ Error: ${error}`;
            this.color = '#722f37';
            this.bgcolor = '#2d1b1e';
        } else if (typeof text === 'string') {
            this.displayText = text;
            this.color = '#1f2a44';
            this.bgcolor = '#0b1220';
        } else if (finalMsg && typeof finalMsg?.content === 'string') {
            this.displayText = finalMsg.content;
            this.color = '#1f2a44';
            this.bgcolor = '#0b1220';
        }
        this.setDirtyCanvas(true, true);
    }

    updateDisplay(result: any) {
        // Check for errors first
        const error = result?.metrics?.error;
        if (error) {
            this.displayText = `❌ Error: ${error}`;
            this.color = '#722f37';
            this.bgcolor = '#2d1b1e';
            this.setDirtyCanvas(true, true);
            return;
        }

        // Prefer assistant_text, then assistant_message.content for non-stream responses
        const textPref = result?.assistant_text;
        const msg = result?.assistant_message || result?.output || result;
        const text = typeof textPref === 'string' ? textPref : (typeof msg === 'string' ? msg : (msg?.content || JSON.stringify(msg, null, 2)));
        this.displayText = text || '';
        this.color = '#1f2a44';
        this.bgcolor = '#0b1220';
        this.setDirtyCanvas(true, true);
    }
}


