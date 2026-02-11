// components/App.tsx
// Root application component — fetches node metadata, initializes services, renders editor

import React, { useEffect, useState, useCallback, useRef } from 'react';
import { ReteEditor } from './editor/ReteEditor';
import { undo, redo, autoArrange } from './editor/editor-actions';
import type { NodeSchemaMap } from '../types/nodes';
import { useGraphStore } from '../stores/graphStore';
import { useLogStore } from '../stores/logStore';
import { setupWebSocket, stopExecution } from '../services/WebSocketClient';
import { saveGraph, loadGraphFromFile, startAutosave } from '../services/FileManager';
import { ExecutionStatusService } from '../services/ExecutionStatusService';
import { Toast } from './Toast';
import './editor.css';

export function App() {
  const [nodeMetadata, setNodeMetadata] = useState<NodeSchemaMap>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const statusServiceRef = useRef<ExecutionStatusService | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Reactive store subscriptions
  const docName = useGraphStore((s) => s.docName);
  const isExecuting = useGraphStore((s) => s.isExecuting);
  const metaStatus = useGraphStore((s) => s.metaStatus);
  const executionUI = useGraphStore((s) => s.executionUI);
  const logPanelOpen = useLogStore((s) => s.isOpen);
  const toggleLogPanel = useLogStore((s) => s.togglePanel);

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
    const cleanup = startAutosave();
    return cleanup;
  }, []);

  // Toolbar handlers
  const handleExecute = useCallback(() => {
    useGraphStore.getState().setIsExecuting(true);
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

  // Progress bar visibility
  const showProgress = !(executionUI.progress === 0 && executionUI.determinate);
  const progressBarClass = executionUI.determinate
    ? 'fig-top-progress-bar'
    : 'fig-top-progress-bar indeterminate';
  const progressBarWidth = executionUI.determinate
    ? `${(executionUI.progress ?? 0).toFixed(1)}%`
    : '100%';

  return (
    <div className="fig-app">
      {/* Toolbar */}
      <div className="fig-toolbar">
        <div className="fig-toolbar-left">
          <span className="fig-logo">sosa</span>
          <span className="fig-graph-name">{docName}</span>
        </div>
        <div className="fig-toolbar-center">
          {showProgress && (
            <div className="fig-top-progress" style={{ display: 'block' }}>
              <div
                className={progressBarClass}
                style={{ width: progressBarWidth }}
              />
              <span className="fig-top-progress-text">{executionUI.message}</span>
            </div>
          )}
        </div>
        <div className="fig-toolbar-right">
          <div
            className={`status-indicator ${executionUI.status}`}
            title={executionUI.message}
            aria-label={executionUI.message}
          />
          {Object.entries(metaStatus).map(([key, value]) => (
            <span key={key} className="meta-status" title={`${key}: ${value}`}>
              {value}
            </span>
          ))}
          <button className="fig-btn" onClick={undo} title="Undo (Ctrl+Z)">Undo</button>
          <button className="fig-btn" onClick={redo} title="Redo (Ctrl+Shift+Z)">Redo</button>
          <button className="fig-btn" onClick={autoArrange} title="Auto-layout nodes">Layout</button>
          <button className={`fig-btn ${logPanelOpen ? 'fig-btn-active' : ''}`} onClick={toggleLogPanel} title="Execution log">Log</button>
          {!isExecuting && (
            <button className="fig-btn fig-btn-execute" onClick={handleExecute}>
              Execute
            </button>
          )}
          {isExecuting && (
            <button className="fig-btn fig-btn-stop" onClick={handleStop}>
              Stop
            </button>
          )}
          <button className="fig-btn" onClick={handleSave}>Save</button>
          <button className="fig-btn" onClick={handleLoad}>Load</button>
          <input
            ref={fileInputRef}
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

      {/* Notifications */}
      <Toast />
    </div>
  );
}
