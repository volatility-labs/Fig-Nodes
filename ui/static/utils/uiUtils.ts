export function updateStatus(status: 'connected' | 'disconnected' | 'loading' | 'executing', message?: string) {
    const indicator = document.getElementById('status-indicator');
    if (indicator) {
        indicator.className = `status-indicator ${status}`;
        // Use tooltip/aria label instead of visible text to avoid layout conflicts
        const label = message || status.charAt(0).toUpperCase() + status.slice(1);
        indicator.setAttribute('title', label);
        indicator.setAttribute('aria-label', label);
        if (indicator.firstChild) {
            indicator.textContent = '';
        }
    }

    // Mirror status text into the top progress bar label
    const progressRoot = document.getElementById('top-progress');
    const progressText = document.getElementById('top-progress-text');
    if (progressText) {
        progressText.textContent = message || status.charAt(0).toUpperCase() + status.slice(1);
    }
    // Keep the container visible so text can be shown even when the bar is idle
    if (progressRoot) {
        progressRoot.style.display = 'block';
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
    // Keyboard handling is now done in app.ts to avoid conflicts
    // This function is kept for backward compatibility but does nothing
}

export let showError: (message: string) => void = (message) => {
    const dialog = document.createElement('div');
    dialog.classList.add('error-dialog');

    const content = document.createElement('p');
    content.textContent = message;

    const button = document.createElement('button');
    button.textContent = 'OK';
    button.onclick = () => {
        document.body.removeChild(dialog);
    };

    dialog.appendChild(content);
    dialog.appendChild(button);
    document.body.appendChild(dialog);
};

export async function showTextEditor(initial: string, options?: { title?: string; placeholder?: string; monospace?: boolean; width?: number; height?: number; }): Promise<string | null> {
    return new Promise((resolve) => {
        const overlay = document.createElement('div');
        overlay.classList.add('text-editor-overlay');

        const dialog = document.createElement('div');
        dialog.classList.add('text-editor-dialog');
        if (options?.width) dialog.style.width = `${options.width}px`;
        if (options?.height) dialog.style.height = `${options.height}px`;

        const title = document.createElement('h3');
        title.textContent = options?.title || 'Edit Text';
        dialog.appendChild(title);

        const textarea = document.createElement('textarea');
        textarea.classList.add('text-editor-textarea');
        if (options?.monospace !== false) textarea.classList.add('monospace');
        textarea.placeholder = options?.placeholder || '';
        textarea.value = initial || '';
        dialog.appendChild(textarea);

        const footer = document.createElement('div');
        footer.classList.add('text-editor-footer');

        const counter = document.createElement('div');
        counter.classList.add('text-editor-counter');
        const updateCounter = () => {
            counter.textContent = `${textarea.value.length} chars`;
        };
        updateCounter();

        const buttons = document.createElement('div');
        buttons.classList.add('text-editor-buttons');

        const cancelBtn = document.createElement('button');
        cancelBtn.classList.add('dialog-button');
        cancelBtn.textContent = 'Cancel (Esc)';
        cancelBtn.onclick = () => {
            document.body.removeChild(overlay);
            resolve(null);
        };

        const saveBtn = document.createElement('button');
        saveBtn.classList.add('dialog-button', 'primary');
        saveBtn.textContent = 'Save (Ctrl/Cmd+Enter)';
        const doSave = () => {
            const val = textarea.value;
            document.body.removeChild(overlay);
            resolve(val);
        };
        saveBtn.onclick = doSave;

        buttons.appendChild(cancelBtn);
        buttons.appendChild(saveBtn);

        footer.appendChild(counter);
        footer.appendChild(buttons);

        dialog.appendChild(footer);
        overlay.appendChild(dialog);
        document.body.appendChild(overlay);

        textarea.focus();
        textarea.selectionStart = textarea.value.length;
        textarea.selectionEnd = textarea.value.length;

        const keyHandler = (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                cancelBtn.click();
            } else if ((e.key === 'Enter' && (e.ctrlKey || e.metaKey))) {
                doSave();
            }
        };
        const inputHandler = () => updateCounter();
        document.addEventListener('keydown', keyHandler);
        textarea.addEventListener('input', inputHandler);

        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                cancelBtn.click();
            }
        });

        const cleanup = () => {
            document.removeEventListener('keydown', keyHandler);
            textarea.removeEventListener('input', inputHandler);
        };
        cancelBtn.addEventListener('click', cleanup);
        saveBtn.addEventListener('click', cleanup);
    });
}
