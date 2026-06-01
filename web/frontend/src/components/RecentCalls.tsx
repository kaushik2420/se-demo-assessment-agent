"use client";
import { useState } from "react";
import Link from "next/link";

type Call = {
  call_id: string;
  prospect: string;
  type: string;
  score: number | null;
  cx_maturity: string | null;
  duration_min?: number | null;
  date: string;
  se_name?: string | null;  // shown on the manager view (when showSE=true)
};

const PAGE_SIZE = 15;

/** CX maturity color mapping — directly tied to maturity tiers */
function maturityClasses(level: string | null): string {
  if (!level) return "bg-slate-100 text-slate-500";
  const v = level.toLowerCase();
  if (v.startsWith("form")) return "bg-slate-100 text-slate-700";
  if (v.startsWith("low")) return "bg-amber-100 text-amber-800";
  if (v.startsWith("potential")) return "bg-sky-100 text-sky-800";
  if (v.startsWith("high")) return "bg-emerald-100 text-emerald-800";
  return "bg-slate-100 text-slate-600";
}

function maturityShortLabel(level: string | null): string {
  if (!level) return "—";
  if (level.toLowerCase().startsWith("form")) return "Form / Basic";
  if (level.toLowerCase().startsWith("low")) return "Low Maturity";
  if (level.toLowerCase().startsWith("potential")) return "Potential High";
  if (level.toLowerCase().startsWith("high")) return "High Maturity";
  return level;
}

function scoreColor(score: number | null): string {
  if (score == null) return "text-ss-navy-soft";
  if (score >= 3.9) return "text-emerald-600";
  if (score >= 3.4) return "text-ss-navy";
  if (score >= 2.8) return "text-amber-700";
  return "text-red-600";
}

export function RecentCalls({
  calls,
  showSE = false,
  title = "Recent calls",
  emptyMessage = "No calls yet — upload your first transcript above.",
}: {
  calls: Call[];
  /** Show "SE" column/badge — turn on for manager / cross-team views */
  showSE?: boolean;
  title?: string;
  emptyMessage?: string;
}) {
  const [view, setView] = useState<"card" | "table">("card");
  const [page, setPage] = useState(1);

  const totalPages = Math.max(1, Math.ceil(calls.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const pageCalls = calls.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  if (!calls || calls.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-ss-cyan-soft p-6">
        <h2 className="font-semibold text-ss-navy mb-2">{title}</h2>
        <p className="text-ss-navy-soft italic">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-ss-cyan-soft p-6">
      <div className="flex justify-between items-center mb-4">
        <div>
          <h2 className="font-semibold text-ss-navy">{title}</h2>
          <p className="text-xs text-ss-navy-soft mt-0.5">
            {calls.length} total · showing {pageCalls.length} of {calls.length}
          </p>
        </div>
        {/* View toggle */}
        <div className="flex bg-ss-cream rounded-lg p-1">
          <button onClick={() => setView("card")}
            className={`px-3 py-1 text-xs font-medium rounded transition ${
              view === "card" ? "bg-white text-ss-navy shadow-sm" : "text-ss-navy-soft hover:text-ss-navy"
            }`}>▦ Cards</button>
          <button onClick={() => setView("table")}
            className={`px-3 py-1 text-xs font-medium rounded transition ${
              view === "table" ? "bg-white text-ss-navy shadow-sm" : "text-ss-navy-soft hover:text-ss-navy"
            }`}>☰ Table</button>
        </div>
      </div>

      {view === "card" ? (
        <div className="grid grid-cols-3 gap-3">
          {pageCalls.map((c) => (
            <Link key={c.call_id} href={`/call/${c.call_id}`}
              className="border border-ss-cyan-soft rounded-lg p-4 hover:border-ss-teal hover:shadow-sm transition group">
              <div className="flex justify-between items-start mb-2">
                <div className="font-semibold text-ss-navy group-hover:text-ss-teal-deep transition truncate flex-1 min-w-0">
                  {c.prospect}
                </div>
                <div className={`font-bold text-lg ml-2 flex-shrink-0 ${scoreColor(c.score)}`}>
                  {c.score?.toFixed(2) ?? "—"}
                </div>
              </div>
              <div className="text-xs text-ss-navy-soft mb-3">
                {showSE && c.se_name ? <><span className="font-semibold text-ss-navy">{c.se_name}</span> · </> : null}
                {c.date}{c.duration_min ? ` · ${c.duration_min} min` : ""}
              </div>
              <div className="flex gap-1.5 flex-wrap">
                <span className="px-2 py-0.5 bg-ss-cyan-soft text-ss-navy text-[10px] font-semibold rounded uppercase tracking-wide">
                  {c.type.replace("_", " ")}
                </span>
                <span className={`px-2 py-0.5 text-[10px] font-semibold rounded uppercase tracking-wide ${maturityClasses(c.cx_maturity)}`}>
                  {maturityShortLabel(c.cx_maturity)}
                </span>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <div className="overflow-hidden border border-ss-cyan-soft rounded-lg">
          <table className="w-full text-sm">
            <thead className="bg-ss-cream text-xs font-semibold text-ss-navy-soft uppercase tracking-wider">
              <tr>
                {showSE && <th className="text-left px-3 py-2.5">SE</th>}
                <th className="text-left px-3 py-2.5">Prospect</th>
                <th className="text-left px-3 py-2.5">Date</th>
                <th className="text-left px-3 py-2.5">Type</th>
                <th className="text-left px-3 py-2.5">CX Maturity</th>
                <th className="text-right px-3 py-2.5">Score</th>
              </tr>
            </thead>
            <tbody>
              {pageCalls.map((c) => (
                <tr key={c.call_id}
                  className="border-t border-ss-cyan-soft hover:bg-ss-cream transition cursor-pointer"
                  onClick={() => window.location.href = `/call/${c.call_id}`}>
                  {showSE && <td className="px-3 py-2.5 text-ss-navy whitespace-nowrap">{c.se_name || "—"}</td>}
                  <td className="px-3 py-2.5 font-medium text-ss-navy">{c.prospect}</td>
                  <td className="px-3 py-2.5 text-xs text-ss-navy-soft whitespace-nowrap">{c.date}</td>
                  <td className="px-3 py-2.5">
                    <span className="px-2 py-0.5 bg-ss-cyan-soft text-ss-navy text-[10px] font-semibold rounded uppercase tracking-wide">
                      {c.type.replace("_", " ")}
                    </span>
                  </td>
                  <td className="px-3 py-2.5">
                    <span className={`px-2 py-0.5 text-[10px] font-semibold rounded uppercase tracking-wide ${maturityClasses(c.cx_maturity)}`}>
                      {maturityShortLabel(c.cx_maturity)}
                    </span>
                  </td>
                  <td className={`px-3 py-2.5 text-right font-semibold ${scoreColor(c.score)}`}>
                    {c.score?.toFixed(2) ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="mt-4 flex justify-between items-center text-sm">
          <div className="text-ss-navy-soft text-xs">
            Page {safePage} of {totalPages}
          </div>
          <div className="flex gap-2">
            <button
              disabled={safePage <= 1}
              onClick={() => setPage(safePage - 1)}
              className="px-3 py-1.5 border border-ss-cyan-soft text-ss-navy rounded hover:bg-ss-cream transition disabled:opacity-40 disabled:cursor-not-allowed text-xs font-medium">
              ← Prev
            </button>
            <button
              disabled={safePage >= totalPages}
              onClick={() => setPage(safePage + 1)}
              className="px-3 py-1.5 border border-ss-cyan-soft text-ss-navy rounded hover:bg-ss-cream transition disabled:opacity-40 disabled:cursor-not-allowed text-xs font-medium">
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
