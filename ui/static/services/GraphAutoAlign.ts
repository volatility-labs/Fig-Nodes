import { LGraph, LGraphNode } from '@comfyorg/litegraph';


export class GraphAutoAlign {
    private static readonly HORIZONTAL_SPACING = 300; // Space between levels
    private static readonly VERTICAL_SPACING = 100; // Space between nodes in same level
    private static readonly START_X = 100; // Starting X position
    private static readonly START_Y = 100; // Starting Y position
    private static readonly ESTIMATED_CANVAS_HEIGHT = 800; // Fallback if no canvas info; can be overridden

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
        // Since asSerialisable with sortNodes: true preserves order, we can match by index
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

        // Topological sort to assign levels
        const nodeLevels = this.topologicalLevels(nodeMap, inEdges, outEdges);

        // Position nodes
        this.positionNodes(nodeLevels, nodeMap);

        // Redraw canvas
        const canvas = graph.list_of_graphcanvas?.[0];
        if (canvas) {
            canvas.draw(true, true);
        }
    }

    private static topologicalLevels(
        nodeMap: Map<number, LGraphNode>,
        inEdges: Map<number, number[]>,
        outEdges: Map<number, number[]>
    ): Map<number, number> {
        const nodeLevels = new Map<number, number>();
        const queue: Array<{ id: number; level: number }> = [];
        const inDegree = new Map<number, number>();

        // Calculate in-degree for each node
        nodeMap.forEach((_, nodeId) => {
            const degree = inEdges.get(nodeId)?.length || 0;
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

            // Process outgoing edges
            const neighbors = outEdges.get(id) || [];
            neighbors.forEach(neighborId => {
                const currentDegree = inDegree.get(neighborId) || 0;
                inDegree.set(neighborId, currentDegree - 1);

                if (currentDegree - 1 === 0 && !nodeLevels.has(neighborId)) {
                    queue.push({ id: neighborId, level: level + 1 });
                }
            });
        }

        // Handle disconnected nodes (assign to level 0)
        nodeMap.forEach((_, nodeId) => {
            if (!nodeLevels.has(nodeId)) {
                nodeLevels.set(nodeId, 0);
            }
        });

        // After processing, detect cycles (unprocessed nodes with inDegree > 0)
        const processedCount = nodeLevels.size;
        if (processedCount < nodeMap.size) {
            console.warn(`Cycle detected: ${nodeMap.size - processedCount} nodes in cycle(s). Grouping at max level + 1.`);
            let maxLevel = Math.max(...Array.from(nodeLevels.values()), 0);
            nodeMap.forEach((_, nodeId) => {
                if (!nodeLevels.has(nodeId)) {
                    nodeLevels.set(nodeId, maxLevel + 1);
                }
            });
        }
        return nodeLevels;
    }

    private static positionNodes(
        nodeLevels: Map<number, number>,
        nodeMap: Map<number, LGraphNode>
    ): void {
        const nodesByLevel = new Map<number, LGraphNode[]>();

        nodeLevels.forEach((level, nodeId) => {
            const node = nodeMap.get(nodeId);
            if (node) {
                if (!nodesByLevel.has(level)) {
                    nodesByLevel.set(level, []);
                }
                nodesByLevel.get(level)!.push(node);
            }
        });

        const sortedLevels = Array.from(nodesByLevel.keys()).sort((a, b) => a - b);

        // For disconnected components at level 0, offset them horizontally if multiple groups
        if (nodesByLevel.has(0)) {
            const level0Nodes = nodesByLevel.get(0)!;
            // Simple grouping: sort by original X to cluster
            level0Nodes.sort((a, b) => (a.pos?.[0] ?? 0) - (b.pos?.[0] ?? 0));
        }

        sortedLevels.forEach((level, levelIndex) => {
            let levelNodes = nodesByLevel.get(level) || [];
            
            // Sort within level by original Y position for consistency
            levelNodes = levelNodes.sort((a, b) => (a.pos?.[1] ?? 0) - (b.pos?.[1] ?? 0));
            
            // Dynamic horizontal spacing: add extra based on max width in previous level
            let x = this.START_X + (level * this.HORIZONTAL_SPACING);
            if (level > 0) {
                const prevLevelNodes = nodesByLevel.get(sortedLevels[levelIndex - 1]) || [];
                const maxPrevWidth = Math.max(...prevLevelNodes.map(n => (n.size?.[0] ?? 200)), 200);
                x += maxPrevWidth / 2;
            }
            
            // Calculate total height for centering
            const totalHeight = levelNodes.reduce((sum, node) => {
                return sum + ((node.size && node.size[1]) ? node.size[1] : 100) + this.VERTICAL_SPACING;
            }, 0) - this.VERTICAL_SPACING;
            
            // Center vertically using estimated canvas height
            let currentY = this.START_Y + (this.ESTIMATED_CANVAS_HEIGHT - totalHeight) / 2;
            
            levelNodes.forEach(node => {
                const nodeHeight = (node.size && node.size[1]) ? node.size[1] : 100;
                node.pos = [x, currentY];
                node.setDirtyCanvas(true, true);
                currentY += nodeHeight + this.VERTICAL_SPACING;
            });
        });
    }
}
