"""
Spatial Polygon Optimizer
=========================
Performs ACTUAL SPATIAL ANALYSIS of hub polygons:

1. Calculates real haversine distance from hub to each polygon centroid & boundary
2. Checks SOP compliance (is the polygon rate correct for its actual distance?)
3. Matches AWB shipments to polygons via point-in-polygon (actual lat/long)
4. Calculates per-polygon burn based on shipment landing density
5. Scores each polygon for optimization priority (spatial scoring model)
6. Recommends per-polygon: decrease rate OR increase radius
7. Generates before/after cost comparison per hub

No CPO heuristics — all decisions driven by actual geometry and shipment locations.
"""

import os
import pandas as pd
import numpy as np
from math import radians, sin, cos, sqrt, atan2, pi

try:
    from shapely.geometry import Point
    from shapely.prepared import prep as shapely_prep
    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False

try:
    import duckdb
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False


# ── SOP Pricing Slabs (distance → rate in ₹) ──
# Standard Operating Procedure: polygons are created outward from hub
# in concentric rings. Each ring's rate depends on distance from hub.
#
# STANDARD PRACTICE: C1 → C3 → C5 → C7 → C9 → C11 → C12 → C13 → ... → C20
# The even categories (C2, C4, C6, C8, C10) are SKIPPED in standard practice.
# When skipped, the next category's ring starts where the previous one ends.
# The intermediate rates (₹0.50, ₹1.50, ₹2.50, ₹3.50, ₹4.50) are sometimes
# used for fine-tuning but are NOT the standard SOP.
#
# PRIMARY SOP SLABS (standard practice — what compliance checks use):
SOP_SLABS = [
    (0,  4,  0.0),    # C1:  0–4 km   → ₹0   (Ring 1)
    (4,  12, 1.0),    # C3:  4–12 km  → ₹1   (Ring 2, skips C2)
    (12, 22, 2.0),    # C5:  12–22 km → ₹2   (Ring 3, skips C4)
    (22, 30, 3.0),    # C7:  22–30 km → ₹3   (Ring 4, skips C6)
    (30, 40, 4.0),    # C9:  30–40 km → ₹4   (Ring 5, skips C8)
    (40, 48, 5.0),    # C11: 40–48 km → ₹5   (Ring 6, skips C10)
    (48, 52, 6.0),    # C12: 48–52 km → ₹6
    (52, 56, 7.0),    # C13: 52–56 km → ₹7
    (56, 60, 8.0),    # C14: 56–60 km → ₹8
    (60, 64, 9.0),    # C15: 60–64 km → ₹9
    (64, 68, 10.0),   # C16: 64–68 km → ₹10
    (68, 72, 11.0),   # C17: 68–72 km → ₹11
    (72, 76, 12.0),   # C18: 72–76 km → ₹12
    (76, 80, 13.0),   # C19: 76–80 km → ₹13
]
# C20: beyond 80 km → ₹15.00

# FULL SOP (all 20 categories — used to check if a non-standard rate
# is at least within the fine-grained SOP table)
SOP_SLABS_FULL = [
    (0,  4,  0.0),    # C1
    (4,  8,  0.5),    # C2  (₹0.50 — sometimes used)
    (8,  12, 1.0),    # C3
    (12, 16, 1.5),    # C4  (₹1.50 — sometimes used)
    (16, 22, 2.0),    # C5
    (22, 26, 2.5),    # C6  (₹2.50 — sometimes used)
    (26, 30, 3.0),    # C7
    (30, 36, 3.5),    # C8  (₹3.50 — sometimes used)
    (36, 40, 4.0),    # C9
    (40, 44, 4.5),    # C10 (₹4.50 — sometimes used)
    (44, 48, 5.0),    # C11
    (48, 52, 6.0),    # C12
    (52, 56, 7.0),    # C13
    (56, 60, 8.0),    # C14
    (60, 64, 9.0),    # C15
    (64, 68, 10.0),   # C16
    (68, 72, 11.0),   # C17
    (72, 76, 12.0),   # C18
    (76, 80, 13.0),   # C19
]
# C20: 80+ km → ₹15.00

# Non-standard intermediate rates (sometimes used, not standard SOP)
NON_STANDARD_RATES = {0.5, 1.5, 2.5, 3.5, 4.5}

# SOP also specifies: Cappings=2 (all categories), Order Capping varies (100–1200)

# Standard SOP outer-boundary distances per ring (for custom radius detection)
# Primary bands: C1 ends at 4km, C3 at 12km, C5 at 22km, etc.
SOP_RING_BOUNDARIES = [4, 12, 22, 30, 40, 48, 52, 56, 60, 64, 68, 72, 76, 80]

# Category integer → rate (must match data_loader.CATEGORY_TO_RATE)
CATEGORY_TO_RATE = {
    1: 0.00, 2: 0.50, 3: 1.00, 4: 1.50, 5: 2.00,
    6: 2.50, 7: 3.00, 8: 3.50, 9: 4.00, 10: 4.50,
    11: 5.00, 12: 6.00, 13: 7.00, 14: 8.00, 15: 9.00,
    16: 10.00, 17: 11.00, 18: 12.00, 19: 13.00, 20: 15.00,
}


# ════════════════════════════════════════════════════
# SPATIAL UTILITIES
# ════════════════════════════════════════════════════

def _haversine_km(lat1, lon1, lat2, lon2):
    """Haversine distance between two points in km."""
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def _polygon_area_sq_km(geom):
    """Approximate area of a lat/lon polygon in sq km.
    Uses the spherical excess formula for small polygons."""
    if geom is None:
        return 0.0
    try:
        # Use the bounds to get a local scale factor
        minx, miny, maxx, maxy = geom.bounds
        mid_lat = (miny + maxy) / 2
        # 1 degree lat ≈ 111.32 km, 1 degree lon ≈ 111.32 * cos(lat) km
        km_per_deg_lat = 111.32
        km_per_deg_lon = 111.32 * cos(radians(mid_lat))
        # Approximate area: polygon area in degrees² * scale
        area_deg2 = geom.area  # in degree²
        return area_deg2 * km_per_deg_lat * km_per_deg_lon
    except Exception:
        return 0.0


def _get_sop_rate(distance_km):
    """Return the PRIMARY SOP rate for a given distance from hub.
    Uses standard practice: C1, C3, C5, C7, C9, C11, C12-C20."""
    for lo, hi, rate in SOP_SLABS:
        if lo <= distance_km < hi:
            return rate
    if distance_km >= 80:
        return 15.0
    return 0.0


def _get_sop_rate_full(distance_km):
    """Return the FULL SOP rate (all 20 categories) for a given distance.
    Used to check if a non-standard intermediate rate is still within SOP."""
    for lo, hi, rate in SOP_SLABS_FULL:
        if lo <= distance_km < hi:
            return rate
    if distance_km >= 80:
        return 15.0
    return 0.0


def _get_sop_slab_label(distance_km):
    """Human-readable slab label for a distance (primary SOP)."""
    for lo, hi, rate in SOP_SLABS:
        if lo <= distance_km < hi:
            return f"{lo}-{hi}km (₹{rate:.1f})"
    if distance_km >= 80:
        return f"80+km (₹15)"
    return "Unknown"


def _detect_custom_radius(max_distance_km):
    """Check if a polygon's outer boundary is at a non-standard SOP distance.

    Standard SOP rings end at 4, 12, 22, 30, 40, 48, 52, ... 80 km.
    Some hubs use custom radii like 3, 4.3, 4.5 km for operational reasons.

    Returns (is_custom, nearest_sop_boundary, deviation_km).
    """
    best_dev = float("inf")
    best_boundary = 0
    for b in SOP_RING_BOUNDARIES:
        dev = abs(max_distance_km - b)
        if dev < best_dev:
            best_dev = dev
            best_boundary = b
    # Consider "custom" if > 1.5km off from any SOP boundary
    is_custom = best_dev > 1.5
    return is_custom, best_boundary, round(best_dev, 2)


def _detect_exception_rate(actual_rate, sop_rate, distance_km, awb_density):
    """Detect if an above-SOP rate is likely a justified exception (criticality-based).

    Heuristics:
    - Rate is exactly 1 or 2 full SOP steps above expected → likely intentional
    - High AWB density (>50/km²) with above-SOP rate → critical zone
    - Rate gap > ₹3 above SOP at short distance (<15km) → strong signal of exception

    Returns (is_exception, reason).
    """
    gap = actual_rate - sop_rate
    if gap <= 0.01:
        return False, ""

    # Short distance (<15km) with high rate → likely criticality exception
    if distance_km < 15 and gap >= 2.0:
        return True, f"High rate (+₹{gap:.1f}) at {distance_km:.1f}km — likely criticality exception"

    # High density area with above-SOP rate → critical demand zone
    if awb_density > 50 and gap >= 1.0:
        return True, f"High density ({awb_density:.0f}/km²) with rate +₹{gap:.1f} above SOP — critical zone"

    # Rate is exactly at a higher SOP slab boundary (someone assigned a wrong slab)
    # but with very low gap (< ₹1), might just be miscategorized, not an exception
    return False, ""


def _classify_compliance(actual_rate, distance_km):
    """Classify a polygon's rate compliance against SOP.

    Returns (compliance_label, rate_gap):
      - 'compliant':     rate matches primary SOP for this distance
      - 'non_standard':  rate uses an intermediate category (C2/C4/C6/C8/C10)
                          but is within the full SOP table — acceptable
      - 'overcharged':   rate is HIGHER than what SOP allows for this distance
      - 'undercharged':  rate is LOWER than primary SOP (favorable to company)
    """
    primary_rate = _get_sop_rate(distance_km)
    full_rate = _get_sop_rate_full(distance_km)
    gap = actual_rate - primary_rate

    # Exact match with primary SOP → compliant
    if abs(gap) < 0.01:
        return "compliant", 0.0

    # Check if rate matches the full (fine-grained) SOP for this distance
    # This catches non-standard intermediate rates (C2/C4/C6/C8/C10)
    if abs(actual_rate - full_rate) < 0.01 and actual_rate in NON_STANDARD_RATES:
        return "non_standard", gap

    # Rate exceeds even the fine-grained SOP → definitely overcharged
    if actual_rate > full_rate + 0.01:
        return "overcharged", gap

    # Rate is above primary but within full SOP range (non-standard intermediate)
    if actual_rate > primary_rate + 0.01:
        return "overcharged", gap

    # Rate is below primary SOP and doesn't match full SOP → favorable
    return "undercharged", gap


# ════════════════════════════════════════════════════
# SPATIAL SCORING MODEL
# ════════════════════════════════════════════════════
# Scores each polygon for optimization priority.
# Higher score = more urgent to optimize.

def _compute_polygon_score(rate_gap, burn_monthly, awb_count, awb_density, area_sq_km):
    """
    Spatial optimization priority score (0–100).

    Factors:
      1. Rate gap penalty (40%): How far off from SOP rate
      2. Burn severity (30%): Monthly burn amount
      3. AWB density (20%): Higher density = bigger impact
      4. Area factor (10%): Larger polygons have more room for optimization
    """
    # 1. Rate gap score (0–40): bigger gap = higher score
    rate_score = min(abs(rate_gap) / 8.0 * 40, 40)

    # 2. Burn score (0–30): more burn = higher priority
    # Scale: ₹5000+/month is max score
    burn_score = min(burn_monthly / 5000 * 30, 30) if burn_monthly > 0 else 0

    # 3. AWB density score (0–20): more AWBs = bigger impact
    # Scale: 50+ AWBs/sq.km is max
    density_score = min(awb_density / 50 * 20, 20) if awb_density > 0 else 0

    # 4. Area factor (0–10): larger areas = more impact
    area_score = min(area_sq_km / 100 * 10, 10) if area_sq_km > 0 else 0

    return round(rate_score + burn_score + density_score + area_score, 1)


# ════════════════════════════════════════════════════
# MAIN CLASS
# ════════════════════════════════════════════════════

class PolygonOptimizer:
    """
    Spatial Polygon Analyzer — goes through each hub and each polygon,
    calculates actual radius, checks SOP compliance, analyzes AWB landing
    density, and recommends rate decrease or radius increase per polygon.

    This is the "AI agent" that performs the spatial analysis the user requested.
    """

    def __init__(self, cluster_df, hub_df, cpo_analytics=None, awb_counts=None,
                 awb_parquet_path=None):
        """
        Parameters
        ----------
        cluster_df : DataFrame
            Processed cluster data with: hub_id, hub_name, hub_lat, hub_lon,
            pincode, surge_amount, geometry (Shapely polygon), boundary (WKT).
        hub_df : DataFrame
            Hub locations: id, name, latitude, longitude.
        cpo_analytics : CPOAnalytics, optional
            For enriched cost data.
        awb_counts : dict, optional
            {(hub_name, pincode): awb_count} — fallback when parquet unavailable.
        awb_parquet_path : str, optional
            Path to AWB parquet file for spatial point-in-polygon analysis.
        """
        self.cluster_df = cluster_df.copy() if cluster_df is not None else pd.DataFrame()
        self.hub_df = hub_df.copy() if hub_df is not None else pd.DataFrame()
        self.cpo_analytics = cpo_analytics
        self.awb_counts = awb_counts or {}
        self.awb_parquet_path = awb_parquet_path

        # Caches
        self._spatial_metrics = None     # Per-polygon spatial metrics
        self._awb_polygon_map = None     # AWB → polygon matching results
        self._hub_analysis = None        # Hub-level aggregated analysis
        self._suggestions = None         # Optimization suggestions
        self._full_analysis = None       # Complete polygon-level analysis

    # ──────────────────────────────────────────────────
    #  STEP 1: Compute spatial metrics for every polygon
    # ──────────────────────────────────────────────────

    def _compute_spatial_metrics(self) -> pd.DataFrame:
        """For each polygon, compute:
        - centroid_distance_km: haversine distance from hub to polygon centroid
        - max_distance_km: farthest point of polygon from hub
        - min_distance_km: nearest point of polygon from hub
        - area_sq_km: approximate area
        - sop_rate: what the rate SHOULD be per SOP
        - actual_rate: what the rate IS (surge_amount)
        - rate_gap: actual - SOP (positive = overcharged)
        - compliance: 'compliant' / 'overcharged' / 'undercharged'
        """
        if self._spatial_metrics is not None:
            return self._spatial_metrics

        df = self.cluster_df
        if df.empty:
            return pd.DataFrame()

        # Ensure surge_amount is numeric
        if "surge_amount" in df.columns:
            df["surge_amount"] = pd.to_numeric(df["surge_amount"], errors="coerce").fillna(0)

        rows = []
        for idx, row in df.iterrows():
            geom = row.get("geometry")
            hub_lat = float(row.get("hub_lat", 0) or 0)
            hub_lon = float(row.get("hub_lon", 0) or 0)
            actual_rate = float(row.get("surge_amount", 0) or 0)
            hub_name = str(row.get("hub_name", ""))
            hub_id = str(row.get("hub_id", ""))
            pincode = str(row.get("pincode", "")).replace(".0", "").strip()
            cluster_code = str(row.get("cluster_code", ""))

            if geom is None or hub_lat == 0 or hub_lon == 0:
                continue

            try:
                centroid = geom.centroid
                centroid_dist = _haversine_km(hub_lat, hub_lon, centroid.y, centroid.x)

                # Min and max distance from hub to polygon boundary
                coords = list(geom.exterior.coords)
                point_dists = [
                    _haversine_km(hub_lat, hub_lon, y, x)
                    for x, y in coords
                ]
                max_dist = max(point_dists) if point_dists else centroid_dist
                min_dist = min(point_dists) if point_dists else centroid_dist

                area = _polygon_area_sq_km(geom)
                sop_rate = _get_sop_rate(centroid_dist)
                sop_slab = _get_sop_slab_label(centroid_dist)
                compliance, rate_gap = _classify_compliance(actual_rate, centroid_dist)

                # Detect custom radius (non-standard polygon boundary distance)
                is_custom_radius, nearest_sop_boundary, radius_deviation = _detect_custom_radius(max_dist)
                polygon_radius = round(max_dist - min_dist, 2)  # ring width

                rows.append({
                    "hub_name": hub_name,
                    "hub_id": hub_id,
                    "hub_lat": hub_lat,
                    "hub_lon": hub_lon,
                    "pincode": pincode,
                    "cluster_code": cluster_code,
                    "centroid_lat": centroid.y,
                    "centroid_lon": centroid.x,
                    "centroid_distance_km": round(centroid_dist, 2),
                    "max_distance_km": round(max_dist, 2),
                    "min_distance_km": round(min_dist, 2),
                    "polygon_radius_km": polygon_radius,
                    "is_custom_radius": is_custom_radius,
                    "nearest_sop_boundary_km": nearest_sop_boundary,
                    "radius_deviation_km": radius_deviation,
                    "area_sq_km": round(area, 3),
                    "actual_rate": actual_rate,
                    "sop_rate": sop_rate,
                    "rate_gap": round(rate_gap, 2),
                    "sop_slab": sop_slab,
                    "compliance": compliance,
                    "geometry": geom,
                })
            except Exception:
                continue

        result = pd.DataFrame(rows)
        self._spatial_metrics = result
        return result

    # ──────────────────────────────────────────────────
    #  STEP 2: Match AWBs to polygons (point-in-polygon)
    # ──────────────────────────────────────────────────

    def _load_awb_coordinates(self) -> pd.DataFrame:
        """Load AWB lat/long data from parquet.
        Returns DataFrame with columns: lat, long, hub, pincode."""
        if not self.awb_parquet_path or not os.path.exists(self.awb_parquet_path):
            return pd.DataFrame()

        try:
            if HAS_DUCKDB:
                con = duckdb.connect()
                df = con.execute("""
                    SELECT CAST(hub AS VARCHAR) AS hub,
                           CAST(pincode AS VARCHAR) AS pincode,
                           TRY_CAST(lat AS DOUBLE) AS lat,
                           TRY_CAST(long AS DOUBLE) AS lng
                    FROM read_parquet(?)
                    WHERE TRY_CAST(lat AS DOUBLE) IS NOT NULL
                      AND TRY_CAST(long AS DOUBLE) IS NOT NULL
                      AND TRY_CAST(lat AS DOUBLE) != 0
                      AND TRY_CAST(long AS DOUBLE) != 0
                      AND TRY_CAST(lat AS DOUBLE) BETWEEN 6 AND 38
                      AND TRY_CAST(long AS DOUBLE) BETWEEN 68 AND 98
                """, [self.awb_parquet_path]).fetchdf()
                con.close()
                return df
            else:
                df = pd.read_parquet(self.awb_parquet_path,
                                     columns=["hub", "pincode", "lat", "long"])
                df = df.dropna(subset=["lat", "long"])
                df = df[(df["lat"] != 0) & (df["long"] != 0)]
                df = df[(df["lat"].between(6, 38)) & (df["long"].between(68, 98))]
                df = df.rename(columns={"long": "lng"})
                df["hub"] = df["hub"].astype(str)
                df["pincode"] = df["pincode"].astype(str).str.replace(".0", "", regex=False)
                return df
        except Exception as e:
            print(f"AWB coordinate load error: {e}")
            return pd.DataFrame()

    def _match_awbs_to_polygons(self) -> pd.DataFrame:
        """Point-in-polygon matching: for each AWB, find which polygon it lands in.

        Strategy:
        1. Group polygons by hub_name
        2. For each hub, get AWBs belonging to that hub
        3. For each AWB, check containment against hub's polygons
        4. Match to smallest-area polygon that contains the point (innermost)

        Returns DataFrame with columns:
            hub_name, pincode, cluster_code, actual_rate, awb_count,
            centroid_distance_km, sop_rate, compliance
        """
        if self._awb_polygon_map is not None:
            return self._awb_polygon_map

        metrics = self._compute_spatial_metrics()
        if metrics.empty:
            self._awb_polygon_map = pd.DataFrame()
            return self._awb_polygon_map

        awb_df = self._load_awb_coordinates()
        use_spatial = len(awb_df) > 0 and HAS_SHAPELY

        if use_spatial:
            return self._do_spatial_awb_matching(metrics, awb_df)
        else:
            return self._do_fallback_awb_matching(metrics)

    def _do_spatial_awb_matching(self, metrics, awb_df) -> pd.DataFrame:
        """Actual point-in-polygon AWB matching using Shapely.

        Optimized: processes AWBs hub-by-hub, uses numpy vectorization for
        coordinate extraction, and prepared geometries for fast containment.
        For large datasets (>1M AWBs), samples per hub for speed.
        """
        # Build hub → prepared polygons lookup
        hub_polygons = {}
        for _, row in metrics.iterrows():
            hn = row["hub_name"]
            geom = row["geometry"]
            if geom is None:
                continue
            if hn not in hub_polygons:
                hub_polygons[hn] = []
            hub_polygons[hn].append({
                "prepared": shapely_prep(geom),
                "geom": geom,
                "area": row["area_sq_km"],
                "cluster_code": row["cluster_code"],
                "pincode": row["pincode"],
                "actual_rate": row["actual_rate"],
                "centroid_distance_km": row["centroid_distance_km"],
                "max_distance_km": row["max_distance_km"],
                "min_distance_km": row["min_distance_km"],
                "polygon_radius_km": row.get("polygon_radius_km", 0),
                "is_custom_radius": row.get("is_custom_radius", False),
                "sop_rate": row["sop_rate"],
                "compliance": row["compliance"],
                "rate_gap": row["rate_gap"],
            })

        # Sort each hub's polygons by area ascending (match smallest = innermost first)
        for hn in hub_polygons:
            hub_polygons[hn].sort(key=lambda p: p["area"])

        # Determine if we need sampling (>5M AWBs = sample 20% per hub)
        total_awbs = len(awb_df)
        sample_frac = 1.0
        scale_factor = 1.0
        if total_awbs > 5_000_000:
            sample_frac = 0.2
            scale_factor = 1.0 / sample_frac

        # Count AWBs per polygon
        polygon_awb_counts = {}

        # Only process hubs that have polygons
        hubs_with_polygons = set(hub_polygons.keys())
        relevant_awbs = awb_df[awb_df["hub"].isin(hubs_with_polygons)]

        for hub_name, group in relevant_awbs.groupby("hub"):
            polys = hub_polygons[hub_name]

            # Sample if dataset is large
            if sample_frac < 1.0 and len(group) > 1000:
                group = group.sample(frac=sample_frac, random_state=42)

            # Extract coordinates as numpy arrays for speed
            lats = group["lat"].values
            lngs = group["lng"].values

            for i in range(len(lats)):
                point = Point(float(lngs[i]), float(lats[i]))
                for poly in polys:
                    if poly["prepared"].contains(point):
                        cc = poly["cluster_code"]
                        polygon_awb_counts[cc] = polygon_awb_counts.get(cc, 0) + 1
                        break

        # Build result: merge AWB counts back into metrics
        result_rows = []
        for _, row in metrics.iterrows():
            cc = row["cluster_code"]
            raw_count = polygon_awb_counts.get(cc, 0)
            # Scale up if we sampled
            awb_count = int(round(raw_count * scale_factor))
            area = row["area_sq_km"]
            awb_density = awb_count / area if area > 0 else 0

            # Detect exception rates (criticality-based above-SOP rates)
            is_exception, exception_reason = _detect_exception_rate(
                row["actual_rate"], row["sop_rate"],
                row["centroid_distance_km"], awb_density,
            )

            result_rows.append({
                "hub_name": row["hub_name"],
                "hub_id": row["hub_id"],
                "pincode": row["pincode"],
                "cluster_code": cc,
                "centroid_distance_km": row["centroid_distance_km"],
                "max_distance_km": row["max_distance_km"],
                "min_distance_km": row["min_distance_km"],
                "polygon_radius_km": row.get("polygon_radius_km", 0),
                "is_custom_radius": row.get("is_custom_radius", False),
                "nearest_sop_boundary_km": row.get("nearest_sop_boundary_km", 0),
                "radius_deviation_km": row.get("radius_deviation_km", 0),
                "area_sq_km": area,
                "actual_rate": row["actual_rate"],
                "sop_rate": row["sop_rate"],
                "rate_gap": row["rate_gap"],
                "sop_slab": row["sop_slab"],
                "compliance": row["compliance"],
                "is_exception_rate": is_exception,
                "exception_reason": exception_reason,
                "awb_count": awb_count,
                "awb_density_per_sqkm": round(awb_density, 2),
                "monthly_cost": round(awb_count * row["actual_rate"], 2),
                "sop_cost": round(awb_count * row["sop_rate"], 2),
                "monthly_burn": round(awb_count * max(row["rate_gap"], 0), 2),
                "monthly_saving_if_sop": round(awb_count * max(row["rate_gap"], 0), 2),
                "data_source": "spatial" if sample_frac == 1.0 else "spatial_sampled",
            })

        self._awb_polygon_map = pd.DataFrame(result_rows)
        return self._awb_polygon_map

    def _do_fallback_awb_matching(self, metrics) -> pd.DataFrame:
        """Fallback: use awb_counts dict when parquet unavailable."""
        # Build pincode-only fallback
        pin_only = {}
        for (h, p), c in self.awb_counts.items():
            pin_only[p] = pin_only.get(p, 0) + c

        result_rows = []
        for _, row in metrics.iterrows():
            hn = row["hub_name"]
            pin = row["pincode"]
            awb_count = self.awb_counts.get((hn, pin), 0)
            if awb_count == 0:
                awb_count = pin_only.get(pin, 0)

            area = row["area_sq_km"]
            awb_density = awb_count / area if area > 0 else 0

            # Detect exception rates
            is_exception, exception_reason = _detect_exception_rate(
                row["actual_rate"], row["sop_rate"],
                row["centroid_distance_km"], awb_density,
            )

            result_rows.append({
                "hub_name": row["hub_name"],
                "hub_id": row["hub_id"],
                "pincode": pin,
                "cluster_code": row["cluster_code"],
                "centroid_distance_km": row["centroid_distance_km"],
                "max_distance_km": row["max_distance_km"],
                "min_distance_km": row["min_distance_km"],
                "polygon_radius_km": row.get("polygon_radius_km", 0),
                "is_custom_radius": row.get("is_custom_radius", False),
                "nearest_sop_boundary_km": row.get("nearest_sop_boundary_km", 0),
                "radius_deviation_km": row.get("radius_deviation_km", 0),
                "area_sq_km": area,
                "actual_rate": row["actual_rate"],
                "sop_rate": row["sop_rate"],
                "rate_gap": row["rate_gap"],
                "sop_slab": row["sop_slab"],
                "compliance": row["compliance"],
                "is_exception_rate": is_exception,
                "exception_reason": exception_reason,
                "awb_count": awb_count,
                "awb_density_per_sqkm": round(awb_density, 2),
                "monthly_cost": round(awb_count * row["actual_rate"], 2),
                "sop_cost": round(awb_count * row["sop_rate"], 2),
                "monthly_burn": round(awb_count * max(row["rate_gap"], 0), 2),
                "monthly_saving_if_sop": round(awb_count * max(row["rate_gap"], 0), 2),
                "data_source": "count_based",
            })

        self._awb_polygon_map = pd.DataFrame(result_rows)
        return self._awb_polygon_map

    # ──────────────────────────────────────────────────
    #  STEP 3: Full polygon-level analysis with scoring
    # ──────────────────────────────────────────────────

    def _build_full_polygon_analysis(self) -> pd.DataFrame:
        """Complete per-polygon analysis with spatial scoring.

        Adds optimization_score and recommended_action to each polygon.
        """
        if self._full_analysis is not None:
            return self._full_analysis

        polygon_data = self._match_awbs_to_polygons()
        if polygon_data.empty:
            self._full_analysis = pd.DataFrame()
            return self._full_analysis

        # Score each polygon
        scores = []
        actions = []
        for _, row in polygon_data.iterrows():
            score = _compute_polygon_score(
                rate_gap=row["rate_gap"],
                burn_monthly=row["monthly_burn"],
                awb_count=row["awb_count"],
                awb_density=row["awb_density_per_sqkm"],
                area_sq_km=row["area_sq_km"],
            )
            scores.append(score)

            # Decision: decrease rate OR increase radius?
            action = self._decide_action(row)
            actions.append(action)

        result = polygon_data.copy()
        result["optimization_score"] = scores
        result["recommended_action"] = actions
        result = result.sort_values("optimization_score", ascending=False).reset_index(drop=True)

        self._full_analysis = result
        return result

    def _decide_action(self, polygon_row) -> str:
        """Decision engine: for a single polygon, what should we do?

        This analyzes like a 20-year geospatial analytics professional:
        1. Check if rate is an intentional exception (criticality-based) — don't blindly reduce
        2. Check if custom radius is being used — analyze if it's optimal
        3. If rate > SOP (overcharged) and NOT an exception → DECREASE RATE to SOP
        4. If rate uses non-standard intermediate (C2/C4/C6/C8/C10) → suggest standardizing
        5. If rate < SOP but low AWB density → EXPAND RADIUS to absorb more volume
        6. If high AWB density at high rate → highest priority to DECREASE RATE
        7. If zero AWBs → monitor or decommission
        """
        rate_gap = polygon_row["rate_gap"]
        awb_count = polygon_row["awb_count"]
        actual_rate = polygon_row["actual_rate"]
        sop_rate = polygon_row["sop_rate"]
        compliance = polygon_row["compliance"]
        awb_density = polygon_row["awb_density_per_sqkm"]
        distance = polygon_row["centroid_distance_km"]
        is_exception = polygon_row.get("is_exception_rate", False)
        exception_reason = polygon_row.get("exception_reason", "")
        is_custom = polygon_row.get("is_custom_radius", False)
        custom_detail = f" [Custom radius: {polygon_row.get('polygon_radius_km', 0):.1f}km ring]" if is_custom else ""

        if awb_count == 0:
            if compliance == "overcharged":
                return (
                    f"DECREASE RATE: ₹{actual_rate:.1f} → ₹{sop_rate:.1f} "
                    f"(no shipments, overcharged for {distance:.1f}km){custom_detail}"
                )
            return f"MONITOR: No shipments in this polygon{custom_detail}"

        if compliance == "overcharged":
            saving = round(awb_count * rate_gap, 0)
            if is_exception:
                # Exception rate — flag for review but still show savings potential
                return (
                    f"REVIEW EXCEPTION: ₹{actual_rate:.1f} at {distance:.1f}km (SOP ₹{sop_rate:.1f}) — "
                    f"{exception_reason}. "
                    f"If not justified: save ₹{saving:,.0f}/mo ({awb_count} AWBs){custom_detail}"
                )
            return (
                f"DECREASE RATE: ₹{actual_rate:.1f} → ₹{sop_rate:.1f} "
                f"(save ₹{saving:,.0f}/mo, {awb_count} AWBs at {distance:.1f}km){custom_detail}"
            )

        if compliance == "non_standard":
            saving = round(awb_count * abs(rate_gap), 0) if rate_gap > 0 else 0
            if saving > 0:
                return (
                    f"STANDARDIZE: ₹{actual_rate:.1f} → ₹{sop_rate:.1f} "
                    f"(non-standard rate at {distance:.1f}km, save ₹{saving:,.0f}/mo, {awb_count} AWBs)"
                )
            return (
                f"NON-STANDARD OK: ₹{actual_rate:.1f} at {distance:.1f}km "
                f"(intermediate category, ₹{abs(rate_gap):.2f} below SOP — favorable)"
            )

        if compliance == "undercharged":
            if awb_density < 5 and awb_count > 0:
                return (
                    f"EXPAND RADIUS: Polygon at {distance:.1f}km rated ₹{actual_rate:.1f} "
                    f"(SOP ₹{sop_rate:.1f}), low density {awb_density:.1f}/km² — "
                    f"expand to absorb nearby shipments{custom_detail}"
                )
            if is_custom:
                return (
                    f"CUSTOM RADIUS OK: ₹{actual_rate:.1f} at {distance:.1f}km "
                    f"(below SOP ₹{sop_rate:.1f}, custom radius polygon){custom_detail}"
                )
            return f"OK (favorable): Rate ₹{actual_rate:.1f} < SOP ₹{sop_rate:.1f} at {distance:.1f}km"

        if compliance == "compliant":
            if is_custom:
                return (
                    f"COMPLIANT (custom radius): Rate ₹{actual_rate:.1f} matches SOP for {distance:.1f}km"
                    f"{custom_detail}"
                )
            return f"COMPLIANT: Rate ₹{actual_rate:.1f} matches SOP for {distance:.1f}km"

        return f"OK: Rate ₹{actual_rate:.1f} at {distance:.1f}km"

    # ──────────────────────────────────────────────────
    #  PUBLIC API: analyze_hub_polygons
    # ──────────────────────────────────────────────────

    def analyze_hub_polygons(self) -> pd.DataFrame:
        """Analyze every hub's polygons spatially and return hub-level summary.

        Returns DataFrame with columns:
            hub_name, hub_id, hub_lat, hub_lon, polygon_count, total_awb,
            total_cost, sop_cost, total_burn, total_saving_potential,
            avg_distance_km, max_distance_km, sop_compliant_pct,
            overcharged_count, undercharged_count, avg_optimization_score,
            top_action
        """
        if self._hub_analysis is not None:
            return self._hub_analysis

        full = self._build_full_polygon_analysis()
        if full.empty:
            return pd.DataFrame()

        rows = []
        for hub_name, grp in full.groupby("hub_name"):
            hub_id = grp["hub_id"].iloc[0]
            hub_lat = float(grp.iloc[0].get("hub_lat", 0)) if "hub_lat" in grp.columns else 0
            hub_lon = float(grp.iloc[0].get("hub_lon", 0)) if "hub_lon" in grp.columns else 0

            # Get hub coords from hub_df if not in polygon data
            if (hub_lat == 0 or hub_lon == 0) and self.hub_df is not None and not self.hub_df.empty:
                name_col = "name" if "name" in self.hub_df.columns else "hub_name"
                id_col = "id" if "id" in self.hub_df.columns else "hub_id"
                hub_match = self.hub_df[self.hub_df[name_col] == hub_name] if name_col in self.hub_df.columns else pd.DataFrame()
                if len(hub_match) == 0 and id_col in self.hub_df.columns:
                    hub_match = self.hub_df[self.hub_df[id_col].astype(str) == str(hub_id)]
                if len(hub_match) > 0:
                    lat_col = "latitude" if "latitude" in hub_match.columns else "hub_lat"
                    lon_col = "longitude" if "longitude" in hub_match.columns else "hub_lon"
                    hub_lat = float(hub_match.iloc[0].get(lat_col, 0))
                    hub_lon = float(hub_match.iloc[0].get(lon_col, 0))

            total_awb = int(grp["awb_count"].sum())
            total_cost = grp["monthly_cost"].sum()
            sop_cost = grp["sop_cost"].sum()
            total_burn = grp["monthly_burn"].sum()
            saving_potential = grp["monthly_saving_if_sop"].sum()

            compliant = (grp["compliance"] == "compliant").sum()
            non_standard = (grp["compliance"] == "non_standard").sum()
            overcharged = (grp["compliance"] == "overcharged").sum()
            undercharged = (grp["compliance"] == "undercharged").sum()
            compliant_pct = round((compliant + non_standard) / len(grp) * 100, 1) if len(grp) > 0 else 0

            # Count exception rates and custom radius polygons
            exception_count = int(grp.get("is_exception_rate", pd.Series(False)).sum()) if "is_exception_rate" in grp.columns else 0
            custom_radius_count = int(grp.get("is_custom_radius", pd.Series(False)).sum()) if "is_custom_radius" in grp.columns else 0

            avg_score = grp["optimization_score"].mean()
            # Top action = the action from the highest-scoring polygon
            top_poly = grp.sort_values("optimization_score", ascending=False).iloc[0]
            top_action = top_poly["recommended_action"]

            cpo = total_cost / total_awb if total_awb > 0 else 0
            sop_cpo = sop_cost / total_awb if total_awb > 0 else 0

            rows.append({
                "hub_name": str(hub_name),
                "hub_id": str(hub_id),
                "hub_lat": hub_lat,
                "hub_lon": hub_lon,
                "polygon_count": len(grp),
                "total_awb": total_awb,
                "total_cost": round(total_cost, 2),
                "sop_cost": round(sop_cost, 2),
                "total_burn": round(total_burn, 2),
                "total_saving_potential": round(saving_potential, 2),
                "current_cpo": round(cpo, 2),
                "sop_cpo": round(sop_cpo, 2),
                "avg_distance_km": round(grp["centroid_distance_km"].mean(), 1),
                "max_distance_km": round(grp["max_distance_km"].max(), 1),
                "sop_compliant_pct": compliant_pct,
                "overcharged_count": int(overcharged),
                "undercharged_count": int(undercharged),
                "compliant_count": int(compliant),
                "exception_rate_count": exception_count,
                "custom_radius_count": custom_radius_count,
                "avg_optimization_score": round(avg_score, 1),
                "top_action": top_action,
            })

        result = pd.DataFrame(rows)
        if not result.empty:
            result = result.sort_values("total_burn", ascending=False).reset_index(drop=True)
        self._hub_analysis = result
        return result

    # ──────────────────────────────────────────────────
    #  PUBLIC API: suggest_optimal_radius
    # ──────────────────────────────────────────────────

    def suggest_optimal_radius(self, target_saving=2000000) -> pd.DataFrame:
        """For each hub, suggest specific polygon-level changes to reach savings target.

        Each suggestion is based on ACTUAL spatial analysis:
        - Overcharged polygons: reduce rate to SOP
        - Low-density polygons: expand radius to absorb more volume

        Returns DataFrame with columns:
            hub_name, hub_id, total_awb, polygon_count,
            current_monthly_cost, suggested_monthly_cost, monthly_saving,
            annual_saving, current_avg_rate, suggested_avg_rate,
            current_cpo, suggested_cpo, changes (list), impact_pct, priority,
            overcharged_polygons, avg_distance_km, sop_compliant_pct
        """
        if self._suggestions is not None:
            return self._suggestions

        full = self._build_full_polygon_analysis()
        if full.empty:
            return pd.DataFrame()

        hub_analysis = self.analyze_hub_polygons()
        suggestions = []
        cumulative_saving = 0.0

        for _, hub_row in hub_analysis.iterrows():
            hub_name = hub_row["hub_name"]
            if hub_row["total_awb"] == 0:
                continue

            hub_polygons = full[full["hub_name"] == hub_name]
            changes = []
            hub_saving = 0.0
            new_cost = hub_row["total_cost"]

            # Process overcharged polygons: reduce rate to primary SOP
            # Separate exception rates from clear overcharges
            overcharged = hub_polygons[
                hub_polygons["compliance"].isin(["overcharged", "non_standard"])
            ].sort_values("monthly_burn", ascending=False)

            for _, poly in overcharged.iterrows():
                if poly["awb_count"] == 0 and poly["monthly_burn"] == 0:
                    continue
                saving = poly["monthly_saving_if_sop"]
                if saving <= 0:
                    continue

                is_exception = poly.get("is_exception_rate", False)
                is_custom = poly.get("is_custom_radius", False)

                if is_exception:
                    action_type = "review_exception"
                    action_label = "REVIEW EXCEPTION"
                    detail = f" [{poly.get('exception_reason', 'criticality-based')}]"
                elif poly["compliance"] == "non_standard":
                    action_type = "standardize"
                    action_label = "STANDARDIZE"
                    detail = ""
                else:
                    action_type = "rate_decrease"
                    action_label = "DECREASE RATE"
                    detail = ""

                custom_note = f" [Custom {poly.get('polygon_radius_km', 0):.1f}km radius]" if is_custom else ""
                changes.append({
                    "polygon": poly["cluster_code"],
                    "pincode": poly["pincode"],
                    "distance_km": poly["centroid_distance_km"],
                    "from_rate": poly["actual_rate"],
                    "to_rate": poly["sop_rate"],
                    "awb_affected": poly["awb_count"],
                    "monthly_saving": round(saving, 2),
                    "is_exception": is_exception,
                    "is_custom_radius": is_custom,
                    "action": f"{action_label}: ₹{poly['actual_rate']:.1f} → ₹{poly['sop_rate']:.1f} "
                              f"({poly['centroid_distance_km']:.1f}km from hub, "
                              f"{poly['awb_count']} AWBs, save ₹{saving:,.0f}/mo)"
                              f"{detail}{custom_note}",
                    "type": action_type,
                })
                hub_saving += saving
                new_cost -= saving

            # Process low-density undercharged polygons: suggest radius expansion
            low_density = hub_polygons[
                (hub_polygons["compliance"] == "undercharged") &
                (hub_polygons["awb_density_per_sqkm"] < 5) &
                (hub_polygons["awb_count"] > 0)
            ]
            for _, poly in low_density.iterrows():
                # Expanding radius could absorb nearby higher-rate shipments
                potential = poly["awb_count"] * abs(poly["rate_gap"]) * 0.3  # conservative 30%
                if potential > 100:
                    changes.append({
                        "polygon": poly["cluster_code"],
                        "pincode": poly["pincode"],
                        "distance_km": poly["centroid_distance_km"],
                        "from_rate": poly["actual_rate"],
                        "to_rate": poly["actual_rate"],
                        "awb_affected": poly["awb_count"],
                        "monthly_saving": round(potential, 2),
                        "action": f"EXPAND RADIUS: Grow polygon at {poly['centroid_distance_km']:.1f}km "
                                  f"to absorb {poly['awb_count']} nearby AWBs at ₹{poly['actual_rate']:.1f}",
                        "type": "radius_expansion",
                    })
                    hub_saving += potential
                    new_cost -= potential

            if hub_saving <= 0:
                continue

            new_cpo = new_cost / hub_row["total_awb"] if hub_row["total_awb"] > 0 else 0
            new_avg_rate = new_cost / hub_row["total_awb"] if hub_row["total_awb"] > 0 else 0

            suggestions.append({
                "hub_name": hub_name,
                "hub_id": hub_row["hub_id"],
                "total_awb": hub_row["total_awb"],
                "cluster_count": hub_row["polygon_count"],
                "current_monthly_cost": round(hub_row["total_cost"], 0),
                "suggested_monthly_cost": round(new_cost, 0),
                "monthly_saving": round(hub_saving, 0),
                "annual_saving": round(hub_saving * 12, 0),
                "current_avg_rate": round(hub_row["current_cpo"], 2),
                "suggested_avg_rate": round(new_avg_rate, 2),
                "current_cpo": hub_row["current_cpo"],
                "suggested_cpo": round(new_cpo, 2),
                "changes": changes,
                "impact_pct": round(hub_saving / hub_row["total_cost"] * 100, 1)
                             if hub_row["total_cost"] > 0 else 0,
                "overcharged_polygons": hub_row["overcharged_count"],
                "avg_distance_km": hub_row["avg_distance_km"],
                "sop_compliant_pct": hub_row["sop_compliant_pct"],
            })
            cumulative_saving += hub_saving

        result = pd.DataFrame(suggestions)
        if result.empty:
            return result

        result = result.sort_values("monthly_saving", ascending=False).reset_index(drop=True)

        # Assign priority based on contribution to target
        running = 0.0
        priorities = []
        for _, row in result.iterrows():
            running += row["monthly_saving"]
            if running <= target_saving * 0.5:
                priorities.append("Critical")
            elif running <= target_saving * 0.8:
                priorities.append("High")
            elif running <= target_saving:
                priorities.append("Medium")
            else:
                priorities.append("Low")
        result["priority"] = priorities

        self._suggestions = result
        return result

    # ──────────────────────────────────────────────────
    #  PUBLIC API: generate_before_after
    # ──────────────────────────────────────────────────

    def generate_before_after(self, suggestions_df=None) -> list:
        """Generate detailed before/after comparison for each hub.

        Each comparison includes:
        - Spatial metrics (distances, SOP compliance)
        - Per-polygon rate changes with distances
        - Cost breakdown by distance band
        """
        if suggestions_df is None:
            suggestions_df = self.suggest_optimal_radius()
        if suggestions_df is None or (hasattr(suggestions_df, 'empty') and suggestions_df.empty):
            return []

        full = self._build_full_polygon_analysis()
        comparisons = []

        for _, sug in suggestions_df.iterrows():
            hub_name = sug["hub_name"]
            hub_polygons = full[full["hub_name"] == hub_name] if not full.empty else pd.DataFrame()

            # Build before: rate distribution by distance band
            before_by_slab = {}
            after_by_slab = {}
            if not hub_polygons.empty:
                for _, poly in hub_polygons.iterrows():
                    slab = poly["sop_slab"]
                    if slab not in before_by_slab:
                        before_by_slab[slab] = {"awb": 0, "cost": 0, "polygons": 0, "avg_rate": 0, "rates": []}
                    before_by_slab[slab]["awb"] += poly["awb_count"]
                    before_by_slab[slab]["cost"] += poly["monthly_cost"]
                    before_by_slab[slab]["polygons"] += 1
                    before_by_slab[slab]["rates"].append(poly["actual_rate"])

                # Compute avg rates
                for slab in before_by_slab:
                    rates = before_by_slab[slab]["rates"]
                    before_by_slab[slab]["avg_rate"] = round(sum(rates) / len(rates), 2) if rates else 0
                    del before_by_slab[slab]["rates"]
                    before_by_slab[slab]["cost"] = round(before_by_slab[slab]["cost"], 0)

            # Build after: apply changes
            after_by_slab = {}
            for slab, data in before_by_slab.items():
                after_by_slab[slab] = dict(data)  # copy

            total_change_saving = 0
            for chg in sug.get("changes", []):
                if chg["type"] == "rate_decrease":
                    # Find the slab for this polygon's distance
                    dist = chg["distance_km"]
                    slab = _get_sop_slab_label(dist)
                    if slab in after_by_slab:
                        after_by_slab[slab]["cost"] -= chg["monthly_saving"]
                        after_by_slab[slab]["avg_rate"] = chg["to_rate"]
                    total_change_saving += chg["monthly_saving"]

            cost_reduction = sug["current_monthly_cost"] - sug["suggested_monthly_cost"]

            comparisons.append({
                "hub_name": hub_name,
                "total_awb": sug["total_awb"],
                "cluster_count": sug["cluster_count"],
                "priority": sug.get("priority", "Medium"),
                "avg_distance_km": sug.get("avg_distance_km", 0),
                "sop_compliant_pct": sug.get("sop_compliant_pct", 0),
                "overcharged_polygons": sug.get("overcharged_polygons", 0),
                "before": {
                    "monthly_cost": sug["current_monthly_cost"],
                    "cpo": sug["current_cpo"],
                    "avg_rate": sug["current_avg_rate"],
                    "rate_by_distance": before_by_slab,
                },
                "after": {
                    "monthly_cost": sug["suggested_monthly_cost"],
                    "cpo": sug["suggested_cpo"],
                    "avg_rate": sug["suggested_avg_rate"],
                    "rate_by_distance": after_by_slab,
                },
                "delta": {
                    "cost_reduction": round(cost_reduction, 0),
                    "annual_reduction": round(cost_reduction * 12, 0),
                    "cpo_reduction": round(sug["current_cpo"] - sug["suggested_cpo"], 2),
                    "pct_reduction": sug["impact_pct"],
                },
                "changes": sug.get("changes", []),
            })

        return comparisons

    # ──────────────────────────────────────────────────
    #  PUBLIC API: get_optimization_summary
    # ──────────────────────────────────────────────────

    def get_optimization_summary(self, target_saving=2000000) -> dict:
        """High-level summary of the spatial optimization opportunity."""
        hub_analysis = self.analyze_hub_polygons()
        suggestions = self.suggest_optimal_radius(target_saving=target_saving)
        full = self._build_full_polygon_analysis()

        if hub_analysis.empty:
            return {
                "total_hubs_analyzed": 0, "hubs_with_changes": 0,
                "total_monthly_saving": 0, "total_annual_saving": 0,
                "target_met": False, "target_pct": 0,
            }

        monthly_saving = suggestions["monthly_saving"].sum() if not suggestions.empty else 0
        annual_saving = monthly_saving * 12

        # Spatial insights
        total_polygons = len(full) if not full.empty else 0
        overcharged_polygons = int((full["compliance"] == "overcharged").sum()) if not full.empty else 0
        compliant_polygons = int((full["compliance"] == "compliant").sum()) if not full.empty else 0
        non_standard_polygons = int((full["compliance"] == "non_standard").sum()) if not full.empty else 0
        undercharged_polygons = int((full["compliance"] == "undercharged").sum()) if not full.empty else 0

        total_burn = float(full["monthly_burn"].sum()) if not full.empty else 0
        total_awb = int(full["awb_count"].sum()) if not full.empty else 0

        # AWBs affected by changes
        awb_affected = 0
        rate_decrease_count = 0
        radius_expansion_count = 0
        review_exception_count = 0
        if not suggestions.empty:
            for _, row in suggestions.iterrows():
                for chg in row.get("changes", []):
                    awb_affected += chg.get("awb_affected", 0)
                    if chg.get("type") == "rate_decrease":
                        rate_decrease_count += 1
                    elif chg.get("type") == "radius_expansion":
                        radius_expansion_count += 1
                    elif chg.get("type") == "review_exception":
                        review_exception_count += 1

        # Exception and custom radius counts
        exception_polygons = int(full["is_exception_rate"].sum()) if not full.empty and "is_exception_rate" in full.columns else 0
        custom_radius_polygons = int(full["is_custom_radius"].sum()) if not full.empty and "is_custom_radius" in full.columns else 0

        # Data quality / confidence
        data_source = full["data_source"].iloc[0] if not full.empty and "data_source" in full.columns else "unknown"
        awb_with_data = int((full["awb_count"] > 0).sum()) if not full.empty else 0
        confidence = round(awb_with_data / total_polygons * 100, 1) if total_polygons > 0 else 0

        # Friendly label for data source
        ds_labels = {
            "spatial": "Spatial (AWB lat/long point-in-polygon)",
            "spatial_sampled": "Spatial Sampled (20% AWBs, scaled up)",
            "count_based": "Count-based (hub x pincode counts)",
        }

        return {
            "total_hubs_analyzed": len(hub_analysis),
            "hubs_with_changes": len(suggestions),
            "total_monthly_saving": round(monthly_saving, 0),
            "total_annual_saving": round(annual_saving, 0),
            "target_met": monthly_saving >= target_saving,
            "target_pct": round(monthly_saving / target_saving * 100, 1) if target_saving > 0 else 0,
            "top_hubs": suggestions.head(10)[
                ["hub_name", "monthly_saving", "priority"]
            ].to_dict("records") if not suggestions.empty else [],
            "total_awb_affected": awb_affected,
            "total_awb": total_awb,
            "avg_cost_reduction_pct": round(
                suggestions["impact_pct"].mean(), 1
            ) if not suggestions.empty else 0,
            "confidence": confidence,
            # Spatial-specific metrics
            "total_polygons_analyzed": total_polygons,
            "overcharged_polygons": overcharged_polygons,
            "compliant_polygons": compliant_polygons,
            "non_standard_polygons": non_standard_polygons,
            "undercharged_polygons": undercharged_polygons,
            "total_monthly_burn": round(total_burn, 0),
            "rate_decrease_actions": rate_decrease_count,
            "radius_expansion_actions": radius_expansion_count,
            "review_exception_actions": review_exception_count,
            "exception_rate_polygons": exception_polygons,
            "custom_radius_polygons": custom_radius_polygons,
            "data_source": ds_labels.get(data_source, "Count-based (hub x pincode)"),
            "sop_compliance_pct": round(
                (compliant_polygons + non_standard_polygons) / total_polygons * 100, 1
            ) if total_polygons > 0 else 0,
        }

    # ──────────────────────────────────────────────────
    #  PUBLIC API: validate_no_hub_impact
    # ──────────────────────────────────────────────────

    def validate_no_hub_impact(self, suggestions_df=None) -> list:
        """Validate that suggestions don't negatively impact hub operations."""
        if suggestions_df is None:
            suggestions_df = self.suggest_optimal_radius()
        if suggestions_df is None or (hasattr(suggestions_df, 'empty') and suggestions_df.empty):
            return []

        warnings = []
        for _, sug in suggestions_df.iterrows():
            hub = sug["hub_name"]

            # Check 1: Rate increases (should never happen, our algo only decreases)
            for chg in sug.get("changes", []):
                if chg.get("to_rate", 0) > chg.get("from_rate", 0):
                    warnings.append({
                        "hub_name": hub,
                        "warning_type": "rate_increase",
                        "message": f"Rate increase: ₹{chg['from_rate']} → ₹{chg['to_rate']} at {chg.get('distance_km', 0):.1f}km",
                        "severity": "high",
                    })

            # Check 2: Excessive cost reduction (>60% is suspicious)
            if sug["impact_pct"] > 60:
                warnings.append({
                    "hub_name": hub,
                    "warning_type": "excessive_reduction",
                    "message": f"Cost reduction of {sug['impact_pct']:.1f}% — verify polygon boundaries are correct",
                    "severity": "medium",
                })

            # Check 3: Very few AWBs (low statistical confidence)
            if sug["total_awb"] < 50:
                warnings.append({
                    "hub_name": hub,
                    "warning_type": "low_volume",
                    "message": f"Only {sug['total_awb']} AWBs — spatial analysis confidence is low",
                    "severity": "low",
                })

            # Check 4: Large distance polygons (>40km) — verify hub can service
            if sug.get("avg_distance_km", 0) > 40:
                warnings.append({
                    "hub_name": hub,
                    "warning_type": "extreme_distance",
                    "message": f"Avg polygon distance {sug['avg_distance_km']:.1f}km — verify hub can service this range",
                    "severity": "medium",
                })

        return warnings

    # ──────────────────────────────────────────────────
    #  GANDALF INTEGRATION: get detailed polygon report
    # ──────────────────────────────────────────────────

    def get_polygon_detail_report(self, hub_name=None, top_n=50) -> str:
        """Generate a detailed markdown report of polygon spatial analysis.
        Used by GANDALF AI to provide insights."""
        full = self._build_full_polygon_analysis()
        if full.empty:
            return "No polygon data available for spatial analysis."

        if hub_name:
            full = full[full["hub_name"].str.lower() == hub_name.lower()]
            if full.empty:
                return f"No polygons found for hub '{hub_name}'."

        lines = []
        lines.append("## Spatial Polygon Analysis Report\n")

        # Overall stats
        total = len(full)
        overcharged = (full["compliance"] == "overcharged").sum()
        compliant = (full["compliance"] == "compliant").sum()
        lines.append(f"**Polygons analyzed:** {total}")
        lines.append(f"**SOP Compliant:** {compliant} ({compliant/total*100:.0f}%)")
        lines.append(f"**Overcharged:** {overcharged} ({overcharged/total*100:.0f}%)")
        lines.append(f"**Total Monthly Burn:** ₹{full['monthly_burn'].sum():,.0f}")
        lines.append(f"**Total Saving Potential:** ₹{full['monthly_saving_if_sop'].sum():,.0f}/mo\n")

        # Top polygons by burn
        top_burn = full[full["monthly_burn"] > 0].head(top_n)
        if len(top_burn) > 0:
            lines.append("### Top Polygons by Burn\n")
            lines.append("| Hub | Pincode | Distance | Rate | SOP Rate | Gap | AWBs | Burn/mo | Action |")
            lines.append("|-----|---------|----------|------|----------|-----|------|---------|--------|")
            for _, p in top_burn.iterrows():
                lines.append(
                    f"| {p['hub_name'][:20]} | {p['pincode']} | {p['centroid_distance_km']:.1f}km "
                    f"| ₹{p['actual_rate']:.1f} | ₹{p['sop_rate']:.1f} | ₹{p['rate_gap']:.1f} "
                    f"| {p['awb_count']:,} | ₹{p['monthly_burn']:,.0f} "
                    f"| {'↓Rate' if p['rate_gap'] > 0 else '↑Radius'} |"
                )

        return "\n".join(lines)

    def get_sop_compliance_report(self) -> str:
        """Generate SOP compliance report for GANDALF.
        Uses PRIMARY SOP bands (C1, C3, C5, C7, C9, C11, C12-C20)."""
        full = self._build_full_polygon_analysis()
        if full.empty:
            return "No polygon data available."

        lines = []
        lines.append("## SOP Compliance Report\n")
        lines.append("*Standard SOP: C1(0-4km)→C3(4-12km)→C5(12-22km)→C7(22-30km)"
                      "→C9(30-40km)→C11(40-48km)→C12-C20(48-80+km)*\n")

        # By distance slab (primary)
        lines.append("### Compliance by Distance Band (Primary SOP)\n")
        lines.append("| Distance Band | SOP Rate | Total | Compliant | Non-Std | Overcharged | Undercharged | Avg Gap |")
        lines.append("|---------------|----------|-------|-----------|---------|-------------|--------------|---------|")

        for lo, hi, sop_rate in SOP_SLABS:
            slab = full[
                (full["centroid_distance_km"] >= lo) &
                (full["centroid_distance_km"] < hi)
            ]
            if len(slab) == 0:
                continue
            c = (slab["compliance"] == "compliant").sum()
            ns = (slab["compliance"] == "non_standard").sum()
            o = (slab["compliance"] == "overcharged").sum()
            u = (slab["compliance"] == "undercharged").sum()
            avg_gap = slab["rate_gap"].mean()
            lines.append(
                f"| {lo}-{hi}km | ₹{sop_rate:.1f} | {len(slab)} "
                f"| {c} | {ns} | {o} | {u} | ₹{avg_gap:+.2f} |"
            )

        # Beyond 80km
        far = full[full["centroid_distance_km"] >= 80]
        if len(far) > 0:
            c = (far["compliance"] == "compliant").sum()
            o = (far["compliance"] == "overcharged").sum()
            lines.append(f"| 80+km | ₹15.0 | {len(far)} | {c} | 0 | {o} | 0 | — |")

        return "\n".join(lines)
