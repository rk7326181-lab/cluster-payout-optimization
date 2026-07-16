"""
G.A.N.D.A.L.F. Hub Anomaly Detection Tab
==========================================
Streamlit UI for the full geospatial hub-centroid anomaly detection system.

Sections:
  1. File uploader  (kepler_gl CSV)
  2. Executive summary cards
  3. Data quality report
  4. Color-coded hub summary table  (Green / Yellow / Red)
  5. Full anomaly report with drill-down details
  6. Interactive Folium map  (Green / Yellow / Red markers)
  7. G.A.N.D.A.L.F. feature export for ML training
"""

import streamlit as st
import pandas as pd
import numpy as np
import math
from pathlib import Path

# Optional heavy deps — graceful fallback if not installed
try:
    import folium
    from streamlit_folium import st_folium
    _HAS_FOLIUM = True
except ImportError:
    _HAS_FOLIUM = False

try:
    from modules.hub_anomaly import detect_hub_centroid_anomalies, summarise_centroid_anomalies
except ImportError:
    from hub_anomaly import detect_hub_centroid_anomalies, summarise_centroid_anomalies


# ── Colour helpers ────────────────────────────────────────────────────────────
STATUS_COLOR = {
    "Correct":         "#22c55e",   # green-500
    "Warning":         "#eab308",   # yellow-500
    "Critical Anomaly":"#ef4444",   # red-500
    "Data Error":      "#94a3b8",   # slate-400
}
STATUS_BG = {
    "Correct":         "rgba(34,197,94,0.12)",
    "Warning":         "rgba(234,179,8,0.12)",
    "Critical Anomaly":"rgba(239,68,68,0.12)",
    "Data Error":      "rgba(148,163,184,0.12)",
}
STATUS_EMOJI = {
    "Correct":          "🟢",
    "Warning":          "🟡",
    "Critical Anomaly": "🔴",
    "Data Error":       "⬜",
}
FOLIUM_ICON = {
    "Correct":          ("green",  "home"),
    "Warning":          ("orange", "exclamation-sign"),
    "Critical Anomaly": ("red",    "remove"),
    "Data Error":       ("gray",   "question-sign"),
}


# ── Metric card HTML ──────────────────────────────────────────────────────────
def _metric_card(label, value, sub, color, icon):
    return f"""
    <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);
                border-left:4px solid {color};border-radius:12px;padding:18px 20px;
                display:flex;align-items:center;gap:14px;min-height:90px;">
      <span style="font-size:2rem;">{icon}</span>
      <div>
        <div style="font-size:1.7rem;font-weight:700;color:{color};line-height:1.1;">{value}</div>
        <div style="font-size:0.78rem;color:#94a3b8;margin-top:2px;">{label}</div>
        <div style="font-size:0.72rem;color:#64748b;margin-top:1px;">{sub}</div>
      </div>
    </div>"""


def _status_badge(status):
    c = STATUS_COLOR.get(status, "#94a3b8")
    bg = STATUS_BG.get(status, "rgba(148,163,184,0.1)")
    e = STATUS_EMOJI.get(status, "⬜")
    return (f'<span style="background:{bg};color:{c};border:1px solid {c};'
            f'border-radius:6px;padding:2px 8px;font-size:0.75rem;font-weight:600;">'
            f'{e} {status}</span>')


# ── Main render entry point ───────────────────────────────────────────────────
def render_hub_anomaly_tab(session_kepler_df=None):
    """
    Call this from app.py inside the Hub Anomaly tab:

        from modules.gandalf_hub_anomaly_tab import render_hub_anomaly_tab
        with tab_anomaly:
            render_hub_anomaly_tab(session_kepler_df=st.session_state.get("kepler_df"))
    """

    # ── 1. Header ─────────────────────────────────────────────────────────────
    st.markdown("""
    <div style="padding:4px 0 18px;">
      <h2 style="margin:0;font-size:1.5rem;font-weight:800;letter-spacing:-0.02em;">
        🧙 G.A.N.D.A.L.F. — Hub Anomaly Detection
      </h2>
      <p style="margin:4px 0 0;color:#94a3b8;font-size:0.85rem;">
        Geospatial Anomaly Detection and Location Framework &nbsp;·&nbsp;
        Hub-centroid displacement analysis using Haversine distances,
        polygon containment, ring monotonicity &amp; directional asymmetry.
      </p>
    </div>
    """, unsafe_allow_html=True)

    # ── 2. Data source ────────────────────────────────────────────────────────
    st.markdown("#### Data Source")
    col_src1, col_src2 = st.columns([2, 1])
    with col_src1:
        uploaded = st.file_uploader(
            "Upload kepler_gl CSV  (Hub ID · WKT · Hub_Name · Cluster_Category · Hub lat · Hub Long)",
            type=["csv"],
            key="gandalf_kepler_upload",
        )
    with col_src2:
        use_cached = st.checkbox(
            "Use pre-loaded session data",
            value=(session_kepler_df is not None),
            key="gandalf_use_session",
            disabled=(session_kepler_df is None),
        )

    # Resolve DataFrame
    kepler_df = None
    if uploaded:
        try:
            kepler_df = pd.read_csv(uploaded, low_memory=False)
            st.success(f"Loaded {len(kepler_df):,} rows from uploaded file.")
        except Exception as e:
            st.error(f"Could not read CSV: {e}")
            return
    elif use_cached and session_kepler_df is not None:
        kepler_df = session_kepler_df
        st.info(f"Using session data — {len(kepler_df):,} rows.")

    # Check for required columns
    if kepler_df is not None:
        required = {"Hub ID", "WKT", "Hub_Name", "Cluster_Category", "Hub lat", "Hub Long"}
        missing = required - set(kepler_df.columns)
        if missing:
            st.error(f"Missing required columns: {missing}")
            kepler_df = None

    if kepler_df is None:
        st.markdown("""
        <div style="background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.2);
                    border-radius:12px;padding:24px;text-align:center;margin-top:20px;">
          <div style="font-size:2.5rem;">🗺️</div>
          <div style="font-weight:600;margin-top:8px;">Upload a kepler_gl CSV to start analysis</div>
          <div style="color:#94a3b8;font-size:0.82rem;margin-top:4px;">
            Expected columns: Hub ID · WKT · Hub_Name · Cluster_Category · Hub lat · Hub Long
          </div>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── 3. Run detection (cached in session state) ────────────────────────────
    cache_key = f"gandalf_anomaly_{len(kepler_df)}_{id(kepler_df)}"
    if cache_key not in st.session_state or st.button("🔄 Re-run Analysis", key="gandalf_rerun"):
        with st.spinner("G.A.N.D.A.L.F. is scanning all hubs… this takes ~60s for 1,500 hubs"):
            records = detect_hub_centroid_anomalies(kepler_df)
            summary = summarise_centroid_anomalies(records)
            st.session_state[cache_key] = {"records": records, "summary": summary}

    cached = st.session_state[cache_key]
    records = cached["records"]
    summary = cached["summary"]
    df = pd.DataFrame(records)

    # ── 4. Executive Summary ──────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Executive Summary")
    c1, c2, c3, c4, c5 = st.columns(5)
    cards = [
        (c1, "Total Hubs",       f"{summary['total_hubs']:,}",    "",                            "#6366f1", "🏢"),
        (c2, "Correct",          f"{summary['correct_count']:,}", f"{summary['correct_pct']}%",  "#22c55e", "✅"),
        (c3, "Warning",          f"{summary['warning_count']:,}", f"{summary['warning_pct']}%",  "#eab308", "⚠️"),
        (c4, "Critical Anomaly", f"{summary['critical_count']:,}",f"{summary['critical_pct']}%","#ef4444", "🚨"),
        (c5, "Data Errors",      f"{summary['data_error_count']:,}", "skipped",                  "#94a3b8", "⬜"),
    ]
    for col, label, value, sub, color, icon in cards:
        with col:
            st.markdown(_metric_card(label, value, sub, color, icon), unsafe_allow_html=True)

    # ── 5. Data Quality Report ────────────────────────────────────────────────
    with st.expander("📋 Data Quality Report", expanded=False):
        dq = df["data_quality"].value_counts().to_dict()
        dq_cols = st.columns(3)
        with dq_cols[0]:
            st.metric("Clean hubs (OK)",      dq.get("OK", 0))
        with dq_cols[1]:
            st.metric("Partial (some corrupt)", dq.get("PARTIAL", 0))
        with dq_cols[2]:
            st.metric("Data Errors",           dq.get("DATA_ERROR", 0))

        null_hub = kepler_df[["Hub lat", "Hub Long"]].isnull().sum()
        null_poly = kepler_df[["latitude", "longitude"]].isnull().sum() if "latitude" in kepler_df.columns else {}
        swap = df[df["dq_note"].str.contains("SWAPPED", na=False)]

        st.markdown(f"""
        | Check | Result |
        |---|---|
        | Total polygon rows | {len(kepler_df):,} |
        | Unique hubs | {kepler_df['Hub ID'].nunique():,} |
        | Null Hub lat/lon | {null_hub.sum()} rows |
        | Lat/lon swapped hubs | {len(swap)} (auto-corrected) |
        | Corrupt WKT polygons | {df['n_corrupt_polygons'].sum():.0f} |
        | Avg polygons per hub | {len(kepler_df)/max(kepler_df['Hub ID'].nunique(),1):.1f} |
        """)

        if len(swap) > 0:
            st.warning(f"**{len(swap)} hubs** had lat/lon swapped — auto-corrected during analysis:")
            st.dataframe(swap[["hub_name", "hub_lat", "hub_lon", "dq_note"]].head(10), use_container_width=True)

    # ── 6. Hub Summary Table ──────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Hub Summary Table")

    # Filter controls
    f1, f2, f3 = st.columns([2, 2, 1])
    with f1:
        status_filter = st.multiselect(
            "Filter by Status",
            options=["Correct", "Warning", "Critical Anomaly", "Data Error"],
            default=["Warning", "Critical Anomaly"],
            key="gandalf_status_filter",
        )
    with f2:
        search = st.text_input("Search hub name", key="gandalf_search", placeholder="e.g. AGR_")
    with f3:
        sort_by = st.selectbox("Sort by", ["anomaly_score", "hub_to_weighted_centroid_km",
                                            "confidence_score", "hub_name"], key="gandalf_sort")

    view_df = df.copy()
    if status_filter:
        view_df = view_df[view_df["status"].isin(status_filter)]
    if search.strip():
        view_df = view_df[view_df["hub_name"].str.contains(search.strip(), case=False, na=False)]
    view_df = view_df.sort_values(sort_by, ascending=(sort_by == "hub_name"), na_position="last")

    st.caption(f"Showing {len(view_df):,} of {len(df):,} hubs")

    # Build color-coded HTML table
    rows_html = ""
    for _, row in view_df.head(200).iterrows():
        status = row.get("status", "")
        bg     = STATUS_BG.get(status, "transparent")
        badge  = _status_badge(status)
        cdist  = f"{row['hub_to_weighted_centroid_km']:.2f} km" if pd.notna(row.get("hub_to_weighted_centroid_km")) else "—"
        rs0d   = f"{row['hub_to_rs0_centroid_km']:.2f} km"     if pd.notna(row.get("hub_to_rs0_centroid_km"))     else "—"
        conf   = f"{row['confidence_score']:.0f}%"             if pd.notna(row.get("confidence_score"))           else "—"
        score  = f"{row['anomaly_score']:.1f}"                  if pd.notna(row.get("anomaly_score"))              else "—"
        in_rs0 = "✅" if row.get("hub_in_rs0_polygon") else "❌"
        rows_html += f"""
        <tr style="background:{bg};border-bottom:1px solid rgba(255,255,255,0.05);">
          <td style="padding:8px 10px;font-weight:600;">{row['hub_name']}</td>
          <td style="padding:8px 10px;font-family:monospace;">{row['hub_lat']:.4f}, {row['hub_lon']:.4f}</td>
          <td style="padding:8px 10px;">{badge}</td>
          <td style="padding:8px 10px;">{conf}</td>
          <td style="padding:8px 10px;">{cdist}</td>
          <td style="padding:8px 10px;">{rs0d}</td>
          <td style="padding:8px 10px;text-align:center;">{in_rs0}</td>
          <td style="padding:8px 10px;">{score}</td>
        </tr>"""

    table_html = f"""
    <div style="overflow-x:auto;border-radius:10px;border:1px solid rgba(255,255,255,0.08);">
    <table style="width:100%;border-collapse:collapse;font-size:0.82rem;font-family:'Inter',sans-serif;">
      <thead>
        <tr style="background:rgba(255,255,255,0.05);border-bottom:2px solid rgba(255,255,255,0.1);">
          <th style="padding:10px;text-align:left;">Hub Name</th>
          <th style="padding:10px;text-align:left;">Coordinates</th>
          <th style="padding:10px;text-align:left;">Status</th>
          <th style="padding:10px;text-align:left;">Confidence</th>
          <th style="padding:10px;text-align:left;">Centroid Dist</th>
          <th style="padding:10px;text-align:left;">Rs.0 Dist</th>
          <th style="padding:10px;text-align:center;">In Rs.0</th>
          <th style="padding:10px;text-align:left;">Score</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    </div>"""
    st.markdown(table_html, unsafe_allow_html=True)

    # ── 7. Anomaly Drill-Down ─────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Anomaly Drill-Down")

    anomalies_df = df[df["status"].isin(["Critical Anomaly", "Warning"])].sort_values(
        "anomaly_score", ascending=False).reset_index(drop=True)
    top10 = anomalies_df.head(10)

    st.markdown(f"**Top 10 Most Anomalous Hubs** (of {len(anomalies_df):,} total anomalies)")

    for i, row in top10.iterrows():
        status = row.get("status", "")
        color  = STATUS_COLOR.get(status, "#94a3b8")
        with st.expander(
            f"{STATUS_EMOJI.get(status,'⬜')} #{i+1}  {row['hub_name']}  "
            f"[{status}]  Score={row.get('anomaly_score','?')}  "
            f"Confidence={row.get('confidence_score','?')}%",
            expanded=(i == 0)
        ):
            d1, d2, d3 = st.columns(3)
            with d1:
                st.markdown(f"**Hub Location**")
                st.code(f"lat: {row['hub_lat']}\nlon: {row['hub_lon']}")
            with d2:
                st.markdown(f"**Weighted Centroid**")
                c_lat = row.get('weighted_centroid_lat', '—')
                c_lon = row.get('weighted_centroid_lon', '—')
                st.code(f"lat: {c_lat}\nlon: {c_lon}")
            with d3:
                st.markdown("**Key Distances**")
                st.code(
                    f"Hub → centroid : {row.get('hub_to_weighted_centroid_km','—')} km\n"
                    f"Hub → Rs.0     : {row.get('hub_to_rs0_centroid_km','—')} km\n"
                    f"Bnd min/max    : {row.get('bnd_min_km','—')} / {row.get('bnd_max_km','—')} km\n"
                    f"Radius overshoot: {row.get('radius_overshoot_km','—')} km"
                )

            m1, m2, m3, m4 = st.columns(4)
            with m1: st.metric("Polygons",         row.get("n_polygons", "—"))
            with m2: st.metric("Area km²",          f"{row.get('total_area_km2','—')}")
            with m3: st.metric("Compactness",       f"{row.get('avg_compactness','—')}")
            with m4: st.metric("Ring Monotonicity", f"{row.get('ring_monotonicity','—')}")

            st.markdown(f"**Root Cause:** {row.get('reason', '—')}")

            st.markdown(f"""
            <div style="background:rgba(239,68,68,0.08);border-left:4px solid {color};
                        border-radius:6px;padding:10px 14px;margin-top:8px;font-size:0.82rem;">
              <b>Recommended Action:</b> {'Relocate hub GPS pin to the polygon centroid '
              f'({row.get("weighted_centroid_lat","?")}, {row.get("weighted_centroid_lon","?")}) '
              'or redraw polygon boundaries around the actual hub location.'
              if status == "Critical Anomaly" else
              'Review hub placement — hub is not centred in its Rs.0 (core) polygon. '
              'Consider slight relocation toward the service-area centroid.'}
            </div>
            """, unsafe_allow_html=True)

    # ── 8. Interactive Folium Map ─────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Map Visualization")

    if not _HAS_FOLIUM:
        st.warning("`folium` and `streamlit-folium` are not installed. "
                   "Run `pip install folium streamlit-folium` to enable map view.")
    else:
        map_status = st.multiselect(
            "Show on map",
            ["Correct", "Warning", "Critical Anomaly"],
            default=["Warning", "Critical Anomaly"],
            key="gandalf_map_filter",
        )
        map_limit = st.slider("Max markers (performance)", 50, 500, 200, 50, key="gandalf_map_limit")

        map_df = df[df["status"].isin(map_status)].dropna(
            subset=["hub_lat", "hub_lon"]).head(map_limit)

        if len(map_df) > 0:
            center_lat = map_df["hub_lat"].mean()
            center_lon = map_df["hub_lon"].mean()
            m = folium.Map(location=[center_lat, center_lon], zoom_start=5,
                           tiles="CartoDB dark_matter")

            for _, row in map_df.iterrows():
                status  = row.get("status", "")
                fi_col, fi_icon = FOLIUM_ICON.get(status, ("gray", "info-sign"))
                popup_html = f"""
                <div style="min-width:220px;font-family:sans-serif;font-size:12px;">
                  <b style="font-size:13px;">{row['hub_name']}</b><br>
                  <span style="color:{STATUS_COLOR.get(status,'#888')};font-weight:600;">{status}</span>
                  &nbsp;·&nbsp; Score: {row.get('anomaly_score','?')}
                  &nbsp;·&nbsp; Conf: {row.get('confidence_score','?')}%<br><br>
                  <b>Hub:</b> {row['hub_lat']:.5f}, {row['hub_lon']:.5f}<br>
                  <b>Centroid:</b> {row.get('weighted_centroid_lat','?')}, {row.get('weighted_centroid_lon','?')}<br>
                  <b>Centroid dist:</b> {row.get('hub_to_weighted_centroid_km','?')} km<br>
                  <b>Rs.0 dist:</b> {row.get('hub_to_rs0_centroid_km','?')} km<br>
                  <b>In Rs.0:</b> {'Yes' if row.get('hub_in_rs0_polygon') else 'No'}<br><br>
                  <i>{str(row.get('reason',''))[:120]}</i>
                </div>"""

                folium.Marker(
                    location=[row["hub_lat"], row["hub_lon"]],
                    popup=folium.Popup(popup_html, max_width=280),
                    tooltip=f"{row['hub_name']} [{status}]",
                    icon=folium.Icon(color=fi_col, icon=fi_icon, prefix="glyphicon"),
                ).add_to(m)

                # Draw line from hub to weighted centroid for anomalous hubs
                if (status in ("Critical Anomaly", "Warning") and
                        pd.notna(row.get("weighted_centroid_lat"))):
                    line_color = STATUS_COLOR.get(status, "#888")
                    folium.PolyLine(
                        locations=[
                            [row["hub_lat"], row["hub_lon"]],
                            [row["weighted_centroid_lat"], row["weighted_centroid_lon"]],
                        ],
                        color=line_color, weight=1.5, opacity=0.6,
                        tooltip=f"Displacement: {row.get('hub_to_weighted_centroid_km','?')} km",
                    ).add_to(m)
                    # Centroid marker (X)
                    folium.CircleMarker(
                        location=[row["weighted_centroid_lat"], row["weighted_centroid_lon"]],
                        radius=4, color=line_color, fill=True,
                        fill_color=line_color, fill_opacity=0.8,
                        tooltip=f"Centroid of {row['hub_name']}",
                    ).add_to(m)

            # Legend
            legend_html = """
            <div style="position:fixed;bottom:30px;left:30px;z-index:9999;
                        background:rgba(15,23,42,0.9);border-radius:10px;padding:12px 16px;
                        font-family:sans-serif;font-size:12px;color:#e2e8f0;min-width:160px;">
              <b style="font-size:13px;">G.A.N.D.A.L.F.</b><br><br>
              <span style="color:#22c55e;">●</span> Correct Hub<br>
              <span style="color:#eab308;">●</span> Warning<br>
              <span style="color:#ef4444;">●</span> Critical Anomaly<br>
              <span style="color:#94a3b8;">—</span> Displacement line<br>
              <span style="color:#94a3b8;">●</span> Service centroid
            </div>"""
            m.get_root().html.add_child(folium.Element(legend_html))

            st_folium(m, width="100%", height=500, returned_objects=[])
        else:
            st.info("No hubs match the selected filter.")

    # ── 9. Export ─────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Export")
    ec1, ec2 = st.columns(2)

    with ec1:
        full_csv = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ Download Full Anomaly Report (CSV)",
            data=full_csv,
            file_name="gandalf_hub_anomaly_report.csv",
            mime="text/csv",
            key="gandalf_download_full",
        )
    with ec2:
        anom_only = df[df["status"].isin(["Critical Anomaly", "Warning"])].to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ Download Anomalies Only (CSV)",
            data=anom_only,
            file_name="gandalf_anomalies_only.csv",
            mime="text/csv",
            key="gandalf_download_anom",
        )

    # ── 10. ML Feature Export ─────────────────────────────────────────────────
    with st.expander("🤖 G.A.N.D.A.L.F. ML Training Data Export", expanded=False):
        ml_features = [
            "hub_lat", "hub_lon",
            "weighted_centroid_lat", "weighted_centroid_lon",
            "hub_to_weighted_centroid_km", "hub_to_rs0_centroid_km",
            "bnd_min_km", "bnd_max_km", "bnd_mean_km", "bnd_std_km", "bnd_skewness",
            "total_area_km2", "avg_compactness", "coverage_density", "radius_variance",
            "dir_asymmetry_deg", "ring_monotonicity",
            "max_poly_centroid_dist_km", "min_poly_centroid_dist_km",
            "mean_poly_centroid_dist_km", "radius_overshoot_km",
            "n_polygons", "max_tier",
        ]
        label_map = {"Correct": 0, "Warning": 1, "Critical Anomaly": 2, "Data Error": -1}
        ml_df = df[["hub_name", "hub_id", "status"] + [c for c in ml_features if c in df.columns]].copy()
        ml_df["label"] = ml_df["status"].map(label_map)
        ml_df = ml_df[ml_df["label"] >= 0]  # exclude data errors

        st.markdown(f"""
        **{len(ml_df):,} hubs ready for ML training**

        | Label | Status | Count |
        |---|---|---|
        | 0 | Correct | {(ml_df['label']==0).sum()} |
        | 1 | Warning | {(ml_df['label']==1).sum()} |
        | 2 | Critical Anomaly | {(ml_df['label']==2).sum()} |

        Features: {len(ml_features)} geospatial features · Labels: rule-based (0/1/2)
        """)

        st.dataframe(ml_df.head(20), use_container_width=True)
        ml_csv = ml_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ Download ML Training Dataset",
            data=ml_csv,
            file_name="gandalf_ml_training_data.csv",
            mime="text/csv",
            key="gandalf_download_ml",
        )
