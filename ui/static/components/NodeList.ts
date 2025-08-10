import { LiteGraph } from '@comfyorg/litegraph';

export function createNodeList(meta: any, graph: any) {
    const nodeList = document.getElementById('node-list') as HTMLUListElement;
    if (!nodeList) return;

    nodeList.innerHTML = '';
    const categorizedNodes: { [key: string]: string[] } = {};

    for (const name in meta.nodes) {
        const data = meta.nodes[name];
        const category = data.category || 'Utilities';
        if (!categorizedNodes[category]) categorizedNodes[category] = [];
        categorizedNodes[category].push(name);
    }

    for (const category in categorizedNodes) {
        const categoryHeader = document.createElement('div');
        categoryHeader.className = 'node-category';
        categoryHeader.textContent = category;
        nodeList.appendChild(categoryHeader);

        categorizedNodes[category].forEach(name => {
            const li = document.createElement('li');
            const btn = document.createElement('button');
            btn.textContent = name;
            btn.title = meta.nodes[name].description || name;
            btn.addEventListener('click', () => {
                const node = LiteGraph.createNode(name);
                if (node) {
                    node.pos = [Math.random() * 300 + 100, Math.random() * 300 + 100];
                    graph.add(node);
                }
            });
            li.appendChild(btn);
            nodeList.appendChild(li);
        });
    }
}
