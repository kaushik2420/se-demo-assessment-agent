# SE Onboarding — Granola + SE Coach Portal

Hi team — quick note from kaushik on a new coaching system we're rolling out.

## What's changing

Every external demo / discovery / POC / closure call gets analyzed by an AI coach and you get a personal scorecard. Strengths, gaps, a single coaching action for the month, and how you stack up against B2B SaaS SEs benchmarks.

You only see your own calls. I see everyone's, and the CEO sees the aggregated executive view. No one else sees your data.

## What I need from you (15 min one-time setup)

### 1. Install Granola

- Download: <https://granola.ai/download>
- Mac users — Granola runs best on macOS, that's why I picked it.
- Sign up with your `@surveysparrow.com` work email.
- In Granola settings: enable **Auto-record meetings on my calendar**.

### 2. Keep Granola running during external calls

Open Granola before you join Zoom / Meet / Teams. It runs in your menu bar; once it detects the call it starts recording silently. After the call, transcript appears in Granola within ~2 minutes.

### 3. Log in to the SE Coach portal

- URL: `<your-vercel-url>` (I'll DM you)
- Email: your `@surveysparrow.com` address
- Initial password: I'll DM you individually. Change it on first login (Settings → Password).

### 4. After every external call: share the note to "Calls for analysis"

This is the only manual step required, and it takes 5 seconds:

1. In Granola, open the meeting note
2. Click **Share** → **Add to folder**
3. Select the workspace folder: **Calls for analysis**

That's it. Within ~30 minutes, the portal auto-pulls the note, runs the full
analysis (scoring + 9-signal insights), and your scorecard appears on your
dashboard. You don't need to copy/paste anything, set the call type manually,
or click "Analyze". It's all automatic.

**Call type** is auto-detected from your Granola meeting title — keywords like
"demo", "POC", "discovery", "follow-up", "closure" map to the right rubric.
If the auto-detection ever picks the wrong type, ping kaushik and we can
recategorize and re-score.

**Privacy is in your hands:** if you don't add a note to "Calls for analysis",
the portal never sees it. So personal 1:1s, internal calls, sensitive client
conversations, anything you want to keep out of the coaching loop — just
don't share to the folder.

### 4b. (Fallback) Manually paste a transcript

For calls where Granola wasn't running, or where you want to use a richer
per-speaker transcript (e.g., from Avoma / Zoom recording), use the manual
upload path:

1. In the portal: click **+ Upload transcript**
2. Pick the call type, type the prospect company name
3. Paste the transcript → **Analyze**
4. You'll see your scorecard in ~30-60 seconds

**Important:** paste the **transcript** (raw spoken words), not Granola's
"AI notes" or any summary. The portal will reject notes with a clear error.

### 5. Check your dashboard weekly

Your dashboard shows:

- Your current weighted score (out of 5) and SaaS-industry percentile
- 6-month trend line
- Top 3 strengths and top 3 areas of improvement
- **Your single coaching action for the month** — this is what to focus on next
- All recent calls; click any one for the deep dive

---

## FAQ

**Q: Do I have to use Granola? Can I just paste from Avoma / Otter / Fathom?**
Yes. Any tool that gives you a speaker-labeled transcript works — use the manual
upload path. Granola is recommended because it's automatic (just share to the
folder), but it's not the only source.

**Q: What if I forget to share a Granola note to the folder?**
The call simply doesn't get analyzed. No penalty — your score averages over
what's analyzed, not what wasn't. You can share it later (within 14 days of
the call) and the portal will pick it up on the next sync.

**Q: What if I forget to start Granola entirely?**
Use any other transcript source (Avoma, Zoom recording, Otter) and paste it
manually via the upload form. Same result, just one extra step.

**Q: How accurate are AE-quality signals from Granola-sourced calls?**
Directionally accurate, not surgically precise. Granola can clearly identify
your turns (your microphone) but combines the AE's and prospect's audio into
a single channel — so AE vs prospect attribution is inferred from content,
not measured. For calls where you specifically want to evaluate AE quality
(e.g., flag a problematic AE pattern to leadership), paste a richer
per-speaker transcript via the Upload flow instead.

**Q: Will the AI judge me unfairly?**
Each score comes with a specific evidence quote from your transcript. If a score looks wrong, push back — there's a feedback button on every scorecard (coming soon) and you can ping me directly.

**Q: Are my scores visible to other SEs?**
No. SEs only see their own data. I (kaushik) see the team. The CEO sees aggregated metrics — no individual SE names below the manager level except for the leaderboard ranking.

**Q: How is "good" defined? Different call types have different expectations.**
Yes — POC calls are scored heavier on Solution Skills and Craftsmanship; closure calls are scored heavier on Consultative Approach and Pain Points (and lighter on Craftsmanship since you shouldn't be doing new demos at close). The rubric adjusts automatically based on the call type you pick.

**Q: How long does analysis take?**
30-60 seconds per call. You'll see the result immediately.

**Q: My customer asked me not to record. What do I do?**
Don't record. The customer's consent always wins. Skip the upload for that call.

---

## Privacy & consent

- Granola shows a visible "AI is recording" indicator during the call
- All transcripts are stored encrypted; only you, your manager (me), and admin see your data
- Right-to-delete: tell me to purge your data and it's gone within 24 hours
- The AI analysis uses Anthropic's Claude API with "do not train on this data" headers — your transcripts never become training data

---

Questions? DM me on Slack. Let's make the team measurably better, one demo at a time.

— kaushik
