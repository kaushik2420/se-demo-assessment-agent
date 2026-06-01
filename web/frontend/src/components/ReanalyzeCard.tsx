"use client";
import { useEffect, useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";

const fetcher = (url: string): Promise<any> => api(url);

type Status = {
  in_progress: boolean;
  current_scoring_version: string;
  current_insights_version: string;
  last_result: {
    started_at?: string;
    finished_at?: string;
    mode?: string;
    candidates?: number;
    reanalyzed?: number;
    skipped_up_to_date?: number;
    skipped_no_transcript?: number;
    failed?: number;
    errors?: string[];
  } | null;
};

export function ReanalyzeCard() {
  const { data, mutate } = useSWR<Status>("/team/reanalyze/status", fetcher, {
    refreshInterval: (d) => (d?.in_progress ? 5000 : 0),  // poll while running
  });
  const [starting, setStarting] = useState(false);
  const [mode, setMode] = useState<"outdated" | "all">("outdated");

  // Re-poll on demand when starting
  useEffect(() => { if (starting) mutate(); }, [starting, mutate]);

  async function start() {
    if (!confirm(
      mode === "all"
        ? "Re-analyze EVERY call (incl. ones already on the current prompts). This costs Claude API spend. Continue?"
        : "Re-analyze all calls that are on an older prompt version. Continue?"
    )) return;
    setStarting(true);
    try {
      await api<any>(`/team/reanalyze?mode=${mode}`, { method: "POST" });
      setTimeout(() => mutate(), 1000);
    } catch (e: any) {
      alert(`Failed to start: ${e?.message || e}`);
    } finally {
      setStarting(false);
    }
  }

  const lr = data?.last_result;
  const running = data?.in_progress;

  return (
    <div className="bg-white border border-ss-cyan-soft rounded-xl p-6">
      <div className="flex justify-between items-start mb-3">
        <div>
          <h2 className="font-semibold text-ss-navy">Re-analyze calls under current prompts</h2>
          <p className="text-xs text-ss-navy-soft mt-1">
            Current scoring prompt: <span className="font-mono text-ss-navy">{data?.current_scoring_version || "—"}</span>
            {" · "}insights: <span className="font-mono text-ss-navy">{data?.current_insights_version || "—"}</span>
          </p>
        </div>
        <span className={`px-2 py-0.5 text-[10px] font-semibold rounded uppercase tracking-wide ${
          running ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-800"
        }`}>{running ? "Running…" : "Idle"}</span>
      </div>

      <div className="flex gap-2 items-center mb-3">
        <select value={mode} onChange={(e) => setMode(e.target.value as any)}
          disabled={running}
          className="text-xs border border-ss-cyan-soft rounded px-2 py-1.5 bg-white disabled:opacity-50">
          <option value="outdated">Outdated only (recommended)</option>
          <option value="all">All calls (forces re-run)</option>
        </select>
        <button onClick={start} disabled={running || starting}
          className="px-4 py-1.5 bg-ss-navy text-white rounded text-sm font-semibold hover:bg-ss-navy-dark disabled:opacity-50 disabled:cursor-not-allowed">
          {running ? "Running…" : starting ? "Starting…" : "Re-analyze now"}
        </button>
      </div>

      {lr && (
        <div className="text-xs text-ss-navy-soft bg-ss-cream rounded p-3 border border-ss-cyan-soft">
          <div className="font-semibold text-ss-navy mb-1">
            Last run · {lr.mode} · {lr.finished_at ? new Date(lr.finished_at).toLocaleString() : "in progress…"}
          </div>
          <div>
            <span className="font-semibold">{lr.reanalyzed ?? 0}</span> re-analyzed
            {" · "}<span>{lr.skipped_up_to_date ?? 0} up-to-date</span>
            {" · "}<span>{lr.skipped_no_transcript ?? 0} no-transcript</span>
            {" · "}<span className={lr.failed ? "text-red-700 font-semibold" : ""}>{lr.failed ?? 0} failed</span>
            {" / "}{lr.candidates ?? 0} candidates
          </div>
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
