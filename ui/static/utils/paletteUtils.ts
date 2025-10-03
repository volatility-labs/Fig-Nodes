import { LGraphCanvas, LGraph, LiteGraph } from '@comfyorg/litegraph';

export function setupPalette(allItems: { name: string; category: string; description?: string }[], canvas: LGraphCanvas, graph: LGraph) {
    const overlay = document.getElementById('node-palette-overlay') as HTMLDivElement | null;
    const palette = document.getElementById('node-palette') as HTMLDivElement | null;
    const searchInput = document.getElementById('node-palette-search') as HTMLInputElement | null;
    const listContainer = document.getElementById('node-palette-list') as HTMLDivElement | null;

    let paletteVisible = false;
    let selectionIndex = 0;
    let filtered = allItems.slice();
    let lastCanvasPos: [number, number] = [0, 0];

    function updateSelectionHighlight() {
        if (!listContainer) return;
        const children = Array.from(listContainer.children) as HTMLElement[];
        children.forEach((el, i) => {
            if (i === selectionIndex) el.classList.add('selected');
            else el.classList.remove('selected');
        });
        const selectedEl = children[selectionIndex];
        if (selectedEl) selectedEl.scrollIntoView({ block: 'nearest' });
    }

    function renderList(items: typeof allItems) {
        if (!listContainer) return;
        listContainer.innerHTML = '';
        items.forEach((item, idx) => {
            const row = document.createElement('div');
            row.className = 'node-palette-item' + (idx === selectionIndex ? ' selected' : '');
            const title = document.createElement('div');
            title.className = 'node-palette-title';
            title.textContent = item.name;
            const subtitle = document.createElement('div');
            subtitle.className = 'node-palette-subtitle';
            subtitle.textContent = `${item.category}${item.description ? ' — ' + item.description : ''}`;
            row.appendChild(title);
            row.appendChild(subtitle);
            row.addEventListener('mouseenter', () => {
                selectionIndex = idx;
                updateSelectionHighlight();
            });
            row.addEventListener('click', () => addSelectedNode());
            listContainer.appendChild(row);
        });
    }

    function openPalette(event?: MouseEvent) {
        if (!overlay || !palette || !searchInput) return;
        paletteVisible = true;
        overlay.style.display = 'flex';
        selectionIndex = 0;
        filtered = allItems.slice();
        renderList(filtered);
        if (event) {
            const p = canvas.convertEventToCanvasOffset(event) as unknown as number[];
            lastCanvasPos = [p[0], p[1]];
        } else {
            const rect = canvas.canvas.getBoundingClientRect();
            const fakeEvent = { clientX: rect.left + rect.width / 2, clientY: rect.top + rect.height / 2 } as MouseEvent;
            const p = canvas.convertEventToCanvasOffset(fakeEvent) as unknown as number[];
            lastCanvasPos = [p[0], p[1]];
        }
        palette.style.position = '';
        palette.style.left = '';
        palette.style.top = '';
        searchInput.value = '';
        setTimeout(() => searchInput.focus(), 0);
    }

    function closePalette() {
        if (!overlay) return;
        paletteVisible = false;
        overlay.style.display = 'none';
    }

    function addSelectedNode() {
        const item = filtered[selectionIndex];
        if (!item) return;
        const node = LiteGraph.createNode(item.name);
        if (node) {
            node.pos = [lastCanvasPos[0], lastCanvasPos[1]];
            graph.add(node as any);
            canvas.draw(true, true);
        }
        closePalette();
    }

    if (overlay) {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closePalette();
        });
    }

    if (searchInput) {
        searchInput.addEventListener('input', () => {
            const q = searchInput.value.trim().toLowerCase();
            selectionIndex = 0;
            if (!q) {
                filtered = allItems.slice();
            } else {
                filtered = allItems.filter((x) =>
                    x.name.toLowerCase().includes(q) ||
                    x.category.toLowerCase().includes(q) ||
                    (x.description || '').toLowerCase().includes(q)
                );
            }
            renderList(filtered);
        });
    }

    return {
        openPalette,
        addSelectedNode,
        paletteVisible,
        get selectionIndex() { return selectionIndex; },
        set selectionIndex(val: number) { selectionIndex = val; },
        get filtered() { return filtered; },
        set filtered(val) { filtered = val; },
        lastCanvasPos,
        closePalette,
        updateSelectionHighlight,
        renderList
    };
}
