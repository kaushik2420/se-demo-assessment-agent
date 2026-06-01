"use client";
import { useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";
import { TopNav } from "@/components/TopNav";
import { GranolaSyncCard } from "@/components/GranolaSyncCard";
import { ReanalyzeCard } from "@/components/ReanalyzeCard";

type User = {
  id: number;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
  created_at: string;
};

type Me = { email: string; role: string; name: string };

const fetcher = (url: string): Promise<any> => api(url);

const ROLE_BADGES: Record<string, string> = {
  admin: "bg-purple-100 text-purple-800",
  manager: "bg-blue-100 text-blue-800",
  ceo: "bg-amber-100 text-amber-800",
  se: "bg-slate-100 text-slate-700",
};

export default function TeamPage() {
  const { data: me } = useSWR<Me>("/auth/me", fetcher);
  const { data: users, mutate, error, isLoading } = useSWR<User[]>("/team/users", fetcher);

  const [showForm, setShowForm] = useState(false);
  const [newPassword, setNewPassword] = useState<{ pwd: string; user: User } | null>(null);

  const canCreateAnyRole = me?.role === "admin";
  const canCreate = me?.role === "admin" || me?.role === "manager";

  // Loading & access guard
  if (!me) return (<><TopNav /><div className="p-10 text-ss-navy-soft">Loading…</div></>);
  if (!canCreate) return (
    <><TopNav />
      <div className="max-w-3xl mx-auto p-10">
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-6 text-amber-900">
          You don't have permission to manage team members. This page is for admins and managers only.
        </div>
      </div>
    </>
  );

  return (
    <>
      <TopNav />
      <main className="max-w-5xl mx-auto p-10">
        <div className="flex justify-between items-end mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-ss-navy">Team management</h1>
            <p className="text-ss-navy-soft mt-1">
              Add new SEs, managers, and admins to the SE Coach portal.
            </p>
          </div>
          {!showForm && (
            <button onClick={() => setShowForm(true)}
              className="px-5 py-2.5 bg-ss-navy text-white rounded-lg font-semibold hover:bg-ss-navy-dark transition">
              + Add team member
            </button>
          )}
        </div>

        {/* One-time password — must be shown immediately after creation */}
        {newPassword && (
          <div className="mb-6 bg-emerald-50 border-2 border-emerald-300 rounded-xl p-6">
            <div className="flex justify-between items-start mb-3">
              <div>
                <div className="text-xs font-bold text-emerald-900 uppercase tracking-wider mb-1">
                  ✓ Created — share this password securely
                </div>
                <div className="text-xl font-bold text-emerald-900">{newPassword.user.name}</div>
                <div className="text-sm text-emerald-800">{newPassword.user.email}</div>
              </div>
              <button onClick={() => setNewPassword(null)}
                className="text-emerald-700 hover:text-emerald-900 text-2xl leading-none">✕</button>
            </div>
            <div className="bg-white rounded-lg p-4 flex justify-between items-center gap-3 border border-emerald-200">
              <code className="font-mono text-lg text-ss-navy select-all">{newPassword.pwd}</code>
              <button
                onClick={() => { navigator.clipboard.writeText(newPassword.pwd); }}
                className="px-4 py-2 bg-emerald-600 text-white rounded font-semibold text-sm hover:bg-emerald-700 transition flex-shrink-0">
                Copy password
              </button>
            </div>
            <p className="text-xs text-emerald-900 mt-3">
              <strong>You can't see this password again.</strong> Copy it now and DM it to {newPassword.user.name.split(" ")[0]}
              {" "}via Slack DM (not channel) or 1Password. They should change it on first login.
            </p>
          </div>
        )}

        {/* Create form */}
        {showForm && (
          <CreateUserForm
            canCreateAnyRole={canCreateAnyRole}
            onCancel={() => setShowForm(false)}
            onCreated={(created, pwd) => {
              setShowForm(false);
              setNewPassword({ pwd, user: created });
              mutate();   // refresh list
            }}
          />
        )}

        {/* Granola sync controls */}
        <div className="mb-6">
          <GranolaSyncCard />
        </div>

        {/* Re-analyze under current prompts — admin only */}
        {me?.role === "admin" && (
          <div className="mb-6">
            <ReanalyzeCard />
          </div>
        )}

        {/* Existing users */}
        <div className="bg-white border border-ss-cyan-soft rounded-xl overflow-hidden mt-2">
          <div className="px-6 py-4 border-b border-ss-cyan-soft flex justify-between items-center">
            <h2 className="font-semibold text-ss-navy">All team members</h2>
            <span className="text-xs text-ss-navy-soft">{users?.length ?? 0} total</span>
          </div>
          {isLoading && <div className="p-6 text-ss-navy-soft">Loading users…</div>}
          {error && <div className="p-6 text-red-600">Failed to load users.</div>}
          {users && (
            <table className="w-full text-sm">
              <thead className="bg-ss-cream text-xs font-semibold text-ss-navy-soft uppercase tracking-wider">
                <tr>
                  <th className="text-left px-6 py-3">Name</th>
                  <th className="text-left px-6 py-3">Email</th>
                  <th className="text-left px-6 py-3">Role</th>
                  <th className="text-left px-6 py-3">Created</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-t border-ss-cyan-soft">
                    <td className="px-6 py-3 font-medium text-ss-navy">{u.name}</td>
                    <td className="px-6 py-3 text-ss-navy">{u.email}</td>
                    <td className="px-6 py-3">
                      <span className={`px-2 py-0.5 text-[10px] font-semibold rounded uppercase tracking-wide ${ROLE_BADGES[u.role] ?? "bg-slate-100"}`}>
                        {u.role}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-xs text-ss-navy-soft">
                      {new Date(u.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </main>
    </>
  );
}

function CreateUserForm({
  canCreateAnyRole, onCancel, onCreated,
}: {
  canCreateAnyRole: boolean;
  onCancel: () => void;
  onCreated: (user: User, pwd: string) => void;
}) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<"se" | "manager" | "ceo" | "admin">("se");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setErr(null);
    try {
      const res = await api<any>("/team/users", {
        method: "POST",
        body: JSON.stringify({ email: email.trim(), name: name.trim(), role }),
      });
      onCreated(
        { id: res.id, email: res.email, name: res.name, role: res.role,
          is_active: true, created_at: res.created_at },
        res.one_time_password
      );
    } catch (e: any) {
      const msg = String(e?.message || e);
      // Try to parse JSON error from FastAPI
      const match = msg.match(/\{.*\}/);
      if (match) {
        try { setErr(JSON.parse(match[0]).detail); return; } catch {}
      }
      setErr(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} className="bg-white border border-ss-cyan-soft rounded-xl p-6 mb-6">
      <h2 className="font-semibold text-ss-navy mb-4">Add team member</h2>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <label className="block text-xs font-semibold text-ss-navy-soft uppercase tracking-wider mb-1.5">
            Full name
          </label>
          <input required value={name} onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Parul Gajaraj"
            className="w-full px-4 py-2.5 border border-ss-cyan-soft rounded-lg outline-none focus:ring-2 focus:ring-ss-teal focus:border-ss-teal-deep transition" />
        </div>
        <div>
          <label className="block text-xs font-semibold text-ss-navy-soft uppercase tracking-wider mb-1.5">
            Work email
          </label>
          <input required type="email" value={email} onChange={(e) => setEmail(e.target.value)}
            placeholder="parul.gajaraj@surveysparrow.com"
            className="w-full px-4 py-2.5 border border-ss-cyan-soft rounded-lg outline-none focus:ring-2 focus:ring-ss-teal focus:border-ss-teal-deep transition" />
        </div>
      </div>

      <div className="mb-5">
        <label className="block text-xs font-semibold text-ss-navy-soft uppercase tracking-wider mb-1.5">
          Role
        </label>
        <select value={role} onChange={(e) => setRole(e.target.value as any)}
          className="w-full px-4 py-2.5 border border-ss-cyan-soft rounded-lg outline-none focus:ring-2 focus:ring-ss-teal focus:border-ss-teal-deep transition bg-white">
          <option value="se">SE — Solution Engineer (own dashboard only)</option>
          {canCreateAnyRole && (
            <>
              <option value="manager">Manager — sees team leaderboard + DOTM</option>
              <option value="ceo">CEO — sees executive summary</option>
              <option value="admin">Admin — full access incl. user management</option>
            </>
          )}
        </select>
        {!canCreateAnyRole && (
          <p className="text-xs text-ss-navy-soft mt-1.5 italic">
            Managers can only create SE accounts. Ask an admin to onboard a manager / CEO / admin.
          </p>
        )}
      </div>

      {err && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-800">
          {err}
        </div>
      )}

      <div className="flex justify-end gap-3">
        <button type="button" onClick={onCancel}
          className="px-5 py-2.5 border border-ss-cyan-soft text-ss-navy rounded-lg hover:bg-ss-cream transition">
          Cancel
        </button>
        <button type="submit" disabled={submitting || !email || !name}
          className="px-5 py-2.5 bg-ss-navy text-white rounded-lg font-semibold hover:bg-ss-navy-dark transition disabled:opacity-50 disabled:cursor-not-allowed">
          {submitting ? "Creating…" : "Create user"}
        </button>
      </div>
    </form>
  );
}
