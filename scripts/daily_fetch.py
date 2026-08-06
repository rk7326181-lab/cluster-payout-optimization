"""
daily_fetch.py — run by GitHub Actions at 5 AM IST every day.
Fetches fresh cluster + hub data from BigQuery and saves to data/.

Requirements (set in GitHub Actions secrets):
  BQ_SERVICE_ACCOUNT_JSON — contents of the service account JSON key file.

Usage:
  python scripts/daily_fetch.py
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "modules"))

# ── Validate credentials are available ────────────────────────────────
sa_key_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/sa_key.json")
if not Path(sa_key_path).exists():
    print(
        "ERROR: Service account key file not found.\n"
        "  Make sure BQ_SERVICE_ACCOUNT_JSON secret is set in GitHub Settings → Secrets.",
        file=sys.stderr,
    )
    sys.exit(1)

# ── Load the key JSON ──────────────────────────────────────────────────
try:
    with open(sa_key_path) as f:
        creds_dict = json.load(f)
    # Sanity-check it's a real service account key (not an empty file)
    if not creds_dict.get("client_email"):
        raise ValueError("Key file appears empty or invalid — is BQ_SERVICE_ACCOUNT_JSON set?")
except Exception as e:
    print(f"ERROR reading service account key: {e}", file=sys.stderr)
    sys.exit(1)

# ── Connect to BigQuery ────────────────────────────────────────────────
from bigquery_client import connect_with_service_account, fetch_live_clusters, fetch_hub_locations
from data_loader import DataLoader

print("Connecting to BigQuery …")
bq_client, err = connect_with_service_account(creds_dict)
if err or bq_client is None:
    print(f"ERROR: could not connect to BigQuery: {err}", file=sys.stderr)
    sys.exit(1)
print("Connected.")

# ── Fetch data ─────────────────────────────────────────────────────────
now = datetime.now()

print("Fetching cluster data …")
cl_df, err = fetch_live_clusters(bq_client, force_refresh=True)
if err:
    print(f"ERROR fetching clusters: {err}", file=sys.stderr)
    sys.exit(1)
print(f"  → {len(cl_df):,} cluster rows")

print("Fetching hub locations …")
h_df, err = fetch_hub_locations(bq_client, now.year, now.month)
if err:
    print(f"ERROR fetching hubs: {err}", file=sys.stderr)
    sys.exit(1)
print(f"  → {len(h_df):,} hub rows")

# ── Clean and save ─────────────────────────────────────────────────────
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

loader = DataLoader()
cl_df = loader._clean_cluster_data(cl_df)
h_df = loader._clean_hub_data(h_df)

date_str = now.strftime('%d%m%Y')
cl_path = DATA_DIR / f"clustering_live_{date_str}.csv"
h_path  = DATA_DIR / f"hub_Lat_Long{date_str}.csv"

cl_df.to_csv(cl_path, index=False, encoding="utf-8")
h_df.to_csv(h_path, index=False, encoding="utf-8")
print(f"Saved: {cl_path.name}, {h_path.name}")

_, kep_path = loader.generate_kepler_csv(cl_df, h_df)
loader.save_cache_manifest(cl_path, h_path, kep_path)
print(f"Manifest updated. Done at {now.strftime('%Y-%m-%d %H:%M:%S')} UTC.")
