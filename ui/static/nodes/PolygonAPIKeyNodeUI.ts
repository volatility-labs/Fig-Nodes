import BaseCustomNode from './BaseCustomNode';

export default class PolygonAPIKeyNodeUI extends BaseCustomNode {
    constructor(title: string, data: any) {
        super(title, data);
        this.size = [280, 120];
        this.color = '#8b5a3c';  // Brown theme for security/key nodes
        this.bgcolor = '#3d2818';

        // Do not display results - this is a provider node
        this.displayResults = false;

        // Add a security indicator button
        this.addWidget('button', '🔒 Secure Key', '', () => {
            window.alert('API key is handled securely and not stored in workflow files.');
        }, {});
    }

    updateDisplay(result: any) {
        // Provider nodes typically don't show output in display text
        this.result = result;
        this.setDirtyCanvas(true, true);
    }
}
