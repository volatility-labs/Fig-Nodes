import BaseCustomNode from '../base/BaseCustomNode';

export default class SymbolQuickPlotNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [400, 200];
        // Don't display results on the node - images should go to ImageDisplay node
        this.displayResults = false;
        
        // Add "Run" button to execute this node independently
        // Create the button widget
        const runButton = this.addWidget('button', '▶ Run', '', (event?: any) => {
            // Stop event propagation to prevent triggering full graph execution
            if (event) {
                event.stopPropagation?.();
                event.preventDefault?.();
            }
            this.executeNode();
        }, {});
        
        // Move Run button to the top of the widgets array
        if (this.widgets && this.widgets.length > 1) {
            const buttonIndex = this.widgets.indexOf(runButton);
            if (buttonIndex > 0) {
                // Remove from current position
                this.widgets.splice(buttonIndex, 1);
                // Insert at the beginning
                this.widgets.unshift(runButton);
            }
        }
    }
    
    /**
     * Execute just this node independently without running the entire graph
     */
    async executeNode(): Promise<void> {
        if (!this.graph) {
            console.warn('Cannot execute node: no graph context');
            return;
        }
        
        // Check if symbols are provided
        const symbols = (this.properties['symbols'] as string) || '';
        if (!symbols.trim()) {
            alert('Please enter symbols in the "symbols" parameter');
            return;
        }
        
        // Clear previous state
        this.error = '';
        this.progress = -1;
        this.progressText = '';
        this.setDirtyCanvas(true, true);
        
        // Create a minimal subgraph containing just this node
        // Use the node's serialize method to properly serialize this node
        const nodeData = this.serialize();
        
        // Ensure node ID is a number (required by backend)
        const nodeId = typeof this.id === 'number' ? this.id : parseInt(String(this.id), 10) || 0;
        
        // Ensure the serialized node has a numeric ID and correct type
        nodeData.id = nodeId;
        if (!nodeData.type) {
            nodeData.type = this.type || 'SymbolQuickPlot';
        }
        
        // Ensure properties are included (they should be from serialize(), but double-check)
        // Merge properties to ensure all current values are included
        nodeData.properties = { ...this.properties, ...(nodeData.properties || {}) };
        
        // Debug: Log properties being sent
        console.log('Node properties being sent:', nodeData.properties);
        console.log('Symbols value:', nodeData.properties?.symbols);
        
        // Get the full graph serialization and filter to just this node
        // This ensures we match the exact format expected by the backend
        const fullGraph = this.graph?.asSerialisable({ sortNodes: false });
        
        // Create a proper SerialisableGraph structure matching backend expectations
        // Use the graph's structure but filter nodes to just this one
        const subgraph = {
            id: fullGraph?.id || String(nodeId),
            revision: fullGraph?.revision || 0,
            version: (fullGraph?.version ?? 0) as 0 | 1,
            state: fullGraph?.state || {
                lastNodeId: nodeId,
                lastLinkId: 0,
                lastGroupId: 0,
                lastRerouteId: 0,
            },
            nodes: [nodeData],
            groups: [],
            config: fullGraph?.config || {},
            extra: { ...(fullGraph?.extra || {}), force_execute_all: true },
        };
        
        // Debug: Log the subgraph structure (truncated for readability)
        console.log('Subgraph structure:', {
            id: subgraph.id,
            revision: subgraph.revision,
            version: subgraph.version,
            state: subgraph.state,
            nodeCount: subgraph.nodes.length,
            nodeType: subgraph.nodes[0]?.type,
            nodeId: subgraph.nodes[0]?.id,
            hasProperties: !!subgraph.nodes[0]?.properties,
        });
        
        // Execute via WebSocket using a dedicated connection
        // Use a unique URL parameter to ensure this is treated as a separate execution
        this.executeSubgraphViaWebSocket(subgraph);
    }
    
    /**
     * Execute a subgraph via WebSocket
     * Uses a dedicated WebSocket connection to avoid interfering with main graph execution
     */
    private executeSubgraphViaWebSocket(graphData: any): void {
        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const backendHost = window.location.hostname;
        // Use a unique session ID to ensure this is a separate execution
        const uniqueSessionId = `node_${this.id}_${Date.now()}`;
        const wsUrl = `${protocol}://${backendHost}${window.location.port === '8000' ? '' : ':8000'}/execute`;
        
        let ws: WebSocket | null = null;
        let isClosing = false;
        
        try {
            ws = new WebSocket(wsUrl);
            
            ws.onopen = () => {
                // Send connect message with unique session ID to ensure isolation
                const connectMessage = { type: 'connect', session_id: uniqueSessionId };
                ws?.send(JSON.stringify(connectMessage));
            };
            
            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    
                    // Handle session message
                    if (data.type === 'session') {
                        const newSessionId = data.session_id;
                        console.log('Session established:', newSessionId);
                        // Store in a separate key to avoid conflicts
                        localStorage.setItem(`node_session_${this.id}`, newSessionId);
                        
                        // Ensure node ID is a number in the serialized node data
                        const serializedNode = graphData.nodes[0];
                        if (serializedNode && typeof serializedNode.id !== 'number') {
                            serializedNode.id = typeof this.id === 'number' ? this.id : parseInt(String(this.id), 10) || 0;
                        }
                        
                        // Validate graph structure before sending
                        if (!graphData.nodes || graphData.nodes.length === 0) {
                            console.error('No nodes in graph data');
                            this.error = 'Invalid graph structure: no nodes';
                            this.setDirtyCanvas(true, true);
                            if (ws && !isClosing) {
                                isClosing = true;
                                ws.close();
                            }
                            return;
                        }
                        
                        if (!graphData.nodes[0].type) {
                            console.error('Node missing type:', graphData.nodes[0]);
                            this.error = 'Invalid node: missing type';
                            this.setDirtyCanvas(true, true);
                            if (ws && !isClosing) {
                                isClosing = true;
                                ws.close();
                            }
                            return;
                        }
                        
                        // Send graph execution message
                        const message = { type: 'graph', graph_data: graphData };
                        console.log('Sending graph message - Node type:', graphData.nodes[0].type, 'Node ID:', graphData.nodes[0].id);
                        try {
                            ws?.send(JSON.stringify(message));
                        } catch (sendErr) {
                            console.error('Failed to send graph message:', sendErr);
                            this.error = 'Failed to send execution request';
                            this.setDirtyCanvas(true, true);
                        }
                        return;
                    }
                    
                    // Handle error messages
                    if (data.type === 'error') {
                        console.error('Backend error:', data.message);
                        this.error = data.message || 'Unknown error occurred';
                        this.setDirtyCanvas(true, true);
                        if (ws && !isClosing) {
                            isClosing = true;
                            ws.close();
                        }
                        return;
                    }
                    
                    // Handle results - only process if this is for our node
                    if (data.type === 'data' && data.results) {
                        console.log('Received data results:', Object.keys(data.results));
                        // Try both string and number keys for node ID
                        const nodeIdStr = this.id.toString();
                        const nodeIdNum = typeof this.id === 'number' ? this.id : parseInt(String(this.id), 10);
                        const nodeResults = data.results[nodeIdStr] || data.results[nodeIdNum] || data.results[String(nodeIdNum)];
                        console.log('Node results for ID', this.id, '(tried:', nodeIdStr, nodeIdNum, '):', nodeResults);
                        if (nodeResults) {
                            this.onExecute(nodeResults);
                        } else {
                            console.warn('No results found for node ID:', this.id, 'Available keys:', Object.keys(data.results));
                            // If no results but execution finished, show message
                            this.progressText = 'Execution completed but no results received';
                            this.setDirtyCanvas(true, true);
                        }
                        if (!isClosing) {
                            isClosing = true;
                            ws?.close();
                        }
                    } else if (data.type === 'error') {
                        console.error('Execution error:', data.message);
                        this.error = data.message || 'Execution failed';
                        this.setDirtyCanvas(true, true);
                        if (!isClosing) {
                            isClosing = true;
                            ws?.close();
                        }
                    } else if (data.type === 'progress') {
                        // Handle progress updates - only for this node
                        if (data.node_id === this.id) {
                            this.progress = data.progress ?? -1;
                            this.progressText = data.text || '';
                            this.setDirtyCanvas(true, true);
                        }
                    } else if (data.type === 'status') {
                        // Handle status messages
                        console.log('Status update:', data.state, data.message);
                        if (data.message) {
                            this.progressText = data.message;
                            this.setDirtyCanvas(true, true);
                        }
                        // If status is ERROR, show error
                        if (data.state === 'error') {
                            this.error = data.message || 'Execution error';
                            this.setDirtyCanvas(true, true);
                            if (!isClosing) {
                                isClosing = true;
                                ws?.close();
                            }
                        }
                        // If status is FINISHED but no data was received, log warning
                        if (data.state === 'finished') {
                            console.log('Execution finished, waiting for data...');
                            // Don't close yet - wait for data message
                        }
                    } else {
                        // Log any unhandled message types
                        console.log('Unhandled message type:', data.type, data);
                    }
                } catch (err) {
                    console.error('Error processing WebSocket message:', err);
                }
            };
            
            ws.onerror = (err) => {
                console.error('WebSocket error:', err);
                this.error = 'Connection error';
                this.setDirtyCanvas(true, true);
                if (!isClosing) {
                    isClosing = true;
                    ws?.close();
                }
            };
            
            ws.onclose = () => {
                // Cleanup
                ws = null;
                isClosing = false;
            };
        } catch (err: any) {
            console.error('Failed to execute node:', err);
            this.error = err.message || 'Execution failed';
            this.setDirtyCanvas(true, true);
        }
    }

    onExecute(nodeData: any): void {
        // Images are output via the output port - propagate to connected nodes
        // Find the "images" output slot and set its data
        const imagesOutputIndex = this.findOutputSlotIndex('images');
        if (imagesOutputIndex >= 0 && nodeData.images) {
            // Set output data so connected nodes can receive it
            this.setOutputData(imagesOutputIndex, nodeData.images);
            
            // Manually propagate to connected nodes (like ImageDisplay)
            // This is needed because standalone execution doesn't automatically trigger connected nodes
            if (this.graph && this.outputs && this.outputs[imagesOutputIndex]) {
                const outputSlot = this.outputs[imagesOutputIndex];
                if (outputSlot.links) {
                    for (const linkId of outputSlot.links) {
                        const link = this.graph._links.get(linkId);
                        if (link) {
                            const targetNode = this.graph.getNodeById(link.target_id);
                            if (targetNode && typeof (targetNode as any).updateDisplay === 'function') {
                                // Call updateDisplay on the connected node with the images data
                                (targetNode as any).updateDisplay({ images: nodeData.images });
                            }
                        }
                    }
                }
            }
        }
        this.setDirtyCanvas(true, true);
    }
}

