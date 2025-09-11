import BaseCustomNode from './BaseCustomNode';

export default class OllamaChatNodeUI extends BaseCustomNode {
    constructor(title: string, data: any) {
        super(title, data);
        this.size = [320, 160];
        this.color = '#1f2a44';
        this.bgcolor = '#0b1220';

        // Ensure textarea widgets are shown for options/format when present
        // Leave default widgets from BaseCustomNode intact

        // Convenience buttons
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
        const delta = _data?.delta;
        const final = _data?.assistant_message;
        if (typeof delta === 'string' && delta.length) {
            this.displayText = (this.displayText || '') + delta;
        }
        if (final && typeof final?.content === 'string') {
            this.displayText = final.content;
        }
        this.setDirtyCanvas(true, true);
    }

    updateDisplay(result: any) {
        // Prefer assistant_message.content for non-stream responses
        const msg = result?.assistant_message || result?.output || result;
        const text = typeof msg === 'string' ? msg : (msg?.content || JSON.stringify(msg, null, 2));
        this.displayText = text || '';
        this.setDirtyCanvas(true, true);
    }
}


