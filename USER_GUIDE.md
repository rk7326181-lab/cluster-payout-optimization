# 📖 User Guide - Hub Cluster Optimizer

Complete guide for using the Hub Cluster Cost Optimization Dashboard.

---

## 📑 Table of Contents

1. [Getting Started](#getting-started)
2. [Understanding the Interface](#understanding-the-interface)
3. [Loading Data](#loading-data)
4. [Using Filters](#using-filters)
5. [Interactive Map Guide](#interactive-map-guide)
6. [Cost Dashboard](#cost-dashboard)
7. [Hub Comparison](#hub-comparison)
8. [Exporting Data](#exporting-data)
9. [Tips & Best Practices](#tips--best-practices)
10. [FAQ](#faq)

---

## 1. Getting Started

### First Launch

When you first open the application, you'll see:
- A welcome screen with feature overview
- Sidebar with configuration options
- Instructions to load data

### Initial Setup

1. **Choose Data Source**
   - Local Files: Uses sample CSV data
   - BigQuery: Connects to live database (requires credentials)

2. **Load Data**
   - Click "🔄 Load Data" button in sidebar
   - Wait for confirmation message
   - Check the Quick Stats panel

---

## 2. Understanding the Interface

### Main Components

```
┌─────────────────────────────────────────────────────┐
│  SIDEBAR                  │  MAIN CONTENT           │
│  ┌──────────────┐        │  ┌──────────────────┐  │
│  │ Data Source  │        │  │ Tab 1: Map       │  │
│  │ Load Button  │        │  │ Tab 2: Dashboard │  │
│  │ Filters      │        │  │ Tab 3: Compare   │  │
│  │ Quick Stats  │        │  │ Tab 4: Export    │  │
│  └──────────────┘        │  └──────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### Navigation

- **Tabs**: Switch between different views
- **Sidebar**: Control filters and settings
- **Main Area**: Display selected content

---

## 3. Loading Data

### Option A: Local CSV Files (Default)

**When to use**: Testing, offline work, sample data

**Steps**:
1. Select "Local Files (CSV)" in sidebar
2. Click "🔄 Load Data"
3. Wait 5-10 seconds
4. See confirmation with cluster/hub count

**Data loaded**:
- `clustering_live_02042026.csv` - Cluster polygons and rates
- `hub_Lat_Long02042026.csv` - Hub locations

### Option B: BigQuery (Live Data)

**When to use**: Production, real-time data, full dataset

**Prerequisites**:
- Google Cloud credentials in `config/credentials.json`
- BigQuery access permissions
- Internet connection

**Steps**:
1. Select "BigQuery (Live)" in sidebar
2. Set Year and Month filters
3. Click "🔄 Load Data"
4. Wait 30-60 seconds for query
5. See confirmation

**Troubleshooting**:
- ❌ "Authentication failed" → Check credentials file
- ❌ "No data returned" → Verify year/month have data
- ❌ "Timeout" → Reduce date range, check internet

---

## 4. Using Filters

Filters help you narrow down the view to specific hubs, regions, or rate categories.

### Available Filters

#### Hub Name
- **Location**: Sidebar, dropdown menu
- **Options**: "All Hubs" or specific hub names
- **Use case**: Focus on one hub at a time
- **Example**: Select "BVU_Balipara" to see only that hub

#### Hub ID
- **Auto-populated** based on Hub Name selection
- Shows the numeric identifier

#### Pincode
- **Location**: Sidebar, text input
- **Format**: Comma-separated values
- **Example**: `400701, 414403, 784101`
- **Use case**: View specific postal areas

#### Surge Rate Range
- **Location**: Sidebar, slider
- **Range**: ₹0 to ₹14
- **Use case**: Filter by cost tier
- **Example**: Set 0-3 to see only low-rate clusters

### Applying Filters

Filters are applied **automatically** as you change them. Watch the Quick Stats panel update in real-time.

### Clearing Filters

- Hub Name: Select "All Hubs"
- Pincode: Delete text
- Surge Rate: Reset slider to 0-14

---

## 5. Interactive Map Guide

### Map Features

#### Cluster Polygons
- **Gray areas**: Cluster boundaries
- **Color intensity**: Based on surge rate
  - Light gray: ₹0 (base rate)
  - Blue: ₹1-₹6 (low-medium)
  - Yellow/Orange: ₹7-₹10 (high)
  - Red: ₹11+ (very high)

#### Rate Labels
- **₹ Numbers**: Displayed inside each cluster
- **Toggle**: Use "Show Rate Labels" checkbox
- **Purpose**: Quick rate identification

#### Hub Markers
- **Red Triangles**: Hub locations
- **Toggle**: Use "Show Hub Markers" checkbox
- **Click**: See hub details popup

### Map Controls

#### Navigation
- **Pan**: Click and drag anywhere
- **Zoom In**: Mouse wheel up OR + button
- **Zoom Out**: Mouse wheel down OR - button
- **Reset**: Reload the tab

#### Interactions
- **Click Polygon**: View cluster details popup
  - Cluster code
  - Hub name
  - Pincode
  - Surge rate
  - Category

- **Hover Polygon**: See tooltip with basic info

- **Click Hub Marker**: View hub details
  - Hub name and ID
  - Category
  - Coordinates

#### Map Options
- **Fullscreen**: Click fullscreen button (top-right)
- **Layers**: Switch base map (OpenStreetMap default)

### Reading the Map

**Example Scenario**:
```
You see a cluster labeled "₹6" in a gray polygon.

This means:
- Deliveries to this area cost an extra ₹6
- It's a medium-surge zone
- The polygon shows the exact boundaries
- Click it to see which hub serves it
```

### Legend

Located in bottom-right corner:
- Color codes for each rate tier
- Hub marker symbol
- Click legend to toggle visibility

---

## 6. Cost Dashboard

### Overview Metrics

Top row shows 4 key metrics:

1. **Total Revenue**
   - Sum of all cluster surge charges
   - Trend: Green ↑ = increasing, Red ↓ = decreasing

2. **Total Shipments**
   - Number of deliveries (estimated)
   - Based on cluster activity

3. **Avg Cluster Rate**
   - Average surge rate across all clusters
   - Lower = more affordable service

4. **Active Clusters**
   - Clusters with surge > ₹0
   - Indicator of complex routing

### Revenue Breakdown

#### By Hub
- **Table**: Top 10 hubs by revenue
- **Columns**: Hub name, revenue, shipments
- **Sorted**: Highest revenue first
- **Use case**: Identify top performers

#### By Cluster Category
- **Table**: Revenue grouped by rate tier
- **Categories**:
  - ₹0 (Base): No surcharge areas
  - ₹1-₹3 (Low): Slight surcharge
  - ₹4-₹6 (Medium): Moderate surcharge
  - ₹7-₹10 (High): Significant surcharge
  - ₹11+ (Very High): Maximum surcharge

### Optimization Recommendations

The dashboard generates **AI-powered suggestions** based on:
- Low-density high-rate clusters
- High-density zero-rate clusters
- Inconsistent rates within same pincode
- Hub efficiency metrics

**Example Suggestions**:

```
1. Consider merging low-density cluster
   Clusters: 784101_F (₹6)
   💰 Potential Saving: ₹8,400/month
   📝 Low shipment volume (45) with high surcharge.
      Merging with adjacent base-rate cluster could save costs.

2. Consider adding minimal surge rate
   Clusters: 400701_A (1,200 shipments)
   💰 Potential Revenue: ₹1,200/month
   📝 High shipment volume with no surcharge.
      Market can likely bear ₹1-₹2 rate increase.
```

### Understanding Suggestions

Each suggestion includes:
- **Action**: What to do
- **Clusters**: Which clusters affected
- **Potential Saving**: Estimated monthly impact
- **Reasoning**: Why this is recommended
- **Priority**: High/Medium/Low

---

## 7. Hub Comparison

### Selecting Hubs

1. Use **Hub A** dropdown to select first hub
2. Use **Hub B** dropdown to select second hub
3. Comparison updates automatically

### Comparison Metrics

| Metric | Description | Good vs Bad |
|--------|-------------|-------------|
| Total Revenue | Sum of surge charges | Higher = better (if efficient) |
| Total Shipments | Number of deliveries | Higher = more active |
| Avg Cluster Rate | Average surge rate | Lower = more accessible |
| Active Clusters | Clusters with surge | Optimal varies by hub size |
| Revenue per Shipment | Revenue efficiency | Higher = more profitable |
| Clusters per Hub | Complexity measure | Lower = simpler operation |

### Difference Column

- **Green %**: Hub A performs better
- **Red %**: Hub A performs worse
- **Absolute numbers**: Actual difference

### Use Cases

**Scenario 1: Why is Hub A more profitable?**
- Compare revenue per shipment
- Check average cluster rate
- Review active cluster count

**Scenario 2: Should we replicate Hub B's model?**
- Look at shipment count vs revenue
- Compare cluster efficiency
- Note best practices

**Scenario 3: Which hub needs optimization?**
- Higher avg rate + lower shipments = optimization needed
- Many active clusters + low revenue = inefficient

---

## 8. Exporting Data

### Export Formats

#### CSV - Cluster Data
**Contents**:
- All cluster information
- Hub assignments
- Surge rates
- Pincodes

**Use case**: Excel analysis, reporting

**Steps**:
1. Go to "Export & Reports" tab
2. Select "CSV - Cluster Data"
3. Click "Generate Export"
4. Click download button
5. Open in Excel/Google Sheets

#### CSV - Hub Summary
**Contents**:
- Hub-level aggregated data
- Cluster counts
- Average rates
- Pincode coverage

**Use case**: Executive summary, dashboards

#### HTML - Interactive Map
**Contents**:
- Standalone HTML file
- Embedded map with all features
- Works offline

**Use case**: Share with colleagues, embed in reports

**Steps**:
1. Select "HTML - Interactive Map"
2. Click "Generate Export"
3. Download .html file
4. Open in any web browser
5. Share the file or host on web server

### Export Tips

✅ **Best Practices**:
- Apply filters before exporting for targeted data
- Use CSV for data analysis
- Use HTML for presentations
- Include date in filename for versioning

❌ **Avoid**:
- Exporting without filters (too large)
- Opening large CSVs in Notepad
- Sharing HTML maps with sensitive data publicly

---

## 9. Tips & Best Practices

### Performance

**For faster loading**:
1. Filter to specific hub before loading map
2. Reduce date range in BigQuery mode
3. Close unused browser tabs
4. Clear browser cache if sluggish

**For large datasets**:
- Use filters aggressively
- Export subsets instead of full data
- Consider pagination (future feature)

### Analysis Workflows

**Weekly Review**:
1. Load latest data
2. Check cost dashboard metrics
3. Review top 5 optimization suggestions
4. Export hub summary CSV
5. Share with management

**Hub Optimization**:
1. Select target hub in filters
2. View map to identify geographic patterns
3. Check cost dashboard for efficiency
4. Review suggestions specific to hub
5. Compare with best-performing hub
6. Export action plan

**Monthly Reporting**:
1. Load data for entire month
2. Export hub summary CSV
3. Export interactive map HTML
4. Create presentation with:
   - Top hubs by revenue
   - Cost optimization wins
   - Recommendations for next month

### Common Tasks

**Find clusters to merge**:
1. Set surge rate filter to ₹4+
2. Look at cost dashboard suggestions
3. Check map for adjacent ₹0 clusters
4. Export cluster data for detailed analysis

**Identify underutilized hubs**:
1. Go to cost dashboard
2. Sort revenue by hub (ascending)
3. Check shipment counts
4. Compare with other hubs
5. Review suggestions

**Optimize pincode coverage**:
1. Enter target pincode in filter
2. View map to see cluster coverage
3. Check if rates are consistent
4. Review suggestions for that pincode

---

## 10. FAQ

### General

**Q: How often is data updated?**
- CSV mode: Manual - update files in `data/` folder
- BigQuery mode: Real-time - select current year/month

**Q: Can I use this on mobile?**
- Partially. Best experience on desktop/laptop with 1920x1080+ screen.
- Map interactions work on tablet.

**Q: Is my data secure?**
- Local mode: Data never leaves your computer
- BigQuery mode: Uses secure Google Cloud connection
- Deployed version: Follow your organization's security policy

### Data

**Q: What if a cluster has no geometry?**
- It won't appear on map but will be in dashboard stats
- Check original data for WKT boundary

**Q: Why are some hubs missing?**
- Check hub_id matches between cluster and hub datasets
- Verify hub has valid lat/long coordinates
- Try "All Hubs" filter to see all

**Q: Can I add my own data?**
- Yes! Replace CSV files in `data/` folder
- Match the expected column names
- Reload the app

### Features

**Q: How are optimization suggestions generated?**
- Algorithm analyzes shipment density vs surge rate
- Identifies inefficiencies
- Calculates potential savings based on historical patterns
- Uses statistical models for recommendations

**Q: Can I customize the map colors?**
- Yes! Edit `modules/map_renderer.py`
- Modify `RATE_COLORS` dictionary
- Restart app to see changes

**Q: How do I save my filter settings?**
- Currently manual (note your settings)
- Future feature: Save filter presets

### Technical

**Q: App is slow. How to fix?**
1. Filter to smaller dataset
2. Reduce browser tabs
3. Clear browser cache
4. Increase server resources (if deployed)
5. Add database indexes (for BigQuery)

**Q: Export button not working?**
- Check browser pop-up blocker
- Try different browser (Chrome recommended)
- Check file size isn't too large
- See browser console for errors (F12)

**Q: Map not rendering?**
- Check internet connection (map tiles from OpenStreetMap)
- Verify geometry data is valid WKT format
- Try reducing cluster count with filters
- Clear browser cache

### Errors

**Q: "No module named 'streamlit'"**
```bash
pip install -r requirements.txt
```

**Q: "BigQuery authentication failed"**
- Check `config/credentials.json` exists
- Verify service account has BigQuery permissions
- Ensure project ID matches

**Q: "Cannot load data files"**
- Verify CSV files in `data/` folder
- Check file names match exactly
- Ensure CSV format is correct

---

## 📞 Support

For additional help:

1. **Check Documentation**: README.md, QUICKSTART.md, DEPLOYMENT.md
2. **Review Code**: Comments in source files
3. **Test Installation**: Run `python test_installation.py`
4. **Browser Console**: Press F12 to see error details
5. **Contact Admin**: Your organization's IT support

---

## 🎓 Training Resources

### Video Tutorials (Future)
- Getting Started (5 min)
- Using Filters (3 min)
- Reading the Dashboard (7 min)
- Exporting Data (4 min)

### Sample Scenarios
Located in `examples/` folder (future):
- Optimizing a high-cost hub
- Merging adjacent clusters
- Monthly performance review
- Executive report generation

---

**Happy Optimizing! 🚀**

Remember: The goal is to reduce costs while maintaining service quality. Use the insights from this dashboard to make data-driven decisions about your cluster configuration.
