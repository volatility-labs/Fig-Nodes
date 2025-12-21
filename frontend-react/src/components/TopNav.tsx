import type { EditorInstance } from '@legacy/services/EditorInitializer';
import { useLitegraphCanvas } from '@hooks/useLitegraphCanvas';
import './TopNav.css';

interface TopNavProps {
  editor: EditorInstance | null;
  onToggleSidebar: () => void;
  onToggleProperties: () => void;
}

/**
 * Top navigation bar - React component for app-level navigation
 */
export function TopNav({ editor, onToggleSidebar, onToggleProperties }: TopNavProps) {
  const { fitToView } = useLitegraphCanvas(editor);

  return (
    <nav className="top-nav">
      <div className="nav-left">
        <div className="logo">
          <span className="logo-icon">📊</span>
          <span className="logo-text">Fig Nodes</span>
        </div>

        <div className="nav-divider" />

        <button onClick={onToggleSidebar} className="nav-button" title="Toggle Sidebar">
          <span className="icon">☰</span>
        </button>

        <button onClick={onToggleProperties} className="nav-button" title="Toggle Properties">
          <span className="icon">⚙️</span>
        </button>

        <div className="nav-divider" />

        <button 
          onClick={fitToView} 
          className="nav-button" 
          title="Fit all nodes to view"
          disabled={!editor}
        >
          <span className="icon">🔍</span>
          <span>Fit View</span>
        </button>
      </div>

      <div className="nav-center">
        {/* Workspace selector will go here */}
        <select className="workspace-selector" defaultValue="default">
          <option value="default">My Workspace</option>
        </select>
      </div>

      <div className="nav-right">
        {/* Refresh button for when things get stuck */}
        <button 
          className="nav-button" 
          onClick={() => window.location.reload()}
          title="Refresh page"
        >
          <span className="icon">🔄</span>
        </button>

        {/* User profile will go here after auth is set up */}
        <button className="nav-button">
          <span className="icon">👤</span>
        </button>
        
        {/* This is where "Upgrade" button would go for free tier users */}
        {/* <button className="nav-button-primary">Upgrade</button> */}
      </div>
    </nav>
  );
}

