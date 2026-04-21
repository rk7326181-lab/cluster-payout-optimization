"""
Free Maps Studio — Leaflet-based map editor (no API key required).
Uses OpenStreetMap, Leaflet Draw, OSRM routing, and leaflet-heat.
All features: markers, polylines, polygons, rectangles, circles,
editing, deletion, measurement, directions, search, heatmap,
clustering, layer management, import/export (GeoJSON/CSV/KML).

Supports injecting cluster GeoJSON, hub locations, and AWB data
so the Map Studio can display and edit hub polygons with AWB overlays.
"""

import json
from pathlib import Path


def get_free_maps_html(cluster_geojson=None, hub_list=None, awb_data=None, hexbin_data=None) -> str:
    """
    Return the complete HTML for the free Leaflet-based map editor.

    Optional data injection:
      cluster_geojson: GeoJSON FeatureCollection of cluster polygons
      hub_list:        list of dicts {id, name, lat, lng, category}
      awb_data:        list of dicts {lat, lng, hub, pincode, awb, date, payment}
      hexbin_data:     list of dicts {lat, lng, hub, count, pincode} — pre-computed hex cells
    """
    html_path = Path(__file__).parent.parent / "maps_studio.html"
    if not html_path.exists():
        return (
            "<!DOCTYPE html><html><body style=\"font-family:sans-serif;display:flex;"
            "align-items:center;justify-content:center;height:100vh;background:#0d1117;"
            "color:#e2e8f0;\"><p>maps_studio.html not found in project root.</p></body></html>"
        )

    html = html_path.read_text(encoding="utf-8")

    # Inject data as JavaScript globals if provided
    has_data = (
        (cluster_geojson and cluster_geojson.get("features"))
        or (hub_list and len(hub_list) > 0)
        or (awb_data and len(awb_data) > 0)
        or (hexbin_data and len(hexbin_data) > 0)
    )
    if has_data:
        data_script = "\n<script>\n"
        data_script += "window.__CLUSTER_GEOJSON__ = %s;\n" % json.dumps(
            cluster_geojson or {"type": "FeatureCollection", "features": []},
            separators=(",", ":"),
        )
        data_script += "window.__HUB_DATA__ = %s;\n" % json.dumps(
            hub_list or [], separators=(",", ":")
        )
        data_script += "window.__AWB_DATA__ = %s;\n" % json.dumps(
            awb_data or [], separators=(",", ":")
        )
        data_script += "window.__HEXBIN_DATA__ = %s;\n" % json.dumps(
            hexbin_data or [], separators=(",", ":")
        )
        data_script += "</script>\n"
        # Insert data script BEFORE the main <script> block so globals are
        # available when the maps_studio JS runs.
        html = html.replace(
            "<script src=\"https://unpkg.com/papaparse",
            data_script + "<script src=\"https://unpkg.com/papaparse",
        )

    return html
