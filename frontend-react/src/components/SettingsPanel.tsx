import { useState, useEffect } from 'react';
import './SettingsPanel.css';

interface SettingsPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export function SettingsPanel({ isOpen, onClose }: SettingsPanelProps) {
  const [zoomDirection, setZoomDirection] = useState<'natural' | 'reversed'>(() => {
    const saved = localStorage.getItem('zoom-direction');
    return (saved as 'natural' | 'reversed') || 'reversed';
  });
  
  const [zoomSpeed, setZoomSpeed] = useState(() => {
    const saved = localStorage.getItem('zoom-speed');
    return saved ? parseFloat(saved) : 1.1;
  });
  
  const [panSpeed, setPanSpeed] = useState(() => {
    const saved = localStorage.getItem('pan-speed');
    return saved ? parseFloat(saved) : 1.0;
  });
  
  const [autoSave, setAutoSave] = useState(() => {
    const saved = localStorage.getItem('auto-save');
    return saved === 'true';
  });
  
  const [showGrid, setShowGrid] = useState(() => {
    const saved = localStorage.getItem('show-grid');
    return saved !== 'false'; // Default to true
  });

  // Apply zoom direction setting
  useEffect(() => {
    localStorage.setItem('zoom-direction', zoomDirection);
    // Dispatch event for LiteGraph to listen to
    window.dispatchEvent(new CustomEvent('zoom-direction-changed', { detail: { direction: zoomDirection } }));
  }, [zoomDirection]);

  // Apply zoom speed setting
  useEffect(() => {
    localStorage.setItem('zoom-speed', zoomSpeed.toString());
    window.dispatchEvent(new CustomEvent('zoom-speed-changed', { detail: { speed: zoomSpeed } }));
  }, [zoomSpeed]);

  // Apply pan speed setting
  useEffect(() => {
    localStorage.setItem('pan-speed', panSpeed.toString());
    window.dispatchEvent(new CustomEvent('pan-speed-changed', { detail: { speed: panSpeed } }));
  }, [panSpeed]);

  // Apply auto-save setting
  useEffect(() => {
    localStorage.setItem('auto-save', autoSave.toString());
  }, [autoSave]);

  // Apply grid visibility setting
  useEffect(() => {
    localStorage.setItem('show-grid', showGrid.toString());
    window.dispatchEvent(new CustomEvent('grid-visibility-changed', { detail: { visible: showGrid } }));
  }, [showGrid]);

  if (!isOpen) return null;

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div className="settings-panel" onClick={(e) => e.stopPropagation()}>
        <div className="settings-header">
          <h2>Settings</h2>
          <button className="settings-close" onClick={onClose}>×</button>
        </div>
        
        <div className="settings-content">
          {/* Canvas Navigation */}
          <section className="settings-section">
            <h3>Canvas Navigation</h3>
            
            <div className="setting-item">
              <label className="setting-label">
                <span>Zoom Direction</span>
                <span className="setting-description">Scroll up to zoom in/out</span>
              </label>
              <div className="setting-control">
                <label className="radio-option">
                  <input
                    type="radio"
                    name="zoom-direction"
                    value="natural"
                    checked={zoomDirection === 'natural'}
                    onChange={(e) => setZoomDirection(e.target.value as 'natural' | 'reversed')}
                  />
                  <span>Natural (scroll up = zoom out)</span>
                </label>
                <label className="radio-option">
                  <input
                    type="radio"
                    name="zoom-direction"
                    value="reversed"
                    checked={zoomDirection === 'reversed'}
                    onChange={(e) => setZoomDirection(e.target.value as 'natural' | 'reversed')}
                  />
                  <span>Reversed (scroll up = zoom in)</span>
                </label>
              </div>
            </div>

            <div className="setting-item">
              <label className="setting-label">
                <span>Zoom Speed</span>
                <span className="setting-description">How fast zooming occurs</span>
              </label>
              <div className="setting-control">
                <input
                  type="range"
                  min="1.05"
                  max="1.5"
                  step="0.05"
                  value={zoomSpeed}
                  onChange={(e) => setZoomSpeed(parseFloat(e.target.value))}
                />
                <span className="setting-value">{zoomSpeed.toFixed(2)}x</span>
              </div>
            </div>

            <div className="setting-item">
              <label className="setting-label">
                <span>Pan Speed</span>
                <span className="setting-description">How fast canvas panning occurs</span>
              </label>
              <div className="setting-control">
                <input
                  type="range"
                  min="0.5"
                  max="2.0"
                  step="0.1"
                  value={panSpeed}
                  onChange={(e) => setPanSpeed(parseFloat(e.target.value))}
                />
                <span className="setting-value">{panSpeed.toFixed(1)}x</span>
              </div>
            </div>
          </section>

          {/* Canvas Appearance */}
          <section className="settings-section">
            <h3>Canvas Appearance</h3>
            
            <div className="setting-item">
              <label className="setting-label">
                <span>Show Grid</span>
                <span className="setting-description">Display background grid on canvas</span>
              </label>
              <div className="setting-control">
                <label className="toggle-switch">
                  <input
                    type="checkbox"
                    checked={showGrid}
                    onChange={(e) => setShowGrid(e.target.checked)}
                  />
                  <span className="toggle-slider"></span>
                </label>
              </div>
            </div>
          </section>

          {/* Editor Behavior */}
          <section className="settings-section">
            <h3>Editor Behavior</h3>
            
            <div className="setting-item">
              <label className="setting-label">
                <span>Auto-Save</span>
                <span className="setting-description">Automatically save graph changes</span>
              </label>
              <div className="setting-control">
                <label className="toggle-switch">
                  <input
                    type="checkbox"
                    checked={autoSave}
                    onChange={(e) => setAutoSave(e.target.checked)}
                  />
                  <span className="toggle-slider"></span>
                </label>
              </div>
            </div>
          </section>

          {/* Reset Section */}
          <section className="settings-section">
            <div className="setting-item">
              <button
                className="settings-reset-button"
                onClick={() => {
                  if (confirm('Reset all settings to defaults?')) {
                    localStorage.removeItem('zoom-direction');
                    localStorage.removeItem('zoom-speed');
                    localStorage.removeItem('pan-speed');
                    localStorage.removeItem('auto-save');
                    localStorage.removeItem('show-grid');
                    window.location.reload();
                  }
                }}
              >
                Reset to Defaults
              </button>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

