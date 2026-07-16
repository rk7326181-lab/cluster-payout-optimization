"""
Hub Anomaly Detection
=====================
Two detection modes:

1. HUB LOCATION DRIFT  (detect_hub_location_changes)
   Detects when hub GPS coordinates change between data fetches.
   Uses haversine distance; flags hubs that moved > threshold_km.

2. HUB-POLYGON CENTROID ANOMALY  (detect_hub_centroid_anomalies)
   G.A.N.D.A.L.F. core geospatial check.
   A hub is CORRECT when it is positioned near the centre of its
   service-area polygons.  A hub is ANOMALOUS when it is outside
   its polygon, near the boundary, or significantly displaced from
   the weighted polygon centroid.

   Input: kepler_gl CSV DataFrame with columns:
       Hub ID, WKT, CLUSTER_CODE, Hub_Name, Cluster_Category,
       Hub lat, Hub Long, latitude, longitude

   Classification:
       Correct          -- hub well-centred, all checks pass
       Warning          -- moderate displacement or partial issues
       Critical Anomaly -- hub outside polygon / major displacement
       Data Error       -- invalid/corrupt coordinates

Snapshot format (hub_location_snapshot.json):
{
  "<hub_id>": {"name": "...", "lat": 12.34, "lon": 77.56},
  ...
}
"""

import json
import math
from datetime import datetime
from pathlib import Path

# shapely is optional; centroid anomaly detection requires it
try:
    from shapely import wkt as _shapely_wkt
    from shapely.geometry import Point as _ShapelyPoint
    _SHAPELY_OK = True
except ImportError:
    _SHAPELY_OK = False


SNAPSHOT_FILENAME = "hub_location_snapshot.json"
ANOMALIES_FILENAME = "hub_anomalies.json"


# ──────────────────────────────────────────────
# Haversine distance (km)
# ──────────────────────────────────────────────

def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ──────────────────────────────────────────────
# Snapshot persistence
# ──────────────────────────────────────────────

def save_hub_snapshot(hub_df, data_dir: Path):
    """Save current hub locations as the new baseline snapshot.

    hub_df columns expected: id (or hub_id), name (or hub_name),
    latitude (or hub_lat), longitude (or hub_lon).
    """
    snapshot = {}
    df = hub_df.copy()

    # Normalise column names
    renames = {}
    col_map = {c.lower(): c for c in df.columns}
    for src, dst in [
        ("hub_id", "id"), ("hub_name", "name"),
        ("hub_lat", "latitude"), ("hub_lon", "longitude"),
    ]:
        if src in col_map and dst not in col_map:
            renames[col_map[src]] = dst
    if renames:
        df = df.rename(columns=renames)

    for _, row in df.iterrows():
        hub_id = str(row.get("id", "")).strip()
        if not hub_id:
            continue
        try:
            lat = float(row["latitude"])
            lon = float(row["longitude"])
            if math.isnan(lat) or math.isnan(lon):
                continue
        except (KeyError, TypeError, ValueError):
            continue
        snapshot[hub_id] = {
            "name": str(row.get("name", hub_id)),
            "lat":  round(lat, 6),
            "lon":  round(lon, 6),
        }

    path = Path(data_dir) / SNAPSHOT_FILENAME
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)
    return path


def load_hub_snapshot(data_dir: Path):
    """Return {hub_id: {name, lat, lon}} or {} if no snapshot exists."""
    path = Path(data_dir) / SNAPSHOT_FILENAME
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# ──────────────────────────────────────────────
# Anomaly persistence
# ──────────────────────────────────────────────

def save_anomalies(anomalies: list, data_dir: Path):
    path = Path(data_dir) / ANOMALIES_FILENAME
    with open(path, "w", encoding="utf-8") as f:
        json.dump(anomalies, f, indent=2)


def load_anomalies(data_dir: Path) -> list:
    path = Path(data_dir) / ANOMALIES_FILENAME
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def clear_anomalies(data_dir: Path):
    path = Path(data_dir) / ANOMALIES_FILENAME
    if path.exists():
        path.unlink()


# ──────────────────────────────────────────────
# Core detection
# ──────────────────────────────────────────────

def detect_hub_location_changes(new_hub_df, data_dir: Path, threshold_km: float = 0.1):
    """Compare new_hub_df against the saved snapshot.

    Returns a list of anomaly dicts for hubs whose location changed by
    more than threshold_km.  Also saves a new snapshot and writes
    hub_anomalies.json.

    Steps:
    1. Load previous snapshot.
    2. Build a lookup from new_hub_df.
    3. For each hub in both old and new, compute haversine distance.
    4. Flag if distance > threshold_km.
    5. Persist new snapshot (replaces old baseline).
    6. Persist anomalies list.
    """
    prev_snapshot = load_hub_snapshot(data_dir)

    # Build new lookup
    new_snapshot = {}
    df = new_hub_df.copy()

    renames = {}
    col_map = {c.lower(): c for c in df.columns}
    for src, dst in [
        ("hub_id", "id"), ("hub_name", "name"),
        ("hub_lat", "latitude"), ("hub_lon", "longitude"),
    ]:
        if src in col_map and dst not in col_map:
            renames[col_map[src]] = dst
    if renames:
        df = df.rename(columns=renames)

    for _, row in df.iterrows():
        hub_id = str(row.get("id", "")).strip()
        if not hub_id:
            continue
        try:
            lat = float(row["latitude"])
            lon = float(row["longitude"])
            if math.isnan(lat) or math.isnan(lon):
                continue
        except (KeyError, TypeError, ValueError):
            continue
        new_snapshot[hub_id] = {
            "name": str(row.get("name", hub_id)),
            "lat":  round(lat, 6),
            "lon":  round(lon, 6),
        }

    anomalies = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if prev_snapshot:
        for hub_id, new_info in new_snapshot.items():
            old_info = prev_snapshot.get(hub_id)
            if old_info is None:
                continue  # New hub — not an anomaly
            dist = _haversine_km(
                old_info["lat"], old_info["lon"],
                new_info["lat"],  new_info["lon"],
            )
            if dist >= threshold_km:
                anomalies.append({
                    "hub_id":      hub_id,
                    "hub_name":    new_info["name"],
                    "old_lat":     old_info["lat"],
                    "old_lon":     old_info["lon"],
                    "new_lat":     new_info["lat"],
                    "new_lon":     new_info["lon"],
                    "distance_km": round(dist, 4),
                    "distance_m":  round(dist * 1000, 1),
                    "detected_at": now_str,
                })

        # Sort most-moved first
        anomalies.sort(key=lambda x: x["distance_km"], reverse=True)

    # Persist new snapshot (becomes baseline for the NEXT fetch)
    save_hub_snapshot(new_hub_df, data_dir)

    # Persist anomaly list
    save_anomalies(anomalies, data_dir)

    return anomalies


# ══════════════════════════════════════════════════════════════════════
#  G.A.N.D.A.L.F. GEOSPATIAL CENTROID ANOMALY DETECTION  v2.0
#  Hub-not-centred-in-polygon detection from kepler_gl CSV data.
#
#  New in v2.0:
#    - Polygon perimeter calculation
#    - Hub-to-boundary distances (min / max / avg / std / skewness)
#    - Polygon compactness (isoperimetric quotient)
#    - Coverage density & radius variance
#    - Confidence score 0-100
#    - Full feature vector for G.A.N.D.A.L.F. ML training
# ══════════════════════════════════════════════════════════════════════

# India bounding box — used to filter corrupt/placeholder coordinates.
_INDIA = dict(lat_min=6.0, lat_max=38.0, lon_min=68.0, lon_max=98.0)


def _in_india(lat, lon):
    return (_INDIA["lat_min"] <= lat <= _INDIA["lat_max"] and
            _INDIA["lon_min"] <= lon <= _INDIA["lon_max"])


def _bearing(lat1, lon1, lat2, lon2):
    """Compass bearing (degrees, 0-360) from point 1 to point 2."""
    lat1r, lat2r = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(lat2r)
    y = math.cos(lat1r) * math.sin(lat2r) - math.sin(lat1r) * math.cos(lat2r) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _cat_to_float(cat_str):
    try:
        return float(str(cat_str).replace("Rs.", "").strip())
    except (ValueError, TypeError):
        return 0.0


def _parse_wkt_geometry(wkt_str):
    """
    Parse WKT string and return (geometry, centroid_lat, centroid_lon,
    area_deg2, perimeter_deg) or (None, None, None, None, None).
    Only returns valid geometries whose centroid falls inside India bbox.
    """
    if not _SHAPELY_OK or not wkt_str:
        return None, None, None, None, None
    try:
        geom = _shapely_wkt.loads(wkt_str)
        c = geom.centroid
        if not _in_india(c.y, c.x):
            return None, None, None, None, None
        return geom, c.y, c.x, geom.area, geom.length
    except Exception:
        return None, None, None, None, None


def _parse_wkt_centroid(wkt_str):
    """Return (centroid_lat, centroid_lon, area_deg2) or (None, None, None)."""
    _, clat, clon, area, _ = _parse_wkt_geometry(wkt_str)
    return clat, clon, area


def _hub_in_wkt(hub_lat, hub_lon, wkt_str):
    """True if the hub point is inside the WKT polygon."""
    if not _SHAPELY_OK or not wkt_str:
        return False
    try:
        geom = _shapely_wkt.loads(wkt_str)
        return geom.contains(_ShapelyPoint(hub_lon, hub_lat))
    except Exception:
        return False


def _boundary_distances_km(hub_lat, hub_lon, geom):
    """
    Sample boundary points of a shapely geometry and return
    (min_km, max_km, mean_km, std_km, skewness) of Haversine distances
    from the hub to each boundary vertex.
    Returns (None, None, None, None, None) if geometry is invalid.
    """
    if geom is None:
        return None, None, None, None, None
    try:
        import statistics
        coords = list(geom.exterior.coords) if hasattr(geom, "exterior") else []
        if len(coords) < 2:
            return None, None, None, None, None
        dists = [_haversine_km(hub_lat, hub_lon, lat, lon) for lon, lat in coords]
        if len(dists) < 2:
            return None, None, None, None, None
        mn   = min(dists)
        mx   = max(dists)
        mean = sum(dists) / len(dists)
        variance = sum((d - mean) ** 2 for d in dists) / len(dists)
        std  = variance ** 0.5
        # Pearson skewness: 3*(mean - median) / std
        median = sorted(dists)[len(dists) // 2]
        skew = 3 * (mean - median) / std if std > 0 else 0.0
        return round(mn, 4), round(mx, 4), round(mean, 4), round(std, 4), round(skew, 4)
    except Exception:
        return None, None, None, None, None


def _polygon_metrics_km(geom, centroid_lat):
    """
    Return (area_km2, perimeter_km, compactness) for a shapely geometry.
    compactness = 4*pi*area / perimeter^2  (isoperimetric quotient, 1.0 = circle)
    """
    if geom is None:
        return None, None, None
    try:
        import math as _m
        km_per_deg_lat = 111.32
        km_per_deg_lon = 111.32 * _m.cos(_m.radians(centroid_lat))
        area_km2 = geom.area * km_per_deg_lat * km_per_deg_lon
        # Convert perimeter (degrees) to km using average of lat/lon scale
        peri_km  = geom.length * (km_per_deg_lat + km_per_deg_lon) / 2
        compactness = (4 * _m.pi * area_km2) / (peri_km ** 2) if peri_km > 0 else 0.0
        return round(area_km2, 4), round(peri_km, 4), round(compactness, 4)
    except Exception:
        return None, None, None


def _confidence_score(dist_km, rs0_dist, in_rs0, in_any,
                      asym_deg, monotonicity, overshoot_km, boundary_std):
    """
    Compute anomaly confidence score 0-100 using a weighted penalty model.
    100 = certain anomaly, 0 = certainly correct.
    """
    penalties = 0.0

    # Hub not in any polygon — severe
    if not in_any:
        penalties += 40
    elif not in_rs0:
        penalties += 15

    # Centroid displacement
    penalties += min(dist_km / 10.0, 1.0) * 25

    # Rs.0 ring displacement
    if rs0_dist is not None:
        penalties += min(rs0_dist / 6.0, 1.0) * 15

    # Directional asymmetry (normalised against 180 degrees max)
    penalties += min((asym_deg or 0) / 180.0, 1.0) * 8

    # Ring monotonicity broken
    penalties += (1.0 - (monotonicity or 1.0)) * 7

    # Radius overshoot
    if overshoot_km is not None:
        penalties += min(max(overshoot_km, 0) / 20.0, 1.0) * 5

    return round(min(penalties, 100.0), 1)


def _classify_hub(dist_km, rs0_dist, in_rs0, in_any, asym_deg, monotonicity, overshoot_km,
                  boundary_std=None):
    """
    Return (status, reason_string).
    status values: 'Correct' | 'Warning' | 'Critical Anomaly'
    """
    reasons = []

    # ── Critical ──────────────────────────────────────────────────────
    if not in_any:
        reasons.append("Hub sits outside ALL service polygons")
    if rs0_dist is not None and rs0_dist > 4.0:
        reasons.append(f"Hub is {rs0_dist:.2f} km from Rs.0 centroid (expected <4 km)")
    if dist_km > 6.0:
        reasons.append(f"Hub is {dist_km:.2f} km from weighted service centroid (expected <3 km)")
    if overshoot_km is not None and overshoot_km > 10.0:
        reasons.append(f"Polygons extend {overshoot_km:.1f} km beyond expected max radius")
    if monotonicity < 0.4:
        reasons.append(f"Payout ring order is broken (monotonicity={monotonicity:.2f})")
    if reasons:
        return "Critical Anomaly", "; ".join(reasons)

    # ── Warning ────────────────────────────────────────────────────────
    if not in_rs0 and in_any:
        reasons.append("Hub is not inside the Rs.0 (core) polygon")
    if rs0_dist is not None and rs0_dist > 2.0:
        reasons.append(f"Hub is {rs0_dist:.2f} km from Rs.0 centroid (expected <2 km)")
    if dist_km > 3.0:
        reasons.append(f"Hub is {dist_km:.2f} km from weighted service centroid (3-6 km)")
    if asym_deg > 120:
        reasons.append(f"Polygon coverage is strongly asymmetric ({asym_deg:.0f} deg)")
    if overshoot_km is not None and overshoot_km > 5.0:
        reasons.append(f"Polygons extend {overshoot_km:.1f} km beyond expected max radius")
    if monotonicity < 0.6:
        reasons.append(f"Payout ring order partially broken (monotonicity={monotonicity:.2f})")
    if boundary_std is not None and boundary_std > 3.0:
        reasons.append(f"High boundary distance variance ({boundary_std:.2f} km std dev) — skewed coverage")
    if reasons:
        return "Warning", "; ".join(reasons)

    return "Correct", "Hub is well-centred within its service area"


def _anomaly_score(dist_km, rs0_dist, in_rs0, in_any, asym_deg, monotonicity, overshoot_km):
    s = min(dist_km, 50) * 2.0
    s += min(rs0_dist or 0, 20) * 1.5
    s += 0 if in_rs0 else 3.0
    s += 0 if in_any else 5.0
    s += min(asym_deg or 0, 180) / 30
    s += min(max(overshoot_km or 0, 0), 30) * 0.3
    s += (1 - (monotonicity or 1)) * 4.0
    return round(s, 3)


def detect_hub_centroid_anomalies(kepler_df, expected_rs0_radius_km=4.0):
    """
    Analyse a kepler_gl-format DataFrame and return a list of hub-level
    anomaly records.

    Parameters
    ----------
    kepler_df : pandas.DataFrame
        Must contain: Hub ID, WKT, Hub_Name, Cluster_Category,
                      Hub lat, Hub Long
    expected_rs0_radius_km : float
        Expected radius of the Rs.0 (innermost) ring in km.  Default 4.

    Returns
    -------
    list[dict]  — one record per hub, sorted by anomaly_score descending.

    Each record contains:
        hub_id, hub_name, hub_lat, hub_lon,
        n_polygons, n_corrupt_polygons,
        weighted_centroid_lat, weighted_centroid_lon,
        hub_to_weighted_centroid_km, hub_to_rs0_centroid_km,
        hub_in_rs0_polygon, hub_in_any_polygon,
        dir_asymmetry_deg, ring_monotonicity,
        max_poly_centroid_dist_km, min_poly_centroid_dist_km,
        max_tier, expected_max_radius_km, radius_overshoot_km,
        anomaly_score, status, reason, data_quality
    """
    if not _SHAPELY_OK:
        raise ImportError(
            "shapely is required for centroid anomaly detection. "
            "Install with: pip install shapely"
        )

    import numpy as np  # imported here to keep top-level import light

    results = []

    for hub_id, grp in kepler_df.groupby("Hub ID"):
        hub_name     = str(grp["Hub_Name"].iloc[0])
        hub_lat_raw  = float(grp["Hub lat"].iloc[0]) if not _is_nan(grp["Hub lat"].iloc[0]) else None
        hub_lon_raw  = float(grp["Hub Long"].iloc[0]) if not _is_nan(grp["Hub Long"].iloc[0]) else None

        if hub_lat_raw is None or hub_lon_raw is None:
            results.append(_err_record(hub_id, hub_name, hub_lat_raw, hub_lon_raw,
                                       len(grp), "NULL_COORDINATES"))
            continue

        # Detect lat/lon swap (lat has a longitude-range value)
        latlon_swapped = (_INDIA["lon_min"] <= hub_lat_raw <= _INDIA["lon_max"] and
                          _INDIA["lat_min"] <= hub_lon_raw <= _INDIA["lat_max"])
        if latlon_swapped:
            hub_lat, hub_lon = hub_lon_raw, hub_lat_raw
            dq_note = "LAT_LON_SWAPPED_AUTO_CORRECTED"
        else:
            hub_lat, hub_lon = hub_lat_raw, hub_lon_raw
            dq_note = "OK"

        if not _in_india(hub_lat, hub_lon):
            results.append(_err_record(hub_id, hub_name, hub_lat, hub_lon,
                                       len(grp), "HUB_OUTSIDE_INDIA_BBOX"))
            continue

        # Parse polygons — keep only those with valid India centroids
        valid_rows = []
        corrupt_count = 0
        for _, row in grp.iterrows():
            geom, clat, clon, area, peri = _parse_wkt_geometry(str(row.get("WKT", "")))
            if clat is None:
                corrupt_count += 1
                continue
            valid_rows.append({
                "wkt":    str(row.get("WKT", "")),
                "geom":   geom,
                "clat":   clat,
                "clon":   clon,
                "area":   area,
                "peri":   peri,
                "tier":   _cat_to_float(row.get("Cluster_Category", "0")),
                "code":   str(row.get("CLUSTER_CODE", "")),
            })

        if not valid_rows:
            results.append(_err_record(hub_id, hub_name, hub_lat, hub_lon,
                                       len(grp), f"ALL_POLYGONS_CORRUPT; {dq_note}"))
            continue

        # Area-weighted centroid of all polygons
        total_area = sum(r["area"] for r in valid_rows)
        if total_area > 0:
            wt_lat = sum(r["clat"] * r["area"] for r in valid_rows) / total_area
            wt_lon = sum(r["clon"] * r["area"] for r in valid_rows) / total_area
        else:
            wt_lat = sum(r["clat"] for r in valid_rows) / len(valid_rows)
            wt_lon = sum(r["clon"] for r in valid_rows) / len(valid_rows)

        hub_to_weighted = _haversine_km(hub_lat, hub_lon, wt_lat, wt_lon)

        # Rs.0 ring
        rs0_rows = [r for r in valid_rows if r["tier"] == 0.0]
        if rs0_rows:
            rs0_area = sum(r["area"] for r in rs0_rows)
            if rs0_area > 0:
                rs0_clat = sum(r["clat"] * r["area"] for r in rs0_rows) / rs0_area
                rs0_clon = sum(r["clon"] * r["area"] for r in rs0_rows) / rs0_area
            else:
                rs0_clat = sum(r["clat"] for r in rs0_rows) / len(rs0_rows)
                rs0_clon = sum(r["clon"] for r in rs0_rows) / len(rs0_rows)
            hub_to_rs0 = _haversine_km(hub_lat, hub_lon, rs0_clat, rs0_clon)
            hub_in_rs0 = any(_hub_in_wkt(hub_lat, hub_lon, r["wkt"]) for r in rs0_rows)
        else:
            hub_to_rs0 = None
            hub_in_rs0 = False

        hub_in_any = any(_hub_in_wkt(hub_lat, hub_lon, r["wkt"]) for r in valid_rows)

        # Per-polygon centroid distances
        dists = [_haversine_km(hub_lat, hub_lon, r["clat"], r["clon"]) for r in valid_rows]
        max_dist = max(dists)
        min_dist = min(dists)
        mean_dist = sum(dists) / len(dists)

        max_tier        = max(r["tier"] for r in valid_rows)
        expected_max_r  = expected_rs0_radius_km + max_tier
        overshoot       = max_dist - expected_max_r

        # ── Aggregate polygon metrics ────────────────────────────────
        total_area_deg2 = sum(r["area"] for r in valid_rows)
        total_peri_deg  = sum(r["peri"] for r in valid_rows if r["peri"])

        # Area-weighted centroid lat for km conversion
        area_km2_list, peri_km_list, compact_list = [], [], []
        for r in valid_rows:
            ak, pk, ck = _polygon_metrics_km(r["geom"], r["clat"])
            if ak is not None:
                area_km2_list.append(ak)
                peri_km_list.append(pk)
                compact_list.append(ck)

        total_area_km2 = round(sum(area_km2_list), 4) if area_km2_list else None
        avg_compactness = round(sum(compact_list) / len(compact_list), 4) if compact_list else None

        # ── Hub-to-boundary distances (using the Rs.0 polygon if available,
        #    otherwise the polygon whose centroid is closest to the hub) ──
        target_geom = None
        if rs0_rows:
            # pick the Rs.0 polygon with largest area
            target_geom = max(rs0_rows, key=lambda r: r["area"])["geom"]
        else:
            # pick polygon whose centroid is closest
            closest = min(valid_rows, key=lambda r: _haversine_km(hub_lat, hub_lon, r["clat"], r["clon"]))
            target_geom = closest["geom"]

        bnd_min, bnd_max, bnd_mean, bnd_std, bnd_skew = _boundary_distances_km(hub_lat, hub_lon, target_geom)

        # Coverage density = total polygon area (km²) / (pi * expected_max_r²)
        coverage_density = None
        if total_area_km2 is not None and expected_max_r > 0:
            import math as _m2
            coverage_density = round(total_area_km2 / (_m2.pi * expected_max_r ** 2), 4)

        # Radius variance across polygon centroid distances
        if len(dists) >= 2:
            var_r = sum((d - mean_dist) ** 2 for d in dists) / len(dists)
            radius_variance = round(var_r, 4)
        else:
            radius_variance = 0.0

        # ── Directional asymmetry (circular std dev of bearings) ────
        brgs = [_bearing(hub_lat, hub_lon, r["clat"], r["clon"]) for r in valid_rows]
        if len(brgs) >= 2:
            sin_m = sum(math.sin(math.radians(b)) for b in brgs) / len(brgs)
            cos_m = sum(math.cos(math.radians(b)) for b in brgs) / len(brgs)
            R_c   = math.sqrt(sin_m ** 2 + cos_m ** 2)
            dir_asym = math.degrees(math.sqrt(max(0.0, -2.0 * math.log(R_c + 1e-9))))
        else:
            dir_asym = 0.0

        # ── Ring monotonicity ────────────────────────────────────────
        from collections import defaultdict
        tier_dists = defaultdict(list)
        for r, d in zip(valid_rows, dists):
            tier_dists[r["tier"]].append(d)
        tier_avg = sorted((t, sum(ds) / len(ds)) for t, ds in tier_dists.items())
        if len(tier_avg) >= 2:
            diffs = [tier_avg[i + 1][1] - tier_avg[i][1] for i in range(len(tier_avg) - 1)]
            monotonicity = sum(1 for d in diffs if d > 0) / len(diffs)
        else:
            monotonicity = 1.0

        status, reason = _classify_hub(
            hub_to_weighted, hub_to_rs0, hub_in_rs0, hub_in_any,
            dir_asym, monotonicity, overshoot, bnd_std)

        score = _anomaly_score(
            hub_to_weighted, hub_to_rs0, hub_in_rs0, hub_in_any,
            dir_asym, monotonicity, overshoot)

        confidence = _confidence_score(
            hub_to_weighted, hub_to_rs0, hub_in_rs0, hub_in_any,
            dir_asym, monotonicity, overshoot, bnd_std)

        results.append({
            # ── Identity ──────────────────────────────────────────────
            "hub_id":                       int(hub_id),
            "hub_name":                     hub_name,
            "hub_lat":                      round(hub_lat, 6),
            "hub_lon":                      round(hub_lon, 6),
            # ── Data quality ──────────────────────────────────────────
            "n_polygons":                   len(grp),
            "n_corrupt_polygons":           corrupt_count,
            "data_quality":                 "PARTIAL" if corrupt_count else "OK",
            "dq_note":                      dq_note,
            # ── Centroid ──────────────────────────────────────────────
            "weighted_centroid_lat":        round(wt_lat, 6),
            "weighted_centroid_lon":        round(wt_lon, 6),
            "hub_to_weighted_centroid_km":  round(hub_to_weighted, 4),
            "hub_to_rs0_centroid_km":       round(hub_to_rs0, 4) if hub_to_rs0 is not None else None,
            # ── Containment ───────────────────────────────────────────
            "hub_in_rs0_polygon":           hub_in_rs0,
            "hub_in_any_polygon":           hub_in_any,
            # ── Boundary distances ────────────────────────────────────
            "bnd_min_km":                   bnd_min,
            "bnd_max_km":                   bnd_max,
            "bnd_mean_km":                  bnd_mean,
            "bnd_std_km":                   bnd_std,
            "bnd_skewness":                 bnd_skew,
            # ── Polygon shape ─────────────────────────────────────────
            "total_area_km2":               total_area_km2,
            "avg_compactness":              avg_compactness,   # 1.0 = circle
            "coverage_density":             coverage_density,
            "radius_variance":              radius_variance,
            # ── Distance ring stats ───────────────────────────────────
            "dir_asymmetry_deg":            round(dir_asym, 2),
            "ring_monotonicity":            round(monotonicity, 3),
            "max_poly_centroid_dist_km":    round(max_dist, 4),
            "min_poly_centroid_dist_km":    round(min_dist, 4),
            "mean_poly_centroid_dist_km":   round(mean_dist, 4),
            "max_tier":                     max_tier,
            "expected_max_radius_km":       expected_max_r,
            "radius_overshoot_km":          round(overshoot, 4),
            # ── Classification ────────────────────────────────────────
            "anomaly_score":                score,
            "confidence_score":             confidence,
            "status":                       status,
            "reason":                       reason,
        })

    results.sort(key=lambda r: (r.get("anomaly_score") or -1), reverse=True)
    return results


def _is_nan(v):
    try:
        return math.isnan(float(v))
    except (TypeError, ValueError):
        return True


def _err_record(hub_id, hub_name, hub_lat, hub_lon, n_polys, note):
    return {
        "hub_id":                       hub_id,
        "hub_name":                     hub_name,
        "hub_lat":                      hub_lat,
        "hub_lon":                      hub_lon,
        "n_polygons":                   n_polys,
        "n_corrupt_polygons":           n_polys,
        "data_quality":                 "DATA_ERROR",
        "dq_note":                      note,
        "weighted_centroid_lat":        None,
        "weighted_centroid_lon":        None,
        "hub_to_weighted_centroid_km":  None,
        "hub_to_rs0_centroid_km":       None,
        "hub_in_rs0_polygon":           False,
        "hub_in_any_polygon":           False,
        "bnd_min_km":                   None,
        "bnd_max_km":                   None,
        "bnd_mean_km":                  None,
        "bnd_std_km":                   None,
        "bnd_skewness":                 None,
        "total_area_km2":               None,
        "avg_compactness":              None,
        "coverage_density":             None,
        "radius_variance":              None,
        "dir_asymmetry_deg":            None,
        "ring_monotonicity":            None,
        "max_poly_centroid_dist_km":    None,
        "min_poly_centroid_dist_km":    None,
        "mean_poly_centroid_dist_km":   None,
        "max_tier":                     None,
        "expected_max_radius_km":       None,
        "radius_overshoot_km":          None,
        "anomaly_score":                None,
        "confidence_score":             None,
        "status":                       "Data Error",
        "reason":                       f"Invalid hub/polygon data: {note}",
    }


def summarise_centroid_anomalies(anomaly_records):
    """
    Return a summary dict from the output of detect_hub_centroid_anomalies().

    Useful for dashboard cards and GANDALF briefing generation.
    """
    total  = len(anomaly_records)
    by_status = {}
    for r in anomaly_records:
        s = r.get("status", "Unknown")
        by_status[s] = by_status.get(s, 0) + 1

    critical = [r for r in anomaly_records if r.get("status") == "Critical Anomaly"]
    warnings = [r for r in anomaly_records if r.get("status") == "Warning"]
    correct  = [r for r in anomaly_records if r.get("status") == "Correct"]

    top10 = sorted(
        [r for r in anomaly_records if r.get("anomaly_score") is not None],
        key=lambda r: r["anomaly_score"], reverse=True
    )[:10]

    return {
        "total_hubs":          total,
        "critical_count":      len(critical),
        "warning_count":       len(warnings),
        "correct_count":       len(correct),
        "data_error_count":    by_status.get("Data Error", 0),
        "critical_pct":        round(len(critical) / max(total, 1) * 100, 1),
        "warning_pct":         round(len(warnings) / max(total, 1) * 100, 1),
        "correct_pct":         round(len(correct)  / max(total, 1) * 100, 1),
        "top10_anomalous":     top10,
        "by_status":           by_status,
    }
