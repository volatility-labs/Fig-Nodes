import { LGraph, LGraphNode } from '@fig-node/litegraph';

/**
 * Graph auto-alignment using a layered DAG layout algorithm (Sugiyama-style).
 * 
 * Algorithm phases:
 * 1. Detect connected components
 * 2. Assign levels using longest-path algorithm
 * 3. Minimize edge crossings using barycenter heuristic
 * 4. Position nodes with proper spacing
 */
export class GraphAutoAlign {
    private static readonly LEVEL_SPACING = 280; // Horizontal space between levels
    private static readonly NODE_SPACING = 100; // Vertical space between nodes in same level
    private static readonly START_X = 100;
    private static readonly START_Y = 100;
    private static readonly COMPONENT_SPACING = 300; // Vertical spacing between disconnected components

    /**
     * Auto-aligns all nodes in the graph based on flow topology
     */
    static alignGraph(graph: LGraph): void {
        const nodes = graph._nodes || [];
        if (nodes.length === 0) return;

        // Build adjacency data directly from graph (no serialization needed)
        const { nodeIds, inEdges, outEdges } = this.buildAdjacencyFromGraph(graph);
        
        if (nodeIds.size === 0) return;

        // Phase 1: Detect connected components
        const components = this.detectComponents(nodeIds, inEdges, outEdges);

        // Process each component
        let componentYOffset = this.START_Y;
        
        // Sort components by number of root nodes (simpler graphs first for better stacking)
        const sortedComponentIds = Array.from(components.keys()).sort((a, b) => {
            const rootsA = this.countRoots(components.get(a)!, inEdges);
            const rootsB = this.countRoots(components.get(b)!, inEdges);
            return rootsA - rootsB;
        });

        for (const componentId of sortedComponentIds) {
            const componentNodeIds = components.get(componentId)!;
            
            // Phase 2: Assign levels using longest-path
            const nodeLevels = this.assignLevelsLongestPath(componentNodeIds, inEdges, outEdges);
            
            // Phase 3: Minimize crossings
            const nodeOrders = this.minimizeCrossings(componentNodeIds, nodeLevels, inEdges, outEdges);
            
            // Phase 4: Position nodes
            const componentHeight = this.positionComponentNodes(
                graph,
                componentNodeIds,
                nodeLevels,
                nodeOrders,
                componentYOffset
            );
            
            componentYOffset += componentHeight + this.COMPONENT_SPACING;
        }

        // Redraw canvas
        const canvas = graph.list_of_graphcanvas?.[0];
        if (canvas) {
            canvas.draw(true, true);
        }
    }

    /**
     * Build adjacency lists directly from graph without serialization
     */
    private static buildAdjacencyFromGraph(graph: LGraph): {
        nodeIds: Set<number>;
        inEdges: Map<number, number[]>;
        outEdges: Map<number, number[]>;
    } {
        const nodeIds = new Set<number>();
        const inEdges = new Map<number, number[]>();
        const outEdges = new Map<number, number[]>();

        // Collect all node IDs
        for (const node of graph._nodes) {
            const nodeId = node.id as number;
            nodeIds.add(nodeId);
            inEdges.set(nodeId, []);
            outEdges.set(nodeId, []);
        }

        // Build edges from links
        const linksArray = Array.from(graph._links.values());
        for (const link of linksArray) {
            const fromId = link.origin_id as number;
            const toId = link.target_id as number;
            
            // Only process valid internal links (not subgraph IO)
            if (nodeIds.has(fromId) && nodeIds.has(toId)) {
                // Avoid duplicates
                const currentIn = inEdges.get(toId)!;
                if (!currentIn.includes(fromId)) {
                    currentIn.push(fromId);
                }
                
                const currentOut = outEdges.get(fromId)!;
                if (!currentOut.includes(toId)) {
                    currentOut.push(toId);
                }
            }
        }

        return { nodeIds, inEdges, outEdges };
    }

    /**
     * Detect disconnected components using DFS
     */
    private static detectComponents(
        nodeIds: Set<number>,
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

            // Visit all neighbors (undirected for component detection)
            const neighbors = [
                ...(inEdges.get(nodeId) || []),
                ...(outEdges.get(nodeId) || [])
            ];
            
            for (const neighborId of neighbors) {
                if (!visited.has(neighborId) && nodeIds.has(neighborId)) {
                    dfs(neighborId, component);
                }
            }
        };

        for (const nodeId of nodeIds) {
            if (!visited.has(nodeId)) {
                const component = new Set<number>();
                dfs(nodeId, component);
                components.set(componentIndex++, component);
            }
        }

        return components;
    }

    /**
     * Count root nodes (nodes with no incoming edges within component)
     */
    private static countRoots(componentNodes: Set<number>, inEdges: Map<number, number[]>): number {
        let count = 0;
        for (const nodeId of componentNodes) {
            const incomingFromComponent = (inEdges.get(nodeId) || [])
                .filter(id => componentNodes.has(id));
            if (incomingFromComponent.length === 0) {
                count++;
            }
        }
        return count;
    }

    /**
     * Assign levels using longest-path algorithm.
     * Each node is placed at the level equal to (max level of predecessors) + 1.
     * This ensures proper spacing in the DAG.
     */
    private static assignLevelsLongestPath(
        componentNodes: Set<number>,
        inEdges: Map<number, number[]>,
        outEdges: Map<number, number[]>
    ): Map<number, number> {
        const nodeLevels = new Map<number, number>();
        const inDegree = new Map<number, number>();
        const queue: number[] = [];

        // Calculate in-degree for each node (only counting edges within component)
        for (const nodeId of componentNodes) {
            const incomingFromComponent = (inEdges.get(nodeId) || [])
                .filter(id => componentNodes.has(id));
            inDegree.set(nodeId, incomingFromComponent.length);
            
            if (incomingFromComponent.length === 0) {
                queue.push(nodeId);
                nodeLevels.set(nodeId, 0);
            }
        }

        // Process in topological order, assigning levels based on max predecessor level
        while (queue.length > 0) {
            const nodeId = queue.shift()!;
            const currentLevel = nodeLevels.get(nodeId)!;

            // Process all outgoing edges within component
            const neighbors = (outEdges.get(nodeId) || [])
                .filter(id => componentNodes.has(id));
            
            for (const neighborId of neighbors) {
                // Update neighbor level to be at least current + 1
                const existingLevel = nodeLevels.get(neighborId);
                const newLevel = currentLevel + 1;
                
                if (existingLevel === undefined || newLevel > existingLevel) {
                    nodeLevels.set(neighborId, newLevel);
                }

                // Decrease in-degree
                const deg = inDegree.get(neighborId)! - 1;
                inDegree.set(neighborId, deg);

                if (deg === 0) {
                    queue.push(neighborId);
                }
            }
        }

        // Handle cycles: nodes not yet assigned get max level + 1
        const assignedLevels = Array.from(nodeLevels.values());
        const maxLevel = assignedLevels.length > 0 ? Math.max.apply(null, assignedLevels) : 0;
        
        for (const nodeId of componentNodes) {
            if (!nodeLevels.has(nodeId)) {
                nodeLevels.set(nodeId, maxLevel + 1);
            }
        }

        return nodeLevels;
    }

    /**
     * Minimize edge crossings using barycenter heuristic.
     * For each level, order nodes by the average position of their connected neighbors.
     */
    private static minimizeCrossings(
        componentNodes: Set<number>,
        nodeLevels: Map<number, number>,
        inEdges: Map<number, number[]>,
        outEdges: Map<number, number[]>
    ): Map<number, number> {
        // Group nodes by level
        const levels = new Map<number, number[]>();
        for (const nodeId of componentNodes) {
            const level = nodeLevels.get(nodeId) ?? 0;
            if (!levels.has(level)) {
                levels.set(level, []);
            }
            levels.get(level)!.push(nodeId);
        }

        const sortedLevelKeys = Array.from(levels.keys()).sort((a, b) => a - b);
        const nodeOrders = new Map<number, number>();

        // Initialize first level order (by node ID for consistency)
        const firstLevel = levels.get(sortedLevelKeys[0] ?? 0) || [];
        firstLevel.sort((a, b) => a - b);
        firstLevel.forEach((nodeId, idx) => nodeOrders.set(nodeId, idx));

        // Iterate multiple passes to improve ordering
        const NUM_PASSES = 4;
        for (let pass = 0; pass < NUM_PASSES; pass++) {
            // Forward sweep (level 0 to max)
            for (let i = 1; i < sortedLevelKeys.length; i++) {
                const levelKey = sortedLevelKeys[i];
                if (levelKey === undefined) continue;
                const levelNodesForKey = levels.get(levelKey);
                if (levelNodesForKey) {
                    this.orderLevelByBarycenter(
                        levelNodesForKey,
                        nodeOrders,
                        inEdges,
                        componentNodes
                    );
                }
            }

            // Backward sweep (max to level 0)
            for (let i = sortedLevelKeys.length - 2; i >= 0; i--) {
                const levelKey = sortedLevelKeys[i];
                if (levelKey === undefined) continue;
                const levelNodesForKey = levels.get(levelKey);
                if (levelNodesForKey) {
                    this.orderLevelByBarycenter(
                        levelNodesForKey,
                        nodeOrders,
                        outEdges,
                        componentNodes
                    );
                }
            }
        }

        return nodeOrders;
    }

    /**
     * Order nodes in a level by the barycenter (average position) of connected neighbors
     */
    private static orderLevelByBarycenter(
        levelNodes: number[],
        nodeOrders: Map<number, number>,
        adjacency: Map<number, number[]>,
        componentNodes: Set<number>
    ): void {
        // Calculate barycenter for each node
        const barycenters: Array<{ nodeId: number; barycenter: number }> = [];
        
        for (const nodeId of levelNodes) {
            const neighbors = (adjacency.get(nodeId) || [])
                .filter(id => componentNodes.has(id) && nodeOrders.has(id));
            
            if (neighbors.length > 0) {
                const sum = neighbors.reduce((acc, nid) => acc + (nodeOrders.get(nid) ?? 0), 0);
                barycenters.push({ nodeId, barycenter: sum / neighbors.length });
            } else {
                // Keep relative position for isolated nodes
                barycenters.push({ nodeId, barycenter: nodeOrders.get(nodeId) ?? 0 });
            }
        }

        // Sort by barycenter
        barycenters.sort((a, b) => a.barycenter - b.barycenter);

        // Update orders
        barycenters.forEach((item, idx) => {
            nodeOrders.set(item.nodeId, idx);
        });
    }

    /**
     * Position nodes for a single component
     */
    private static positionComponentNodes(
        graph: LGraph,
        componentNodes: Set<number>,
        nodeLevels: Map<number, number>,
        nodeOrders: Map<number, number>,
        startY: number
    ): number {
        // Group by level
        const levels = new Map<number, LGraphNode[]>();

        for (const nodeId of componentNodes) {
            const level = nodeLevels.get(nodeId) ?? 0;
            const node = graph._nodes_by_id[nodeId];

            if (node) {
                if (!levels.has(level)) {
                    levels.set(level, []);
                }
                levels.get(level)!.push(node);
            }
        }

        // Sort levels by level number
        const sortedLevelKeys = Array.from(levels.keys()).sort((a, b) => a - b);

        // Calculate max height per level (for centering)
        const levelHeights = new Map<number, number>();
        const levelEntries = Array.from(levels.entries());
        for (const [levelKey, levelNodes] of levelEntries) {
            let height = 0;
            for (let i = 0; i < levelNodes.length; i++) {
                const node = levelNodes[i];
                if (node) {
                    height += node.size?.[1] ?? 100;
                    if (i > 0) height += this.NODE_SPACING;
                }
            }
            levelHeights.set(levelKey, height);
        }

        // Find max height across all levels (for centering)
        const heightValues = Array.from(levelHeights.values());
        const maxHeight = heightValues.length > 0 ? Math.max.apply(null, heightValues) : 0;

        // Position nodes
        let currentX = this.START_X;

        for (const levelKey of sortedLevelKeys) {
            const levelNodes = levels.get(levelKey)!;

            // Sort by computed order
            levelNodes.sort((a, b) => {
                const orderA = nodeOrders.get(a.id as number) ?? 0;
                const orderB = nodeOrders.get(b.id as number) ?? 0;
                return orderA - orderB;
            });

            // Calculate level height
            const levelHeight = levelHeights.get(levelKey) ?? 0;

            // Center this level vertically relative to max height
            const yOffset = startY + (maxHeight - levelHeight) / 2;

            let currentY = yOffset;
            let maxWidthInLevel = 0;

            for (const node of levelNodes) {
                const nodeWidth = node.size?.[0] ?? 200;
                const nodeHeight = node.size?.[1] ?? 100;

                node.pos = [currentX, currentY];
                node.setDirtyCanvas(true, true);

                currentY += nodeHeight + this.NODE_SPACING;
                maxWidthInLevel = Math.max(maxWidthInLevel, nodeWidth);
            }

            currentX += maxWidthInLevel + this.LEVEL_SPACING;
        }

        return maxHeight;
    }
}
