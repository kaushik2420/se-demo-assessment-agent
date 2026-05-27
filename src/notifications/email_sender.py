"""
Send monthly reports via AWS SES.

Behavior:
  - SE monthly report: TO=se_email, CC=kaushikn2416@gmail.com, attach .docx
  - CEO exec summary: TO=ceo_email, CC=kaushikn2416@gmail.com, attach .docx

In local mode (no AWS creds), we just write the email payload to ./out/emails/
so kaushik can preview before going live.
"""

from __future__ import annotations

import json
import os
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional


def _build_message(
    sender: str, to: str, cc: str, subject: str, body_html: str, attachment_path: str
) -> MIMEMultipart:
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg["Cc"] = cc
    msg.attach(MIMEText(body_html, "html"))
    with open(attachment_path, "rb") as f:
        part = MIMEApplication(f.read())
    part.add_header("Content-Disposition", "attachment", filename=Path(attachment_path).name)
    msg.attach(part)
    return msg


def send_se_report(
    se_name: str, se_email: str, attachment_path: str, summary_html: str,
    month_label: str, dry_run: Optional[bool] = None,
) -> dict:
    sender = os.getenv("SES_FROM_EMAIL", "coaching@surveysparrow.com")
    cc = os.getenv("SES_CC_EMAIL", "kaushikn2416@gmail.com")
    subject = f"[Monthly Coaching] {se_name} — Demo performance, {month_label}"
    msg = _build_message(sender, se_email, cc, subject, summary_html, attachment_path)

    if dry_run is None:
        dry_run = not os.getenv("AWS_REGION")
    if dry_run:
        out = Path("out/emails") / f"se_{se_name.lower().replace(' ', '_')}_{month_label}.eml"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(bytes(msg))
        return {"dry_run": True, "saved_to": str(out)}

    import boto3
    ses = boto3.client("ses", region_name=os.getenv("AWS_REGION"))
    r = ses.send_raw_email(
        Source=sender, Destinations=[se_email, cc], RawMessage={"Data": msg.as_string()},
    )
    return {"dry_run": False, "message_id": r["MessageId"]}


def send_exec_summary(
    ceo_email: str, attachment_path: str, summary_html: str, month_label: str,
    dry_run: Optional[bool] = None,
) -> dict:
    sender = os.getenv("SES_FROM_EMAIL", "coaching@surveysparrow.com")
    cc = os.getenv("SES_CC_EMAIL", "kaushikn2416@gmail.com")
    subject = f"[SE Executive Summary] {month_label} — process & product gaps"
    msg = _build_message(sender, ceo_email, cc, subject, summary_html, attachment_path)

    if dry_run is None:
        dry_run = not os.getenv("AWS_REGION")
    if dry_run:
        out = Path("out/emails") / f"exec_summary_{month_label}.eml"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(bytes(msg))
        return {"dry_run": True, "saved_to": str(out)}

    import boto3
    ses = boto3.client("ses", region_name=os.getenv("AWS_REGION"))
    r = ses.send_raw_email(
        Source=sender, Destinations=[ceo_email, cc], RawMessage={"Data": msg.as_string()},
    )
    return {"dry_run": False, "message_id": r["MessageId"]}
