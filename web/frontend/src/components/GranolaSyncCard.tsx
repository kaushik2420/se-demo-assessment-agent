"use client";
import { useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";

const fetcher = (url: string): Promise<any> => api(url);

type Status = {
  last_sync_at: string;
  minutes_since_last_sync: number;
  configured: boolean;
  internal_domain: string;
  folder_filter: string | null;
};

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

function fmtAgo(min: number): string {
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

export function GranolaSyncCard() {
  const { data: status, mutate: refreshStatus, isLoading } =
    useSWR<Status>("/team/granola/status", fetcher, { refreshInterval: 60_000 });

  const [syncing, setSyncing] = useState(false);
  const [lastResult, setLastResult] = useState<SyncResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function runSync() {
    setSyncing(true);
    setErr(null);
    try {
      const r = await api<SyncResult>("/team/granola/sync", { method: "POST" });
      setLastResult(r);
      refreshStatus();
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setSyncing(false);
    }
  }

  if (isLoading) return (
    <div className="bg-white border border-ss-cyan-soft rounded-xl p-6">
      <p className="text-ss-navy-soft text-sm">Loading Granola status…</p>
    </div>
  );

  if (!status) return null;

  const tealOk = status.configured;

  return (
    <div className="bg-white border border-ss-cyan-soft rounded-xl p-6">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h2 className="font-semibold text-ss-navy flex items-center gap-2">
            Granola auto-sync
            <span className={`px-2 py-0.5 text-[10px] font-semibold rounded uppercase tracking-wide ${
              tealOk ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"
            }`}>
              {tealOk ? "Configured" : "Not configured"}
            </span>
          </h2>
          <p className="text-xs text-ss-navy-soft mt-1">
            {tealOk
              ? "Pulls workspace notes every 30 min · runs scoring automatically"
              : "Set GRANOLA_API_KEY in Render env to enable"}
          </p>
        </div>
        <button
          onClick={runSync}
          disabled={syncing || !tealOk}
          className="px-4 py-2 bg-ss-navy text-white rounded-lg font-semibold text-sm hover:bg-ss-navy-dark transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2">
          {syncing ? (<><span className="inline-block w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin"></span> Syncing…</>) : "↻ Sync now"}
        </button>
      </div>

      <div className="grid grid-cols-3 gap-3 text-sm">
        <Mini label="Last sync" value={fmtAgo(status.minutes_since_last_sync)} />
        <Mini label="Folder filter" value={status.folder_filter || "(all folders)"} />
        <Mini label="Internal domain" value={status.internal_domain} />
      </div>

      {err && (
        <div className="mt-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-800">
          Sync failed: {err}
        </div>
      )}

      {lastResult && (
        <div className="mt-4 p-4 bg-ss-cream rounded-lg">
          <div className="flex justify-between items-start mb-2">
            <div className="font-semibold text-ss-navy text-sm">Last sync result</div>
            <button onClick={() => setLastResult(null)}
              className="text-ss-navy-soft hover:text-ss-navy text-xs">✕</button>
          </div>
          <div className="grid grid-cols-3 gap-x-4 gap-y-1 text-xs text-ss-navy">
            <KV label="Notes seen" v={lastResult.notes_seen} />
            <KV label="Imported" v={lastResult.imported} highlight={lastResult.imported > 0} />
            <KV label="Already imported" v={lastResult.skipped_already_imported} />
            <KV label="Wrong folder" v={lastResult.skipped_folder_filter} />
            <KV label="Internal-only" v={lastResult.skipped_external_filter} />
            <KV label="Unknown SE" v={lastResult.skipped_unknown_se} warn={lastResult.skipped_unknown_se > 0} />
            <KV label="No transcript" v={lastResult.skipped_no_transcript} />
            <KV label="Analysis failed" v={lastResult.analysis_failed} warn={lastResult.analysis_failed > 0} />
            <KV label="Errors" v={lastResult.errors.length} warn={lastResult.errors.length > 0} />
          </div>
          {lastResult.errors.length > 0 && (
            <details className="mt-3 text-xs">
              <summary className="cursor-pointer text-ss-navy-soft hover:text-ss-navy">
                Error details ({lastResult.errors.length})
              </summary>
              <ul className="mt-2 space-y-1 font-mono text-red-700 max-h-32 overflow-y-auto">
                {lastResult.errors.map((e, i) => <li key={i}>• {e}</li>)}
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
