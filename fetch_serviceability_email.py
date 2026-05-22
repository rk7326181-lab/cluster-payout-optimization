"""
fetch_serviceability_email.py
─────────────────────────────
Fetches the latest "Updated LM Serviceable Pincode List" Excel from Gmail,
then enriches it with Hub IDs from BigQuery to produce a Hub | Hub ID | Pincode table.

Usage:
    python fetch_serviceability_email.py

On first run it will open a browser for Google OAuth (same account as BigQuery).
Credentials are cached at ~/.hub_cluster_optimizer_oauth_credentials.json.
"""

import os
import io
import base64
import json
import pickle
import re
from pathlib import Path
from datetime import datetime

import pandas as pd

# ── Google Auth ───────────────────────────────────────────────────────────────
from google.oauth2.credentials import Credentials as OAuthCredentials
from google.auth.transport.requests import Request as AuthRequest
from google_auth_oauthlib.flow import InstalledAppFlow

# Gmail + BigQuery scopes together so a single OAuth covers both
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/bigquery",
    "https://www.googleapis.com/auth/cloud-platform",
]

# Your GCP OAuth client credentials (Desktop app type)
# Download from: GCP Console → APIs & Services → Credentials → Create OAuth client ID
# Save as: config/credentials_oauth.json
_CREDS_FILE = Path(__file__).parent / "config" / "credentials_oauth.json"

def _get_oauth_client_config() -> dict:
    if not _CREDS_FILE.exists():
        raise FileNotFoundError(
            f"\nOAuth credentials file not found: {_CREDS_FILE}\n"
            "Steps to fix:\n"
            "  1. Go to console.cloud.google.com → project bi-team-400508\n"
            "  2. APIs & Services → Credentials → + Create Credentials → OAuth client ID\n"
            "  3. Type: Desktop app  →  Download JSON\n"
            "  4. Save as: config/credentials_oauth.json\n"
        )
    with open(_CREDS_FILE) as f:
        return json.load(f)

CREDENTIALS_CACHE = Path.home() / ".hub_cluster_optimizer_gmail_creds.json"

DATA_PROJECT_ID = "data-warehousing-391512"
PROJECT_ID = "bi-team-400508"

SENDER_EMAIL = "tripti.kumari0@shadowfax.in"
SUBJECT_KEYWORD = "Updated LM Serviceable Pincode List"

OUTPUT_DIR = Path(__file__).parent / "data"
OUTPUT_DIR.mkdir(exist_ok=True)


# ── Auth ──────────────────────────────────────────────────────────────────────

def _save_creds(creds):
    data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else SCOPES,
    }
    with open(CREDENTIALS_CACHE, "w") as f:
        json.dump(data, f)


def _load_creds():
    if not CREDENTIALS_CACHE.exists():
        return None
    try:
        with open(CREDENTIALS_CACHE) as f:
            data = json.load(f)
        creds = OAuthCredentials(
            token=data.get("token"),
            refresh_token=data.get("refresh_token"),
            token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=data.get("client_id"),
            client_secret=data.get("client_secret"),
            scopes=data.get("scopes", SCOPES),
        )
        # Check that Gmail scope is included
        saved_scopes = set(data.get("scopes", []))
        if "https://www.googleapis.com/auth/gmail.readonly" not in saved_scopes:
            return None  # Need to re-auth with Gmail scope
        if creds.expired and creds.refresh_token:
            creds.refresh(AuthRequest())
            _save_creds(creds)
        return creds if creds.valid else None
    except Exception:
        return None


def get_credentials():
    """Return valid OAuth credentials, triggering browser login if needed."""
    creds = _load_creds()
    if creds:
        print("✅ Using cached credentials")
        return creds

    print("🔐 Opening browser for Google login (Gmail + BigQuery access)...")
    flow = InstalledAppFlow.from_client_config(_get_oauth_client_config(), SCOPES)
    creds = flow.run_local_server(
        port=0,
        prompt="consent",
        success_message="Auth successful! Return to the terminal.",
    )
    _save_creds(creds)
    print("✅ Credentials saved")
    return creds


# ── Gmail fetch ───────────────────────────────────────────────────────────────

def fetch_latest_attachment(creds):
    """
    Searches Gmail for the latest email from SENDER_EMAIL with SUBJECT_KEYWORD.
    Returns (excel_bytes, filename) or raises if not found.
    """
    from googleapiclient.discovery import build

    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    query = f'from:{SENDER_EMAIL} subject:"{SUBJECT_KEYWORD}"'
    print(f"🔍 Searching Gmail: {query}")

    result = service.users().messages().list(userId="me", q=query, maxResults=10).execute()
    messages = result.get("messages", [])

    if not messages:
        raise RuntimeError(
            f"No emails found from {SENDER_EMAIL} with subject containing '{SUBJECT_KEYWORD}'"
        )

    # messages are newest-first
    latest_id = messages[0]["id"]
    msg = service.users().messages().get(userId="me", id=latest_id, format="full").execute()

    # Extract subject + date for logging
    headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
    print(f"📧 Found: '{headers.get('Subject', '')}' — {headers.get('Date', '')}")

    # Walk MIME parts looking for xlsx/xls attachment
    def _find_attachment(parts):
        for part in parts:
            if part.get("parts"):
                result = _find_attachment(part["parts"])
                if result:
                    return result
            filename = part.get("filename", "")
            if filename.lower().endswith((".xlsx", ".xls")):
                body = part.get("body", {})
                att_id = body.get("attachmentId")
                if att_id:
                    att = service.users().messages().attachments().get(
                        userId="me", messageId=latest_id, id=att_id
                    ).execute()
                    data = base64.urlsafe_b64decode(att["data"])
                    return data, filename
        return None

    parts = msg["payload"].get("parts", [msg["payload"]])
    found = _find_attachment(parts)
    if not found:
        raise RuntimeError("Email found but no Excel attachment detected")

    excel_bytes, filename = found
    print(f"📎 Attachment: {filename} ({len(excel_bytes):,} bytes)")
    return excel_bytes, filename


# ── Parse Excel ───────────────────────────────────────────────────────────────

def parse_serviceability_excel(excel_bytes):
    """
    Reads the Active_Pincode sheet from the serviceability Excel.
    Returns DataFrame with columns: hub_name, pincode.
    """
    wb_io = io.BytesIO(excel_bytes)
    df = pd.read_excel(wb_io, sheet_name="Active_Pincode", engine="openpyxl")

    # Standardise column names (file uses 'Hub' and 'Pincode')
    df.columns = [c.strip() for c in df.columns]
    hub_col = next((c for c in df.columns if c.lower() == "hub"), None)
    pin_col = next((c for c in df.columns if c.lower() == "pincode"), None)

    if not hub_col or not pin_col:
        raise ValueError(f"Expected 'Hub' and 'Pincode' columns, got: {list(df.columns)}")

    result = df[[hub_col, pin_col]].dropna()
    result = result.rename(columns={hub_col: "hub_name", pin_col: "pincode"})
    result["pincode"] = result["pincode"].apply(
        lambda x: str(int(float(x))) if str(x).replace(".", "", 1).isdigit() else str(x).strip()
    )
    print(f"📊 Parsed {len(result):,} rows, {result['hub_name'].nunique():,} unique hubs")
    return result


# ── BigQuery hub ID lookup ────────────────────────────────────────────────────

def fetch_hub_ids(creds):
    """
    Fetches id + name for all hubs from BigQuery ecommerce_hub table.
    Returns DataFrame with columns: hub_id, hub_name.
    """
    from google.cloud import bigquery

    print(f"🔗 Querying BigQuery for hub IDs...")
    client = bigquery.Client(project=PROJECT_ID, credentials=creds)

    query = f"""
    SELECT CAST(id AS STRING) AS hub_id, name AS hub_name
    FROM `{DATA_PROJECT_ID}.ecommerce.ecommerce_hub`
    WHERE name IS NOT NULL
    ORDER BY name
    """
    df = client.query(query).to_dataframe()
    print(f"✅ {len(df):,} hubs fetched from BigQuery")
    return df


# ── Main ──────────────────────────────────────────────────────────────────────

def run(skip_bq=False):
    """
    Full pipeline:
      1. Authenticate
      2. Fetch Excel from Gmail
      3. Parse hub → pincode data
      4. (Optional) Enrich with hub IDs from BigQuery
      5. Save outputs
    """
    creds = get_credentials()

    # Step 1 — fetch attachment
    excel_bytes, filename = fetch_latest_attachment(creds)

    # Save raw Excel
    date_str = datetime.now().strftime("%Y%m%d")
    raw_path = OUTPUT_DIR / f"serviceability_{date_str}.xlsx"
    raw_path.write_bytes(excel_bytes)
    print(f"💾 Saved raw Excel → {raw_path}")

    # Step 2 — parse
    pins_df = parse_serviceability_excel(excel_bytes)

    if skip_bq:
        out_path = OUTPUT_DIR / f"serviceability_hub_pincodes_{date_str}.csv"
        pins_df.to_csv(out_path, index=False)
        print(f"💾 Saved (no hub IDs) → {out_path}")
        return pins_df

    # Step 3 — enrich with hub IDs
    hubs_df = fetch_hub_ids(creds)

    merged = pins_df.merge(hubs_df, on="hub_name", how="left")
    merged = merged[["hub_name", "hub_id", "pincode"]]

    matched = merged["hub_id"].notna().sum()
    unmatched = merged["hub_id"].isna().sum()
    print(f"✅ Matched: {matched:,} rows | ⚠️  Unmatched (no BQ hub ID): {unmatched:,} rows")

    # Save final output
    out_path = OUTPUT_DIR / f"serviceability_with_hub_ids_{date_str}.csv"
    merged.to_csv(out_path, index=False)
    print(f"💾 Saved final table → {out_path}")

    # Preview
    print("\n── Preview (first 10 rows) ─────────────────────────────")
    print(merged.head(10).to_string(index=False))

    # Summary per hub
    summary = (
        merged.groupby(["hub_name", "hub_id"])
        .agg(pincode_count=("pincode", "count"))
        .reset_index()
        .sort_values("hub_name")
    )
    summary_path = OUTPUT_DIR / f"serviceability_hub_summary_{date_str}.csv"
    summary.to_csv(summary_path, index=False)
    print(f"\n💾 Hub summary → {summary_path}")
    print(f"   Total hubs: {len(summary)}, Total pincodes: {summary['pincode_count'].sum():,}")

    return merged


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fetch Shadowfax serviceability file from Gmail")
    parser.add_argument("--skip-bq", action="store_true", help="Skip BigQuery hub ID lookup")
    args = parser.parse_args()

    run(skip_bq=args.skip_bq)
