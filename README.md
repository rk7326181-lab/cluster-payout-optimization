# 🗺️ Hub Cluster Cost Optimization Dashboard

A comprehensive web application for visualizing delivery clusters, analyzing hub performance, and optimizing operational costs through interactive mapping and data analytics.

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.8+-green)
![Streamlit](https://img.shields.io/badge/streamlit-1.28+-red)

---

## 📋 Features

### 🗺️ Interactive Maps
- Visualize cluster zones with color-coded surge rates (₹0-₹14)
- Hub location markers with detailed information
- Real-time filtering by hub, pincode, and rate category
- Click polygons for cluster details
- Exportable HTML maps

### 📊 Cost Analytics
- Revenue tracking across hubs and clusters
- Shipment density analysis
- Cost per delivery calculations
- Performance metrics dashboard
- Trend analysis (when connected to BigQuery)

### 💡 Smart Recommendations
- AI-powered cost optimization suggestions
- Identifies low-efficiency clusters
- Merger opportunities for cost savings
- Rate optimization recommendations

### 🔄 Hub Comparison
- Side-by-side hub performance comparison
- Benchmarking metrics
- Efficiency scoring
- Best practices identification

---

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- pip package manager
- (Optional) Google Cloud account for BigQuery integration

### Installation

1. **Clone or download this project**
   ```bash
   cd hub-cluster-optimizer
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   streamlit run app.py
   ```

4. **Open in browser**
   - The app will automatically open at `http://localhost:8501`

---

## 📁 Project Structure

```
hub-cluster-optimizer/
│
├── app.py                      # Main Streamlit application
├── requirements.txt            # Python dependencies
├── README.md                   # This file
│
├── modules/                    # Core application modules
│   ├── __init__.py
│   ├── data_loader.py          # Data loading from CSV/BigQuery
│   ├── map_renderer.py         # Interactive map generation
│   ├── cost_analyzer.py        # Cost analysis & recommendations
│   └── utils.py                # Utility functions
│
├── data/                       # Data files (CSV)
│   ├── clustering_live_02042026.csv
│   └── hub_Lat_Long02042026.csv
│
├── config/                     # Configuration files
│   └── credentials.json        # BigQuery credentials (optional)
│
└── assets/                     # Static assets (images, etc.)
```

---

## 🎯 Usage Guide

### 1. Loading Data

**Option A: Local CSV Files (Default)**
- Click **"Load Data"** in the sidebar
- App uses sample CSV files from `data/` folder
- No configuration needed

**Option B: BigQuery (Live Data)**
1. Select **"BigQuery (Live)"** in data source
2. Add your Google Cloud credentials to `config/credentials.json`
3. Set year and month filters
4. Click **"Load Data"**

### 2. Filtering Data

Use sidebar filters to narrow down the view:
- **Hub Name**: Select specific hub or "All Hubs"
- **Pincode**: Enter comma-separated pincodes
- **Surge Rate Range**: Adjust slider (₹0-₹14)

### 3. Exploring the Map

- **Pan**: Click and drag
- **Zoom**: Mouse wheel or +/- buttons
- **Click Polygon**: View cluster details
- **Toggle Labels**: Show/hide rate labels
- **Toggle Hubs**: Show/hide hub markers

### 4. Viewing Analytics

Navigate to **"Cost Dashboard"** tab:
- View top-level metrics
- Explore revenue breakdown
- Review optimization suggestions

### 5. Comparing Hubs

Navigate to **"Hub Comparison"** tab:
- Select two hubs from dropdowns
- Compare performance metrics
- Identify efficiency gaps

### 6. Exporting Data

Navigate to **"Export & Reports"** tab:
- Choose export format (CSV or HTML)
- Click **"Generate Export"**
- Download file to your computer

---

## ⚙️ Configuration

### BigQuery Setup (Optional)

If you want to connect to live BigQuery data:

1. **Create a Google Cloud service account**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Navigate to IAM & Admin → Service Accounts
   - Create new service account
   - Grant BigQuery User role
   - Download JSON key

2. **Add credentials to project**
   - Save JSON key as `config/credentials.json`
   - Update project ID in `modules/data_loader.py` if needed

3. **Verify table names**
   - Ensure BigQuery tables match:
     - `geocode_geoclusters` (cluster data)
     - `ecommerce_hub_locations` (hub data)

### Environment Variables

You can optionally use a `.env` file for configuration:

```bash
# .env
BIGQUERY_PROJECT_ID=your-project-id
DEFAULT_YEAR=2026
DEFAULT_MONTH=3
```

---

## 📊 Data Format

### Cluster Data (CSV)

Required columns:
- `hub_id`: Hub identifier (integer)
- `hub_name`: Hub name (string)
- `cluster_code`: Unique cluster code (string)
- `boundary`: WKT polygon geometry (string)
- `pincode`: Postal code (string)
- `surge_amount`: Surge rate in rupees (numeric)

Example:
```csv
id,hub_id,hub_name,cluster_code,boundary,pincode,surge_amount
1,12509,BOM_Ghansoli,400701_A,"POLYGON ((72.991 19.128, ...))",400701,0
```

### Hub Data (CSV)

Required columns:
- `id`: Hub identifier (integer)
- `name`: Hub name (string)
- `latitude`: Latitude coordinate (numeric)
- `longitude`: Longitude coordinate (numeric)
- `hub_category`: Hub category (string)

Example:
```csv
id,name,latitude,longitude,hub_category
1099,CHN_SHOLINGANALLURKT,12.9424475,80.2417398,ECOM_SELF_LM
```

---

## 🔧 Customization

### Changing Color Scheme

Edit `modules/map_renderer.py`:

```python
RATE_COLORS = {
    0: '#YOUR_COLOR',   # Gray - Base rate
    1: '#YOUR_COLOR',   # Light blue
    # ... etc
}
```

### Adding New Metrics

Edit `modules/cost_analyzer.py` in the `calculate_metrics()` function:

```python
metrics['your_new_metric'] = your_calculation
```

### Modifying Optimization Logic

Edit `modules/cost_analyzer.py` in the `generate_suggestions()` function to add new recommendation types.

---

## 🐛 Troubleshooting

### Error: "Module not found"
```bash
pip install -r requirements.txt
```

### Error: "Cannot load data"
- Check that CSV files exist in `data/` folder
- Verify CSV format matches expected structure
- Check file paths in `modules/data_loader.py`

### Error: "BigQuery authentication failed"
- Verify `config/credentials.json` exists
- Check service account has BigQuery access
- Ensure project ID is correct

### Map not displaying
- Check browser console for JavaScript errors
- Verify cluster geometries are valid WKT
- Try reducing the number of clusters displayed

### Performance issues
- Filter data to specific hub/region
- Reduce date range if using BigQuery
- Close other browser tabs

---

## 📈 Performance Optimization

For large datasets (>10,000 clusters):

1. **Use pagination**: Modify app to load data in chunks
2. **Add caching**: Use `@st.cache_data` decorator more aggressively
3. **Cluster simplification**: Simplify polygon geometries
4. **Database indexing**: Add indexes on frequently queried columns

Example caching:

```python
@st.cache_data(ttl=3600)
def load_data():
    # Your data loading logic
    pass
```

---

## 🚢 Deployment

### Streamlit Cloud (Free)

1. Push code to GitHub repository
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Add secrets in dashboard (for BigQuery credentials)
5. Deploy!

### Docker Deployment

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8501
CMD ["streamlit", "run", "app.py"]
```

Build and run:
```bash
docker build -t hub-optimizer .
docker run -p 8501:8501 hub-optimizer
```

### Google Cloud Run

```bash
gcloud run deploy hub-cluster-optimizer \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

---

## 📝 License

This project is provided as-is for internal use.

---

## 🆘 Support

For issues or questions:
- Check this README
- Review code comments
- Open an issue on GitHub

---

## 🔮 Roadmap

Future enhancements:

- [ ] Real-time shipment tracking integration
- [ ] Machine learning for demand prediction
- [ ] Automated cluster optimization algorithm
- [ ] Mobile-responsive design
- [ ] Multi-language support
- [ ] Advanced reporting (PDF generation)
- [ ] API endpoints for external systems
- [ ] Role-based access control

---

## 📚 References

- [Streamlit Documentation](https://docs.streamlit.io/)
- [Folium Maps](https://python-visualization.github.io/folium/)
- [Google BigQuery](https://cloud.google.com/bigquery/docs)
- [Shapely Geometry](https://shapely.readthedocs.io/)

---

**Built with ❤️ using Python & Streamlit**

Version 1.0.0 | Last Updated: April 2026
