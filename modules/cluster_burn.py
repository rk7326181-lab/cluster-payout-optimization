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
            ["Auto — select from list (BigQuery)", "Manual — type hub IDs"],
            horizontal=True,
            key="burn_hub_mode",
            label_visibility="collapsed",
        )

        if hub_mode.startswith("Auto"):
            # Fetch hub list (cached in session)
            if "burn_hub_df" not in st.session_state:
                if bq_ok:
                    with st.spinner("Loading hub list from BigQuery…"):
                        try:
                            st.session_state["burn_hub_df"] = calc.fetch_hub_list(bq_client)
                        except Exception as exc:
                            st.error(f"Hub fetch failed: {exc}")
                            st.session_state["burn_hub_df"] = pd.DataFrame(columns=["id", "name"])
                else:
                    st.session_state["burn_hub_df"] = pd.DataFrame(columns=["id", "name"])

            hub_df = st.session_state["burn_hub_df"]

            if hub_df.empty:
                st.info("No hubs loaded. Check BigQuery connection.")
                selected_ids = []
            else:
                options      = [f"{r['name']}  (ID: {r['id']})" for _, r in hub_df.iterrows()]
                id_map       = {f"{r['name']}  (ID: {r['id']})": int(r["id"]) for _, r in hub_df.iterrows()}
                name_map     = {int(r["id"]): r["name"] for _, r in hub_df.iterrows()}

                chosen = st.multiselect(
                    "Select hub(s)",
                    options=options,
                    placeholder="Search and select one or more hubs…",
                    key="burn_hub_multiselect",
                )
                selected_ids = [id_map[c] for c in chosen]

                if st.button("🔄 Refresh hub list", key="burn_refresh_hubs"):
                    st.session_state.pop("burn_hub_df", None)
                    st.rerun()
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
            if bq_ok and selected_ids and "burn_hub_df" in st.session_state:
                hdf = st.session_state["burn_hub_df"]
                name_map = {int(r["id"]): r["name"] for _, r in hdf.iterrows()}

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
        '<div class="pn-section-label" style="margin-bottom:8px;">Step 3 — Upload CSV Files</div>',
        unsafe_allow_html=True,
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
        st.markdown("**Pincode boundaries CSV** *(optional)*")
        pincode_file = st.file_uploader(
            "Pincode map  (columns: pincode, description)",
            type=["csv"], key="burn_pincode_csv",
            label_visibility="collapsed",
        )
        if pincode_file:
            st.success(f"✅ {pincode_file.name}")
        else:
            st.caption("_Not uploaded — built-in defaults used_")

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
        <div><span style="color:{_muted};min-width:110px;display:inline-block;">Live CSV:</span>
             {_fname(live_file, "Not uploaded — will use Live5.csv")}</div>
        <div style="margin-top:4px;">
             <span style="color:{_muted};min-width:110px;display:inline-block;">Pincode CSV:</span>
             {_fname(pincode_file, "Not uploaded — built-in defaults")}</div>
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
        "▶  Fetch AWB & Calculate Burn",
        key="burn_run_btn",
        type="primary",
        disabled=run_disabled,
        use_container_width=False,
        help=run_tip or "Fetch AWB data and compute P&L",
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

        # 4b. Load cluster polygons
        clusters, skipped = (
            calc.load_clusters(live_file)
            if live_file
            else ([], [])
        )
        if not clusters:
            from pathlib import Path as _Path
            _fallback = _Path("Live5.csv")
            if _fallback.exists():
                with st.spinner("No upload — loading fallback Live5.csv…"):
                    clusters, skipped = calc.load_clusters(str(_fallback))
            else:
                st.warning("No Live CSV uploaded and Live5.csv not found. "
                           "Cluster assignment will use pincode fallback only.")
                clusters = []

        if skipped:
            with st.expander(f"⚠ {len(skipped)} polygon row(s) skipped"):
                for s in skipped:
                    st.caption(f"Row {s[0]} | {s[1]} | {s[2]}")

        if clusters:
            st.caption(f"Cluster polygons loaded: **{len(clusters)}**")

        # 4c. Load pincode map
        pincode_map = calc.load_pincode_map(pincode_file)

        # 4d. Assign clusters
        with st.spinner(f"Assigning clusters to {len(awb_df):,} AWB points…"):
            result_df = calc.assign_clusters(awb_df, clusters, pincode_map)

        # 4e. P&L
        pnl_df = calc.calculate_pnl(result_df)

        st.session_state["burn_pnl_df"]    = pnl_df
        st.session_state["burn_result_df"] = result_df

    # ════════════════════════════════════════
    # RESULTS
    # ════════════════════════════════════════
    pnl_df = st.session_state.get("burn_pnl_df")

    if pnl_df is not None and not pnl_df.empty:
        st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
        st.markdown(
            '<div class="pn-section-label" style="margin-bottom:8px;">Results — P&L Report</div>',
            unsafe_allow_html=True,
        )

        # ── Summary metric cards ──────────────────────────────────────────────
        total_saving  = pnl_df["Saving"].sum()
        total_burning = pnl_df["Burning"].sum()
        total_pnl     = pnl_df["P & L"].sum()
        total_awb     = len(pnl_df)
        pnl_color     = _green if total_pnl >= 0 else "#ba1a1a"

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total AWBs",      f"{total_awb:,}")
        m2.metric("Total Saving",    f"₹{total_saving:,.1f}")
        m3.metric("Total Burning",   f"₹{total_burning:,.1f}")
        m4.metric("Net P & L",       f"₹{total_pnl:,.1f}",
                  delta=f"{'▲' if total_pnl >= 0 else '▼'} {abs(total_pnl):,.1f}")

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        # ── Pivot table ───────────────────────────────────────────────────────
        st.markdown("#### Hub-level P&L Pivot")
        styled = calc.build_pivot(pnl_df)
        st.dataframe(styled, use_container_width=True)

        # ── Download buttons ──────────────────────────────────────────────────
        col_d1, col_d2, _ = st.columns([2, 2, 6])
        with col_d1:
            st.download_button(
                "⬇ Download raw data (CSV)",
                data=pnl_df.to_csv(index=False).encode("utf-8"),
                file_name="cluster_burn_raw.csv",
                mime="text/csv",
                key="burn_dl_raw",
            )
        with col_d2:
            pivot_df = pnl_df.pivot_table(
                index="hub",
                values=["Pin_Pay", "Clustering_payout", "Saving", "Burning", "P & L"],
                aggfunc="sum", margins=True, margins_name="Grand Total",
            ).reset_index()
            st.download_button(
                "⬇ Download pivot (CSV)",
                data=pivot_df.to_csv(index=False).encode("utf-8"),
                file_name="cluster_burn_pivot.csv",
                mime="text/csv",
                key="burn_dl_pivot",
            )

        # ── Expandable raw data table ─────────────────────────────────────────
        with st.expander("View raw AWB data"):
            st.dataframe(pnl_df, use_container_width=True, height=320)
