# 🚀 Quick Start Guide

Get the Hub Cluster Optimizer running in 5 minutes!

---

## ⚡ Option 1: Local Python (Fastest)

### Step 1: Install Python Dependencies

```bash
# Navigate to project folder
cd hub-cluster-optimizer

# Install requirements
pip install -r requirements.txt
```

### Step 2: Run the Application

```bash
streamlit run app.py
```

### Step 3: Open in Browser

The app will automatically open at: **http://localhost:8501**

If it doesn't open automatically, manually navigate to that URL.

### Step 4: Load Sample Data

1. In the sidebar, keep **"Local Files (CSV)"** selected
2. Click **"🔄 Load Data"** button
3. Wait 5-10 seconds for data to load
4. Start exploring!

---

## 🐳 Option 2: Docker (Recommended for Production)

### Step 1: Build Container

```bash
docker-compose up -d
```

### Step 2: Access Application

Open browser to: **http://localhost:8501**

### Step 3: Stop Application

```bash
docker-compose down
```

---

## 🌐 Option 3: Deploy to Streamlit Cloud (Free Hosting)

### Step 1: Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin YOUR_GITHUB_REPO_URL
git push -u origin main
```

### Step 2: Deploy

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Sign in with GitHub
3. Click "New app"
4. Select your repository
5. Set main file path: `app.py`
6. Click "Deploy"

### Step 3: Access Your App

You'll get a public URL like: `https://your-app.streamlit.app`

---

## 📊 First Steps After Launch

### 1. Load Data

- Sidebar → Click "🔄 Load Data"
- Wait for confirmation message
- You should see cluster and hub counts

### 2. Explore the Map

- **Tab 1: Interactive Map**
- See all clusters displayed with surge rates
- Click any polygon to see details
- Use filters to narrow down view

### 3. View Analytics

- **Tab 2: Cost Dashboard**
- See revenue metrics
- Review optimization suggestions
- Explore revenue breakdown

### 4. Compare Hubs

- **Tab 3: Hub Comparison**
- Select two hubs from dropdowns
- See side-by-side performance

### 5. Export Data

- **Tab 4: Export & Reports**
- Download CSV or HTML maps
- Share with your team

---

## ⚙️ Configuration (Optional)

### Connect to BigQuery (Live Data)

1. **Get Google Cloud Credentials**
   - Create service account in Google Cloud Console
   - Download JSON key file
   - Save as `config/credentials.json`

2. **Select BigQuery in App**
   - Sidebar → Choose "BigQuery (Live)"
   - Set year and month
   - Click "Load Data"

### Customize Settings

Edit `.env` file (copy from `.env.example`):

```bash
DEFAULT_YEAR=2026
DEFAULT_MONTH=3
CACHE_TTL=3600
```

---

## 🐛 Troubleshooting

### "No module named 'streamlit'"

```bash
pip install -r requirements.txt
```

### "Cannot find data files"

Make sure you're in the correct directory:
```bash
cd hub-cluster-optimizer
ls data/  # Should show CSV files
```

### Port 8501 already in use

Kill existing Streamlit process:
```bash
# Windows
taskkill /F /IM streamlit.exe

# Mac/Linux
pkill -f streamlit
```

Or use a different port:
```bash
streamlit run app.py --server.port 8502
```

### Map not loading

- Check browser console (F12)
- Try different browser (Chrome recommended)
- Clear browser cache
- Reduce number of clusters with filters

---

## 📞 Need Help?

1. Check the full README.md for detailed documentation
2. Review error messages in the terminal
3. Look at code comments in source files
4. Try loading a smaller dataset first

---

## 🎯 Next Steps

Once you're comfortable with the basics:

1. **Integrate Real Data**: Connect to your BigQuery
2. **Customize**: Modify colors, metrics, suggestions
3. **Share**: Deploy to Streamlit Cloud for your team
4. **Extend**: Add new features based on your needs

---

**You're ready to go! 🎉**

Run `streamlit run app.py` and start optimizing your hub clusters!
