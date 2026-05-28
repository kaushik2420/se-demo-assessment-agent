"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";
import { Logo } from "@/components/Logo";

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
    <div
      className="min-h-screen flex items-center justify-center"
      style={{
        background:
          "radial-gradient(circle at 20% 20%, #5CCDED 0%, transparent 40%)," +
          "radial-gradient(circle at 80% 80%, #2DC1E4 0%, transparent 50%)," +
          "linear-gradient(135deg,#253043 0%, #1A2433 50%, #0F1623 100%)",
      }}
    >
      <form
        onSubmit={onSubmit}
        className="bg-white p-10 rounded-2xl shadow-2xl w-[440px]"
      >
        <div className="mb-8"><Logo variant="login" /></div>

        <h1 className="text-2xl font-semibold text-ss-navy mb-1">Sign in</h1>
        <p className="text-ss-navy-soft text-sm mb-6">
          Use your <span className="font-medium">@surveysparrow.com</span> work email.
        </p>

        <label className="text-xs font-medium text-ss-navy-soft uppercase tracking-wider">
          Email
        </label>
        <input
          type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
          className="w-full mt-1.5 mb-4 px-4 py-3 border border-ss-cyan-soft rounded-lg
                     focus:ring-2 focus:ring-ss-cyan focus:border-ss-cyan-deep outline-none transition"
          placeholder="you@surveysparrow.com"
        />

        <label className="text-xs font-medium text-ss-navy-soft uppercase tracking-wider">
          Password
        </label>
        <input
          type="password" required value={pwd} onChange={(e) => setPwd(e.target.value)}
          className="w-full mt-1.5 mb-2 px-4 py-3 border border-ss-cyan-soft rounded-lg
                     focus:ring-2 focus:ring-ss-cyan focus:border-ss-cyan-deep outline-none transition"
        />

        {err && <div className="text-red-600 text-sm mt-2">{err}</div>}

        <button
          disabled={loading}
          className="w-full mt-4 py-3 bg-ss-navy text-white font-semibold rounded-lg
                     hover:bg-ss-navy-dark transition disabled:opacity-50"
        >
          {loading ? "Signing in…" : "Sign in"}
        </button>

        <div className="text-center text-xs text-ss-navy-soft mt-6">
          Trouble logging in? Contact{" "}
          <a className="text-ss-cyan-deep font-medium"
             href="mailto:kaushik.natarajan@surveysparrow.com">
            kaushik
          </a>
        </div>
      </form>
    </div>
  );
}
