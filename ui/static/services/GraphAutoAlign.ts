import { LGraph, LGraphNode } from '@comfyorg/litegraph';

interface NodePosition {
    node: LGraphNode;
    level: number;
    index: number;
}

export class GraphAutoAlign {
    private static readonly HORIZONTAL_SPACING = 300; // Space between levels
    private static readonly VERTICAL_SPACING = 100; // Space between nodes in same level
    private static readonly START_X = 100; // Starting X position
    private static readonly START_Y = 100; // Starting Y position

    /**
     * Auto-aligns all nodes in the graph based on flow topology
     */
    static alignGraph(graph: LGraph): void {
        const nodes = graph._nodes || [];
        if (nodes.length === 0) return;

        // Get serialized graph data to access links and node IDs
        const serialized = graph.asSerialisable({ sortNodes: true }) as any;
        const links = serialized.links || [];
        const serializedNodes = serialized.nodes || [];

        // Build node ID to node map
        // Since asSerialisable with sortNodes: true preserves order, we can match by index
        const nodeMap = new Map<number, LGraphNode>();
        
        serializedNodes.forEach((serializedNode: any, index: number) => {
            const nodeId = serializedNode.id;
            let node: LGraphNode | undefined;
            
            // First try to match by index (most reliable when sortNodes: true)
            if (index < nodes.length) {
                node = nodes[index];
            }
            
            // Fallback: try to find by ID property if nodes have it
            if (!node) {
                node = nodes.find((n: any) => {
                    const nodeIdProp = (n as any).id;
                    return nodeIdProp !== undefined && nodeIdProp === nodeId;
                });
            }
            
            // Final fallback: match by position and size
            if (!node) {
                node = nodes.find((n: any) => {
                    return (
                        n.pos &&
                        Math.abs(n.pos[0] - serializedNode.pos[0]) < 0.1 &&
                        Math.abs(n.pos[1] - serializedNode.pos[1]) < 0.1 &&
                        n.size &&
                        n.size[0] === serializedNode.size[0] &&
                        n.size[1] === serializedNode.size[1]
                    );
                });
            }
            
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

        return nodeLevels;
    }

    private static positionNodes(
        nodeLevels: Map<number, number>,
        nodeMap: Map<number, LGraphNode>
    ): void {
        const nodesByLevel = new Map<number, LGraphNode[]>();

        // Group nodes by level
        nodeLevels.forEach((level, nodeId) => {
            const node = nodeMap.get(nodeId);
            if (node) {
                if (!nodesByLevel.has(level)) {
                    nodesByLevel.set(level, []);
                }
                nodesByLevel.get(level)!.push(node);
            }
        });

        // Sort levels
        const sortedLevels = Array.from(nodesByLevel.keys()).sort((a, b) => a - b);

        // Position nodes level by level
        sortedLevels.forEach(level => {
            const levelNodes = nodesByLevel.get(level) || [];
            const x = this.START_X + (level * this.HORIZONTAL_SPACING);

            // Calculate starting Y position to center nodes vertically
            let currentY = this.START_Y;

            levelNodes.forEach(node => {
                const nodeHeight = (node.size && node.size[1]) ? node.size[1] : 100;
                node.pos = [x, currentY];
                node.setDirtyCanvas(true, true);
                currentY += nodeHeight + this.VERTICAL_SPACING;
            });
        });
    }
}
