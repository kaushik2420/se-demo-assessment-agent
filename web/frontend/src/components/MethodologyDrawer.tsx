"use client";
import { createContext, useContext, useEffect, useRef, useState, ReactNode } from "react";

/**
 * Global methodology drawer — slide-out panel from the right with the full
 * scoring + percentile explainer.
 *
 * Usage:
 *   1. Wrap your app (or page tree) in <MethodologyProvider>
 *   2. Anywhere you want a "ⓘ" icon, use <InfoIcon section="percentile" />
 *   3. The provider exposes openTo(section?) for programmatic opens
 *
 * Sections (deep-link anchors):
 *   tldr | rubric | formula | percentile | per-criterion | sources |
 *   call-types | scorecard | faq | managers
 */

type Section =
  | "tldr"
  | "rubric"
  | "formula"
  | "percentile"
  | "per-criterion"
  | "sources"
  | "call-types"
  | "scorecard"
  | "faq"
  | "managers";

type Ctx = {
  open: boolean;
  section: Section | null;
  openTo: (section?: Section) => void;
  close: () => void;
};

const MethodologyCtx = createContext<Ctx | null>(null);

export function useMethodology() {
  const c = useContext(MethodologyCtx);
  if (!c) throw new Error("useMethodology must be inside <MethodologyProvider>");
  return c;
}

export function MethodologyProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [section, setSection] = useState<Section | null>(null);

  // Lock body scroll when drawer is open
  useEffect(() => {
    if (typeof document === "undefined") return;
    document.body.style.overflow = open ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  // Esc to close
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const openTo = (s?: Section) => {
    setSection(s || null);
    setOpen(true);
  };

  return (
    <MethodologyCtx.Provider value={{ open, section, openTo, close: () => setOpen(false) }}>
      {children}
      <MethodologyDrawer />
    </MethodologyCtx.Provider>
  );
}

export function InfoIcon({ section, label }: { section?: Section; label?: string }) {
  const { openTo } = useMethodology();
  return (
    <button
      type="button"
      aria-label={label || "How is this calculated?"}
      title={label || "How is this calculated?"}
      onClick={(e) => { e.preventDefault(); e.stopPropagation(); openTo(section); }}
      className="inline-flex items-center justify-center w-4 h-4 ml-1.5 rounded-full
                 bg-ss-teal-soft text-ss-teal-deep hover:bg-ss-teal hover:text-white
                 text-[10px] font-bold leading-none transition cursor-pointer flex-shrink-0"
    >
      i
    </button>
  );
}

function MethodologyDrawer() {
  const { open, section, close } = useMethodology();
  const drawerRef = useRef<HTMLDivElement>(null);

  // Scroll to section when drawer opens or section changes
  useEffect(() => {
    if (!open || !section || !drawerRef.current) return;
    const t = setTimeout(() => {
      const el = drawerRef.current?.querySelector(`[data-section="${section}"]`);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 100);
    return () => clearTimeout(t);
  }, [open, section]);

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={close}
        className={`fixed inset-0 z-40 transition-opacity duration-200
          ${open ? "bg-slate-900/40 backdrop-blur-sm opacity-100" : "opacity-0 pointer-events-none"}`}
      />
      {/* Drawer */}
      <aside
        ref={drawerRef}
        className={`fixed top-0 right-0 z-50 h-full w-full max-w-[720px] bg-white shadow-2xl
          overflow-y-auto transition-transform duration-300 ease-out
          ${open ? "translate-x-0" : "translate-x-full"}`}
        aria-hidden={!open}
      >
        {/* Sticky header */}
        <div className="sticky top-0 z-10 bg-white border-b border-ss-cyan-soft px-8 py-5 flex justify-between items-center">
          <div>
            <h2 className="text-xl font-semibold text-ss-navy">Scoring methodology</h2>
            <p className="text-xs text-ss-navy-soft mt-0.5">
              How we score · how to read percentile · benchmarks
            </p>
          </div>
          <button
            onClick={close}
            className="w-9 h-9 rounded-lg grid place-items-center text-ss-navy-soft
                       hover:bg-ss-cream hover:text-ss-navy transition text-xl"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* TOC */}
        <nav className="px-8 py-4 border-b border-ss-cyan-soft bg-ss-cream">
          <div className="text-xs font-semibold text-ss-navy-soft uppercase tracking-wider mb-2">
            Jump to
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
            {TOC.map((t) => (
              <a key={t.anchor} href={`#m-${t.anchor}`}
                 onClick={(e) => {
                   e.preventDefault();
                   const el = drawerRef.current?.querySelector(`[data-section="${t.anchor}"]`);
                   if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
                 }}
                 className="text-ss-teal-deep hover:underline">
                {t.label}
              </a>
            ))}
          </div>
        </nav>

        {/* Content */}
        <div className="px-8 py-6 prose-content">
          <Content />
        </div>

        {/* Footer */}
        <div className="px-8 py-5 border-t border-ss-cyan-soft text-xs text-ss-navy-soft bg-ss-cream">
          Questions about your scores? Reply to your monthly coaching email
          (kaushik is CC'd). Every score has a transcript-quote as evidence —
          we use that as the conversation starter.
        </div>
      </aside>

      {/* Inline content styles (scoped, no global Tailwind plugin needed) */}
      <style jsx global>{`
        .prose-content h3 {
          font-size: 16px; font-weight: 600; color: #253043;
          margin: 24px 0 10px; padding-top: 4px;
        }
        .prose-content h3:first-child { margin-top: 0; }
        .prose-content p { font-size: 14px; line-height: 1.6; color: #253043; margin: 0 0 12px; }
        .prose-content ul { font-size: 14px; line-height: 1.6; color: #253043; padding-left: 22px; margin: 0 0 14px; }
        .prose-content ul li { margin-bottom: 6px; }
        .prose-content strong { color: #253043; font-weight: 600; }
        .prose-content table { width: 100%; border-collapse: collapse; margin: 12px 0 18px; font-size: 13px; }
        .prose-content th { text-align: left; padding: 8px 10px; background: #DCEFF1; color: #253043; font-weight: 600; }
        .prose-content td { padding: 8px 10px; border-bottom: 1px solid #DCEFF1; color: #253043; vertical-align: top; }
        .prose-content tr:last-child td { border-bottom: none; }
        .prose-content code { background: #F4FBFD; padding: 1px 5px; border-radius: 4px; font-size: 12px; color: #3A8290; }
        .prose-content blockquote { border-left: 3px solid #4A9CA6; padding-left: 12px; margin: 12px 0; color: #3D4858; font-style: italic; }
        .prose-content .callout {
          background: linear-gradient(135deg,#DCEFF1,#B1EAF8);
          border: 1px solid #5DACB6; border-radius: 10px; padding: 14px 16px; margin: 14px 0;
        }
        .prose-content .callout strong { color: #1A2433; }
      `}</style>
    </>
  );
}

const TOC: { label: string; anchor: Section }[] = [
  { label: "TL;DR", anchor: "tldr" },
  { label: "Rubric", anchor: "rubric" },
  { label: "Formula", anchor: "formula" },
  { label: "Percentile", anchor: "percentile" },
  { label: "Per-criterion", anchor: "per-criterion" },
  { label: "Sources", anchor: "sources" },
  { label: "Call types", anchor: "call-types" },
  { label: "Scorecard", anchor: "scorecard" },
  { label: "FAQ", anchor: "faq" },
  { label: "For managers", anchor: "managers" },
];

function Content() {
  return (
    <>
      <section data-section="tldr">
        <h3>TL;DR</h3>
        <p>
          Every call you upload is scored on a <strong>7-criterion rubric</strong>. Each criterion has 2-3 sub-criteria.
          Claude reads the transcript, scores each sub-criterion on a <strong>0-5 scale with a transcript quote as evidence</strong>,
          and computes a <strong>weighted final score out of 5</strong>.
        </p>
        <p>
          We then compare your final score to a baseline of typical B2B SaaS Solution Engineers and tell you which
          percentile bucket you fall into. <strong>P50 = median. P75 = top quarter. P10 = bottom decile.</strong>
        </p>
        <div className="callout">
          The rubric is the same scoring system kaushik used historically in his "Demo of the Month" Excel sheets —
          we just automated it and benchmarked it against industry data.
        </div>
      </section>

      <section data-section="rubric">
        <h3>1. The rubric — what we score</h3>
        <table>
          <thead><tr><th>Criterion</th><th>Weight (Demo)</th><th>What we look for</th></tr></thead>
          <tbody>
            <tr><td><strong>Solution Skills</strong></td><td>30%</td><td>Customization to prospect's pain · framing features as outcomes</td></tr>
            <tr><td><strong>Craftsmanship</strong></td><td>20%</td><td>Personalized demo env · prospect logo · pre-built workflows</td></tr>
            <tr><td><strong>Communication</strong></td><td>15%</td><td>Tone, pacing · engaging delivery, stories, analogies</td></tr>
            <tr><td><strong>Consultative Approach</strong></td><td>15%</td><td>Proactive insights · clear recommendations · anchoring takeaways</td></tr>
            <tr><td><strong>Presentation</strong></td><td>10%</td><td>Relevance of what's shown · narrative cohesion</td></tr>
            <tr><td><strong>Touchbase on Pain</strong></td><td>5%</td><td>Surfacing + addressing pains throughout, not just at start</td></tr>
            <tr><td><strong>Audience Engagement</strong></td><td>5%</td><td>Personalization (name, industry examples) · interactivity</td></tr>
          </tbody>
        </table>
        <p>
          Weights change automatically based on call type — see the "Call types" section below.
        </p>
      </section>

      <section data-section="formula">
        <h3>2. How the final score is computed</h3>
        <p>Same formula as the original Excel sheets:</p>
        <p><code>final = Σ over criteria of (weight_pct / 100) × avg(sub_scores)</code></p>
        <p><strong>Worked example</strong> — a demo call with these sub-score averages:</p>
        <ul>
          <li>Solution Skills: 3.75 → contributes 0.30 × 3.75 = 1.125</li>
          <li>Craftsmanship: 4.0 → contributes 0.20 × 4.0 = 0.800</li>
          <li>Communication: 4.0 → contributes 0.15 × 4.0 = 0.600</li>
          <li>Consultative Approach: 3.33 → contributes 0.15 × 3.33 = 0.500</li>
          <li>Presentation: 3.75 → contributes 0.10 × 3.75 = 0.375</li>
          <li>Pain Points: 3.75 → contributes 0.05 × 3.75 = 0.188</li>
          <li>Audience Engagement: 4.0 → contributes 0.05 × 4.0 = 0.200</li>
        </ul>
        <p><strong>Final = 3.79 / 5.</strong> That's the big number on your dashboard.</p>
      </section>

      <section data-section="percentile">
        <h3>3. Industry percentile — what P10 / P50 / P75 actually mean</h3>
        <p>
          We compare your final weighted score against the distribution of SaaS SE scores from industry data.
          Current bands (final score out of 5):
        </p>
        <table>
          <thead><tr><th>Band</th><th>Score ≥</th><th>What it means</th></tr></thead>
          <tbody>
            <tr><td><strong>P95</strong></td><td>4.5</td><td>Top 5% — world-class. SEs at this level get hired into Director / Head of SE roles.</td></tr>
            <tr><td><strong>P90</strong></td><td>4.3</td><td>Top 10% — leadership track. Trusted to demo to C-suite and run complex POCs.</td></tr>
            <tr><td><strong>P75</strong></td><td>3.9</td><td>Top 25% — strong, consistent performer. Trusted with the biggest deals.</td></tr>
            <tr><td><strong>P50</strong></td><td>3.4</td><td><strong>Median.</strong> The "typical" B2B SaaS SE. Solid but not yet differentiated.</td></tr>
            <tr><td><strong>P25</strong></td><td>2.8</td><td>Bottom 25% — needs structured coaching. Usually weak discovery / feature-selling.</td></tr>
            <tr><td><strong>P10</strong></td><td>&lt; 2.8</td><td>Bottom 10% — likely doing feature tours instead of value-led demos.</td></tr>
          </tbody>
        </table>
        <div className="callout">
          <strong>"P10" does NOT mean "10/100".</strong> It means: out of 100 SaaS SEs scored on this rubric,
          roughly 90 score higher than you, and you sit in the bottom 10%. <strong>P50</strong> means 50 above, 50 below — median.
          <strong> P95</strong> means only ~5 in 100 score higher — top performer.
        </div>
        <p>
          The percentile is your rank vs the entire <strong>SaaS industry</strong>, not just SurveySparrow.
          A P50 score puts you on par with median SEs at Salesforce, HubSpot, Atlassian, Gong — not just this team.
        </p>
      </section>

      <section data-section="per-criterion">
        <h3>4. Per-criterion gap vs industry median</h3>
        <p>
          In the call detail view, each criterion shows a "vs median" gap — your score on that one criterion
          vs the SaaS-industry median for that specific criterion (not the overall final score).
        </p>
        <table>
          <thead><tr><th>Criterion</th><th>Industry median (0-5)</th></tr></thead>
          <tbody>
            <tr><td>Communication</td><td>3.8</td></tr>
            <tr><td>Presentation</td><td>3.6</td></tr>
            <tr><td>Audience Engagement</td><td>3.4</td></tr>
            <tr><td>Solution Skills</td><td>3.5</td></tr>
            <tr><td>Consultative Approach</td><td>3.2</td></tr>
            <tr><td>Touchbase on Pain</td><td>3.3</td></tr>
            <tr><td>Craftsmanship</td><td>3.0</td></tr>
          </tbody>
        </table>
        <p>
          <strong>Craftsmanship median is lowest (3.0)</strong> because most SEs use generic demo environments.
          Personalizing yours with prospect logo + data is a fast way to leapfrog the median.
        </p>
        <p>
          <strong>Consultative Approach (3.2)</strong> is the second-lowest — the industry over-indexes on
          product demonstration vs trusted-advisor positioning. SEs who bring proactive insights stand out fast.
        </p>
      </section>

      <section data-section="sources">
        <h3>5. Where the benchmark data comes from</h3>
        <p>Current numbers are seeded estimates synthesized from publicly-available sources:</p>
        <ul>
          <li><strong>Gartner SE Excellence</strong> report (annual)</li>
          <li><strong>PreSales Collective State of PreSales</strong> annual survey</li>
          <li><strong>SalesHood / Gong</strong> public demo benchmarks</li>
          <li><strong>Bain SaaS GTM</strong> benchmark surveys</li>
        </ul>
        <p>
          These are reasonable starting estimates — not a live data feed. We refresh them quarterly.
        </p>
        <div className="callout">
          <strong>Caveat:</strong> the percentile is directionally accurate, not surgically precise.
          P50 vs P75 is a real signal; don't agonize over P74 vs P76.
        </div>
      </section>

      <section data-section="call-types">
        <h3>6. How scoring adapts to call type</h3>
        <p>Same 7 criteria, but weights shift and Claude gets type-specific guidance:</p>
        <table>
          <thead><tr><th>Call type</th><th>Heaviest weight</th><th>Type-specific guidance</th></tr></thead>
          <tbody>
            <tr><td><strong>Demo</strong></td><td>Solution 30% + Craft 20%</td><td>Personalize env, tie features to pains, clear next step</td></tr>
            <tr><td><strong>Follow-up demo</strong></td><td>Solution 25% + Consult 20%</td><td>MUST reference prior-call pains — otherwise 0 on Pain Points</td></tr>
            <tr><td><strong>Follow-up query</strong></td><td>Consult 30% + Solution 20%</td><td>Be a trusted advisor, not an FAQ answerer</td></tr>
            <tr><td><strong>POC</strong></td><td>Solution 35% + Craft 20%</td><td>Penalize "that's on the roadmap"; reward real workflow integration</td></tr>
            <tr><td><strong>Closure</strong></td><td>Consult 35% + Pain 20% (Craft 0%)</td><td>Loop back to original pains. No new feature tours.</td></tr>
          </tbody>
        </table>
        <p>
          <strong>Picking the wrong call type scores you against the wrong lens.</strong> If it was a closure call,
          don't pick "demo" — closure calls don't get penalized for low Craftsmanship.
        </p>
      </section>

      <section data-section="scorecard">
        <h3>7. What's in your scorecard</h3>
        <p>Every scorecard has 4 things:</p>
        <ul>
          <li><strong>Final weighted score + industry percentile</strong> — the headline. Use it for trend, not for ego.</li>
          <li><strong>Per-criterion scores + industry-gap deltas</strong> — the diagnostic. Biggest negative gap = highest-leverage area.</li>
          <li><strong>Top 3 strengths + top 3 gaps</strong> — qualitative, evidence-based. Each tied to a transcript moment.</li>
          <li><strong>One coaching action for the month</strong> — single concrete behavior change. <strong>This is the only thing you have to do.</strong></li>
        </ul>
        <div className="callout">
          One behavior change, sustained, moves you up a percentile band over a quarter.
          Six behavior changes attempted at once moves you nowhere.
        </div>
      </section>

      <section data-section="faq">
        <h3>8. FAQ</h3>
        <p><strong>Why bands (P10, P25...) not exact numbers like P67?</strong><br/>
          Because the underlying benchmark data is itself imprecise. Fake precision would mislead.
        </p>
        <p><strong>My score went down month-over-month. Did I get worse?</strong><br/>
          Maybe — or you took harder deals, or it's normal variance. Look at the 3-month trend, not month-to-month wobble.
        </p>
        <p><strong>I disagree with a score. What do I do?</strong><br/>
          Reply to your coaching email. Every score has a transcript quote as evidence — that's the conversation starter.
        </p>
        <p><strong>Will my AE see my scores?</strong><br/>
          No. SEs see only their own scores. Managers see the team. CEO sees aggregates. AEs do not have portal access.
        </p>
      </section>

      <section data-section="managers">
        <h3>9. For managers — how to use this</h3>
        <ul>
          <li><strong>Don't lead with percentile in 1:1s.</strong> Lead with the single coaching action.</li>
          <li><strong>Watch the trend, not the snapshot.</strong> A great SE having a bad month is a coaching conversation. Three months of decline is a process intervention.</li>
          <li><strong>Use per-criterion gaps to spot team-level patterns.</strong> If 6 of 8 SEs are low on Craftsmanship, that's an enablement problem.</li>
          <li><strong>Demo of the Month rewards sustained quality.</strong> Min 2 demo-class calls to be eligible — prevents single-call winners.</li>
        </ul>
      </section>
    </>
  );
}
