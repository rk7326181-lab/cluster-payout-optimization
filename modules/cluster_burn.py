"""
Cluster Burn Calculation Module
=================================
Computes P&L between pincode-based payout and cluster-based payout.

ClusterBurnCalculator  — pure computation (no Streamlit)
render_burn_tab()      — full Streamlit UI for the Burn Calc tab
"""

import io
from typing import List, Optional, Tuple

import pandas as pd
import streamlit as st
from shapely.geometry import Point
from shapely.wkt import loads as load_wkt
from shapely.prepared import prep

try:
    from google.api_core.exceptions import GoogleAPIError
    HAS_BQ = True
except ImportError:
    HAS_BQ = False

# ── Constants ────────────────────────────────────────────────────────────────

DATA_PROJECT = "data-warehousing-391512"

PAYMENT_MAPPING = {
    "P1": 0,   "P2": 1,   "P3": 2,   "P4": 4,   "P5": 6,
    "P6": 8,   "P7": 9,   "P8": 10,  "P9": 10,  "P10": 10,
    "P11": 11, "P12": 12, "P13": 13, "P14": 14, "P15": 15,
    "P16": 16, "P17": 17, "P18": 18, "P19": 19, "P20": 20,
    "P21": 21, "P22": 22, "P23": 23, "P24": 24, "P25": 25,
    "P26": 26, "P27": 27, "P28": 28, "P29": 29, "P30": 30,
}

DESCRIPTION_MAPPING = {
    "C1": 0,   "C2": 0.5, "C3": 1,   "C4": 1.5, "C5": 2,
    "C6": 2.5, "C7": 3,   "C8": 3.5, "C9": 4,   "C10": 4.5,
    "C11": 5,  "C12": 6,  "C13": 7,  "C14": 8,  "C15": 9,
    "C16": 10, "C17": 11, "C18": 12, "C19": 13, "C20": 15,
}

DEFAULT_PINCODE_MAP = {
    580011: "C4", 203209: "C8", 282009: "C6",
    584128: "C2", 110074: "C2", 800001: "C0",
}


# ════════════════════════════════════════════════════════════════════════════
# COMPUTATION ENGINE
# ════════════════════════════════════════════════════════════════════════════

class ClusterBurnCalculator:
    """Pure-computation engine — no Streamlit dependencies."""

    # ── Hub list ──────────────────────────────────────────────────────────────
    @staticmethod
    def fetch_hub_list(client) -> pd.DataFrame:
        return client.query(f"""
            SELECT id, name
            FROM `{DATA_PROJECT}.ecommerce.ecommerce_hub`
            ORDER BY name
        """).to_dataframe()

    # ── AWB query ─────────────────────────────────────────────────────────────
    @staticmethod
    def fetch_awb(
        client,
        hub_ids: List[int],
        days_back: int,
    ) -> Tuple[pd.DataFrame, Optional[str]]:
        ids_str = ", ".join(str(i) for i in hub_ids)
        query = f"""
        WITH awb_data AS (

          SELECT
            sg.order_date, sg.rider_id, sg.hub_id, sg.pincode, sg.pincode_category,
            sg.order_id                AS fwd_del_awb_number,
            edp.delivery_latitude      AS lat,
            edp.delivery_longitude     AS long,
            ROW_NUMBER() OVER (PARTITION BY sg.rider_id ORDER BY edp.update_timestamp) AS row_num
          FROM `{DATA_PROJECT}.smaug_dataengine.data_engine_orderleveldata` sg
          LEFT JOIN `{DATA_PROJECT}.ecommerce.ecommerce_deliveryrequest` edr
            ON edr.awb_number = sg.order_id
           AND edr.last_updated > CURRENT_DATE - INTERVAL {days_back} DAY
          LEFT JOIN `{DATA_PROJECT}.ecommerce.ecommerce_deliveryrequestproof` edp
            ON edr.id = edp.delivery_request_id
           AND edp.update_timestamp > CURRENT_DATE - INTERVAL {days_back} DAY
          WHERE sg.order_date > CURRENT_DATE - INTERVAL {days_back} DAY
            AND sg.order_category = 1 AND ecom_request_type IN (1)
            AND sg.order_status IN (1) AND sg.order_tag IN (0, 1, 14)
            AND edr.client_id NOT IN (
                  5,18,60,61,67,68,102,354,552,557,715,
                  818,862,875,11,996,1579,1575,1819,2063,2253)
            AND sg.hub_id IN ({ids_str})

          UNION ALL

          SELECT
            sg.order_date, sg.rider_id, sg.hub_id, sg.pincode, sg.pincode_category,
            sg.order_id                AS fwd_del_awb_number,
            epp.pickup_latitude        AS lat,
            epp.pickup_longitude       AS long,
            ROW_NUMBER() OVER (PARTITION BY sg.rider_id ORDER BY epp.update_timestamp) AS row_num
          FROM `{DATA_PROJECT}.smaug_dataengine.data_engine_orderleveldata` sg
          LEFT JOIN `{DATA_PROJECT}.ecommerce.pickup_pickuprequestproof` epp
            ON sg.order_id = epp.pickup_request_id
           AND epp.update_timestamp > CURRENT_DATE - INTERVAL {days_back} DAY
          WHERE sg.order_date > CURRENT_DATE - INTERVAL {days_back} DAY
            AND sg.order_category = 1 AND ecom_request_type IN (5)
            AND sg.order_status IN (2, 3) AND sg.order_tag IN (0, 1, 14)
            AND sg.hub_id IN ({ids_str})
        )

        SELECT
          order_date, rider_id, eh.name AS hub, ad.pincode,
          CONCAT(CAST('P' AS STRING), ad.pincode_category) AS payment_category,
          fwd_del_awb_number,
          COALESCE(lat,  FIRST_VALUE(lat)  OVER (
              PARTITION BY rider_id ORDER BY row_num
              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS lat,
          COALESCE(long, FIRST_VALUE(long) OVER (
              PARTITION BY rider_id ORDER BY row_num
              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS long
        FROM awb_data ad
        LEFT JOIN `{DATA_PROJECT}.ecommerce.ecommerce_hub` eh ON ad.hub_id = eh.id
        """
        try:
            df = client.query(query).to_dataframe()
            return df, None
        except Exception as exc:
            return pd.DataFrame(), str(exc)

    # ── CSV loaders ───────────────────────────────────────────────────────────
    @staticmethod
    def _to_bytes(source) -> Optional[bytes]:
        """Accept a Streamlit UploadedFile, a file-path string, or raw bytes."""
        if source is None:
            return None
        if isinstance(source, (bytes, bytearray)):
            return bytes(source)
        if isinstance(source, str):
            try:
                with open(source, "rb") as fh:
                    return fh.read()
            except OSError:
                return None
        try:
            source.seek(0)
            return source.read()
        except Exception:
            return None

    @staticmethod
    def load_clusters(source) -> Tuple[list, list]:
        """Parse WKT polygon CSV. source = UploadedFile | path string | bytes | None.
        Returns (clusters, skipped)."""
        raw = ClusterBurnCalculator._to_bytes(source)
        if raw is None:
            return [], []

        df = pd.read_csv(io.BytesIO(raw))
        clusters, skipped = [], []

        for idx, row in df.iterrows():
            try:
                wkt_str = str(row["WKT"]).strip()
                if "POLYGON ()" in wkt_str:
                    skipped.append((idx, row["name"], "Empty polygon")); continue
                if wkt_str.startswith("GEOMETRYCOLLECTION"):
                    skipped.append((idx, row["name"], "GeometryCollection not supported")); continue
                polygon = load_wkt(wkt_str)
                if polygon.is_empty:
                    skipped.append((idx, row["name"], "Empty after parse")); continue
                clusters.append({
                    "prepared":    prep(polygon),
                    "polygon":     polygon,
                    "name":        row["name"],
                    "description": str(row["description"]),
                })
            except Exception as exc:
                skipped.append((idx, row.get("name", "?"), str(exc)))

        return clusters, skipped

    @staticmethod
    def load_pincode_map(uploaded_file) -> dict:
        """Columns: pincode, description. Falls back to built-in defaults."""
        raw = ClusterBurnCalculator._to_bytes(uploaded_file)
        if raw is None:
            return DEFAULT_PINCODE_MAP.copy()
        df = pd.read_csv(io.BytesIO(raw))
        return dict(zip(df["pincode"].astype(int), df["description"].astype(str)))

    # ── Cluster assignment ────────────────────────────────────────────────────
    @staticmethod
    def _match_point(lat, lon, clusters) -> Tuple[Optional[str], Optional[str]]:
        if pd.isnull(lat) or pd.isnull(lon):
            return None, None
        pt = Point(lon, lat)
        for c in clusters:
            if c["prepared"].contains(pt):
                return c["name"], c["description"]
        return None, None

    @staticmethod
    def assign_clusters(
        awb_df: pd.DataFrame,
        clusters: list,
        pincode_map: dict,
    ) -> pd.DataFrame:
        rows = []
        for row in awb_df.itertuples(index=False):
            name, desc = ClusterBurnCalculator._match_point(row.lat, row.long, clusters)
            if not name and row.pincode in pincode_map:
                name, desc = "Previous mapping", pincode_map[row.pincode]
            rows.append({
                "order_date":       row.order_date,
                "awb_number":       row.fwd_del_awb_number,
                "rider_id":         row.rider_id,
                "pincode":          row.pincode,
                "payment_category": row.payment_category,
                "hub":              row.hub,
                "lat":              row.lat,
                "long":             row.long,
                "cluster_name":     name,
                "description":      desc,
            })
        return pd.DataFrame(rows)

    # ── P&L ───────────────────────────────────────────────────────────────────
    @staticmethod
    def calculate_pnl(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["Pin_Pay"] = df["payment_category"].map(PAYMENT_MAPPING).fillna(0)
        df["Clustering_payout"] = (
            df["description"].map(DESCRIPTION_MAPPING).fillna(df["Pin_Pay"])
        )
        df["P & L"]   = df["Pin_Pay"] - df["Clustering_payout"]
        df["Saving"]  = df["P & L"].apply(lambda x: x  if x > 0 else 0)
        df["Burning"] = df["P & L"].apply(lambda x: -x if x < 0 else 0)
        fin = ["Pin_Pay", "Clustering_payout", "Saving", "Burning", "P & L"]
        return df[~(df[fin] == 0).all(axis=1)].reset_index(drop=True)

    # ── Pivot ─────────────────────────────────────────────────────────────────
    @staticmethod
    def build_pivot(df: pd.DataFrame):
        pivot = df.pivot_table(
            index="hub",
            values=["Pin_Pay", "Clustering_payout", "Saving", "Burning", "P & L"],
            aggfunc="sum", margins=True, margins_name="Grand Total",
        ).reset_index().rename(columns={
            "Pin_Pay":           "Expt_Pincode_Pay",
            "Clustering_payout": "Cluster_Payout",
        })
        num = ["Expt_Pincode_Pay", "Cluster_Payout", "Saving", "Burning", "P & L"]
        pivot[num] = pivot[num].apply(pd.to_numeric, errors="coerce")
        pivot["P & L %"] = (pivot["P & L"] / pivot["Expt_Pincode_Pay"] * 100).round(2)

        gt   = pivot[pivot["hub"] == "Grand Total"]
        rest = pivot[pivot["hub"] != "Grand Total"].sort_values("P & L", ascending=False)
        out  = (
            pd.concat([gt, rest])[["hub"] + num + ["P & L %"]]
            .set_index("hub").rename_axis(index=None)
        )
        return (
            out.style
            .map(
                lambda v: ("color:green" if v > 0 else "color:red")
                if isinstance(v, (int, float)) else "",
                subset=["P & L", "P & L %"],
            )
            .format({
                "Expt_Pincode_Pay": "{:,.0f}", "Cluster_Payout": "{:,.0f}",
                "Saving": "{:,.0f}", "Burning": "{:,.0f}",
                "P & L": "{:,.0f}", "P & L %": "{:.2f}%",
            })
            .set_properties(**{"text-align": "center"})
            .set_table_styles([{"selector": "th", "props": [
                ("text-align", "center"), ("font-weight", "bold"),
                ("background-color", "#99ccff"),
            ]}])
        )


# ════════════════════════════════════════════════════════════════════════════
# STREAMLIT TAB RENDERER
# ════════════════════════════════════════════════════════════════════════════

def render_burn_tab(bq_client=None):
    """
    Render the full Cluster Burn Calculation tab inside app.py.
    Call as:  render_burn_tab(st.session_state.get("bq_client"))
    """
    dark = st.session_state.get("dark_mode", False)
    _bg       = "#1A1C24" if dark else "#ffffff"
    _bg2      = "#13151C" if dark else "#f5f5f4"
    _border   = "rgba(255,255,255,0.06)" if dark else "rgba(0,0,0,0.06)"
    _text     = "#e7e5e4" if dark else "#1b1c1c"
    _muted    = "#9CA3AF" if dark else "#78716c"
    _green    = "#6fd9bc" if dark else "#008A71"
    _card_shd = "0 4px 24px rgba(0,138,113,0.08)"

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="pn-header-banner" style="margin-bottom:24px;border-radius:16px;">
        <h1>🔥 Cluster Burn Calculation</h1>
        <p class="pn-header-sub">Pincode payout vs cluster payout — P&L analysis</p>
    </div>
    """, unsafe_allow_html=True)

    bq_ok = bq_client is not None
    if not bq_ok:
        st.warning("BigQuery not connected. Connect via the sidebar to fetch hub list and AWB data.")

    calc = ClusterBurnCalculator()

    # ════════════════════════════════════════
    # STEP 1 — HUB SELECTION
    # ════════════════════════════════════════
    st.markdown(
        f'<div class="pn-section-label" style="margin-bottom:8px;">Step 1 — Select Hub(s)</div>',
        unsafe_allow_html=True,
    )

    with st.container():
        hub_mode = st.radio(
            "Hub ID source",
            ["Auto — select from loaded data", "Manual — type hub IDs"],
            horizontal=True,
            key="burn_hub_mode",
            label_visibility="collapsed",
        )

        if hub_mode.startswith("Auto"):
            hub_df = st.session_state.get("hub_data")

            if hub_df is None or (hasattr(hub_df, "empty") and hub_df.empty):
                st.info("No hub data loaded yet. Please load data using the **Data** tab first.")
                selected_ids = []
                name_map = {}
            else:
                options  = [f"{r['name']}  (ID: {r['id']})" for _, r in hub_df.iterrows()]
                id_map   = {f"{r['name']}  (ID: {r['id']})": int(r["id"]) for _, r in hub_df.iterrows()}
                name_map = {int(r["id"]): r["name"] for _, r in hub_df.iterrows()}

                chosen = st.multiselect(
                    "Select hub(s)",
                    options=options,
                    placeholder="Search and select one or more hubs…",
                    key="burn_hub_multiselect",
                )
                selected_ids = [id_map[c] for c in chosen]
        else:
            manual_raw = st.text_input(
                "Hub IDs (comma-separated)",
                placeholder="e.g.  15344, 12345, 67890",
                key="burn_manual_hub_ids",
            )
            selected_ids = [
                int(x.strip()) for x in manual_raw.split(",")
                if x.strip().isdigit()
            ] if manual_raw.strip() else []

            name_map = {}
            hub_df = st.session_state.get("hub_data")
            if hub_df is not None and not (hasattr(hub_df, "empty") and hub_df.empty):
                name_map = {int(r["id"]): r["name"] for _, r in hub_df.iterrows()}

    # ════════════════════════════════════════
    # STEP 2 — DATE RANGE
    # ════════════════════════════════════════
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown(
        '<div class="pn-section-label" style="margin-bottom:8px;">Step 2 — Date Range</div>',
        unsafe_allow_html=True,
    )
    col_sl, col_num = st.columns([4, 1])
    with col_sl:
        days_back = st.slider(
            "Days back from today",
            min_value=1, max_value=90, value=30, step=1,
            key="burn_days_slider",
            label_visibility="collapsed",
        )
    with col_num:
        days_back = st.number_input(
            "Days", min_value=1, max_value=90,
            value=days_back, step=1,
            key="burn_days_num",
            label_visibility="collapsed",
        )
    st.caption(f"Querying last **{days_back}** day(s)  ·  "
               f"{(pd.Timestamp.today() - pd.Timedelta(days=days_back)).strftime('%Y-%m-%d')} "
               f"→ {pd.Timestamp.today().strftime('%Y-%m-%d')}")

    # ════════════════════════════════════════
    # STEP 3 — FILE UPLOADS
    # ════════════════════════════════════════
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown(
        '<div class="pn-section-label" style="margin-bottom:8px;">Step 3 — Upload Cluster Polygon CSVs</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Upload **two** cluster-polygon CSVs (WKT + name + description). "
        "Burn is computed independently for each, then compared side-by-side."
    )
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        st.markdown("**Cluster polygons — Live CSV** *(required)*")
        live_file = st.file_uploader(
            "WKT polygon boundaries  (columns: WKT, name, description)",
            type=["csv"], key="burn_live_csv",
            label_visibility="collapsed",
        )
        if live_file:
            st.success(f"✅ {live_file.name}")
        else:
            st.caption("_Not uploaded — will use `Live5.csv` as fallback_")

    with col_f2:
        st.markdown("**Cluster polygons — Live CSV #2 (live1.csv)** *(required)*")
        live_file2 = st.file_uploader(
            "Second WKT polygon set (columns: WKT, name, description)",
            type=["csv"], key="burn_live_csv2",
            label_visibility="collapsed",
        )
        if live_file2:
            st.success(f"✅ {live_file2.name}")
        else:
            st.caption("_Upload the second polygon CSV to enable the comparison_")

    # Pincode CSV uploader removed — pincode-based fallback is disabled when
    # two cluster polygon CSVs drive the comparison.
    pincode_file = None

    # ════════════════════════════════════════
    # PREVIEW CARD
    # ════════════════════════════════════════
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown(
        '<div class="pn-section-label" style="margin-bottom:8px;">Preview — Confirm Before Running</div>',
        unsafe_allow_html=True,
    )

    hub_rows_html = ""
    for hid in selected_ids:
        hname = name_map.get(hid, "—") if name_map else "—"
        hub_rows_html += (
            f'<tr>'
            f'<td style="padding:5px 14px;font-weight:700;color:#1a56db;">{hid}</td>'
            f'<td style="padding:5px 14px;">{hname}</td>'
            f'</tr>'
        )
    if not hub_rows_html:
        hub_rows_html = (
            '<tr><td colspan="2" style="padding:5px 14px;color:#ba1a1a;">'
            '⚠ No hubs selected</td></tr>'
        )

    date_from = (pd.Timestamp.today() - pd.Timedelta(days=int(days_back))).strftime("%Y-%m-%d")
    date_to   = pd.Timestamp.today().strftime("%Y-%m-%d")

    def _fname(f, fallback):
        return f"<b style='color:#008A71'>{f.name}</b>" if f else f"<i style='color:#9ca3af'>{fallback}</i>"

    st.markdown(f"""
    <div style="background:{_bg};border:1.5px solid {_border};border-radius:14px;
                padding:20px 26px;max-width:700px;box-shadow:{_card_shd};">
      <div style="font-weight:700;font-size:1rem;margin-bottom:14px;color:{_text};">
        ✅ Query Preview
      </div>
      <table style="border-collapse:collapse;width:100%;margin-bottom:14px;
                    border:1px solid #bcd4f5;border-radius:8px;overflow:hidden;">
        <thead>
          <tr style="background:#99ccff;">
            <th style="padding:6px 14px;text-align:left;font-size:12px;">Hub ID</th>
            <th style="padding:6px 14px;text-align:left;font-size:12px;">Hub Name</th>
          </tr>
        </thead>
        <tbody style="background:#fff;">{hub_rows_html}</tbody>
      </table>
      <div style="margin-bottom:10px;color:{_text};">
        <span style="color:{_muted};">Date range:</span>
        <b style="font-size:1.2rem;margin:0 6px;color:{_green};">{int(days_back)}</b> days
        <span style="color:{_muted};font-size:12px;">({date_from} → {date_to})</span>
      </div>
      <div style="border-top:1px solid {_border};padding-top:10px;font-size:12px;color:{_text};">
        <div><span style="color:{_muted};min-width:130px;display:inline-block;">Live CSV #1:</span>
             {_fname(live_file, "Not uploaded — will use Live5.csv")}</div>
        <div style="margin-top:4px;">
             <span style="color:{_muted};min-width:130px;display:inline-block;">Live CSV #2:</span>
             {_fname(live_file2, "Not uploaded — comparison disabled")}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ════════════════════════════════════════
    # STEP 4 — RUN
    # ════════════════════════════════════════
    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    run_disabled = not selected_ids or not bq_ok
    run_tip = (
        "Select at least one hub to run" if not selected_ids
        else "BigQuery not connected" if not bq_ok
        else ""
    )

    if st.button(
        "▶  Fetch AWB & Calculate Burn (both CSVs)",
        key="burn_run_btn",
        type="primary",
        disabled=run_disabled,
        use_container_width=False,
        help=run_tip or "Fetch AWB data and compute P&L for both CSVs",
    ):
        # 4a. Fetch AWB
        with st.spinner(f"Fetching AWB data for {len(selected_ids)} hub(s), last {int(days_back)} days…"):
            awb_df, err = calc.fetch_awb(bq_client, selected_ids, int(days_back))

        if err:
            st.error(f"BigQuery error: {err}")
            return

        if awb_df.empty:
            st.warning("No AWB records returned. Try a wider date range or different hub IDs.")
            return

        st.success(f"✅ {len(awb_df):,} AWB records fetched")

        # 4b. Load BOTH cluster polygon sets
        def _load_csv(file_obj, label, fallback_path=None):
            clusters, skipped = (calc.load_clusters(file_obj) if file_obj else ([], []))
            if not clusters and fallback_path is not None:
                from pathlib import Path as _Path
                fb = _Path(fallback_path)
                if fb.exists():
                    with st.spinner(f"No upload for {label} — loading fallback {fb.name}…"):
                        clusters, skipped = calc.load_clusters(str(fb))
            return clusters, skipped

        clusters1, skipped1 = _load_csv(live_file, "Live CSV #1", "Live5.csv")
        clusters2, skipped2 = _load_csv(live_file2, "Live CSV #2", None)

        if not clusters1:
            st.error("Live CSV #1 produced no usable polygons. Upload a valid WKT CSV.")
            return
        if not clusters2:
            st.error("Live CSV #2 (live1.csv) is required for the comparison. Upload it and re-run.")
            return

        for label, skipped in (("Live CSV #1", skipped1), ("Live CSV #2", skipped2)):
            if skipped:
                with st.expander(f"⚠ {len(skipped)} polygon row(s) skipped in {label}"):
                    for s in skipped:
                        st.caption(f"Row {s[0]} | {s[1]} | {s[2]}")

        st.caption(f"Polygons loaded — CSV #1: **{len(clusters1)}**  ·  CSV #2: **{len(clusters2)}**")

        # 4c. Empty pincode map (we no longer use pincode fallback)
        pincode_map = {}

        # 4d. Assign clusters for each set, then compute P&L
        with st.spinner(f"Assigning clusters (CSV #1) to {len(awb_df):,} AWB points…"):
            result_df1 = calc.assign_clusters(awb_df, clusters1, pincode_map)
        with st.spinner(f"Assigning clusters (CSV #2) to {len(awb_df):,} AWB points…"):
            result_df2 = calc.assign_clusters(awb_df, clusters2, pincode_map)

        pnl_df1 = calc.calculate_pnl(result_df1)
        pnl_df2 = calc.calculate_pnl(result_df2)

        # Store both runs
        st.session_state["burn_pnl_df"]   = pnl_df1   # kept for legacy downloads
        st.session_state["burn_pnl_df1"]  = pnl_df1
        st.session_state["burn_pnl_df2"]  = pnl_df2
        st.session_state["burn_result_df1"] = result_df1
        st.session_state["burn_result_df2"] = result_df2
        st.session_state["burn_csv1_label"] = live_file.name if live_file else "Live5.csv"
        st.session_state["burn_csv2_label"] = live_file2.name if live_file2 else "live1.csv"

    # ════════════════════════════════════════
    # RESULTS — TWO TABLES + COMPARISON
    # ════════════════════════════════════════
    pnl_df1 = st.session_state.get("burn_pnl_df1")
    pnl_df2 = st.session_state.get("burn_pnl_df2")
    csv1_label = st.session_state.get("burn_csv1_label", "Live CSV #1")
    csv2_label = st.session_state.get("burn_csv2_label", "Live CSV #2")

    def _summary(df):
        if df is None or df.empty:
            return 0, 0.0, 0.0, 0.0
        return len(df), df["Saving"].sum(), df["Burning"].sum(), df["P & L"].sum()

    def _flat_pivot(df):
        """Hub × metric flat DataFrame (no styler) for diff arithmetic & download."""
        if df is None or df.empty:
            return pd.DataFrame(columns=["hub", "Expt_Pincode_Pay", "Cluster_Payout",
                                         "Saving", "Burning", "P & L", "P & L %"])
        p = df.pivot_table(
            index="hub",
            values=["Pin_Pay", "Clustering_payout", "Saving", "Burning", "P & L"],
            aggfunc="sum", margins=True, margins_name="Grand Total",
        ).reset_index().rename(columns={
            "Pin_Pay": "Expt_Pincode_Pay",
            "Clustering_payout": "Cluster_Payout",
        })
        num = ["Expt_Pincode_Pay", "Cluster_Payout", "Saving", "Burning", "P & L"]
        p[num] = p[num].apply(pd.to_numeric, errors="coerce")
        p["P & L %"] = (p["P & L"] / p["Expt_Pincode_Pay"].replace(0, pd.NA) * 100).round(2)
        return p[["hub"] + num + ["P & L %"]]

    have_results = (pnl_df1 is not None and not pnl_df1.empty) or \
                   (pnl_df2 is not None and not pnl_df2.empty)

    if have_results:
        st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
        st.markdown(
            '<div class="pn-section-label" style="margin-bottom:8px;">Results — P&L Report (both CSVs)</div>',
            unsafe_allow_html=True,
        )

        # ── Side-by-side summary metrics ──────────────────────────────────────
        t1, s1, b1, n1 = _summary(pnl_df1)
        t2, s2, b2, n2 = _summary(pnl_df2)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**CSV #1 — {csv1_label}**")
            mA, mB, mC, mD = st.columns(4)
            mA.metric("AWBs", f"{t1:,}")
            mB.metric("Saving", f"₹{s1:,.1f}")
            mC.metric("Burning", f"₹{b1:,.1f}")
            mD.metric("Net P&L", f"₹{n1:,.1f}",
                      delta=f"{'▲' if n1 >= 0 else '▼'} {abs(n1):,.1f}")
        with c2:
            st.markdown(f"**CSV #2 — {csv2_label}**")
            mA, mB, mC, mD = st.columns(4)
            mA.metric("AWBs", f"{t2:,}")
            mB.metric("Saving", f"₹{s2:,.1f}")
            mC.metric("Burning", f"₹{b2:,.1f}")
            mD.metric("Net P&L", f"₹{n2:,.1f}",
                      delta=f"{'▲' if n2 >= 0 else '▼'} {abs(n2):,.1f}")

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        # ── Two pivot tables side-by-side ─────────────────────────────────────
        tcol1, tcol2 = st.columns(2)
        with tcol1:
            st.markdown(f"#### Hub-level P&L — CSV #1 ({csv1_label})")
            if pnl_df1 is not None and not pnl_df1.empty:
                st.dataframe(calc.build_pivot(pnl_df1), use_container_width=True)
            else:
                st.info("No results for CSV #1.")
        with tcol2:
            st.markdown(f"#### Hub-level P&L — CSV #2 ({csv2_label})")
            if pnl_df2 is not None and not pnl_df2.empty:
                st.dataframe(calc.build_pivot(pnl_df2), use_container_width=True)
            else:
                st.info("No results for CSV #2.")

        # ── Comparison / diff table ───────────────────────────────────────────
        st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
        st.markdown("#### Comparison — CSV #2 vs CSV #1 (Δ per hub)")

        flat1 = _flat_pivot(pnl_df1).set_index("hub")
        flat2 = _flat_pivot(pnl_df2).set_index("hub")
        cols = ["Expt_Pincode_Pay", "Cluster_Payout", "Saving", "Burning", "P & L"]
        diff = pd.DataFrame(index=sorted(set(flat1.index) | set(flat2.index)))
        for c in cols:
            v1 = flat1[c].reindex(diff.index).fillna(0)
            v2 = flat2[c].reindex(diff.index).fillna(0)
            diff[f"{c} (CSV1)"] = v1
            diff[f"{c} (CSV2)"] = v2
            diff[f"Δ {c}"] = (v2 - v1).round(2)

        # Move Grand Total to the top, sort rest by |Δ P & L| desc
        diff = diff.reset_index().rename(columns={"index": "hub"})
        gt   = diff[diff["hub"] == "Grand Total"]
        rest = diff[diff["hub"] != "Grand Total"].assign(
            _abs=lambda d: d["Δ P & L"].abs()
        ).sort_values("_abs", ascending=False).drop(columns="_abs")
        diff = pd.concat([gt, rest], ignore_index=True)

        # Color the Δ columns
        delta_cols = [c for c in diff.columns if c.startswith("Δ ")]
        styled_diff = (
            diff.set_index("hub").style
                .map(
                    lambda v: ("color:green" if v > 0 else "color:red")
                    if isinstance(v, (int, float)) else "",
                    subset=delta_cols,
                )
                .format({c: "{:,.0f}" for c in diff.columns if c != "hub"})
                .set_properties(**{"text-align": "center"})
                .set_table_styles([{"selector": "th", "props": [
                    ("text-align", "center"), ("font-weight", "bold"),
                    ("background-color", "#fde68a"),
                ]}])
        )
        st.dataframe(styled_diff, use_container_width=True)

        # ── Download buttons ──────────────────────────────────────────────────
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        dc1, dc2, dc3 = st.columns(3)
        with dc1:
            if pnl_df1 is not None and not pnl_df1.empty:
                st.download_button(
                    "⬇ CSV #1 raw (csv)",
                    data=pnl_df1.to_csv(index=False).encode("utf-8"),
                    file_name="cluster_burn_csv1_raw.csv",
                    mime="text/csv", key="burn_dl_raw1",
                )
        with dc2:
            if pnl_df2 is not None and not pnl_df2.empty:
                st.download_button(
                    "⬇ CSV #2 raw (csv)",
                    data=pnl_df2.to_csv(index=False).encode("utf-8"),
                    file_name="cluster_burn_csv2_raw.csv",
                    mime="text/csv", key="burn_dl_raw2",
                )
        with dc3:
            st.download_button(
                "⬇ Diff table (csv)",
                data=diff.to_csv(index=False).encode("utf-8"),
                file_name="cluster_burn_diff.csv",
                mime="text/csv", key="burn_dl_diff",
            )

        # ── Expandable raw data tables ────────────────────────────────────────
        with st.expander("View raw AWB data — CSV #1"):
            if pnl_df1 is not None:
                st.dataframe(pnl_df1, use_container_width=True, height=320)
        with st.expander("View raw AWB data — CSV #2"):
            if pnl_df2 is not None:
                st.dataframe(pnl_df2, use_container_width=True, height=320)
