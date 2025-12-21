import type { EditorInstance } from '@legacy/services/EditorInitializer';
import './PropertiesPanel.css';

interface PropertiesPanelProps {
  editor: EditorInstance | null;
}

/**
 * Right properties panel - Shows selected node properties, graph stats, etc.
 */
export function PropertiesPanel({ editor }: PropertiesPanelProps) {
  // TODO: Listen to node selection events from Litegraph
  // and display selected node properties here

  return (
    <aside className="properties-panel">
      <div className="panel-header">
        <h3 className="panel-title">Properties</h3>
      </div>

      <div className="panel-content">
        {!editor ? (
          <div className="empty-state">
            <p>Loading editor...</p>
          </div>
        ) : (
          <div className="empty-state">
            <p>No node selected</p>
            <small>Click on a node to view its properties</small>
          </div>
        )}

        {/* Example of what properties might look like */}
        {/* <div className="property-group">
          <h4 className="property-group-title">Node</h4>
          <div className="property-item">
            <label>Name</label>
            <input type="text" defaultValue="PolygonStockUniverse" />
          </div>
          <div className="property-item">
            <label>Enabled</label>
            <input type="checkbox" defaultChecked />
          </div>
        </div> */}
      </div>

      <div className="panel-footer">
        <div className="stats">
          <div className="stat-item">
            <span className="stat-label">Nodes:</span>
            <span className="stat-value">0</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Links:</span>
            <span className="stat-value">0</span>
          </div>
        </div>
      </div>
    </aside>
  );
}

