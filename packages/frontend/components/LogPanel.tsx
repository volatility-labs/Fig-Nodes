// components/LogPanel.tsx
// Right-side collapsible panel with Live and History tabs for execution logs.

import { useEffect, useRef } from 'react';
import { useLogStore, type LiveLogEntry } from '../stores/logStore';
import { fetchLogList, fetchLogFile } from '../services/LogService';

function formatTime(ts: string): string {
  try {
    const d = new Date(ts);
    return d.toISOString().slice(11, 23); // HH:MM:SS.mmm
  } catch {
    return ts;
  }
}

const EVENT_COLORS: Record<string, string> = {
  status: '#58a6ff',
  progress: '#3fb950',
  data: '#d2a8ff',
  error: '#f85149',
  stopped: '#d29922',
};

function badgeColor(event: string): string {
  return EVENT_COLORS[event] ?? '#8b949e';
}

function entryDetail(entry: LiveLogEntry): string {
  switch (entry.event) {
    case 'status':
      return `${entry.state ?? ''} ${entry.message ?? ''}`.trim();
    case 'progress': {
      const node = entry.node_id ?? '';
      const state = entry.state ?? '';
      const pct = entry.progress != null ? ` ${entry.progress}%` : '';
      const text = entry.text ? ` ${entry.text}` : '';
      return `${node} ${state}${pct}${text}`.trim();
    }
    case 'data':
      return `${entry.node_id ?? 'result'} [${(entry.keys as string[])?.join(', ') ?? ''}]`;
    case 'error':
      return `${entry.message ?? ''}`;
    case 'stopped':
      return `${entry.message ?? ''}`;
    default:
      return JSON.stringify(entry);
  }
}

function LogEntry({ entry }: { entry: LiveLogEntry }) {
  return (
    <div className="sosa-log-entry">
      <span className="sosa-log-time">{formatTime(entry.ts)}</span>
      <span className="sosa-log-badge" style={{ background: badgeColor(entry.event) }}>
        {entry.event}
      </span>
      <span className="sosa-log-detail">{entryDetail(entry)}</span>
    </div>
  );
}

function LiveTab() {
  const entries = useLogStore((s) => s.liveEntries);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [entries.length]);

  return (
    <div className="sosa-log-entries" ref={scrollRef}>
      {entries.length === 0 && (
        <div className="sosa-log-empty">No live entries yet. Execute a graph to see logs.</div>
      )}
      {entries.map((e, i) => (
        <LogEntry key={i} entry={e} />
      ))}
    </div>
  );
}

function HistoryTab() {
  const logFiles = useLogStore((s) => s.logFiles);
  const selectedFile = useLogStore((s) => s.selectedFile);
  const selectedFileEntries = useLogStore((s) => s.selectedFileEntries);
  const setLogFiles = useLogStore((s) => s.setLogFiles);
  const setSelectedFile = useLogStore((s) => s.setSelectedFile);

  useEffect(() => {
    fetchLogList().then(setLogFiles).catch(console.error);
  }, [setLogFiles]);

  const handleSelectFile = async (filename: string) => {
    try {
      const entries = await fetchLogFile(filename);
      setSelectedFile(filename, entries as LiveLogEntry[]);
    } catch (err) {
      console.error('Failed to load log file:', err);
    }
  };

  if (selectedFile) {
    return (
      <div className="sosa-log-history-viewer">
        <button className="sosa-log-back" onClick={() => setSelectedFile(null)}>
          &larr; Back
        </button>
        <div className="sosa-log-filename">{selectedFile}</div>
        <div className="sosa-log-entries">
          {selectedFileEntries.map((e, i) => (
            <LogEntry key={i} entry={e} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="sosa-log-file-list">
      {logFiles.length === 0 && (
        <div className="sosa-log-empty">No log files found.</div>
      )}
      {logFiles.map((file) => (
        <div key={file} className="sosa-log-file-item" onClick={() => handleSelectFile(file)}>
          {file}
        </div>
      ))}
    </div>
  );
}

export function LogPanel() {
  const isOpen = useLogStore((s) => s.isOpen);
  const activeTab = useLogStore((s) => s.activeTab);
  const setActiveTab = useLogStore((s) => s.setActiveTab);

  if (!isOpen) return null;

  return (
    <div className="sosa-log-panel">
      <div className="sosa-log-header">
        <button
          className={`sosa-log-tab ${activeTab === 'live' ? 'active' : ''}`}
          onClick={() => setActiveTab('live')}
        >
          Live
        </button>
        <button
          className={`sosa-log-tab ${activeTab === 'history' ? 'active' : ''}`}
          onClick={() => setActiveTab('history')}
        >
          History
        </button>
      </div>
      {activeTab === 'live' ? <LiveTab /> : <HistoryTab />}
    </div>
  );
}
