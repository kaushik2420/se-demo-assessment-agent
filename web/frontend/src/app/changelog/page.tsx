"use client";
import { useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";
import { TopNav } from "@/components/TopNav";

type Entry = {
  id: number;
  entry_number: number;
  title: string;
  issue: string;
  rca: string;
  fix: string;
  status: string;
  entry_date: string;
  created_by: string | null;
  created_at: string;
  updated_at: string | null;
  updated_by: string | null;
};

const fetcher = (url: string): Promise<any> => api(url);
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
const STATUSES = ["shipped", "pending", "blocked", "deferred"] as const;

const STATUS_PILL: Record<string, string> = {
  shipped:  "bg-emerald-100 text-emerald-800",
  pending:  "bg-amber-100 text-amber-800",
  blocked:  "bg-red-100 text-red-800",
  deferred: "bg-slate-100 text-slate-700",
};

function fmtDate(s: string | null | undefined): string {
  if (!s) return "—";
  try { return new Date(s).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }); }
  catch { return s; }
}

export default function ChangelogPage() {
  const { data: me } = useSWR<any>("/auth/me", fetcher);
  const { data: entries, error, isLoading, mutate } = useSWR<Entry[]>("/changelog", fetcher);
  const [editing, setEditing] = useState<Entry | null>(null);
  const [adding, setAdding] = useState(false);
  const [filter, setFilter] = useState<"all" | "shipped" | "pending" | "blocked" | "deferred">("all");
  const [search, setSearch] = useState("");

  if (isLoading) return (<><TopNav /><div className="p-10 text-ss-navy-soft">Loading changelog…</div></>);
  if (error)     return (<><TopNav /><div className="p-10 text-red-600">Failed: {String(error)}</div></>);

  const canDelete = me?.role === "admin";

  const filtered = (entries || [])
    .filter(e => filter === "all" || e.status === filter)
    .filter(e => !search ||
      e.title.toLowerCase().includes(search.toLowerCase()) ||
      e.issue.toLowerCase().includes(search.toLowerCase()) ||
      e.fix.toLowerCase().includes(search.toLowerCase()));

  async function downloadMarkdown() {
    const token = window.localStorage.getItem("se_coach_token");
    const res = await fetch(`${API_BASE}/changelog/export.md`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `se-coach-changelog-${new Date().toISOString().slice(0,10)}.md`;
    document.body.appendChild(a); a.click(); a.remove();
    window.URL.revokeObjectURL(url);
  }

  async function handleDelete(id: number, num: number) {
    if (!confirm(`Delete entry #${num}? This is irreversible.`)) return;
    try {
      await api(`/changelog/${id}`, { method: "DELETE" });
      mutate();
    } catch (e: any) {
      alert(`Delete failed: ${e?.message || e}`);
    }
  }

  return (
    <>
      <TopNav />
      <main className="max-w-5xl mx-auto p-10">
        <div className="flex justify-between items-end mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-ss-navy">Post-Deployment Change Log</h1>
            <p className="text-ss-navy-soft mt-1">
              Every bug, feedback item, and fix since day-1. Source of truth lives here — download
              as markdown when you need to share.
            </p>
          </div>
          <div className="flex gap-2">
            <button onClick={downloadMarkdown}
              className="px-4 py-2 border border-ss-cyan-soft text-ss-navy rounded-lg text-sm hover:bg-ss-cream transition">
              ⤓ Download (.md)
            </button>
            <button onClick={() => setAdding(true)}
              className="px-4 py-2 bg-ss-navy text-white rounded-lg text-sm font-semibold hover:bg-ss-navy-dark transition">
              + Add entry
            </button>
          </div>
        </div>

        <div className="flex gap-3 mb-5 items-center text-sm">
          <span className="text-ss-navy-soft">Filter:</span>
          {(["all", ...STATUSES] as const).map(s => (
            <button key={s} onClick={() => setFilter(s)}
              className={`px-3 py-1 rounded-lg font-medium transition ${
                filter === s ? "bg-ss-navy text-white"
                             : "bg-white border border-ss-cyan-soft text-ss-navy hover:bg-ss-cream"
              }`}>
              {s}
            </button>
          ))}
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search title / issue / fix…"
            className="ml-auto px-3 py-1.5 border border-ss-cyan-soft rounded outline-none focus:ring-2 focus:ring-ss-teal text-sm w-64" />
          <span className="text-ss-navy-soft">{filtered.length} of {(entries || []).length}</span>
        </div>

        <div className="space-y-3">
          {filtered.length === 0 && (
            <div className="bg-white border border-ss-cyan-soft rounded-xl p-10 text-center text-ss-navy-soft italic">
              No entries match.
            </div>
          )}
          {filtered.map(e => (
            <EntryCard key={e.id} entry={e}
              canDelete={canDelete}
              onEdit={() => setEditing(e)}
              onDelete={() => handleDelete(e.id, e.entry_number)} />
          ))}
        </div>
      </main>

      {(adding || editing) && (
        <EntryFormModal
          entry={editing}
          onClose={() => { setEditing(null); setAdding(false); }}
          onSaved={() => { setEditing(null); setAdding(false); mutate(); }}
        />
      )}
    </>
  );
}

function EntryCard({ entry, canDelete, onEdit, onDelete }: {
  entry: Entry; canDelete: boolean; onEdit: () => void; onDelete: () => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="bg-white border border-ss-cyan-soft rounded-xl overflow-hidden">
      <div className="px-5 py-4 flex justify-between items-start gap-4 cursor-pointer hover:bg-ss-cream"
           onClick={() => setOpen(!open)}>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="font-mono text-xs bg-ss-cream px-2 py-0.5 rounded text-ss-navy-soft font-bold">#{entry.entry_number}</span>
            <span className={`px-2 py-0.5 text-[10px] font-semibold rounded uppercase tracking-wide ${STATUS_PILL[entry.status] || "bg-slate-100"}`}>
              {entry.status}
            </span>
            <span className="text-xs text-ss-navy-soft">{fmtDate(entry.entry_date)}</span>
          </div>
          <div className="font-semibold text-ss-navy">{entry.title}</div>
        </div>
        <div className="flex gap-1 items-center flex-shrink-0">
          <button onClick={(ev) => { ev.stopPropagation(); onEdit(); }}
            className="px-2 py-1 text-xs text-ss-navy-soft hover:text-ss-navy hover:bg-ss-cream rounded transition">
            ✎ Edit
          </button>
          {canDelete && (
            <button onClick={(ev) => { ev.stopPropagation(); onDelete(); }}
              className="px-2 py-1 text-xs text-red-600 hover:text-white hover:bg-red-600 rounded transition">
              🗑
            </button>
          )}
          <span className="text-ss-navy-soft ml-2">{open ? "▾" : "▸"}</span>
        </div>
      </div>
      {open && (
        <div className="px-5 pb-5 pt-1 border-t border-slate-100 space-y-3 text-sm">
          <Section label="Issue / Feedback" body={entry.issue} />
          <Section label="RCA" body={entry.rca} />
          <Section label="Fix" body={entry.fix} />
          <div className="text-xs text-ss-navy-soft pt-2 border-t border-slate-100">
            Created {fmtDate(entry.created_at)} {entry.created_by && `by ${entry.created_by}`}
            {entry.updated_at && ` · Updated ${fmtDate(entry.updated_at)} by ${entry.updated_by || "—"}`}
          </div>
        </div>
      )}
    </div>
  );
}

function Section({ label, body }: { label: string; body: string }) {
  return (
    <div>
      <div className="text-[11px] font-bold text-ss-navy-soft uppercase tracking-wider mb-1.5">{label}</div>
      <div className="text-ss-navy whitespace-pre-wrap leading-relaxed">{body}</div>
    </div>
  );
}

function EntryFormModal({ entry, onClose, onSaved }: {
  entry: Entry | null; onClose: () => void; onSaved: () => void;
}) {
  const isEdit = !!entry;
  const [form, setForm] = useState({
    title: entry?.title || "",
    issue: entry?.issue || "",
    rca: entry?.rca || "",
    fix: entry?.fix || "",
    status: entry?.status || "shipped",
    entry_date: entry?.entry_date ? entry.entry_date.slice(0, 10) : new Date().toISOString().slice(0, 10),
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!form.title.trim() || !form.issue.trim() || !form.rca.trim() || !form.fix.trim()) {
      setErr("Title, Issue, RCA, and Fix are all required.");
      return;
    }
    setSaving(true); setErr(null);
    try {
      if (isEdit) {
        await api(`/changelog/${entry!.id}`, { method: "PATCH", body: JSON.stringify(form) });
      } else {
        await api(`/changelog`, { method: "POST", body: JSON.stringify(form) });
      }
      onSaved();
    } catch (e: any) {
      const msg = String(e?.message || e);
      const m = msg.match(/\{.*\}/);
      if (m) { try { setErr(JSON.parse(m[0]).detail); return; } catch {} }
      setErr(msg);
    } finally {
      setSaving(false);
    }
  }

  function set<K extends keyof typeof form>(k: K, v: (typeof form)[K]) {
    setForm(f => ({ ...f, [k]: v }));
  }

  return (
    <>
      <div onClick={onClose} className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-40" />
      <div className="fixed inset-0 z-50 flex items-start justify-center pt-12 pb-12 px-4 overflow-y-auto">
        <form onSubmit={save} className="bg-white w-full max-w-3xl rounded-xl shadow-2xl">
          <div className="px-6 py-4 border-b border-ss-cyan-soft flex justify-between items-center">
            <h2 className="font-semibold text-ss-navy">
              {isEdit ? `Edit entry #${entry!.entry_number}` : "Add changelog entry"}
            </h2>
            <button type="button" onClick={onClose}
              className="text-ss-navy-soft hover:text-ss-navy text-xl leading-none">✕</button>
          </div>

          <div className="p-6 space-y-4">
            <div className="grid grid-cols-4 gap-4">
              <div className="col-span-3">
                <Label>Title</Label>
                <input value={form.title} onChange={e => set("title", e.target.value)}
                  placeholder="Short summary in problem/feature framing"
                  className={inpCls} />
              </div>
              <div>
                <Label>Date</Label>
                <input type="date" value={form.entry_date}
                  onChange={e => set("entry_date", e.target.value)} className={inpCls} />
              </div>
            </div>

            <div>
              <Label>Status</Label>
              <div className="flex gap-2">
                {STATUSES.map(s => (
                  <button key={s} type="button" onClick={() => set("status", s)}
                    className={`px-3 py-1.5 rounded text-xs font-semibold transition ${
                      form.status === s
                        ? "bg-ss-navy text-white"
                        : "bg-white border border-ss-cyan-soft text-ss-navy hover:bg-ss-cream"
                    }`}>
                    {s}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <Label>Issue / Feedback</Label>
              <textarea value={form.issue} onChange={e => set("issue", e.target.value)} rows={3}
                placeholder="What was reported, by whom, when. Paste their words if useful."
                className={inpCls} />
            </div>
            <div>
              <Label>RCA (root cause)</Label>
              <textarea value={form.rca} onChange={e => set("rca", e.target.value)} rows={3}
                placeholder="WHY the system behaved this way. Code path, prompt logic, schema gap, etc."
                className={inpCls} />
            </div>
            <div>
              <Label>Fix</Label>
              <textarea value={form.fix} onChange={e => set("fix", e.target.value)} rows={5}
                placeholder="What changed (with file paths if useful). Markdown is fine — bullet lists, code blocks, etc."
                className={inpCls} />
            </div>

            {err && (
              <div className="px-3 py-2 bg-red-50 border border-red-200 rounded text-red-800 text-xs">{err}</div>
            )}
          </div>

          <div className="px-6 py-4 border-t border-ss-cyan-soft flex justify-end gap-3">
            <button type="button" onClick={onClose}
              className="px-4 py-2 border border-ss-cyan-soft text-ss-navy rounded text-sm hover:bg-ss-cream transition">
              Cancel
            </button>
            <button type="submit" disabled={saving}
              className="px-5 py-2 bg-ss-navy text-white rounded text-sm font-semibold hover:bg-ss-navy-dark disabled:opacity-50 transition">
              {saving ? "Saving…" : (isEdit ? "Save changes" : "Create entry")}
            </button>
          </div>
        </form>
      </div>
    </>
  );
}

const inpCls = "w-full px-3 py-2 border border-ss-cyan-soft rounded outline-none focus:ring-2 focus:ring-ss-teal text-sm";
function Label({ children }: { children: React.ReactNode }) {
  return <label className="block text-[11px] font-semibold text-ss-navy-soft uppercase tracking-wider mb-1.5">{children}</label>;
}
