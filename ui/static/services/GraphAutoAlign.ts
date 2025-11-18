import { LGraph, LGraphNode } from '@comfyorg/litegraph';

export class GraphAutoAlign {
    private static readonly LEVEL_SPACING = 250; // Space between topological levels (horizontal)
    private static readonly NODE_SPACING = 120; // Space between nodes in same level (vertical)
    private static readonly MIN_NODE_SPACING = 150; // Minimum spacing to prevent overlap (vertical)
    private static readonly START_X = 100; // Starting X position
    private static readonly START_Y = 100; // Starting Y position
    private static readonly COMPONENT_SPACING = 400; // Vertical spacing between disconnected components

    /**
     * Auto-aligns all nodes in the graph based on flow topology
     */
    static alignGraph(graph: LGraph): void {
        const nodes = graph._nodes || [];
        if (nodes.length === 0) return;

        // Ensure all nodes have unique IDs
        nodes.forEach((node: LGraphNode, index: number) => {
            if (!(node as any).id) {
                (node as any).id = `node_${index}_${Date.now()}`;
            }
        });

        // Get serialized graph data to access links and node IDs
        const serialized = graph.asSerialisable({ sortNodes: true }) as any;
        const links = serialized.links || [];
        const serializedNodes = serialized.nodes || [];

        // Build node ID to node map
        const nodeMap = new Map<number, LGraphNode>();
        
        serializedNodes.forEach((serializedNode: any) => {
            const nodeId = serializedNode.id;
            const node = nodes.find((n: any) => (n as any).id === nodeId) ||
                        nodes.find((n: any) => 
                            n.pos &&
                            Math.abs(n.pos[0] - serializedNode.pos[0]) < 0.1 &&
                            Math.abs(n.pos[1] - serializedNode.pos[1]) < 0.1 &&
                            n.size &&
                            n.size[0] === serializedNode.size[0] &&
                            n.size[1] === serializedNode.size[1]
                        );
            if (node) {
                nodeMap.set(nodeId, node);
            }
        });

        // Build dependency graph
        const inEdges = new Map<number, number[]>();
        const outEdges = new Map<number, number[]>();

        // Initialize all nodes
        nodeMap.forEach((_, nodeId) => {
            inEdges.set(nodeId, []);
            outEdges.set(nodeId, []);
        });

        // Process links to build edges
        links.forEach((link: any) => {
            const fromId = link.origin_id;
            const toId = link.target_id;
            if (inEdges.has(toId) && outEdges.has(fromId)) {
                inEdges.get(toId)!.push(fromId);
                outEdges.get(fromId)!.push(toId);
            }
        });

        // Detect disconnected components
        const components = this.detectComponents(nodeMap, inEdges, outEdges);

        // Topological sort to assign levels for each component
        const nodeLevels = new Map<number, number>();
        components.forEach((componentNodes, componentIndex) => {
            const componentLevels = this.topologicalLevels(componentNodes, inEdges, outEdges);
            componentLevels.forEach((level, nodeId) => {
                nodeLevels.set(nodeId, level);
            });
        });

        // Position nodes with component awareness
        this.positionNodes(nodeLevels, nodeMap, components);

        // Redraw canvas
        const canvas = graph.list_of_graphcanvas?.[0];
        if (canvas) {
            canvas.draw(true, true);
        }
    }

    /**
     * Detects disconnected components in the graph
     */
    private static detectComponents(
        nodeMap: Map<number, LGraphNode>,
        inEdges: Map<number, number[]>,
        outEdges: Map<number, number[]>
    ): Map<number, Set<number>> {
        const visited = new Set<number>();
        const components = new Map<number, Set<number>>();
        let componentIndex = 0;

        const dfs = (nodeId: number, component: Set<number>) => {
            if (visited.has(nodeId)) return;
            visited.add(nodeId);
            component.add(nodeId);

            // Visit all neighbors (both incoming and outgoing)
            const neighbors = [
                ...(inEdges.get(nodeId) || []),
                ...(outEdges.get(nodeId) || [])
            ];
            
            neighbors.forEach(neighborId => {
                if (!visited.has(neighborId)) {
                    dfs(neighborId, component);
                }
            });
        };

        nodeMap.forEach((_, nodeId) => {
            if (!visited.has(nodeId)) {
                const component = new Set<number>();
                dfs(nodeId, component);
                components.set(componentIndex++, component);
            }
        });

        return components;
    }

    private static topologicalLevels(
        componentNodes: Set<number>,
        inEdges: Map<number, number[]>,
        outEdges: Map<number, number[]>
    ): Map<number, number> {
        const nodeLevels = new Map<number, number>();
        const queue: Array<{ id: number; level: number }> = [];
        const inDegree = new Map<number, number>();

        // Calculate in-degree for each node in component
        componentNodes.forEach((nodeId) => {
            const degree = inEdges.get(nodeId)?.filter(id => componentNodes.has(id)).length || 0;
            inDegree.set(nodeId, degree);
            if (degree === 0) {
                queue.push({ id: nodeId, level: 0 });
            }
        });

        // Process nodes level by level using BFS
        while (queue.length > 0) {
            const { id, level } = queue.shift()!;
            if (nodeLevels.has(id)) continue;

            nodeLevels.set(id, level);

            // Process outgoing edges (only within component)
            const neighbors = (outEdges.get(id) || []).filter(nid => componentNodes.has(nid));
            neighbors.forEach(neighborId => {
                const currentDegree = inDegree.get(neighborId) || 0;
                inDegree.set(neighborId, currentDegree - 1);

                if (currentDegree - 1 === 0 && !nodeLevels.has(neighborId)) {
                    queue.push({ id: neighborId, level: level + 1 });
                }
            });
        }

        // Handle disconnected nodes within component (assign to level 0)
        componentNodes.forEach((nodeId) => {
            if (!nodeLevels.has(nodeId)) {
                nodeLevels.set(nodeId, 0);
            }
        });

        // After processing, detect cycles (unprocessed nodes with inDegree > 0)
        const processedCount = nodeLevels.size;
        if (processedCount < componentNodes.size) {
            console.warn(`Cycle detected in component: ${componentNodes.size - processedCount} nodes in cycle(s). Grouping at max level + 1.`);
            let maxLevel = Math.max(...Array.from(nodeLevels.values()), 0);
            componentNodes.forEach((nodeId) => {
                if (!nodeLevels.has(nodeId)) {
                    nodeLevels.set(nodeId, maxLevel + 1);
                }
            });
        }
        return nodeLevels;
    }

    private static positionNodes(
        nodeLevels: Map<number, number>,
        nodeMap: Map<number, LGraphNode>,
        components: Map<number, Set<number>>
    ): void {
        // Group nodes by component and level
        const componentLevels = new Map<number, Map<number, LGraphNode[]>>();
        
        components.forEach((componentNodes, componentIndex) => {
            const levels = new Map<number, LGraphNode[]>();
            componentNodes.forEach((nodeId) => {
                const level = nodeLevels.get(nodeId) ?? 0;
                const node = nodeMap.get(nodeId);
                if (node) {
                    if (!levels.has(level)) {
                        levels.set(level, []);
                    }
                    levels.get(level)!.push(node);
                }
            });
            componentLevels.set(componentIndex, levels);
        });

        // Calculate component bounds for layout
        const componentBounds = new Map<number, { width: number; height: number; maxLevel: number }>();
        componentLevels.forEach((levels, componentIndex) => {
            const sortedLevels = Array.from(levels.keys()).sort((a, b) => a - b);
            const maxLevel = sortedLevels.length > 0 ? Math.max(...sortedLevels) : 0;
            
            // Calculate total width (horizontal span)
            let totalWidth = 0;
            sortedLevels.forEach((level, i) => {
                const levelNodes = levels.get(level) || [];
                const levelWidth = Math.max(...levelNodes.map(n => n.size?.[0] ?? 200), 200);
                if (i > 0) totalWidth += this.LEVEL_SPACING;
                totalWidth += levelWidth;
            });
            
            // Calculate max height across all levels (vertical span per level, take max)
            let maxHeight = 0;
            levels.forEach((levelNodes) => {
                let levelHeight = 0;
                levelNodes.forEach((node, i) => {
                    const h = node.size?.[1] ?? 100;
                    if (i > 0) levelHeight += this.NODE_SPACING;
                    levelHeight += h;
                });
                maxHeight = Math.max(maxHeight, levelHeight);
            });
            
            componentBounds.set(componentIndex, { width: totalWidth, height: maxHeight, maxLevel });
        });

        // Position components vertically (disconnected components top to bottom)
        let currentComponentY = this.START_Y;
        const componentYOffsets = new Map<number, number>();
        
        // Sort components by size (largest first) for better layout
        const sortedComponents = Array.from(components.keys()).sort((a, b) => {
            const boundsA = componentBounds.get(a)!;
            const boundsB = componentBounds.get(b)!;
            // Sort by number of nodes (larger components first)
            return components.get(b)!.size - components.get(a)!.size;
        });

        sortedComponents.forEach((componentIndex) => {
            componentYOffsets.set(componentIndex, currentComponentY);
            const bounds = componentBounds.get(componentIndex)!;
            // Move to next component position with spacing
            currentComponentY += bounds.height + this.COMPONENT_SPACING;
        });

        // Position nodes within each component
        componentLevels.forEach((levels, componentIndex) => {
            const componentYOffset = componentYOffsets.get(componentIndex) ?? this.START_Y;
            const sortedLevels = Array.from(levels.keys()).sort((a, b) => a - b);
            
            let currentX = this.START_X;

            sortedLevels.forEach((level) => {
                let levelNodes = levels.get(level) || [];
                
                // Sort within level by original Y position for consistency
                levelNodes = levelNodes.sort((a, b) => (a.pos?.[1] ?? 0) - (b.pos?.[1] ?? 0));
                
                // Level X is currentX
                const levelX = currentX;
                
                // Position nodes vertically with spacing
                let currentY = componentYOffset;
                let lastNodeBottom = componentYOffset;
                let maxWidthInLevel = 0;

                levelNodes.forEach((node, nodeIndex) => {
                    const nodeWidth = node.size?.[0] ?? 200;
                    const nodeHeight = node.size?.[1] ?? 100;

                    if (nodeIndex > 0) {
                        currentY = lastNodeBottom + this.NODE_SPACING;
                        currentY = Math.max(currentY, lastNodeBottom + this.MIN_NODE_SPACING);
                    }

                    node.pos = [levelX, currentY];
                    node.setDirtyCanvas(true, true);
                    
                    lastNodeBottom = currentY + nodeHeight;
                    maxWidthInLevel = Math.max(maxWidthInLevel, nodeWidth);
                });
                
                // Update currentX for next level
                currentX = levelX + maxWidthInLevel + this.LEVEL_SPACING;
            });
        });
    }
}
