import { useState, useEffect, useRef } from 'react';
import type { EditorInstance } from '@legacy/services/EditorInitializer';
import { useLitegraphCanvas } from '@hooks/useLitegraphCanvas';
import { ScansPanel } from './ScansPanel';
import './Sidebar.css';

interface SidebarProps {
  editor: EditorInstance | null;
}

interface NodeMetadata {
  name: string;
  category: string;
  description?: string;
  icon?: string;
}

/**
 * Left sidebar - Node palette, assets, etc.
 * Fetches all available nodes from the backend API and displays them in a scrollable list
 */
export function Sidebar({ editor }: SidebarProps) {
  const [activeTab, setActiveTab] = useState<'nodes' | 'scans'>('nodes');
  const [searchQuery, setSearchQuery] = useState('');
  const [nodes, setNodes] = useState<NodeMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isMouseOverSidebar, setIsMouseOverSidebar] = useState(false);
  const nodeListRef = useRef<HTMLDivElement>(null);
  
  // Use canvas utilities hook for better UX
  const { addNodeAtViewportCenter } = useLitegraphCanvas(editor);

  // Fetch all nodes from the backend API
  useEffect(() => {
    async function fetchNodes() {
      try {
        setLoading(true);
        const response = await fetch('/api/v1/nodes');
        if (!response.ok) {
          throw new Error(`Failed to fetch nodes: ${response.statusText}`);
        }
        
        const data = await response.json();
        const nodeMetadata = data.nodes || {};
        
        // Convert node metadata to array format
        const nodesList: NodeMetadata[] = Object.entries(nodeMetadata).map(([name, metadata]: [string, any]) => ({
          name,
          category: metadata.category || 'base',
          description: metadata.description || '',
          icon: getNodeIcon(name, metadata.category),
        }));
        
        // Sort by category, then by name
        nodesList.sort((a, b) => {
          if (a.category !== b.category) {
            return a.category.localeCompare(b.category);
          }
          return a.name.localeCompare(b.name);
        });
        
        setNodes(nodesList);
        setError(null);
      } catch (err) {
        console.error('Error fetching nodes:', err);
        setError(err instanceof Error ? err.message : 'Failed to load nodes');
      } finally {
        setLoading(false);
      }
    }
    
    fetchNodes();
  }, []);

  // Prevent scroll events from reaching Litegraph canvas when mouse is over sidebar
  useEffect(() => {
    const sidebarElement = document.querySelector('.sidebar') as HTMLElement;
    if (!sidebarElement) return;

    const handleWheelCapture = (e: WheelEvent) => {
      // Check if mouse position is actually over the sidebar
      const mouseX = e.clientX;
      const mouseY = e.clientY;
      const sidebarRect = sidebarElement.getBoundingClientRect();
      const isOverSidebar = mouseX >= sidebarRect.left && 
                           mouseX <= sidebarRect.right && 
                           mouseY >= sidebarRect.top && 
                           mouseY <= sidebarRect.bottom;
      
      // Also check if the event target is within the sidebar
      const target = e.target as HTMLElement;
      const sidebar = target?.closest('.sidebar');
      const nodeList = target?.closest('.node-list');
      
      if (isOverSidebar || sidebar || nodeList) {
        // CRITICAL: Stop propagation AND prevent default to block Litegraph completely
        e.stopPropagation();
        e.preventDefault();
        e.stopImmediatePropagation(); // Also stop any other handlers
        
        // If we're on the node list, manually scroll it with increased speed
        if (nodeList && nodeListRef.current) {
          const list = nodeListRef.current;
          const canScrollUp = list.scrollTop > 0;
          const canScrollDown = list.scrollTop < list.scrollHeight - list.clientHeight;
          
          // Only scroll if we can actually scroll
          if ((e.deltaY < 0 && canScrollUp) || (e.deltaY > 0 && canScrollDown)) {
            // Faster scrolling - 2.5x multiplier for quick navigation through nodes
            const scrollMultiplier = 2.5;
            list.scrollTop += e.deltaY * scrollMultiplier;
          }
        }
        
        // Return false to ensure event doesn't propagate
        return false;
      }
    };

    // Use capture phase to catch events BEFORE Litegraph's handler
    // Use passive: false so we can call preventDefault()
    // Use capture: true to intercept before any other handlers
    document.addEventListener('wheel', handleWheelCapture, { capture: true, passive: false });
    window.addEventListener('wheel', handleWheelCapture, { capture: true, passive: false });
    return () => {
      document.removeEventListener('wheel', handleWheelCapture, { capture: true });
      window.removeEventListener('wheel', handleWheelCapture, { capture: true });
    };
  }, []);

  // Get icon for node based on name and category
  function getNodeIcon(name: string, category?: string): string {
    // Category-based icons
    if (category === 'MARKET') return '📈';
    if (category === 'INDICATORS') return '📊';
    if (category === 'LLM') return '🤖';
    if (category === 'IO') return '📝';
    if (category === 'FLOW') return '🔄';
    if (category === 'CORE') return '⚙️';
    
    // Name-based icons for specific nodes
    if (name.includes('Filter')) return '🔍';
    if (name.includes('Chart') || name.includes('Plot')) return '📉';
    if (name.includes('Universe') || name.includes('Stock')) return '📈';
    if (name.includes('Save') || name.includes('Output')) return '💾';
    if (name.includes('Input') || name.includes('Text')) return '📝';
    if (name.includes('Chat') || name.includes('LLM')) return '🤖';
    
    return '📦'; // Default icon
  }

  const filteredNodes = nodes.filter(node =>
    node.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    node.category.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (node.description || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleAddNode = async (nodeType: string) => {
    if (!editor) {
      console.warn('Editor not ready yet');
      return;
    }

    // Use the utility function which handles positioning and centering
    await addNodeAtViewportCenter(nodeType);
  };

  return (
    <aside 
      className="sidebar"
      onMouseEnter={() => setIsMouseOverSidebar(true)}
      onMouseLeave={() => setIsMouseOverSidebar(false)}
      onWheel={(e) => {
        // Stop all wheel events on sidebar from reaching canvas
        e.stopPropagation();
        e.preventDefault();
        e.stopImmediatePropagation();
      }}
    >
      <div className="sidebar-tabs">
        <button
          className={`tab ${activeTab === 'nodes' ? 'active' : ''}`}
          onClick={() => setActiveTab('nodes')}
        >
          Nodes
        </button>
        <button
          className={`tab ${activeTab === 'scans' ? 'active' : ''}`}
          onClick={() => setActiveTab('scans')}
        >
          Scans
        </button>
      </div>

      {activeTab === 'nodes' && (
        <div 
          className="sidebar-content"
          onWheel={(e) => {
            // Stop propagation on entire sidebar content area
            e.stopPropagation();
            e.preventDefault();
            e.stopImmediatePropagation();
          }}
        >
          <div className="search-container">
            <input
              type="search"
              placeholder="Search nodes..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="search-input"
            />
          </div>

          <div 
            ref={nodeListRef}
            className="node-list"
            tabIndex={-1}
            onWheel={(e) => {
              // Stop propagation to prevent canvas scrolling
              e.stopPropagation();
              e.preventDefault();
              e.stopImmediatePropagation();
              
              // Manually scroll the node list with increased speed
              if (nodeListRef.current) {
                const list = nodeListRef.current;
                const canScrollUp = list.scrollTop > 0;
                const canScrollDown = list.scrollTop < list.scrollHeight - list.clientHeight;
                
                if ((e.deltaY < 0 && canScrollUp) || (e.deltaY > 0 && canScrollDown)) {
                  // Faster scrolling - 2.5x multiplier for quick navigation through nodes
                  const scrollMultiplier = 2.5;
                  list.scrollTop += e.deltaY * scrollMultiplier;
                }
              }
            }}
          >
            {loading ? (
              <div className="empty-state">
                <p>Loading nodes...</p>
              </div>
            ) : error ? (
              <div className="empty-state">
                <p>Error loading nodes</p>
                <small>{error}</small>
              </div>
            ) : filteredNodes.length === 0 ? (
              <div className="empty-state">
                <p>No nodes found</p>
                <small>Try a different search term</small>
              </div>
            ) : (
              <>
                {filteredNodes.map((node) => (
                  <div
                    key={node.name}
                    className="node-item"
                    onClick={() => handleAddNode(node.name)}
                    title={`Add ${node.name}${node.description ? ` - ${node.description}` : ''}`}
                  >
                    <span className="node-icon">{node.icon || '📦'}</span>
                    <div className="node-info">
                      <div className="node-name">{node.name}</div>
                      <div className="node-category">{node.category}</div>
                    </div>
                  </div>
                ))}
                {searchQuery && (
                  <div className="node-list-footer">
                    <small>Showing {filteredNodes.length} of {nodes.length} nodes</small>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {activeTab === 'scans' && (
        <ScansPanel editor={editor} />
      )}
    </aside>
  );
}

