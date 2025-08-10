export function updateStatus(status: 'connected' | 'disconnected' | 'loading' | 'executing', message?: string) {
    const indicator = document.getElementById('status-indicator');
    if (indicator) {
        indicator.className = `status-indicator ${status}`;
        indicator.textContent = message || status.charAt(0).toUpperCase() + status.slice(1);
    }
}

export function showLoading(show: boolean, message: string = "Executing...") {
    const overlay = document.getElementById('loading-overlay');
    const overlayText = overlay?.querySelector('span');
    if (overlay && overlayText) {
        overlay.style.display = show ? 'flex' : 'none';
        overlayText.textContent = message;
    }
}

export function setupResize(canvasElement: HTMLCanvasElement, canvas: any) {
    const resizeCanvas = () => {
        const rect = canvasElement.parentElement!.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;
        if (canvas.canvas.width !== rect.width * dpr || canvas.canvas.height !== rect.height * dpr) {
            canvas.canvas.width = rect.width * dpr;
            canvas.canvas.height = rect.height * dpr;
            canvas.canvas.style.width = `${rect.width}px`;
            canvas.canvas.style.height = `${rect.height}px`;
            const ctx = canvas.canvas.getContext('2d');
            if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        }
        canvas.draw(true, true);
    };
    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();
}

export function setupKeyboard(graph: any) {
    document.addEventListener('keydown', (e: KeyboardEvent) => {
        if ((e.key === 'Delete' || e.key === 'Backspace') && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)) {
            const selected = graph.selected_nodes || {};
            Object.values(selected).forEach((node: any) => graph.remove(node));
        }
    });
}
