"""
serviceability_fetcher.py
─────────────────────────
Streamlit-friendly wrapper around fetch_serviceability_email.py.
Handles Gmail OAuth, attachment download, Excel parsing, and BigQuery
hub ID enrichment — all callable from the Data tab.
"""

import io
import json
import base64
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st

# ── Config ────────────────────────────────────────────────────────────────────

DATA_PROJECT_ID = "data-warehousing-391512"
PROJECT_ID      = "bi-team-400508"

SENDER_EMAIL    = "tripti.kumari0@shadowfax.in"
SUBJECT_KEYWORD = "Updated LM Serviceable Pincode List"

GMAIL_CREDS_CACHE = Path.home() / ".hub_cluster_optimizer_gmail_creds.json"

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/bigquery",
    "https://www.googleapis.com/auth/cloud-platform",
]

_CREDS_FILE = Path(__file__).parent.parent / "config" / "credentials_oauth.json"

def _load_oauth_client_config() -> dict:
    """
    Load OAuth client config from config/credentials_oauth.json.
    This file is downloaded from GCP Console → APIs & Services → Credentials
    → Create OAuth client ID (Desktop app) → Download JSON.
    """
    if not _CREDS_FILE.exists():
        raise FileNotFoundError(
            f"OAuth credentials file not found: {_CREDS_FILE}\n"
            "Download it from GCP Console → APIs & Services → Credentials → "
            "Create OAuth client ID (Desktop app) → Download JSON, "
            "and save it as config/credentials_oauth.json"
        )
    with open(_CREDS_FILE) as f:
        return json.load(f)


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _save_gmail_creds(creds):
    data = {
        "token":         creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri":     creds.token_uri,
        "client_id":     creds.client_id,
        "client_secret": creds.client_secret,
        "scopes":        list(creds.scopes) if creds.scopes else GMAIL_SCOPES,
    }
    with open(GMAIL_CREDS_CACHE, "w") as f:
        json.dump(data, f)


def _load_gmail_creds():
    """Load cached Gmail creds. Returns None if missing or no gmail.readonly scope."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        if not GMAIL_CREDS_CACHE.exists():
            return None

        with open(GMAIL_CREDS_CACHE) as f:
            data = json.load(f)

        saved_scopes = set(data.get("scopes", []))
        if "https://www.googleapis.com/auth/gmail.readonly" not in saved_scopes:
            return None  # Need re-auth to add Gmail scope

        creds = Credentials(
            token=data.get("token"),
            refresh_token=data.get("refresh_token"),
            token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=data.get("client_id"),
            client_secret=data.get("client_secret"),
            scopes=data.get("scopes", GMAIL_SCOPES),
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save_gmail_creds(creds)
        return creds if creds.valid else None
    except Exception:
        return None


def has_gmail_auth() -> bool:
    """True if valid Gmail OAuth credentials are cached."""
    return _load_gmail_creds() is not None


def connect_gmail() -> tuple:
    """
    Run Google OAuth for Gmail + BigQuery scopes using your own GCP OAuth client.
    Opens browser. Returns (creds, error_msg).
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        client_config = _load_oauth_client_config()
        flow = InstalledAppFlow.from_client_config(client_config, GMAIL_SCOPES)
        creds = flow.run_local_server(
            port=0,
            prompt="consent",
            success_message="Auth successful! Return to the Streamlit app.",
        )
        _save_gmail_creds(creds)
        return creds, None
    except FileNotFoundError as e:
        return None, str(e)
    except Exception as e:
        return None, str(e)


# ── Gmail fetch ───────────────────────────────────────────────────────────────

def fetch_attachment_from_gmail(creds) -> tuple:
    """
    Find the latest email from SENDER_EMAIL with SUBJECT_KEYWORD.
    Returns (excel_bytes, filename, subject_line) or raises.
    """
    from googleapiclient.discovery import build

    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    query = f'from:{SENDER_EMAIL} subject:"{SUBJECT_KEYWORD}"'

    result = service.users().messages().list(userId="me", q=query, maxResults=10).execute()
    messages = result.get("messages", [])

    if not messages:
        raise RuntimeError(
            f"No emails found from **{SENDER_EMAIL}** with subject containing "
            f"**{SUBJECT_KEYWORD}**. Check that the email has arrived in your inbox."
        )

    latest_id = messages[0]["id"]
    msg = service.users().messages().get(userId="me", id=latest_id, format="full").execute()

    headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
    subject = headers.get("Subject", "")
    date    = headers.get("Date", "")

    def _find_xlsx(parts):
        for part in parts:
            if part.get("parts"):
                found = _find_xlsx(part["parts"])
                if found:
                    return found
            fname = part.get("filename", "")
            if fname.lower().endswith((".xlsx", ".xls")):
                att_id = part.get("body", {}).get("attachmentId")
                if att_id:
                    att = service.users().messages().attachments().get(
                        userId="me", messageId=latest_id, id=att_id
                    ).execute()
                    return base64.urlsafe_b64decode(att["data"]), fname
        return None

    parts = msg["payload"].get("parts", [msg["payload"]])
    found = _find_xlsx(parts)
    if not found:
        raise RuntimeError(
            f"Email found (**{subject}**) but no Excel attachment detected."
        )

    excel_bytes, filename = found
    return excel_bytes, filename, subject, date


# ── Excel parser ──────────────────────────────────────────────────────────────

def parse_serviceability_excel(excel_bytes: bytes) -> pd.DataFrame:
    """
    Reads Active_Pincode sheet. Returns DataFrame: hub_name, pincode.
    """
    df = pd.read_excel(io.BytesIO(excel_bytes), sheet_name="Active_Pincode", engine="openpyxl")
    df.columns = [c.strip() for c in df.columns]

    hub_col = next((c for c in df.columns if c.lower() == "hub"), None)
    pin_col = next((c for c in df.columns if c.lower() == "pincode"), None)

    if not hub_col or not pin_col:
        raise ValueError(f"Expected 'Hub' and 'Pincode' columns, got: {list(df.columns)}")

    result = df[[hub_col, pin_col]].dropna().rename(
        columns={hub_col: "hub_name", pin_col: "pincode"}
    )
    result["pincode"] = result["pincode"].apply(
        lambda x: str(int(float(x))) if str(x).replace(".", "", 1).isdigit() else str(x).strip()
    )
    return result.reset_index(drop=True)


# ── BigQuery hub ID lookup ────────────────────────────────────────────────────

def fetch_hub_ids_from_bq(bq_client) -> pd.DataFrame:
    """
    Pulls id + name from ecommerce_hub. Returns DataFrame: hub_id, hub_name.
    """
    query = f"""
    SELECT CAST(id AS STRING) AS hub_id, name AS hub_name
    FROM `{DATA_PROJECT_ID}.ecommerce.ecommerce_hub`
    WHERE name IS NOT NULL
    ORDER BY name
    """
    df = bq_client.query(query).to_dataframe()
    return df


# ── Full pipeline ─────────────────────────────────────────────────────────────

def run_full_pipeline(bq_client=None, status_cb=None) -> tuple:
    """
    End-to-end: Gmail fetch → parse → BQ hub ID enrichment.
    status_cb(msg): called with progress strings.
    Returns (merged_df, summary_df, metadata_dict, error_str).
    """
    def _log(msg):
        if status_cb:
            status_cb(msg)

    try:
        # Step 1 — auth
        _log("Authenticating with Gmail...")
        creds = _load_gmail_creds()
        if not creds:
            _log("Opening browser for Google login...")
            creds, err = connect_gmail()
            if err:
                return None, None, None, f"OAuth failed: {err}"

        # Step 2 — fetch email
        _log(f"Searching Gmail for emails from {SENDER_EMAIL}...")
        excel_bytes, filename, subject, date = fetch_attachment_from_gmail(creds)
        _log(f"Found: **{subject}** ({date})")

        # Step 3 — save raw file
        out_dir = Path(__file__).parent.parent / "data"
        out_dir.mkdir(exist_ok=True)
        date_str = datetime.now().strftime("%Y%m%d")
        raw_path = out_dir / f"serviceability_{date_str}.xlsx"
        raw_path.write_bytes(excel_bytes)
        _log(f"Saved raw file to `{raw_path.name}`")

        # Step 4 — parse Excel
        _log("Parsing Active_Pincode sheet...")
        pins_df = parse_serviceability_excel(excel_bytes)
        n_hubs = pins_df["hub_name"].nunique()
        n_pins = len(pins_df)
        _log(f"Parsed **{n_pins:,}** pincode rows across **{n_hubs:,}** hubs")

        # Step 5 — BQ hub IDs
        merged_df = pins_df.copy()
        matched, unmatched = n_pins, 0

        if bq_client is not None:
            _log("Fetching hub IDs from BigQuery...")
            hubs_df = fetch_hub_ids_from_bq(bq_client)
            merged_df = pins_df.merge(hubs_df, on="hub_name", how="left")
            merged_df = merged_df[["hub_name", "hub_id", "pincode"]]
            matched   = merged_df["hub_id"].notna().sum()
            unmatched = merged_df["hub_id"].isna().sum()
            _log(f"Matched **{matched:,}** rows with hub IDs. Unmatched: {unmatched:,}")
        else:
            merged_df["hub_id"] = None
            _log("Skipped hub ID lookup (no BigQuery connection)")

        # Step 6 — summary
        summary_df = (
            merged_df.groupby(["hub_name", "hub_id"], dropna=False)
            .agg(pincode_count=("pincode", "count"))
            .reset_index()
            .sort_values("hub_name")
        )

        # Save outputs
        full_path    = out_dir / f"serviceability_with_hub_ids_{date_str}.csv"
        summary_path = out_dir / f"serviceability_hub_summary_{date_str}.csv"
        merged_df.to_csv(full_path,    index=False)
        summary_df.to_csv(summary_path, index=False)

        metadata = {
            "subject":    subject,
            "email_date": date,
            "filename":   filename,
            "total_rows": n_pins,
            "total_hubs": n_hubs,
            "matched":    int(matched),
            "unmatched":  int(unmatched),
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "full_path":  str(full_path),
        }
        _log("Done.")
        return merged_df, summary_df, metadata, None

    except Exception as e:
        return None, None, None, str(e)
