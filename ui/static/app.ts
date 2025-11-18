import './style.css';
import { EditorInitializer } from './services/EditorInitializer';

async function createEditor(container: HTMLElement) {
    const editorInitializer = new EditorInitializer();
    return await editorInitializer.createEditor(container);
}

document.addEventListener('DOMContentLoaded', () => {
    const container = document.querySelector('.app-container') as HTMLElement;
    if (container) createEditor(container);
    else console.error('Canvas container not found');
});