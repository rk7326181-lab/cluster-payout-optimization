"""
generate_bq_token.py
─────────────────────
Run this once locally to generate a fresh BigQuery refresh token
for your Google account.

Usage:
    python generate_bq_token.py

A browser will open. Sign in with the Google account that has
BigQuery access (your Shadowfax account). The token will be printed
— copy it into your Streamlit app Secrets.
"""

from google_auth_oauthlib.flow import InstalledAppFlow
from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPIError

SCOPES = [
    "https://www.googleapis.com/auth/bigquery",
    "https://www.googleapis.com/auth/cloud-platform",
]

OAUTH_CLIENT_CONFIG = {
    "installed": {
        "client_id": "764086051850-6qr4p6gpi6hn506pt8ejuq83di341hur.apps.googleusercontent.com",
        "client_secret": "d-FL95Q19q7MQmFpd7hHD0Ty",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}

DATA_PROJECT_ID = "data-warehousing-391512"

print("Opening browser — sign in with the Google account that has BigQuery access...")
flow = InstalledAppFlow.from_client_config(OAUTH_CLIENT_CONFIG, SCOPES)
creds = flow.run_local_server(port=0, prompt="consent",
                               success_message="Auth OK — return to terminal.")

print("\n✅ Token obtained. Verifying BigQuery access...")

# Try both projects as billing project
connected_project = None
for proj in ["bi-team-400508", "data-warehousing-391512"]:
    try:
        client = bigquery.Client(project=proj, credentials=creds)
        client.query(
            f"SELECT 1 FROM `{DATA_PROJECT_ID}.ecommerce.ecommerce_hub` LIMIT 1"
        ).result(timeout=15)
        print(f"✅ BigQuery access confirmed (billing project: {proj})")
        connected_project = proj
        break
    except GoogleAPIError as e:
        print(f"⚠️  {proj}: {str(e)[:100]}")
    except Exception as e:
        print(f"⚠️  {proj}: {str(e)[:100]}")

if connected_project is None:
    print("\n❌ This account does not have BigQuery access on either project.")
    print("Ask your GCP admin to grant you 'BigQuery Job User' role on")
    print("project bi-team-400508 or data-warehousing-391512, then re-run this script.")
else:
    print(f"\n{'='*60}")
    print("COPY THIS INTO YOUR STREAMLIT APP → SETTINGS → SECRETS")
    print("="*60)
    print()
    print("[google_oauth]")
    print(f'refresh_token = "{creds.refresh_token}"')
    print(f'client_id     = "{creds.client_id}"')
    print(f'client_secret = "{creds.client_secret}"')
    print(f'token_uri     = "https://oauth2.googleapis.com/token"')
    print()
    print(f"Also update PROJECT_ID in modules/bigquery_client.py to: {connected_project}")
    print("="*60)
