"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [pwd, setPwd] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErr(null);
    try {
      await login(email, pwd);
      router.replace("/dashboard");
    } catch {
      setErr("Invalid email or password.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 to-blue-800">
      <form onSubmit={onSubmit} className="bg-white p-10 rounded-2xl shadow-xl w-[420px]">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-9 h-9 bg-blue-600 rounded-lg grid place-items-center text-white font-bold">S</div>
          <div>
            <div className="font-semibold">SurveySparrow SE Coach</div>
            <div className="text-xs text-slate-500">Demo performance & coaching portal</div>
          </div>
        </div>
        <h1 className="text-2xl font-semibold mb-1">Sign in</h1>
        <p className="text-slate-500 text-sm mb-6">Use your SurveySparrow work email.</p>
        <label className="text-xs font-medium text-slate-500 uppercase tracking-wider">Email</label>
        <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
               className="w-full mt-1.5 mb-4 px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-200 focus:border-blue-600 outline-none" />
        <label className="text-xs font-medium text-slate-500 uppercase tracking-wider">Password</label>
        <input type="password" required value={pwd} onChange={(e) => setPwd(e.target.value)}
               className="w-full mt-1.5 mb-2 px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-200 focus:border-blue-600 outline-none" />
        {err && <div className="text-red-600 text-sm mt-2">{err}</div>}
        <button disabled={loading} className="w-full mt-4 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50">
          {loading ? "Signing in…" : "Sign in"}
        </button>
        <div className="text-center text-xs text-slate-400 mt-6">
          Trouble logging in? Contact kaushikn2416@gmail.com
        </div>
      </form>
    </div>
  );
}
