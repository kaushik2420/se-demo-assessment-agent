// Tiny fetch wrapper with bearer-token auth.
// In production, swap localStorage for httpOnly cookies + refresh-token flow.

const BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

function token(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("se_coach_token");
}

export function setToken(t: string) {
  window.localStorage.setItem("se_coach_token", t);
}

export function clearToken() {
  window.localStorage.removeItem("se_coach_token");
}

export async function api<T = unknown>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const headers = new Headers(init.headers);
  const t = token();
  if (t) headers.set("Authorization", `Bearer ${t}`);
  if (init.body && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");

  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (res.status === 401) {
    clearToken();
    if (typeof window !== "undefined") {
      // Preserve where the user was so login can bounce them back instead of
      // dumping them at /dashboard and losing their context.
      const here = window.location.pathname + window.location.search;
      const next = here && here !== "/login" ? `?next=${encodeURIComponent(here)}` : "";
      // Avoid an infinite redirect loop if we're ALREADY on /login
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = `/login${next}`;
      }
    }
    throw new Error("Unauthorized");
  }
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

export async function login(email: string, password: string) {
  const body = new FormData();
  body.append("username", email);
  body.append("password", password);
  const res = await fetch(`${BASE}/auth/login`, { method: "POST", body });
  if (!res.ok) throw new Error("Invalid credentials");
  const data = await res.json();
  setToken(data.access_token);
  return data;
}
