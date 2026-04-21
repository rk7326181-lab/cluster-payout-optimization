# 📦 INSTALLATION INSTRUCTIONS

Complete installation guide for the Hub Cluster Cost Optimization Dashboard.

---

## 🎯 Choose Your Installation Method

1. **[Automated Setup](#method-1-automated-setup-recommended)** - One command install (5 minutes)
2. **[Manual Setup](#method-2-manual-setup)** - Step-by-step installation (10 minutes)
3. **[Docker Setup](#method-3-docker-setup)** - Containerized deployment (5 minutes)

---

## Method 1: Automated Setup (Recommended)

### Prerequisites
- Python 3.8 or higher
- pip package manager
- Internet connection

### Installation

```bash
# Navigate to project directory
cd hub-cluster-optimizer

# Run automated setup
python setup.py
```

The script will:
- ✅ Check Python version
- ✅ Install all dependencies
- ✅ Create necessary directories
- ✅ Setup configuration files
- ✅ Verify data files
- ✅ Run tests

### Next Steps

```bash
# Start the application
streamlit run app.py
```

Open browser to: http://localhost:8501

---

## Method 2: Manual Setup

### Step 1: Verify Python

```bash
python --version
# Should show Python 3.8 or higher
```

If not installed, download from [python.org](https://www.python.org/downloads/)

### Step 2: Install Dependencies

```bash
# Upgrade pip
python -m pip install --upgrade pip

# Install requirements
pip install -r requirements.txt
```

**Expected output:**
```
Successfully installed streamlit-1.28.0 pandas-2.0.0 ...
```

### Step 3: Create Directories

```bash
# Create necessary folders
mkdir -p data config assets outputs logs
```

### Step 4: Setup Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit if needed
nano .env  # or use your favorite editor
```

### Step 5: Add Data Files

Place your CSV files in the `data/` directory:
- `clustering_live_02042026.csv`
- `hub_Lat_Long02042026.csv`

Or use your own data files (match the expected format).

### Step 6: Test Installation

```bash
python test_installation.py
```

Should show all green checkmarks ✅

### Step 7: Run Application

```bash
streamlit run app.py
```

Browser should open automatically to http://localhost:8501

---

## Method 3: Docker Setup

### Prerequisites
- Docker installed ([get Docker](https://docs.docker.com/get-docker/))
- Docker Compose (included with Docker Desktop)

### Quick Start

```bash
# Navigate to project
cd hub-cluster-optimizer

# Build and run with Docker Compose
docker-compose up -d
```

### Access Application

Open browser to: http://localhost:8501

### Stop Application

```bash
docker-compose down
```

### Manual Docker Build

```bash
# Build image
docker build -t hub-optimizer .

# Run container
docker run -d -p 8501:8501 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/config:/app/config \
  hub-optimizer

# View logs
docker logs hub-optimizer

# Stop container
docker stop hub-optimizer
```

---

## 🔧 Post-Installation

### Verify Installation

1. **Check data loaded**
   - Sidebar → Click "Load Data"
   - Should see cluster and hub counts

2. **Check map renders**
   - Tab 1: Interactive Map
   - Should see gray polygons with rate labels

3. **Check dashboard**
   - Tab 2: Cost Dashboard
   - Should see metrics and suggestions

### Configure BigQuery (Optional)

To connect to live data:

1. **Get credentials**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create service account
   - Download JSON key

2. **Add to project**
   ```bash
   # Save credentials
   cp your-key.json config/credentials.json
   ```

3. **Test connection**
   - In app: Select "BigQuery (Live)"
   - Click "Load Data"
   - Should fetch data from cloud

---

## 🐛 Troubleshooting

### Common Issues

#### "Command 'streamlit' not found"

**Solution:**
```bash
# Ensure streamlit is installed
pip install streamlit

# Or use python -m
python -m streamlit run app.py
```

#### "No module named 'pandas'" (or other module)

**Solution:**
```bash
pip install -r requirements.txt
```

#### "Port 8501 already in use"

**Solution:**
```bash
# Find and kill process (Mac/Linux)
lsof -ti:8501 | xargs kill -9

# Or use different port
streamlit run app.py --server.port 8502
```

#### "Data files not found"

**Solution:**
- Check files are in `data/` folder
- Verify file names match exactly
- Check file permissions

#### "Map not rendering"

**Solution:**
- Check internet connection (for map tiles)
- Try different browser (Chrome recommended)
- Clear browser cache
- Check browser console (F12) for errors

### Windows-Specific Issues

#### "pip is not recognized"

**Solution:**
```cmd
python -m pip install -r requirements.txt
```

#### Permission errors

**Solution:**
Run Command Prompt as Administrator

### Mac-Specific Issues

#### SSL certificate errors

**Solution:**
```bash
/Applications/Python\ 3.x/Install\ Certificates.command
```

### Linux-Specific Issues

#### Missing dependencies

**Solution:**
```bash
# Ubuntu/Debian
sudo apt-get install python3-pip python3-dev

# CentOS/RHEL
sudo yum install python3-pip python3-devel
```

---

## 📊 Verifying Data Format

Your CSV files should have these columns:

### clustering_live.csv
```csv
id,hub_id,hub_name,cluster_code,boundary,pincode,surge_amount
1,12509,BOM_Ghansoli,400701_A,"POLYGON((...))","400701",0
```

### hub_Lat_Long.csv
```csv
id,name,latitude,longitude,hub_category
1099,CHN_SHOLINGANALLURKT,12.9424475,80.2417398,ECOM_SELF_LM
```

---

## 🚀 Quick Test

After installation, run this quick test:

```bash
# 1. Start the app
streamlit run app.py

# 2. In the app (browser):
#    - Sidebar: Keep "Local Files (CSV)" selected
#    - Click "🔄 Load Data"
#    - Wait for "✅ Loaded X clusters from Y hubs"

# 3. Navigate tabs:
#    - Tab 1: Should see map with polygons
#    - Tab 2: Should see metrics
#    - Tab 3: Should see comparison dropdowns
#    - Tab 4: Should see export options

# ✅ If all above work, installation successful!
```

---

## 📚 Next Steps

1. **Read Quick Start**: `QUICKSTART.md`
2. **Read User Guide**: `USER_GUIDE.md`
3. **Try the app**: Load sample data and explore
4. **Customize**: Add your own data
5. **Deploy**: See `DEPLOYMENT.md` for production setup

---

## 🆘 Still Having Issues?

1. **Check Python version**
   ```bash
   python --version  # Must be 3.8+
   ```

2. **Update pip**
   ```bash
   python -m pip install --upgrade pip
   ```

3. **Fresh install**
   ```bash
   # Remove existing packages
   pip uninstall -r requirements.txt -y
   
   # Reinstall
   pip install -r requirements.txt
   ```

4. **Check file structure**
   ```bash
   ls -la
   # Should see: app.py, modules/, data/, etc.
   ```

5. **Run test script**
   ```bash
   python test_installation.py
   ```

---

## 💡 Tips

- **Virtual Environment** (recommended):
  ```bash
  python -m venv venv
  source venv/bin/activate  # Mac/Linux
  venv\Scripts\activate     # Windows
  pip install -r requirements.txt
  ```

- **Check logs**:
  ```bash
  # Streamlit logs
  streamlit run app.py --logger.level=debug
  ```

- **Browser cache**:
  - Press Ctrl+Shift+R (hard refresh)
  - Or use incognito mode

---

## ✅ Installation Complete!

You're ready to start optimizing hub clusters!

Run: `streamlit run app.py`

Happy analyzing! 🎉
