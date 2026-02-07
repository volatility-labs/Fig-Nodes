// components/App.tsx
// Root application component — fetches node metadata, initializes services, renders editor

import React, { useEffect, useState, useCallback, useRef } from 'react';
import { ReteEditor } from '../rete/ReteEditor';
import type { NodeMetadataMap } from '../types/node-metadata';
import { useGraphStore } from '../stores/graph-store';
import { setupWebSocket, stopExecution } from '../services/WebSocketClient';
import { saveGraph, loadGraphFromFile, restoreFromAutosave, startAutosave } from '../services/FileManager';
import { ExecutionStatusService } from '../services/ExecutionStatusService';
import './editor.css';

export function App() {
  const [nodeMetadata, setNodeMetadata] = useState<NodeMetadataMap>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const statusServiceRef = useRef<ExecutionStatusService | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fetch node metadata from backend
  useEffect(() => {
    fetch('/api/v1/nodes')
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to fetch nodes: ${res.status}`);
        return res.json();
      })
      .then((data) => {
        setNodeMetadata(data.nodes);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load node types:', err);
        setError(err.message);
        setLoading(false);
      });
  }, []);

  // Initialize services
  useEffect(() => {
    statusServiceRef.current = new ExecutionStatusService();
    setupWebSocket(statusServiceRef.current);
    restoreFromAutosave();
    const cleanup = startAutosave();
    return cleanup;
  }, []);

  // Toolbar handlers
  const handleExecute = useCallback(() => {
    const executeBtn = document.getElementById('execute');
    const stopBtn = document.getElementById('stop');
    if (executeBtn) executeBtn.style.display = 'none';
    if (stopBtn) stopBtn.style.display = 'inline-block';

    const event = new CustomEvent('fig:execute');
    window.dispatchEvent(event);
  }, []);

  const handleStop = useCallback(() => {
    stopExecution();
  }, []);

  const handleSave = useCallback(() => {
    saveGraph();
  }, []);

  const handleLoad = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileChange = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      await loadGraphFromFile(file, nodeMetadata);
      e.target.value = '';
    }
  }, [nodeMetadata]);

  if (loading) {
    return (
      <div className="fig-loading">
        <div className="fig-loading-text">Loading node types...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="fig-error">
        <div className="fig-error-text">Failed to load: {error}</div>
        <button onClick={() => window.location.reload()}>Retry</button>
      </div>
    );
  }

  return (
    <div className="fig-app">
      {/* Toolbar */}
      <div className="fig-toolbar">
        <div className="fig-toolbar-left">
          <span className="fig-logo">fig-node</span>
          <span id="graph-name" className="fig-graph-name">
            {useGraphStore.getState().doc.name}
          </span>
        </div>
        <div className="fig-toolbar-center">
          <div id="top-progress" className="fig-top-progress" style={{ display: 'none' }}>
            <div id="top-progress-bar" className="fig-top-progress-bar" />
            <span id="top-progress-text" className="fig-top-progress-text" />
          </div>
        </div>
        <div className="fig-toolbar-right">
          <div id="status-indicator" className="status-indicator connected" title="Ready" />
          <div id="polygon-status" className="polygon-status na">N/A</div>
          <button id="execute" className="fig-btn fig-btn-execute" onClick={handleExecute}>
            Execute
          </button>
          <button
            id="stop"
            className="fig-btn fig-btn-stop"
            onClick={handleStop}
            style={{ display: 'none' }}
          >
            Stop
          </button>
          <button id="save" className="fig-btn" onClick={handleSave}>Save</button>
          <button id="load" className="fig-btn" onClick={handleLoad}>Load</button>
          <input
            ref={fileInputRef}
            id="graph-file"
            type="file"
            accept=".json"
            style={{ display: 'none' }}
            onChange={handleFileChange}
          />
        </div>
      </div>

      {/* Editor */}
      <div className="fig-editor-wrapper">
        <ReteEditor nodeMetadata={nodeMetadata} />
      </div>
    </div>
  );
}
