"""
BigQuery Client for Hub Cluster Optimizer V2
Auth priority: ADC -> Cached Google OAuth -> Service Account JSON -> Manual Google Login.
Ported from clustering_app's bigquery_client.py — same queries, same auth methods.
"""
import os
import json
import time
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime
from pathlib import Path

try:
    import duckdb
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False

try:
    from google.cloud import bigquery
    from google.api_core.exceptions import GoogleAPIError
    HAS_BQ = True
except ImportError:
    HAS_BQ = False

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.oauth2.credentials import Credentials as OAuthCredentials
    from google.auth.transport.requests import Request as AuthRequest
    HAS_OAUTH = True
except ImportError:
    HAS_OAUTH = False


PROJECT_ID = "bi-team-400508"
DATA_PROJECT_ID = "data-warehousing-391512"

# Daily cache files
LIVE_CLUSTERS_CACHE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data", "live_clusters_cache.json"
)
AWB_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data", "awb_cache"
)

# Google OAuth scopes for BigQuery
OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/bigquery",
    "https://www.googleapis.com/auth/cloud-platform",
]

# Google Cloud SDK's built-in OAuth client (public, used by gcloud CLI)
OAUTH_CLIENT_CONFIG = {
    "installed": {
        "client_id": "764086051850-6qr4p6gpi6hn506pt8ejuq83di341hur.apps.googleusercontent.com",
        "client_secret": "d-FL95Q19q7MQmFpd7hHD0Ty",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}

# Cache file for OAuth credentials (persists across sessions)
CREDENTIALS_CACHE = os.path.join(
    os.path.expanduser("~"), ".hub_cluster_optimizer_oauth_credentials.json"
)


# ════════════════════════════════════════════════════
# OAUTH HELPERS — credential persistence
# ════════════════════════════════════════════════════

def _save_oauth_credentials(creds):
    """Save OAuth credentials to disk for reuse across sessions."""
    data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else OAUTH_SCOPES,
    }
    with open(CREDENTIALS_CACHE, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _load_cached_oauth_credentials():
    """Load cached OAuth credentials if available and still valid."""
    if not HAS_OAUTH or not os.path.exists(CREDENTIALS_CACHE):
        return None
    try:
        with open(CREDENTIALS_CACHE, "r", encoding="utf-8") as f:
            data = json.load(f)
        creds = OAuthCredentials(
            token=data.get("token"),
            refresh_token=data.get("refresh_token"),
            token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=data.get("client_id"),
            client_secret=data.get("client_secret"),
            scopes=data.get("scopes", OAUTH_SCOPES),
        )
        # Refresh if expired
        if creds.expired and creds.refresh_token:
            creds.refresh(AuthRequest())
            _save_oauth_credentials(creds)
        if creds.valid:
            return creds
        return None
    except Exception:
        return None


def clear_oauth_credentials():
    """Remove cached OAuth credentials (logout)."""
    if os.path.exists(CREDENTIALS_CACHE):
        os.remove(CREDENTIALS_CACHE)


# ════════════════════════════════════════════════════
# AUTH — ADC -> Cached OAuth -> Service Account -> Manual Login
# ════════════════════════════════════════════════════

def auto_connect():
    """
    Try ADC first, then cached OAuth credentials.
    Returns (client, auth_mode, error_msg).
    auth_mode: "adc" | "google_oauth" | "streamlit_secrets" | "needs_key" | None
    """
    if not HAS_BQ:
        return None, None, "google-cloud-bigquery not installed. Run: pip install google-cloud-bigquery"

    # Option S1 — Streamlit secrets: OAuth refresh token (Gmail login, no JSON key needed)
    try:
        if HAS_OAUTH and "google_oauth" in st.secrets:
            s = st.secrets["google_oauth"]
            creds = OAuthCredentials(
                token=None,
                refresh_token=s["refresh_token"],
                token_uri=s.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=s["client_id"],
                client_secret=s["client_secret"],
                scopes=["https://www.googleapis.com/auth/bigquery",
                        "https://www.googleapis.com/auth/cloud-platform"],
            )
            creds.refresh(AuthRequest())
            client = bigquery.Client(project=PROJECT_ID, credentials=creds)
            client.query(f"SELECT 1 FROM `{DATA_PROJECT_ID}.ecommerce.ecommerce_hub` LIMIT 1").result(timeout=10)
            return client, "streamlit_oauth", None
    except Exception:
        pass

    # Option S2 — Streamlit secrets: service account JSON (gcp_service_account section)
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            client = bigquery.Client.from_service_account_info(creds_dict, project=PROJECT_ID)
            client.query(f"SELECT 1 FROM `{DATA_PROJECT_ID}.ecommerce.ecommerce_hub` LIMIT 1").result(timeout=10)
            return client, "streamlit_secrets", None
    except Exception:
        pass

    # Option B — Cached Google OAuth credentials (try first — fast check)
    try:
        creds = _load_cached_oauth_credentials()
        if creds:
            client = bigquery.Client(project=PROJECT_ID, credentials=creds)
            client.query(f"SELECT 1 FROM `{DATA_PROJECT_ID}.ecommerce.ecommerce_hub` LIMIT 1").result(timeout=10)
            return client, "google_oauth", None
    except Exception:
        pass

    # Option A — Application Default Credentials (gcloud auth)
    # Only try if GOOGLE_APPLICATION_CREDENTIALS is set (avoids slow metadata server timeout)
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        try:
            client = bigquery.Client(project=PROJECT_ID)
            client.query(f"SELECT 1 FROM `{DATA_PROJECT_ID}.ecommerce.ecommerce_hub` LIMIT 1").result(timeout=10)
            return client, "adc", None
        except Exception:
            pass

    return None, "needs_key", None


def connect_with_service_account(creds_dict):
    """
    Option C — Service account JSON upload.
    Returns (client, error_msg).
    """
    if not HAS_BQ:
        return None, "google-cloud-bigquery not installed."
    try:
        client = bigquery.Client.from_service_account_info(creds_dict, project=PROJECT_ID)
        return client, None
    except Exception as e:
        return None, str(e)


def is_cloud_environment() -> bool:
    """Detect if running on Streamlit Cloud or any headless server (no browser available)."""
    # Streamlit Community Cloud sets HOME=/home/appuser
    if os.environ.get("HOME") == "/home/appuser":
        return True
    # No DISPLAY on Linux = headless
    if os.name != "nt" and not os.environ.get("DISPLAY"):
        return True
    # Try finding a browser — if none found, we're headless
    try:
        import webbrowser
        webbrowser.get()
        return False
    except Exception:
        return True


def connect_with_google_oauth():
    """
    Option D — Google OAuth login. Opens browser for Google sign-in.
    On cloud/headless environments, returns an instructional error instead.
    Returns (client, error_msg).
    """
    if not HAS_BQ:
        return None, "google-cloud-bigquery not installed."
    if not HAS_OAUTH:
        return None, "google-auth-oauthlib not installed. Run: pip install google-auth-oauthlib"

    # On Streamlit Cloud, browser-based OAuth is not possible.
    # BigQuery should connect automatically via st.secrets["google_oauth"].
    if is_cloud_environment():
        return None, (
            "CLOUD_ENV: Browser login is not available on Streamlit Cloud. "
            "BigQuery connects automatically via your saved Google credentials in Secrets. "
            "Go to app Settings → Secrets and make sure the [google_oauth] section is saved correctly."
        )

    try:
        flow = InstalledAppFlow.from_client_config(OAUTH_CLIENT_CONFIG, OAUTH_SCOPES)
        creds = flow.run_local_server(
            port=0,
            prompt="consent",
            success_message=(
                "Authentication successful! You can close this tab and return to the Streamlit app."
            ),
        )
        _save_oauth_credentials(creds)
        client = bigquery.Client(project=PROJECT_ID, credentials=creds)
        return client, None
    except Exception as e:
        return None, str(e)


def init_bq_on_startup():
    """
    Called once on app startup. Tries ADC then cached OAuth silently.
    Sets st.session_state.bq_client and st.session_state.bq_auth_mode.
    """
    if st.session_state.get("bq_client") is not None:
        return  # Already connected

    client, mode, err = auto_connect()
    if client:
        st.session_state["bq_client"] = client
        st.session_state["bq_auth_mode"] = mode
    else:
        st.session_state["bq_auth_mode"] = "needs_key"


def handle_service_account_upload(uploaded_file):
    """Process uploaded JSON key file. Returns (success, error_msg)."""
    try:
        creds_dict = json.load(uploaded_file)
        client, err = connect_with_service_account(creds_dict)
        if err:
            return False, err
        st.session_state["bq_client"] = client
        st.session_state["bq_auth_mode"] = "service_account"
        st.session_state["bq_credentials"] = creds_dict
        return True, None
    except Exception as e:
        return False, str(e)


def handle_google_oauth_login():
    """Run Google OAuth login flow. Returns (success, error_msg)."""
    client, err = connect_with_google_oauth()
    if err:
        return False, err
    st.session_state["bq_client"] = client
    st.session_state["bq_auth_mode"] = "google_oauth"
    return True, None


# ════════════════════════════════════════════════════
# CACHE — Daily cache for live clusters
# ════════════════════════════════════════════════════

def _get_live_clusters_cache():
    """Load cached live clusters if cache exists and was fetched today."""
    try:
        if not os.path.exists(LIVE_CLUSTERS_CACHE_FILE):
            return None
        with open(LIVE_CLUSTERS_CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        fetched_date = cache.get("fetched_date", "")
        today = datetime.now().strftime("%Y-%m-%d")
        if fetched_date != today:
            return None  # Cache is stale
        df = pd.DataFrame(cache["data"])
        return df
    except Exception:
        return None


def _save_live_clusters_cache(df):
    """Save live clusters data to local cache with today's date."""
    try:
        cache_dir = os.path.dirname(LIVE_CLUSTERS_CACHE_FILE)
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)
        cache = {
            "fetched_date": datetime.now().strftime("%Y-%m-%d"),
            "fetched_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "record_count": len(df),
            "data": df.to_dict(orient="records")
        }
        with open(LIVE_CLUSTERS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, default=str, ensure_ascii=False)
    except Exception as e:
        print(f"Cache save error: {e}")


# ════════════════════════════════════════════════════
# BigQuery Job Status Polling
# ════════════════════════════════════════════════════

def _format_bytes(n):
    """Human-readable byte size."""
    if n is None:
        return "—"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _poll_query_job(query_job, progress_cb, base_pct=0.10, end_pct=0.75, label=""):
    """
    Poll a BigQuery QueryJob until it completes.
    Sends real-time status via progress_cb(pct, message).
    Returns the completed job.
    """
    if not progress_cb:
        query_job.result(timeout=600)
        return query_job

    poll_interval = 1.5
    elapsed = 0.0
    prev_state = None

    while True:
        query_job.reload()
        state = query_job.state  # PENDING → RUNNING → DONE

        # Build status message
        stats = query_job.query_plan or []
        bytes_processed = query_job.total_bytes_processed
        bytes_billed = query_job.total_bytes_billed
        slot_millis = getattr(query_job, "slot_millis", None)

        # Count completed vs total stages
        completed_stages = sum(1 for s in stats if s.status == "COMPLETE") if stats else 0
        total_stages = len(stats) if stats else 0

        # Progress estimation within our range
        if state == "DONE":
            pct = end_pct
        elif total_stages > 0:
            stage_ratio = completed_stages / total_stages
            pct = base_pct + (end_pct - base_pct) * stage_ratio * 0.9
        else:
            # No plan yet, slow tick
            pct = min(base_pct + elapsed * 0.003, end_pct - 0.05)

        # Build detail line
        parts = [f"{label}" if label else ""]
        if state == "PENDING":
            parts.append("⏳ Queued — waiting for slot allocation...")
        elif state == "RUNNING":
            parts.append("⚙️ Running query")
            if total_stages:
                parts.append(f"({completed_stages}/{total_stages} stages)")
            if bytes_processed:
                parts.append(f"• {_format_bytes(bytes_processed)} scanned")
            if slot_millis:
                parts.append(f"• {slot_millis / 1000:.0f}s slot time")
        elif state == "DONE":
            parts.append("✅ Query complete")
            if bytes_processed:
                parts.append(f"• {_format_bytes(bytes_processed)} scanned")
            if bytes_billed:
                parts.append(f"• {_format_bytes(bytes_billed)} billed")

        msg = " ".join(p for p in parts if p)
        progress_cb(pct, msg)

        if state == "DONE":
            if query_job.error_result:
                raise Exception(f"BigQuery job failed: {query_job.error_result}")
            break

        time.sleep(poll_interval)
        elapsed += poll_interval
        # Slow down polling after 30s
        if elapsed > 30:
            poll_interval = min(poll_interval + 0.5, 5.0)

    return query_job


# ════════════════════════════════════════════════════
# FETCH — Live Clusters & Hub Locations
# ════════════════════════════════════════════════════

def fetch_live_clusters(client, force_refresh=False, progress_cb=None):
    """Fetch active payout clusters. Uses daily cache — only queries BigQuery once per day."""
    # Check cache first
    if not force_refresh:
        cached = _get_live_clusters_cache()
        if cached is not None:
            if progress_cb:
                progress_cb(0.35, "✅ Loaded clusters from cache")
            return cached, None

    # Cache miss or stale — query BigQuery
    try:
        query = """
        SELECT gc.id, gc.created, gc.modified, gc.hub_id,
            eh.name AS hub_name, gc.cluster_code, gc.description,
            gc.boundary, gc.is_active, gc.cluster_category,
            gc.cluster_type, gc.pincode, gc.surge_amount
        FROM `data-warehousing-391512.ecommerce.geocode_geoclusters` gc
        LEFT JOIN `data-warehousing-391512.ecommerce.ecommerce_hub` eh
            ON gc.hub_id = eh.id
        WHERE is_active = TRUE
            AND cluster_type = "payout_cluster"
        """
        if progress_cb:
            progress_cb(0.10, "📡 Submitting cluster query...")
        query_job = client.query(query)

        _poll_query_job(query_job, progress_cb, base_pct=0.10, end_pct=0.30, label="Clusters")

        if progress_cb:
            progress_cb(0.32, "⬇️ Downloading cluster results...")
        result = query_job.to_dataframe()

        # Save to cache
        _save_live_clusters_cache(result)
        if progress_cb:
            progress_cb(0.35, f"✅ {len(result):,} clusters fetched")
        return result, None
    except GoogleAPIError as e:
        return None, f"BigQuery API Error: {e}"
    except Exception as e:
        return None, f"Error: {e}"


def fetch_hub_locations(client, year, month, progress_cb=None):
    """Fetch hub locations with year/month."""
    try:
        query = f"""
        SELECT eh.creation_date, eh.id, eh.name,
            COALESCE(ehl.latitude, eh.latitude) AS latitude,
            COALESCE(ehl.longitude, eh.longitude) AS longitude,
            eh.hub_category
        FROM `{DATA_PROJECT_ID}.ecommerce.ecommerce_hub` eh
        LEFT JOIN `{DATA_PROJECT_ID}.analytics_tables.ecommerce_hub_locations` ehl
            ON eh.id = ehl.hub_id
            AND ehl.year = {year}
            AND ehl.month = {month}
        """
        if progress_cb:
            progress_cb(0.38, "📡 Submitting hub locations query...")
        query_job = client.query(query)

        _poll_query_job(query_job, progress_cb, base_pct=0.38, end_pct=0.55, label="Hubs")

        if progress_cb:
            progress_cb(0.56, "⬇️ Downloading hub results...")
        result = query_job.to_dataframe()

        if progress_cb:
            progress_cb(0.60, f"✅ {len(result):,} hub locations fetched")
        return result, None
    except GoogleAPIError as e:
        return None, f"BigQuery API Error: {e}"
    except Exception as e:
        return None, f"Error: {e}"


# ════════════════════════════════════════════════════
# AWB DATA — Query, Fetch, Cache
# ════════════════════════════════════════════════════

def _get_awb_cache_path(hub_id=None):
    """Get the AWB cache CSV path. If hub_id given, per-hub file; else global."""
    os.makedirs(AWB_CACHE_DIR, exist_ok=True)
    if hub_id:
        return os.path.join(AWB_CACHE_DIR, f"awb_hub_{hub_id}.csv")
    return os.path.join(AWB_CACHE_DIR, "awb_all.csv")


def _get_awb_cache_meta_path():
    return os.path.join(AWB_CACHE_DIR, "awb_cache_meta.json")


def get_awb_cache_info():
    """Return cache metadata (date fetched, row count) or None."""
    meta_path = _get_awb_cache_meta_path()
    if not os.path.exists(meta_path):
        return None
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def load_awb_from_cache():
    """Load AWB data from disk cache. Returns DataFrame or None."""
    # Try parquet first (fast), fall back to CSV
    cache_parquet = _get_awb_cache_path().replace(".csv", ".parquet")
    cache_csv = _get_awb_cache_path()
    if os.path.exists(cache_parquet):
        try:
            return pd.read_parquet(cache_parquet)
        except Exception:
            # BigQuery parquet files may embed 'dbdate' in pandas metadata
            # which newer pandas can't parse. Strip metadata and retry.
            try:
                import pyarrow.parquet as pq
                tbl = pq.read_table(cache_parquet)
                meta = tbl.schema.metadata.copy() if tbl.schema.metadata else {}
                meta.pop(b"pandas", None)
                tbl = tbl.replace_schema_metadata(meta)
                return tbl.to_pandas()
            except Exception:
                pass
    if not os.path.exists(cache_csv):
        return None
    try:
        df = pd.read_csv(cache_csv, low_memory=True)
        return df
    except Exception:
        return None


def get_hub_pincode_counts() -> dict:
    """Fast AWB counts per (hub, pincode) via DuckDB direct parquet query.
    Returns {(hub_str, pincode_str): count} dict, or empty dict if unavailable."""
    cache_parquet = _get_awb_cache_path().replace(".csv", ".parquet")
    if not os.path.exists(cache_parquet):
        return {}
    if HAS_DUCKDB:
        try:
            con = duckdb.connect()
            result = con.execute("""
                SELECT CAST(hub AS VARCHAR) AS hub,
                       CAST(pincode AS VARCHAR) AS pincode,
                       COUNT(*) AS cnt
                FROM read_parquet(?)
                GROUP BY hub, pincode
            """, [cache_parquet]).fetchall()
            con.close()
            return {(row[0], row[1]): row[2] for row in result}
        except Exception as e:
            print(f"DuckDB get_hub_pincode_counts error: {e}")
    # Pandas fallback
    df = load_awb_from_cache()
    if df is None or len(df) == 0:
        return {}
    return df.groupby(
        [df["hub"].astype(str), df["pincode"].astype(str)]
    ).size().to_dict()


def get_hub_pincode_counts_by_period() -> dict:
    """AWB counts per (hub, pincode) for 1d, 30d, and all via DuckDB.
    Returns {"1d": {(hub,pin):count}, "30d": {...}, "all": {...}}.
    The 'all' key is a synonym for the full 60d dataset."""
    cache_parquet = _get_awb_cache_path().replace(".csv", ".parquet")
    if not os.path.exists(cache_parquet):
        return {"1d": {}, "30d": {}, "all": {}}

    def _query_period(con, parquet_path, days_back=None):
        """Run hub×pincode count query with optional date filter."""
        if days_back is not None:
            sql = f"""
                SELECT CAST(hub AS VARCHAR) AS hub,
                       CAST(pincode AS VARCHAR) AS pincode,
                       COUNT(*) AS cnt
                FROM read_parquet(?)
                WHERE CAST(order_date AS DATE) >= CURRENT_DATE - INTERVAL '{days_back}' DAY
                GROUP BY hub, pincode
            """
        else:
            sql = """
                SELECT CAST(hub AS VARCHAR) AS hub,
                       CAST(pincode AS VARCHAR) AS pincode,
                       COUNT(*) AS cnt
                FROM read_parquet(?)
                GROUP BY hub, pincode
            """
        rows = con.execute(sql, [parquet_path]).fetchall()
        return {(r[0], r[1]): r[2] for r in rows}

    if HAS_DUCKDB:
        try:
            con = duckdb.connect()
            result = {
                "1d": _query_period(con, cache_parquet, days_back=1),
                "30d": _query_period(con, cache_parquet, days_back=30),
                "all": _query_period(con, cache_parquet, days_back=None),
            }
            con.close()
            return result
        except Exception as e:
            print(f"DuckDB get_hub_pincode_counts_by_period error: {e}")

    # Pandas fallback
    df = load_awb_from_cache()
    if df is None or len(df) == 0:
        return {"1d": {}, "30d": {}, "all": {}}
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    today = pd.Timestamp.now().normalize()

    def _pd_counts(mask):
        sub = df[mask] if mask is not None else df
        return sub.groupby([sub["hub"].astype(str), sub["pincode"].astype(str)]).size().to_dict()

    return {
        "1d": _pd_counts(df["order_date"] >= today - pd.Timedelta(days=1)),
        "30d": _pd_counts(df["order_date"] >= today - pd.Timedelta(days=30)),
        "all": _pd_counts(None),
    }


def compute_period_overlay_data() -> dict:
    """Compute hexbin cells + AWB sample for 1d and 30d time periods.
    Returns {"hexbin_1d":[...], "hexbin_30d":[...], "awb_1d":[...], "awb_30d":[...]}.
    Each hexbin item: {lat, lng, hub, count, pincode}.
    Each awb item: {lat, lng, hub, pincode}."""
    cache_parquet = _get_awb_cache_path().replace(".csv", ".parquet")
    if not os.path.exists(cache_parquet):
        return {"hexbin_1d": [], "hexbin_30d": [], "awb_1d": [], "awb_30d": []}

    try:
        import numpy as np
        HEX_SIZE = 0.008
        sqrt3 = np.sqrt(3)

        # Load full DataFrame once
        if HAS_DUCKDB:
            con = duckdb.connect()
            full_df = con.execute("SELECT * FROM read_parquet(?)", [cache_parquet]).fetchdf()
            con.close()
        else:
            full_df = load_awb_from_cache()
        if full_df is None or len(full_df) == 0:
            return {"hexbin_1d": [], "hexbin_30d": [], "awb_1d": [], "awb_30d": []}

        full_df["lat"] = pd.to_numeric(full_df.get("lat", pd.Series(dtype=float)), errors="coerce")
        full_df["long"] = pd.to_numeric(full_df.get("long", pd.Series(dtype=float)), errors="coerce")
        full_df = full_df.dropna(subset=["lat", "long"])
        full_df = full_df[(full_df["lat"] != 0) & (full_df["long"] != 0)]
        full_df["order_date"] = pd.to_datetime(full_df["order_date"], errors="coerce")
        today = pd.Timestamp.now().normalize()

        result = {}
        SAMPLE_SIZE = 4000  # Smaller sample per period to keep payload reasonable

        for label, days in [("1d", 1), ("30d", 30)]:
            sub = full_df[full_df["order_date"] >= today - pd.Timedelta(days=days)]
            if sub.empty:
                result[f"hexbin_{label}"] = []
                result[f"awb_{label}"] = []
                continue

            lats = sub["lat"].to_numpy(dtype=np.float64)
            lngs = sub["long"].to_numpy(dtype=np.float64)
            hubs = sub["hub"].astype(str).to_numpy() if "hub" in sub.columns else np.full(len(sub), "", dtype=object)
            if "pincode" in sub.columns:
                _raw = sub["pincode"].tolist()
                pincodes = np.array([
                    str(int(float(p))) if str(p).replace('.', '', 1).isdigit() else str(p).strip()
                    for p in _raw
                ], dtype=object)
            else:
                pincodes = np.full(len(sub), "", dtype=object)

            # Hex grid
            cols = np.round(lngs / (HEX_SIZE * 1.5)).astype(np.int32)
            row_offsets = np.where(np.abs(cols) % 2 == 1, HEX_SIZE * sqrt3 * 0.5, 0.0)
            rows = np.round((lats - row_offsets) / (HEX_SIZE * sqrt3)).astype(np.int32)

            agg_df = pd.DataFrame({"hub": hubs, "col": cols, "row": rows, "pincode": pincodes})
            agg_df["key"] = agg_df["hub"] + "|" + agg_df["col"].astype(str) + "|" + agg_df["row"].astype(str)
            counts = agg_df.groupby("key").size().rename("count")
            meta = agg_df.groupby("key").agg(hub=("hub", "first"), col=("col", "first"), row=("row", "first"), pincode=("pincode", "first"))
            combined = meta.join(counts)
            combined["center_lat"] = combined["row"].astype(float) * HEX_SIZE * sqrt3 + np.where(
                np.abs(combined["col"]) % 2 == 1, HEX_SIZE * sqrt3 * 0.5, 0.0)
            combined["center_lng"] = combined["col"].astype(float) * HEX_SIZE * 1.5

            hex_records = [{"lat": round(float(r["center_lat"]), 5), "lng": round(float(r["center_lng"]), 5),
                            "hub": str(r["hub"]), "count": int(r["count"]), "pincode": str(r["pincode"])}
                           for r in combined.reset_index(drop=True).to_dict("records")]
            result[f"hexbin_{label}"] = hex_records

            # Sample
            sample_df = pd.DataFrame({"lat": lats, "lng": lngs, "hub": hubs, "pincode": pincodes})
            if len(sample_df) > SAMPLE_SIZE:
                sample_df = sample_df.sample(n=SAMPLE_SIZE, random_state=42)
            result[f"awb_{label}"] = [{"lat": round(float(r["lat"]), 5), "lng": round(float(r["lng"]), 5),
                                        "hub": str(r["hub"]), "pincode": str(r["pincode"])}
                                       for r in sample_df.to_dict("records")]

        return result
    except Exception as e:
        print(f"compute_period_overlay_data error: {e}")
        return {"hexbin_1d": [], "hexbin_30d": [], "awb_1d": [], "awb_30d": []}


def get_awb_preview(limit=200):
    """Fast AWB preview using DuckDB. Returns dict with preview_df, total_rows, unique_hubs or None."""
    cache_parquet = _get_awb_cache_path().replace(".csv", ".parquet")
    if not os.path.exists(cache_parquet):
        return None
    if HAS_DUCKDB:
        try:
            con = duckdb.connect()
            preview_df = con.execute(
                "SELECT * FROM read_parquet(?) LIMIT ?", [cache_parquet, limit]
            ).fetchdf()
            stats = con.execute("""
                SELECT COUNT(*) AS total_rows, COUNT(DISTINCT hub) AS unique_hubs
                FROM read_parquet(?)
            """, [cache_parquet]).fetchone()
            con.close()
            return {
                "preview_df": preview_df,
                "total_rows": stats[0],
                "unique_hubs": stats[1],
            }
        except Exception as e:
            print(f"DuckDB get_awb_preview error: {e}")
    # Pandas fallback
    df = load_awb_from_cache()
    if df is None or len(df) == 0:
        return None
    return {
        "preview_df": df.head(limit),
        "total_rows": len(df),
        "unique_hubs": df["hub"].nunique() if "hub" in df.columns else 0,
    }


def query_awb_for_hub(hub_name: str) -> pd.DataFrame:
    """Return AWB rows for a single hub using DuckDB parquet query."""
    cache_parquet = _get_awb_cache_path().replace(".csv", ".parquet")
    if not os.path.exists(cache_parquet):
        return pd.DataFrame()
    if HAS_DUCKDB:
        try:
            con = duckdb.connect()
            df = con.execute("""
                SELECT * FROM read_parquet(?)
                WHERE CAST(hub AS VARCHAR) = ?
            """, [cache_parquet, hub_name]).fetchdf()
            con.close()
            return df
        except Exception as e:
            print(f"DuckDB query_awb_for_hub error: {e}")
    # Pandas fallback
    full_df = load_awb_from_cache()
    if full_df is None:
        return pd.DataFrame()
    return full_df[full_df["hub"].astype(str) == hub_name].copy()


def regenerate_hexbin_cache():
    """Re-generate hexbin_cache.json from parquet using DuckDB (reads only needed columns)."""
    cache_parquet = _get_awb_cache_path().replace(".csv", ".parquet")
    if not os.path.exists(cache_parquet):
        print("regenerate_hexbin_cache: no parquet file found")
        return
    if HAS_DUCKDB:
        try:
            con = duckdb.connect()
            df = con.execute("""
                SELECT CAST(hub AS VARCHAR) AS hub,
                       CAST(pincode AS VARCHAR) AS pincode,
                       CAST(lat AS DOUBLE) AS lat,
                       CAST(long AS DOUBLE) AS long
                FROM read_parquet(?)
                WHERE lat IS NOT NULL AND long IS NOT NULL
                  AND lat != 0 AND long != 0
            """, [cache_parquet]).fetchdf()
            con.close()
            _precompute_hexbin_cache(df)
            return
        except Exception as e:
            print(f"DuckDB regenerate_hexbin_cache error: {e}, falling back to pandas")
    # Pandas fallback
    df = load_awb_from_cache()
    if df is not None:
        _precompute_hexbin_cache(df)


def _save_awb_cache(df):
    """Save AWB data to disk cache with metadata. Uses parquet for speed."""
    os.makedirs(AWB_CACHE_DIR, exist_ok=True)
    # Save as parquet (5-10x faster than CSV for large files)
    cache_parquet = _get_awb_cache_path().replace(".csv", ".parquet")
    try:
        df.to_parquet(cache_parquet, index=False, engine="pyarrow")
    except Exception:
        # Fallback to CSV if parquet not available
        cache_path = _get_awb_cache_path()
        df.to_csv(cache_path, index=False, encoding="utf-8")
    meta = {
        "fetched_date": datetime.now().strftime("%Y-%m-%d"),
        "fetched_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "record_count": len(df),
        "columns": list(df.columns),
    }
    with open(_get_awb_cache_meta_path(), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)
    # Pre-compute hexbin cache to avoid on-the-fly computation in the UI
    _precompute_hexbin_cache(df)


def _precompute_hexbin_cache(df):
    """
    Pre-compute hex grid assignments for all AWB rows and save as a compact
    JSON cache.  Also saves an 8k proportionally-sampled point cache.

    Hex math (must match Maps Studio exactly):
        HEX_SIZE = 0.008
        cols = round(lng / (HEX_SIZE * 1.5))
        row_offsets = HEX_SIZE * sqrt3 * 0.5  if abs(col) % 2 == 1  else 0
        rows = round((lat - row_offset) / (HEX_SIZE * sqrt3))
        center_lat = row * HEX_SIZE * sqrt3 + (HEX_SIZE * sqrt3 * 0.5 if abs(col) % 2 == 1 else 0)
        center_lng = col * HEX_SIZE * 1.5
    """
    try:
        os.makedirs(AWB_CACHE_DIR, exist_ok=True)
        HEX_SIZE = 0.008
        sqrt3 = np.sqrt(3)

        # ── coerce lat/lng to numeric, drop nulls / zeros ───────────────────
        work = df.copy()
        work["lat"] = pd.to_numeric(work.get("lat", pd.Series(dtype=float)), errors="coerce")
        work["long"] = pd.to_numeric(work.get("long", pd.Series(dtype=float)), errors="coerce")
        work = work.dropna(subset=["lat", "long"])
        work = work[(work["lat"] != 0) & (work["long"] != 0)]

        if work.empty:
            print("hexbin cache: no valid coordinates found, skipping")
            return

        lats = work["lat"].to_numpy(dtype=np.float64)
        lngs = work["long"].to_numpy(dtype=np.float64)
        hubs = work["hub"].astype(str).to_numpy() if "hub" in work.columns else np.full(len(work), "", dtype=object)

        # Normalize pincodes: parquet round-trips integers as float64 → "577526.0"
        # Strip the trailing ".0" so JS lookup matches cluster pincode strings.
        if "pincode" in work.columns:
            raw_pins = work["pincode"].tolist()
            pincodes = np.array([
                str(int(float(p))) if str(p).replace('.', '', 1).isdigit() else str(p).strip()
                for p in raw_pins
            ], dtype=object)
        else:
            pincodes = np.full(len(work), "", dtype=object)

        # ── hex grid assignment ──────────────────────────────────────────────
        cols = np.round(lngs / (HEX_SIZE * 1.5)).astype(np.int32)
        row_offsets = np.where(np.abs(cols) % 2 == 1, HEX_SIZE * sqrt3 * 0.5, 0.0)
        rows = np.round((lats - row_offsets) / (HEX_SIZE * sqrt3)).astype(np.int32)

        # ── build a composite key for groupby: "hub|col|row" (vectorized) ──
        keys = np.char.add(
            np.char.add(hubs, "|"),
            np.char.add(cols.astype(str), np.char.add(np.full(len(cols), "|"), rows.astype(str)))
        )

        # ── aggregate: count per (hub, col, row) + pick most-common pincode ─
        key_series = pd.Series(keys, name="key")
        agg_df = pd.DataFrame({
            "key": keys,
            "hub": hubs,
            "col": cols,
            "row": rows,
            "pincode": pincodes,
        })

        # count
        counts = agg_df.groupby("key").size().rename("count")

        # most-common pincode per key
        def _most_common(s):
            vc = s.value_counts()
            return vc.index[0] if len(vc) else ""

        meta_agg = (
            agg_df.groupby("key")
            .agg(hub=("hub", "first"), col=("col", "first"), row=("row", "first"), pincode=("pincode", _most_common))
        )
        combined = meta_agg.join(counts)

        # ── compute hex cell centers (vectorized) ────────────────────────────
        combined["center_lat"] = combined["row"].astype(float) * HEX_SIZE * sqrt3 + np.where(
            np.abs(combined["col"]) % 2 == 1, HEX_SIZE * sqrt3 * 0.5, 0.0
        )
        combined["center_lng"] = combined["col"].astype(float) * HEX_SIZE * 1.5
        hex_records = [{
            "lat": round(float(r["center_lat"]), 5),
            "lng": round(float(r["center_lng"]), 5),
            "hub": str(r["hub"]),
            "count": int(r["count"]),
            "pincode": str(r["pincode"]),
        } for r in combined.reset_index(drop=True).to_dict("records")]

        hexbin_path = os.path.join(AWB_CACHE_DIR, "hexbin_cache.json")
        with open(hexbin_path, "w", encoding="utf-8") as f:
            json.dump(hex_records, f, ensure_ascii=False)
        print(f"hexbin cache: saved {len(hex_records):,} hex cells to {hexbin_path}")

        # ── proportional 8k sample across hubs (fast groupby approach) ─────
        SAMPLE_SIZE = 8000
        sample_df = pd.DataFrame({
            "lat": lats, "lng": lngs, "hub": hubs, "pincode": pincodes,
        })
        if len(sample_df) > SAMPLE_SIZE:
            _total = len(sample_df)
            sample_result = sample_df.groupby("hub", group_keys=False).apply(
                lambda g: g.sample(n=max(1, min(len(g), round(SAMPLE_SIZE * len(g) / _total))), random_state=42)
            ).head(SAMPLE_SIZE)
        else:
            sample_result = sample_df
        sample_records = [{
            "lat": round(float(r["lat"]), 5),
            "lng": round(float(r["lng"]), 5),
            "hub": str(r["hub"]),
            "pincode": str(r["pincode"]),
        } for r in sample_result.to_dict("records")]

        sample_path = os.path.join(AWB_CACHE_DIR, "awb_sample.json")
        with open(sample_path, "w", encoding="utf-8") as f:
            json.dump(sample_records, f, ensure_ascii=False)
        print(f"hexbin cache: saved {len(sample_records):,} sample points to {sample_path}")

    except Exception as e:
        print(f"hexbin cache precomputation error: {e}")


def load_hexbin_cache():
    """
    Load the pre-computed hexbin cache.
    Returns a list of hex cell dicts, or empty list if not found.
    Each dict: {"lat": float, "lng": float, "hub": str, "count": int, "pincode": str}
    """
    hexbin_path = os.path.join(AWB_CACHE_DIR, "hexbin_cache.json")
    if not os.path.exists(hexbin_path):
        return []
    try:
        with open(hexbin_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"load_hexbin_cache error: {e}")
        return []


def load_awb_sample_cache():
    """
    Load the pre-computed AWB sample (up to 8k points).
    Returns a list of point dicts, or empty list if not found.
    Each dict: {"lat": float, "lng": float, "hub": str, "pincode": str}
    """
    sample_path = os.path.join(AWB_CACHE_DIR, "awb_sample.json")
    if not os.path.exists(sample_path):
        return []
    try:
        with open(sample_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"load_awb_sample_cache error: {e}")
        return []


def build_awb_query(cluster_df=None, manual_pincodes=None):
    """
    Build the AWB SQL query. Pincodes injected from cluster_df or manual list.
    Exact SQL from the original Jupyter notebook.
    """
    if manual_pincodes:
        # Use manually provided pincodes
        pincodes = [str(p).strip() for p in manual_pincodes if str(p).strip()]
    elif cluster_df is not None and "pincode" in cluster_df.columns:
        pincodes = (
            cluster_df["pincode"]
            .astype(str)
            .str.strip()
            .str.replace(".0", "", regex=False)
            .unique()
            .tolist()
        )
    else:
        raise ValueError("Provide either cluster_df with 'pincode' column or manual_pincodes list")
    pincodes = [p for p in pincodes if p and p != 'nan' and p != '']
    if not pincodes:
        raise ValueError("No valid pincodes to query")
    pincode_list = ",".join(pincodes)

    # Split pincodes into batches if too many (BigQuery has ~1MB query limit)
    # 2852 pincodes × ~7 chars each ≈ 20KB — well within limit
    query = f"""
    WITH awb_data AS (
        SELECT
            sg.order_date, sg.rider_id, sg.pincode,
            sg.order_id AS fwd_del_awb_number,
            SAFE_CAST(edp.delivery_latitude AS FLOAT64) AS lat, SAFE_CAST(edp.delivery_longitude AS FLOAT64) AS long,
            ROW_NUMBER() OVER (PARTITION BY sg.rider_id ORDER BY edp.update_timestamp) AS row_num
        FROM `{DATA_PROJECT_ID}.smaug_dataengine.data_engine_orderleveldata` sg
        LEFT JOIN `{DATA_PROJECT_ID}.ecommerce.ecommerce_deliveryrequest` edr
            ON CAST(edr.awb_number AS STRING) = CAST(sg.order_id AS STRING)
            AND edr.last_updated > CURRENT_DATE() - INTERVAL 30 DAY
        LEFT JOIN `{DATA_PROJECT_ID}.ecommerce.ecommerce_deliveryrequestproof` edp
            ON CAST(edr.id AS STRING) = CAST(edp.delivery_request_id AS STRING)
            AND edp.update_timestamp > CURRENT_DATE() - INTERVAL 30 DAY
        WHERE sg.order_date > CURRENT_DATE() - INTERVAL 30 DAY
            AND sg.order_category = 1
            AND ecom_request_type IN (1)
            AND sg.order_status IN (1)
            AND sg.order_tag IN (0, 1, 14)
            AND edr.client_id NOT IN (
                5,18,60,61,67,68,102,354,552,557,
                715,818,862,875,11,996,1579,1575,
                1819,2063,2253
            )
            AND sg.pincode IN ({pincode_list})

        UNION ALL

        SELECT
            sg.order_date, sg.rider_id, sg.pincode,
            sg.order_id AS fwd_del_awb_number,
            SAFE_CAST(epp.pickup_latitude AS FLOAT64) AS lat, SAFE_CAST(epp.pickup_longitude AS FLOAT64) AS long,
            ROW_NUMBER() OVER (PARTITION BY sg.rider_id ORDER BY epp.update_timestamp) AS row_num
        FROM `{DATA_PROJECT_ID}.smaug_dataengine.data_engine_orderleveldata` sg
        LEFT JOIN `{DATA_PROJECT_ID}.ecommerce.pickup_pickuprequestproof` epp
            ON CAST(sg.order_id AS STRING) = CAST(epp.pickup_request_id AS STRING)
            AND epp.update_timestamp > CURRENT_DATE() - INTERVAL 30 DAY
        WHERE sg.order_date > CURRENT_DATE() - INTERVAL 30 DAY
            AND sg.order_category = 1
            AND ecom_request_type IN (5)
            AND sg.order_status IN (2,3)
            AND sg.order_tag IN (0,1,14)
            AND sg.pincode IN ({pincode_list})
    ),
    Pin AS (
        WITH ranked_data AS (
            SELECT report_date, pincode, hub, payment_category,
                ROW_NUMBER() OVER (PARTITION BY pincode ORDER BY report_date DESC) AS row_num
            FROM `{DATA_PROJECT_ID}.analytics_tables.client_pincode_active_data`
            WHERE service = "regular"
        )
        SELECT report_date, pincode, hub, payment_category
        FROM ranked_data WHERE row_num = 1
    ),
    final AS (
        SELECT
            order_date, rider_id, Pin.hub,
            awb_data.pincode AS pincode,
            CONCAT("P", CAST(pin.payment_category AS STRING)) AS payment_category,
            fwd_del_awb_number,
            COALESCE(lat, FIRST_VALUE(lat) OVER (
                PARTITION BY rider_id ORDER BY row_num
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            )) AS lat,
            COALESCE(long, FIRST_VALUE(long) OVER (
                PARTITION BY rider_id ORDER BY row_num
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            )) AS long
        FROM awb_data
        LEFT JOIN Pin ON CAST(awb_data.pincode AS STRING) = CAST(Pin.pincode AS STRING)
    )
    SELECT * FROM final
    WHERE lat IS NOT NULL AND long IS NOT NULL AND lat != 0 AND long != 0
    """
    return query


def _norm_pincode(val):
    """Normalize pincode: strip trailing .0 from float round-trips (577526.0 → 577526)."""
    s = str(val).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def _stream_to_parquet(query_job, parquet_path, progress_cb=None, start_pct=0.72, end_pct=0.90):
    """
    Stream BigQuery results page-by-page directly to a parquet file.
    Never loads the full result into memory — safe for 11M+ row results on 1GB RAM.
    Returns total rows written.
    """
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        # pyarrow not available — fall back to in-memory download
        if progress_cb:
            progress_cb(start_pct + 0.02, "⬇️ Downloading (no pyarrow, loading into memory)...")
        df = query_job.to_dataframe()
        df.to_parquet(parquet_path, index=False)
        if progress_cb:
            progress_cb(end_pct, f"⬇️ Downloaded {len(df):,} rows")
        return len(df)

    os.makedirs(os.path.dirname(parquet_path), exist_ok=True)
    PAGE_SIZE = 25_000

    # Try to get total row count for progress display
    total_rows_est = None
    try:
        dest = query_job.destination
        if dest:
            _tbl = query_job._client.get_table(dest)
            total_rows_est = _tbl.num_rows
    except Exception:
        pass

    if total_rows_est and progress_cb:
        progress_cb(start_pct, f"⬇️ Streaming {total_rows_est:,} rows to parquet...")

    writer = None
    rows_written = 0
    try:
        rows_iter = query_job._client.list_rows(query_job.destination, page_size=PAGE_SIZE)
        for page in rows_iter.pages:
            page_df = page.to_dataframe()
            if page_df.empty:
                continue
            # Normalize pincode in-flight so parquet stores clean strings
            if "pincode" in page_df.columns:
                page_df["pincode"] = page_df["pincode"].apply(_norm_pincode)
            tbl = pa.Table.from_pandas(page_df, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(parquet_path, tbl.schema)
            writer.write_table(tbl)
            rows_written += len(page_df)
            if progress_cb:
                if total_rows_est:
                    pct = start_pct + (end_pct - start_pct) * min(rows_written / total_rows_est, 1.0)
                    progress_cb(pct, f"⬇️ {rows_written:,} / {total_rows_est:,} rows ({rows_written * 100 // total_rows_est}%)")
                else:
                    progress_cb(min(start_pct + 0.1, end_pct - 0.05), f"⬇️ {rows_written:,} rows written...")
    except Exception as e:
        # Fallback: in-memory download if streaming fails
        print(f"Streaming fallback triggered: {e}")
        if writer:
            try:
                writer.close()
            except Exception:
                pass
            writer = None
        if progress_cb:
            progress_cb(start_pct + 0.02, "⬇️ Streaming failed, loading into memory (fallback)...")
        try:
            df = query_job.to_dataframe()
            if "pincode" in df.columns:
                df["pincode"] = df["pincode"].apply(_norm_pincode)
            df.to_parquet(parquet_path, index=False, engine="pyarrow")
            rows_written = len(df)
        except Exception as e2:
            raise Exception(f"Both streaming and fallback download failed: {e2}")
    finally:
        if writer:
            try:
                writer.close()
            except Exception:
                pass

    if progress_cb:
        progress_cb(end_pct, f"✅ {rows_written:,} rows saved to parquet")
    return rows_written


def _precompute_hexbin_from_parquet(parquet_path):
    """
    Memory-efficient hexbin computation using DuckDB directly on parquet.
    Performs the full hex-grid aggregation in SQL — never loads all rows into Python.
    Safe for 11M+ row datasets on 1GB RAM cloud instances.
    """
    if not os.path.exists(parquet_path):
        print("_precompute_hexbin_from_parquet: parquet file not found")
        return
    if not HAS_DUCKDB:
        print("_precompute_hexbin_from_parquet: DuckDB not available, using pandas fallback")
        _precompute_hexbin_cache(load_awb_from_cache() or pd.DataFrame())
        return

    HEX_SIZE = 0.008
    SQRT3 = 1.7320508075688772

    try:
        con = duckdb.connect()

        # Compute hex grid entirely in SQL — output is ~100k aggregated rows, not 11M
        agg_sql = f"""
            WITH norm AS (
                SELECT
                    CAST(hub AS VARCHAR)     AS hub,
                    CAST(pincode AS VARCHAR) AS pincode,
                    CAST(lat  AS DOUBLE)     AS lat,
                    CAST(long AS DOUBLE)     AS lng
                FROM read_parquet(?)
                WHERE lat IS NOT NULL AND long IS NOT NULL
                  AND lat != 0 AND long != 0
            ),
            grid AS (
                SELECT hub, pincode,
                    ROUND(lng / {HEX_SIZE * 1.5})::INT AS col,
                    ROUND((lat - CASE
                        WHEN ABS(ROUND(lng / {HEX_SIZE * 1.5})) % 2 = 1
                        THEN {HEX_SIZE * SQRT3 * 0.5}
                        ELSE 0.0 END) / {HEX_SIZE * SQRT3})::INT AS row_
                FROM norm
            )
            SELECT hub, pincode, col, row_, COUNT(*) AS cnt
            FROM grid
            GROUP BY hub, pincode, col, row_
        """
        agg_df = con.execute(agg_sql, [parquet_path]).fetchdf()
        print(f"hexbin: DuckDB aggregated {len(agg_df):,} hex cells from parquet")

        # Sample 8k random points for awb_sample.json (lat/lng preview layer)
        sample_sql = """
            SELECT
                CAST(hub      AS VARCHAR) AS hub,
                CAST(pincode  AS VARCHAR) AS pincode,
                CAST(lat      AS DOUBLE)  AS lat,
                CAST(long     AS DOUBLE)  AS lng
            FROM read_parquet(?) USING SAMPLE 8000
            WHERE lat IS NOT NULL AND long IS NOT NULL AND lat != 0 AND long != 0
        """
        sample_df = con.execute(sample_sql, [parquet_path]).fetchdf()
        con.close()

        _build_hexbin_json(agg_df, sample_df, HEX_SIZE, SQRT3)

    except Exception as e:
        print(f"_precompute_hexbin_from_parquet DuckDB error: {e}")
        # Last-resort fallback: read only 4 columns with DuckDB and process in pandas
        try:
            con2 = duckdb.connect()
            slim = con2.execute("""
                SELECT CAST(hub AS VARCHAR) AS hub, CAST(pincode AS VARCHAR) AS pincode,
                       CAST(lat AS DOUBLE) AS lat, CAST(long AS DOUBLE) AS long
                FROM read_parquet(?)
                WHERE lat IS NOT NULL AND long IS NOT NULL AND lat != 0 AND long != 0
            """, [parquet_path]).fetchdf()
            con2.close()
            _precompute_hexbin_cache(slim)
        except Exception as e2:
            print(f"_precompute_hexbin_from_parquet fallback also failed: {e2}")


def _build_hexbin_json(agg_df, sample_df, HEX_SIZE, SQRT3):
    """
    Convert DuckDB-aggregated hex cells (hub, pincode, col, row_, cnt) into
    hexbin_cache.json and awb_sample.json. Called after DuckDB aggregation.
    """
    try:
        os.makedirs(AWB_CACHE_DIR, exist_ok=True)

        if agg_df is None or len(agg_df) == 0:
            print("_build_hexbin_json: empty aggregation, skipping")
            return

        cols_arr = agg_df["col"].to_numpy(dtype=np.float64)
        rows_arr = agg_df["row_"].to_numpy(dtype=np.float64)
        center_lat = rows_arr * HEX_SIZE * SQRT3 + np.where(
            np.abs(cols_arr) % 2 == 1, HEX_SIZE * SQRT3 * 0.5, 0.0
        )
        center_lng = cols_arr * HEX_SIZE * 1.5

        hex_records = []
        hubs_col   = agg_df["hub"].tolist()
        pins_col   = agg_df["pincode"].tolist()
        cnts_col   = agg_df["cnt"].tolist()
        for i in range(len(agg_df)):
            pin = _norm_pincode(pins_col[i])
            hex_records.append({
                "lat":     round(float(center_lat[i]), 5),
                "lng":     round(float(center_lng[i]), 5),
                "hub":     str(hubs_col[i]),
                "count":   int(cnts_col[i]),
                "pincode": pin,
            })

        hexbin_path = os.path.join(AWB_CACHE_DIR, "hexbin_cache.json")
        with open(hexbin_path, "w", encoding="utf-8") as f:
            json.dump(hex_records, f, ensure_ascii=False)
        print(f"hexbin cache: saved {len(hex_records):,} hex cells → {hexbin_path}")

        # AWB sample (8k points for window.__AWB_DATA__)
        if sample_df is not None and len(sample_df) > 0:
            lat_col = "lat" if "lat" in sample_df.columns else next((c for c in sample_df.columns if "lat" in c.lower()), None)
            lng_col = "lng" if "lng" in sample_df.columns else next((c for c in sample_df.columns if "lng" in c.lower() or "lon" in c.lower()), None)
            if lat_col and lng_col:
                sample_records = []
                for r in sample_df.to_dict("records"):
                    pin = _norm_pincode(r.get("pincode", ""))
                    sample_records.append({
                        "lat":     round(float(r[lat_col]), 5),
                        "lng":     round(float(r[lng_col]), 5),
                        "hub":     str(r.get("hub", "")),
                        "pincode": pin,
                    })
                sample_path = os.path.join(AWB_CACHE_DIR, "awb_sample.json")
                with open(sample_path, "w", encoding="utf-8") as f:
                    json.dump(sample_records, f, ensure_ascii=False)
                print(f"hexbin cache: saved {len(sample_records):,} sample points → {sample_path}")

    except Exception as e:
        print(f"_build_hexbin_json error: {e}")


def fetch_awb_data(client, cluster_df=None, force_refresh=False, progress_cb=None, manual_pincodes=None):
    """
    Fetch AWB data from BigQuery.
    Uses streaming parquet write to handle 11M+ rows without OOM.
    Returns a 50k-row sample DataFrame for session state + stores full data in parquet.
    """
    if not force_refresh:
        cached = load_awb_from_cache()
        if cached is not None:
            return cached, None

    query = build_awb_query(cluster_df=cluster_df, manual_pincodes=manual_pincodes)
    cache_parquet = _get_awb_cache_path().replace(".csv", ".parquet")
    os.makedirs(AWB_CACHE_DIR, exist_ok=True)

    try:
        if progress_cb:
            progress_cb(0.05, "📡 Submitting AWB query to BigQuery...")
        query_job = client.query(query)

        _poll_query_job(query_job, progress_cb, base_pct=0.08, end_pct=0.70, label="AWB")

        if progress_cb:
            progress_cb(0.72, "⬇️ Streaming results to parquet (memory-safe)...")

        # Stream page-by-page to parquet — never loads full dataset into Python memory
        total_rows = _stream_to_parquet(
            query_job, cache_parquet, progress_cb, start_pct=0.72, end_pct=0.88
        )

        # Save metadata
        meta = {
            "fetched_date":   datetime.now().strftime("%Y-%m-%d"),
            "fetched_time":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "record_count":   total_rows,
            "columns":        ["order_date","rider_id","hub","pincode","payment_category",
                               "fwd_del_awb_number","lat","long"],
        }
        with open(_get_awb_cache_meta_path(), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)

        if progress_cb:
            progress_cb(0.90, f"🔢 Computing AWB hexbins via DuckDB ({total_rows:,} rows)...")

        # Compute hexbins entirely via DuckDB SQL — never loads 11M rows into pandas
        _precompute_hexbin_from_parquet(cache_parquet)

        # Return a small sample for session state (PIP stats, sidebar display)
        if progress_cb:
            progress_cb(0.97, "📋 Loading 50k sample for session...")
        sample_df = _load_session_sample(cache_parquet, n=50_000)

        if progress_cb:
            progress_cb(1.0, f"✅ {total_rows:,} AWB records saved. Session sample: {len(sample_df):,} rows.")
        return sample_df, None

    except GoogleAPIError as e:
        return None, f"BigQuery API Error: {e}"
    except Exception as e:
        return None, f"Error: {e}"


def _load_session_sample(parquet_path, n=50_000):
    """Load a small random sample from parquet for session state. Never OOMs."""
    if HAS_DUCKDB and os.path.exists(parquet_path):
        try:
            con = duckdb.connect()
            df = con.execute(f"SELECT * FROM read_parquet(?) USING SAMPLE {n}", [parquet_path]).fetchdf()
            con.close()
            return df
        except Exception:
            pass
    # Pandas fallback
    try:
        df = pd.read_parquet(parquet_path)
        return df.sample(min(len(df), n), random_state=42) if len(df) > n else df
    except Exception:
        return pd.DataFrame()
