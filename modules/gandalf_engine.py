"""
G.A.N.D.A.L.F. Intelligence Engine
Guided Analytics Network for Delivery And Logistics Facilitation

The AI brain behind Shadowfax's logistics cost optimization.
Free, no paid API. Pure Python analytics + optional Ollama/Groq LLM.
"""

import numpy as np
import pandas as pd
from datetime import datetime


class GandalfEngine:
    """Core GANDALF analytics brain. Analyzes clusters, hubs, costs, anomalies."""

    VERSION = "1.0.0"
    CODENAME = "GANDALF"
    FULL_NAME = "Guided Analytics Network for Delivery And Logistics Facilitation"

    def __init__(self, cluster_df=None, hub_df=None, processed_df=None,
                 cpo_analytics=None, awb_counts=None, polygon_optimizer=None):
        self.cluster_df = cluster_df
        self.hub_df = hub_df
        self.processed_df = processed_df
        self.cpo_analytics = cpo_analytics
        self.awb_counts = awb_counts or {}
        self.polygon_optimizer = polygon_optimizer
        self._cache = {}

    def update_data(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)
        self._cache.clear()

    # ──────────────────────────────────────────────
    #  SYSTEM HEALTH ANALYSIS
    # ──────────────────────────────────────────────

    def analyze_health(self) -> dict:
        if "health" in self._cache:
            return self._cache["health"]

        health = {"score": 0, "max_score": 100, "checks": [], "warnings": [], "critical": []}

        if self.cluster_df is not None and len(self.cluster_df) > 0:
            health["checks"].append({"name": "Cluster Data", "status": "ok",
                                     "detail": f"{len(self.cluster_df):,} clusters loaded"})
            health["score"] += 20
        else:
            health["critical"].append("No cluster data loaded")

        if self.hub_df is not None and len(self.hub_df) > 0:
            health["checks"].append({"name": "Hub Data", "status": "ok",
                                     "detail": f"{len(self.hub_df):,} hubs loaded"})
            health["score"] += 20
        else:
            health["critical"].append("No hub data loaded")

        if self.awb_counts and len(self.awb_counts) > 0:
            total_awb = sum(self.awb_counts.values())
            health["checks"].append({"name": "AWB Data", "status": "ok",
                                     "detail": f"{total_awb:,} shipments tracked"})
            health["score"] += 20
        else:
            health["warnings"].append("AWB data not loaded — fetch for full analytics")

        if self.cpo_analytics is not None:
            health["checks"].append({"name": "CPO Analytics", "status": "ok",
                                     "detail": "Engine initialized"})
            health["score"] += 20
        else:
            health["warnings"].append("CPO analytics not initialized")

        if self.cluster_df is not None and len(self.cluster_df) > 0:
            if "surge_amount" in self.cluster_df.columns:
                zero_rates = (self.cluster_df["surge_amount"] == 0).sum()
                if zero_rates <= len(self.cluster_df) * 0.3:
                    health["score"] += 20
                else:
                    health["warnings"].append(
                        f"{zero_rates:,} clusters ({zero_rates * 100 // len(self.cluster_df)}%) have zero surge rate")

        health["grade"] = (
            "A+" if health["score"] >= 95 else "A" if health["score"] >= 85 else
            "B" if health["score"] >= 70 else "C" if health["score"] >= 50 else
            "D" if health["score"] >= 30 else "F")

        self._cache["health"] = health
        return health

    # ──────────────────────────────────────────────
    #  ANOMALY DETECTION
    # ──────────────────────────────────────────────

    def detect_anomalies(self) -> list:
        if "anomalies" in self._cache:
            return self._cache["anomalies"]
        anomalies = []
        if self.cluster_df is None or len(self.cluster_df) == 0:
            return anomalies
        df = self.cluster_df

        # 1. Surge rate outliers (IQR)
        if "surge_amount" in df.columns:
            rates = df["surge_amount"].dropna()
            if len(rates) > 10:
                q1, q3 = rates.quantile(0.25), rates.quantile(0.75)
                iqr = q3 - q1
                upper = q3 + 1.5 * iqr
                outliers = df[df["surge_amount"] > upper]
                if len(outliers) > 0:
                    hubs = outliers["hub_name"].unique()[:3].tolist() if "hub_name" in outliers.columns else []
                    anomalies.append({
                        "type": "cost", "severity": "high",
                        "title": f"{len(outliers)} clusters with abnormally high surge rates",
                        "detail": f"Rates above {upper:.1f}. Top hubs: {', '.join(hubs)}",
                        "action": "Review rate justification; compare with neighboring areas",
                    })

        # 2. Hub concentration
        if "hub_name" in df.columns:
            hub_counts = df["hub_name"].value_counts()
            if len(hub_counts) > 5:
                mean_c, std_c = hub_counts.mean(), hub_counts.std()
                overloaded = hub_counts[hub_counts > mean_c + 2 * std_c]
                if len(overloaded) > 0:
                    anomalies.append({
                        "type": "capacity", "severity": "medium",
                        "title": f"{len(overloaded)} hubs with disproportionately many clusters",
                        "detail": f"Avg: {mean_c:.0f}/hub. These have {overloaded.min()}-{overloaded.max()}: {', '.join(overloaded.index[:3])}",
                        "action": "Consider splitting or redistributing clusters",
                    })

        # 3. Rate inconsistency within hubs
        if "surge_amount" in df.columns and "hub_name" in df.columns:
            hvar = df.groupby("hub_name")["surge_amount"].agg(["std", "count"])
            hvar = hvar[hvar["count"] >= 5]
            if len(hvar) > 0:
                high_var = hvar[hvar["std"] > hvar["std"].quantile(0.9)]
                if len(high_var) > 0:
                    anomalies.append({
                        "type": "inconsistency", "severity": "medium",
                        "title": f"{len(high_var)} hubs with highly inconsistent rates",
                        "detail": f"High rate variance: {', '.join(high_var.index[:3])}",
                        "action": "Standardize rates within these hubs",
                    })

        # 4. AWB coverage gaps
        if self.awb_counts and "hub_name" in df.columns and "pincode" in df.columns:
            defined = {(str(r.get("hub_name", "")), str(r.get("pincode", "")))
                       for _, r in df.iterrows() if r.get("hub_name") and r.get("pincode")}
            awb_keys = set(self.awb_counts.keys())
            no_awb = defined - awb_keys
            if len(no_awb) > len(defined) * 0.1:
                anomalies.append({
                    "type": "coverage", "severity": "medium",
                    "title": f"{len(no_awb)} cluster-pincode pairs have zero shipments",
                    "detail": f"{100 * len(no_awb) // max(1, len(defined))}% of defined clusters have no AWB data",
                    "action": "Remove or merge zero-demand clusters",
                })

        self._cache["anomalies"] = anomalies
        return anomalies

    # ──────────────────────────────────────────────
    #  COST OPTIMIZATION INTELLIGENCE
    # ──────────────────────────────────────────────

    def analyze_cost_opportunities(self) -> list:
        if "cost_opps" in self._cache:
            return self._cache["cost_opps"]
        opportunities = []
        if self.cluster_df is None or len(self.cluster_df) == 0:
            return opportunities
        df = self.cluster_df

        # 1. Rate reduction targets
        if "surge_amount" in df.columns and "hub_name" in df.columns:
            hub_stats = df.groupby("hub_name").agg(
                avg_rate=("surge_amount", "mean"), max_rate=("surge_amount", "max"),
                cluster_count=("surge_amount", "count"), total_rate=("surge_amount", "sum"),
            ).reset_index()
            median_avg = hub_stats["avg_rate"].median()
            expensive = hub_stats[hub_stats["avg_rate"] > median_avg * 1.5]
            if len(expensive) > 0:
                opportunities.append({
                    "type": "rate_reduction", "priority": "high",
                    "title": f"{len(expensive)} hubs with above-median surge rates",
                    "detail": f"Avg {expensive['avg_rate'].mean():.2f}/order vs median {median_avg:.2f}",
                    "savings_estimate": f"~{expensive['total_rate'].sum() - len(expensive) * median_avg * expensive['cluster_count'].mean():.0f}/order potential",
                    "confidence": 0.75,
                    "hubs": expensive.nlargest(5, "avg_rate")["hub_name"].tolist(),
                })

        # 2. Consolidation
        if "hub_name" in df.columns and "pincode" in df.columns:
            pin_counts = df.groupby(["hub_name", "pincode"]).size().reset_index(name="n")
            multi = pin_counts[pin_counts["n"] > 3]
            if len(multi) > 0:
                opportunities.append({
                    "type": "consolidation", "priority": "medium",
                    "title": f"{len(multi)} pincodes with 4+ clusters (merge candidates)",
                    "detail": f"Max: {multi['n'].max()} clusters in one pincode",
                    "savings_estimate": "5-15% operational overhead reduction",
                    "confidence": 0.6,
                    "hubs": multi.nlargest(5, "n")["hub_name"].tolist(),
                })

        # 3. Zero-rate revenue capture
        if "surge_amount" in df.columns:
            zero_rate = df[df["surge_amount"] == 0]
            non_zero = df[df["surge_amount"] > 0]
            if len(zero_rate) > len(df) * 0.3 and len(non_zero) > 0:
                avg_nz = non_zero["surge_amount"].mean()
                opportunities.append({
                    "type": "revenue_capture", "priority": "medium",
                    "title": f"{len(zero_rate)} clusters ({100 * len(zero_rate) // len(df)}%) at zero rate",
                    "detail": f"Non-zero clusters average {avg_nz:.2f}",
                    "savings_estimate": f"Potential {len(zero_rate) * avg_nz * 0.3:.0f}/order additional revenue",
                    "confidence": 0.5,
                    "hubs": zero_rate["hub_name"].value_counts().head(5).index.tolist() if "hub_name" in zero_rate.columns else [],
                })

        # 4. CPO-driven
        if self.cpo_analytics is not None:
            try:
                cands = self.cpo_analytics.get_optimization_candidates(min_orders=50, top_n=10)
                if cands is not None and len(cands) > 0:
                    monthly = cands["potential_saving"].sum() if "potential_saving" in cands.columns else 0
                    opportunities.insert(0, {
                        "type": "cpo_optimization", "priority": "critical",
                        "title": f"{len(cands)} hubs with excess CPO",
                        "detail": f"Monthly savings: {monthly:,.0f}. Annual: {monthly * 12:,.0f}",
                        "savings_estimate": f"{monthly:,.0f}/month",
                        "confidence": 0.85,
                        "hubs": cands["hub"].head(5).tolist() if "hub" in cands.columns else [],
                    })
            except Exception:
                pass

        # 5. High burn hubs (cluster_cpo > 1)
        if self.cpo_analytics is not None:
            try:
                burn_hubs = self.cpo_analytics.get_high_burn_hubs(cpo_threshold=1.0, min_orders=50)
                if burn_hubs is not None and len(burn_hubs) > 0:
                    monthly_burn = burn_hubs["monthly_burn"].sum() if "monthly_burn" in burn_hubs.columns else 0
                    opportunities.append({
                        "type": "burn_reduction", "priority": "critical",
                        "title": f"{len(burn_hubs)} hubs with Cluster CPO > Rs.1 (high burn)",
                        "detail": f"Polygon expansion could reduce Rs.{monthly_burn:,.0f}/month burn. Annual: Rs.{monthly_burn * 12:,.0f}",
                        "savings_estimate": f"Rs.{monthly_burn:,.0f}/month",
                        "confidence": 0.80,
                        "hubs": burn_hubs["hub"].head(5).tolist() if "hub" in burn_hubs.columns else [],
                    })
            except Exception:
                pass

        # 6. Polygon optimization — only if results already cached (avoid triggering
        #    the expensive full spatial analysis during briefing generation)
        if hasattr(self, "polygon_optimizer") and self.polygon_optimizer is not None:
            try:
                # Check if optimizer already has cached results (from a previous Run)
                cached_summary = getattr(self.polygon_optimizer, '_cached_summary', None)
                if cached_summary is None and hasattr(self.polygon_optimizer, '_cache'):
                    cached_summary = self.polygon_optimizer._cache.get('summary')
                if cached_summary and cached_summary.get("total_monthly_saving", 0) > 0:
                    summary = cached_summary
                    opportunities.insert(0, {
                        "type": "polygon_optimization", "priority": "critical",
                        "title": f"Polygon expansion can save Rs.{summary['total_monthly_saving']:,.0f}/month",
                        "detail": (
                            f"{summary['hubs_with_changes']} hubs need rate adjustments. "
                            f"Annual impact: Rs.{summary['total_annual_saving']:,.0f}. "
                            "Target " + ("MET" if summary.get("target_met") else f"{summary.get('target_pct', 0):.0f}% reached")
                        ),
                        "savings_estimate": f"Rs.{summary['total_monthly_saving']:,.0f}/month",
                        "confidence": summary.get("confidence", 70) / 100,
                        "hubs": [h["hub_name"] for h in summary.get("top_hubs", [])[:5]],
                    })
            except Exception:
                pass

        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        opportunities.sort(key=lambda x: priority_order.get(x["priority"], 99))
        self._cache["cost_opps"] = opportunities
        return opportunities

    # ──────────────────────────────────────────────
    #  HUB PERFORMANCE RANKING
    # ──────────────────────────────────────────────

    def analyze_hub_performance(self) -> dict:
        if "hub_perf" in self._cache:
            return self._cache["hub_perf"]
        if self.cluster_df is None or "hub_name" not in self.cluster_df.columns:
            return {"hubs": [], "summary": {}}

        df = self.cluster_df
        global_avg_rate = df["surge_amount"].mean() if "surge_amount" in df.columns else 0
        hub_perf = []

        for hub_name, grp in df.groupby("hub_name"):
            p = {"hub_name": hub_name, "cluster_count": len(grp)}
            p["unique_pincodes"] = grp["pincode"].nunique() if "pincode" in grp.columns else 0
            if "surge_amount" in grp.columns:
                rates = grp["surge_amount"].dropna()
                p["avg_rate"] = rates.mean()
                p["max_rate"] = rates.max()
                p["rate_std"] = rates.std() if len(rates) > 1 else 0
                p["zero_rate_pct"] = (rates == 0).sum() / max(1, len(rates)) * 100
            else:
                p.update(avg_rate=0, max_rate=0, rate_std=0, zero_rate_pct=0)

            awb_total = sum(cnt for (h, _), cnt in self.awb_counts.items() if str(h) == str(hub_name))
            p["awb_count"] = awb_total
            p["awb_per_cluster"] = awb_total / max(1, p["cluster_count"])

            rate_score = max(0, 100 - (p["avg_rate"] / max(0.01, global_avg_rate) * 50)) if global_avg_rate > 0 else 50
            consistency = max(0, 100 - p["rate_std"] * 20) if p["rate_std"] < 5 else 0
            coverage = min(100, p["unique_pincodes"] * 10)
            volume = min(100, p["awb_per_cluster"] / 100 * 100) if p["awb_per_cluster"] > 0 else 30

            p["efficiency_score"] = max(0, min(100, round(
                rate_score * 0.35 + consistency * 0.25 + coverage * 0.2 + volume * 0.2)))
            hub_perf.append(p)

        hub_perf.sort(key=lambda x: x["efficiency_score"], reverse=True)
        scores = [h["efficiency_score"] for h in hub_perf]
        summary = {
            "total_hubs": len(hub_perf),
            "avg_score": np.mean(scores) if scores else 0,
            "top_hub": hub_perf[0]["hub_name"] if hub_perf else "N/A",
            "bottom_hub": hub_perf[-1]["hub_name"] if hub_perf else "N/A",
            "above_80": sum(1 for s in scores if s >= 80),
            "below_40": sum(1 for s in scores if s < 40),
        }
        result = {"hubs": hub_perf, "summary": summary}
        self._cache["hub_perf"] = result
        return result

    # ──────────────────────────────────────────────
    #  MORNING BRIEFING
    # ──────────────────────────────────────────────

    def generate_briefing(self) -> dict:
        if "briefing" in self._cache:
            return self._cache["briefing"]

        hour = datetime.now().hour
        greeting = (
            "Good morning, sir. Your logistics intelligence briefing is ready." if hour < 12
            else "Good afternoon, sir. I've completed my analysis of the latest data." if hour < 17
            else "Good evening, sir. Here's your operations summary.")

        briefing = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "greeting": greeting,
            "summary": {},
            "key_metrics": [],
            "alerts": [],
            "top_actions": [],
            "insights": [],
        }

        if self.cluster_df is not None and len(self.cluster_df) > 0:
            df = self.cluster_df
            total_c = len(df)
            total_h = df["hub_name"].nunique() if "hub_name" in df.columns else 0
            total_p = df["pincode"].nunique() if "pincode" in df.columns else 0
            avg_r = df["surge_amount"].mean() if "surge_amount" in df.columns else 0
            total_awb = sum(self.awb_counts.values()) if self.awb_counts else 0

            briefing["summary"] = {
                "clusters": total_c, "hubs": total_h, "pincodes": total_p,
                "avg_rate": round(avg_r, 2), "total_awb": total_awb,
            }
            briefing["key_metrics"] = [
                {"label": "Network Size", "value": f"{total_h:,} hubs / {total_c:,} clusters", "icon": "hub"},
                {"label": "Coverage", "value": f"{total_p:,} pincodes", "icon": "map"},
                {"label": "Avg Surge Rate", "value": f"{avg_r:.2f}", "icon": "payments"},
                {"label": "Shipments", "value": f"{total_awb:,}" if total_awb else "Not loaded", "icon": "local_shipping"},
            ]

        for a in self.detect_anomalies()[:5]:
            briefing["alerts"].append({"severity": a["severity"], "title": a["title"], "action": a["action"]})

        for opp in self.analyze_cost_opportunities()[:4]:
            briefing["top_actions"].append({
                "priority": opp["priority"], "title": opp["title"],
                "savings": opp.get("savings_estimate", ""), "confidence": opp.get("confidence", 0),
            })

        briefing["insights"] = self._generate_insights()
        self._cache["briefing"] = briefing
        return briefing

    def _generate_insights(self) -> list:
        insights = []
        if self.cluster_df is None or len(self.cluster_df) == 0:
            return insights
        df = self.cluster_df

        if "surge_amount" in df.columns:
            rates = df["surge_amount"].dropna()
            if len(rates) > 0:
                pct_zero = (rates == 0).sum() / len(rates) * 100
                if pct_zero > 30:
                    insights.append(
                        f"{pct_zero:.0f}% of clusters at zero surge rate — untapped revenue potential. "
                        f"Even a modest {rates[rates > 0].quantile(0.25):.2f} would improve margins.")
                pct_high = (rates > rates.quantile(0.75)).sum() / len(rates) * 100
                if pct_high > 30:
                    insights.append(
                        f"{pct_high:.0f}% of clusters in top rate quartile (>{rates.quantile(0.75):.2f}). "
                        f"Heavy concentration suggests room for rate optimization.")

        if "hub_name" in df.columns:
            sizes = df["hub_name"].value_counts()
            if len(sizes) > 2:
                top3 = sizes.head(3).sum() / len(df) * 100
                if top3 > 20:
                    insights.append(
                        f"Top 3 hubs ({', '.join(sizes.head(3).index)}) hold {top3:.0f}% of clusters — "
                        f"concentration risk.")

        if self.awb_counts:
            hub_awb = {}
            for (h, _), cnt in self.awb_counts.items():
                hub_awb[h] = hub_awb.get(h, 0) + cnt
            if hub_awb:
                top_h = max(hub_awb, key=hub_awb.get)
                total = sum(hub_awb.values())
                insights.append(
                    f"Highest volume: {top_h} with {hub_awb[top_h]:,} shipments "
                    f"({hub_awb[top_h] * 100 / total:.1f}% of total).")
        return insights

    # ──────────────────────────────────────────────
    #  QUERY ENGINE (Rule-Based — works without LLM)
    # ──────────────────────────────────────────────

    def answer_query(self, query: str) -> dict:
        """Answer natural language questions. No LLM required — pure data analysis."""
        q = query.lower().strip()

        if "expensive" in q and "hub" in q:
            return self._q_expensive_hubs()
        if ("merge" in q or "consolidat" in q) and "cluster" in q:
            return self._q_merge_candidates()
        if "reduce" in q and ("payout" in q or "cost" in q or "rate" in q):
            return self._q_reduce_payout()
        if "slow" in q or "lag" in q or "performance" in q or "loading" in q:
            return self._q_performance()
        if "optimize" in q and "today" in q:
            return self._q_optimize_today()
        if "anomal" in q or "unusual" in q or "outlier" in q:
            return self._q_anomalies()
        if "health" in q or "status" in q or "diagnostic" in q:
            return self._q_performance()
        if "burn" in q or ("cpo" in q and ("high" in q or "above" in q or "> 1" in q or "threshold" in q)):
            return self._q_high_burn_hubs()
        if "exception" in q or ("critical" in q and ("rate" in q or "polygon" in q)):
            return self._q_exception_analysis()
        if "custom" in q and ("radius" in q or "radii" in q):
            return self._q_custom_radius_analysis()
        if "sop" in q or "compliance" in q or "complian" in q:
            return self._q_sop_compliance()
        if "spatial" in q or ("distance" in q and ("polygon" in q or "hub" in q)):
            return self._q_spatial_detail()
        if "polygon" in q or "radius" in q or "band" in q or ("optim" in q and ("polygon" in q or "cluster" in q)):
            return self._q_polygon_optimization()
        if "before" in q and "after" in q:
            return self._q_before_after()
        if "20" in q and ("lakh" in q or "l " in q or "lac" in q) and "save" in q:
            return self._q_savings_target()
        if "saving" in q or "save" in q:
            return self._q_reduce_payout()
        if "how many" in q or "count" in q or "total" in q:
            return self._q_counts()
        if "hub" in q and ("best" in q or "top" in q or "perform" in q):
            return self._q_top_hubs()
        if "hub" in q and ("worst" in q or "bottom" in q or "under" in q):
            return self._q_worst_hubs()
        if "brief" in q or "summary" in q or "overview" in q:
            return self._q_summary()
        if "recommend" in q or "suggest" in q or "action" in q or "what should" in q:
            return self._q_optimize_today()
        if "why" in q and "hub" in q:
            return self._q_why_hub(q)

        return {"text": (
            "I can help you with:\n\n"
            "**Spatial Analysis** — 'Analyze polygons', 'Spatial distance analysis'\n"
            "**SOP Compliance** — 'Check SOP compliance', 'Which polygons are overcharged?'\n"
            "**Exception Rates** — 'Analyze exception rates', 'Which rates are criticality-based?'\n"
            "**Custom Radii** — 'Analyze custom radius polygons', 'Which hubs use non-standard radii?'\n"
            "**Cost Analysis** — 'Why is this hub expensive?', 'Where can I reduce payout?'\n"
            "**Polygon Optimization** — 'Optimize polygons', 'Suggest radius changes'\n"
            "**Burn Analysis** — 'Show high burn hubs', 'CPO above 1'\n"
            "**Before/After** — 'Show before after comparison'\n"
            "**Cluster Optimization** — 'Which clusters should I merge?'\n"
            "**Performance** — 'Top performing hubs', 'Underperforming hubs'\n"
            "**Diagnostics** — 'Run health check', 'Show anomalies'\n"
            "**Planning** — 'What should I optimize today?', 'Show savings', 'Save 20 lakh'\n"
            "**Data** — 'How many clusters?', 'Show summary'\n\n"
            "I analyze actual polygon geometry, haversine distances, AWB landing density, exception rates, "
            "and custom radii. 20 years of geospatial analytics at your service, sir."
        ), "data": None}

    def _q_expensive_hubs(self):
        if self.cluster_df is None or "surge_amount" not in self.cluster_df.columns:
            return {"text": "No cluster data available for cost analysis.", "data": None}
        stats = self.cluster_df.groupby("hub_name").agg(
            avg_rate=("surge_amount", "mean"), max_rate=("surge_amount", "max"),
            clusters=("surge_amount", "count"),
        ).sort_values("avg_rate", ascending=False).head(10).reset_index()
        med = self.cluster_df.groupby("hub_name")["surge_amount"].mean().median()
        text = "**Most Expensive Hubs** by average surge rate:\n\n"
        for _, r in stats.iterrows():
            text += f"- **{r['hub_name']}**: avg {r['avg_rate']:.2f}, max {r['max_rate']:.2f}, {r['clusters']:.0f} clusters\n"
        text += f"\n*Network median: {med:.2f}. Hubs above this are candidates for rate review.*"
        return {"text": text, "data": stats.to_dict("records")}

    def _q_merge_candidates(self):
        if self.cluster_df is None:
            return {"text": "No data loaded.", "data": None}
        df = self.cluster_df
        grp = df.groupby(["hub_name", "pincode"]).size().reset_index(name="n")
        cands = grp[grp["n"] >= 4].sort_values("n", ascending=False).head(10)
        if len(cands) == 0:
            return {"text": "No merge candidates — all pincodes have reasonable cluster counts.", "data": None}
        text = "**Cluster Merge Candidates** (pincodes with 4+ clusters):\n\n"
        for _, r in cands.iterrows():
            text += f"- **{r['hub_name']}** / Pin {r['pincode']}: {r['n']} clusters\n"
        text += "\n*Merging reduces overhead and simplifies rate structures.*"
        return {"text": text, "data": cands.to_dict("records")}

    def _q_reduce_payout(self):
        opps = self.analyze_cost_opportunities()
        if not opps:
            return {"text": "No specific payout reduction opportunities identified.", "data": None}
        text = "**Payout Reduction Opportunities:**\n\n"
        for i, o in enumerate(opps[:5], 1):
            text += f"{i}. **[{o['priority'].upper()}]** {o['title']}\n   Savings: {o['savings_estimate']}\n"
            if o.get("hubs"):
                text += f"   Top hubs: {', '.join(o['hubs'][:3])}\n"
            text += "\n"
        return {"text": text, "data": opps[:5]}

    def _q_performance(self):
        h = self.analyze_health()
        text = f"**System Health: {h['score']}/{h['max_score']} (Grade {h['grade']})**\n\n"
        if h["critical"]:
            text += "Critical:\n" + "".join(f"- {c}\n" for c in h["critical"]) + "\n"
        if h["warnings"]:
            text += "Warnings:\n" + "".join(f"- {w}\n" for w in h["warnings"]) + "\n"
        if h["checks"]:
            text += "OK:\n" + "".join(f"- {c['name']}: {c['detail']}\n" for c in h["checks"])
        return {"text": text, "data": h}

    def _q_optimize_today(self):
        b = self.generate_briefing()
        text = f"**Today's Priorities** ({b['timestamp']}):\n\n"
        if b["top_actions"]:
            for i, a in enumerate(b["top_actions"], 1):
                conf = f" ({a['confidence'] * 100:.0f}% confidence)" if a.get("confidence") else ""
                text += f"{i}. **[{a['priority'].upper()}]** {a['title']}{conf}\n"
                if a.get("savings"):
                    text += f"   Impact: {a['savings']}\n"
                text += "\n"
        else:
            text += "All systems nominal. No high-priority actions at this time.\n"
        if b["insights"]:
            text += "**Insights:**\n" + "".join(f"- {ins}\n" for ins in b["insights"][:3])
        return {"text": text, "data": b["top_actions"]}

    def _q_anomalies(self):
        anoms = self.detect_anomalies()
        if not anoms:
            return {"text": "No anomalies detected. All parameters within normal ranges.", "data": None}
        text = f"**Anomaly Report** ({len(anoms)} detected):\n\n"
        for i, a in enumerate(anoms, 1):
            text += f"{i}. **[{a['severity'].upper()}]** {a['title']}\n   {a['detail']}\n   Action: {a['action']}\n\n"
        return {"text": text, "data": anoms}

    def _q_counts(self):
        if self.cluster_df is None:
            return {"text": "No data loaded.", "data": None}
        df = self.cluster_df
        text = "**Network Statistics:**\n\n"
        text += f"- Clusters: **{len(df):,}**\n"
        if "hub_name" in df.columns:
            text += f"- Hubs: **{df['hub_name'].nunique():,}**\n"
        if "pincode" in df.columns:
            text += f"- Pincodes: **{df['pincode'].nunique():,}**\n"
        if "surge_amount" in df.columns:
            text += f"- Avg Rate: **{df['surge_amount'].mean():.2f}**\n"
            text += f"- Range: **{df['surge_amount'].min():.2f}** to **{df['surge_amount'].max():.2f}**\n"
        if self.awb_counts:
            text += f"- Shipments: **{sum(self.awb_counts.values()):,}**\n"
        return {"text": text, "data": None}

    def _q_top_hubs(self):
        perf = self.analyze_hub_performance()
        if not perf["hubs"]:
            return {"text": "No hub data available.", "data": None}
        top = perf["hubs"][:10]
        text = "**Top Performing Hubs:**\n\n"
        for i, h in enumerate(top, 1):
            text += f"{i}. **{h['hub_name']}** — Score: {h['efficiency_score']}/100, {h['cluster_count']} clusters, avg rate {h['avg_rate']:.2f}\n"
        return {"text": text, "data": top}

    def _q_worst_hubs(self):
        perf = self.analyze_hub_performance()
        if not perf["hubs"]:
            return {"text": "No hub data available.", "data": None}
        bottom = list(reversed(perf["hubs"][-10:]))
        text = "**Underperforming Hubs:**\n\n"
        for i, h in enumerate(bottom, 1):
            text += f"{i}. **{h['hub_name']}** — Score: {h['efficiency_score']}/100, avg rate {h['avg_rate']:.2f}\n"
        text += "\n*These hubs may benefit from cluster restructuring or rate adjustments.*"
        return {"text": text, "data": bottom}

    def _q_summary(self):
        b = self.generate_briefing()
        s = b["summary"]
        text = f"**{b['greeting']}**\n\n"
        if s:
            text += (f"Network: **{s.get('hubs', 0):,}** hubs, **{s.get('clusters', 0):,}** clusters, "
                     f"**{s.get('pincodes', 0):,}** pincodes. Avg rate: **{s.get('avg_rate', 0):.2f}**.\n")
            if s.get("total_awb"):
                text += f"Tracking **{s['total_awb']:,}** shipments.\n"
        if b["alerts"]:
            text += f"\n{len(b['alerts'])} alerts require attention. "
        if b["top_actions"]:
            text += f"{len(b['top_actions'])} optimization actions identified."
        return {"text": text, "data": b}

    def _q_why_hub(self, q):
        if self.cluster_df is None:
            return {"text": "No data loaded.", "data": None}
        df = self.cluster_df
        hubs = df["hub_name"].unique() if "hub_name" in df.columns else []
        found = next((h for h in hubs if h.lower() in q), None)
        if not found:
            return self._q_expensive_hubs()

        grp = df[df["hub_name"] == found]
        global_avg = df["surge_amount"].mean() if "surge_amount" in df.columns else 0
        hub_avg = grp["surge_amount"].mean() if "surge_amount" in grp.columns else 0
        text = f"**Analysis: {found}**\n\n"
        text += f"- Clusters: {len(grp)}\n"
        text += f"- Avg rate: {hub_avg:.2f} (network avg: {global_avg:.2f})\n"
        text += f"- Max rate: {grp['surge_amount'].max():.2f}\n" if "surge_amount" in grp.columns else ""
        text += f"- Pincodes: {grp['pincode'].nunique()}\n" if "pincode" in grp.columns else ""
        if hub_avg > global_avg * 1.3:
            text += f"\n*{((hub_avg / global_avg) - 1) * 100:.0f}% above network average — geographic spread or premium demand zone.*"
        elif hub_avg < global_avg * 0.7:
            text += f"\n*{(1 - hub_avg / global_avg) * 100:.0f}% below average — efficient or centrally located.*"
        else:
            text += "\n*Within normal range.*"
        return {"text": text, "data": grp.describe().to_dict()}

    def _q_high_burn_hubs(self):
        if self.cpo_analytics is None or not self.cpo_analytics.is_loaded:
            return {"text": "CPO data not loaded. Upload the CPO Excel to analyze burn, sir.", "data": None}
        burn_hubs = self.cpo_analytics.get_high_burn_hubs(cpo_threshold=1.0, min_orders=50)
        if len(burn_hubs) == 0:
            return {"text": "No hubs with Cluster CPO > Rs.1 — the network is operating efficiently, sir.", "data": None}
        summary = self.cpo_analytics.get_burn_summary(cpo_threshold=1.0, min_orders=50)
        text = "**High Burn Hubs Analysis** (Cluster CPO > Rs.1)\n\n"
        text += f"- **{summary['hub_count']}** hubs are burning excess cluster payout\n"
        text += f"- **Monthly burn:** Rs.{summary['total_monthly_burn']:,.0f}\n"
        text += f"- **Annual burn:** Rs.{summary['total_annual_burn']:,.0f}\n"
        text += f"- **Avg Cluster CPO:** Rs.{summary['avg_cluster_cpo']:.2f}\n"
        text += f"- **Max Cluster CPO:** Rs.{summary['max_cluster_cpo']:.2f}\n\n"
        text += "**Top 10 Burn Hubs:**\n\n"
        for _, row in burn_hubs.head(10).iterrows():
            text += f"- **{row['hub']}**: CPO Rs.{row['cluster_cpo']:.2f}, Burn Rs.{row['monthly_burn']:,.0f}/mo, {int(row['LM_Orders']):,} orders\n"
        text += "\n**Recommendation:** Expand polygon boundaries at these hubs to reduce per-order cluster payout, sir."
        return {"text": text, "data": burn_hubs.head(20).to_dict(orient="records")}

    def _q_polygon_optimization(self):
        if not hasattr(self, "polygon_optimizer") or self.polygon_optimizer is None:
            return {"text": "Polygon optimizer not initialized. Load cluster data and AWB data first, sir.", "data": None}
        try:
            summary = self.polygon_optimizer.get_optimization_summary()
            suggestions = self.polygon_optimizer.suggest_optimal_radius()
        except Exception as e:
            return {"text": f"Error running polygon analysis: {e}", "data": None}
        if summary["hubs_with_changes"] == 0:
            return {"text": "All hubs are already optimally configured — no polygon changes needed, sir.", "data": None}
        text = "**Spatial Polygon Optimization Analysis**\n\n"
        text += f"- **{summary['total_hubs_analyzed']}** hubs analyzed spatially\n"
        text += f"- **{summary.get('total_polygons_analyzed', 0)}** individual polygons scanned\n"
        text += f"- **{summary['hubs_with_changes']}** hubs need rate/polygon adjustments\n"
        text += f"- **Monthly saving potential:** Rs.{summary['total_monthly_saving']:,.0f}\n"
        text += f"- **Annual saving potential:** Rs.{summary['total_annual_saving']:,.0f}\n"
        _tgt_str = "MET" if summary.get("target_met") else f"{summary.get('target_pct', 0):.0f}% reached"
        text += f"- **Target (20L):** {_tgt_str}\n"
        text += f"- **Data source:** {summary.get('data_source', 'Unknown')}\n"
        text += f"- **Confidence:** {summary['confidence']:.0f}%\n\n"

        # SOP compliance overview
        text += "**SOP Compliance:**\n"
        text += f"- Compliant: {summary.get('compliant_polygons', 0)} polygons ({summary.get('sop_compliance_pct', 0):.0f}%)\n"
        text += f"- Non-standard (C2/C4/C6/C8/C10): {summary.get('non_standard_polygons', 0)} polygons\n"
        text += f"- Overcharged: {summary.get('overcharged_polygons', 0)} polygons (rate > SOP for distance)\n"
        text += f"- Undercharged: {summary.get('undercharged_polygons', 0)} polygons\n"
        text += f"- Total monthly burn from overcharging: Rs.{summary.get('total_monthly_burn', 0):,.0f}\n\n"

        # Exception and custom radius analysis
        exc_count = summary.get('exception_rate_polygons', 0)
        cust_count = summary.get('custom_radius_polygons', 0)
        if exc_count > 0 or cust_count > 0:
            text += "**Special Cases Detected:**\n"
            if exc_count > 0:
                text += f"- **{exc_count} exception rate polygons** — rates above SOP likely due to criticality (high demand, difficult terrain). These need manual review before changing.\n"
            if cust_count > 0:
                text += f"- **{cust_count} custom radius polygons** — using non-standard radii (not matching SOP distance bands). Some may be operationally justified.\n"
            text += "\n"

        # Action breakdown
        text += "**Recommended Actions:**\n"
        text += f"- Rate decreases: {summary.get('rate_decrease_actions', 0)} polygons\n"
        text += f"- Radius expansions: {summary.get('radius_expansion_actions', 0)} polygons\n"
        if summary.get('review_exception_actions', 0) > 0:
            text += f"- Exception reviews: {summary.get('review_exception_actions', 0)} polygons (need human verification)\n"
        text += "\n"

        text += "**Top 10 Hubs for Optimization:**\n\n"
        for _, row in suggestions.head(10).iterrows():
            text += (
                f"- **{row['hub_name']}** [{row.get('priority', 'Medium')}]: "
                f"Rs.{row['current_monthly_cost']:,.0f} → Rs.{row['suggested_monthly_cost']:,.0f} "
                f"(save Rs.{row['monthly_saving']:,.0f}/mo, "
                f"{row.get('overcharged_polygons', 0)} overcharged polygons, "
                f"avg {row.get('avg_distance_km', 0):.1f}km)\n"
            )
        text += "\n*Ask 'show before after' for detailed comparison, 'SOP compliance' for distance analysis, sir.*"
        return {"text": text, "data": suggestions.head(20).drop(columns=["changes"], errors="ignore").to_dict(orient="records")}

    def _q_before_after(self):
        if not hasattr(self, "polygon_optimizer") or self.polygon_optimizer is None:
            return {"text": "Polygon optimizer not initialized. Load data first, sir.", "data": None}
        try:
            comparisons = self.polygon_optimizer.generate_before_after()
        except Exception as e:
            return {"text": f"Error generating comparison: {e}", "data": None}
        if not comparisons:
            return {"text": "No optimization changes to compare, sir.", "data": None}
        text = "**Before / After Comparison** (Top 15 Hubs)\n\n"
        for comp in comparisons[:15]:
            b = comp["before"]
            a = comp["after"]
            d = comp["delta"]
            text += f"### {comp['hub_name']} [{comp['priority']}]\n"
            text += f"*{comp.get('overcharged_polygons', 0)} overcharged polygons, "
            text += f"avg distance {comp.get('avg_distance_km', 0):.1f}km, "
            text += f"SOP compliance {comp.get('sop_compliant_pct', 0):.0f}%*\n\n"
            text += f"| Metric | Before | After | Change |\n|---|---|---|---|\n"
            text += f"| Monthly Cost | Rs.{b['monthly_cost']:,.0f} | Rs.{a['monthly_cost']:,.0f} | -Rs.{d['cost_reduction']:,.0f} |\n"
            text += f"| CPO | Rs.{b['cpo']:.2f} | Rs.{a['cpo']:.2f} | -{d['cpo_reduction']:.2f} |\n"
            text += f"| Avg Rate | Rs.{b['avg_rate']:.2f} | Rs.{a['avg_rate']:.2f} | — |\n"
            text += f"| Annual Impact | — | — | Rs.{d['annual_reduction']:,.0f} |\n\n"
            for chg in comp.get("changes", [])[:5]:
                text += f"  - {chg['action']}\n"
            text += "\n"
        total_saving = sum(c["delta"]["cost_reduction"] for c in comparisons)
        text += f"\n**Total Monthly Saving:** Rs.{total_saving:,.0f} | **Annual:** Rs.{total_saving * 12:,.0f}"
        return {"text": text, "data": comparisons[:15]}

    def _q_savings_target(self):
        if not hasattr(self, "polygon_optimizer") or self.polygon_optimizer is None:
            # Fall back to CPO-based analysis
            if self.cpo_analytics is not None and self.cpo_analytics.is_loaded:
                recs = self.cpo_analytics.generate_recommendations(min_orders=50, top_n=30)
                if not recs.empty and "Monthly Saving" in recs.columns:
                    total = recs["Monthly Saving"].sum()
                    text = f"**Roadmap to Rs.20L Monthly Savings**\n\n"
                    text += f"Based on CPO analysis, **Rs.{total:,.0f}/month** is achievable via rate optimization:\n\n"
                    for _, row in recs.head(15).iterrows():
                        text += f"- **{row['Hub']}**: Rs.{row['Monthly Saving']:,.0f}/mo ({row['Action']})\n"
                    pct = total / 2000000 * 100
                    text += f"\n**Progress toward 20L target:** {pct:.0f}% ({'Target met!' if pct >= 100 else f'Gap: Rs.{max(0, 2000000 - total):,.0f}'})"
                    return {"text": text, "data": recs.head(15).to_dict(orient="records")}
            return {"text": "Load CPO data or polygon optimizer to calculate savings roadmap, sir.", "data": None}
        summary = self.polygon_optimizer.get_optimization_summary(target_saving=2000000)
        suggestions = self.polygon_optimizer.suggest_optimal_radius(target_saving=2000000)
        text = f"**Roadmap to Rs.20L Monthly Savings**\n\n"
        text += f"- **Achievable:** Rs.{summary['total_monthly_saving']:,.0f}/month ({summary['target_pct']:.0f}% of target)\n"
        text += f"- **Annual impact:** Rs.{summary['total_annual_saving']:,.0f}\n"
        text += f"- **Hubs to modify:** {summary['hubs_with_changes']}\n"
        text += f"- **AWBs affected:** {summary['total_awb_affected']:,}\n\n"
        text += "**Action Plan (by priority):**\n\n"
        for priority in ["Critical", "High", "Medium"]:
            pf = suggestions[suggestions["priority"] == priority] if not suggestions.empty else pd.DataFrame()
            if pf.empty:
                continue
            text += f"**{priority} Priority ({len(pf)} hubs):**\n"
            for _, row in pf.head(5).iterrows():
                text += f"- **{row['hub_name']}**: Save Rs.{row['monthly_saving']:,.0f}/mo by reducing avg rate from Rs.{row['current_avg_rate']:.2f} to Rs.{row['suggested_avg_rate']:.2f}\n"
            text += "\n"
        if summary["target_met"]:
            text += "**Target of Rs.20L/month is achievable with the above changes, sir.**"
        else:
            gap = 2000000 - summary["total_monthly_saving"]
            text += f"**Gap:** Rs.{gap:,.0f}/month. Consider additional measures (hub consolidation, SOP compliance)."
        return {"text": text, "data": suggestions.head(20).drop(columns=["changes"], errors="ignore").to_dict(orient="records")}

    def _q_sop_compliance(self):
        """SOP compliance analysis — which polygons have rates that don't match their actual distance."""
        if not hasattr(self, "polygon_optimizer") or self.polygon_optimizer is None:
            return {"text": "Polygon optimizer not initialized. Load cluster data first, sir.", "data": None}
        try:
            report = self.polygon_optimizer.get_sop_compliance_report()
            summary = self.polygon_optimizer.get_optimization_summary()
        except Exception as e:
            return {"text": f"Error running SOP analysis: {e}", "data": None}

        text = "**SOP Compliance Analysis**\n\n"
        text += f"I've analyzed the actual haversine distance of every polygon from its hub and compared the charged rate against the SOP.\n\n"
        text += f"- **Total polygons scanned:** {summary.get('total_polygons_analyzed', 0)}\n"
        text += f"- **SOP Compliant:** {summary.get('compliant_polygons', 0)} ({summary.get('sop_compliance_pct', 0):.0f}%)\n"
        text += f"- **Non-standard (C2/C4/C6/C8/C10):** {summary.get('non_standard_polygons', 0)}\n"
        text += f"- **Overcharged (rate > SOP):** {summary.get('overcharged_polygons', 0)}\n"
        text += f"- **Undercharged (rate < SOP):** {summary.get('undercharged_polygons', 0)}\n"
        text += f"- **Monthly burn from overcharging:** Rs.{summary.get('total_monthly_burn', 0):,.0f}\n\n"

        exc = summary.get('exception_rate_polygons', 0)
        cust = summary.get('custom_radius_polygons', 0)
        if exc > 0 or cust > 0:
            text += "**Special Cases (as a senior analyst, I flag these for your review):**\n"
            if exc > 0:
                text += f"- **{exc} exception rate polygons** — above-SOP rates that appear intentional (criticality-based). I recommend reviewing these with hub operations before changing.\n"
            if cust > 0:
                text += f"- **{cust} custom radius polygons** — non-standard radii (3km, 4.3km, 4.5km, etc.). Some may be operationally justified.\n"
            text += "\n"

        text += report
        text += "\n\n*Overcharged polygons are the primary savings lever. Exception rates need human verification. "
        text += "Non-standard rates (C2/C4 etc.) are acceptable but can be standardized for consistency, sir.*"
        return {"text": text, "data": summary}

    def _q_spatial_detail(self):
        """Detailed spatial analysis — per-polygon distances, rates, AWB density."""
        if not hasattr(self, "polygon_optimizer") or self.polygon_optimizer is None:
            return {"text": "Polygon optimizer not initialized. Load cluster data first, sir.", "data": None}
        try:
            report = self.polygon_optimizer.get_polygon_detail_report(top_n=30)
        except Exception as e:
            return {"text": f"Error running spatial analysis: {e}", "data": None}

        text = "**Detailed Spatial Polygon Analysis**\n\n"
        text += "I've calculated the actual haversine distance from each hub to every polygon centroid, "
        text += "matched AWB shipments to polygons via point-in-polygon, and computed burn per polygon.\n\n"
        text += report
        text += "\n\n*For hub-specific analysis, ask 'analyze polygon for [hub name]', sir.*"
        return {"text": text, "data": None}

    def _q_exception_analysis(self):
        """Analyze exception rate polygons — rates above SOP due to criticality."""
        if not hasattr(self, "polygon_optimizer") or self.polygon_optimizer is None:
            return {"text": "Polygon optimizer not initialized. Load cluster data first, sir.", "data": None}
        try:
            full = self.polygon_optimizer._build_full_polygon_analysis()
        except Exception as e:
            return {"text": f"Error running analysis: {e}", "data": None}

        if full.empty or "is_exception_rate" not in full.columns:
            return {"text": "No exception rate data available. Run spatial polygon analysis first, sir.", "data": None}

        exceptions = full[full["is_exception_rate"] == True]
        if len(exceptions) == 0:
            return {"text": "No exception rate polygons detected. All above-SOP rates appear to be standard overcharges rather than criticality-based exceptions, sir.", "data": None}

        text = "**Exception Rate Analysis** (Senior Analyst Assessment)\n\n"
        text += f"I've identified **{len(exceptions)} polygons** where rates are above SOP but appear to be intentional exceptions "
        text += f"(criticality-based, not accidental overcharges).\n\n"
        text += f"**These require your manual review before changing.**\n\n"

        text += "| Hub | Polygon | Distance | Rate | SOP Rate | Gap | AWBs | Monthly Burn | Reason |\n"
        text += "|-----|---------|----------|------|----------|-----|------|-------------|--------|\n"

        total_burn = 0
        for _, row in exceptions.sort_values("monthly_burn", ascending=False).head(20).iterrows():
            burn = row["monthly_burn"]
            total_burn += burn
            text += (
                f"| {row['hub_name']} | {row['cluster_code']} | {row['centroid_distance_km']:.1f}km | "
                f"Rs.{row['actual_rate']:.1f} | Rs.{row['sop_rate']:.1f} | +Rs.{row['rate_gap']:.1f} | "
                f"{row['awb_count']:,} | Rs.{burn:,.0f} | {row.get('exception_reason', 'Unknown')} |\n"
            )

        text += f"\n**Total monthly burn from exception polygons:** Rs.{total_burn:,.0f}\n"
        text += f"\nSir, as a senior analyst with 20 years of experience, I recommend reviewing each exception individually. "
        text += f"Some may be justified (critical demand zones, difficult terrain), while others may have been set as exceptions "
        text += f"but no longer need elevated rates. Each polygon should be evaluated against current operational data."

        return {"text": text, "data": exceptions.head(20).drop(columns=["geometry"], errors="ignore").to_dict(orient="records") if "geometry" in exceptions.columns else exceptions.head(20).to_dict(orient="records")}

    def _q_custom_radius_analysis(self):
        """Analyze polygons with custom (non-standard) radii."""
        if not hasattr(self, "polygon_optimizer") or self.polygon_optimizer is None:
            return {"text": "Polygon optimizer not initialized. Load cluster data first, sir.", "data": None}
        try:
            full = self.polygon_optimizer._build_full_polygon_analysis()
        except Exception as e:
            return {"text": f"Error running analysis: {e}", "data": None}

        if full.empty or "is_custom_radius" not in full.columns:
            return {"text": "No custom radius data available. Run spatial polygon analysis first, sir.", "data": None}

        custom = full[full["is_custom_radius"] == True]
        if len(custom) == 0:
            return {"text": "All polygons use standard SOP radius boundaries. No custom radii detected, sir.", "data": None}

        text = "**Custom Radius Analysis** (Senior Analyst Assessment)\n\n"
        text += f"I've detected **{len(custom)} polygons** with non-standard radii that don't align with SOP distance bands.\n\n"
        text += "Standard SOP ring boundaries are at: 4, 12, 22, 30, 40, 48, 52, 56, 60, 64, 68, 72, 76, 80 km.\n\n"

        text += "| Hub | Polygon | Ring Width | Max Dist | Nearest SOP | Deviation | Rate | Compliance |\n"
        text += "|-----|---------|-----------|----------|-------------|-----------|------|------------|\n"

        for _, row in custom.sort_values("radius_deviation_km", ascending=False).head(20).iterrows():
            text += (
                f"| {row['hub_name']} | {row['cluster_code']} | {row.get('polygon_radius_km', 0):.1f}km | "
                f"{row['max_distance_km']:.1f}km | {row.get('nearest_sop_boundary_km', 0)}km | "
                f"{row.get('radius_deviation_km', 0):.1f}km | Rs.{row['actual_rate']:.1f} | "
                f"{row['compliance']} |\n"
            )

        text += f"\nSir, custom radii (3km, 4.3km, 4.5km, etc.) are common when hub operations need tighter or wider "
        text += f"coverage than standard SOP. I recommend verifying with each hub manager whether the custom radius "
        text += f"is still needed, or if it can be standardized to reduce operational complexity."

        return {"text": text, "data": None}
