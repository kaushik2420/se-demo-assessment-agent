"use client";
import useSWR from "swr";
import { api } from "@/lib/api";

const fetcher = (url: string) => api(url);

function fmt(d: string | null): string {
  if (!d) return "Recurring";
  try {
    return new Date(d).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return d;
  }
}

export function EventsFeed() {
  const { data, error, isLoading, mutate } = useSWR<any>("/events", fetcher, {
    revalidateOnFocus: false,
    refreshInterval: 6 * 60 * 60 * 1000, // 6h client-side too
  });

  return (
    <div className="bg-white border border-ss-cyan-soft rounded-xl p-6">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="font-semibold text-ss-navy">Community events & content</h3>
          <p className="text-xs text-ss-navy-soft mt-1">
            Auto-fetched from PreSales Collective and similar public sources.
          </p>
        </div>
        <button
          onClick={() => mutate(api("/events?refresh=true"))}
          className="text-xs text-ss-teal hover:text-ss-teal-deep font-medium"
        >
          ↻ Refresh
        </button>
      </div>

      {isLoading && <p className="text-sm text-ss-navy-soft">Loading…</p>}
      {error && <p className="text-sm text-red-600">Couldn't load events: {String(error)}</p>}

      {data && (
        <>
          <ul className="divide-y divide-ss-cyan-soft">
            {data.events.slice(0, 8).map((e: any, i: number) => (
              <li key={`${e.url}-${i}`} className="py-3 first:pt-0 last:pb-0">
                <a
                  href={e.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block group"
                >
                  <div className="flex justify-between gap-3 items-start">
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-ss-navy group-hover:text-ss-teal-deep transition truncate">
                        {e.title}
                      </div>
                      <div className="text-xs text-ss-navy-soft mt-0.5">
                        <span className="font-medium">{e.source}</span> · {fmt(e.date)}
                      </div>
                      {e.description && (
                        <div className="text-xs text-ss-navy-soft mt-1 line-clamp-2">
                          {e.description.replace(/<[^>]+>/g, "")}
                        </div>
                      )}
                    </div>
                    <span className="text-ss-teal-deep flex-shrink-0 opacity-0 group-hover:opacity-100 transition">→</span>
                  </div>
                </a>
              </li>
            ))}
          </ul>
          <div className="mt-4 pt-3 border-t border-ss-cyan-soft text-xs text-ss-navy-soft flex justify-between items-center">
            <span>
              {data.live_count} live · {data.curated_count} curated · cached {data.cache_ttl_hours}h
            </span>
            <span>
              {data.fetched_at && `Updated ${new Date(data.fetched_at).toLocaleTimeString()}`}
            </span>
          </div>
        </>
      )}
    </div>
  );
}
