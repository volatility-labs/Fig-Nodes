import { LGraph, LGraphCanvas, LiteGraph } from '@fig-node/litegraph';
import { TypeColorRegistry } from './TypeColorRegistry';

export interface Theme {
    name: string;
    displayName: string;
    colors: {
        // Canvas colors
        canvasBackground: string;
        canvasGridColor?: string;
        
        // Node colors
        nodeDefaultColor: string;
        nodeDefaultBgColor: string;
        nodeTitleColor: string;
        nodeSelectedTitleColor: string;
        nodeTextColor: string;
        nodeTextHighlightColor: string;
        nodeBoxOutlineColor: string;
        nodeDefaultBoxColor: string;
        
        // Link colors
        linkColor: string;
        eventLinkColor: string;
        connectingLinkColor: string;
        linkTypeNumber: string;
        linkTypeNode: string;
        
        // Connection slot colors
        inputOff: string;
        inputOn: string;
        outputOff: string;
        outputOn: string;
        
        // Widget colors
        widgetBgColor: string;
        widgetOutlineColor: string;
        widgetAdvancedOutlineColor: string;
        widgetTextColor: string;
        widgetSecondaryTextColor: string;
        widgetDisabledTextColor: string;
        
        // UI colors (for CSS)
        uiBackground: string;
        uiBorder: string;
        uiText: string;
        uiTextSecondary: string;
    };
}

export const THEMES: Record<string, Theme> = {
    dark: {
        name: 'dark',
        displayName: 'Dark',
        colors: {
            canvasBackground: '#2a2a2a',
            nodeDefaultColor: '#333',
            nodeDefaultBgColor: '#353535',
            nodeTitleColor: '#999',
            nodeSelectedTitleColor: '#FFF',
            nodeTextColor: '#AAA',
            nodeTextHighlightColor: '#EEE',
            nodeBoxOutlineColor: '#FFF',
            nodeDefaultBoxColor: '#666',
            linkColor: '#9A9',
            eventLinkColor: '#A86',
            connectingLinkColor: '#AFA',
            linkTypeNumber: '#AAA',
            linkTypeNode: '#DCA',
            inputOff: '#778',
            inputOn: '#7F7',
            outputOff: '#778',
            outputOn: '#7F7',
            widgetBgColor: '#222',
            widgetOutlineColor: '#666',
            widgetAdvancedOutlineColor: 'rgba(56, 139, 253, 0.8)',
            widgetTextColor: '#DDD',
            widgetSecondaryTextColor: '#999',
            widgetDisabledTextColor: '#666',
            uiBackground: '#1a1a1a',
            uiBorder: '#2a2a2a',
            uiText: '#ffffff',
            uiTextSecondary: '#aaa',
            canvasGridColor: '#333'
        }
    },
    bloomberg: {
        name: 'bloomberg',
        displayName: 'Bloomberg Terminal',
        colors: {
            canvasBackground: '#161b22',
            nodeDefaultColor: '#1c2128',
            nodeDefaultBgColor: '#22272e',
            nodeTitleColor: '#adbac7',
            nodeSelectedTitleColor: '#cdd9e5',
            nodeTextColor: '#768390',
            nodeTextHighlightColor: '#adbac7',
            nodeBoxOutlineColor: '#373e47',
            nodeDefaultBoxColor: '#373e47',
            linkColor: '#316dca',
            eventLinkColor: '#f85149',
            connectingLinkColor: '#3fb950',
            linkTypeNumber: '#316dca',
            linkTypeNode: '#3fb950',
            inputOff: '#545d68',
            inputOn: '#3fb950',
            outputOff: '#545d68',
            outputOn: '#316dca',
            widgetBgColor: '#1c2128',
            widgetOutlineColor: '#373e47',
            widgetAdvancedOutlineColor: 'rgba(49, 109, 202, 0.8)',
            widgetTextColor: '#adbac7',
            widgetSecondaryTextColor: '#768390',
            widgetDisabledTextColor: '#545d68',
            uiBackground: '#0d1117',
            uiBorder: '#30363d',
            uiText: '#c9d1d9',
            uiTextSecondary: '#768390',
            canvasGridColor: '#30363d'
        }
    },
    light: {
        name: 'light',
        displayName: 'Light',
        colors: {
            canvasBackground: '#f0f0f0',
            nodeDefaultColor: '#ffffff',
            nodeDefaultBgColor: '#ffffff',
            nodeTitleColor: '#333333',
            nodeSelectedTitleColor: '#000000',
            nodeTextColor: '#555555',
            nodeTextHighlightColor: '#222222',
            nodeBoxOutlineColor: '#b0b0b0',
            nodeDefaultBoxColor: '#d0d0d0',
            linkColor: '#0066cc',
            eventLinkColor: '#cc6600',
            connectingLinkColor: '#00aa00',
            linkTypeNumber: '#0066cc',
            linkTypeNode: '#00aa00',
            inputOff: '#999999',
            inputOn: '#00aa00',
            outputOff: '#999999',
            outputOn: '#0066cc',
            widgetBgColor: '#ffffff',
            widgetOutlineColor: '#b0b0b0',
            widgetAdvancedOutlineColor: 'rgba(0, 102, 204, 0.8)',
            widgetTextColor: '#333333',
            widgetSecondaryTextColor: '#666666',
            widgetDisabledTextColor: '#999999',
            uiBackground: '#ffffff',
            uiBorder: '#d0d0d0',
            uiText: '#222222',
            uiTextSecondary: '#666666',
            canvasGridColor: '#d0d0d0'
        }
    },
};

export class ThemeManager {
    private currentTheme: Theme;
    private canvas: LGraphCanvas | null = null;
    private graph: LGraph | null = null;
    private typeColorRegistry: TypeColorRegistry | null = null;
    
    constructor() {
        // Load from localStorage or default to bloomberg
        const saved = localStorage.getItem('fig-node-theme');
        this.currentTheme = THEMES[saved || 'bloomberg'] || THEMES.bloomberg;
    }
    
    /**
     * Set TypeColorRegistry reference for connector theming
     */
    setTypeColorRegistry(registry: TypeColorRegistry): void {
        this.typeColorRegistry = registry;
    }
    
    /**
     * Apply theme to canvas and graph (call during initialization)
     */
    applyTheme(canvas: LGraphCanvas, graph: LGraph) {
        this.canvas = canvas;
        this.graph = graph;
        this._applyThemeColors();
    }
    
    /**
     * Change theme at runtime
     */
    setTheme(themeName: string) {
        const theme = THEMES[themeName];
        if (!theme) {
            console.warn(`Theme "${themeName}" not found`);
            return;
        }
        
        this.currentTheme = theme;
        localStorage.setItem('fig-node-theme', themeName);
        
        if (this.canvas && this.graph) {
            this._applyThemeColors();
            // Trigger redraw
            this.canvas.draw(true, true);
        }
    }
    
    /**
     * Get current theme
     */
    getCurrentTheme(): Theme {
        return this.currentTheme;
    }
    
    /**
     * Get all available themes
     */
    getAvailableThemes(): Theme[] {
        return Object.values(THEMES);
    }
    
    /**
     * Internal method to apply colors
     */
    private _applyThemeColors() {
        if (!this.canvas || !this.graph) return;
        
        const colors = this.currentTheme.colors;
        
        // 1. Update LiteGraph global constants (static)
        LiteGraph.NODE_DEFAULT_COLOR = colors.nodeDefaultColor;
        LiteGraph.NODE_DEFAULT_BGCOLOR = colors.nodeDefaultBgColor;
        LiteGraph.NODE_TITLE_COLOR = colors.nodeTitleColor;
        LiteGraph.NODE_SELECTED_TITLE_COLOR = colors.nodeSelectedTitleColor;
        LiteGraph.NODE_TEXT_COLOR = colors.nodeTextColor;
        LiteGraph.NODE_TEXT_HIGHLIGHT_COLOR = colors.nodeTextHighlightColor;
        LiteGraph.NODE_BOX_OUTLINE_COLOR = colors.nodeBoxOutlineColor;
        LiteGraph.NODE_DEFAULT_BOXCOLOR = colors.nodeDefaultBoxColor;
        LiteGraph.LINK_COLOR = colors.linkColor;
        LiteGraph.EVENT_LINK_COLOR = colors.eventLinkColor;
        LiteGraph.CONNECTING_LINK_COLOR = colors.connectingLinkColor;
        LiteGraph.WIDGET_BGCOLOR = colors.widgetBgColor;
        LiteGraph.WIDGET_OUTLINE_COLOR = colors.widgetOutlineColor;
        LiteGraph.WIDGET_ADVANCED_OUTLINE_COLOR = colors.widgetAdvancedOutlineColor;
        LiteGraph.WIDGET_TEXT_COLOR = colors.widgetTextColor;
        LiteGraph.WIDGET_SECONDARY_TEXT_COLOR = colors.widgetSecondaryTextColor;
        LiteGraph.WIDGET_DISABLED_TEXT_COLOR = colors.widgetDisabledTextColor;
        
        // 2. Update canvas instance properties
        this.canvas.clear_background_color = colors.canvasBackground;
        this.canvas.node_title_color = colors.nodeTitleColor;
        this.canvas.default_link_color = colors.linkColor;
        this.canvas.default_connection_color = {
            input_off: colors.inputOff,
            input_on: colors.inputOn,
            output_off: colors.outputOff,
            output_on: colors.outputOn,
        };
        
        // 3. Update link type colors (basic types)
        // Initialize link_type_colors if it doesn't exist (e.g., in test environments)
        if (!LGraphCanvas.link_type_colors) {
            LGraphCanvas.link_type_colors = {} as any;
        }
        LGraphCanvas.link_type_colors["-1"] = colors.eventLinkColor;
        LGraphCanvas.link_type_colors["number"] = colors.linkTypeNumber;
        LGraphCanvas.link_type_colors["node"] = colors.linkTypeNode;
        LGraphCanvas.DEFAULT_EVENT_LINK_COLOR = colors.eventLinkColor;
        
        // 4. Refresh type-based connector colors if TypeColorRegistry is available
        // This ensures all registered type colors are refreshed when theme changes
        if (this.typeColorRegistry) {
            this.typeColorRegistry.refresh();
        }
        
        // 5. Update CSS variables for UI elements
        document.documentElement.style.setProperty('--theme-bg', colors.uiBackground);
        document.documentElement.style.setProperty('--theme-border', colors.uiBorder);
        document.documentElement.style.setProperty('--theme-text', colors.uiText);
        document.documentElement.style.setProperty('--theme-text-secondary', colors.uiTextSecondary);
        
        // 6. Update canvas element background
        const canvasEl = document.getElementById('litegraph-canvas');
        if (canvasEl) {
            canvasEl.style.background = colors.uiBackground;
        }
        
        // 7. Update body background
        document.body.style.background = colors.uiBackground;
        document.body.style.color = colors.uiText;
        
        // 8. Update footer background
        const footer = document.getElementById('footer');
        if (footer) {
            footer.style.background = colors.uiBackground;
            footer.style.borderTopColor = colors.uiBorder;
        }

        // Disable image-based grid and enable procedural grid
        this.canvas.background_image = null;
        this.canvas.onDrawBackground = (ctx: CanvasRenderingContext2D, visible_area: [number, number, number, number]) => {
            this.drawProceduralGrid(ctx, visible_area);
            return true; // Prevents default background rendering
        };
    }

    private drawProceduralGrid(ctx: CanvasRenderingContext2D, visibleArea: [number, number, number, number]) {
        const [x, y, width, height] = visibleArea;
        const gridSize = 10; // LiteGraph.CANVAS_GRID_SIZE
        const majorGridSize = 100;
        const gridColor = this.currentTheme.colors.canvasGridColor || '#30363d';
        const majorGridColor = this._darkenColor(gridColor, 0.3) || '#545d68'; // Slightly bolder
        
        ctx.save();
        ctx.strokeStyle = gridColor;
        ctx.lineWidth = 1;
        ctx.globalAlpha = 0.15;
        
        // Vertical lines
        for (let i = Math.floor(x / gridSize) * gridSize; i < x + width; i += gridSize) {
            if (i % majorGridSize === 0) {
                ctx.strokeStyle = majorGridColor;
                ctx.globalAlpha = 0.25;
                ctx.lineWidth = 1.5;
            } else {
                ctx.strokeStyle = gridColor;
                ctx.globalAlpha = 0.15;
                ctx.lineWidth = 1;
            }
            ctx.beginPath();
            ctx.moveTo(i, y);
            ctx.lineTo(i, y + height);
            ctx.stroke();
            
            // Reset for next line
            if (i % majorGridSize === 0) {
                ctx.globalAlpha = 0.15;
                ctx.lineWidth = 1;
            }
        }
        
        // Horizontal lines
        for (let i = Math.floor(y / gridSize) * gridSize; i < y + height; i += gridSize) {
            if (i % majorGridSize === 0) {
                ctx.strokeStyle = majorGridColor;
                ctx.globalAlpha = 0.25;
                ctx.lineWidth = 1.5;
            } else {
                ctx.strokeStyle = gridColor;
                ctx.globalAlpha = 0.15;
                ctx.lineWidth = 1;
            }
            ctx.beginPath();
            ctx.moveTo(x, i);
            ctx.lineTo(x + width, i);
            ctx.stroke();
            
            // Reset for next line
            if (i % majorGridSize === 0) {
                ctx.globalAlpha = 0.15;
                ctx.lineWidth = 1;
            }
        }
        
        ctx.restore();
    }

    private _darkenColor(hex: string, amount: number): string {
        if (!hex || !hex.startsWith('#')) return hex;
        const num = parseInt(hex.replace('#', ''), 16);
        const amt = Math.round(2.55 * amount * 100) * -1;  // Negative for darken
        const R = Math.max(0, Math.min(255, (num >> 16) + amt));
        const G = Math.max(0, Math.min(255, (num >> 8 & 0x00FF) + amt));
        const B = Math.max(0, Math.min(255, (num & 0x0000FF) + amt));
        return '#' + (1 << 24 | R << 16 | G << 8 | B).toString(16).slice(1);
    }
}

