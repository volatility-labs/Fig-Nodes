import Rete from 'rete';
import AreaPlugin from 'rete-area-plugin';
import ConnectionPlugin from 'rete-connection-plugin';
import RenderPlugin from 'rete-render-utils';

class NumComponent extends Rete.Component {
    constructor() {
        super('Number');
    }

    builder(node) {
        const out1 = new Rete.Output('num', 'Number', Rete.Socket);
        node.addOutput(out1);
        return node;
    }
}

class DataProviderComponent extends Rete.Component {
    constructor() {
        super('Data Provider');
    }
    builder(node) {
        const out = new Rete.Output('data', 'Data', Rete.Socket);
        node.addOutput(out);
        return node;
    }
}

class IndicatorsComponent extends Rete.Component {
    constructor() {
        super('Indicators');
    }
    builder(node) {
        const inp = new Rete.Input('data', 'Data', Rete.Socket);
        const out = new Rete.Output('indicators', 'Indicators', Rete.Socket);
        node.addInput(inp).addOutput(out);
        return node;
    }
}

class ScoringComponent extends Rete.Component {
    constructor() {
        super('Scoring');
    }
    builder(node) {
        const inp = new Rete.Input('indicators', 'Indicators', Rete.Socket);
        const out = new Rete.Output('score', 'Score', Rete.Socket);
        node.addInput(inp).addOutput(out);
        return node;
    }
}

class TradingComponent extends Rete.Component {
    constructor() {
        super('Trading');
    }
    builder(node) {
        const inp1 = new Rete.Input('symbol', 'Symbol', Rete.Socket);
        const inp2 = new Rete.Input('score', 'Score', Rete.Socket);
        node.addInput(inp1).addInput(inp2);
        return node;
    }
}

// Add more components for our nodes later

async function createEditor(container) {
    const components = [new NumComponent(), new DataProviderComponent(), new IndicatorsComponent(), new ScoringComponent(), new TradingComponent()];

    const editor = new Rete.NodeEditor('trading-bot@0.1.0', container);
    editor.use(ConnectionPlugin);
    editor.use(RenderPlugin);
    editor.use(AreaPlugin);

    const engine = new Rete.Engine('trading-bot@0.1.0');

    components.forEach(c => {
        editor.register(c);
        engine.register(c);
    });

    // Fetch available nodes from backend
    const response = await fetch('/nodes');
    const { nodes } = await response.json();
    console.log('Available nodes:', nodes);

    // Example: Add a node
    const n1 = await components[0].createNode({});
    editor.addNode(n1);

    editor.on('process nodecreated noderemoved connectioncreated connectionremoved', async () => {
        await engine.abort();
        await engine.process(editor.toJSON());
    });

    document.getElementById('execute').addEventListener('click', async () => {
        const graph = editor.toJSON();
        const res = await fetch('/execute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(graph)
        });
        const result = await res.json();
        console.log('Execution result:', result);
    });
}

const container = document.querySelector('#rete');
createEditor(container); 