// services/LogService.ts
// API wrappers for fetching execution log files from the server.

export async function fetchLogList(): Promise<string[]> {
  const res = await fetch('/api/v1/logs');
  if (!res.ok) throw new Error(`Failed to fetch log list: ${res.status}`);
  const data = await res.json();
  return data.files;
}

export async function fetchLogFile(filename: string): Promise<Record<string, unknown>[]> {
  const res = await fetch(`/api/v1/logs/${encodeURIComponent(filename)}`);
  if (!res.ok) throw new Error(`Failed to fetch log file: ${res.status}`);
  const data = await res.json();
  return data.entries;
}
