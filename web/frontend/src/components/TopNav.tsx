"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, clearToken } from "@/lib/api";

export function TopNav() {
  const router = useRouter();
  const pathname = usePathname();
  const [me, setMe] = useState<{ name: string; role: string; email: string } | null>(null);

  useEffect(() => {
    api<typeof me>("/auth/me").then(setMe).catch(() => router.replace("/login"));
  }, [router]);

  if (!me) return null;

  const tabs = [
    { href: "/dashboard", label: "My Dashboard", roles: ["se", "manager", "ceo", "admin"] },
    { href: "/manager", label: "Manager", roles: ["manager", "admin"] },
    { href: "/executive", label: "Executive", roles: ["ceo", "manager", "admin"] },
  ].filter((t) => t.roles.includes(me.role));

  return (
    <nav className="h-16 bg-white border-b border-slate-200 flex items-center px-6 justify-between">
      <div className="flex items-center gap-4">
        <Link href="/dashboard" className="flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-600 rounded-lg grid place-items-center text-white font-bold">S</div>
          <div>
            <div className="font-semibold text-sm leading-tight">SE Coach</div>
            <div className="text-xs text-slate-500 leading-tight">SurveySparrow</div>
          </div>
        </Link>
        <div className="flex bg-slate-100 p-1 rounded-lg ml-6 gap-1">
          {tabs.map((t) => (
            <Link key={t.href} href={t.href}
                  className={`px-3 py-1.5 rounded text-sm font-medium transition
                    ${pathname === t.href ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900"}`}>
              {t.label}
            </Link>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-3">
        <Link href="/upload" className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium hover:bg-slate-50">
          + Upload transcript
        </Link>
        <button onClick={() => { clearToken(); router.push("/login"); }}
                className="text-sm text-slate-500 hover:text-slate-900">
          Sign out
        </button>
        <div className="w-9 h-9 rounded-full bg-gradient-to-br from-blue-500 to-blue-800 text-white grid place-items-center font-semibold text-sm">
          {me.name.split(" ").map((p) => p[0]).slice(0, 2).join("")}
        </div>
      </div>
    </nav>
  );
}
