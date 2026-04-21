"""
CPO Analytics — Hub-Level Cluster Payout & CPO Analysis
========================================================
Reads the hub_wise sheet from CPO Excel to identify high-cost hubs,
analyze cluster payouts, and generate data-driven optimization recommendations.
"""

import pandas as pd
import numpy as np
from pathlib import Path

# Clustering financial constants (from clustering_app)
DESCRIPTION_MAPPING = {
    "C1": 0, "C2": 0.5, "C3": 1, "C4": 1.5, "C5": 2, "C6": 2.5,
    "C7": 3, "C8": 3.5, "C9": 4, "C10": 4.5, "C11": 5, "C12": 6,
    "C13": 7, "C14": 8, "C15": 9, "C16": 10, "C17": 11, "C18": 12,
    "C19": 13, "C20": 15,
}

# Official SOP: Standard practice uses C1→C3→C5→C7→C9→C11→C12-C20
# Even categories (C2/C4/C6/C8/C10) are skipped normally; used sometimes for fine-tuning.
# When skipped, the next category covers the wider distance range.
PRICING_SLABS = [
    (0, 4, 0),      # C1: ₹0
    (4, 12, 1),     # C3: ₹1  (covers C2 range too)
    (12, 22, 2),    # C5: ₹2  (covers C4 range too)
    (22, 30, 3),    # C7: ₹3  (covers C6 range too)
    (30, 40, 4),    # C9: ₹4  (covers C8 range too)
    (40, 48, 5),    # C11: ₹5 (covers C10 range too)
    (48, 52, 6),    # C12: ₹6
    (52, 56, 7),    # C13: ₹7
    (56, 60, 8),    # C14: ₹8
    (60, 64, 9),    # C15: ₹9
    (64, 68, 10),   # C16: ₹10
    (68, 72, 11),   # C17: ₹11
    (72, 76, 12),   # C18: ₹12
    (76, 80, 13),   # C19: ₹13
    # C20: 80+ km = ₹15
]


class CPOAnalytics:
    """Hub-level CPO and Cluster Payout analytics from the CPO Excel file."""

    def __init__(self, excel_path=None):
        self.excel_path = excel_path
        self.hub_df = None
        self.base_df = None
        self._loaded = False

        if excel_path and Path(excel_path).exists():
            self._load(excel_path)

    def _load(self, path):
        """Load hub_wise sheet (lightweight). Base file loaded on demand."""
        try:
            self.hub_df = pd.read_excel(path, sheet_name="hub_wise")
            self.hub_df.columns = self.hub_df.columns.str.strip()
            # Derived columns
            self.hub_df["is_clustered"] = self.hub_df["Cluster_Pay"] > 0
            self.hub_df["cluster_cpo"] = np.where(
                self.hub_df["LM_Orders"] > 0,
                self.hub_df["Cluster_Pay"] / self.hub_df["LM_Orders"],
                0,
            )
            self._loaded = True
        except Exception as e:
            print(f"CPOAnalytics load error: {e}")
            self._loaded = False

    @property
    def is_loaded(self):
        return self._loaded and self.hub_df is not None

    # ──────────────────────────────────────────────
    # Summary KPIs
    # ──────────────────────────────────────────────
    def get_summary(self):
        """Return top-level KPIs across all hubs."""
        df = self.hub_df
        clustered = df[df["is_clustered"]]
        non_clustered = df[~df["is_clustered"]]

        # Filter to hubs with meaningful order volume
        sig = df[df["LM_Orders"] >= 50]

        clustered_sig = clustered[clustered["LM_Orders"] >= 50]
        non_clustered_sig = non_clustered[non_clustered["LM_Orders"] >= 50]
        return {
            "total_hubs": len(df),
            "clustered_hubs": len(clustered),
            "non_clustered_hubs": len(non_clustered),
            "total_cluster_pay": float(df["Cluster_Pay"].sum()),
            "avg_cluster_cpo_all": float(sig["cluster_cpo"].mean()) if len(sig) else 0,
            "avg_cluster_cpo_clustered": float(
                clustered_sig["cluster_cpo"].mean()
            ) if len(clustered_sig) else 0,
            "avg_cluster_cpo_non_clustered": float(
                non_clustered_sig["cluster_cpo"].mean()
            ) if len(non_clustered_sig) else 0,
            # Keep Net CPO for backward compat but not primary display
            "avg_net_cpo_all": float(sig["Net_CPO"].mean()) if len(sig) else 0,
            "avg_net_cpo_clustered": float(
                clustered_sig["Net_CPO"].mean()
            ) if len(clustered_sig) else 0,
            "avg_net_cpo_non_clustered": float(
                non_clustered_sig["Net_CPO"].mean()
            ) if len(non_clustered_sig) else 0,
            "total_orders": int(df["LM_Orders"].sum()),
            "total_payout": float(df["total_pay"].sum()),
            "total_pn_pay": float(df["Pn_Pay"].sum()),
        }

    # ──────────────────────────────────────────────
    # High Cluster Payout Hubs
    # ──────────────────────────────────────────────
    def get_high_cluster_payout_hubs(self, top_n=30):
        """Hubs ranked by total Cluster_Pay (descending)."""
        df = self.hub_df[self.hub_df["Cluster_Pay"] > 0].copy()
        df = df.sort_values("Cluster_Pay", ascending=False).head(top_n)
        df["cluster_pct_of_total"] = np.where(
            df["total_pay"] > 0,
            (df["Cluster_Pay"] / df["total_pay"] * 100).round(1),
            0,
        )
        return df[
            ["hub", "Cluster_Pay", "cluster_cpo", "LM_CPO",
             "LM_Orders", "total_pay", "cluster_pct_of_total"]
        ].reset_index(drop=True)

    # ──────────────────────────────────────────────
    # High CPO Hubs
    # ──────────────────────────────────────────────
    def get_high_cpo_hubs(self, min_orders=100, top_n=30, cpo_col="cluster_cpo"):
        """Hubs with highest Cluster CPO that have significant order volume."""
        df = self.hub_df[self.hub_df["LM_Orders"] >= min_orders].copy()
        df = df.sort_values(cpo_col, ascending=False).head(top_n)
        return df[
            ["hub", "cluster_cpo", "Cluster_Pay", "LM_CPO",
             "LM_Orders", "total_pay"]
        ].reset_index(drop=True)

    # ──────────────────────────────────────────────
    # CPO Distribution
    # ──────────────────────────────────────────────
    def get_cpo_distribution(self, min_orders=50):
        """Cluster CPO buckets for significant-volume hubs."""
        df = self.hub_df[self.hub_df["LM_Orders"] >= min_orders].copy()
        bins = [0, 0.5, 1, 1.5, 2, 3, 5, 1000]
        labels = ["<0.5", "0.5-1", "1-1.5", "1.5-2", "2-3", "3-5", "5+"]
        df["cpo_bucket"] = pd.cut(df["cluster_cpo"], bins=bins, labels=labels, right=False)
        dist = df.groupby("cpo_bucket", observed=True).agg(
            hub_count=("hub", "count"),
            avg_cluster_pay=("Cluster_Pay", "mean"),
            total_orders=("LM_Orders", "sum"),
        ).reset_index()
        return dist

    # ──────────────────────────────────────────────
    # Optimization Candidates
    # ──────────────────────────────────────────────
    def get_optimization_candidates(self, min_orders=100, top_n=30):
        """
        Hubs where clustering cost is disproportionately high relative to orders.
        High cluster_cpo = Cluster_Pay / LM_Orders.
        These are the hubs where rate changes will have the most impact.
        """
        df = self.hub_df[
            (self.hub_df["LM_Orders"] >= min_orders) &
            (self.hub_df["Cluster_Pay"] > 0)
        ].copy()

        # Cluster CPO = how much clustering costs per order at this hub
        median_cluster_cpo = df["cluster_cpo"].median()
        df["excess_cluster_cpo"] = (df["cluster_cpo"] - median_cluster_cpo).clip(lower=0)
        df["potential_saving"] = df["excess_cluster_cpo"] * df["LM_Orders"]
        df["potential_saving_annual"] = df["potential_saving"] * 12

        # Priority based on absolute saving potential
        df["priority"] = pd.cut(
            df["potential_saving"],
            bins=[-1, 500, 2000, 5000, float("inf")],
            labels=["Low", "Medium", "High", "Critical"],
        )

        df = df.sort_values("potential_saving", ascending=False).head(top_n)
        return df[
            ["hub", "Cluster_Pay", "cluster_cpo", "excess_cluster_cpo",
             "LM_Orders", "Net_CPO", "potential_saving", "potential_saving_annual",
             "priority", "Pn_Pay", "total_pay"]
        ].reset_index(drop=True)

    # ──────────────────────────────────────────────
    # High Burn Hubs (CPO > threshold)
    # ──────────────────────────────────────────────
    def get_high_burn_hubs(self, cpo_threshold=1.0, min_orders=50):
        """Hubs where cluster_cpo exceeds the threshold — targets for polygon expansion.
        cluster_cpo = Cluster_Pay / LM_Orders (per-order cluster payout in ₹)."""
        if not self.is_loaded:
            return pd.DataFrame()
        df = self.hub_df[
            (self.hub_df["cluster_cpo"] > cpo_threshold) &
            (self.hub_df["LM_Orders"] >= min_orders) &
            (self.hub_df["Cluster_Pay"] > 0)
        ].copy()
        if df.empty:
            return pd.DataFrame()

        df["excess_cpo"] = df["cluster_cpo"] - cpo_threshold
        df["monthly_burn"] = df["excess_cpo"] * df["LM_Orders"]
        df["annual_burn"] = df["monthly_burn"] * 12

        df = df.sort_values("monthly_burn", ascending=False)
        return df[
            ["hub", "Cluster_Pay", "cluster_cpo", "excess_cpo",
             "LM_Orders", "LM_CPO", "total_pay",
             "monthly_burn", "annual_burn"]
        ].reset_index(drop=True)

    def get_burn_summary(self, cpo_threshold=1.0, min_orders=50):
        """Summary KPIs for high-burn hubs."""
        burn_df = self.get_high_burn_hubs(cpo_threshold=cpo_threshold, min_orders=min_orders)
        if burn_df.empty:
            return {
                "hub_count": 0, "total_monthly_burn": 0, "total_annual_burn": 0,
                "avg_cluster_cpo": 0, "max_cluster_cpo": 0,
                "total_cluster_pay": 0, "total_orders": 0, "top_burn_hub": "N/A",
            }
        return {
            "hub_count": len(burn_df),
            "total_monthly_burn": float(burn_df["monthly_burn"].sum()),
            "total_annual_burn": float(burn_df["annual_burn"].sum()),
            "avg_cluster_cpo": float(burn_df["cluster_cpo"].mean()),
            "max_cluster_cpo": float(burn_df["cluster_cpo"].max()),
            "total_cluster_pay": float(burn_df["Cluster_Pay"].sum()),
            "total_orders": int(burn_df["LM_Orders"].sum()),
            "top_burn_hub": str(burn_df.iloc[0]["hub"]) if len(burn_df) > 0 else "N/A",
        }

    # ──────────────────────────────────────────────
    # Cluster vs Non-Cluster Comparison
    # ──────────────────────────────────────────────
    def get_cluster_comparison(self, min_orders=50):
        """Side-by-side comparison of clustered vs non-clustered hubs."""
        df = self.hub_df[self.hub_df["LM_Orders"] >= min_orders]
        clustered = df[df["is_clustered"]]
        non_clustered = df[~df["is_clustered"]]

        rows = []
        for label, subset in [("Clustered", clustered), ("Non-Clustered", non_clustered)]:
            rows.append({
                "Category": label,
                "Hubs": len(subset),
                "Total Orders": int(subset["LM_Orders"].sum()),
                "Avg Cluster CPO": round(subset["cluster_cpo"].mean(), 2),
                "Avg LM CPO": round(subset["LM_CPO"].mean(), 2),
                "Total Cluster Pay": int(subset["Cluster_Pay"].sum()),
                "Total Payout": int(subset["total_pay"].sum()),
            })
        return pd.DataFrame(rows)

    # ──────────────────────────────────────────────
    # Generate Rate Change Recommendations
    # ──────────────────────────────────────────────
    def generate_recommendations(self, min_orders=100, top_n=20):
        """
        For each high-cost clustered hub, recommend a target cluster rate reduction
        and estimate the monthly/annual savings.
        """
        candidates = self.get_optimization_candidates(min_orders=min_orders, top_n=top_n)
        if len(candidates) == 0:
            return pd.DataFrame()

        median_cpo = self.hub_df[
            (self.hub_df["LM_Orders"] >= min_orders) &
            (self.hub_df["Cluster_Pay"] > 0)
        ]["cluster_cpo"].median()

        recs = []
        for _, row in candidates.iterrows():
            current_cluster_cpo = row["cluster_cpo"]
            target_cluster_cpo = median_cpo
            orders = row["LM_Orders"]
            saving_per_order = max(0, current_cluster_cpo - target_cluster_cpo)
            monthly_save = saving_per_order * orders
            annual_save = monthly_save * 12

            # Suggest action
            if saving_per_order > 3:
                action = f"Reduce cluster rates by ~₹{saving_per_order:.1f}/order. Review polygon boundaries."
            elif saving_per_order > 1.5:
                action = f"Optimize cluster to reduce ~₹{saving_per_order:.1f}/order. Check P-mapping alignment."
            elif saving_per_order > 0.5:
                action = f"Minor rate adjustment of ~₹{saving_per_order:.1f}/order possible."
            else:
                action = "Near optimal — monitor for drift."

            recs.append({
                "Hub": row["hub"],
                "Current Cluster CPO": round(current_cluster_cpo, 2),
                "Target Cluster CPO": round(target_cluster_cpo, 2),
                "Excess (₹/order)": round(saving_per_order, 2),
                "Orders": int(orders),
                "Monthly Saving": round(monthly_save, 0),
                "Annual Saving": round(annual_save, 0),
                "Net CPO": round(row["Net_CPO"], 2),
                "Priority": row["priority"],
                "Action": action,
            })
        return pd.DataFrame(recs)

    # ──────────────────────────────────────────────
    # Scatter Data (for plotly)
    # ──────────────────────────────────────────────
    def get_scatter_data(self, min_orders=50):
        """Return DataFrame for CPO vs Cluster Pay scatter plot."""
        df = self.hub_df[self.hub_df["LM_Orders"] >= min_orders].copy()
        df["marker_size"] = np.clip(df["LM_Orders"] / df["LM_Orders"].max() * 30, 4, 30)
        return df[["hub", "Net_CPO", "Cluster_Pay", "cluster_cpo",
                    "LM_Orders", "total_pay", "marker_size", "is_clustered"]]


# ════════════════════════════════════════════════════
# AWB Financial Calculations — Pin_Pay vs Clustering Payout
# ════════════════════════════════════════════════════

def calculate_awb_financials(awb_df, cluster_df):
    """
    Given AWB data with lat/long and cluster polygon data,
    compute Pin_Pay, Clustering_payout, P&L per AWB row.
    Returns enriched DataFrame with financial columns.
    """
    from shapely.wkt import loads as load_wkt
    from shapely.geometry import Point
    from shapely.prepared import prep

    df = awb_df.copy()
    df.columns = df.columns.str.strip().str.lower()
    df["lat"] = pd.to_numeric(df.get("lat"), errors="coerce")
    df["long"] = pd.to_numeric(df.get("long"), errors="coerce")

    # Build spatial index from cluster polygons
    clusters = []
    for _, row in cluster_df.iterrows():
        boundary = row.get("boundary", "")
        if not boundary or pd.isna(boundary):
            continue
        try:
            polygon = load_wkt(str(boundary))
            clusters.append({
                "prepared": prep(polygon),
                "description": str(row.get("description", "")),
                "cluster_code": str(row.get("cluster_code", "")),
                "hub_id": row.get("hub_id"),
            })
        except Exception:
            continue

    # Match each AWB to a cluster polygon
    results = []
    for _, row in df.iterrows():
        lat, lon = row.get("lat"), row.get("long")
        if pd.isna(lat) or pd.isna(lon) or lat == 0 or lon == 0:
            continue

        point = Point(float(lon), float(lat))
        matched_desc = None
        for c in clusters:
            if c["prepared"].contains(point):
                matched_desc = c["description"]
                break

        # Pin_Pay = payment_category value (P-mapping number)
        pin_pay = None
        pay_cat = str(row.get("payment_category", ""))
        if pay_cat.startswith("P"):
            try:
                pin_pay = float(pay_cat[1:])
            except ValueError:
                pass

        # Clustering_payout = DESCRIPTION_MAPPING lookup
        clustering_payout = DESCRIPTION_MAPPING.get(matched_desc, pin_pay) if matched_desc else pin_pay

        pnl = (pin_pay or 0) - (clustering_payout or 0)

        results.append({
            "awb": row.get("fwd_del_awb_number", ""),
            "hub": row.get("hub", ""),
            "pincode": row.get("pincode", ""),
            "pin_pay": pin_pay,
            "cluster_desc": matched_desc,
            "clustering_payout": clustering_payout,
            "p_and_l": pnl,
            "saving": pnl if pnl > 0 else 0,
            "burning": -pnl if pnl < 0 else 0,
        })

    return pd.DataFrame(results)
