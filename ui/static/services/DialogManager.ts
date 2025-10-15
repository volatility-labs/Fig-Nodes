export interface DialogOptions {
    type?: 'number' | 'text';
    input?: 'number' | 'text';
    step?: number;
    min?: number;
    title?: string;
    placeholder?: string;
    monospace?: boolean;
    width?: number;
    height?: number;
}

export interface Position {
    x: number;
    y: number;
}

export class DialogManager {
    private lastMouseEvent: MouseEvent | null = null;

    setLastMouseEvent(event: MouseEvent): void {
        this.lastMouseEvent = event;
    }

    showQuickPrompt(
        title: string,
        value: unknown,
        callback: (v: unknown) => void,
        options?: DialogOptions
    ): void {
        const numericOnly = (options && (options.type === 'number' || options.input === 'number')) || typeof value === 'number';

        const overlay = document.createElement('div');
        overlay.className = 'quick-input-overlay';

        const dialog = document.createElement('div');
        dialog.className = 'quick-input-dialog';

        const label = document.createElement('div');
        label.className = 'quick-input-label';
        label.textContent = title || 'Value';

        const input = document.createElement('input');
        input.className = 'quick-input-field';
        input.type = numericOnly ? 'number' : 'text';
        input.value = (value !== undefined && value !== null) ? String(value) : '';
        if (numericOnly) {
            input.setAttribute('step', options?.step?.toString() || '1');
            input.setAttribute('min', options?.min?.toString() || '0');
        }

        const okButton = document.createElement('button');
        okButton.className = 'quick-input-ok';
        okButton.textContent = 'OK';

        const submit = () => {
            let out: string | number = input.value;
            if (numericOnly) {
                const n = Number(out);
                if (!Number.isFinite(n)) return;
                out = Math.floor(n);
            }
            if (overlay.parentNode) document.body.removeChild(overlay);
            try { callback(out); } catch { /* ignore */ }
        };
        const cancel = () => { if (overlay.parentNode) document.body.removeChild(overlay); };

        okButton.addEventListener('click', submit);
        input.addEventListener('keydown', (ev) => {
            ev.stopPropagation();
            if (ev.key === 'Enter') submit();
            else if (ev.key === 'Escape') cancel();
        });
        overlay.addEventListener('click', (ev) => {
            if (ev.target === overlay) cancel();
        });

        dialog.appendChild(label);
        dialog.appendChild(input);
        dialog.appendChild(okButton);
        overlay.appendChild(dialog);
        document.body.appendChild(overlay);

        const ev = this.lastMouseEvent;
        if (ev) {
            dialog.style.position = 'absolute';
            dialog.style.left = `${ev.clientX}px`;
            dialog.style.top = `${ev.clientY - 28}px`;
            overlay.style.background = 'transparent';
            overlay.style.pointerEvents = 'none';
            dialog.style.pointerEvents = 'auto';
        }

        input.focus();
        input.select();
    }

    showCustomPrompt(title: string, defaultValue: string, isPassword: boolean, callback: (value: string | null) => void): void {
        if (!isPassword) {
            this.showQuickValuePrompt(title || 'Value', defaultValue, false, (val) => callback(val));
            return;
        }

        const dialog = document.createElement('div');
        dialog.className = 'custom-input-dialog';

        const label = document.createElement('label');
        label.className = 'dialog-label';
        label.textContent = title;

        const input = document.createElement('input');
        input.className = 'dialog-input';
        input.type = 'password';
        input.value = defaultValue;

        const okButton = document.createElement('button');
        okButton.className = 'dialog-button';
        okButton.textContent = 'OK';
        okButton.onclick = () => {
            callback(input.value);
            document.body.removeChild(dialog);
        };

        dialog.appendChild(label);
        dialog.appendChild(input);
        dialog.appendChild(okButton);

        document.body.appendChild(dialog);
        input.focus();
        input.select();
    }

    showQuickValuePrompt(
        labelText: string,
        defaultValue: string | number,
        numericOnly: boolean,
        callback: (value: string | null) => void,
        position?: Position
    ): void {
        const overlay = document.createElement('div');
        overlay.className = 'quick-input-overlay';

        const dialog = document.createElement('div');
        dialog.className = 'quick-input-dialog';

        const label = document.createElement('div');
        label.className = 'quick-input-label';
        label.textContent = labelText || 'Value';

        const input = document.createElement('input');
        input.className = 'quick-input-field';
        input.type = numericOnly ? 'number' : 'text';
        input.value = String(defaultValue ?? '');
        input.spellcheck = false;

        const okButton = document.createElement('button');
        okButton.className = 'quick-input-ok';
        okButton.textContent = 'OK';

        const submit = () => {
            if (numericOnly) {
                const n = Number(input.value);
                if (!Number.isFinite(n)) {
                    return;
                }
                callback(String(Math.floor(n)));
            } else {
                callback(input.value);
            }
            document.body.removeChild(overlay);
        };

        const cancel = () => {
            callback(null);
            if (overlay.parentNode) document.body.removeChild(overlay);
        };

        okButton.addEventListener('click', submit);
        input.addEventListener('keydown', (ev) => {
            ev.stopPropagation();
            if (ev.key === 'Enter') submit();
            if (ev.key === 'Escape') cancel();
        });
        overlay.addEventListener('click', (ev) => {
            if (ev.target === overlay) cancel();
        });

        dialog.appendChild(label);
        dialog.appendChild(input);
        dialog.appendChild(okButton);
        overlay.appendChild(dialog);
        document.body.appendChild(overlay);

        try {
            const graph: any = (window as any).graph;
            const canvas = graph?.list_of_graphcanvas?.[0];
            const prompt = (canvas && (canvas as any).prompt) || (window as any).LiteGraph?.prompt;
            if (typeof prompt === 'function') {
                document.body.removeChild(overlay);
                prompt(labelText, defaultValue, (val: any) => {
                    if (numericOnly && val != null) {
                        const n = Number(val);
                        if (!Number.isFinite(n)) { callback(null); return; }
                        callback(String(Math.floor(n)));
                    } else {
                        callback(val == null ? null : String(val));
                    }
                }, { type: numericOnly ? 'number' : 'text', step: 1, min: 0 });
                return;
            }
        } catch { /* fall back to inline */ }

        if (position && Number.isFinite(position.x) && Number.isFinite(position.y)) {
            dialog.style.position = 'absolute';
            dialog.style.left = `${position.x}px`;
            dialog.style.top = `${position.y}px`;
            overlay.style.background = 'transparent';
            (overlay.style as any).pointerEvents = 'none';
            (dialog.style as any).pointerEvents = 'auto';
        }

        input.focus();
        input.select();
    }

    showCustomDropdown(paramName: string, options: any[], callback: (value: any) => void): void {
        const overlay = document.createElement('div');
        overlay.className = 'custom-dropdown-overlay';

        const menu = document.createElement('div');
        menu.className = 'custom-dropdown-menu';

        // Add search bar if there are many options
        const hasSearch = options.length > 10;
        let searchInput: HTMLInputElement | null = null;
        let filteredOptions = options.slice();

        if (hasSearch) {
            searchInput = document.createElement('input');
            searchInput.type = 'text';
            searchInput.className = 'custom-dropdown-search';
            searchInput.placeholder = 'Search...';
            searchInput.spellcheck = false;
            menu.appendChild(searchInput);
        }

        const itemsContainer = document.createElement('div');
        itemsContainer.className = 'custom-dropdown-items';
        menu.appendChild(itemsContainer);

        const graph = (window as any).graph;
        const canvas = graph?.list_of_graphcanvas?.[0];
        if (canvas && canvas.canvas) {
            const canvasRect = canvas.canvas.getBoundingClientRect();
            const lastMouseEvent = this.lastMouseEvent;

            if (lastMouseEvent) {
                let menuX = lastMouseEvent.clientX;
                let menuY = lastMouseEvent.clientY + 5;

                const menuWidth = 280;
                const searchHeight = hasSearch ? 36 : 0;
                const menuHeight = Math.min(300, options.length * 26 + searchHeight + 8);

                if (menuX + menuWidth > window.innerWidth) {
                    menuX = window.innerWidth - menuWidth - 10;
                }
                if (menuY + menuHeight > window.innerHeight) {
                    menuY = lastMouseEvent.clientY - menuHeight - 5;
                }

                menu.style.left = `${menuX}px`;
                menu.style.top = `${menuY}px`;
                menu.style.width = `${menuWidth}px`;
                menu.style.maxHeight = `${menuHeight}px`;
            } else {
                const scale = canvas.ds?.scale || 1;
                const offset = canvas.ds?.offset || [0, 0];
                const screenX = canvasRect.left + (0 + offset[0]) * scale; // Using 0 for node pos as fallback
                const screenY = canvasRect.top + (0 + offset[1] + 100) * scale; // Using 100 for node size as fallback
                menu.style.left = `${screenX}px`;
                menu.style.top = `${screenY + 5}px`;
                menu.style.width = '280px';
                menu.style.maxHeight = '300px';
            }
        }

        const renderItems = (itemsToRender: any[]) => {
            itemsContainer.innerHTML = '';
            itemsToRender.forEach((option) => {
                const item = document.createElement('div');
                item.className = 'custom-dropdown-item';
                item.textContent = this.formatComboValue(option);
                item.setAttribute('data-value', String(option));

                item.addEventListener('click', () => {
                    callback(option);
                    document.body.removeChild(overlay);
                });

                itemsContainer.appendChild(item);
            });
        };

        renderItems(filteredOptions);

        if (searchInput) {
            searchInput.addEventListener('input', () => {
                const query = searchInput.value.toLowerCase().trim();
                if (!query) {
                    filteredOptions = options.slice();
                } else {
                    filteredOptions = options.filter((opt: any) =>
                        String(opt).toLowerCase().includes(query)
                    );
                }
                renderItems(filteredOptions);
                selectedIndex = 0;
                updateSelection();
            });

            searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter') {
                    e.preventDefault();
                    e.stopPropagation();
                    if (e.key === 'ArrowDown') {
                        selectedIndex = Math.min(selectedIndex + 1, filteredOptions.length - 1);
                        updateSelection();
                    } else if (e.key === 'ArrowUp') {
                        selectedIndex = Math.max(selectedIndex - 1, 0);
                        updateSelection();
                    } else if (e.key === 'Enter' && filteredOptions[selectedIndex] !== undefined) {
                        callback(filteredOptions[selectedIndex]);
                        document.body.removeChild(overlay);
                    }
                } else if (e.key === 'Escape') {
                    document.body.removeChild(overlay);
                }
            });
        }

        overlay.appendChild(menu);
        overlay.tabIndex = -1;
        document.body.appendChild(overlay);

        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                document.body.removeChild(overlay);
            }
        });

        let selectedIndex = 0;

        const updateSelection = () => {
            const items = itemsContainer.querySelectorAll('.custom-dropdown-item');
            items.forEach((item, i) => {
                if (i === selectedIndex) {
                    item.classList.add('selected');
                    if (typeof item.scrollIntoView === 'function') {
                        item.scrollIntoView({ block: 'nearest' });
                    }
                } else {
                    item.classList.remove('selected');
                }
            });
        };

        updateSelection();

        overlay.addEventListener('keydown', (e) => {
            if (searchInput && document.activeElement === searchInput) {
                return;
            }
            e.preventDefault();
            e.stopPropagation();

            if (e.key === 'ArrowDown') {
                selectedIndex = (selectedIndex + 1) % filteredOptions.length;
                updateSelection();
            } else if (e.key === 'ArrowUp') {
                selectedIndex = (selectedIndex - 1 + filteredOptions.length) % filteredOptions.length;
                updateSelection();
            } else if (e.key === 'Enter' && filteredOptions[selectedIndex] !== undefined) {
                callback(filteredOptions[selectedIndex]);
                document.body.removeChild(overlay);
            } else if (e.key === 'Escape') {
                document.body.removeChild(overlay);
            }
        });

        if (searchInput) {
            setTimeout(() => searchInput?.focus(), 0);
        } else {
            overlay.focus();
        }
    }

    async showTextEditor(
        initial: string,
        options?: DialogOptions
    ): Promise<string | null> {
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

            textarea.addEventListener('input', updateCounter);
            textarea.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    cancelBtn.click();
                } else if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                    doSave();
                }
            });

            buttons.appendChild(cancelBtn);
            buttons.appendChild(saveBtn);
            footer.appendChild(counter);
            footer.appendChild(buttons);
            dialog.appendChild(footer);
            overlay.appendChild(dialog);
            document.body.appendChild(overlay);

            textarea.focus();
            textarea.select();
        });
    }

    private formatComboValue(value: any): string {
        if (typeof value === 'boolean') {
            return value ? 'true' : 'false';
        }
        return String(value);
    }
}
