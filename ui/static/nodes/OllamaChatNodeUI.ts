import BaseCustomNode from './BaseCustomNode';

export default class OllamaChatNodeUI extends BaseCustomNode {
    constructor(title: string, data: any) {
        super(title, data);
        // Increase size to accommodate all parameter widgets
        this.size = [320, 280];
        this.color = '#1f2a44';
        this.bgcolor = '#0b1220';

        // Convenience buttons only. Params come from backend via BaseCustomNode.
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
        const error = _data?.metrics?.error;
        const msg = _data?.message;
        let text: string | undefined;

        if (typeof msg === 'string') {
            text = msg;
        } else if (msg && typeof msg.content === 'string') {
            text = msg.content;
        }

        if (error) {
            this.displayText = `❌ Error: ${error}`;
            this.color = '#722f37';
            this.bgcolor = '#2d1b1e';
        } else if (typeof text === 'string') {
            this.displayText = text;
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

        // Message is now directly a string or object with content
        const msg = result?.message;
        let text: string;
        if (typeof msg === 'string') {
            text = msg;
        } else if (msg && typeof msg.content === 'string') {
            text = msg.content;
        } else if (typeof result === 'string') {
            text = result;
        } else {
            text = JSON.stringify(result, null, 2);
        }
        this.displayText = text || '';
        this.color = '#1f2a44';
        this.bgcolor = '#0b1220';
        this.setDirtyCanvas(true, true);
    }
}


