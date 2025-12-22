import { useState, useEffect } from 'react';
import { LitegraphEditor } from '@components/LitegraphEditor';
import { TopNav } from '@components/TopNav';
import { Sidebar } from '@components/Sidebar';
import { PropertiesPanel } from '@components/PropertiesPanel';
import { WatchlistPanel } from '@components/WatchlistPanel';
import { useLitegraphCanvas } from '@hooks/useLitegraphCanvas';
import type { EditorInstance } from '@legacy/services/EditorInitializer';
import './App.css';

function App() {
  const [editor, setEditor] = useState<EditorInstance | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [rightPanelOpen, setRightPanelOpen] = useState(true);
  const [rightPanelTab, setRightPanelTab] = useState<'watchlist' | 'properties'>('watchlist');
  const [rightPanelWidth, setRightPanelWidth] = useState(() => {
    const saved = localStorage.getItem('right-panel-width');
    return saved ? parseInt(saved, 10) : 500; // Default width for watchlist
  });
  const [isResizing, setIsResizing] = useState(false);
  
  // Get canvas utilities
  const { fitToView } = useLitegraphCanvas(editor);

  // Wire up the Fit View button once editor is ready
  useEffect(() => {
    if (!editor) return;

    // Find the Fit View button and attach handler
    const fitViewButton = document.getElementById('fit-view-btn');
    if (fitViewButton) {
      const handleFitView = (e: Event) => {
        e.preventDefault();
        e.stopPropagation();
        fitToView();
      };
      
      fitViewButton.addEventListener('click', handleFitView);
      
      return () => {
        fitViewButton.removeEventListener('click', handleFitView);
      };
    }
  }, [editor, fitToView]);

  // Handle panel resizing
  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      const newWidth = window.innerWidth - e.clientX;
      const minWidth = 450; // Ensure Volume and Actions are always visible
      const maxWidth = window.innerWidth * 0.7;
      const clampedWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));
      setRightPanelWidth(clampedWidth);
      document.documentElement.style.setProperty('--properties-width', `${clampedWidth}px`);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      localStorage.setItem('right-panel-width', rightPanelWidth.toString());
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing, rightPanelWidth]);

  // Set initial width
  useEffect(() => {
    document.documentElement.style.setProperty('--properties-width', `${rightPanelWidth}px`);
  }, []);

  return (
    <div className="app-container">
      {/* Top Navigation Bar - React Component */}
      <TopNav 
        editor={editor}
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        onToggleProperties={() => setRightPanelOpen(!rightPanelOpen)}
      />

      <div className="main-layout">
        {/* Left Sidebar - React Component */}
        {sidebarOpen && (
          <Sidebar editor={editor} />
        )}

        {/* Center: Litegraph Canvas - Your Existing Implementation */}
        <div className="canvas-container">
          <LitegraphEditor onEditorReady={setEditor} />
        </div>

        {/* Right Panel - React Component with Tabs */}
        {rightPanelOpen && (
          <div className={`right-panel-wrapper ${isResizing ? 'resizing' : ''}`}>
            <div
              className="right-panel-resize-handle"
              onMouseDown={(e) => {
                e.preventDefault();
                setIsResizing(true);
              }}
            />
            <div className="right-panel-container">
              <div className="right-panel-tabs">
                <button
                  className={`panel-tab ${rightPanelTab === 'watchlist' ? 'active' : ''}`}
                  onClick={() => setRightPanelTab('watchlist')}
                  title="Watchlist"
                >
                  📊 Watchlist
                </button>
                <button
                  className={`panel-tab ${rightPanelTab === 'properties' ? 'active' : ''}`}
                  onClick={() => setRightPanelTab('properties')}
                  title="Properties"
                >
                  ⚙️ Properties
                </button>
              </div>
              <div className="right-panel-content">
                {rightPanelTab === 'watchlist' ? (
                  <WatchlistPanel editor={editor} />
                ) : (
          <PropertiesPanel editor={editor} />
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;

