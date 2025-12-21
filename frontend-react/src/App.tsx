import { useState, useEffect } from 'react';
import { LitegraphEditor } from '@components/LitegraphEditor';
import { TopNav } from '@components/TopNav';
import { Sidebar } from '@components/Sidebar';
import { PropertiesPanel } from '@components/PropertiesPanel';
import { useLitegraphCanvas } from '@hooks/useLitegraphCanvas';
import type { EditorInstance } from '@legacy/services/EditorInitializer';
import './App.css';

function App() {
  const [editor, setEditor] = useState<EditorInstance | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [propertiesPanelOpen, setPropertiesPanelOpen] = useState(true);
  
  // Get canvas utilities
  const { fitToView } = useLitegraphCanvas(editor);

  // Wire up the Reset button once editor is ready
  useEffect(() => {
    if (!editor) return;

    // Find the Reset button and attach handler
    const resetButton = document.getElementById('reset-charts-btn');
    if (resetButton) {
      const handleReset = (e: Event) => {
        e.preventDefault();
        e.stopPropagation();
        fitToView();
      };
      
      resetButton.addEventListener('click', handleReset);
      
      return () => {
        resetButton.removeEventListener('click', handleReset);
      };
    }
  }, [editor, fitToView]);

  return (
    <div className="app-container">
      {/* Top Navigation Bar - React Component */}
      <TopNav 
        editor={editor}
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        onToggleProperties={() => setPropertiesPanelOpen(!propertiesPanelOpen)}
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

        {/* Right Panel - React Component */}
        {propertiesPanelOpen && (
          <PropertiesPanel editor={editor} />
        )}
      </div>
    </div>
  );
}

export default App;

