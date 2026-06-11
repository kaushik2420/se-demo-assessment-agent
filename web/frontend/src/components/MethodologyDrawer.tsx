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
  | "fairness"
  | "audio-only"
  | "deal-intel"
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

  const backdropCls = "fixed inset-0 z-40 transition-opacity duration-200 " +
    (open ? "bg-slate-900/40 backdrop-blur-sm opacity-100" : "opacity-0 pointer-events-none");
  const drawerCls = "fixed top-0 right-0 z-50 h-full w-full max-w-[720px] bg-white shadow-2xl overflow-y-auto transition-transform duration-300 ease-out " +
    (open ? "translate-x-0" : "translate-x-full");

  return (
    <>
      <div onClick={close} className={backdropCls} />
      <aside ref={drawerRef} className={drawerCls} aria-hidden={!open}>
        <div className="sticky top-0 z-10 bg-white border-b border-ss-cyan-soft px-8 py-5 flex justify-between items-center">
          <div>
            <h2 className="text-xl font-semibold text-ss-navy">Scoring methodology</h2>
            <p className="text-xs text-ss-navy-soft mt-0.5">How we score · how to read percentile · benchmarks</p>
          </div>
          <button onClick={close} aria-label="Close"
            className="w-9 h-9 rounded-lg grid place-items-center text-ss-navy-soft hover:bg-ss-cream hover:text-ss-navy transition text-xl">
            ✕
          </button>
        </div>

        <nav className="px-8 py-4 border-b border-ss-cyan-soft bg-ss-cream">
          <div className="text-xs font-semibold text-ss-navy-soft uppercase tracking-wider mb-2">Jump to</div>
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

        <div className="px-8 py-6 prose-content">
          <Content />
        </div>

        <div className="px-8 py-5 border-t border-ss-cyan-soft text-xs text-ss-navy-soft bg-ss-cream">
          Questions about your scores? Reply to your monthly coaching email (kaushik is CC'd). Every score has a transcript-quote as evidence — we use that as the conversation starter.
        </div>
      </aside>
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
  { label: "What we won't penalize", anchor: "fairness" },
  { label: "Audio-only scoring", anchor: "audio-only" },
  { label: "Deal intelligence", anchor: "deal-intel" },
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
        <p>
          Beyond the score, we extract <strong>deal-intelligence signals</strong> from each call — what product the
          conversation is about (SurveySparrow / ThriveSparrow / SparrowDesk), the prospect's program maturity
          (CX or EX scope), features they discussed vs features they explicitly requested as gaps, competitors,
          trial issues, AE behavior, and selling style.
        </p>
        <div className="callout">
          The rubric is the same scoring system kaushik used historically in his "Demo of the Month" Excel sheets —
          we just automated it and benchmarked it against industry data. <strong>v3 (Jun 2026)</strong> added
          explicit fairness rules — SE check-ins aren't flagged as pain, AE-domain topics aren't your gaps,
          phased rollouts are respected, and procurement/security calls have their own scoring lens. See
          "What we won't penalize" below for the full list. Visual-only signals (was your logo on screen?)
          are only scored when the transcript verbally describes them — see "Audio-only scoring."
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
        <div className="callout">
          <strong>Weight rescaling for unassessable sub-criteria.</strong> If an entire criterion ends up unscorable
          (e.g. all of Craftsmanship was visual-only on a call with no screen description), it drops out and the
          remaining weights are <strong>rescaled to sum to 100</strong>. So your final score isn't artificially
          deflated by the missing criterion — you're scored on what was actually assessable from the transcript.
          See "Audio-only scoring" for the full rule.
        </div>
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
            <tr><td><strong>P25</strong></td><td>2.8</td><td>Bottom 25% — needs structured coaching. Often heavy on product walkthrough without tying back to stated outcomes.</td></tr>
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
            <tr><td><strong>Procurement</strong></td><td>Consult 40% + Comm 20%</td><td>Vendor security review / SOC 2 / compliance. No demo expected. Accuracy + honesty over selling.</td></tr>
          </tbody>
        </table>
        <p>
          <strong>Picking the wrong call type scores you against the wrong lens.</strong> If it was a closure call,
          don't pick "demo" — closure calls don't get penalized for low Craftsmanship.
        </p>
      </section>

      <section data-section="fairness">
        <h3>7. What we won't penalize you for</h3>
        <p>
          The scoring rubric exists to coach you on craft — not to nitpick about
          things that aren't actually your job, or normal call moves that get
          mis-read as gaps. Based on team feedback, these explicit fairness
          rules now ship with v3 of the scoring prompt:
        </p>

        <h4>SE check-ins are facilitation, not "unaddressed pain"</h4>
        <p>
          When you pause to ask <em>"any questions?"</em>, <em>"does that make
          sense?"</em>, <em>"anything I missed?"</em>, <em>"shall I keep going
          or pause here?"</em> — that's you structuring the call. The earlier
          version of the prompt sometimes flagged these as pain points the SE
          failed to address. <strong>Fixed.</strong> Only counts as a pain
          point if the <em>prospect</em> raised a concern / blocker / requirement
          and you didn't loop back to it.
        </p>

        <h4>AE-domain topics are not your responsibility</h4>
        <p>
          The following topics are owned by the Account Executive by default —
          the scoring no longer dings you for "not addressing" them, "not
          pushing on" them, or "not closing on" them:
        </p>
        <ul>
          <li>Commercial terms / pricing / discount discussion</li>
          <li>Contracts / SOW / paperwork</li>
          <li>Procurement / vendor onboarding / security questionnaires (as a process)</li>
          <li>Billing, invoicing, payment terms</li>
          <li>Legal review / MSA / DPA</li>
        </ul>
        <p>
          If you happen to handle these gracefully, that's a small bonus. If
          the AE handles them while you listen, that's <strong>normal and
          expected</strong>. You stepping aside for AE-domain topics is good
          role boundary, not a gap.
        </p>

        <h4>Phased rollouts respected when discovery already scoped them</h4>
        <p>
          If the prospect says <em>"Phase 1 is X, Phase 2 will be Y"</em> or
          references prior planning (<em>"as we discussed, ticketing comes in
          phase 2"</em>), the analysis now assumes the phases were already
          defined in an earlier discovery call. It won't flag "phases need to
          be identified" — that's mature discovery, not a gap. (Caveat: the
          system only sees the current call's transcript, so it can't proactively
          reference what was decided in that earlier discovery call. It just
          won't penalize you for not re-litigating it.)
        </p>

        <h4>Procurement / security-review calls have their own scoring lens</h4>
        <p>
          When the call is a vendor security review, SOC 2 walkthrough, IT
          compliance call, or procurement questionnaire — you're in
          trusted-advisor mode, not selling mode. The new <strong>"Procurement"
          call type</strong> shifts the weights accordingly: Consultative
          Approach jumps to 40%, Solution Skills drops to 10%, Craftsmanship
          drops to 10%. The analysis rewards accuracy, honesty (admitting when
          something isn't supported instead of bluffing), and pointing the
          prospect to the right doc / right person. It does NOT penalize you
          for the absence of demo content or value-selling — neither applies
          on this call type.
        </p>
        <div className="callout">
          <strong>Pick the right call type at upload time.</strong> If you
          select "demo" for what was actually a procurement call, you'll be
          scored against the wrong lens — Craftsmanship and Solution Skills
          will look weak through no fault of yours. Granola titles with
          "security review", "SOC 2", "compliance", "vendor onboarding" get
          auto-routed to Procurement; for manual uploads, pick it from the
          Call Type selector.
        </div>
      </section>

      <section data-section="audio-only">
        <h3>8. Audio-only scoring — how we handle visual signals</h3>
        <p>
          The analysis only ever sees a <strong>written transcript of the audio</strong>. We never have video,
          screenshots, or the actual demo screen. That matters because several sub-criteria in the rubric are about
          things on screen:
        </p>
        <ul>
          <li><strong>Craftsmanship → Personalization</strong> (was the prospect's logo on screen? vertical-relevant data?)</li>
          <li><strong>Craftsmanship → Customization</strong> (custom dashboards, role-played personas, working integrations?)</li>
          <li><strong>Presentation → Relevance</strong> (does each shown artifact tie to a stated need?)</li>
          <li><strong>Presentation → Cohesion</strong> (visual narrative arc)</li>
        </ul>
        <p>For these visual sub-criteria, Claude follows a strict rule:</p>
        <ol>
          <li>Search the transcript for verbal evidence of what was on screen. <em>"Let me pull up your dashboard with your company logo"</em> counts. <em>"As you can see, this is your industry's data"</em> counts. A prospect reacting to visuals (<em>"nice, that's our brand color"</em>) counts.</li>
          <li>If found → score normally, with the verbal evidence as the quote.</li>
          <li>If <strong>none found</strong> → mark the sub-criterion <code>not_assessable</code>, score = null. The sub is <strong>excluded</strong> from the criterion average rather than getting a penalty score.</li>
        </ol>
        <p>
          On the call detail page you'll see a grey banner at the top listing which sub-criteria were excluded for
          this reason. If most of Craftsmanship was not_assessable, that's expected for an audio-only call where you
          didn't verbally describe what was on screen.
        </p>
        <div className="callout">
          <strong>The takeaway for SEs:</strong> if you want credit for a beautifully personalized demo environment,
          <em>say it out loud during the call</em> — "let me pull up the dashboard we mocked with your logo and
          last quarter's NPS data." That gives the analysis verbal evidence to score against. Without it, the demo
          craft doesn't reach the transcript, and we won't make claims about it either way.
        </div>
      </section>

      <section data-section="deal-intel">
        <h3>9. Deal-intelligence signals — what we extract beyond the score</h3>
        <p>
          Each call also gets a structured extract of <strong>deal-context</strong> signals — visible on the call
          detail page and rolled up into the manager + CEO dashboards. The score is the SE's coaching loop; the
          intelligence is the company's deal-loop.
        </p>
        <table>
          <thead><tr><th>Signal</th><th>What it captures</th></tr></thead>
          <tbody>
            <tr><td><strong>Product</strong></td><td>Which product the conversation is primarily about: SurveySparrow (CX/feedback), ThriveSparrow (EX/employee engagement), or SparrowDesk (helpdesk/support).</td></tr>
            <tr><td><strong>Use case</strong></td><td>1-2 sentence description of what the prospect actually wants to do, with direct quotes.</td></tr>
            <tr><td><strong>Maturity</strong></td><td>An 8-dimension 0-3 scorecard rolling into a band: Form / Basic · Low Maturity · Potential High · High. The <strong>scope</strong> (CX or EX) is set by the product. ThriveSparrow conversations get EX maturity; the others get CX.</td></tr>
            <tr><td><strong>Features discussed</strong></td><td>Capabilities already in our product that came up — demoed, mentioned, or that the prospect asked about and we have. <strong>Most product-feature talk goes here.</strong></td></tr>
            <tr><td><strong>Feature requests / gaps</strong></td><td>Things we <em>don't</em> have that the prospect asked for, or that our team admitted is missing/roadmap. Tagged blocker / nice-to-have / mentioned. <strong>Only true gaps end up here</strong>, not existing capabilities.</td></tr>
            <tr><td><strong>Competitors</strong></td><td>Other vendors named, with context: evaluated, currently using, dismissed.</td></tr>
            <tr><td><strong>Trial issues</strong></td><td>Things that broke or were confusing during a trial, with severity.</td></tr>
            <tr><td><strong>Loss-risk signals</strong></td><td>No-reference-customer asks, support quality concerns, pricing pushback, product-gap concerns.</td></tr>
            <tr><td><strong>AE behavior</strong></td><td>How many times the AE interrupted the SE mid-value, plus an impact verdict.</td></tr>
            <tr><td><strong>Selling approach</strong></td><td>Product-led vs outcome-led vs balanced — describes the approach the call lent itself to, not a label on the SE. The metric reflects framing on this specific call, not a permanent style.</td></tr>
            <tr><td><strong>Prospect engagement</strong></td><td>Overall sentiment, buying signals, objections.</td></tr>
          </tbody>
        </table>
        <div className="callout">
          <strong>Features discussed vs feature requests — the bright line:</strong> if you demoed it or it already
          exists in the platform, it's <em>discussed</em>. If the prospect explicitly said they need something we
          don't have, or your team said "that's not available today" — it's a <em>request</em>. The split exists
          because product/engineering doesn't want to wade through 50 "feature requests" that are actually existing
          capabilities the prospect just hadn't seen yet.
        </div>
      </section>

      <section data-section="scorecard">
        <h3>10. What's in your scorecard</h3>
        <p>Every scorecard has the following:</p>
        <ul>
          <li><strong>Final weighted score + industry percentile</strong> — the headline. Use it for trend, not for ego.</li>
          <li><strong>Per-criterion scores + industry-gap deltas</strong> — the diagnostic. Biggest negative gap = highest-leverage area.</li>
          <li><strong>Top 3 strengths + top 3 gaps</strong> — qualitative, evidence-based. Each tied to a transcript moment.</li>
          <li><strong>One coaching action for the month</strong> — single concrete behavior change. <strong>This is the only thing you have to do.</strong></li>
          <li><strong>Not-assessable banner</strong> (when relevant) — lists which sub-criteria couldn't be scored from this transcript and were excluded from the weighted average.</li>
          <li><strong>Product + Maturity badges</strong> — at-a-glance: which product (SurveySparrow/ThriveSparrow/SparrowDesk) and what scope of maturity (CX or EX).</li>
          <li><strong>Deal-intelligence grid</strong> — product, use case, maturity, features discussed, feature requests/gaps, competitors, trial issues, SE selling style, AE behavior, prospect engagement.</li>
        </ul>
        <div className="callout">
          One behavior change, sustained, moves you up a percentile band over a quarter.
          Six behavior changes attempted at once moves you nowhere.
        </div>
      </section>

      <section data-section="faq">
        <h3>11. FAQ</h3>
        <p><strong>My procurement / security-review call got dinged for "no demo." Why?</strong><br/>
          That was the old behaviour — fixed in v3. The system now has a dedicated
          "Procurement" call type with completely different weights (Consultative
          40%, Solution Skills only 10%, Craftsmanship 10%, no demo expected).
          If your past procurement call was scored under "demo" by mistake, ask
          kaushik to re-run the analysis after the deploy; the new call type will
          be applied automatically for titles containing "security review",
          "SOC 2", "vendor onboarding", etc. For manual uploads, pick "Procurement
          / Security" from the call-type selector.
        </p>
        <p><strong>I asked "any questions?" before closing — why was that flagged as unaddressed pain?</strong><br/>
          That was the old behaviour — fixed in v3. SE check-ins like "any
          questions?", "does that make sense?", "anything I missed?" are now
          recognized as facilitation, not unaddressed pain. Only the
          <em>prospect's</em> raised concerns count as pain points.
        </p>
        <p><strong>The scoring said I should have pushed harder on commercials / contracts. But that's the AE's job.</strong><br/>
          Agreed — fixed in v3. The analysis now explicitly excludes AE-domain
          topics (pricing, contracts, paperwork, procurement process, billing,
          legal) from SE evaluation. Stepping aside when the AE handles those
          is good role boundary, not a gap.
        </p>
        <p><strong>The system says I spoke only 5-6 lines on a call I drove the discovery for. Why?</strong><br/>
          This is a Granola transcript-fidelity issue, not analysis logic. Granola
          only distinguishes its <em>account-owner's microphone</em> from
          "everyone else mixed together." If you weren't the Granola account
          owner on that call (e.g. you joined someone else's calendar invite),
          your turns get lumped with the prospect/AE in a single "speaker" track
          and we can't recover the attribution. The fix is operational: be the
          Granola account owner on your own calls. For calls where this fails,
          paste a richer per-speaker transcript via the Upload flow instead.
        </p>
        <p><strong>Why is "Craftsmanship" missing or partial on my call?</strong><br/>
          Most of Craftsmanship is about what's on screen (your logo on the dashboard, custom data, working
          integrations). The analysis only sees the audio transcript — so those sub-criteria are only scored when
          you (or the prospect) verbally referenced them on the call. The grey banner at the top of your call
          detail page lists which sub-criteria couldn't be scored. Those are <em>excluded</em> from the weighted
          average — they don't drag your score down. Solution: narrate your craft out loud during demos.
        </p>
        <p><strong>I demoed feature X — why is it in "Features discussed" instead of "Feature requests"?</strong><br/>
          Because the prospect didn't say it's missing. <em>Feature requests / gaps</em> only contains things we
          don't have or the team admitted is unavailable. Anything you demoed or that the prospect explored and we
          support belongs in <em>features discussed</em>. This split exists because product/engineering needs a
          clean list of true gaps — not 50 "requests" that are actually existing capabilities.
        </p>
        <p><strong>Why does the call say "ThriveSparrow" / "SparrowDesk" / "Unknown" as the product?</strong><br/>
          The product field is inferred from what the conversation is about. NPS / customer feedback / journeys →
          SurveySparrow. eNPS / engagement / 360 reviews → ThriveSparrow. Ticketing / helpdesk → SparrowDesk.
          Multi-product conversations get the primary one in the badge with the others in the call detail. If it
          looks wrong, the transcript probably didn't have strong enough signal — paste a clearer transcript via
          Upload or check the AE's qualifying notes.
        </p>
        <p><strong>What's the "Maturity (CX/EX)" badge?</strong><br/>
          The 8-dimension maturity framework still works the same, but the scope (CX vs EX) is now stated explicitly
          because ThriveSparrow conversations are about employee experience, not customer experience. SurveySparrow
          and SparrowDesk conversations are scoped as CX; ThriveSparrow conversations are scoped as EX. The bands
          are the same.
        </p>
        <p><strong>Why do Granola-sourced calls have a yellow "AE behavior is inferred" banner?</strong><br/>
          Granola records the SE's microphone separately but mixes the AE and prospect into a
          single "other" audio track. So when we label speaker turns, we know which lines are
          the SE's, but we can't directly distinguish AE turns from prospect turns. Claude
          infers attribution from content patterns (AEs talk about pricing/timeline, prospects
          ask about features) — accurate enough for direction, not for surgical metrics like
          exact interruption counts. For calls where AE quality is the question being asked,
          paste a richer per-speaker transcript via the Upload flow.
        </p>
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
        <p><strong>My old calls were scored under the older prompt — will they get updated?</strong><br/>
          Admins can trigger a "Re-analyze under current prompts" run from the Team page. It re-scores every call
          on an older prompt version using the latest rubric, the visual-evidence rule, and the features split.
          Score quotes and dates are preserved; only the scores + insights are refreshed.
        </p>
      </section>

      <section data-section="managers">
        <h3>12. For managers — how to use this</h3>
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
