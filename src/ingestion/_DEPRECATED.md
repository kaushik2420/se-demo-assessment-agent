# Deprecated ingestion paths

As of the May 2026 architecture revision, **Granola is the single source of truth**
for SE call transcripts. The following clients are retained as fallback options
only:

| File                | Status                                                                    |
| ------------------- | ------------------------------------------------------------------------- |
| `recall_bot.py`     | Deprecated. Use only if Granola adoption stalls or for non-SE recordings. |
| `avoma_client.py`   | Deprecated. Keep available for legacy backfill of pre-Granola calls.      |
| `hubspot_client.py` | Active — used for deal/account attribution only, not transcript fetching. |
| `granola_client.py` | **Active — primary ingestion path.**                                      |
| `manual_upload.py`  | **Active — safety net via the SE portal when Granola misses a call.**     |

Migration note: when SurveySparrow mandates Granola org-wide, remove
`recall_bot.py` and `avoma_client.py` from `requirements.txt`-pinned imports
and delete the Terraform resources for Recall.ai webhook handling.
