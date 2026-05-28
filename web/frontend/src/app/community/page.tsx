"use client";
import useSWR from "swr";
import { api } from "@/lib/api";
import { TopNav } from "@/components/TopNav";

const fetcher = (url: string) => api(url);

function fmt(d: string | null): string {
  if (!d) return "Recurring";
  try {
    return new Date(d).toLocaleDateString(undefined, {
      weekday: "short", month: "short", day: "numeric", year: "numeric",
    });
  } catch {
    return d;
  }
}

export default function CommunityPage() {
  const { data, error, isLoading, mutate } = useSWR<any>("/events", fetcher, {
    revalidateOnFocus: false,
    refreshInterval: 6 * 60 * 60 * 1000,
  });

  return (
    <>
      <TopNav />
      <main className="max-w-5xl mx-auto p-10">
        <div className="flex justify-between items-end mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-ss-navy">Community & Events</h1>
            <p className="text-ss-navy-soft mt-1">
              Upcoming events, podcasts, and articles from the wider SE / PreSales community.
              Auto-refreshed every 6 hours.
            </p>
          </div>
          <button
            onClick={() => mutate(api("/events?refresh=true"))}
            className="px-4 py-2 border border-ss-cyan-soft text-ss-navy rounded-lg text-sm font-medium hover:bg-ss-cream transition"
          >
            ↻ Refresh now
          </button>
        </div>

        {isLoading && (
          <p className="text-ss-navy-soft py-12 text-center">Loading events…</p>
        )}
        {error && (
          <p className="text-red-600 py-12 text-center">Couldn't load events: {String(error)}</p>
        )}

        {data && (
          <>
            <div className="grid grid-cols-3 gap-3 mb-6">
              <Stat label="Live events" value={data.live_count} />
              <Stat label="Curated baseline" value={data.curated_count} />
              <Stat label="Cache TTL" value={`${data.cache_ttl_hours}h`} />
            </div>

            <div className="bg-white border border-ss-cyan-soft rounded-xl divide-y divide-ss-cyan-soft">
              {data.events.length === 0 && (
                <p className="p-8 text-center text-ss-navy-soft italic">
                  No events found right now. Try the refresh button or check back later.
                </p>
              )}
              {data.events.map((e: any, i: number) => (
                <a
                  key={`${e.url}-${i}`}
                  href={e.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block p-5 hover:bg-ss-cream transition group first:rounded-t-xl last:rounded-b-xl"
                >
                  <div className="flex justify-between items-start gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="inline-flex px-2 py-0.5 bg-ss-teal-soft text-ss-teal-deep text-xs font-semibold rounded uppercase">
                          {e.source}
                        </span>
                        <span className="text-xs text-ss-navy-soft">{fmt(e.date)}</span>
                      </div>
                      <div className="font-semibold text-ss-navy group-hover:text-ss-teal-deep transition">
                        {e.title}
                      </div>
                      {e.description && (
                        <div className="text-sm text-ss-navy-soft mt-2 line-clamp-2">
                          {e.description.replace(/<[^>]+>/g, "")}
                        </div>
                      )}
                    </div>
                    <span className="text-ss-teal-deep opacity-0 group-hover:opacity-100 transition text-lg">→</span>
                  </div>
                </a>
              ))}
            </div>

            <div className="mt-6 text-xs text-ss-navy-soft">
              <strong>Sources:</strong>{" "}
              {data.sources.map((s: any) => s.name).join(" · ")} ·{" "}
              <em>Last refreshed {new Date(data.fetched_at).toLocaleString()}</em>
            </div>
          </>
        )}
      </main>
    </>
  );
}

function Stat({ label, value }: { label: string; value: any }) {
  return (
    <div className="bg-white border border-ss-cyan-soft rounded-xl p-4">
      <div className="text-xs font-semibold text-ss-navy-soft uppercase tracking-wider mb-1">{label}</div>
      <div className="text-2xl font-bold text-ss-navy">{value}</div>
    </div>
  );
}
