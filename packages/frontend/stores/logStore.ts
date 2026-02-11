// stores/logStore.ts
// Zustand store for log panel state — separate from graphStore to keep concerns isolated.

import { create } from 'zustand';

export interface LiveLogEntry {
  ts: string;
  event: string;
  [key: string]: unknown;
}

type ActiveTab = 'live' | 'history';

interface LogStore {
  isOpen: boolean;
  activeTab: ActiveTab;

  // Live execution entries
  liveEntries: LiveLogEntry[];

  // History (saved log files)
  logFiles: string[];
  selectedFile: string | null;
  selectedFileEntries: LiveLogEntry[];

  togglePanel: () => void;
  setActiveTab: (tab: ActiveTab) => void;
  addLiveEntry: (data: Record<string, unknown>) => void;
  clearLiveEntries: () => void;
  setLogFiles: (files: string[]) => void;
  setSelectedFile: (file: string | null, entries?: LiveLogEntry[]) => void;
}

const LOGGED_EVENTS = new Set(['progress', 'status', 'error', 'data', 'stopped']);

export const useLogStore = create<LogStore>((set) => ({
  isOpen: false,
  activeTab: 'live',
  liveEntries: [],
  logFiles: [],
  selectedFile: null,
  selectedFileEntries: [],

  togglePanel: () => set((s) => ({ isOpen: !s.isOpen })),

  setActiveTab: (tab) => set({ activeTab: tab }),

  addLiveEntry: (data) => {
    const eventType = data.type as string | undefined;
    if (!eventType || !LOGGED_EVENTS.has(eventType)) return;

    const entry: LiveLogEntry = {
      ts: new Date().toISOString(),
      event: eventType,
      ...data,
    };
    set((s) => ({ liveEntries: [...s.liveEntries, entry] }));
  },

  clearLiveEntries: () => set({ liveEntries: [] }),

  setLogFiles: (files) => set({ logFiles: files }),

  setSelectedFile: (file, entries) =>
    set({
      selectedFile: file,
      selectedFileEntries: entries ?? [],
    }),
}));
