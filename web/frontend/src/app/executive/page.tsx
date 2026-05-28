"use client";
import useSWR from "swr";
import { api } from "@/lib/api";
import { TopNav } from "@/components/TopNav";

const fetcher = (url: string) => api(url);

export default function ExecutivePage() {
  const { data, error, isLoading } = useSWR<any>("/dashboard/ceo", fetcher);
  if (isLoading) return (<><TopNav /><div className="p-10 text-ss-navy-soft">Loading…</div></>);
  if (error) return (<><TopNav /><div className="p-10 text-red-600">Failed: {String(error)}</div></>);

  return (
    <>
      <TopNav />
      <main className="max-w-7xl mx-auto p-10">
        <h1 className="text-2xl font-semibold text-ss-navy mb-1">Executive summary — {data.month}</h1>
        <p className="text-ss-navy-soft mb-6">{data.headline}</p>

        <div className="grid grid-cols-3 gap-4 mb-6">
          <Stat label="Calls analyzed" value={data.month_metrics.calls} />
          <Stat label="Feature-selling demos" value={`${Math.round(data.month_metrics.feature_selling_pct * 100)}%`} />
          <Stat label="AE interrupts / call" value={data.month_metrics.ae_interruption_avg_per_call} />
        </div>

        <div className="grid grid-cols-2 gap-6 mb-6">
          <Card title="Top product blockers">
            {data.top_product_blockers.length === 0 && <Empty />}
            {data.top_product_blockers.map((b: any, i: number) => (
              <Row key={i} title={b.feature} sub={`${b.deal_count} deal${b.deal_count !== 1 ? "s" : ""} blocked`} />
            ))}
          </Card>
          <Card title="Most-mentioned competitors">
            {data.most_mentioned_competitors.length === 0 && <Empty />}
            {data.most_mentioned_competitors.map((c: any, i: number) => (
              <Row key={i} title={c.name} sub={`${c.mentions} mentions this month`} />
            ))}
          </Card>
        </div>

        <Card title="AE quality risks">
          {data.ae_quality_risks.length === 0 && <Empty msg="No AE quality flags this month — clean." />}
          {data.ae_quality_risks.map((ae: any, i: number) => (
            <div key={i} className="p-4 bg-red-50 border border-red-200 rounded-lg mb-2">
              <div className="font-semibold text-red-900">
                {ae.ae_name} — {ae.interruption_count} interruptions
              </div>
              <ul className="mt-2 text-sm text-ss-navy list-disc list-inside">
                {(ae.examples || []).slice(0, 3).map((e: string, j: number) => <li key={j}>{e}</li>)}
              </ul>
            </div>
          ))}
        </Card>
      </main>
    </>
  );
}

function Stat({ label, value }: { label: string; value: any }) {
  return (
    <div className="bg-white border border-ss-cyan-soft rounded-xl p-5">
      <div className="text-xs font-semibold text-ss-navy-soft uppercase tracking-wider mb-2">{label}</div>
      <div className="text-3xl font-bold text-ss-navy">{value}</div>
    </div>
  );
}
function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white border border-ss-cyan-soft rounded-xl p-6">
      <h3 className="font-semibold text-ss-navy mb-4">{title}</h3>
      <div>{children}</div>
    </div>
  );
}
function Row({ title, sub }: { title: string; sub: string }) {
  return (
    <div className="py-2 border-b border-ss-cyan-soft last:border-0">
      <div className="font-medium text-ss-navy">{title}</div>
      <div className="text-sm text-ss-navy-soft">{sub}</div>
    </div>
  );
}
function Empty({ msg = "No data yet — analyze a few calls first." }: { msg?: string }) {
  return <p className="text-sm text-ss-navy-soft italic">{msg}</p>;
}
