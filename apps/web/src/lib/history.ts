export interface HistoryEntry {
  job_id: string;
  timestamp: string;
  decision: string;
  thumbnail_url: string | null;
}

const KEY = "loopsight_history";

export function loadHistory(): HistoryEntry[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed;
  } catch {
    return [];
  }
}

export function saveToHistory(entry: HistoryEntry) {
  if (typeof window === "undefined") return;
  try {
    const current = loadHistory();
    // De-duplicate by job_id, newest first
    const filtered = current.filter((h) => h.job_id !== entry.job_id);
    const next = [entry, ...filtered].slice(0, 20);
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // quota exceeded — ignore
  }
}

export function clearHistory() {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(KEY);
  } catch {}
}
