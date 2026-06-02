"use client";
import { useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";

const fetcher = (url: string): Promise<any> => api(url);

type Status = {
  in_progress: boolean;
  last_result: {
    started_at?: string;
    finished_at?: string;
    mode?: string;
    candidates?: number;
    reextracted?: number;
    skipped_already_complete?: number;
    skipped_thread_gone?: number;
    failed?: number;
    fields_backfilled?: Record<string, number>;
    errors?: string[];
  } | null;
};

export function TrackerReextractCard() {
  const { data, mutate } = useSWR<Status>("/tracker/reextract/status", fetcher, {
    refreshInterval: (d) => (d?.in_progress ? 4000 : 0),
  });
  const [starting, setStarting] = useState(false);
  const [mode, setMode] = useState<"outdated" | "all">("outdated");

  async function start() {
    const msg = mode === "all"
      ? "Re-extract EVERY tracker row (slower, costs more Claude API). Continue?"
      : "Re-extract rows missing product/kind (the new v2 fields). Continue?";
    if (!confirm(msg)) return;
    setStarting(true);
    try {
      await api<any>(`/tracker/reextract?mode=${mode}`, { method: "POST" });
      setTimeout(() => mutate(), 1000);
    } catch (e: any) {
      alert(`Failed: ${e?.message || e}`);
    } finally { setStarting(false); }
  }

  const lr = data?.last_result;
  const running = data?.in_progress;

  return (
    <div className="bg-white border border-ss-cyan-soft rounded-xl p-5 mb-6">
      <div className="flex justify-between items-start gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <h2 className="font-semibold text-ss-navy">Re-extract existing tracker rows</h2>
            <span className={`px-2 py-0.5 text-[10px] font-semibold rounded uppercase tracking-wide ${
              running ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-800"
            }`}>{running ? "Running…" : "Idle"}</span>
          </div>
          <p className="text-xs text-ss-navy-soft">
            Re-fetches the original Slack thread for each row and runs the v2 extraction
            (product, kind, L2/Jira URLs, first-poster SE attribution).
            Backfill-only — any manual edits you've made are preserved.
          </p>
        </div>
        <div className="flex gap-2 items-center flex-shrink-0">
          <select value={mode} onChange={(e) => setMode(e.target.value as any)}
            disabled={running}
            className="text-xs border border-ss-cyan-soft rounded px-2 py-1.5 bg-white disabled:opacity-50">
            <option value="outdated">Outdated (recommended)</option>
            <option value="all">All rows</option>
          </select>
          <button onClick={start} disabled={running || starting}
            className="px-4 py-1.5 bg-ss-navy text-white rounded text-sm font-semibold hover:bg-ss-navy-dark disabled:opacity-50 disabled:cursor-not-allowed">
            {running ? "Running…" : starting ? "Starting…" : "Re-extract"}
          </button>
        </div>
      </div>

      {lr && (
        <div className="mt-3 text-xs text-ss-navy-soft bg-ss-cream rounded p-3 border border-ss-cyan-soft">
          <div className="font-semibold text-ss-navy mb-1">
            Last run · {lr.mode} · {lr.finished_at ? new Date(lr.finished_at).toLocaleString() : "in progress…"}
          </div>
          <div>
            <span className="font-semibold">{lr.reextracted ?? 0}</span> re-extracted
            {" · "}<span>{lr.skipped_already_complete ?? 0} already complete</span>
            {" · "}<span>{lr.skipped_thread_gone ?? 0} thread gone</span>
            {" · "}<span className={lr.failed ? "text-red-700 font-semibold" : ""}>{lr.failed ?? 0} failed</span>
            {" / "}{lr.candidates ?? 0} candidates
          </div>
          {lr.fields_backfilled && Object.values(lr.fields_backfilled).some((n) => n > 0) && (
            <div className="mt-1.5">
              <span className="font-semibold text-ss-navy">Backfilled fields:</span>{" "}
              {Object.entries(lr.fields_backfilled)
                .filter(([, n]) => n > 0)
                .map(([k, n]) => `${k}: ${n}`)
                .join(" · ")}
            </div>
          )}
          {lr.errors && lr.errors.length > 0 && (
            <details className="mt-2 cursor-pointer">
              <summary className="font-semibold text-red-700">
                {lr.errors.length} error{lr.errors.length === 1 ? "" : "s"}
              </summary>
              <ul className="mt-1.5 ml-4 space-y-0.5">
                {lr.errors.slice(0, 20).map((e, i) => (
                  <li key={i} className="text-red-800">• {e}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
