"use client";
import { useEffect, useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";
import { TopNav } from "@/components/TopNav";
import { TrackerReextractCard } from "@/components/TrackerReextractCard";

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
  product: string | null;
  kind: string | null;
  l2_url: string | null;
  jira_url: string | null;
  last_synced_at: string | null;
  last_updated_at: string;
  days_stale: number;
  created_at: string;
};

type SEOption = { id: number; name: string; email: string };
type Me = { email: string; role: string; name: string };

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

function productClass(p: string | null): string {
  if (!p) return "bg-slate-100 text-slate-600";
  const t = p.toLowerCase();
  if (t.includes("thrive")) return "bg-violet-100 text-violet-800";
  if (t.includes("desk")) return "bg-orange-100 text-orange-800";
  if (t.includes("survey")) return "bg-teal-100 text-teal-800";
  return "bg-slate-100 text-slate-600";
}

function kindClass(k: string | null): string {
  if (!k) return "bg-slate-100 text-slate-600";
  if (k === "issue")       return "bg-rose-100 text-rose-800";
  if (k === "enhancement") return "bg-violet-100 text-violet-800";
  return "bg-sky-100 text-sky-800";  // request
}

export default function TrackerPage() {
  const { data: me } = useSWR<Me>("/auth/me", fetcher);
  const { data: items, error, isLoading, mutate } = useSWR<Item[]>("/tracker", fetcher);
  const [selected, setSelected] = useState<Item | null>(null);
  const [filter, setFilter] = useState<"all" | "open" | "stale">("all");

  // Keep drawer in sync if list refreshes after an edit
  useEffect(() => {
    if (!selected || !items) return;
    const fresh = items.find((i) => i.id === selected.id);
    if (fresh && fresh !== selected) setSelected(fresh);
  }, [items]);  // eslint-disable-line react-hooks/exhaustive-deps

  if (isLoading) return (<><TopNav /><div className="p-10 text-ss-navy-soft">Loading tracker…</div></>);
  if (error) return (<><TopNav /><div className="p-10 text-red-600">Failed: {String(error)}</div></>);

  const filtered = (items || []).filter((i) => {
    if (filter === "open") return i.status === "open";
    if (filter === "stale") return i.days_stale >= 15;
    return true;
  });

  async function downloadCsv() {
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

  const canEdit = me?.role === "admin" || me?.role === "manager";

  return (
    <>
      <TopNav />
      <main className="max-w-[1400px] mx-auto p-10">
        <div className="flex justify-between items-end mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-ss-navy">Request Tracker</h1>
            <p className="text-ss-navy-soft mt-1">
              Auto-populated by @SE Coach mentions in Slack. Everyone sees every record.
              {canEdit && <> Admins and managers can edit any row.</>}
            </p>
          </div>
          <button onClick={downloadCsv}
            className="px-4 py-2 bg-ss-navy text-white rounded-lg font-semibold text-sm hover:bg-ss-navy-dark transition">
            ⤓ Export CSV
          </button>
        </div>

        {me?.role === "admin" && <TrackerReextractCard />}

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
                <th className="text-left px-3 py-3">Requested</th>
                <th className="text-left px-3 py-3">ETA</th>
                <th className="text-left px-3 py-3">SE</th>
                <th className="text-left px-3 py-3">Engineer</th>
                <th className="text-left px-3 py-3">Product</th>
                <th className="text-left px-3 py-3">Kind</th>
                <th className="text-left px-3 py-3">Details</th>
                <th className="text-left px-3 py-3">L2</th>
                <th className="text-left px-3 py-3">Jira</th>
                <th className="text-left px-3 py-3">Stale</th>
                <th className="text-left px-3 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr><td colSpan={11} className="p-8 text-center text-ss-navy-soft italic">
                  No tracker items yet. Tag @SE Coach in any Slack thread to start logging requests.
                </td></tr>
              )}
              {filtered.map((i) => (
                <tr key={i.id} onClick={() => setSelected(i)}
                  className="border-t border-ss-cyan-soft hover:bg-ss-cream cursor-pointer">
                  <td className="px-3 py-3 text-xs text-ss-navy whitespace-nowrap">{fmtDate(i.requested_date)}</td>
                  <td className="px-3 py-3 text-xs text-ss-navy whitespace-nowrap">{fmtDate(i.eta)}</td>
                  <td className="px-3 py-3 text-ss-navy whitespace-nowrap">{i.se_name || "—"}</td>
                  <td className="px-3 py-3 text-ss-navy whitespace-nowrap">{i.engineer_name || "—"}</td>
                  <td className="px-3 py-3">
                    {i.product ? (
                      <span className={`px-2 py-0.5 text-[10px] font-semibold rounded uppercase tracking-wide ${productClass(i.product)}`}>
                        {i.product}
                      </span>
                    ) : <span className="text-ss-navy-soft text-xs">—</span>}
                  </td>
                  <td className="px-3 py-3">
                    {i.kind ? (
                      <span className={`px-2 py-0.5 text-[10px] font-semibold rounded uppercase tracking-wide ${kindClass(i.kind)}`}>
                        {i.kind}
                      </span>
                    ) : <span className="text-ss-navy-soft text-xs">—</span>}
                  </td>
                  <td className="px-3 py-3 text-ss-navy max-w-xs truncate" title={i.details || ""}>{i.details || "—"}</td>
                  <td className="px-3 py-3 text-xs">
                    {i.l2_url ? <a href={i.l2_url} target="_blank" rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="text-ss-teal-deep hover:underline">L2 ↗</a> : <span className="text-ss-navy-soft">—</span>}
                  </td>
                  <td className="px-3 py-3 text-xs">
                    {i.jira_url ? <a href={i.jira_url} target="_blank" rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="text-ss-teal-deep hover:underline">Jira ↗</a> : <span className="text-ss-navy-soft">—</span>}
                  </td>
                  <td className="px-3 py-3"><span className={`px-2 py-0.5 text-[10px] font-semibold rounded uppercase tracking-wide ${staleClass(i.days_stale)}`}>
                    {i.days_stale}d
                  </span></td>
                  <td className="px-3 py-3 text-ss-teal-deep text-xs whitespace-nowrap">View →</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>

      {selected && (
        <DetailDrawer
          item={selected}
          canEdit={canEdit}
          onClose={() => setSelected(null)}
          onSaved={(updated) => { setSelected(updated); mutate(); }}
          onDeleted={() => { setSelected(null); mutate(); }}
        />
      )}
    </>
  );
}

function DetailDrawer({
  item, canEdit, onClose, onSaved, onDeleted,
}: {
  item: Item;
  canEdit: boolean;
  onClose: () => void;
  onSaved: (updated: Item) => void;
  onDeleted: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    if (!confirm(`Delete tracker item #${item.id} (${(item.details || "no details").slice(0, 80)})? This cannot be undone.`)) return;
    setDeleting(true);
    try {
      await api(`/tracker/${item.id}`, { method: "DELETE" });
      onDeleted();
    } catch (e: any) {
      alert(`Delete failed: ${e?.message || e}`);
      setDeleting(false);
    }
  }

  return (
    <>
      <div onClick={onClose}
           className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-40" />
      <aside className="fixed top-0 right-0 z-50 h-full w-full max-w-[640px] bg-white shadow-2xl overflow-y-auto">
        <div className="sticky top-0 z-10 bg-white border-b border-ss-cyan-soft p-6 flex justify-between items-start">
          <div>
            <h2 className="text-lg font-semibold text-ss-navy">Tracker item #{item.id}</h2>
            <p className="text-xs text-ss-navy-soft mt-1">
              {item.channel_name && `#${item.channel_name} · `}
              Last updated {fmtDate(item.last_updated_at)} ({item.days_stale}d ago)
              {item.last_synced_at && ` · last synced ${fmtDate(item.last_synced_at)}`}
            </p>
          </div>
          <div className="flex gap-2 items-center">
            {canEdit && !editing && (
              <>
                <button onClick={() => setEditing(true)}
                  className="px-3 py-1.5 bg-ss-cream border border-ss-cyan-soft text-ss-navy rounded font-semibold text-xs hover:bg-ss-cyan-soft transition">
                  ✎ Edit
                </button>
                <button onClick={handleDelete} disabled={deleting}
                  className="px-3 py-1.5 text-xs font-semibold text-red-700 hover:text-white hover:bg-red-600 border border-red-200 hover:border-red-600 rounded transition disabled:opacity-50">
                  {deleting ? "Deleting…" : "🗑 Delete"}
                </button>
              </>
            )}
            <button onClick={onClose}
              className="text-ss-navy-soft hover:text-ss-navy text-xl leading-none">✕</button>
          </div>
        </div>
        {editing ? (
          <EditForm
            item={item}
            onCancel={() => setEditing(false)}
            onSaved={(updated) => { setEditing(false); onSaved(updated); }}
          />
        ) : (
          <ViewBody item={item} />
        )}
      </aside>
    </>
  );
}

function ViewBody({ item }: { item: Item }) {
  return (
    <div className="p-6 space-y-4 text-sm">
      <DetailRow label="Details" value={item.details} />
      <div className="grid grid-cols-2 gap-4">
        <DetailRow label="Requested date" value={fmtDate(item.requested_date)} />
        <DetailRow label="ETA" value={fmtDate(item.eta)} />
        <DetailRow label="SE (owner)" value={item.se_name} />
        <DetailRow label="Engineer / PM" value={item.engineer_name} />
        <DetailRow label="Product" value={item.product || "—"} />
        <DetailRow label="Kind" value={item.kind || "—"} />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-xs font-semibold text-ss-navy-soft uppercase tracking-wider mb-1">L2 ticket</div>
          {item.l2_url
            ? <a href={item.l2_url} target="_blank" rel="noopener noreferrer"
                 className="text-ss-teal-deep hover:underline text-sm break-all">{item.l2_url}</a>
            : <div className="text-ss-navy">—</div>}
        </div>
        <div>
          <div className="text-xs font-semibold text-ss-navy-soft uppercase tracking-wider mb-1">Jira</div>
          {item.jira_url
            ? <a href={item.jira_url} target="_blank" rel="noopener noreferrer"
                 className="text-ss-teal-deep hover:underline text-sm break-all">{item.jira_url}</a>
            : <div className="text-ss-navy">—</div>}
        </div>
      </div>
      <DetailRow label="Status" value={item.status} />
      <div>
        <div className="text-xs font-semibold text-ss-navy-soft uppercase tracking-wider mb-1">Comment log</div>
        <pre className="text-xs whitespace-pre-wrap text-ss-navy bg-ss-cream rounded p-3 border border-ss-cyan-soft max-h-[300px] overflow-y-auto">
          {item.comments || "(no comments)"}
        </pre>
      </div>
      {item.slack_url && (
        <a href={item.slack_url} target="_blank" rel="noopener noreferrer"
          className="inline-block px-4 py-2 bg-ss-navy text-white rounded-lg font-semibold text-sm hover:bg-ss-navy-dark transition">
          Open in Slack ↗
        </a>
      )}
    </div>
  );
}

function EditForm({
  item, onCancel, onSaved,
}: {
  item: Item;
  onCancel: () => void;
  onSaved: (updated: Item) => void;
}) {
  const { data: ses } = useSWR<SEOption[]>("/tracker/ses", fetcher);
  const [form, setForm] = useState({
    se_email: item.se_email || "",
    engineer_name: item.engineer_name || "",
    details: item.details || "",
    status: item.status,
    product: item.product || "",
    kind: item.kind || "",
    l2_url: item.l2_url || "",
    jira_url: item.jira_url || "",
    requested_date: item.requested_date ? item.requested_date.slice(0, 10) : "",
    eta: item.eta ? item.eta.slice(0, 10) : "",
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setErr(null);
    try {
      const updated = await api<Item>(`/tracker/${item.id}`, {
        method: "PATCH",
        body: JSON.stringify(form),
      });
      onSaved(updated);
    } catch (e: any) {
      const msg = String(e?.message || e);
      const match = msg.match(/\{.*\}/);
      if (match) { try { setErr(JSON.parse(match[0]).detail); return; } catch {} }
      setErr(msg);
    } finally { setSaving(false); }
  }

  function set<K extends keyof typeof form>(k: K, v: (typeof form)[K]) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  return (
    <form onSubmit={save} className="p-6 space-y-4 text-sm">
      <div>
        <Label>Details</Label>
        <textarea value={form.details} onChange={(e) => set("details", e.target.value)}
          rows={3} className="w-full px-3 py-2 border border-ss-cyan-soft rounded outline-none focus:ring-2 focus:ring-ss-teal" />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label>SE (owner)</Label>
          <select value={form.se_email} onChange={(e) => set("se_email", e.target.value)}
            className="w-full px-3 py-2 border border-ss-cyan-soft rounded bg-white outline-none focus:ring-2 focus:ring-ss-teal">
            <option value="">— Unassigned —</option>
            {(ses || []).map((s) => (
              <option key={s.id} value={s.email}>{s.name} ({s.email})</option>
            ))}
            {/* Preserve current value if it's not an SE-role user (e.g. manager) */}
            {item.se_email && !(ses || []).some((s) => s.email === item.se_email) && (
              <option value={item.se_email}>{item.se_name || item.se_email} — current (non-SE role)</option>
            )}
          </select>
        </div>
        <div>
          <Label>Engineer / PM</Label>
          <input value={form.engineer_name} onChange={(e) => set("engineer_name", e.target.value)}
            className="w-full px-3 py-2 border border-ss-cyan-soft rounded outline-none focus:ring-2 focus:ring-ss-teal" />
        </div>
      </div>
      <div className="grid grid-cols-3 gap-4">
        <div>
          <Label>Product</Label>
          <select value={form.product} onChange={(e) => set("product", e.target.value)}
            className="w-full px-3 py-2 border border-ss-cyan-soft rounded bg-white outline-none focus:ring-2 focus:ring-ss-teal">
            <option value="">— Unknown —</option>
            <option value="SurveySparrow">SurveySparrow</option>
            <option value="ThriveSparrow">ThriveSparrow</option>
            <option value="SparrowDesk">SparrowDesk</option>
          </select>
        </div>
        <div>
          <Label>Kind</Label>
          <select value={form.kind} onChange={(e) => set("kind", e.target.value)}
            className="w-full px-3 py-2 border border-ss-cyan-soft rounded bg-white outline-none focus:ring-2 focus:ring-ss-teal">
            <option value="">— Unknown —</option>
            <option value="issue">Issue (bug / broken)</option>
            <option value="request">Request (net-new functionality)</option>
            <option value="enhancement">Enhancement (improvement to existing)</option>
          </select>
        </div>
        <div>
          <Label>Status</Label>
          <select value={form.status} onChange={(e) => set("status", e.target.value)}
            className="w-full px-3 py-2 border border-ss-cyan-soft rounded bg-white outline-none focus:ring-2 focus:ring-ss-teal">
            <option value="open">Open</option>
            <option value="closed">Closed</option>
          </select>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label>Requested date</Label>
          <input type="date" value={form.requested_date} onChange={(e) => set("requested_date", e.target.value)}
            className="w-full px-3 py-2 border border-ss-cyan-soft rounded outline-none focus:ring-2 focus:ring-ss-teal" />
        </div>
        <div>
          <Label>ETA</Label>
          <input type="date" value={form.eta} onChange={(e) => set("eta", e.target.value)}
            className="w-full px-3 py-2 border border-ss-cyan-soft rounded outline-none focus:ring-2 focus:ring-ss-teal" />
        </div>
      </div>
      <div>
        <Label>L2 ticket URL</Label>
        <input value={form.l2_url} onChange={(e) => set("l2_url", e.target.value)}
          placeholder="https://surveysparrow.zendesk.com/agent/tickets/12345"
          className="w-full px-3 py-2 border border-ss-cyan-soft rounded outline-none focus:ring-2 focus:ring-ss-teal" />
      </div>
      <div>
        <Label>Jira URL</Label>
        <input value={form.jira_url} onChange={(e) => set("jira_url", e.target.value)}
          placeholder="https://surveysparrow.atlassian.net/browse/PROJ-123"
          className="w-full px-3 py-2 border border-ss-cyan-soft rounded outline-none focus:ring-2 focus:ring-ss-teal" />
      </div>
      {err && (
        <div className="px-3 py-2 bg-red-50 border border-red-200 rounded text-red-800 text-xs">{err}</div>
      )}
      <div className="flex justify-end gap-3 pt-2">
        <button type="button" onClick={onCancel}
          className="px-4 py-2 border border-ss-cyan-soft text-ss-navy rounded hover:bg-ss-cream transition text-sm">
          Cancel
        </button>
        <button type="submit" disabled={saving}
          className="px-4 py-2 bg-ss-navy text-white rounded font-semibold text-sm hover:bg-ss-navy-dark disabled:opacity-50 transition">
          {saving ? "Saving…" : "Save changes"}
        </button>
      </div>
    </form>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <label className="block text-xs font-semibold text-ss-navy-soft uppercase tracking-wider mb-1.5">
      {children}
    </label>
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
