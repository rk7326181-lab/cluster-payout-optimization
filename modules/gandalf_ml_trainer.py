"""
G.A.N.D.A.L.F. ML Trainer
===========================
Geospatial Anomaly Detection and Location Framework — Machine Learning Layer.

Trains and runs multiple anomaly detection models on hub-level geospatial features:

  Supervised  : XGBoost Classifier, LightGBM, Random Forest
  Unsupervised: Isolation Forest, Local Outlier Factor (LOF)
  Ensemble    : Majority-vote across all models

Usage (standalone):
    from modules.gandalf_ml_trainer import GandalfMLTrainer
    trainer = GandalfMLTrainer()
    trainer.fit(records)          # records = output of detect_hub_centroid_anomalies()
    report   = trainer.evaluate()
    preds    = trainer.predict(new_records)

Usage (Streamlit):
    from modules.gandalf_ml_trainer import render_ml_training_tab
    render_ml_training_tab(records)
"""

import math
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

# ── Optional ML deps — installed on demand ──────────────────────────────────
def _try_import():
    mods = {}
    try:
        from sklearn.ensemble import RandomForestClassifier, IsolationForest
        from sklearn.neighbors import LocalOutlierFactor
        from sklearn.preprocessing import LabelEncoder
        from sklearn.model_selection import StratifiedKFold, cross_val_score
        from sklearn.metrics import classification_report, confusion_matrix
        from sklearn.pipeline import Pipeline
        from sklearn.impute import SimpleImputer
        from sklearn.preprocessing import StandardScaler
        mods["sklearn"] = True
        mods["RF"]  = RandomForestClassifier
        mods["IF"]  = IsolationForest
        mods["LOF"] = LocalOutlierFactor
        mods["LE"]  = LabelEncoder
        mods["SKF"] = StratifiedKFold
        mods["CVS"] = cross_val_score
        mods["CR"]  = classification_report
        mods["CM"]  = confusion_matrix
        mods["Pipe"]= Pipeline
        mods["SI"]  = SimpleImputer
        mods["SS"]  = StandardScaler
    except ImportError:
        mods["sklearn"] = False

    try:
        import xgboost as xgb
        mods["XGB"] = xgb.XGBClassifier
        mods["xgboost"] = True
    except ImportError:
        mods["xgboost"] = False

    try:
        import lightgbm as lgb
        mods["LGB"] = lgb.LGBMClassifier
        mods["lightgbm"] = True
    except ImportError:
        mods["lightgbm"] = False

    return mods

_MODS = _try_import()


# ── Feature definition ───────────────────────────────────────────────────────
ML_FEATURES = [
    # Centroid displacement
    "hub_to_weighted_centroid_km",
    "hub_to_rs0_centroid_km",
    # Containment (encoded as 0/1)
    "hub_in_rs0_polygon",
    "hub_in_any_polygon",
    # Boundary distances
    "bnd_min_km",
    "bnd_max_km",
    "bnd_mean_km",
    "bnd_std_km",
    "bnd_skewness",
    # Polygon shape
    "total_area_km2",
    "avg_compactness",
    "coverage_density",
    "radius_variance",
    # Ring structure
    "dir_asymmetry_deg",
    "ring_monotonicity",
    "max_poly_centroid_dist_km",
    "min_poly_centroid_dist_km",
    "mean_poly_centroid_dist_km",
    "radius_overshoot_km",
    # Metadata
    "n_polygons",
    "max_tier",
]

LABEL_MAP    = {"Correct": 0, "Warning": 1, "Critical Anomaly": 2}
LABEL_NAMES  = ["Correct", "Warning", "Critical Anomaly"]
INV_LABEL    = {v: k for k, v in LABEL_MAP.items()}


def _build_feature_matrix(records):
    """
    Convert a list of hub anomaly dicts (from detect_hub_centroid_anomalies)
    into a (X, y, hub_names, feature_cols) tuple ready for sklearn.

    Rows with label -1 (Data Error) are excluded.
    Missing values are left as NaN — imputed inside the pipeline.
    """
    df = pd.DataFrame(records)
    df["label"] = df["status"].map(LABEL_MAP)
    df = df[df["label"].notna()].copy()
    df["label"] = df["label"].astype(int)

    # Boolean → int
    for col in ("hub_in_rs0_polygon", "hub_in_any_polygon"):
        if col in df.columns:
            df[col] = df[col].astype(int)

    feature_cols = [c for c in ML_FEATURES if c in df.columns]
    X = df[feature_cols].values.astype(float)
    y = df["label"].values
    hub_names = df["hub_name"].tolist() if "hub_name" in df.columns else [str(i) for i in range(len(df))]
    return X, y, hub_names, feature_cols


def _make_pipeline(estimator):
    """Wrap estimator in impute + scale + model pipeline."""
    if not _MODS.get("sklearn"):
        raise ImportError("scikit-learn is required. pip install scikit-learn")
    SI, SS, Pipe = _MODS["SI"], _MODS["SS"], _MODS["Pipe"]
    return Pipe([
        ("imputer", SI(strategy="median")),
        ("scaler",  SS()),
        ("model",   estimator),
    ])


# ── Main trainer class ───────────────────────────────────────────────────────
class GandalfMLTrainer:
    """
    Train and run G.A.N.D.A.L.F. anomaly detection models.

    Supported models:
      - RandomForest   (supervised, multi-class)
      - XGBoost        (supervised, multi-class)  — requires xgboost
      - LightGBM       (supervised, multi-class)  — requires lightgbm
      - IsolationForest (unsupervised, binary anomaly)
      - LOF             (unsupervised, binary anomaly)
    """

    def __init__(self):
        self.models_   = {}   # name -> fitted pipeline
        self.scores_   = {}   # name -> cross-val accuracy
        self.feature_cols_ = []
        self.X_ = self.y_ = self.hub_names_ = None
        self._fitted = False

    # ── Fit ───────────────────────────────────────────────────────────────────
    def fit(self, records, cv_folds=3):
        """
        Fit all available supervised models on hub anomaly records.

        Parameters
        ----------
        records : list[dict]   — output of detect_hub_centroid_anomalies()
        cv_folds : int         — stratified k-fold for cross-validation
        """
        if not _MODS.get("sklearn"):
            raise ImportError("scikit-learn required: pip install scikit-learn")

        X, y, hub_names, feature_cols = _build_feature_matrix(records)
        self.X_ = X; self.y_ = y
        self.hub_names_ = hub_names
        self.feature_cols_ = feature_cols

        RF, SKF, CVS = _MODS["RF"], _MODS["SKF"], _MODS["CVS"]
        skf = SKF(n_splits=cv_folds, shuffle=True, random_state=42)

        # ── Random Forest ──────────────────────────────────────────────────
        rf_pipe = _make_pipeline(RF(n_estimators=300, max_depth=8,
                                    class_weight="balanced", random_state=42, n_jobs=-1))
        cv_rf = CVS(rf_pipe, X, y, cv=skf, scoring="accuracy").mean()
        rf_pipe.fit(X, y)
        self.models_["RandomForest"] = rf_pipe
        self.scores_["RandomForest"] = round(float(cv_rf), 4)

        # ── XGBoost ────────────────────────────────────────────────────────
        if _MODS.get("xgboost"):
            xgb_pipe = _make_pipeline(_MODS["XGB"](
                n_estimators=300, max_depth=6, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.8,
                use_label_encoder=False, eval_metric="mlogloss",
                random_state=42, n_jobs=-1,
            ))
            cv_xgb = CVS(xgb_pipe, X, y, cv=skf, scoring="accuracy").mean()
            xgb_pipe.fit(X, y)
            self.models_["XGBoost"] = xgb_pipe
            self.scores_["XGBoost"] = round(float(cv_xgb), 4)

        # ── LightGBM ───────────────────────────────────────────────────────
        if _MODS.get("lightgbm"):
            lgb_pipe = _make_pipeline(_MODS["LGB"](
                n_estimators=300, num_leaves=31, learning_rate=0.05,
                class_weight="balanced", random_state=42, n_jobs=-1,
                verbose=-1,
            ))
            cv_lgb = CVS(lgb_pipe, X, y, cv=skf, scoring="accuracy").mean()
            lgb_pipe.fit(X, y)
            self.models_["LightGBM"] = lgb_pipe
            self.scores_["LightGBM"] = round(float(cv_lgb), 4)

        self._fitted = True
        return self

    def fit_unsupervised(self, records, contamination=0.25):
        """
        Fit unsupervised models (IsolationForest + LOF) on hub features.
        contamination: expected fraction of anomalous hubs (default 25%).
        """
        if not _MODS.get("sklearn"):
            raise ImportError("scikit-learn required")

        X, _, hub_names, feature_cols = _build_feature_matrix(records)
        IF, LOF, SI, SS = _MODS["IF"], _MODS["LOF"], _MODS["SI"], _MODS["SS"]

        # Impute + scale
        imp  = SI(strategy="median"); X_imp = imp.fit_transform(X)
        scl  = SS(); X_sc = scl.fit_transform(X_imp)

        # Isolation Forest
        isofor = IF(contamination=contamination, random_state=42, n_jobs=-1)
        isofor.fit(X_sc)
        self.models_["IsolationForest"] = (imp, scl, isofor)

        # LOF (novelty=False → fit-predict mode)
        lof = LOF(n_neighbors=20, contamination=contamination)
        lof.fit(X_sc)
        self.models_["LOF"] = (imp, scl, lof)

        self._if_X_sc  = X_sc
        self._if_hubs  = hub_names
        self.feature_cols_ = feature_cols
        return self

    # ── Predict ───────────────────────────────────────────────────────────────
    def predict(self, records, model_name="RandomForest"):
        """
        Predict anomaly labels for new hub records.
        Returns list of (hub_name, predicted_status, probability_dict).
        """
        if model_name not in self.models_:
            raise ValueError(f"Model '{model_name}' not fitted. Available: {list(self.models_)}")

        df  = pd.DataFrame(records)
        for col in ("hub_in_rs0_polygon", "hub_in_any_polygon"):
            if col in df.columns:
                df[col] = df[col].astype(int)
        feat_cols = [c for c in self.feature_cols_ if c in df.columns]
        X_new = df[feat_cols].values.astype(float)

        pipe = self.models_[model_name]
        preds = pipe.predict(X_new)
        proba = pipe.predict_proba(X_new) if hasattr(pipe, "predict_proba") else None

        results = []
        for i, (pred, row) in enumerate(zip(preds, df.itertuples())):
            label = INV_LABEL.get(int(pred), "Unknown")
            prob  = {LABEL_NAMES[j]: round(float(p), 3) for j, p in enumerate(proba[i])} if proba is not None else {}
            results.append({
                "hub_name":          getattr(row, "hub_name", str(i)),
                "predicted_status":  label,
                "probabilities":     prob,
                "top_prob":          max(prob.values()) if prob else None,
            })
        return results

    # ── Evaluate ─────────────────────────────────────────────────────────────
    def evaluate(self):
        """Return a summary report dict for all fitted supervised models."""
        if not self._fitted:
            return {"error": "No supervised models fitted yet. Call .fit(records) first."}
        CR = _MODS["CR"]
        report = {"cv_scores": self.scores_, "classification_reports": {}, "feature_importances": {}}

        for name, pipe in self.models_.items():
            if name in ("IsolationForest", "LOF"):
                continue
            y_pred = pipe.predict(self.X_)
            report["classification_reports"][name] = CR(
                self.y_, y_pred, target_names=LABEL_NAMES, output_dict=True, zero_division=0)

            # Feature importances (RF / XGBoost / LightGBM)
            model = pipe.named_steps.get("model")
            if hasattr(model, "feature_importances_"):
                fi = dict(zip(self.feature_cols_, model.feature_importances_))
                report["feature_importances"][name] = sorted(
                    fi.items(), key=lambda x: x[1], reverse=True)

        return report

    # ── Unsupervised predict ──────────────────────────────────────────────────
    def predict_unsupervised(self, records):
        """
        Run IsolationForest and LOF on records.
        Returns DataFrame with hub_name, if_anomaly, lof_anomaly, ensemble_anomaly.
        """
        df = pd.DataFrame(records)
        for col in ("hub_in_rs0_polygon", "hub_in_any_polygon"):
            if col in df.columns:
                df[col] = df[col].astype(int)
        feat_cols = [c for c in self.feature_cols_ if c in df.columns]
        X_new = df[feat_cols].values.astype(float)

        results = pd.DataFrame({"hub_name": df.get("hub_name", pd.Series(range(len(df))))})

        if "IsolationForest" in self.models_:
            imp, scl, isofor = self.models_["IsolationForest"]
            X_imp = imp.transform(X_new); X_sc = scl.transform(X_imp)
            preds = isofor.predict(X_sc)   # -1 = anomaly, 1 = normal
            results["if_anomaly"]  = (preds == -1).astype(int)
            results["if_score"]    = -isofor.score_samples(X_sc)  # higher = more anomalous

        if "LOF" in self.models_:
            imp, scl, lof = self.models_["LOF"]
            X_imp = imp.transform(X_new); X_sc = scl.transform(X_imp)
            preds = lof.predict(X_sc)
            results["lof_anomaly"] = (preds == -1).astype(int)

        # Ensemble: flagged by at least one unsupervised model
        anomaly_cols = [c for c in ("if_anomaly", "lof_anomaly") if c in results.columns]
        if anomaly_cols:
            results["ensemble_anomaly"] = (results[anomaly_cols].sum(axis=1) >= 1).astype(int)

        return results


# ── Streamlit UI ─────────────────────────────────────────────────────────────
def render_ml_training_tab(records):
    """
    Renders the G.A.N.D.A.L.F. ML training section inside a Streamlit tab or expander.
    Call with records = output of detect_hub_centroid_anomalies().
    """
    try:
        import streamlit as st
    except ImportError:
        return

    st.markdown("### 🤖 G.A.N.D.A.L.F. — ML Model Training")
    st.markdown(
        "Train supervised and unsupervised models to automatically classify hubs "
        "as **Correct / Warning / Critical Anomaly** on future datasets."
    )

    if not records:
        st.info("Run the Hub Anomaly Detection scan first to generate training data.")
        return

    df_all = pd.DataFrame(records)
    trainable = df_all[df_all["status"].isin(LABEL_MAP)].copy()
    label_counts = trainable["status"].value_counts()

    st.markdown(f"**Training dataset: {len(trainable):,} hubs**")
    lc1, lc2, lc3 = st.columns(3)
    with lc1: st.metric("Correct",         label_counts.get("Correct", 0))
    with lc2: st.metric("Warning",          label_counts.get("Warning", 0))
    with lc3: st.metric("Critical Anomaly", label_counts.get("Critical Anomaly", 0))

    if not _MODS.get("sklearn"):
        st.error("scikit-learn not installed. Run: `pip install scikit-learn xgboost lightgbm`")
        return

    # Model selection
    available_models = ["Random Forest"]
    if _MODS.get("xgboost"):   available_models.append("XGBoost")
    if _MODS.get("lightgbm"):  available_models.append("LightGBM")
    available_models += ["Isolation Forest (unsupervised)", "LOF (unsupervised)"]

    selected = st.multiselect(
        "Models to train", available_models,
        default=["Random Forest", "Isolation Forest (unsupervised)"],
        key="gandalf_ml_models",
    )
    cv_folds = st.slider("Cross-validation folds (supervised)", 2, 10, 3, key="gandalf_cv_folds")

    if st.button("🚀 Train G.A.N.D.A.L.F.", key="gandalf_train_btn"):
        trainer = GandalfMLTrainer()
        do_sup   = any(m in selected for m in ["Random Forest", "XGBoost", "LightGBM"])
        do_unsup = any("unsupervised" in m for m in selected)

        with st.spinner("Training in progress…"):
            if do_sup:
                trainer.fit(records, cv_folds=cv_folds)
            if do_unsup:
                trainer.fit_unsupervised(records)

        st.session_state["gandalf_trainer"] = trainer
        st.success("Training complete!")

        # ── Cross-val scores ──────────────────────────────────────────────
        if trainer.scores_:
            st.markdown("#### Cross-Validation Accuracy")
            score_rows = [{"Model": k, "CV Accuracy": f"{v*100:.1f}%"}
                          for k, v in trainer.scores_.items()]
            st.table(pd.DataFrame(score_rows))

        # ── Classification reports ────────────────────────────────────────
        report = trainer.evaluate()
        for model_name, cr in report.get("classification_reports", {}).items():
            with st.expander(f"📊 {model_name} — Classification Report", expanded=True):
                cr_df = pd.DataFrame(cr).T.round(3)
                st.dataframe(cr_df, use_container_width=True)

        # ── Feature importances ───────────────────────────────────────────
        for model_name, fi_list in report.get("feature_importances", {}).items():
            with st.expander(f"📈 {model_name} — Feature Importances"):
                fi_df = pd.DataFrame(fi_list, columns=["Feature", "Importance"]).head(20)
                st.dataframe(fi_df, use_container_width=True)
                # Simple bar chart via st.bar_chart
                st.bar_chart(fi_df.set_index("Feature")["Importance"])

        # ── Unsupervised results ──────────────────────────────────────────
        if do_unsup and (
            "IsolationForest" in trainer.models_ or "LOF" in trainer.models_
        ):
            st.markdown("#### Unsupervised Anomaly Flags")
            unsup_df = trainer.predict_unsupervised(records)
            # merge with status
            status_map = {r["hub_name"]: r["status"] for r in records}
            unsup_df["rule_status"] = unsup_df["hub_name"].map(status_map)
            n_flagged = unsup_df.get("ensemble_anomaly", pd.Series(dtype=int)).sum()
            st.metric("Hubs flagged as anomalous by unsupervised models", int(n_flagged))
            st.dataframe(unsup_df.head(30), use_container_width=True)

            # Agreement with rule-based labels
            if "if_anomaly" in unsup_df.columns:
                unsup_df["rule_anom"] = unsup_df["rule_status"].isin(
                    ["Warning", "Critical Anomaly"]).astype(int)
                agree = (unsup_df["if_anomaly"] == unsup_df["rule_anom"]).mean() * 100
                st.metric("IsolationForest ↔ Rule-based agreement", f"{agree:.1f}%")

    # Download training dataset
    if st.session_state.get("gandalf_trainer"):
        st.markdown("---")
        X, y, hub_names, feature_cols = _build_feature_matrix(records)
        ml_df = pd.DataFrame(X, columns=feature_cols)
        ml_df.insert(0, "hub_name", hub_names)
        ml_df["label"] = y
        ml_df["label_name"] = [INV_LABEL.get(int(yi), "?") for yi in y]
        csv_bytes = ml_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ Download ML Training Dataset (23 features + labels)",
            data=csv_bytes,
            file_name="gandalf_ml_dataset.csv",
            mime="text/csv",
            key="gandalf_dl_ml_dataset",
        )
