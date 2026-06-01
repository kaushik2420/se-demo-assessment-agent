"use client";
import { useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";
import { TopNav } from "@/components/TopNav";

type Item = {
  id: number;
  requested_date: string | null;
  eta: string | null;
  se_name: string | null;
  se_email: string | null;
  engineer_name: string | null;
  details: string | null;
  comments: string | null;
  status: string;
  slack_url: string | null;
  channel_name: string | null;
  last_updated_at: string;
  days_stale: number;
  created_at: string;
};

const fetcher = (url: string): Promise<any> => api(url);
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

function fmtDate(s: string | null): string {
  if (!s) return "—";
  try {
    return new Date(s).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  } catch { return s; }
}

function staleClass(days: number): string {
  if (days >= 15) return "bg-red-100 text-red-800";
  if (days >= 7) return "bg-amber-100 text-amber-800";
  return "bg-emerald-100 text-emerald-800";
}

export default function TrackerPage() {
  const { data: items, error, isLoading, mutate } = useSWR<Item[]>("/tracker", fetcher);
  const [selected, setSelected] = useState<Item | null>(null);
  const [filter, setFilter] = useState<"all" | "open" | "stale">("all");

  if (isLoading) return (<><TopNav /><div className="p-10 text-ss-navy-soft">Loading tracker…</div></>);
  if (error) return (<><TopNav /><div className="p-10 text-red-600">Failed: {String(error)}</div></>);

  const filtered = (items || []).filter((i) => {
    if (filter === "open") return i.status === "open";
    if (filter === "stale") return i.days_stale >= 15;
    return true;
  });

  async function downloadCsv() {
    // Use the token from localStorage; redirect bypasses our api() helper
    const token = window.localStorage.getItem("se_coach_token");
    const res = await fetch(`${API_BASE}/tracker/export.csv`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `se-coach-tracker-${new Date().toISOString().slice(0,10)}.csv`;
    document.body.appendChild(a); a.click(); a.remove();
    window.URL.revokeObjectURL(url);
  }

  return (
    <>
      <TopNav />
      <main className="max-w-7xl mx-auto p-10">
        <div className="flex justify-between items-end mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-ss-navy">Request Tracker</h1>
            <p className="text-ss-navy-soft mt-1">
              Auto-populated by @SE Coach mentions in Slack. SEs see their own; managers see all.
            </p>
          </div>
          <button onClick={downloadCsv}
            className="px-4 py-2 bg-ss-navy text-white rounded-lg font-semibold text-sm hover:bg-ss-navy-dark transition">
            ⤓ Export CSV
          </button>
        </div>

        <div className="flex gap-3 mb-4 items-center text-sm">
          <span className="text-ss-navy-soft">Filter:</span>
          {(["all", "open", "stale"] as const).map((k) => (
            <button key={k} onClick={() => setFilter(k)}
              className={`px-3 py-1 rounded-lg font-medium transition ${
                filter === k ? "bg-ss-navy text-white" : "bg-white border border-ss-cyan-soft text-ss-navy hover:bg-ss-cream"
              }`}>
              {k === "all" ? "All" : k === "open" ? "Open only" : "Stale (15d+)"}
            </button>
          ))}
          <span className="ml-auto text-ss-navy-soft">{filtered.length} of {(items || []).length}</span>
        </div>

        <div className="bg-white border border-ss-cyan-soft rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-ss-cream text-xs font-semibold text-ss-navy-soft uppercase tracking-wider">
              <tr>
                <th className="text-left px-4 py-3">Requested</th>
                <th className="text-left px-4 py-3">ETA</th>
                <th className="text-left px-4 py-3">SE</th>
                <th className="text-left px-4 py-3">Engineer</th>
                <th className="text-left px-4 py-3">Details</th>
                <th className="text-left px-4 py-3">Stale</th>
                <th className="text-left px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr><td colSpan={7} className="p-8 text-center text-ss-navy-soft italic">
                  No tracker items yet. Tag @SE Coach in any Slack thread to start logging requests.
                </td></tr>
              )}
              {filtered.map((i) => (
                <tr key={i.id} onClick={() => setSelected(i)}
                  className="border-t border-ss-cyan-soft hover:bg-ss-cream cursor-pointer">
                  <td className="px-4 py-3 text-xs text-ss-navy whitespace-nowrap">{fmtDate(i.requested_date)}</td>
                  <td className="px-4 py-3 text-xs text-ss-navy whitespace-nowrap">{fmtDate(i.eta)}</td>
                  <td className="px-4 py-3 text-ss-navy">{i.se_name || "—"}</td>
                  <td className="px-4 py-3 text-ss-navy">{i.engineer_name || "—"}</td>
                  <td className="px-4 py-3 text-ss-navy max-w-md truncate">{i.details || "—"}</td>
                  <td className="px-4 py-3"><span className={`px-2 py-0.5 text-[10px] font-semibold rounded uppercase tracking-wide ${staleClass(i.days_stale)}`}>
                    {i.days_stale}d
                  </span></td>
                  <td className="px-4 py-3 text-ss-teal-deep text-xs">View →</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>

      {/* Detail drawer */}
      {selected && (
        <>
          <div onClick={() => setSelected(null)}
               className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-40" />
          <aside className="fixed top-0 right-0 z-50 h-full w-full max-w-[560px] bg-white shadow-2xl overflow-y-auto">
            <div className="sticky top-0 z-10 bg-white border-b border-ss-cyan-soft p-6 flex justify-between items-start">
              <div>
                <h2 className="text-lg font-semibold text-ss-navy">Tracker item #{selected.id}</h2>
                <p className="text-xs text-ss-navy-soft mt-1">
                  {selected.channel_name && `#${selected.channel_name} · `}
                  Last updated {fmtDate(selected.last_updated_at)} ({selected.days_stale}d ago)
                </p>
              </div>
              <button onClick={() => setSelected(null)}
                className="text-ss-navy-soft hover:text-ss-navy text-xl">✕</button>
            </div>
            <div className="p-6 space-y-4 text-sm">
              <DetailRow label="Details" value={selected.details} />
              <DetailRow label="Requested date" value={fmtDate(selected.requested_date)} />
              <DetailRow label="ETA" value={fmtDate(selected.eta)} />
              <DetailRow label="SE" value={selected.se_name} />
              <DetailRow label="Engineer / Product person" value={selected.engineer_name} />
              <div>
                <div className="text-xs font-semibold text-ss-navy-soft uppercase tracking-wider mb-1">Comment log</div>
                <pre className="text-xs whitespace-pre-wrap text-ss-navy bg-ss-cream rounded p-3 border border-ss-cyan-soft">
                  {selected.comments || "(no comments)"}
                </pre>
              </div>
              {selected.slack_url && (
                <a href={selected.slack_url} target="_blank" rel="noopener noreferrer"
                  className="inline-block px-4 py-2 bg-ss-navy text-white rounded-lg font-semibold text-sm hover:bg-ss-navy-dark transition">
                  Open in Slack ↗
                </a>
              )}
            </div>
          </aside>
        </>
      )}
    </>
  );
}

function DetailRow({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <div className="text-xs font-semibold text-ss-navy-soft uppercase tracking-wider mb-1">{label}</div>
      <div className="text-ss-navy">{value || "—"}</div>
    </div>
  );
}
