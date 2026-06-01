# How scoring works — methodology

This is the explainer for SEs, managers, and the CEO. If you ever wonder "where did this score come from?" or "what does P10 mean?", this is the answer.

---

## TL;DR — read this if you read nothing else

Every call you upload is scored on a **7-criterion rubric** (described below). Each criterion has 2-3 sub-criteria. Claude reads the transcript, scores each sub-criterion on a **0-5 scale with a quote from your transcript as evidence**, and computes a **weighted final score out of 5**.

We then compare that final score to a baseline of **typical B2B SaaS Solution Engineers** and tell you which percentile bucket you fall into. **P50 = median. P75 = top quarter. P10 = bottom decile.**

The rubric is the same scoring system kaushik used historically in his "Demo of the Month" Excel sheets — we just automated it and benchmarked it against industry data.

---

## 1. The rubric (what we score)

| Criterion              | Weight (Demo call) | What we look for                                                              |
| ---------------------- | ------------------ | ----------------------------------------------------------------------------- |
| Solution Skills        | 30%                | Customization to prospect's pain · framing features as outcomes               |
| Craftsmanship          | 20%                | Personalized demo env · prospect logo · pre-built workflows                   |
| Communication          | 15%                | Tone, pacing · engaging delivery, stories, analogies                          |
| Consultative Approach  | 15%                | Proactive insights · clear recommendations · anchoring takeaways              |
| Presentation           | 10%                | Relevance of what's shown · narrative cohesion                                |
| Touchbase on Pain      | 5%                 | Surfacing + addressing pains throughout, not just at start                    |
| Audience Engagement    | 5%                 | Personalization (name use, industry examples) · interactivity                 |

Weights change automatically based on call type. A POC walkthrough weights Solution Skills at 35% and Craftsmanship at 20%; a closure call weights Consultative Approach at 35% and drops Craftsmanship to 0% (you shouldn't be doing new demos at close). The full per-call-type weight table is in `src/utils/call_types.py`.

---

## 2. How the final score is computed

Same formula as kaushik's original Excel sheets:

```
final_score = Σ over criteria of  (weight_pct / 100)  ×  avg(sub_scores)
```

Worked example for a demo call where:
- Solution Skills sub-scores: 4.0 and 3.5 → avg 3.75
- Craftsmanship: 4.0 and 4.0 → avg 4.0
- Communication: 4.0 and 4.0 → avg 4.0
- Consultative Approach: 3.5, 3.5, 3.0 → avg 3.33
- Presentation: 3.5 and 4.0 → avg 3.75
- Touchbase on Pain: 4.0 and 3.5 → avg 3.75
- Audience Engagement: 4.0 and 4.0 → avg 4.0

Final = 0.30×3.75 + 0.20×4.0 + 0.15×4.0 + 0.15×3.33 + 0.10×3.75 + 0.05×3.75 + 0.05×4.0
      = 1.125 + 0.800 + 0.600 + 0.500 + 0.375 + 0.188 + 0.200
      = **3.79 / 5**

That score is what shows in the big number on your dashboard.

---

## 3. The industry percentile — what P10 / P50 / P75 actually mean

We compare your final weighted score against the distribution of SaaS SE scores from industry data. The current bands (final score out of 5):

| Percentile | Score ≥ | What it means                                                                                         |
| ---------- | ------- | ----------------------------------------------------------------------------------------------------- |
| **P95**    | 4.5     | Top 5% — world-class. SEs at this level get hired into Director / Head of SE roles.                  |
| **P90**    | 4.3     | Top 10% — leadership track. Trusted to demo to C-suite buyers and run complex POCs.                  |
| **P75**    | 3.9     | Top 25% — strong, consistent performer. Trusted with the biggest deals on the team.                   |
| **P50**    | 3.4     | **Median.** The "typical" B2B SaaS SE. Solid, but not yet differentiated.                            |
| **P25**    | 2.8     | Bottom 25% — needs structured coaching. Usually a sign of weak discovery or feature-selling habit.   |
| **P10**    | < 2.8   | Bottom 10% — likely doing feature tours instead of value-led demos. High-priority coaching needed.   |

**How to read your number:**

- **"P10"** doesn't mean "10/100" or that you're a 10. It means: out of 100 SaaS SEs scored on this rubric, **roughly 90 score higher than you**, and you sit in the bottom 10%.
- **"P50"** means: **50 SEs score higher, 50 score lower** — you're at the median.
- **"P95"** means: **only ~5 in 100 score higher than you** — top performer territory.

The percentile is your **rank vs the entire SaaS industry, not just SurveySparrow**. So a P50 score puts you on par with median SEs at Salesforce, HubSpot, Atlassian, Gong, Asana — not just inside this team.

---

## 4. Per-criterion gap vs industry median

In the call detail view, each criterion shows a "vs median" gap. This compares your score on that one criterion to the SaaS-industry median for that specific criterion (not the overall final score). Example: if your Communication averaged 3.0 across the month, you'll see `−0.8 vs median` because the industry median for Communication is 3.8.

| Criterion              | Industry median (0-5) |
| ---------------------- | --------------------- |
| Communication          | 3.8                   |
| Presentation           | 3.6                   |
| Audience Engagement    | 3.4                   |
| Solution Skills        | 3.5                   |
| Consultative Approach  | 3.2                   |
| Touchbase on Pain      | 3.3                   |
| Craftsmanship          | 3.0                   |

**Why Craftsmanship median is lowest (3.0):** most SEs across the industry use generic demo environments. Personalizing your demo env with prospect logo + data is a fast way to leapfrog the median.

**Why Consultative Approach median is also low (3.2):** the industry over-indexes on product demonstration vs trusted-advisor positioning. SEs who consistently bring proactive insights stand out quickly.

---

## 5. Where the benchmark data comes from

Current numbers are **seeded estimates** synthesized from publicly-available sources:

- **Gartner SE Excellence** report (annual)
- **PreSales Collective State of PreSales** annual survey
- **SalesHood / Gong** public demo benchmarks
- **Bain SaaS GTM** benchmark surveys

These are reasonable starting estimates — they're not pulled from a live data feed. We refresh them quarterly. Source list is in `src/utils/benchmarks.py`.

**Caveat:** because these are estimates, the percentile is **directionally accurate, not surgically precise**. Think of P50 vs P75 as a real signal; don't agonize over P74 vs P76.

---

## 6. How scoring adapts to call type

The rubric is the same 7 criteria, but the **weights shift** and Claude is given **type-specific guidance** so it knows what "good" looks like in that context.

| Call type             | Heaviest weight                                | What we tell Claude to look for                                              |
| --------------------- | ---------------------------------------------- | ---------------------------------------------------------------------------- |
| **Demo call**         | Solution Skills 30% + Craftsmanship 20%        | Personalize the env, tie features to pains, leave a clear next step          |
| **Follow-up demo**    | Solution Skills 25% + Consultative 20%         | MUST reference pain points from the prior call — otherwise 0 on Pain Points  |
| **Follow-up query**   | Consultative 30% + Solution Skills 20%         | Act as a trusted advisor, not an FAQ answerer                                |
| **POC**               | Solution Skills 35% + Craftsmanship 20%        | Penalize "that's on the roadmap" answers; reward real workflow integration   |
| **Closure call**      | Consultative 35% + Pain 20% (Craft 0%)         | Loop back to original pains. No new feature tours. Help AE land the close.   |

This is why call type matters — picking "POC" when it was actually a closure call will score you against the wrong lens.

---

## 7. What's in your scorecard (and what to focus on)

Every scorecard has 4 things:

1. **Final weighted score + industry percentile** — the headline. Use it for trend, not for ego.
2. **Per-criterion scores with industry-gap deltas** — the diagnostic. The criterion with the largest negative gap is your highest-leverage improvement area.
3. **Top 3 strengths + top 3 areas of improvement** — qualitative, evidence-based. Each ties to a specific moment in the transcript.
4. **One coaching action for the month** — single concrete behavior change. **This is the only thing you have to do.** Don't try to fix all 6 gaps at once.

The whole point of one coaching action per month is: **one behavior change, sustained, will move you up a percentile band over a quarter**. Six behavior changes attempted at once moves you nowhere.

---

## 8. FAQ

**Q: Why is the percentile a band (P10, P25, P50, P75, P90, P95) and not an exact number like P67?**
We use bands because the underlying benchmark data is itself imprecise — fake precision would be misleading. Treat P10/P25/P50/P75/P90/P95 as the only meaningful resolution.

**Q: My score went down month-over-month. Did I get worse?**
Maybe, maybe not. Possible explanations: (a) you actually slipped on a specific behavior, (b) you took harder deals this month, (c) the LLM had a noisy month (Claude prompts evolve — we tag every score with the prompt version so we can re-score if needed), (d) variance is real and a single month is a small sample. Look at the 3-month trend, not month-to-month wobble.

**Q: I disagree with a score. What do I do?**
Reply to your monthly coaching email (kaushik is CC'd). Each score has the specific transcript quote as evidence — that's the conversation starter. We update the rubric and prompts based on real disputes, and we can re-score the call under the corrected logic.

**Q: Does the AI judge me unfairly?**
Every score has evidence. Every criterion has a clear definition. Every disagreement gets reviewed by kaushik. The system is calibrated to be honest, not flattering — if your demos score lower than you expected, that's signal, not malfunction.

**Q: Will my AE see my scores?**
No. SEs see only their own scores. Managers see the team. The CEO sees aggregates + executive summary. AEs do not have portal access at this stage.

---

## 9. For managers — how to use this

- **Don't lead with percentile in 1:1s.** Lead with the single coaching action. Percentile is for trend tracking; the action is for behavior change.
- **Watch the trend, not the snapshot.** A great SE having a bad month is a coaching conversation. Three months of decline is a process intervention.
- **Use the per-criterion gap to identify team-level patterns.** If 6 of your 8 SEs score low on Craftsmanship, that's an enablement problem, not 6 individual problems.
- **Demo of the Month celebrates effort + sustained quality.** Min 2 demo-class calls to be eligible — prevents single-call winners.

---

*Want to dig deeper? The full implementation is in `src/utils/rubric.py`, `src/utils/benchmarks.py`, `src/utils/call_types.py`, and the prompts in `prompts/`. Every score includes a `prompt_version` tag so we can audit historical scores against changes to the methodology.*
