import './setup/patchLiteGraph';
import { EditorInitializer } from './services/EditorInitializer';

async function createEditor(container: HTMLElement) {
    const editorInitializer = new EditorInitializer();
    return await editorInitializer.createEditor(container);
}

function setupExpandToggle() {
    const expandToggle = document.getElementById('expand-toggle');
    const appContainer = document.querySelector('.app-container') as HTMLElement;
    
    if (!expandToggle) {
        console.error('Expand toggle button not found');
        return;
    }
    
    if (!appContainer) {
        console.error('App container not found');
        return;
    }
    
    console.log('Expand toggle button found and initialized');
    
    let isExpanded = false;
    
    expandToggle.addEventListener('click', () => {
        isExpanded = !isExpanded;
        
        if (isExpanded) {
            appContainer.classList.add('expanded');
            expandToggle.textContent = 'Exit Fullscreen';
            expandToggle.title = 'Minimize Canvas (ESC)';
        } else {
            appContainer.classList.remove('expanded');
            expandToggle.textContent = 'Fullscreen';
            expandToggle.title = 'Expand Canvas';
        }
        
        // Trigger canvas resize if needed
        const canvas = document.getElementById('litegraph-canvas') as HTMLCanvasElement;
        if (canvas) {
            // Ensure canvas is focusable and receives focus in fullscreen mode
            if (isExpanded) {
                canvas.setAttribute('tabindex', '0');
                // Focus the canvas after a short delay to ensure DOM is updated
                setTimeout(() => {
                    canvas.focus();
                }, 50);
            }
            // Force canvas to recalculate size
            setTimeout(() => {
                const event = new Event('resize');
                window.dispatchEvent(event);
            }, 100);
        }
    });
    
    // Handle ESC key to exit expanded mode
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && isExpanded) {
            isExpanded = false;
            appContainer.classList.remove('expanded');
            expandToggle.textContent = 'Fullscreen';
            expandToggle.title = 'Expand Canvas';
            
            // Trigger canvas resize
            setTimeout(() => {
                const event = new Event('resize');
                window.dispatchEvent(event);
            }, 100);
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const container = document.querySelector('.app-container') as HTMLElement;
    if (container) {
        createEditor(container);
        setupExpandToggle();
    } else {
        console.error('Canvas container not found');
    }
});