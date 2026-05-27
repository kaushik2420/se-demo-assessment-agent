"""
Orchestrator entry point.

Usage:
    python -m src.main --demo                 # run on sample_data, mock LLM
    python -m src.main --demo --live          # run on sample_data, real Claude API
    python -m src.main --month 2026-05        # process all calls for a given month
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

from src.analysis.exec_summary import generate_exec_summary
from src.analysis.insights_extractor import extract_insights
from src.analysis.llm_client import LLMClient
from src.analysis.scoring_engine import CallContext, score_call
from src.ingestion.manual_upload import load_transcript_file
from src.notifications.email_sender import send_exec_summary, send_se_report
from src.reports.exec_summary_report import build_exec_summary
from src.reports.se_monthly_report import build_se_report


REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "out"


def _se_report_html(se_name, month_label, score, percentile):
    return f"""
    <p>Hi {se_name.split()[0]},</p>
    <p>Your monthly demo coaching report for <b>{month_label}</b> is attached.</p>
    <p>Headline: <b>{score}/5</b> weighted score, approximately the <b>{percentile}th percentile</b> of B2B SaaS Solution Engineers this month.</p>
    <p>Open the attachment for your full scorecard, industry-benchmark gap analysis, top 3 strengths, top 3 areas of improvement, and your single coaching action for next month.</p>
    <p>Reply to this email if anything looks wrong — kaushik is on CC.</p>
    <p>— SurveySparrow SE Coaching Agent</p>
    """


def _exec_html(month_label, headline):
    return f"""
    <p>Hi,</p>
    <p>Attached is the <b>{month_label}</b> SE executive summary.</p>
    <p><i>{headline}</i></p>
    <p>The doc contains: top 5 product gaps, top 5 process gaps, AE quality risks, competitive intel, and 5 prioritized actions.</p>
    <p>— SurveySparrow SE Coaching Agent (kaushik)</p>
    """


def run_demo(live: bool = False, dry_run_email: bool = True):
    """End-to-end on bundled sample_data."""
    llm = LLMClient(live=live)
    calls = json.loads((REPO_ROOT / "sample_data" / "sample_calls.json").read_text())
    OUT.mkdir(exist_ok=True)

    all_scorecards = []
    all_insights = []

    for c in calls:
        transcript_path = REPO_ROOT / "sample_data" / c["transcript_file"]
        transcript = load_transcript_file(transcript_path)
        ctx = CallContext(
            se_name=c["se_name"], ae_name=c["ae_name"],
            prospect_company=c["prospect_company"], prospect_industry=c["prospect_industry"],
            stated_use_case=c["stated_use_case"], duration_min=c["duration_min"],
            transcript=transcript, call_id=c["call_id"],
        )
        print(f"\n=== Analyzing {c['call_id']}  ({c['se_name']} → {c['prospect_company']}) ===")
        sc = score_call(ctx, llm=llm)
        ins = extract_insights(ctx, llm=llm)
        all_scorecards.append(sc)
        all_insights.append(ins)
        print(f"  weighted={sc['weighted_final']}  P{sc['industry_percentile']}  "
              f"CX={ins['cx_maturity']['category']}  "
              f"AE_interruptions={ins['ae_behavior']['interruption_count']}")

    (OUT / "raw_scorecards.json").write_text(json.dumps(all_scorecards, indent=2))
    (OUT / "raw_insights.json").write_text(json.dumps(all_insights, indent=2))

    # === PER-SE REPORTS ===
    by_se: dict[str, list] = defaultdict(list)
    by_se_insights: dict[str, list] = defaultdict(list)
    se_email = {c["se_name"]: c["se_email"] for c in calls}
    for sc, ins in zip(all_scorecards, all_insights):
        by_se[sc["se_name"]].append(sc)
        by_se_insights[ins["se_name"]].append(ins)

    month_label = "May 2026"
    for se_name, sc_list in by_se.items():
        ins_list = by_se_insights[se_name]
        # mock trend — in prod, pull from DynamoDB
        history = [3.1, 3.3, sum(x["weighted_final"] for x in sc_list) / len(sc_list)]
        out_path = OUT / f"se_report_{se_name.lower().replace(' ', '_')}_{month_label.replace(' ', '_')}.docx"
        build_se_report(
            se_name=se_name, se_email=se_email[se_name],
            month_label=month_label, scorecards=sc_list,
            insights=ins_list, last_3_months_finals=history,
            output_path=str(out_path),
        )
        print(f"  → wrote {out_path.name}")
        avg = round(sum(s["weighted_final"] for s in sc_list)/len(sc_list), 2)
        pct = sc_list[0]["industry_percentile"]
        res = send_se_report(
            se_name=se_name, se_email=se_email[se_name],
            attachment_path=str(out_path),
            summary_html=_se_report_html(se_name, month_label, avg, pct),
            month_label=month_label, dry_run=dry_run_email,
        )
        print(f"  → email {res}")

    # === CEO EXEC SUMMARY ===
    summary = generate_exec_summary(month_label, all_insights, all_scorecards, llm=llm)
    (OUT / "exec_summary.json").write_text(json.dumps(summary, indent=2))
    exec_path = OUT / f"exec_summary_{month_label.replace(' ', '_')}.docx"
    build_exec_summary(month_label, summary, str(exec_path))
    print(f"\n=== Wrote CEO exec summary: {exec_path.name} ===")
    res = send_exec_summary(
        ceo_email="ceo@surveysparrow.example",
        attachment_path=str(exec_path),
        summary_html=_exec_html(month_label, summary["headline"]),
        month_label=month_label, dry_run=dry_run_email,
    )
    print(f"  → email {res}")


def cli():
    p = argparse.ArgumentParser()
    p.add_argument("--demo", action="store_true", help="Run on bundled sample data")
    p.add_argument("--live", action="store_true", help="Use real Claude API (requires ANTHROPIC_API_KEY)")
    p.add_argument("--send-real-emails", action="store_true", help="Send via SES (default: write .eml previews)")
    args = p.parse_args()
    if args.demo:
        run_demo(live=args.live, dry_run_email=not args.send_real_emails)
    else:
        p.print_help()


if __name__ == "__main__":
    cli()
