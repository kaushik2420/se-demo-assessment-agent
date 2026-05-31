"use client";
import { useEffect, useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";

const fetcher = (url: string): Promise<any> => api(url);

type SyncResult = {
  started_at: string;
  finished_at?: string;
  since: string;
  notes_seen: number;
  imported: number;
  skipped_folder_filter: number;
  skipped_external_filter: number;
  skipped_already_imported: number;
  skipped_unknown_se: number;
  skipped_no_transcript: number;
  analysis_failed: number;
  errors: string[];
};

type Status = {
  last_sync_at: string;
  minutes_since_last_sync: number;
  configured: boolean;
  internal_domain: string;
  folder_filter: string | null;
  in_progress: boolean;
  last_result: SyncResult | null;
};

function fmtAgo(min: number): string {
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function GranolaSyncCard() {
  // Poll every 5s while a sync is in progress; otherwise every 60s
  const [pollFast, setPollFast] = useState(false);
  const { data: status, mutate: refreshStatus, isLoading } =
    useSWR<Status>("/team/granola/status", fetcher, {
      refreshInterval: pollFast ? 5_000 : 60_000,
    });

  const [triggering, setTriggering] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [justFinishedAt, setJustFinishedAt] = useState<string | null>(null);

  // Watch for in_progress edge: when it goes from true → false, capture the finish
  useEffect(() => {
    if (!status) return;
    if (status.in_progress) {
      setPollFast(true);
    } else if (pollFast) {
      setPollFast(false);
      if (status.last_result?.finished_at) {
        setJustFinishedAt(status.last_result.finished_at);
      }
    }
  }, [status, pollFast]);

  async function trigger() {
    setTriggering(true);
    setErr(null);
    try {
      await api<{ status: string; message: string }>("/team/granola/sync", { method: "POST" });
      setPollFast(true);
      refreshStatus();
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setTriggering(false);
    }
  }

  if (isLoading) return (
    <div className="bg-white border border-ss-cyan-soft rounded-xl p-6">
      <p className="text-ss-navy-soft text-sm">Loading Granola status…</p>
    </div>
  );
  if (!status) return null;

  const tealOk = status.configured;
  const running = status.in_progress;
  const result = status.last_result;

  return (
    <div className="bg-white border border-ss-cyan-soft rounded-xl p-6">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h2 className="font-semibold text-ss-navy flex items-center gap-2">
            Granola auto-sync
            <span className={`px-2 py-0.5 text-[10px] font-semibold rounded uppercase tracking-wide ${
              !tealOk ? "bg-amber-100 text-amber-800"
              : running ? "bg-blue-100 text-blue-800"
              : "bg-emerald-100 text-emerald-800"
            }`}>
              {!tealOk ? "Not configured" : running ? "Running…" : "Configured"}
            </span>
          </h2>
          <p className="text-xs text-ss-navy-soft mt-1">
            {!tealOk
              ? "Set GRANOLA_API_KEY in Render env to enable"
              : running
                ? "Sync in progress — this can take several minutes for a large backlog. Stay on this page or come back later."
                : "Pulls workspace notes every 30 min · runs scoring automatically"}
          </p>
        </div>
        <button
          onClick={trigger}
          disabled={triggering || running || !tealOk}
          className="px-4 py-2 bg-ss-navy text-white rounded-lg font-semibold text-sm hover:bg-ss-navy-dark transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2">
          {triggering || running ? (
            <>
              <span className="inline-block w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
              {triggering ? "Starting…" : "Syncing…"}
            </>
          ) : "↻ Sync now"}
        </button>
      </div>

      <div className="grid grid-cols-3 gap-3 text-sm mb-4">
        <Mini label="Last sync" value={fmtAgo(status.minutes_since_last_sync)} />
        <Mini label="Folder filter" value={status.folder_filter || "(all folders)"} />
        <Mini label="Internal domain" value={status.internal_domain} />
      </div>

      {err && (
        <div className="px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-800">
          Failed to start sync: {err}
        </div>
      )}

      {running && (
        <div className="px-4 py-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-900 flex gap-2 items-start">
          <span className="inline-block w-3 h-3 border-2 border-blue-400/40 border-t-blue-700 rounded-full animate-spin mt-0.5"></span>
          <div>
            <strong>Sync running in background.</strong> Each call takes ~10-20 seconds to score
            with Claude. We'll show the results here as soon as it finishes — page auto-refreshes
            every 5 seconds while running. Safe to navigate away; sync continues server-side.
          </div>
        </div>
      )}

      {result && !running && (
        <div className="p-4 bg-ss-cream rounded-lg">
          <div className="flex justify-between items-start mb-2">
            <div className="font-semibold text-ss-navy text-sm">
              {justFinishedAt === result.finished_at ? "✓ Just completed" : "Last sync result"}
              {result.finished_at && (
                <span className="ml-2 text-xs font-normal text-ss-navy-soft">
                  · {new Date(result.finished_at).toLocaleString()}
                </span>
              )}
            </div>
          </div>
          <div className="grid grid-cols-3 gap-x-4 gap-y-1 text-xs text-ss-navy">
            <KV label="Notes seen" v={result.notes_seen} />
            <KV label="Imported" v={result.imported} highlight={result.imported > 0} />
            <KV label="Already imported" v={result.skipped_already_imported} />
            <KV label="Wrong folder" v={result.skipped_folder_filter} />
            <KV label="Internal-only" v={result.skipped_external_filter} />
            <KV label="Unknown SE" v={result.skipped_unknown_se} warn={result.skipped_unknown_se > 0} />
            <KV label="No transcript" v={result.skipped_no_transcript} />
            <KV label="Analysis failed" v={result.analysis_failed} warn={result.analysis_failed > 0} />
            <KV label="Errors" v={result.errors.length} warn={result.errors.length > 0} />
          </div>
          {result.errors.length > 0 && (
            <details className="mt-3 text-xs">
              <summary className="cursor-pointer text-ss-navy-soft hover:text-ss-navy">
                Error details ({result.errors.length})
              </summary>
              <ul className="mt-2 space-y-1 font-mono text-red-700 max-h-40 overflow-y-auto">
                {result.errors.map((e, i) => <li key={i}>• {e}</li>)}
              </ul>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-ss-cream rounded-lg p-3">
      <div className="text-[10px] font-semibold text-ss-navy-soft uppercase tracking-wider mb-1">{label}</div>
      <div className="font-semibold text-ss-navy truncate" title={value}>{value}</div>
    </div>
  );
}

function KV({ label, v, highlight, warn }: { label: string; v: number; highlight?: boolean; warn?: boolean }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-ss-navy-soft">{label}:</span>
      <span className={`font-semibold ${
        highlight ? "text-emerald-700" : warn ? "text-red-700" : "text-ss-navy"
      }`}>{v}</span>
    </div>
  );
}
