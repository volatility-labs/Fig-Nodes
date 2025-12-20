import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import type { EditorInstance } from '@legacy/services/EditorInitializer';
import './ScansPanel.css';

interface Scan {
  id: string;
  name: string;
  description: string | null;
  graph_data: any; // The graph configuration
  created_at: string;
  updated_at: string;
  last_executed: string | null;
}

interface ScansPanelProps {
  editor?: EditorInstance | null;
}

/**
 * Scans Panel - Displays saved scans from cloud storage
 * Replaces local file downloads with cloud-based scan storage
 * Saves graph configurations/workflows instead of output files
 */
export function ScansPanel({ editor }: ScansPanelProps = {}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [saveName, setSaveName] = useState('');
  const [saveDescription, setSaveDescription] = useState('');
  const queryClient = useQueryClient();

  // Fetch scans from cloud API
  const { data: scans, isLoading, error } = useQuery<{ scans: Scan[] }>({
    queryKey: ['scans'],
    queryFn: async () => {
      const response = await fetch('/api/v1/scans');
      if (!response.ok) {
        throw new Error('Failed to fetch scans');
      }
      return response.json();
    },
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  // Save scan mutation
  const saveScan = useMutation({
    mutationFn: async ({ name, description, graphData }: { name: string; description?: string; graphData: any }) => {
      const response = await fetch('/api/v1/scans', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description, graph_data: graphData }),
      });
      if (!response.ok) {
        throw new Error('Failed to save scan');
      }
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scans'] });
      setShowSaveDialog(false);
      setSaveName('');
      setSaveDescription('');
    },
  });

  // Delete scan mutation
  const deleteScan = useMutation({
    mutationFn: async (scanId: string) => {
      const response = await fetch(`/api/v1/scans/${scanId}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        throw new Error('Failed to delete scan');
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scans'] });
    },
  });

  // Load scan into editor mutation
  const loadScan = useMutation({
    mutationFn: async (scanId: string) => {
      const response = await fetch(`/api/v1/scans/${scanId}`);
      if (!response.ok) {
        throw new Error('Failed to load scan');
      }
      const scan = await response.json();
      return scan.graph_data;
    },
  });

  const filteredScans = scans?.scans.filter(scan =>
    scan.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (scan.description && scan.description.toLowerCase().includes(searchQuery.toLowerCase()))
  ) || [];

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const handleLoadScan = async (scan: Scan) => {
    try {
      const graphData = await loadScan.mutateAsync(scan.id);
      // Dispatch custom event to load graph into editor
      window.dispatchEvent(new CustomEvent('loadGraph', { detail: graphData }));
      // Mark as executed
      await fetch(`/api/v1/scans/${scan.id}/execute`, { method: 'POST' });
      queryClient.invalidateQueries({ queryKey: ['scans'] });
    } catch (error) {
      console.error('Failed to load scan:', error);
      alert('Failed to load scan. Please try again.');
    }
  };

  const handleSaveScan = () => {
    if (!editor) {
      alert('Editor not ready. Please wait for the editor to initialize.');
      return;
    }

    const { graph } = editor;
    if (!graph) {
      alert('Graph not available.');
      return;
    }

    try {
      // Get current graph configuration
      const graphData = (graph as any).asSerialisable({ sortNodes: true });
      
      if (!saveName.trim()) {
        alert('Please enter a name for this scan.');
        return;
      }

      saveScan.mutate({
        name: saveName.trim(),
        description: saveDescription.trim() || undefined,
        graphData,
      });
    } catch (error) {
      console.error('Failed to save scan:', error);
      alert('Failed to save scan. Please try again.');
    }
  };

  return (
    <div className="sidebar-content">
      <div className="search-container">
        <input
          type="search"
          placeholder="Search scans..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="search-input"
        />
      </div>

      <div className="scans-list">
        {isLoading ? (
          <div className="empty-state">
            <p>Loading scans...</p>
          </div>
        ) : error ? (
          <div className="empty-state">
            <p>Error loading scans</p>
            <small>Check your connection</small>
          </div>
        ) : filteredScans.length === 0 ? (
          <div className="empty-state">
            <p>No scans found</p>
            <small>
              {searchQuery ? 'Try a different search term' : 'Scans will appear here when you save them'}
            </small>
          </div>
        ) : (
          filteredScans.map((scan) => (
            <div key={scan.id} className="scan-item">
              <div className="scan-info">
                <div className="scan-name">{scan.name}</div>
                {scan.description && (
                  <div className="scan-description">{scan.description}</div>
                )}
                <div className="scan-meta">
                  <span className="scan-date">Updated: {formatDate(scan.updated_at)}</span>
                  {scan.last_executed && (
                    <span className="scan-executed">Executed: {formatDate(scan.last_executed)}</span>
                  )}
                </div>
              </div>
              <div className="scan-actions">
                <button
                  className="scan-action-btn scan-load-btn"
                  onClick={() => handleLoadScan(scan)}
                  title="Load scan into editor"
                  disabled={loadScan.isPending}
                >
                  <span className="scan-load-icon">📂</span>
                  <span className="scan-load-text">Load</span>
                </button>
                <button
                  className="scan-action-btn scan-delete-btn"
                  onClick={() => {
                    if (confirm(`Delete "${scan.name}"?`)) {
                      deleteScan.mutate(scan.id);
                    }
                  }}
                  title="Delete scan"
                  disabled={deleteScan.isPending}
                >
                  🗑️
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      <div className="sidebar-footer">
        <button 
          className="link-button save-scan-btn" 
          onClick={() => setShowSaveDialog(true)}
          disabled={!editor}
          title={!editor ? 'Editor not ready' : 'Save current graph as scan'}
        >
          💾 Save Scan
        </button>
        <button className="link-button" onClick={() => queryClient.invalidateQueries({ queryKey: ['scans'] })}>
          Refresh ↻
        </button>
      </div>

      {showSaveDialog && (
        <div className="save-dialog-overlay" onClick={() => setShowSaveDialog(false)}>
          <div className="save-dialog" onClick={(e) => e.stopPropagation()}>
            <h3>Save Scan</h3>
            <div className="save-dialog-content">
              <label>
                Name *
                <input
                  type="text"
                  value={saveName}
                  onChange={(e) => setSaveName(e.target.value)}
                  placeholder="e.g., Momentum Scanner"
                  autoFocus
                />
              </label>
              <label>
                Description
                <textarea
                  value={saveDescription}
                  onChange={(e) => setSaveDescription(e.target.value)}
                  placeholder="Optional description..."
                  rows={3}
                />
              </label>
            </div>
            <div className="save-dialog-actions">
              <button 
                className="btn-secondary" 
                onClick={() => {
                  setShowSaveDialog(false);
                  setSaveName('');
                  setSaveDescription('');
                }}
              >
                Cancel
              </button>
              <button 
                className="btn-primary" 
                onClick={handleSaveScan}
                disabled={!saveName.trim() || saveScan.isPending}
              >
                {saveScan.isPending ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

