/**
 * PixiJSRenderer - GPU-accelerated rendering layer for LiteGraph
 * 
 * This service provides GPU-accelerated rendering using PixiJS while
 * maintaining full compatibility with LiteGraph's logic layer.
 * 
 * Architecture:
 * - LiteGraph handles: node execution, connections, serialization, backend integration
 * - PixiJS handles: visual rendering, GPU acceleration, glassmorphism effects
 * - This service bridges the two layers
 */

import { Application, Graphics, Container, Text, TextStyle, Ticker, Sprite } from 'pixi.js';
import { LGraph, LGraphCanvas, LGraphNode } from '@comfyorg/litegraph';

export interface PixiNodeSprite {
    node: LGraphNode;
    container: Container;
    bg: Graphics;
    titleBar: Graphics;
    titleText: Text;
    glow: Graphics;
    inputConnectors: Graphics[];
    outputConnectors: Graphics[];
}

export interface PixiConnection {
    from: LGraphNode;
    to: LGraphNode;
    graphics: Graphics;
}

export class PixiJSRenderer {
    private app: Application | null = null;
    private canvas: HTMLCanvasElement | null = null;
    private liteGraphCanvas: LGraphCanvas | null = null;
    private liteGraph: LGraph | null = null;
    
    // Rendering state
    private nodeSprites: Map<number, PixiNodeSprite> = new Map();
    private connections: PixiConnection[] = [];
    private viewportX = 0;
    private viewportY = 0;
    private zoom = 1;
    
    // Interaction state
    private isPanning = false;
    private panStart = { x: 0, y: 0 };
    private selectedNodeId: number | null = null;
    
    // Performance tracking
    private fpsCounter: Text | null = null;
    private fpsUpdateInterval = 0;

    /**
     * Initialize PixiJS application and set up rendering
     */
    async initialize(canvasElement: HTMLCanvasElement, liteGraphCanvas: LGraphCanvas, liteGraph: LGraph): Promise<void> {
        this.canvas = canvasElement;
        this.liteGraphCanvas = liteGraphCanvas;
        this.liteGraph = liteGraph;

        // Create PixiJS Application
        this.app = new Application();
        await this.app.init({
            view: canvasElement,
            width: canvasElement.width || window.innerWidth,
            height: canvasElement.height || window.innerHeight,
            backgroundColor: 0x0a0e14,
            antialias: true,
            resolution: window.devicePixelRatio || 1,
            autoDensity: true,
            backgroundAlpha: 1,
        });

        // Set up viewport
        this.app.stage.scale.set(this.zoom);
        this.app.stage.position.set(this.viewportX, this.viewportY);

        // Set up interaction handlers
        this.setupInteractions();

        // Hook into LiteGraph's node lifecycle
        this.setupLiteGraphHooks();

        // Start render loop
        this.startRenderLoop();
    }

    /**
     * Set up interaction handlers for zoom, pan, and node selection
     */
    private setupInteractions(): void {
        if (!this.canvas || !this.app) return;

        // Zoom with mouse wheel
        this.canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            const delta = e.deltaY > 0 ? 0.9 : 1.1;
            this.zoom = Math.max(0.5, Math.min(3, this.zoom * delta));
            if (this.app) {
                this.app.stage.scale.set(this.zoom);
            }
        });

        // Pan with middle mouse or Ctrl+drag
        this.canvas.addEventListener('mousedown', (e) => {
            if (e.button === 1 || (e.button === 0 && e.ctrlKey)) {
                this.isPanning = true;
                this.panStart.x = e.clientX - this.viewportX;
                this.panStart.y = e.clientY - this.viewportY;
                if (this.canvas) {
                    this.canvas.style.cursor = 'grabbing';
                }
            }
        });

        this.canvas.addEventListener('mousemove', (e) => {
            if (this.isPanning) {
                this.viewportX = e.clientX - this.panStart.x;
                this.viewportY = e.clientY - this.panStart.y;
                if (this.app) {
                    this.app.stage.position.set(this.viewportX, this.viewportY);
                }
            }
        });

        this.canvas.addEventListener('mouseup', () => {
            this.isPanning = false;
            if (this.canvas) {
                this.canvas.style.cursor = 'default';
            }
        });

        // Forward clicks to LiteGraph for node selection
        this.canvas.addEventListener('click', (e) => {
            if (!this.isPanning && e.button === 0 && !e.ctrlKey) {
                // Convert PixiJS coordinates to LiteGraph coordinates
                const rect = this.canvas.getBoundingClientRect();
                const x = (e.clientX - rect.left - this.viewportX) / this.zoom;
                const y = (e.clientY - rect.top - this.viewportY) / this.zoom;
                
                // Find node at this position and forward to LiteGraph
                this.findAndSelectNode(x, y);
            }
        });
    }

    /**
     * Hook into LiteGraph's node lifecycle events
     */
    private setupLiteGraphHooks(): void {
        if (!this.liteGraph || !this.liteGraphCanvas) return;

        // Listen for graph changes by polling (since LiteGraph doesn't always emit events)
        // In a full implementation, you'd want to patch LiteGraph's methods
        
        // Initial sync: add all existing nodes
        if (this.liteGraph._nodes) {
            this.liteGraph._nodes.forEach((node: LGraphNode) => {
                this.addNodeSprite(node);
            });
        }

        // Update node positions and connections on every frame
        if (this.app) {
            this.app.ticker.add(() => {
                this.syncWithLiteGraph();
            });
        }
    }

    /**
     * Sync PixiJS rendering state with LiteGraph state
     */
    private syncWithLiteGraph(): void {
        if (!this.liteGraph) return;

        // Add any new nodes
        if (this.liteGraph._nodes) {
            this.liteGraph._nodes.forEach((node: LGraphNode) => {
                if (!this.nodeSprites.has(node.id)) {
                    this.addNodeSprite(node);
                }
            });
        }

        // Remove deleted nodes
        const currentNodeIds = new Set(
            this.liteGraph._nodes?.map((n: LGraphNode) => n.id) || []
        );
        this.nodeSprites.forEach((sprite, id) => {
            if (!currentNodeIds.has(id)) {
                this.removeNodeSprite(sprite.node);
            }
        });

        // Update positions
        this.updateNodePositions();
        
        // Update connections
        this.updateConnections();
    }

    /**
     * Create a glassmorphic node sprite from a LiteGraph node
     */
    private createNodeSprite(node: LGraphNode): PixiNodeSprite {
        const container = new Container();
        container.x = node.pos[0];
        container.y = node.pos[1];
        container.interactive = true;
        container.buttonMode = true;

        const width = node.size[0] || 200;
        const height = node.size[1] || 100;
        const color = this.getNodeColor(node);

        // Background with glassmorphism
        const bg = new Graphics();
        bg.roundRect(0, 0, width, height, 12);
        bg.fill({ color: 0x1e2329, alpha: 0.7 });
        bg.stroke({ color: 0xffffff, width: 1, alpha: 0.1 });

        // Title bar with gradient
        const titleBar = new Graphics();
        titleBar.roundRect(0, 0, width, 40, 12);
        titleBar.fill({ color: color, alpha: 0.2 });
        titleBar.stroke({ color: 0xffffff, width: 1, alpha: 0.1 });

        // Title text
        const titleText = new Text({
            text: node.title || 'Node',
            style: new TextStyle({
                fontFamily: 'Segoe UI',
                fontSize: 14,
                fontWeight: '600',
                fill: 0xe3f2fd,
            }),
        });
        titleText.x = 12;
        titleText.y = 12;

        // Glow effect
        const glow = new Graphics();
        glow.roundRect(-2, -2, width + 4, height + 4, 14);
        glow.stroke({ color: color, width: 2, alpha: 0.3 });

        container.addChild(bg);
        container.addChild(titleBar);
        container.addChild(titleText);
        container.addChild(glow);

        // Input/output connectors
        const inputConnectors: Graphics[] = [];
        const outputConnectors: Graphics[] = [];

        if (node.inputs) {
            node.inputs.forEach((input, index) => {
                const connector = new Graphics();
                const y = 40 + (index + 1) * 20;
                connector.circle(0, y, 6);
                connector.fill({ color: color, alpha: 0.6 });
                connector.stroke({ color: color, width: 2, alpha: 0.8 });
                connector.x = 0;
                connector.y = y;
                container.addChild(connector);
                inputConnectors.push(connector);
            });
        }

        if (node.outputs) {
            node.outputs.forEach((output, index) => {
                const connector = new Graphics();
                const y = 40 + (index + 1) * 20;
                connector.circle(0, y, 6);
                connector.fill({ color: color, alpha: 0.6 });
                connector.stroke({ color: color, width: 2, alpha: 0.8 });
                connector.x = width;
                connector.y = y;
                container.addChild(connector);
                outputConnectors.push(connector);
            });
        }

        // Interaction handlers
        let dragging = false;
        let dragStart = { x: 0, y: 0 };

        container.on('pointerdown', (e) => {
            dragging = true;
            dragStart.x = e.global.x - container.x;
            dragStart.y = e.global.y - container.y;
            container.zIndex = 1000;
            this.selectedNodeId = node.id;
            this.updateSelection();
        });

        container.on('pointermove', (e) => {
            if (dragging) {
                container.x = e.global.x - dragStart.x;
                container.y = e.global.y - dragStart.y;
                // Update LiteGraph node position
                node.pos[0] = container.x;
                node.pos[1] = container.y;
            }
        });

        container.on('pointerup', () => {
            dragging = false;
        });

        container.on('pointerenter', () => {
            glow.clear();
            glow.roundRect(-2, -2, width + 4, height + 4, 14);
            glow.stroke({ color: color, width: 3, alpha: 0.6 });
        });

        container.on('pointerleave', () => {
            if (this.selectedNodeId !== node.id) {
                glow.clear();
                glow.roundRect(-2, -2, width + 4, height + 4, 14);
                glow.stroke({ color: color, width: 2, alpha: 0.3 });
            }
        });

        return {
            node,
            container,
            bg,
            titleBar,
            titleText,
            glow,
            inputConnectors,
            outputConnectors,
        };
    }

    /**
     * Get color for a node based on its type/category
     */
    private getNodeColor(node: LGraphNode): number {
        // You can customize this based on node category or type
        const colors: Record<string, number> = {
            'market': 0x42a5f5,
            'io': 0x4caf50,
            'llm': 0xff9800,
            'core': 0x9c27b0,
            'default': 0x64b5f6,
        };

        const category = (node as any).category || 'default';
        return colors[category] || colors.default;
    }

    /**
     * Add a node sprite to the PixiJS stage
     */
    private addNodeSprite(node: LGraphNode): void {
        if (!this.app) return;

        const sprite = this.createNodeSprite(node);
        this.nodeSprites.set(node.id, sprite);
        this.app.stage.addChild(sprite.container);
    }

    /**
     * Remove a node sprite from the PixiJS stage
     */
    private removeNodeSprite(node: LGraphNode): void {
        if (!this.app) return;

        const sprite = this.nodeSprites.get(node.id);
        if (sprite) {
            this.app.stage.removeChild(sprite.container);
            this.nodeSprites.delete(node.id);
        }
    }

    /**
     * Update node positions from LiteGraph
     */
    private updateNodePositions(): void {
        this.nodeSprites.forEach((sprite) => {
            sprite.container.x = sprite.node.pos[0];
            sprite.container.y = sprite.node.pos[1];
        });
    }

    /**
     * Update connection graphics
     */
    private updateConnections(): void {
        if (!this.liteGraph || !this.app) return;

        // Clear existing connections
        this.connections.forEach((conn) => {
            this.app?.stage.removeChild(conn.graphics);
        });
        this.connections = [];

        // Recreate connections from LiteGraph
        if (this.liteGraph.links) {
            this.liteGraph.links.forEach((link: any) => {
                const fromNode = this.liteGraph?.getNodeById(link.origin_id);
                const toNode = this.liteGraph?.getNodeById(link.target_id);

                if (fromNode && toNode) {
                    const fromSprite = this.nodeSprites.get(fromNode.id);
                    const toSprite = this.nodeSprites.get(toNode.id);

                    if (fromSprite && toSprite) {
                        const connection = this.createConnection(fromSprite, toSprite);
                        this.connections.push(connection);
                        this.app?.stage.addChildAt(connection.graphics, 0);
                    }
                }
            });
        }
    }

    /**
     * Create a connection graphics object with glow effects
     */
    private createConnection(from: PixiNodeSprite, to: PixiNodeSprite): PixiConnection {
        const graphics = new Graphics();
        const fromNode = from.node;
        const toNode = to.node;

        const updateConnection = () => {
            graphics.clear();

            const x1 = fromNode.pos[0] + (fromNode.size[0] || 200);
            const y1 = fromNode.pos[1] + 60; // Middle of node
            const x2 = toNode.pos[0];
            const y2 = toNode.pos[1] + 60;

            // Bezier curve control points
            const cp1x = x1 + 50;
            const cp1y = y1;
            const cp2x = x2 - 50;
            const cp2y = y2;

            // Glow effect
            graphics.moveTo(x1, y1);
            graphics.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, x2, y2);
            graphics.stroke({ color: 0x42a5f5, width: 4, alpha: 0.3 });

            // Main line
            graphics.moveTo(x1, y1);
            graphics.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, x2, y2);
            graphics.stroke({ color: 0x64b5f6, width: 2, alpha: 0.8 });
        };

        updateConnection();

        // Animate glow
        let time = 0;
        if (this.app) {
            this.app.ticker.add(() => {
                time += 0.02;
                graphics.clear();

                const x1 = fromNode.pos[0] + (fromNode.size[0] || 200);
                const y1 = fromNode.pos[1] + 60;
                const x2 = toNode.pos[0];
                const y2 = toNode.pos[1] + 60;

                const cp1x = x1 + 50;
                const cp1y = y1;
                const cp2x = x2 - 50;
                const cp2y = y2;

                const glowAlpha = 0.2 + Math.sin(time) * 0.2;
                graphics.moveTo(x1, y1);
                graphics.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, x2, y2);
                graphics.stroke({ color: 0x42a5f5, width: 6, alpha: glowAlpha });

                graphics.moveTo(x1, y1);
                graphics.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, x2, y2);
                graphics.stroke({ color: 0x64b5f6, width: 2, alpha: 0.9 });
            });
        }

        return { from: fromNode, to: toNode, graphics };
    }

    /**
     * Find node at coordinates and select it
     */
    private findAndSelectNode(x: number, y: number): void {
        // Find node at position and forward selection to LiteGraph
        for (const [id, sprite] of this.nodeSprites.entries()) {
            const nodeX = sprite.node.pos[0];
            const nodeY = sprite.node.pos[1];
            const nodeW = sprite.node.size[0] || 200;
            const nodeH = sprite.node.size[1] || 100;

            if (x >= nodeX && x <= nodeX + nodeW && y >= nodeY && y <= nodeY + nodeH) {
                this.selectedNodeId = id;
                this.updateSelection();
                // Forward to LiteGraph
                if (this.liteGraphCanvas) {
                    this.liteGraphCanvas.selectNode(sprite.node);
                }
                break;
            }
        }
    }

    /**
     * Update visual selection state
     */
    private updateSelection(): void {
        this.nodeSprites.forEach((sprite, id) => {
            const isSelected = id === this.selectedNodeId;
            const color = this.getNodeColor(sprite.node);
            
            sprite.glow.clear();
            sprite.glow.roundRect(-2, -2, (sprite.node.size[0] || 200) + 4, (sprite.node.size[1] || 100) + 4, 14);
            
            if (isSelected) {
                sprite.glow.stroke({ color: color, width: 4, alpha: 0.8 });
            } else {
                sprite.glow.stroke({ color: color, width: 2, alpha: 0.3 });
            }
        });
    }

    /**
     * Start the render loop
     */
    private startRenderLoop(): void {
        if (!this.app) return;

        // FPS counter (optional, can be removed)
        this.fpsCounter = new Text({
            text: 'FPS: --',
            style: new TextStyle({
                fontFamily: 'Consolas',
                fontSize: 12,
                fill: 0xffffff,
            }),
        });
        this.fpsCounter.x = 10;
        this.fpsCounter.y = 10;
        this.app.stage.addChild(this.fpsCounter);

        this.app.ticker.add(() => {
            this.fpsUpdateInterval++;
            if (this.fpsUpdateInterval % 60 === 0 && this.fpsCounter) {
                this.fpsCounter.text = `FPS: ${Math.round(this.app!.ticker.FPS)}`;
            }
        });
    }

    /**
     * Clean up and destroy the renderer
     */
    destroy(): void {
        if (this.app) {
            this.app.destroy(true);
            this.app = null;
        }
        this.nodeSprites.clear();
        this.connections = [];
    }

    /**
     * Resize the canvas
     */
    resize(width: number, height: number): void {
        if (this.app) {
            this.app.renderer.resize(width, height);
        }
    }
}

