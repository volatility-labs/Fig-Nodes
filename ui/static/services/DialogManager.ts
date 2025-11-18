import { ServiceRegistry } from './ServiceRegistry';


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

    constructor(_serviceRegistry: ServiceRegistry) {

    }
    showError(message: string): void {
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
    }

    setLastMouseEvent(event: MouseEvent): void {
        this.lastMouseEvent = event;
    }

    private isValidPosition(position: Position): boolean {
        return position &&
            Number.isFinite(position.x) &&
            Number.isFinite(position.y) &&
            position.x >= 0 &&
            position.y >= 0;
    }

    showPrompt(title: string, defaultValue: string | number, isPassword: boolean, callback: (value: string | null) => void): void {
        if (isPassword) {
            this.showPasswordPrompt(title, String(defaultValue), callback);
        } else {
            this.showQuickValuePrompt(title, defaultValue, false, callback);
        }
    }

    private showPasswordPrompt(title: string, defaultValue: string, callback: (value: string | null) => void): void {
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
                if (!Number.isFinite(n)) return;
                // Preserve decimal values - check if input has decimal point
                // If the string contains a decimal point, preserve it (it's a float)
                // Otherwise, use Math.floor for integers
                const inputStr = input.value.trim();
                const hasDecimal = inputStr.includes('.');
                if (hasDecimal) {
                    // Preserve decimal value
                    callback(String(n));
                } else {
                    // Integer value - use Math.floor to ensure it's an integer
                    callback(String(Math.floor(n)));
                }
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

        // Position dialog near widget/cursor when possible
        const applyAbsolutePosition = (x: number, y: number) => {
            dialog.style.position = 'absolute';
            dialog.style.left = `${x}px`;
            dialog.style.top = `${y}px`;
            overlay.style.background = 'transparent';
            overlay.style.setProperty('pointer-events', 'none');
            dialog.style.setProperty('pointer-events', 'auto');
        };

        if (position && this.isValidPosition(position)) {
            applyAbsolutePosition(position.x, position.y);
        } else if (this.lastMouseEvent) {
            const mouseX = this.lastMouseEvent.clientX;
            const mouseY = this.lastMouseEvent.clientY + 5;
            applyAbsolutePosition(mouseX, mouseY);
        }

        input.focus();
        input.select();
    }

    showCustomDropdown(_paramName: string, options: any[], callback: (value: any) => void, position?: Position): void {
        const overlay = document.createElement('div');
        overlay.className = 'custom-dropdown-overlay';

        const menu = document.createElement('div');
        menu.className = 'custom-dropdown-menu';

        const removeOverlay = () => {
            if (overlay.parentNode) {
                document.body.removeChild(overlay);
            }
        };

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

        const menuWidth = 280;
        const searchHeight = hasSearch ? 36 : 0;
        const menuHeight = Math.min(300, options.length * 26 + searchHeight + 8);

        let menuX: number;
        let menuY: number;

        // Position dropdown using provided widget position or mouse event
        if (position && this.isValidPosition(position)) {
            menuX = position.x;
            menuY = position.y + 25; // Offset below widget
        } else if (this.lastMouseEvent) {
            menuX = this.lastMouseEvent.clientX;
            menuY = this.lastMouseEvent.clientY + 5;
        } else {
            // Center on screen as fallback
            menuX = window.innerWidth / 2 - menuWidth / 2;
            menuY = window.innerHeight / 2 - menuHeight / 2;
        }

        // Keep menu within viewport bounds
        const padding = 10;
        menuX = Math.max(padding, Math.min(menuX, window.innerWidth - menuWidth - padding));
        menuY = Math.max(padding, Math.min(menuY, window.innerHeight - menuHeight - padding));

        menu.style.left = `${menuX}px`;
        menu.style.top = `${menuY}px`;
        menu.style.width = `${menuWidth}px`;
        menu.style.maxHeight = `${menuHeight}px`;

        const renderItems = (itemsToRender: any[]) => {
            itemsContainer.innerHTML = '';
            itemsToRender.forEach((option) => {
                const item = document.createElement('div');
                item.className = 'custom-dropdown-item';
                item.textContent = this.formatComboValue(option);
                item.setAttribute('data-value', String(option));

                item.addEventListener('click', () => {
                    callback(option);
                    removeOverlay();
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
                        removeOverlay();
                    }
                } else if (e.key === 'Escape') {
                    removeOverlay();
                }
            });
        }

        overlay.appendChild(menu);
        overlay.tabIndex = -1;
        document.body.appendChild(overlay);

        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                removeOverlay();
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
                removeOverlay();
            } else if (e.key === 'Escape') {
                removeOverlay();
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
