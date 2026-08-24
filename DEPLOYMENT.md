# 🚀 Deployment Guide

Complete guide for deploying the Hub Cluster Optimizer to production.

---

## 📋 Pre-Deployment Checklist

Before deploying, ensure:

- [ ] All code is tested locally
- [ ] Required data files are in `data/` folder
- [ ] BigQuery credentials configured (if using live data)
- [ ] Dependencies listed in `requirements.txt`
- [ ] Environment variables set properly
- [ ] Git repository is clean and committed

---

## 🏠 Current Production Setup: Self-Hosted via Tailscale (Private)

This app runs on a dedicated Windows PC/server on your own network and is
reachable **only** over a private [Tailscale](https://tailscale.com) network —
no public port-forwarding, no cloud hosting. It runs alongside its sibling
repo on the same server:

| App | Repo | Port |
|---|---|---|
| cluster-payout-optimization (this repo) | Cluster Optimizer | **8502** |
| Clustering-web-app | Geo Intelligence Portal | 8501 |

See that repo's own `DEPLOYMENT.md` for its setup — the steps below only
cover this repo. Do both once each; they don't interfere with each other.

### 1. One-time server setup

Prerequisites: **Python 3.11** and **Git** on the dedicated Windows PC.

```powershell
git clone https://github.com/rk7326181-lab/cluster-payout-optimization.git
cd cluster-payout-optimization

python -m venv venv
venv\Scripts\pip install --upgrade pip
venv\Scripts\pip install -r requirements.txt
```

Secrets (never committed — `.streamlit\secrets.toml` and `.env` are both
already in `.gitignore`):

```powershell
Copy-Item .streamlit\secrets.toml.example .streamlit\secrets.toml
notepad .streamlit\secrets.toml   # fill in [users] login + BigQuery credentials

Copy-Item .env.example .env
notepad .env                      # fill in GROQ_API_KEY for GANDALF AI
```

BigQuery: either `[google_oauth]` (personal Gmail token — expires every ~2
days under this workspace's session policy; re-run `python generate_bq_token.py`
when it does) or `[gcp_credentials]` (a service account key — doesn't
expire; ask the BI/GCP team for one).

### 2. Install Tailscale and join the private network

```powershell
# On the server, after installing Tailscale for Windows
# (https://tailscale.com/download/windows):
tailscale up
tailscale ip -4     # note this machine's address, or use its MagicDNS name
```

Every teammate's device that needs access installs Tailscale and joins the
same tailnet — a device outside the tailnet cannot reach the server at all.
Optionally scope down which tailnet users/devices may connect via ACLs at
https://login.tailscale.com/admin/acls (see Clustering-web-app's
`DEPLOYMENT.md` for a worked ACL example covering both apps' ports).

Extra layer — restrict this port to Tailscale devices only, on top of
Tailscale's own authentication (run once, as Administrator):

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\Setup-Firewall.ps1
```

### 3. Start / stop / restart / status

| Action | Double-click | Command |
|---|---|---|
| Start | `deploy\Start-App.bat` | `powershell -ExecutionPolicy Bypass -File deploy\start.ps1` |
| Stop | `deploy\Stop-App.bat` | `powershell -ExecutionPolicy Bypass -File deploy\stop.ps1` |
| Restart | `deploy\Restart-App.bat` | `powershell -ExecutionPolicy Bypass -File deploy\restart.ps1` |
| Status | `deploy\Status-App.bat` | `powershell -ExecutionPolicy Bypass -File deploy\status.ps1` |

Runs as a background process; logs land in `deploy\logs\`; refuses to
double-start; any team member with server access can run these same
commands. See Clustering-web-app's `DEPLOYMENT.md` for full details (identical
mechanism, different port).

### 4. Access the app

- From the server: `http://localhost:8502`
- Remotely, from any tailnet device: `http://<tailscale-ip-or-magicdns-name>:8502`

### 5. Updating later

```powershell
git pull
venv\Scripts\pip install -r requirements.txt   # only if requirements changed
deploy\Restart-App.bat
```

---

## 🌐 Other Deployment Options (reference / not currently used)

The options below were evaluated earlier in the project. The app currently
runs self-hosted via Tailscale (above) — kept here for reference only.

### Option 1: Streamlit Cloud (Easiest - Free)

**Best for**: Small teams, internal tools, quick demos

**Pros:**
- ✅ Free hosting
- ✅ Automatic HTTPS
- ✅ Simple deployment
- ✅ Auto-updates from Git

**Cons:**
- ❌ Public unless paid plan
- ❌ Limited resources
- ❌ Streamlit branding

**Steps:**

1. **Push Code to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial deployment"
   git remote add origin https://github.com/YOUR_USERNAME/hub-optimizer.git
   git push -u origin main
   ```

2. **Deploy to Streamlit Cloud**
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Click "New app"
   - Connect GitHub repository
   - Main file: `app.py`
   - Click "Deploy"

3. **Add Secrets (for BigQuery)**
   - App settings → Secrets
   - Paste your `credentials.json` content:
   ```toml
   [gcp_service_account]
   type = "service_account"
   project_id = "your-project-id"
   private_key_id = "your-key-id"
   # ... rest of credentials
   ```

4. **Configure Advanced Settings**
   - Python version: 3.9
   - Resources: Adjust if needed
   - Custom domain: Add if available

**Cost**: Free (public) | $20/month (private)

---

### Option 2: Google Cloud Run (Recommended for Production)

**Best for**: Production apps, scalable deployments, enterprise

**Pros:**
- ✅ Auto-scaling
- ✅ Pay per use
- ✅ Fast deployment
- ✅ HTTPS included
- ✅ Custom domains

**Cons:**
- ❌ Requires GCP account
- ❌ More complex setup

**Steps:**

1. **Setup Google Cloud Project**
   ```bash
   # Install Google Cloud SDK
   # https://cloud.google.com/sdk/docs/install
   
   # Login
   gcloud auth login
   
   # Set project
   gcloud config set project YOUR_PROJECT_ID
   ```

2. **Build and Deploy**
   ```bash
   # Enable required APIs
   gcloud services enable run.googleapis.com
   gcloud services enable containerregistry.googleapis.com
   
   # Deploy (Cloud Run will build automatically)
   gcloud run deploy hub-cluster-optimizer \
     --source . \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --memory 2Gi \
     --timeout 300
   ```

3. **Add Environment Variables**
   ```bash
   gcloud run services update hub-cluster-optimizer \
     --set-env-vars DEFAULT_YEAR=2026,DEFAULT_MONTH=3
   ```

4. **Mount BigQuery Credentials**
   - Store credentials in Secret Manager
   - Mount as volume in Cloud Run

**Cost**: ~$5-50/month (depending on usage)

---

### Option 3: AWS Elastic Beanstalk

**Best for**: AWS-centric organizations

**Steps:**

1. **Install EB CLI**
   ```bash
   pip install awsebcli
   ```

2. **Initialize EB Application**
   ```bash
   eb init -p python-3.9 hub-cluster-optimizer
   ```

3. **Create Environment**
   ```bash
   eb create production-env
   ```

4. **Deploy**
   ```bash
   eb deploy
   ```

**Cost**: ~$10-100/month

---

### Option 4: Heroku

**Best for**: Quick prototypes, startups

**Steps:**

1. **Create Heroku App**
   ```bash
   heroku create hub-cluster-optimizer
   ```

2. **Add Buildpack**
   ```bash
   heroku buildpacks:set heroku/python
   ```

3. **Create Procfile**
   ```
   web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
   ```

4. **Deploy**
   ```bash
   git push heroku main
   ```

**Cost**: $7-25/month

---

### Option 5: Docker + VPS (DigitalOcean, Linode, etc.)

**Best for**: Full control, custom infrastructure

**Steps:**

1. **Build Docker Image**
   ```bash
   docker build -t hub-optimizer .
   ```

2. **Push to Registry**
   ```bash
   docker tag hub-optimizer your-registry/hub-optimizer
   docker push your-registry/hub-optimizer
   ```

3. **Deploy to VPS**
   ```bash
   # SSH into server
   ssh user@your-server-ip
   
   # Pull and run
   docker pull your-registry/hub-optimizer
   docker run -d -p 80:8501 hub-optimizer
   ```

4. **Setup Nginx Reverse Proxy** (optional)
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;
       
       location / {
           proxy_pass http://localhost:8501;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_set_header Host $host;
       }
   }
   ```

**Cost**: $5-20/month (VPS)

---

## 🔐 Security Best Practices

### 1. Protect Credentials

**Never commit credentials to Git!**

```bash
# Add to .gitignore
config/credentials.json
.env
*.key
```

**Use environment variables or secret managers:**

- Streamlit Cloud: Use Secrets
- Cloud Run: Use Secret Manager
- Heroku: Use Config Vars
- AWS: Use Secrets Manager

### 2. Enable Authentication

For Streamlit Cloud:
- Use private app setting (paid plan)

For Cloud Run:
```bash
gcloud run services update hub-cluster-optimizer \
  --no-allow-unauthenticated
```

For custom auth, add to `app.py`:
```python
import streamlit_authenticator as stauth

authenticator = stauth.Authenticate(...)
name, authentication_status, username = authenticator.login('Login', 'main')

if not authentication_status:
    st.stop()
```

### 3. Use HTTPS

All major platforms (Streamlit Cloud, Cloud Run, Heroku) provide HTTPS by default.

For custom deployments, use Let's Encrypt:
```bash
certbot --nginx -d your-domain.com
```

---

## 📊 Monitoring & Logging

### Streamlit Cloud

- View logs in app dashboard
- Monitor resource usage
- Set up uptime alerts

### Google Cloud Run

```bash
# View logs
gcloud logging read "resource.type=cloud_run_revision"

# Set up monitoring
gcloud monitoring dashboards create --config-from-file=dashboard.json
```

### Custom Metrics

Add to your app:
```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"User loaded {len(df)} clusters")
```

---

## 🔄 CI/CD Pipeline

### GitHub Actions Example

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Cloud Run

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Cloud SDK
        uses: google-github-actions/setup-gcloud@v0
        with:
          service_account_key: ${{ secrets.GCP_SA_KEY }}
          project_id: ${{ secrets.GCP_PROJECT_ID }}
      
      - name: Deploy to Cloud Run
        run: |
          gcloud run deploy hub-cluster-optimizer \
            --source . \
            --platform managed \
            --region us-central1
```

---

## 📈 Scaling Considerations

### For High Traffic

1. **Increase Resources**
   ```bash
   # Cloud Run
   gcloud run services update hub-cluster-optimizer \
     --memory 4Gi \
     --cpu 2 \
     --max-instances 10
   ```

2. **Add Caching**
   ```python
   import streamlit as st
   
   @st.cache_data(ttl=3600)
   def load_data():
       # Your expensive operation
       pass
   ```

3. **Use CDN**
   - CloudFlare (free tier available)
   - Google Cloud CDN
   - AWS CloudFront

4. **Optimize Data Loading**
   - Use column selection in BigQuery
   - Add indexes to database tables
   - Implement pagination

---

## 🧪 Testing Before Deployment

### Local Testing

```bash
# Test with production settings
streamlit run app.py --server.headless true
```

### Docker Testing

```bash
docker build -t hub-optimizer .
docker run -p 8501:8501 hub-optimizer
```

### Load Testing

```bash
# Install locust
pip install locust

# Run load test
locust -f loadtest.py --host http://localhost:8501
```

---

## 📱 Post-Deployment

### 1. Verify Deployment

- [ ] App loads without errors
- [ ] Data loads successfully
- [ ] All features work
- [ ] Maps render correctly
- [ ] Exports function properly

### 2. Share with Users

- Email the URL to your team
- Create user documentation
- Provide training if needed

### 3. Monitor Performance

- Check logs daily for first week
- Monitor resource usage
- Track error rates
- Collect user feedback

### 4. Plan for Updates

- Create development/staging environments
- Use Git branches for features
- Test before deploying to production
- Keep dependencies updated

---

## 🆘 Rollback Plan

If deployment fails:

### Streamlit Cloud
- Go to app settings
- Select previous deployment
- Click "Promote"

### Cloud Run
```bash
# List revisions
gcloud run revisions list

# Route traffic to previous revision
gcloud run services update-traffic hub-cluster-optimizer \
  --to-revisions REVISION_NAME=100
```

### Docker
```bash
# Pull previous image version
docker pull your-registry/hub-optimizer:previous-tag
docker run -d -p 8501:8501 your-registry/hub-optimizer:previous-tag
```

---

## 📊 Cost Optimization

### Reduce Costs

1. **Use appropriate instance sizes**
2. **Set auto-scaling limits**
3. **Enable caching aggressively**
4. **Use BigQuery caching**
5. **Optimize query performance**

### Estimated Monthly Costs

| Platform | Free Tier | Paid (Low) | Paid (High) |
|----------|-----------|------------|-------------|
| Streamlit Cloud | ✅ | $20 | $20 |
| Cloud Run | $0-5 | $10-30 | $50-100 |
| Heroku | ❌ | $7 | $25-50 |
| AWS EB | ❌ | $10-20 | $50-200 |
| VPS | ❌ | $5-10 | $20-40 |

---

## ✅ Deployment Checklist

- [ ] Code tested locally
- [ ] Environment variables configured
- [ ] Secrets/credentials secured
- [ ] Dependencies updated
- [ ] Git repository clean
- [ ] Documentation updated
- [ ] Deployment platform chosen
- [ ] Domain name configured (if needed)
- [ ] SSL/HTTPS enabled
- [ ] Monitoring setup
- [ ] Backup plan established
- [ ] Team notified
- [ ] User training scheduled

---

**Ready to deploy! 🚀**

Choose your platform and follow the steps above. Start with Streamlit Cloud for quickest results!
