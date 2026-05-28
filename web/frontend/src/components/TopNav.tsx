"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, clearToken } from "@/lib/api";
import { Logo } from "@/components/Logo";

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
    { href: "/manager",   label: "Manager",      roles: ["manager", "admin"] },
    { href: "/executive", label: "Executive",    roles: ["ceo", "manager", "admin"] },
  ].filter((t) => t.roles.includes(me.role));

  return (
    <nav className="h-16 bg-white border-b border-ss-cyan-soft flex items-center px-6 justify-between">
      <div className="flex items-center gap-4">
        <Link href="/dashboard" className="flex items-center"><Logo /></Link>
        <div className="flex bg-ss-cream p-1 rounded-lg ml-6 gap-1">
          {tabs.map((t) => (
            <Link key={t.href} href={t.href}
                  className={`px-3 py-1.5 rounded text-sm font-medium transition
                    ${pathname === t.href
                      ? "bg-white text-ss-navy shadow-sm"
                      : "text-ss-navy-soft hover:text-ss-navy"}`}>
              {t.label}
            </Link>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-3">
        <Link href="/upload"
              className="px-4 py-2 border border-ss-navy text-ss-navy rounded-lg text-sm font-medium hover:bg-ss-cyan-soft transition">
          + Upload transcript
        </Link>
        <button onClick={() => { clearToken(); router.push("/login"); }}
                className="text-sm text-ss-navy-soft hover:text-ss-navy transition">
          Sign out
        </button>
        <div
          className="w-9 h-9 rounded-full text-white grid place-items-center font-semibold text-sm"
          style={{ background: "linear-gradient(135deg,#5CCDED 0%, #253043 100%)" }}
          title={me.name}
        >
          {me.name.split(" ").map((p) => p[0]).slice(0, 2).join("")}
        </div>
      </div>
    </nav>
  );
}
