import { useEffect, useRef, useState } from 'react';
import type { EditorInstance } from '@legacy/services/EditorInitializer';
import './LitegraphEditor.css';

interface LitegraphEditorProps {
  onEditorReady?: (editor: EditorInstance) => void;
}

/**
 * Wrapper component that mounts your existing Litegraph editor.
 * This component doesn't change your Litegraph implementation at all -
 * it just provides a React mount point for it.
 */
export function LitegraphEditor({ onEditorReady }: LitegraphEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const editorRef = useRef<EditorInstance | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);

  // Listen for loadGraph events from ScansPanel
  useEffect(() => {
    const handleLoadGraph = (event: CustomEvent) => {
      if (!editorRef.current) {
        console.warn('Editor not ready, cannot load graph');
        return;
      }
      
      const { graph, canvas } = editorRef.current;
      if (!graph || !canvas) {
        console.warn('Graph or canvas not available');
        return;
      }
      
      try {
        const graphData = event.detail;
        if (graphData && graphData.nodes && graphData.links) {
          graph.configure(graphData);
          canvas.draw(true);
          
          // Update graph name if provided
          const graphNameEl = document.getElementById('graph-name');
          if (graphNameEl && graphData.name) {
            graphNameEl.textContent = graphData.name;
          }
          
          console.log('✅ Graph loaded from scan');
        } else {
          console.error('Invalid graph data format');
        }
      } catch (error) {
        console.error('Failed to load graph:', error);
      }
    };
    
    window.addEventListener('loadGraph', handleLoadGraph as EventListener);
    return () => {
      window.removeEventListener('loadGraph', handleLoadGraph as EventListener);
    };
  }, []);

  useEffect(() => {
    // Don't initialize if already initialized or container not ready
    if (!containerRef.current || editorRef.current) return;

    let mounted = true;
    let timeoutId: number;

    // Initialize the editor with a small delay to ensure DOM is ready
    const initEditor = async () => {
      // Wait for next tick to ensure React has fully rendered the DOM
      await new Promise(resolve => requestAnimationFrame(resolve));
      
      // Set a timeout in case initialization hangs
      timeoutId = window.setTimeout(() => {
        if (mounted && isLoading) {
          console.error('⏱️ Editor initialization timed out after 30 seconds');
          setLoadError('Initialization timed out. Please refresh the page.');
          setIsLoading(false);
        }
      }, 30000); // 30 second timeout
      try {
        setIsLoading(true);
        setLoadError(null);
        
        console.log('🔄 Loading Litegraph patches...');
        // First, import the patch to ensure Litegraph is patched
        await import('../../../frontend/setup/patchLiteGraph');
        console.log('✅ Litegraph patches loaded');

        console.log('🔄 Loading EditorInitializer...');
        // Then import the EditorInitializer
        const { EditorInitializer } = await import('../../../frontend/services/EditorInitializer');
        
        if (!mounted || !containerRef.current) return;

        // Verify critical DOM elements exist before initializing
        const requiredElements = ['new', 'load', 'save', 'save-as', 'execute', 'graph-file', 'litegraph-canvas'];
        const missingElements = requiredElements.filter(id => !document.getElementById(id));
        
        if (missingElements.length > 0) {
          console.warn('⚠️ Waiting for DOM elements:', missingElements);
          // Wait a bit longer for DOM to be ready
          await new Promise(resolve => setTimeout(resolve, 200));
          
          // Check again
          const stillMissing = requiredElements.filter(id => !document.getElementById(id));
          if (stillMissing.length > 0) {
            throw new Error(`Missing required DOM elements: ${stillMissing.join(', ')}`);
          }
        }

        console.log('📦 Creating editor instance...');
        const initializer = new EditorInitializer();
        
        console.log('🎯 Calling createEditor with container:', containerRef.current);
        console.log('🔍 Container has canvas?', !!containerRef.current?.querySelector('#litegraph-canvas'));
        console.log('🔍 Container has palette?', !!containerRef.current?.querySelector('#node-palette-overlay'));
        
        try {
          const editor = await Promise.race([
            initializer.createEditor(containerRef.current),
            new Promise((_, reject) => 
              setTimeout(() => reject(new Error('createEditor timed out internally')), 25000)
            )
          ]) as EditorInstance;
          
          console.log('✅ createEditor returned successfully');
          
          if (!mounted) return;
          
          editorRef.current = editor;
          window.clearTimeout(timeoutId);
          setIsLoading(false);
          onEditorReady?.(editor);
          console.log('✅ Litegraph editor initialized in React wrapper');
        } catch (err: any) {
          console.error('❌ createEditor failed:', err);
          throw err;
        }
        
      } catch (error: any) {
        window.clearTimeout(timeoutId);
        console.error('❌ Failed to initialize Litegraph editor:', error);
        console.error('Stack trace:', error?.stack);
        setLoadError(error?.message || 'Failed to initialize editor');
        setIsLoading(false);
      }
    };

    initEditor();

    // Cleanup function
    return () => {
      mounted = false;
      window.clearTimeout(timeoutId);
      if (editorRef.current) {
        const graphRunner = (window as any).graphRunner;
        if (graphRunner?.stop) {
          graphRunner.stop();
        }
      }
    };
  }, [onEditorReady, isLoading]);

  // Handle ESC key to exit expanded mode
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isExpanded) {
        setIsExpanded(false);
        // Force reflow and trigger canvas resize
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            window.dispatchEvent(new Event('resize'));
            // Force canvas to recalculate if available
            const canvas = document.getElementById('litegraph-canvas') as HTMLCanvasElement;
            if (canvas && (window as any).LiteGraph) {
              const canvasInstance = (canvas as any).lgc;
              if (canvasInstance) {
                canvasInstance.resize();
              }
            }
          });
        });
      }
    };
    document.addEventListener('keydown', handleEsc);
    return () => document.removeEventListener('keydown', handleEsc);
  }, [isExpanded]);

  return (
    <div ref={containerRef} className={`litegraph-container ${isExpanded ? 'expanded' : ''}`}>
      {/* Loading overlay */}
      {isLoading && (
        <div className="loading-overlay">
          <div className="loading-spinner" />
          <div className="loading-text">Loading Litegraph Editor...</div>
          <button 
            className="reload-button"
            onClick={() => window.location.reload()}
            style={{ marginTop: '16px' }}
          >
            Refresh Page
          </button>
        </div>
      )}
      
      {/* Error overlay */}
      {loadError && (
        <div className="error-overlay">
          <div className="error-content">
            <h3>⚠️ Failed to Load Editor</h3>
            <p>{loadError}</p>
            <button onClick={() => window.location.reload()}>
              Reload Page
            </button>
          </div>
        </div>
      )}
      
      {/* This structure matches your existing index.html */}
      <div id="main-content">
        <canvas id="litegraph-canvas" tabIndex={0} />
        <div id="top-progress" style={{ display: 'none' }}>
          <div id="top-progress-bar" />
          <div id="top-progress-text" />
        </div>
      </div>

      {/* Node palette overlay */}
      <div id="node-palette-overlay" style={{ display: 'none' }}>
        <div id="node-palette">
          <input
            type="text"
            id="node-palette-search"
            placeholder="Search nodes..."
            autoComplete="off"
          />
          <div id="node-palette-list" />
        </div>
      </div>

      {/* Footer controls (file operations, etc.) */}
      <footer className="footer">
        <div className="footer-left">
          <span id="polygon-status" className="polygon-status polygon-status-na" title="Data Status">N/A</span>
          <span id="connection-status" className="status-indicator">Initializing...</span>
          <span id="graph-name" className="graph-name" title="Graph name">Untitled</span>
        </div>
        
        <div className="footer-center">
          <div className="file-controls">
            <button id="new" className="btn-secondary">New</button>
            <button id="load" className="btn-secondary">Load</button>
            {/* Hidden file input for FileManager - MUST have id="graph-file" */}
            <input 
              type="file" 
              id="graph-file" 
              accept=".json" 
              style={{ display: 'none' }} 
            />
            <button id="save" className="btn-secondary">Save</button>
            <button id="save-as" className="btn-secondary">Save As</button>
            
            {/* Divider */}
            <div className="footer-divider" />
            
            {/* Layout controls */}
            <button id="link-mode-btn" className="btn-secondary" title="Link mode">
              🔗
            </button>
            <button id="api-keys-btn" className="btn-secondary" title="API Keys">
              🔐
            </button>
            <button id="auto-align-btn" className="btn-secondary" title="Layout mode: Align">
              Align
            </button>
            <button id="reset-charts-btn" className="btn-secondary" title="Reset view & fit all nodes">
              Reset
            </button>
          </div>
        </div>
        
        <div className="footer-right">
          <button 
            id="expand-toggle" 
            className="btn-secondary"
            onClick={() => {
              setIsExpanded(!isExpanded);
              // Force reflow and trigger canvas resize after state update
              requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                  window.dispatchEvent(new Event('resize'));
                  // Force canvas to recalculate if available
                  const canvas = document.getElementById('litegraph-canvas') as HTMLCanvasElement;
                  if (canvas && (window as any).LiteGraph) {
                    const canvasInstance = (canvas as any).lgc;
                    if (canvasInstance) {
                      canvasInstance.resize();
                    }
                  }
                });
              });
            }}
            title={isExpanded ? 'Exit Fullscreen (ESC)' : 'Expand Canvas'}
          >
            {isExpanded ? 'Exit Fullscreen' : 'Fullscreen'}
          </button>
          <button id="execute" className="btn-primary">Execute</button>
        </div>
      </footer>
    </div>
  );
}

