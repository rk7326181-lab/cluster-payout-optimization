"""
daily_fetch.py — run by GitHub Actions at 5 AM IST every day.
Fetches fresh cluster + hub data from BigQuery and saves to data/.
Requires: GOOGLE_APPLICATION_CREDENTIALS env var pointing to SA key file.
"""

import sys
import os
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "modules"))

from bigquery_client import (
    init_bq_client_from_service_account,
    fetch_live_clusters,
    fetch_hub_locations,
)
from data_loader import DataLoader

DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

sa_key = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
if not sa_key:
    print("ERROR: GOOGLE_APPLICATION_CREDENTIALS not set", file=sys.stderr)
    sys.exit(1)

print("Connecting to BigQuery…")
bq_client, err = init_bq_client_from_service_account(sa_key)
if err:
    print(f"ERROR: {err}", file=sys.stderr)
    sys.exit(1)

now = datetime.now()
print("Fetching cluster data…")
cl_df, err = fetch_live_clusters(bq_client, force_refresh=True)
if err:
    print(f"ERROR fetching clusters: {err}", file=sys.stderr)
    sys.exit(1)

print("Fetching hub locations…")
h_df, err = fetch_hub_locations(bq_client, now.year, now.month)
if err:
    print(f"ERROR fetching hubs: {err}", file=sys.stderr)
    sys.exit(1)

loader = DataLoader()
cl_df = loader._clean_cluster_data(cl_df)
h_df = loader._clean_hub_data(h_df)

date_str = now.strftime('%d%m%Y')
cl_path = DATA_DIR / f"clustering_live_{date_str}.csv"
h_path = DATA_DIR / f"hub_Lat_Long{date_str}.csv"

cl_df.to_csv(cl_path, index=False, encoding="utf-8")
h_df.to_csv(h_path, index=False, encoding="utf-8")
print(f"Saved: {cl_path.name} ({len(cl_df):,} rows), {h_path.name} ({len(h_df):,} rows)")

_, kep_path = loader.generate_kepler_csv(cl_df, h_df)
loader.save_cache_manifest(cl_path, h_path, kep_path)
print(f"Manifest updated. Done at {now.strftime('%Y-%m-%d %H:%M:%S')} UTC.")
