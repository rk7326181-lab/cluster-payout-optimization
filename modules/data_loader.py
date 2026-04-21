"""
Data Loader Module - UPDATED for Kepler CSV Format
==================
Handles loading data from Kepler CSV format or BigQuery and preprocessing.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from shapely import wkt
from shapely.geometry import Polygon, Point
import json
import re
from datetime import datetime


class DataLoader:
    """Handles data loading from various sources"""

    # BigQuery cluster_category integer → actual surge rate (₹)
    CATEGORY_TO_RATE = {
        1: 0.00,   2: 0.50,   3: 1.00,   4: 1.50,   5: 2.00,
        6: 2.50,   7: 3.00,   8: 3.50,   9: 4.00,  10: 4.50,
        11: 5.00,  12: 6.00,  13: 7.00,  14: 8.00,  15: 9.00,
        16: 10.00, 17: 11.00, 18: 12.00, 19: 13.00, 20: 15.00,
    }

    CACHE_MANIFEST = "data/cache_manifest.json"

    def __init__(self, use_bigquery=False):
        self.use_bigquery = use_bigquery
        self.project_root = Path(__file__).parent.parent

    # ════════════════════════════════════════════════════
    # CACHE MANIFEST — remembers last fetched data paths
    # ════════════════════════════════════════════════════

    def _manifest_path(self):
        return self.project_root / self.CACHE_MANIFEST

    def save_cache_manifest(self, cluster_path, hub_path, kepler_path):
        """Write a small JSON that records which files were last saved and when."""
        manifest = {
            "cluster_csv": str(cluster_path),
            "hub_csv": str(hub_path),
            "kepler_csv": str(kepler_path),
            "fetched_date": datetime.now().strftime("%Y-%m-%d"),
            "fetched_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(self._manifest_path(), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

    def get_cache_manifest(self):
        """Return the manifest dict, or None if no cached data exists."""
        mp = self._manifest_path()
        if not mp.exists():
            return None
        try:
            with open(mp, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            # Verify all three files still exist on disk
            for key in ("cluster_csv", "hub_csv", "kepler_csv"):
                if not Path(manifest[key]).exists():
                    return None
            return manifest
        except Exception:
            return None

    def load_cached_data(self):
        """Load the most recently fetched data from disk (no BigQuery call).
        Returns (cluster_df, hub_df, kepler_path, manifest) or raises."""
        manifest = self.get_cache_manifest()
        if manifest is None:
            raise FileNotFoundError("No cached data found. Fetch from BigQuery first.")

        kepler_path = manifest["kepler_csv"]
        # Load from the kepler CSV (primary format — has everything)
        cluster_df, hub_df = self._load_kepler_format(Path(kepler_path))
        return cluster_df, hub_df, kepler_path, manifest

    def load_from_csv(self):
        """Load data from local CSV files"""
        try:
            # Try to load Kepler format first (new format)
            kepler_path = self.project_root / "data" / "kepler_gl_final_main_17022026_csv.csv"
            
            if kepler_path.exists():
                print(f"Loading Kepler format CSV from {kepler_path}")
                return self._load_kepler_format(kepler_path)
            
            # Fallback to old format
            cluster_path = self.project_root / "data" / "clustering_live_02042026.csv"
            hub_path = self.project_root / "data" / "hub_Lat_Long02042026.csv"
            
            cluster_df = pd.read_csv(cluster_path)
            hub_df = pd.read_csv(hub_path)
            
            cluster_df = self._clean_cluster_data(cluster_df)
            hub_df = self._clean_hub_data(hub_df)
            
            return cluster_df, hub_df
            
        except Exception as e:
            raise Exception(f"Error loading CSV files: {str(e)}")
    
    def _load_kepler_format(self, filepath):
        """Load data from Kepler GL final format CSV"""
        try:
            # Read Kepler CSV
            df = pd.read_csv(filepath)
            
            # Rename columns to match expected format
            column_mapping = {
                'Hub ID': 'hub_id',
                'WKT': 'boundary',
                'CLUSTER_CODE': 'cluster_code',
                'Hub_Name': 'hub_name',
                'Cluster_Category': 'cluster_category',
                'Hub lat': 'hub_lat',
                'Hub Long': 'hub_lon',
                'latitude': 'center_lat',  # Centroid latitude
                'longitude': 'center_lon'  # Centroid longitude
            }
            
            df = df.rename(columns=column_mapping)
            
            # Extract pincode from cluster_code (e.g., "577526_A" -> "577526")
            df['pincode'] = df['cluster_code'].apply(self._extract_pincode)
            
            # Extract cluster suffix (e.g., "577526_A" -> "A")
            df['cluster_suffix'] = df['cluster_code'].apply(self._extract_cluster_suffix)
            
            # Parse surge amount from cluster_category (e.g., "Rs.4" -> 4)
            df['surge_amount'] = df['cluster_category'].apply(self._parse_surge_amount)
            
            # Create description field
            df['description'] = df['cluster_code']
            
            # Add default fields
            df['is_active'] = True
            df['cluster_type'] = 'payout_cluster'
            
            # Create cluster_df
            cluster_df = df[[
                'hub_id', 'hub_name', 'cluster_code', 'description',
                'boundary', 'pincode', 'surge_amount', 'is_active',
                'cluster_type', 'center_lat', 'center_lon', 'cluster_category'
            ]].copy()
            
            # Create hub_df (unique hubs only)
            hub_df = df[['hub_id', 'hub_name', 'hub_lat', 'hub_lon']].drop_duplicates(subset=['hub_id'])
            hub_df = hub_df.rename(columns={
                'hub_id': 'id',
                'hub_name': 'name',
                'hub_lat': 'latitude',
                'hub_lon': 'longitude'
            })
            hub_df['hub_category'] = 'ECOM_SELF_LM'
            hub_df['creation_date'] = pd.Timestamp.now()
            
            print(f"Loaded {len(cluster_df)} clusters from {len(hub_df)} unique hubs")
            print(f"Surge rates range: Rs.{cluster_df['surge_amount'].min():.1f} - Rs.{cluster_df['surge_amount'].max():.1f}")
            
            return cluster_df, hub_df
            
        except Exception as e:
            raise Exception(f"Error loading Kepler format: {str(e)}")
    
    @staticmethod
    def _extract_pincode(cluster_code):
        """Extract pincode from cluster code (e.g., '577526_A' -> '577526')"""
        if pd.isna(cluster_code):
            return ''
        
        # Split by underscore and take first part
        parts = str(cluster_code).split('_')
        return parts[0] if parts else ''
    
    @staticmethod
    def _extract_cluster_suffix(cluster_code):
        """Extract cluster suffix (e.g., '577526_A' -> 'A')"""
        if pd.isna(cluster_code):
            return ''
        
        # Split by underscore and take last part
        parts = str(cluster_code).split('_')
        return parts[-1] if len(parts) > 1 else ''
    
    @classmethod
    def _parse_surge_amount(cls, cluster_category):
        """
        Parse surge amount from category.
        - From kepler CSV: 'Rs.4' means ₹4.00 directly
        - From BigQuery: integer 1-20 maps via CATEGORY_TO_RATE
        """
        if pd.isna(cluster_category):
            return 0.0

        cat_str = str(cluster_category).strip()

        # If it has 'Rs.' or '₹' prefix, it's already the rate value (kepler CSV format)
        if 'Rs.' in cat_str or '₹' in cat_str:
            cleaned = cat_str.replace('Rs.', '').replace('₹', '').strip()
            try:
                return float(cleaned)
            except (ValueError, AttributeError):
                return 0.0

        # Otherwise it's a BQ integer category — look up the rate
        try:
            cat_int = int(float(cat_str))
            return cls.CATEGORY_TO_RATE.get(cat_int, 0.0)
        except (ValueError, AttributeError):
            return 0.0
    
    def load_from_bigquery(self, year=2026, month=3):
        """Legacy BigQuery loader (uses service account JSON). Kept for backward compatibility."""
        try:
            from google.cloud import bigquery

            credentials_path = self.project_root / "config" / "credentials.json"
            client = bigquery.Client.from_service_account_json(str(credentials_path))
            cluster_df, hub_df, _kepler_path = self.load_from_bigquery_robust(client, year, month)
            return cluster_df, hub_df

        except Exception as e:
            raise Exception(f"Error loading from BigQuery: {str(e)}")

    def load_from_bigquery_robust(self, bq_client, year=2026, month=4):
        """
        Load data from BigQuery using the robust auth client.
        Fetches live clusters + hub locations, saves CSVs, returns DataFrames.
        """
        from modules.bigquery_client import fetch_live_clusters, fetch_hub_locations

        # Fetch live clusters
        cluster_df, err = fetch_live_clusters(bq_client)
        if err:
            raise Exception(f"Failed to fetch clusters: {err}")

        # Fetch hub locations
        hub_df, err = fetch_hub_locations(bq_client, year, month)
        if err:
            raise Exception(f"Failed to fetch hub locations: {err}")

        # Clean data
        cluster_df = self._clean_cluster_data(cluster_df)
        hub_df = self._clean_hub_data(hub_df)

        # Save CSVs to data/ directory
        date_str = datetime.now().strftime('%d%m%Y')
        cluster_path = self.project_root / "data" / f"clustering_live_{date_str}.csv"
        hub_path = self.project_root / "data" / f"hub_Lat_Long{date_str}.csv"
        cluster_df.to_csv(cluster_path, index=False, encoding="utf-8")
        hub_df.to_csv(hub_path, index=False, encoding="utf-8")

        # Generate kepler CSV and save cache manifest
        kepler_df, kepler_path = self.generate_kepler_csv(cluster_df, hub_df)
        self.save_cache_manifest(cluster_path, hub_path, kepler_path)

        print(f"Saved {len(cluster_df)} clusters to {cluster_path}")
        print(f"Saved {len(hub_df)} hubs to {hub_path}")

        return cluster_df, hub_df, kepler_path

    def generate_kepler_csv(self, cluster_df, hub_df, output_path=None):
        """
        Generate kepler_gl_final_main CSV from cluster + hub data.
        Combines both datasets, computes centroids from WKT boundaries.
        Returns (kepler_df, output_path_str).
        """
        from shapely import wkt as wkt_module

        df = cluster_df.copy()

        # Extract pincode from cluster_code if not already present
        if 'pincode' not in df.columns or df['pincode'].isna().all():
            df['pincode'] = df['cluster_code'].apply(self._extract_pincode)

        # Build surge display using the already-parsed surge_amount (which went through CATEGORY_TO_RATE mapping)
        if 'surge_amount' in df.columns:
            def _fmt_rate(x):
                if pd.isna(x) or x == 0:
                    return "Rs.0"
                return f"Rs.{x:g}"  # e.g. Rs.0.5, Rs.4, Rs.10
            df['surge_display'] = df['surge_amount'].apply(_fmt_rate)
        else:
            df['surge_display'] = "Rs.0"

        # Join with hub data for hub lat/long
        hub_lookup = hub_df.set_index('id')[['latitude', 'longitude']].to_dict('index')
        df['hub_lat'] = df['hub_id'].map(lambda x: hub_lookup.get(x, {}).get('latitude'))
        df['hub_lon'] = df['hub_id'].map(lambda x: hub_lookup.get(x, {}).get('longitude'))

        # Compute centroid from WKT boundary (vectorized)
        def _extract_centroid(boundary_wkt):
            try:
                if pd.notna(boundary_wkt) and str(boundary_wkt).strip():
                    geom = wkt_module.loads(str(boundary_wkt))
                    c = geom.centroid
                    return pd.Series([c.y, c.x])
                return pd.Series([None, None])
            except Exception:
                return pd.Series([None, None])

        df[['centroid_lat', 'centroid_lon']] = df['boundary'].apply(_extract_centroid)

        # Build kepler format DataFrame
        kepler_df = pd.DataFrame({
            'Hub ID': df['hub_id'],
            'WKT': df['boundary'],
            'CLUSTER_CODE': df['cluster_code'],
            'Hub_Name': df['hub_name'],
            'Cluster_Category': df['surge_display'],
            'Hub lat': df['hub_lat'],
            'Hub Long': df['hub_lon'],
            'latitude': df['centroid_lat'],
            'longitude': df['centroid_lon']
        })

        # Drop rows with no geometry
        kepler_df = kepler_df.dropna(subset=['WKT'])

        # Save
        if output_path is None:
            date_str = datetime.now().strftime('%d%m%Y')
            output_path = self.project_root / "data" / f"kepler_gl_final_main_{date_str}_csv.csv"

        kepler_df.to_csv(output_path, index=False, encoding="utf-8")
        print(f"Generated kepler CSV: {len(kepler_df)} rows -> {output_path}")

        return kepler_df, str(output_path)
    
    def _clean_cluster_data(self, df):
        """Clean and standardize cluster data"""
        # Ensure required columns exist
        required_cols = ['hub_id', 'hub_name', 'cluster_code', 'boundary']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
        
        # Handle surge_amount (BQ returns column with all NULLs)
        if 'surge_amount' not in df.columns or df['surge_amount'].isna().all():
            if 'cluster_category' in df.columns:
                df['surge_amount'] = df['cluster_category'].apply(self._parse_surge_amount)
            else:
                df['surge_amount'] = 0
        
        # Convert surge_amount to numeric
        df['surge_amount'] = pd.to_numeric(df['surge_amount'], errors='coerce').fillna(0)
        
        # Clean pincode (BQ returns column with all NULLs)
        if 'pincode' not in df.columns or df['pincode'].isna().all() or (df['pincode'].astype(str).str.strip().isin(['', 'nan', 'None'])).all():
            if 'cluster_code' in df.columns:
                df['pincode'] = df['cluster_code'].apply(self._extract_pincode)
            else:
                df['pincode'] = ''
        
        # Normalize pincode: remove '.0' from float-converted values (e.g. '172102.0' -> '172102')
        df['pincode'] = df['pincode'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)

        # Remove duplicates
        df = df.drop_duplicates(subset=['cluster_code'])
        
        return df
    
    def _clean_hub_data(self, df):
        """Clean and standardize hub data"""
        # Rename columns if needed
        if 'name' not in df.columns and 'hub_name' in df.columns:
            df = df.rename(columns={'hub_name': 'name'})
        
        # Ensure numeric coordinates
        df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
        df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
        
        # Remove rows with missing coordinates
        df = df.dropna(subset=['latitude', 'longitude'])
        
        return df
    
    def process_data(self, cluster_df, hub_df):
        """Process and merge cluster and hub data"""
        processed_df = cluster_df.copy()
        
        # Parse WKT boundaries and extract centroid if not provided
        processed_df['geometry'] = None
        
        # Use provided centroid if available, otherwise calculate from geometry
        if 'center_lat' not in processed_df.columns or 'center_lon' not in processed_df.columns:
            processed_df['center_lat'] = None
            processed_df['center_lon'] = None
            calculate_centroid = True
        else:
            calculate_centroid = False
        
        def _parse_geom(boundary_val):
            try:
                if pd.notna(boundary_val) and boundary_val:
                    return wkt.loads(boundary_val)
            except Exception:
                pass
            return None

        processed_df['geometry'] = processed_df['boundary'].apply(_parse_geom)

        # Calculate centroids where needed
        needs_centroid = calculate_centroid | processed_df['center_lat'].isna()
        mask = needs_centroid & processed_df['geometry'].notna()
        if mask.any():
            centroids = processed_df.loc[mask, 'geometry'].apply(
                lambda g: pd.Series([g.centroid.y, g.centroid.x])
            )
            processed_df.loc[mask, 'center_lat'] = centroids[0].values
            processed_df.loc[mask, 'center_lon'] = centroids[1].values
        
        # Merge with hub data to get hub coordinates if not already present
        if 'hub_lat' not in processed_df.columns or 'hub_lon' not in processed_df.columns:
            hub_lookup = hub_df.set_index('id')[['latitude', 'longitude']].to_dict('index')
            
            processed_df['hub_lat'] = processed_df['hub_id'].map(
                lambda x: hub_lookup.get(x, {}).get('latitude', None)
            )
            processed_df['hub_lon'] = processed_df['hub_id'].map(
                lambda x: hub_lookup.get(x, {}).get('longitude', None)
            )
        
        # Create rate category
        processed_df['rate_category'] = processed_df['surge_amount'].apply(self._categorize_rate)
        
        # Ensure cluster_category exists (for display)
        if 'cluster_category' not in processed_df.columns:
            processed_df['cluster_category'] = processed_df['surge_amount'].apply(
                lambda x: f"Rs.{x:.1f}" if x > 0 else "Rs.0"
            )
        
        return processed_df
    
    @staticmethod
    def _categorize_rate(rate):
        """Categorize surge rates based on the 20 actual rate values"""
        if rate == 0:
            return "₹0 (Base)"
        elif rate <= 1.0:
            return "₹0.50-₹1 (Very Low)"
        elif rate <= 3.0:
            return "₹1.50-₹3 (Low)"
        elif rate <= 5.0:
            return "₹3.50-₹5 (Medium)"
        elif rate <= 9.0:
            return "₹6-₹9 (High)"
        else:
            return "₹10+ (Very High)"
