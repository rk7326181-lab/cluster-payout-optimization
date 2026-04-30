"""
Hub Cluster Cost Optimization Dashboard
========================================
Version: 4.0.0 — Redesigned to match Stitch "Precision Navigator" design system
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import sys, time, base64
from pathlib import Path

sys.path.append(str(Path(__file__).parent / "modules"))

from data_loader import DataLoader
from map_renderer import MapRenderer
from cost_analyzer import CostAnalyzer
from cpo_optimizer import CPOOptimizer
from utils import format_number
from bigquery_client import (
    init_bq_on_startup, handle_service_account_upload,
    handle_google_oauth_login, clear_oauth_credentials,
    HAS_BQ, fetch_awb_data, load_awb_from_cache, get_awb_cache_info,
    _save_awb_cache, load_hexbin_cache, load_awb_sample_cache,
    get_hub_pincode_counts, get_awb_preview, _get_awb_cache_path,
    is_cloud_environment as bq_is_cloud_env,
    auto_connect as bq_auto_connect,
)
from cpo_analytics import CPOAnalytics
from polygon_optimizer import PolygonOptimizer
from gandalf_engine import GandalfEngine
from gandalf_llm import get_llm_status, gandalf_chat
import json
import streamlit.components.v1 as components
from auth_page import render_login_page

APP_ROOT = Path(__file__).parent

# Ensure required data directories exist on first run (gitignored on cloud)
(APP_ROOT / "data").mkdir(exist_ok=True)
(APP_ROOT / "data" / "awb_cache").mkdir(exist_ok=True)

st.set_page_config(
    page_title="Shadowfax Cluster Optimizer",
    page_icon="https://www.shadowfax.in/favicon.ico",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ════════════════════════════════════════════════════
# DESIGN SYSTEM CSS — "The Precision Navigator"
# Matches Stitch reference: tonal layering, no harsh
# borders, Montserrat typography, glassmorphism
# ════════════════════════════════════════════════════
def inject_custom_css():
    dark = st.session_state.get("dark_mode", False)

    # Load fonts first via link tags (injected before CSS block)
    st.markdown("""
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0" rel="stylesheet">
    """, unsafe_allow_html=True)

    # Shared base styles
    shared_css = """
    .material-symbols-outlined {
        font-family: 'Material Symbols Outlined' !important;
        font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
        font-size: 20px; vertical-align: middle;
        line-height: 1; font-style: normal; display: inline-block;
    }

    /* Hide Streamlit chrome */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    .stDeployButton { display: none; }
    [data-testid="stHeader"] { background: transparent !important; }

    /* Smooth transitions (shadowfax.in inspired) */
    *, *::before, *::after { transition: background-color 0.18s ease, color 0.18s ease, border-color 0.18s ease; }

    /* Metric card hover — shadowfax.in translate effect */
    [data-testid="stMetric"] { transition: transform 0.3s ease, box-shadow 0.3s ease !important; }
    [data-testid="stMetric"]:hover { transform: translateY(-4px) !important; }

    /* Dataframe container hover lift */
    [data-testid="stDataFrame"] { transition: transform 0.3s ease, box-shadow 0.3s ease !important; }

    /* ── Sidebar width + text overflow fix ── */
    [data-testid="stSidebar"] { min-width: 280px !important; max-width: 280px !important; }
    [data-testid="stSidebar"] > div:first-child { width: 280px !important; padding-left: 12px !important; padding-right: 12px !important; }
    /* Prevent text overlap in sidebar */
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] .stMarkdown span,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stCaption {
        overflow: hidden !important; text-overflow: ellipsis !important;
        white-space: nowrap !important; max-width: 100% !important;
    }
    [data-testid="stSidebar"] .stExpander { overflow: hidden !important; }
    [data-testid="stSidebar"] .streamlit-expanderHeader p { font-size: 0.82rem !important; }
    /* File uploader compact styling */
    [data-testid="stSidebar"] [data-testid="stFileUploader"] {
        padding: 8px !important; border-radius: 10px !important;
    }
    [data-testid="stSidebar"] [data-testid="stFileUploader"] label {
        font-size: 0.75rem !important; white-space: normal !important;
    }
    [data-testid="stSidebar"] [data-testid="stFileUploader"] button {
        font-size: 0.72rem !important; padding: 4px 10px !important;
    }
    [data-testid="stSidebar"] [data-testid="stFileUploader"] small,
    [data-testid="stSidebar"] [data-testid="stFileUploader"] .uploadedFileName {
        font-size: 0.68rem !important; overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    /* Number input compact */
    [data-testid="stSidebar"] .stNumberInput label { font-size: 0.75rem !important; }
    [data-testid="stSidebar"] .stNumberInput input { font-size: 0.8rem !important; padding: 6px 8px !important; }

    /* ── No-Line rule: never use 1px solid borders ── */
    /* Boundaries defined only through tonal transitions */

    /* ── Nav item styles (sidebar) ── */
    .pn-nav { display: flex; flex-direction: column; gap: 2px; margin: 0 0 4px 0; }
    .pn-nav-item {
        display: flex; align-items: center; gap: 10px;
        padding: 10px 12px; border-radius: 10px;
        font-family: 'Montserrat', sans-serif; font-size: 0.82rem; font-weight: 500;
        letter-spacing: -0.01em; cursor: default;
        transition: background 0.15s;
    }
    .pn-nav-item.active { font-weight: 700; }
    .pn-nav-item .material-symbols-outlined { font-size: 18px; }

    /* ── Section label ── */
    .pn-section-label {
        font-family: 'Montserrat', sans-serif;
        font-size: 0.58rem; font-weight: 700;
        text-transform: uppercase; letter-spacing: 0.14em;
        padding: 0 4px; margin-bottom: 6px;
    }

    /* ── Status pill ── */
    .pn-status-pill {
        display: flex; align-items: center; justify-content: space-between;
        padding: 10px 14px; border-radius: 12px;
    }
    .pn-status-pill-label {
        font-family: 'Montserrat', sans-serif;
        font-size: 0.6rem; font-weight: 700;
        text-transform: uppercase; letter-spacing: 0.1em;
    }
    .pn-badge-connected {
        display: inline-flex; align-items: center; gap: 5px;
        padding: 3px 10px; border-radius: 20px;
        font-family: 'Montserrat', sans-serif;
        font-size: 0.58rem; font-weight: 700;
        background: rgba(34,197,94,0.12); color: #16a34a;
    }
    .pn-badge-connected::before {
        content: ''; width: 5px; height: 5px;
        border-radius: 50%; background: #22c55e;
    }
    .pn-badge-disconnected {
        display: inline-flex; align-items: center; gap: 5px;
        padding: 3px 10px; border-radius: 20px;
        font-family: 'Montserrat', sans-serif;
        font-size: 0.58rem; font-weight: 700;
        background: rgba(186,26,26,0.1); color: #ba1a1a;
    }

    /* ── Header banner (gradient) ── */
    .pn-header-banner {
        background: linear-gradient(135deg, #008A71 0%, #006C68 100%);
        padding: 28px 36px;
        margin-bottom: 0;
        position: relative; overflow: hidden;
        border-radius: 0;
    }
    .pn-header-banner::before {
        content: '';
        position: absolute; inset: 0;
        background: url("data:image/svg+xml,%3Csvg width='100%25' height='100%25' viewBox='0 0 100 100' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M0 100 L100 0 L100 100 Z' fill='rgba(255,255,255,0.04)'/%3E%3C/svg%3E");
        background-size: cover;
        pointer-events: none;
    }
    .pn-header-banner h1 {
        font-family: 'Montserrat', sans-serif !important;
        font-size: 1.6rem !important; font-weight: 900 !important;
        color: #ffffff !important; letter-spacing: -0.03em !important;
        margin: 0 0 2px 0 !important;
    }
    .pn-header-banner .pn-header-sub {
        font-family: 'Montserrat', sans-serif;
        font-size: 0.62rem; font-weight: 600;
        color: rgba(255,255,255,0.7);
        text-transform: uppercase; letter-spacing: 0.14em;
    }
    .pn-header-badge {
        display: inline-flex; align-items: center; gap: 6px;
        background: rgba(255,255,255,0.12);
        backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
        color: #ffffff; padding: 6px 14px; border-radius: 20px;
        font-family: 'Montserrat', sans-serif;
        font-size: 0.62rem; font-weight: 700;
        letter-spacing: 0.04em;
        border: 1px solid rgba(255,255,255,0.18);
    }
    .pn-header-badge::before {
        content: ''; width: 6px; height: 6px;
        border-radius: 50%; background: #D5D226;
    }

    /* ── Bento metric card ── */
    .pn-metric-card {
        border-radius: 20px;
        padding: 28px 24px;
        position: relative; overflow: hidden;
        display: flex; flex-direction: column; gap: 12px;
    }
    .pn-metric-card::after {
        content: ''; position: absolute; top: -40px; right: -40px;
        width: 120px; height: 120px; border-radius: 50%;
        background: rgba(0,138,113,0.06);
        pointer-events: none;
    }
    .pn-metric-label {
        font-family: 'Montserrat', sans-serif;
        font-size: 0.6rem; font-weight: 800;
        text-transform: uppercase; letter-spacing: 0.12em;
    }
    .pn-metric-value {
        font-family: 'Montserrat', sans-serif;
        font-size: 2.2rem; font-weight: 900;
        letter-spacing: -0.03em; line-height: 1;
    }
    .pn-metric-sub {
        font-family: 'Inter', sans-serif;
        font-size: 0.72rem; font-weight: 600;
        display: flex; align-items: center; gap: 4px;
    }
    .pn-metric-sub .material-symbols-outlined { font-size: 14px; }
    .pn-metric-icon {
        width: 36px; height: 36px; border-radius: 10px;
        display: flex; align-items: center; justify-content: center;
    }
    .pn-metric-icon .material-symbols-outlined { font-size: 18px; }

    /* ── Recommendation list card ── */
    .pn-rec-item {
        display: flex; align-items: flex-start; gap: 12px;
        padding: 14px 16px; border-radius: 14px;
        margin-bottom: 8px;
    }
    .pn-rec-icon { flex-shrink: 0; margin-top: 1px; }
    .pn-rec-icon .material-symbols-outlined { font-size: 18px; }
    .pn-rec-title {
        font-family: 'Montserrat', sans-serif;
        font-size: 0.8rem; font-weight: 700; margin-bottom: 2px;
    }
    .pn-rec-desc {
        font-family: 'Inter', sans-serif;
        font-size: 0.72rem; line-height: 1.4;
    }

    /* ── Editorial hero (CPO dashboard) ── */
    .pn-hero {
        border-radius: 24px; overflow: hidden; position: relative;
        min-height: 220px; display: flex; align-items: flex-end;
        padding: 36px 40px; margin-bottom: 0;
    }
    .pn-hero-overlay {
        position: absolute; inset: 0;
        background: linear-gradient(to top, rgba(0,0,0,0.8) 0%, rgba(0,0,0,0.35) 50%, transparent 100%);
        z-index: 1;
    }
    .pn-hero-content { position: relative; z-index: 2; }
    .pn-hero-eyebrow {
        font-family: 'Montserrat', sans-serif;
        font-size: 0.6rem; font-weight: 700;
        text-transform: uppercase; letter-spacing: 0.16em;
        color: #6fd9bc; margin-bottom: 8px;
        display: flex; align-items: center; gap: 6px;
    }
    .pn-hero h2 {
        font-family: 'Montserrat', sans-serif !important;
        font-size: 2.4rem !important; font-weight: 900 !important;
        color: #ffffff !important; letter-spacing: -0.04em !important;
        line-height: 1.1 !important; margin: 0 0 8px 0 !important;
    }
    .pn-hero p { font-family: 'Inter', sans-serif; font-size: 0.85rem; color: rgba(255,255,255,0.7); margin: 0; }

    /* ── Run Optimizer button (sidebar bottom) ── */
    .pn-run-btn {
        width: 100%; padding: 13px;
        background: linear-gradient(135deg, #008A71 0%, #00846c 100%);
        color: #ffffff; border: none; border-radius: 12px;
        font-family: 'Montserrat', sans-serif; font-size: 0.85rem;
        font-weight: 700; letter-spacing: -0.01em;
        cursor: default; text-align: center;
        box-shadow: 0 4px 16px rgba(0,107,87,0.25);
        display: flex; align-items: center; justify-content: center; gap: 8px;
    }
    .pn-bottom-link {
        display: flex; align-items: center; gap: 10px;
        padding: 9px 12px; border-radius: 8px;
        font-family: 'Montserrat', sans-serif; font-size: 0.8rem; font-weight: 500;
        cursor: default;
    }
    .pn-bottom-link .material-symbols-outlined { font-size: 17px; }

    /* ═══ GANDALF AI Panel Styles ═══ */
    .gandalf-briefing-banner {
        background: linear-gradient(135deg, #0d1117 0%, #1a2332 50%, #0d2818 100%);
        border: 1px solid rgba(111,217,188,0.2);
        border-radius: 16px;
        padding: 28px 32px;
        margin-bottom: 20px;
        position: relative;
        overflow: hidden;
        backdrop-filter: blur(12px);
    }
    .gandalf-briefing-banner::before {
        content: '';
        position: absolute; top: 0; left: 0; right: 0; height: 2px;
        background: linear-gradient(90deg, transparent, #6fd9bc, #008A71, transparent);
    }
    .gandalf-metric-card {
        background: rgba(26,35,50,0.85);
        border: 1px solid rgba(111,217,188,0.12);
        border-radius: 12px;
        padding: 18px 20px;
        backdrop-filter: blur(8px);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .gandalf-metric-card:hover {
        transform: translateY(-2px);
        border-color: rgba(111,217,188,0.35);
    }
    .gandalf-alert-card {
        background: rgba(26,35,50,0.7);
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 10px;
        border-left: 3px solid #6b7280;
    }
    .gandalf-alert-critical { border-left-color: #ef4444; background: rgba(239,68,68,0.06); }
    .gandalf-alert-high { border-left-color: #f97316; background: rgba(249,115,22,0.06); }
    .gandalf-alert-medium { border-left-color: #eab308; background: rgba(234,179,8,0.06); }
    .gandalf-alert-low { border-left-color: #22c55e; background: rgba(34,197,94,0.06); }
    .gandalf-insight-card {
        background: rgba(26,35,50,0.6);
        border: 1px solid rgba(111,217,188,0.1);
        border-left: 3px solid #008A71;
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 10px;
        font-size: 13px;
        line-height: 1.6;
        color: #c9d1d9;
    }
    .gandalf-priority-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 10px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .gandalf-priority-critical { background: #7f1d1d; color: #fca5a5; }
    .gandalf-priority-high { background: #7c2d12; color: #fdba74; }
    .gandalf-priority-medium { background: #713f12; color: #fde047; }
    .gandalf-priority-low { background: #14532d; color: #86efac; }
    .gandalf-score-ring {
        width: 80px; height: 80px;
        border-radius: 50%;
        background: conic-gradient(#008A71 calc(var(--score) * 1%), #1a2332 0);
        display: flex; align-items: center; justify-content: center;
        position: relative;
    }
    .gandalf-score-ring::after {
        content: '';
        width: 60px; height: 60px;
        border-radius: 50%;
        background: #0d1117;
        position: absolute;
    }
    .gandalf-score-text {
        position: relative; z-index: 1;
        font-size: 18px; font-weight: 800;
        color: #6fd9bc;
        font-family: 'Montserrat', sans-serif;
    }
    """

    if dark:
        css = shared_css + """
        :root {
            --sfx-primary: #6fd9bc;
            --sfx-primary-dark: #008A71;
            --sfx-primary-container: #00846c;
            --sfx-accent: #cfcc00;
            --sfx-bg: #0F1117;
            --sfx-surface: #151720;
            --sfx-surface-low: #151720;
            --sfx-surface-container: #1A1C24;
            --sfx-surface-high: #242630;
            --sfx-surface-highest: #2E3040;
            --sfx-border: rgba(255,255,255,0.05);
            --sfx-text: #fbf9f8;
            --sfx-text-muted: #9CA3AF;
            --sfx-text-heading: #fbf9f8;
            --sfx-success: #6fd9bc;
            --sfx-warning: #cfcc00;
            --sfx-error: #EF4444;
            --sfx-card-shadow: 0 4px 24px rgba(0,0,0,0.3);
            --sfx-ambient: 0px 12px 32px rgba(0,107,87,0.06);
            --sfx-radius: 16px;
            --sfx-radius-lg: 20px;
        }

        .stApp, [data-testid="stAppViewContainer"] {
            background-color: var(--sfx-bg) !important;
            font-family: 'Montserrat', 'Inter', sans-serif !important;
        }
        .stApp header[data-testid="stHeader"] { background: transparent !important; }

        /* Sidebar — Command Center */
        [data-testid="stSidebar"] {
            background-color: var(--sfx-surface) !important;
            border-right: none !important;
        }
        [data-testid="stSidebar"] > div:first-child {
            padding-top: 0 !important;
        }
        [data-testid="stSidebar"] * {
            color: var(--sfx-text) !important;
            font-family: 'Montserrat', 'Inter', sans-serif !important;
        }
        [data-testid="stSidebar"] .stMarkdown p { font-size: 0.85rem; }
        [data-testid="stSidebar"] hr {
            border-color: var(--sfx-border) !important;
            margin: 0.75rem 0 !important;
        }

        /* Text */
        .stMarkdown, .stText, p, span, label { color: var(--sfx-text) !important; font-family: 'Montserrat', 'Inter', sans-serif !important; }
        h1, h2, h3, h4 { color: var(--sfx-text-heading) !important; font-family: 'Montserrat', sans-serif !important; font-weight: 700 !important; letter-spacing: -0.02em !important; }

        /* Metrics — Tonal Cards */
        [data-testid="stMetric"] {
            background: var(--sfx-surface-container) !important;
            border: 1px solid var(--sfx-border) !important;
            border-radius: var(--sfx-radius) !important;
            padding: 20px 24px !important;
            box-shadow: var(--sfx-card-shadow) !important;
        }
        [data-testid="stMetricLabel"] {
            color: var(--sfx-text-muted) !important;
            font-size: 0.65rem !important;
            font-weight: 800 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.1em !important;
        }
        [data-testid="stMetricValue"] {
            color: var(--sfx-primary) !important;
            font-weight: 800 !important;
            font-size: 1.8rem !important;
            font-family: 'Montserrat', sans-serif !important;
        }
        [data-testid="stMetricDelta"] { font-weight: 600 !important; }

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            background-color: var(--sfx-surface) !important;
            border-radius: 10px !important;
            padding: 4px !important;
            gap: 4px !important;
            border: 1px solid var(--sfx-border) !important;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 8px !important;
            color: var(--sfx-text-muted) !important;
            font-weight: 600 !important;
            font-family: 'Montserrat', sans-serif !important;
            font-size: 0.85rem !important;
            padding: 8px 20px !important;
        }
        .stTabs [aria-selected="true"] {
            background-color: var(--sfx-primary-dark) !important;
            color: #FFFFFF !important;
        }

        /* Buttons */
        .stButton > button {
            background: linear-gradient(135deg, var(--sfx-primary-dark) 0%, var(--sfx-primary-container) 100%) !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 700 !important;
            font-family: 'Montserrat', sans-serif !important;
            padding: 0.6rem 1.2rem !important;
            font-size: 0.85rem !important;
        }
        .stButton > button:hover {
            opacity: 0.9 !important;
            box-shadow: 0 4px 16px rgba(0,138,113,0.3) !important;
            transform: translateY(-1px);
        }
        .stButton > button:active { transform: scale(0.97); }

        /* Inputs */
        .stSelectbox > div > div, .stNumberInput > div > div > input, .stTextInput > div > div > input {
            background-color: var(--sfx-surface-container) !important;
            border: none !important;
            border-radius: 8px !important;
            color: var(--sfx-text) !important;
            font-family: 'Montserrat', sans-serif !important;
        }
        .stSelectbox > div > div:focus-within, .stNumberInput > div > div:focus-within {
            box-shadow: 0 0 0 2px var(--sfx-primary-dark) !important;
        }

        /* Expander */
        .streamlit-expanderHeader {
            background-color: var(--sfx-surface-container) !important;
            border-radius: 8px !important;
            color: var(--sfx-text) !important;
            font-weight: 600 !important;
            border: none !important;
        }

        /* Dataframe */
        [data-testid="stDataFrame"] {
            border-radius: var(--sfx-radius) !important;
            overflow: hidden;
            border: 1px solid var(--sfx-border) !important;
        }

        /* Download buttons */
        .stDownloadButton > button {
            background: transparent !important;
            border: 1.5px solid var(--sfx-primary) !important;
            color: var(--sfx-primary) !important;
        }
        .stDownloadButton > button:hover {
            background: var(--sfx-primary-dark) !important;
            color: #FFFFFF !important;
        }

        /* File uploader */
        [data-testid="stFileUploader"] {
            border: 2px dashed var(--sfx-surface-high) !important;
            border-radius: var(--sfx-radius) !important;
            padding: 1rem !important;
        }

        /* Progress bar */
        .stProgress > div > div > div { background: linear-gradient(90deg, var(--sfx-primary-dark), var(--sfx-primary)) !important; }

        /* ── DARK MODE — Full Precision Navigator ── */
        .stApp, [data-testid="stAppViewContainer"] {
            background-color: #0F1117 !important;
            font-family: 'Inter', 'Montserrat', sans-serif !important;
        }
        /* Sidebar — stone-900 style */
        [data-testid="stSidebar"] {
            background-color: #1c1917 !important;
            border-right: none !important;
            box-shadow: none !important;
        }
        [data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }
        [data-testid="stSidebar"] * { color: #e7e5e4 !important; font-family: 'Montserrat','Inter',sans-serif !important; }
        [data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.06) !important; margin: 0.6rem 0 !important; }
        /* Sidebar scrollbar */
        [data-testid="stSidebar"] ::-webkit-scrollbar { width: 4px; }
        [data-testid="stSidebar"] ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius:4px; }

        /* Main text */
        .stMarkdown, .stText, p, span, label { color: #fbf9f8 !important; font-family:'Inter','Montserrat',sans-serif !important; }
        h1, h2, h3, h4 { color: #fbf9f8 !important; font-family:'Montserrat',sans-serif !important; font-weight:700 !important; letter-spacing:-0.02em !important; }

        /* ── Tabs — horizontal underline style (stitch design) ── */
        .stTabs [data-baseweb="tab-list"] {
            background: rgba(255,255,255,0.04) !important;
            backdrop-filter: blur(16px) !important;
            border-radius: 0 !important;
            padding: 0 !important;
            gap: 0 !important;
            border: none !important;
            border-bottom: 1px solid rgba(255,255,255,0.07) !important;
        }
        .stTabs [data-baseweb="tab"] {
            background: transparent !important;
            border: none !important;
            border-bottom: 2px solid transparent !important;
            border-radius: 0 !important;
            color: #9CA3AF !important;
            font-weight: 500 !important;
            font-family: 'Montserrat', sans-serif !important;
            font-size: 0.85rem !important;
            padding: 14px 22px !important;
            margin-bottom: -1px !important;
            letter-spacing: -0.01em !important;
        }
        .stTabs [aria-selected="true"] {
            color: #6fd9bc !important;
            border-bottom-color: #6fd9bc !important;
            background: transparent !important;
            font-weight: 700 !important;
        }
        .stTabs [data-baseweb="tab-highlight"] { display:none !important; }
        .stTabs [data-baseweb="tab-border"] { display:none !important; }

        /* ── Metric cards — bento style ── */
        [data-testid="stMetric"] {
            background: #1A1C24 !important;
            border: none !important;
            border-radius: 20px !important;
            padding: 28px 24px !important;
            box-shadow: 0px 12px 32px rgba(0,107,87,0.06) !important;
            position: relative; overflow: hidden;
        }
        [data-testid="stMetricLabel"] {
            color: #9CA3AF !important; font-size: 0.6rem !important;
            font-weight: 800 !important; text-transform: uppercase !important;
            letter-spacing: 0.12em !important; font-family: 'Montserrat',sans-serif !important;
        }
        [data-testid="stMetricValue"] {
            color: #6fd9bc !important; font-weight: 900 !important;
            font-size: 2rem !important; font-family: 'Montserrat', sans-serif !important;
            letter-spacing: -0.03em !important;
        }
        [data-testid="stMetricDelta"] { font-weight: 600 !important; font-size: 0.75rem !important; }

        /* ── Buttons — signature gradient ── */
        .stButton > button {
            background: linear-gradient(135deg, #008A71 0%, #00846c 100%) !important;
            color: #fff !important; border: none !important; border-radius: 10px !important;
            font-weight: 700 !important; font-family: 'Montserrat',sans-serif !important;
            padding: 0.65rem 1.4rem !important; font-size: 0.85rem !important;
            box-shadow: 0 4px 16px rgba(0,107,87,0.25) !important; letter-spacing: -0.01em !important;
        }
        .stButton > button:hover { opacity:.92 !important; transform:translateY(-1px); box-shadow: 0 6px 20px rgba(0,107,87,0.35) !important; }
        .stButton > button:active { transform:scale(0.97); }

        /* ── Inputs ── */
        .stSelectbox > div > div, .stNumberInput > div > div > input, .stTextInput > div > div > input {
            background: #1A1C24 !important; border: none !important;
            border-radius: 10px !important; color: #fbf9f8 !important;
            font-family: 'Inter',sans-serif !important;
        }
        .stSelectbox > div > div:focus-within { box-shadow: 0 0 0 2px #008A71 !important; }
        .stTextInput > div > div { border-bottom: 2px solid transparent !important; }
        .stTextInput > div > div:focus-within { border-bottom-color: #6fd9bc !important; }

        /* ── Cards / containers ── */
        .streamlit-expanderHeader {
            background: #1A1C24 !important; border-radius: 10px !important;
            color: #fbf9f8 !important; font-weight: 600 !important; border: none !important;
        }
        [data-testid="stDataFrame"] { border-radius: 16px !important; overflow: hidden; }
        [data-testid="stFileUploader"] {
            border: 2px dashed #2E3040 !important;
            border-radius: 12px !important; padding: 1rem !important;
        }
        [data-testid="stForm"] { background: transparent !important; border: none !important; }

        /* ── Download / progress / alerts ── */
        .stDownloadButton > button {
            background: transparent !important; border: 1.5px solid #6fd9bc !important;
            color: #6fd9bc !important; box-shadow: none !important;
        }
        .stDownloadButton > button:hover { background: #008A71 !important; color: #fff !important; }
        .stProgress > div > div > div { background: linear-gradient(90deg, #008A71, #6fd9bc) !important; }
        [data-testid="stAlert"] { border-radius: 10px !important; border: none !important; }

        /* ── Nav items (dark) ── */
        .pn-nav-item { color: #a8a29e; }
        .pn-nav-item:hover { background: rgba(255,255,255,0.05) !important; color: #e7e5e4; }
        .pn-nav-item.active { color: #6fd9bc; background: rgba(111,217,188,0.1); }
        .pn-section-label { color: #78716c; }
        .pn-status-pill { background: rgba(255,255,255,0.04); }
        .pn-status-pill-label { color: #78716c; }
        .pn-bottom-link { color: #a8a29e; }
        .pn-bottom-link:hover { background: rgba(255,255,255,0.05); color: #e7e5e4; }

        /* Legacy compat */
        .sfx-section-label { color: #78716c; font-size:0.58rem; font-weight:700; text-transform:uppercase; letter-spacing:0.14em; }
        .sfx-hero { background: linear-gradient(135deg,#0F1117 0%,#1A2332 50%,#0F1117 100%); border-radius:20px; padding:40px 36px; position:relative; overflow:hidden; }
        .sfx-hero::before { content:''; position:absolute; inset:0; background:linear-gradient(135deg,rgba(0,138,113,0.15),transparent 60%); pointer-events:none; }
        .sfx-hero-label { font-size:0.62rem; font-weight:700; text-transform:uppercase; letter-spacing:0.15em; color:#6fd9bc; margin-bottom:10px; position:relative; }
        .sfx-hero h2 { font-size:2.2rem !important; font-weight:900 !important; color:#fff !important; margin:0 0 8px 0 !important; letter-spacing:-0.03em !important; position:relative; }
        .sfx-hero p { color:#9CA3AF; font-size:0.85rem; margin:0; position:relative; }
        .sfx-stat-card { background:#1A1C24; border-radius:16px; padding:24px; display:flex; flex-direction:column; gap:12px; }
        .sfx-stat-label { font-size:0.6rem; font-weight:800; text-transform:uppercase; letter-spacing:0.12em; color:#9CA3AF; }
        .sfx-stat-value { font-size:2rem; font-weight:900; font-family:'Montserrat',sans-serif; color:#6fd9bc; }
        .sfx-stat-sub { font-size:0.75rem; color:#9CA3AF; font-weight:500; }
        .sfx-rec-card { background:linear-gradient(135deg,#008A71,#00846c); border-radius:16px; padding:24px; color:#fff; }
        """
    else:
        css = shared_css + """
        :root {
            --sfx-primary: #008A71;
            --sfx-primary-container: #00846c;
            --sfx-primary-fixed-dim: #6fd9bc;
            --sfx-accent: #cfcc00;
            --sfx-bg: #fbf9f8;
            --sfx-surface: #f5f3f3;
            --sfx-surface-lowest: #ffffff;
            --sfx-surface-container: #efeded;
            --sfx-surface-high: #eae8e7;
            --sfx-border: rgba(0,0,0,0.04);
            --sfx-text: #1b1c1c;
            --sfx-text-muted: #6d7a75;
            --sfx-text-heading: #1b1c1c;
            --sfx-success: #008A71;
            --sfx-error: #ba1a1a;
            --sfx-card-shadow: 0px 12px 32px rgba(0,107,87,0.06);
            --sfx-radius: 16px; --sfx-radius-lg: 20px;
        }

        /* ── LIGHT MODE — Full Precision Navigator ── */
        .stApp, [data-testid="stAppViewContainer"] {
            background-color: #fbf9f8 !important;
            font-family: 'Inter', 'Montserrat', sans-serif !important;
        }
        /* Sidebar — stone-100 style */
        [data-testid="stSidebar"] {
            background-color: #f5f3f3 !important;
            border-right: none !important; box-shadow: none !important;
        }
        [data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }
        [data-testid="stSidebar"] * { font-family: 'Montserrat','Inter',sans-serif !important; color: #1b1c1c !important; }
        [data-testid="stSidebar"] hr { border-color: rgba(0,0,0,0.06) !important; margin: 0.6rem 0 !important; }
        [data-testid="stSidebar"] ::-webkit-scrollbar { width: 4px; }
        [data-testid="stSidebar"] ::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.08); border-radius:4px; }

        /* Main content area */
        .main .block-container { padding-top: 0 !important; }

        /* Text */
        .stMarkdown, .stText, p, span, label { color: #1b1c1c !important; font-family:'Inter','Montserrat',sans-serif !important; }
        h1, h2, h3, h4 { color: #1b1c1c !important; font-family:'Montserrat',sans-serif !important; font-weight:700 !important; letter-spacing:-0.02em !important; }

        /* ── Tabs — horizontal underline (stitch nav style) ── */
        .stTabs [data-baseweb="tab-list"] {
            background: rgba(255,255,255,0.85) !important;
            backdrop-filter: blur(20px) !important; -webkit-backdrop-filter: blur(20px) !important;
            border-radius: 0 !important; padding: 0 !important; gap: 0 !important;
            border: none !important; border-bottom: 1px solid rgba(0,0,0,0.07) !important;
            box-shadow: 0 1px 0 rgba(0,0,0,0.04) !important;
        }
        .stTabs [data-baseweb="tab"] {
            background: transparent !important; border: none !important;
            border-bottom: 2px solid transparent !important; border-radius: 0 !important;
            color: #78716c !important; font-weight: 500 !important;
            font-family: 'Montserrat',sans-serif !important; font-size: 0.85rem !important;
            padding: 14px 22px !important; margin-bottom: -1px !important;
            letter-spacing: -0.01em !important;
        }
        .stTabs [aria-selected="true"] {
            color: #008A71 !important; border-bottom-color: #008A71 !important;
            background: transparent !important; font-weight: 700 !important;
        }
        .stTabs [data-baseweb="tab-highlight"] { display:none !important; }
        .stTabs [data-baseweb="tab-border"] { display:none !important; }

        /* ── Metric cards — bento style ── */
        [data-testid="stMetric"] {
            background: #ffffff !important; border: none !important;
            border-radius: 20px !important; padding: 28px 24px !important;
            box-shadow: 0px 12px 32px rgba(0,107,87,0.06) !important;
            position: relative; overflow: hidden;
        }
        [data-testid="stMetricLabel"] {
            color: #6d7a75 !important; font-size: 0.6rem !important;
            font-weight: 800 !important; text-transform: uppercase !important;
            letter-spacing: 0.12em !important; font-family:'Montserrat',sans-serif !important;
        }
        [data-testid="stMetricValue"] {
            color: #008A71 !important; font-weight: 900 !important;
            font-size: 2rem !important; font-family:'Montserrat',sans-serif !important;
            letter-spacing: -0.03em !important;
        }
        [data-testid="stMetricDelta"] { font-weight: 600 !important; font-size: 0.75rem !important; }

        /* ── Buttons — signature gradient ── */
        .stButton > button {
            background: linear-gradient(135deg, #008A71 0%, #00846c 100%) !important;
            color: #fff !important; border: none !important; border-radius: 10px !important;
            font-weight: 700 !important; font-family:'Montserrat',sans-serif !important;
            padding: 0.65rem 1.4rem !important; font-size: 0.85rem !important;
            box-shadow: 0 4px 16px rgba(0,107,87,0.18) !important; letter-spacing:-0.01em !important;
        }
        .stButton > button:hover { opacity:.92 !important; transform:translateY(-1px); box-shadow: 0 8px 24px rgba(0,107,87,0.28) !important; }
        .stButton > button:active { transform:scale(0.97); }

        /* ── Inputs — surface-container-low with primary focus ── */
        .stSelectbox > div > div, .stNumberInput > div > div > input, .stTextInput > div > div > input {
            background: #ffffff !important; border: none !important;
            border-radius: 10px !important; font-family:'Inter',sans-serif !important;
            color: #1b1c1c !important;
        }
        .stSelectbox > div > div:focus-within { box-shadow: 0 0 0 2px #008A71 !important; }
        .stTextInput > div > div { border-bottom: 2px solid transparent !important; }
        .stTextInput > div > div:focus-within { border-bottom-color: #008A71 !important; }

        /* ── Cards / containers ── */
        .streamlit-expanderHeader {
            background: #ffffff !important; border-radius: 10px !important;
            font-weight: 600 !important; border: none !important;
            box-shadow: 0px 2px 8px rgba(0,107,87,0.04) !important;
        }
        [data-testid="stDataFrame"] { border-radius: 16px !important; overflow: hidden; box-shadow: var(--sfx-card-shadow) !important; }
        [data-testid="stFileUploader"] { border: 2px dashed #eae8e7 !important; border-radius: 12px !important; padding: 1rem !important; }
        [data-testid="stForm"] { background: transparent !important; border: none !important; }

        /* ── Download / progress / alerts ── */
        .stDownloadButton > button {
            background: transparent !important; border: 1.5px solid #008A71 !important;
            color: #008A71 !important; box-shadow: none !important;
        }
        .stDownloadButton > button:hover { background: #008A71 !important; color: #fff !important; }
        .stProgress > div > div > div { background: linear-gradient(90deg, #008A71, #6fd9bc) !important; }
        [data-testid="stAlert"] { border-radius: 10px !important; border: none !important; }

        /* ── Nav items (light) ── */
        .pn-nav-item { color: #78716c; }
        .pn-nav-item:hover { background: #eae8e7 !important; color: #1b1c1c; }
        .pn-nav-item.active { color: #008A71; background: rgba(0,138,113,0.08); font-weight: 700; }
        .pn-section-label { color: #a8a29e; }
        .pn-status-pill { background: rgba(255,255,255,0.6); }
        .pn-status-pill-label { color: #a8a29e; }
        .pn-bottom-link { color: #78716c; }
        .pn-bottom-link:hover { background: #eae8e7; color: #1b1c1c; }

        /* Legacy compat */
        .sfx-section-label { color: #a8a29e; font-size:0.58rem; font-weight:700; text-transform:uppercase; letter-spacing:0.14em; }
        .sfx-hero { background: linear-gradient(135deg,#00473A 0%,#006C68 50%,#008A71 100%); border-radius:20px; padding:40px 36px; position:relative; overflow:hidden; }
        .sfx-hero::before { content:''; position:absolute; inset:0; background:linear-gradient(135deg,rgba(0,0,0,0.3),transparent 60%); pointer-events:none; }
        .sfx-hero-label { font-size:0.62rem; font-weight:700; text-transform:uppercase; letter-spacing:0.15em; color:#6fd9bc; margin-bottom:10px; position:relative; }
        .sfx-hero h2 { font-size:2.2rem !important; font-weight:900 !important; color:#fff !important; margin:0 0 8px 0 !important; letter-spacing:-0.03em !important; position:relative; }
        .sfx-hero p { color:rgba(255,255,255,0.75); font-size:0.85rem; margin:0; position:relative; }
        .sfx-stat-card { background:#ffffff; border-radius:16px; padding:24px; box-shadow:0px 12px 32px rgba(0,107,87,0.06); display:flex; flex-direction:column; gap:12px; }
        .sfx-stat-label { font-size:0.6rem; font-weight:800; text-transform:uppercase; letter-spacing:0.12em; color:#6d7a75; }
        .sfx-stat-value { font-size:2rem; font-weight:900; font-family:'Montserrat',sans-serif; color:#008A71; }
        .sfx-stat-sub { font-size:0.75rem; color:#6d7a75; font-weight:500; }
        .sfx-rec-card { background:linear-gradient(135deg,#008A71,#00846c); border-radius:16px; padding:24px; color:#fff; }
        """

    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════
def _invalidate_pip_cache():
    """Clear the point-in-polygon AWB stats cache so it recomputes on next render."""
    st.session_state.pop("_pip_awb_stats", None)
    st.session_state.pop("_pip_data_id", None)
    st.session_state.pop("_hub_pin_counts_cache", None)
    st.session_state.pop("_ms_hex_cache", None)


def _normalize_awb_df(df):
    """
    Auto-detect and normalize column names in an uploaded AWB DataFrame.
    Handles various naming conventions: lat/latitude/Lat/LAT, long/lng/longitude/Longitude, etc.
    Returns (normalized_df, error_message). error_message is None on success.
    """
    col_lower_map = {c.strip().lower().replace(" ", "_").replace("-", "_"): c for c in df.columns}

    # ── Latitude detection ──
    lat_candidates = ["lat", "latitude", "lat.", "delivery_lat", "drop_lat", "dest_lat", "customer_lat", "dlat"]
    lat_col = None
    for cand in lat_candidates:
        if cand in col_lower_map:
            lat_col = col_lower_map[cand]
            break

    # ── Longitude detection ──
    lng_candidates = ["long", "lng", "longitude", "lon", "long.", "delivery_long", "delivery_lng",
                      "drop_lng", "drop_long", "dest_lng", "dest_long", "customer_lng", "dlong", "dlng"]
    lng_col = None
    for cand in lng_candidates:
        if cand in col_lower_map:
            lng_col = col_lower_map[cand]
            break

    if not lat_col or not lng_col:
        # Try to find numeric columns that look like lat/long by value range
        for c in df.columns:
            try:
                vals = pd.to_numeric(df[c], errors='coerce').dropna()
                if len(vals) == 0:
                    continue
                mn, mx = vals.min(), vals.max()
                if not lat_col and 6 < mn and mx < 38 and abs(mx - mn) < 30:
                    lat_col = c  # India lat range ~6-38
                elif not lng_col and 65 < mn and mx < 100 and abs(mx - mn) < 35:
                    lng_col = c  # India long range ~68-98
            except Exception:
                continue

    if not lat_col or not lng_col:
        return None, f"Could not detect lat/long columns. Found columns: {', '.join(df.columns[:20])}"

    # Normalize to standard names
    rename_map = {}
    if lat_col != "lat":
        rename_map[lat_col] = "lat"
    if lng_col != "long":
        rename_map[lng_col] = "long"

    # ── Hub/pincode/AWB detection ──
    hub_candidates = ["hub", "hub_name", "hub_id", "hubname", "facility", "center", "branch", "station"]
    pin_candidates = ["pincode", "pin_code", "pin", "zipcode", "zip_code", "zip", "postal_code", "postalcode"]
    awb_candidates = ["awb_number", "fwd_del_awb_number", "awb", "awb_no", "tracking_number",
                      "tracking_id", "shipment_id", "order_id", "consignment_no", "waybill"]
    date_candidates = ["order_date", "date", "created_date", "created_at", "shipment_date", "booking_date", "delivery_date"]
    payment_candidates = ["payment_category", "payment_type", "payment_mode", "pay_type", "cod_prepaid", "payment"]

    for candidates, target in [
        (hub_candidates, "hub"), (pin_candidates, "pincode"),
        (awb_candidates, "fwd_del_awb_number"), (date_candidates, "order_date"),
        (payment_candidates, "payment_category"),
    ]:
        if target not in col_lower_map:
            for cand in candidates:
                if cand in col_lower_map and col_lower_map[cand] != target:
                    rename_map[col_lower_map[cand]] = target
                    break

    if rename_map:
        df = df.rename(columns=rename_map)

    # Ensure lat/long are numeric
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["long"] = pd.to_numeric(df["long"], errors="coerce")

    return df, None


def _compute_pip_stats(awb_df, processed_df, show_progress=False):
    """
    Match AWB coordinates to cluster polygons using STRtree spatial index.
    Returns dict: cluster_code → {awb_count, total_cost, rate}
    """
    from shapely.geometry import Point
    from shapely.strtree import STRtree

    stats = {}
    if awb_df is None or len(awb_df) == 0 or processed_df is None:
        return stats

    lng_c = "long" if "long" in awb_df.columns else ("lng" if "lng" in awb_df.columns else "longitude")
    lat_c = "lat" if "lat" in awb_df.columns else "latitude"
    if lat_c not in awb_df.columns or lng_c not in awb_df.columns:
        return stats

    coords = awb_df[[lat_c, lng_c]].copy()
    coords = coords.dropna()
    coords[lat_c] = pd.to_numeric(coords[lat_c], errors='coerce')
    coords[lng_c] = pd.to_numeric(coords[lng_c], errors='coerce')
    coords = coords.dropna()
    coords = coords[(coords[lat_c] != 0) & (coords[lng_c] != 0)]

    if len(coords) == 0 or 'geometry' not in processed_df.columns:
        return stats

    # Build polygon list
    polys, poly_cc, poly_rate = [], [], []
    geom_idx = list(processed_df.columns).index('geometry')
    for row in processed_df.itertuples(index=False):
        g = row[geom_idx]
        if g is None or (hasattr(g, 'is_empty') and g.is_empty):
            continue
        if not g.is_valid:
            g = g.buffer(0)
        polys.append(g)
        poly_cc.append(str(getattr(row, 'cluster_code', '')))
        poly_rate.append(float(getattr(row, 'surge_amount', 0)))

    if not polys:
        return stats

    tree = STRtree(polys)
    counts = {cc: 0 for cc in poly_cc}
    rates_map = dict(zip(poly_cc, poly_rate))

    lats = coords[lat_c].values
    lngs = coords[lng_c].values
    total = len(lats)
    matched = 0

    pip_bar = None
    if show_progress:
        pip_bar = st.progress(0, text=f"Matching {total:,} AWBs to {len(polys):,} polygons...")

    batch = 10000
    for start in range(0, total, batch):
        end = min(start + batch, total)
        for i in range(start, end):
            pt = Point(lngs[i], lats[i])
            candidates = tree.query(pt)
            for idx in candidates:
                if polys[idx].contains(pt):
                    counts[poly_cc[idx]] += 1
                    matched += 1
                    break
        if pip_bar:
            pct = min(int((end / total) * 100), 100)
            pip_bar.progress(pct, text=f"Matching AWBs: {end:,}/{total:,} processed • {matched:,} matched")

    if pip_bar:
        pip_bar.empty()

    for cc in counts:
        cnt = counts[cc]
        r = rates_map[cc]
        stats[cc] = {"awb_count": cnt, "total_cost": round(cnt * r, 1), "rate": r}

    return stats


def _ensure_pip_stats():
    """Compute PIP stats if not cached. Call after data or AWB changes."""
    awb_df = st.session_state.get("_awb_cached_df")
    proc_df = st.session_state.get("processed_data")
    if awb_df is None or proc_df is None:
        return

    cache_id = f"{id(awb_df)}_{id(proc_df)}"
    if st.session_state.get("_pip_data_id") == cache_id and st.session_state.get("_pip_awb_stats"):
        return  # Already computed for this data

    # Cap to 100k sampled rows for responsiveness (22M PIP queries would block for minutes)
    PIP_MAX_ROWS = 100_000
    pip_df = awb_df
    scale_factor = 1.0
    if len(awb_df) > PIP_MAX_ROWS:
        scale_factor = len(awb_df) / PIP_MAX_ROWS
        pip_df = awb_df.sample(n=PIP_MAX_ROWS, random_state=42)

    stats = _compute_pip_stats(pip_df, proc_df, show_progress=True)

    # Scale up counts proportionally if we sampled
    if scale_factor > 1.0:
        for cc in stats:
            raw_count = stats[cc]["awb_count"]
            scaled = round(raw_count * scale_factor)
            rate = stats[cc]["rate"]
            stats[cc]["awb_count"] = scaled
            stats[cc]["total_cost"] = round(scaled * rate, 1)

    st.session_state["_pip_awb_stats"] = stats
    st.session_state["_pip_data_id"] = cache_id


def _process_and_store(cluster_df, hub_df, kepler_path=None, excel_path=None):
    loader = DataLoader()
    processed_df = loader.process_data(cluster_df, hub_df)
    if excel_path and Path(excel_path).exists():
        cpo_optimizer = CPOOptimizer(excel_path=str(excel_path))
        processed_df = cpo_optimizer.enrich_cluster_data(processed_df)
        st.session_state.cpo_optimizer = cpo_optimizer
    if 'hub_category' not in processed_df.columns:
        hub_cat_lookup = hub_df.set_index('id')['hub_category'].to_dict() if 'hub_category' in hub_df.columns else {}
        processed_df['hub_category'] = processed_df['hub_id'].map(hub_cat_lookup)
    st.session_state.cluster_data = cluster_df
    st.session_state.hub_data = hub_df
    st.session_state.processed_data = processed_df
    st.session_state.kepler_path = kepler_path
    st.session_state.data_loaded = True


def get_logo_base64():
    logo_path = APP_ROOT / "brand_assets" / "logo.jpeg"
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None


# ════════════════════════════════════════════════════
# INIT SESSION STATE + AUTO-LOAD CACHE
# ════════════════════════════════════════════════════
init_bq_on_startup()

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False
    st.session_state.cluster_data = None
    st.session_state.hub_data = None
    st.session_state.processed_data = None
    st.session_state.cpo_optimizer = None
    st.session_state.kepler_path = None
    st.session_state.cache_date = None

    loader = DataLoader()
    manifest = loader.get_cache_manifest()
    if manifest:
        try:
            cluster_df, hub_df, kepler_path, _ = loader.load_cached_data()
            excel_path = APP_ROOT / "data" / "uploaded_cost_data.xlsx"
            _process_and_store(cluster_df, hub_df, kepler_path=kepler_path,
                              excel_path=str(excel_path) if excel_path.exists() else None)
            st.session_state.cache_date = manifest.get("fetched_time", manifest.get("fetched_date", ""))
        except Exception:
            pass

if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = False

# ── CPO Analytics — load from Excel if present ──
if 'cpo_analytics' not in st.session_state:
    cpo_path = APP_ROOT / "2026-02-19_cpo_with_base.xlsx"
    if not cpo_path.exists():
        cpo_path = APP_ROOT / "data" / "uploaded_cost_data.xlsx"
    if cpo_path.exists():
        st.session_state.cpo_analytics = CPOAnalytics(excel_path=str(cpo_path))
    else:
        st.session_state.cpo_analytics = None

# ── Authentication gate ──
if not st.session_state.get("authenticated", False):
    render_login_page()
    st.stop()

# Inject CSS
inject_custom_css()


# ════════════════════════════════════════════════════
# SIDEBAR — "The Command Center"
# ════════════════════════════════════════════════════
with st.sidebar:
    # ── Brand header ──
    logo_b64 = get_logo_base64()
    logo_html = f'<img src="data:image/jpeg;base64,{logo_b64}" style="width:32px;height:32px;object-fit:contain;border-radius:8px;" />' if logo_b64 else '<svg width="18" height="18" viewBox="0 0 24 24" fill="#fff" stroke="none"><path d="M20 8h-3V4H3c-1.1 0-2 .9-2 2v11h2c0 1.66 1.34 3 3 3s3-1.34 3-3h6c0 1.66 1.34 3 3 3s3-1.34 3-3h2v-5l-3-4zM6 18.5c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zm13.5-9l1.96 2.5H17V9.5h2.5zm-1.5 9c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5z"/></svg>'
    st.markdown(f"""
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@400,0" />
    <div style="padding: 20px 16px 12px 16px;">
        <div style="display:flex;align-items:center;gap:10px;">
            <div style="width:36px;height:36px;background:linear-gradient(135deg,#008A71,#00846c);border-radius:10px;display:flex;align-items:center;justify-content:center;flex-shrink:0;box-shadow:0 4px 12px rgba(0,107,87,0.3);">
                {logo_html}
            </div>
            <div>
                <div style="font-family:'Montserrat',sans-serif;font-weight:800;font-size:1rem;color:#008A71;letter-spacing:-0.03em;line-height:1.1;">Shadowfax</div>
                <div style="font-family:'Montserrat',sans-serif;font-size:0.55rem;font-weight:600;color:#a8a29e;text-transform:uppercase;letter-spacing:0.12em;">Precision Navigator</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Connection status badge (before nav, matching stitch) ──
    bq_mode = st.session_state.get("bq_auth_mode")
    is_connected = bq_mode in ("adc", "google_oauth", "service_account", "streamlit_oauth", "streamlit_secrets")
    badge_cls = "pn-badge-connected" if is_connected else "pn-badge-disconnected"
    badge_txt = "BigQuery Connected" if is_connected else "Not Connected"
    st.markdown(f"""
    <div class="pn-status-pill">
        <span class="pn-status-pill-label">Status</span>
        <span class="{badge_cls}">{badge_txt}</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Nav items (using inline SVG icons — no external font dependency) ──
    st.markdown("""
    <div class="pn-nav" style="margin-top:16px;">
        <div class="pn-nav-item active">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/></svg>
            <span>Map</span>
        </div>
        <div class="pn-nav-item">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
            <span>CPO Dashboard</span>
        </div>
        <div class="pn-nav-item">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
            <span>Recommendations</span>
        </div>
        <div class="pn-nav-item">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>
            <span>Data</span>
        </div>
        <div class="pn-nav-item">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s-8-4.5-8-11.8A8 8 0 0 1 12 2a8 8 0 0 1 8 8.2c0 7.3-8 11.8-8 11.8z"/><circle cx="12" cy="10" r="3"/><path d="M17 10l3-3"/><path d="M20 10v-3h-3"/></svg>
            <span>Maps Studio</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Dark Mode toggle
    dark = st.toggle("Dark Mode", value=st.session_state.dark_mode, key="theme_toggle")
    if dark != st.session_state.dark_mode:
        st.session_state.dark_mode = dark
        st.rerun()

    st.markdown("---")

    # ── BigQuery Connection (only when not connected) ──
    if not is_connected:
        st.markdown('<div class="pn-section-label">Connection</div>', unsafe_allow_html=True)
        if HAS_BQ:
            _on_cloud = bq_is_cloud_env()
            if _on_cloud:
                # On Streamlit Cloud — auto-connect via secrets should have worked.
                # Show status and guide user to fix secrets if it didn't.
                st.warning(
                    "BigQuery not connected.\n\n"
                    "On Streamlit Cloud, connection is automatic via your saved "
                    "Google credentials in Secrets.\n\n"
                    "Go to **App menu (⋮) → Settings → Secrets** and confirm the "
                    "`[google_oauth]` section is present and saved."
                )
                if st.button("Retry Auto-Connect", key="retry_connect_btn", use_container_width=True):
                    with st.spinner("Retrying BigQuery connection..."):
                        _c, _m, _e = bq_auto_connect()
                    if _c:
                        st.session_state["bq_client"] = _c
                        st.session_state["bq_auth_mode"] = _m
                        st.rerun()
                    else:
                        st.error("Still cannot connect. Check Secrets configuration.")
            else:
                # Local environment — offer browser login and JSON key upload
                if st.button("Login with Google", key="login_btn", use_container_width=True):
                    with st.spinner("Opening Google login..."):
                        ok, err = handle_google_oauth_login()
                    if ok:
                        st.rerun()
                    else:
                        st.error(err)
                sa_file = st.file_uploader("Upload JSON key", type=["json"], key="sa_upload")
                if sa_file:
                    ok, err = handle_service_account_upload(sa_file)
                    if ok:
                        st.rerun()
                    else:
                        st.error(err)
        st.markdown("---")
    else:
        if bq_mode == "google_oauth":
            if st.button("Logout", key="logout_btn", use_container_width=True):
                clear_oauth_credentials()
                st.session_state["bq_client"] = None
                st.session_state["bq_auth_mode"] = "needs_key"
                st.rerun()
            st.markdown("---")

    # ── Filters ──
    if st.session_state.data_loaded:
        st.markdown('<div class="pn-section-label">Filters</div>', unsafe_allow_html=True)
        df = st.session_state.processed_data

        hub_categories = ["All Categories"] + sorted(df['hub_category'].dropna().unique().tolist()) if 'hub_category' in df.columns else ["All Categories"]
        selected_category = st.selectbox("Hub Category", hub_categories, key="cat_filter", label_visibility="collapsed")

        category_df = df.copy()
        if selected_category != "All Categories":
            hub_data = st.session_state.hub_data
            matching_hub_ids = hub_data[hub_data['hub_category'] == selected_category]['id'].tolist()
            category_df = category_df[category_df['hub_id'].isin(matching_hub_ids)]

        hub_names = ["All Hubs"] + sorted(category_df['hub_name'].dropna().unique().tolist())
        selected_hub = st.selectbox("Hub Name", hub_names, key="hub_filter", label_visibility="collapsed")

        filtered_df = category_df.copy()
        if selected_hub != "All Hubs":
            filtered_df = filtered_df[filtered_df['hub_name'] == selected_hub]

        st.session_state.filtered_data = filtered_df
        st.session_state.selected_hub = selected_hub if selected_hub != "All Hubs" else None

        st.markdown("---")

    # ── Data Fetch / Load ──
    st.markdown('<div class="pn-section-label">Data</div>', unsafe_allow_html=True)

    cache_date = st.session_state.get("cache_date")
    if st.session_state.data_loaded and cache_date:
        st.caption(f"Last fetched: {cache_date}")
    elif st.session_state.data_loaded:
        st.caption("Loaded from local CSV")

    with st.expander("📡 Fetch fresh data", expanded=not st.session_state.data_loaded):
        col_y, col_m = st.columns(2)
        with col_y:
            bq_year = st.number_input("Year", value=2026, min_value=2020, max_value=2030)
        with col_m:
            bq_month = st.number_input("Month", value=4, min_value=1, max_value=12)

        if st.button("Fetch from BigQuery", key="fetch_bq_btn", use_container_width=True):
            bq_client = st.session_state.get("bq_client")
            if not bq_client:
                st.error("Connect to BigQuery first")
            else:
                progress = st.progress(0, text="Connecting to BigQuery...")
                status_text = st.empty()
                status_detail = st.empty()

                def bq_progress(pct, msg):
                    progress.progress(min(int(pct * 100), 100), text=msg)
                    status_text.caption(msg)

                try:
                    from modules.bigquery_client import fetch_live_clusters, fetch_hub_locations

                    # ── Clear old data immediately so UI shows fresh state ──
                    st.session_state.cluster_data = None
                    st.session_state.hub_data = None
                    st.session_state.processed_data = None
                    st.session_state.data_loaded = False

                    # ── Step 1: Fetch clusters with live status ──
                    bq_progress(0.05, "📡 Submitting cluster query to BigQuery...")
                    cluster_df, err = fetch_live_clusters(bq_client, force_refresh=True, progress_cb=bq_progress)
                    if err:
                        raise Exception(f"Cluster fetch failed: {err}")
                    status_detail.caption(f"✅ {len(cluster_df):,} clusters from {cluster_df['hub_id'].nunique():,} hubs")

                    # ── Step 2: Fetch hub locations with live status ──
                    hub_df, err = fetch_hub_locations(bq_client, bq_year, bq_month, progress_cb=bq_progress)
                    if err:
                        raise Exception(f"Hub fetch failed: {err}")
                    status_detail.caption(f"✅ {len(cluster_df):,} clusters • {len(hub_df):,} hubs fetched")

                    # ── Step 3: Clean + process (fast, local) ──
                    bq_progress(0.62, "🧹 Cleaning data...")
                    loader = DataLoader()
                    cluster_df = loader._clean_cluster_data(cluster_df)
                    hub_df = loader._clean_hub_data(hub_df)

                    bq_progress(0.70, "💾 Saving CSV files...")
                    date_str = datetime.now().strftime('%d%m%Y')
                    cluster_path = APP_ROOT / "data" / f"clustering_live_{date_str}.csv"
                    hub_path = APP_ROOT / "data" / f"hub_Lat_Long{date_str}.csv"
                    cluster_df.to_csv(cluster_path, index=False, encoding="utf-8")
                    hub_df.to_csv(hub_path, index=False, encoding="utf-8")

                    bq_progress(0.78, "📊 Generating Kepler CSV...")
                    kepler_df, kepler_path = loader.generate_kepler_csv(cluster_df, hub_df)

                    bq_progress(0.85, "📋 Saving cache manifest...")
                    loader.save_cache_manifest(cluster_path, hub_path, kepler_path)

                    # ── Step 4: Replace session state atomically ──
                    bq_progress(0.90, "🔄 Replacing old data with new records...")
                    excel_path = APP_ROOT / "data" / "uploaded_cost_data.xlsx"
                    _process_and_store(cluster_df, hub_df, kepler_path=kepler_path,
                                      excel_path=str(excel_path) if excel_path.exists() else None)
                    st.session_state.cache_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    # Clear AWB cache so it refreshes against new clusters
                    st.session_state.pop("_awb_cached_df", None)
                    st.session_state.pop("_awb_processed_id", None)

                    bq_progress(1.0, "✅ Complete — all data replaced with fresh records!")
                    status_detail.empty()
                    time.sleep(0.3)
                    st.success(f"Fetched & replaced: **{len(cluster_df):,}** clusters from **{cluster_df['hub_id'].nunique():,}** hubs")
                    st.rerun()
                except Exception as e:
                    progress.empty()
                    status_text.empty()
                    status_detail.empty()
                    st.error(f"Error: {str(e)}")

    if not st.session_state.data_loaded:
        if st.button("Load from local CSV files", key="load_csv_btn", use_container_width=True):
            with st.spinner("Loading..."):
                try:
                    loader = DataLoader()
                    cluster_df, hub_df = loader.load_from_csv()
                    _process_and_store(cluster_df, hub_df)
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    st.markdown("---")

    # ── External Data Upload ──
    st.markdown('<div class="pn-section-label">External Data</div>', unsafe_allow_html=True)

    # AWB fetch from BigQuery (quick button in sidebar)
    _bq_connected = st.session_state.get("bq_auth_mode") in ("adc", "google_oauth", "service_account", "streamlit_oauth", "streamlit_secrets")
    if _bq_connected and st.session_state.data_loaded:
        if st.button("Fetch AWB from BigQuery", key="sidebar_fetch_awb_bq", use_container_width=True, type="primary"):
            _bq_cl = st.session_state.get("bq_client")
            _live_cl = st.session_state.cluster_data
            _pin_cnt = _live_cl['pincode'].nunique() if 'pincode' in _live_cl.columns else 0
            # Clear old AWB data immediately
            st.session_state.pop("_awb_cached_df", None)
            st.session_state.pop("_awb_processed_id", None)
            _sb_awb_prog = st.progress(0, text=f"Fetching AWB for {_pin_cnt:,} pincodes...")
            _sb_awb_status = st.empty()

            def _sb_awb_cb(pct, msg):
                _sb_awb_prog.progress(min(int(pct * 100), 100), text=msg)
                _sb_awb_status.caption(msg)

            _bq_df, _bq_err = fetch_awb_data(_bq_cl, _live_cl, force_refresh=True, progress_cb=_sb_awb_cb)
            if _bq_err:
                _sb_awb_prog.empty()
                _sb_awb_status.empty()
                st.error(f"AWB fetch failed: {_bq_err}")
            else:
                st.session_state["_awb_cached_df"] = _bq_df
                st.session_state["_awb_processed_id"] = f"bq_{len(_bq_df)}"
                _invalidate_pip_cache()
                _sb_awb_prog.empty()
                _sb_awb_status.empty()
                st.success(f"Fetched {len(_bq_df):,} AWB records")
                st.rerun()

    # AWB CSV upload in sidebar
    _sb_awb_file = st.file_uploader("Upload AWB CSV", type=["csv"], key="sidebar_awb_upload",
                                     help="Upload CSV/Excel with shipment coordinates (auto-detects columns)")
    if _sb_awb_file is not None:
        _sb_awb_id = f"{_sb_awb_file.name}_{_sb_awb_file.size}"
        if st.session_state.get("_awb_processed_id") != _sb_awb_id:
            try:
                with st.spinner("Reading & detecting columns..."):
                    _sb_awb_df = pd.read_csv(_sb_awb_file, low_memory=True)
                    _sb_awb_df, _sb_err = _normalize_awb_df(_sb_awb_df)
                if _sb_err:
                    st.error(_sb_err)
                else:
                    with st.spinner(f"Saving {len(_sb_awb_df):,} AWB records..."):
                        _save_awb_cache(_sb_awb_df)
                    st.session_state["_awb_cached_df"] = _sb_awb_df
                    st.session_state["_awb_processed_id"] = _sb_awb_id
                    _invalidate_pip_cache()
                    st.success(f"{len(_sb_awb_df):,} AWB records saved")
                    st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
        else:
            _awb_meta = get_awb_cache_info()
            _awb_count = _awb_meta.get("record_count") or st.session_state.get("_awb_cached_df", pd.DataFrame()).shape[0]
            st.success(f"AWB data loaded ({_awb_count:,} records)")

    uploaded_excel = st.file_uploader("Upload Excel / CSV", type=['xlsx'], key="cpo_upload")
    if uploaded_excel:
        excel_path = APP_ROOT / "data" / "uploaded_cost_data.xlsx"
        with open(excel_path, "wb") as f:
            f.write(uploaded_excel.getbuffer())
        if st.session_state.data_loaded:
            cpo = CPOOptimizer(excel_path=str(excel_path))
            st.session_state.processed_data = cpo.enrich_cluster_data(st.session_state.processed_data)
            st.session_state.cpo_optimizer = cpo
        # Also refresh CPO analytics (hub-level analysis)
        st.session_state.cpo_analytics = CPOAnalytics(excel_path=str(excel_path))
        st.rerun()

    # ── Run Optimizer button (stitch: bottom of sidebar) ──
    st.markdown("---")
    st.markdown("""
    <div class="pn-run-btn">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" stroke="none"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
        Run Optimizer
    </div>
    """, unsafe_allow_html=True)

    # ── Settings / Support / Sign-out ──
    current_user = st.session_state.get("current_user", "")
    st.markdown(f"""
    <div style="margin-top:8px;">
        <div class="pn-bottom-link">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
            <span>Settings</span>
        </div>
        <div class="pn-bottom-link">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
            <span>Support</span>
        </div>
        <div class="pn-bottom-link" style="margin-top:4px;opacity:0.6;">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            <span style="font-size:0.78rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{current_user}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Sign Out", key="sign_out_btn", use_container_width=True):
        st.session_state["authenticated"] = False
        st.session_state["current_user"] = ""
        st.rerun()


# ════════════════════════════════════════════════════
# MAIN CONTENT
# ════════════════════════════════════════════════════

# Header Banner
logo_b64 = get_logo_base64()
logo_img = f'<img src="data:image/jpeg;base64,{logo_b64}" style="height:32px; object-fit:contain;" />' if logo_b64 else ''
cache_date = st.session_state.get("cache_date", "")
badge_text = f"Data: {cache_date.split(' ')[0]}" if cache_date else "Local CSV"

user_initial = (st.session_state.get("current_user", "A") or "A")[0].upper()
dark = st.session_state.get("dark_mode", False)
_hdr_bg = "rgba(15,17,23,0.95)" if dark else "rgba(255,255,255,0.97)"
_hdr_border = "rgba(255,255,255,0.06)" if dark else "rgba(0,0,0,0.06)"
_hdr_text = "#fbf9f8" if dark else "#1b1c1c"
_hdr_muted = "#9CA3AF" if dark else "#6d7a75"
_hdr_accent = "#6fd9bc" if dark else "#008A71"
_hdr_pill_bg = "rgba(255,255,255,0.06)" if dark else "#f5f3f3"

st.markdown(f"""
<div style="
    background:{_hdr_bg};
    backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);
    border-bottom:1px solid {_hdr_border};
    padding:0 32px;height:64px;
    display:flex;align-items:center;justify-content:space-between;
    margin-bottom:0;position:sticky;top:0;z-index:100;
">
    <div style="display:flex;align-items:center;gap:20px;">
        <div style="display:flex;align-items:center;gap:10px;">
            {f'<img src="data:image/jpeg;base64,{logo_b64}" style="height:28px;object-fit:contain;" />' if logo_b64 else ''}
            <span style="font-family:'Montserrat',sans-serif;font-weight:800;
                font-size:1.1rem;color:{_hdr_accent};letter-spacing:-0.03em;">Shadowfax</span>
        </div>
        <div style="width:1px;height:28px;background:{_hdr_border};"></div>
        <span style="font-family:'Montserrat',sans-serif;font-weight:700;
            font-size:0.95rem;color:{_hdr_text};letter-spacing:-0.02em;">Cluster Optimizer</span>
        <span style="font-family:'Montserrat',sans-serif;font-size:0.6rem;
            font-weight:600;color:{_hdr_muted};text-transform:uppercase;
            letter-spacing:0.08em;">Logistics Intelligence</span>
    </div>
    <div style="display:flex;align-items:center;gap:12px;">
        <span style="font-family:'Inter',sans-serif;font-size:0.72rem;
            color:{_hdr_muted};background:{_hdr_pill_bg};
            padding:5px 12px;border-radius:20px;">{badge_text}</span>
        <div style="width:36px;height:36px;border-radius:50%;
            background:linear-gradient(135deg,#008A71,#00846c);
            display:flex;align-items:center;justify-content:center;
            font-family:'Montserrat',sans-serif;font-weight:700;
            font-size:0.82rem;color:#fff;">{user_initial}</div>
    </div>
</div>
""", unsafe_allow_html=True)

if not st.session_state.data_loaded:
    st.info("No cached data found. Fetch from BigQuery or load local CSV files using the sidebar.")
    st.stop()

# Tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Map", "CPO Dashboard", "Recommendations", "Data", "Maps Studio", "GANDALF AI"])

# ── TAB 1: MAP ──
with tab1:
    filtered_df = st.session_state.filtered_data
    cluster_count = len(filtered_df)

    # Section header
    st.markdown("""
    <div style="margin-bottom:16px;">
        <h2 style="font-size:1.25rem; margin:0 0 4px 0;">Network Distribution Map</h2>
        <p style="font-size:0.85rem; color:var(--sfx-text-muted); margin:0;">Visualizing real-time capacity and cluster efficiency.</p>
    </div>
    """, unsafe_allow_html=True)

    col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([2, 2, 6])
    with col_ctrl1:
        color_mode = st.radio("Color by", ["Surge Rate", "Pincode"], horizontal=True, key="color_mode")
    with col_ctrl2:
        if cluster_count <= 300:
            show_labels = st.checkbox("Show rate labels", value=True, key="labels_chk")
        else:
            show_labels = False
            st.caption(f"{cluster_count:,} clusters — rate on click")

    # Map
    try:
        renderer = MapRenderer()
        map_obj = renderer.create_cluster_map(
            filtered_df, st.session_state.hub_data,
            show_rate_labels=show_labels, show_hub_markers=True,
            selected_hub=st.session_state.get('selected_hub'),
            color_mode='pincode' if color_mode == "Pincode" else 'rate'
        )
        st.components.v1.html(map_obj._repr_html_(), height=620)
    except Exception as e:
        st.error(f"Map error: {str(e)}")

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

    # Stats cards — bento grid matching stitch reference
    cluster_df_full = st.session_state.cluster_data
    hub_df_full = st.session_state.hub_data
    distinct_hubs = cluster_df_full['hub_id'].nunique() if 'hub_id' in cluster_df_full.columns else hub_df_full['id'].nunique()
    unique_pincodes = cluster_df_full['pincode'].nunique() if 'pincode' in cluster_df_full.columns else 0
    surge_pincodes = len(filtered_df[filtered_df['surge_amount'] > 5]) if 'surge_amount' in filtered_df.columns else 0

    dark = st.session_state.get("dark_mode", False)
    _card_bg = "#1A1C24" if dark else "#ffffff"
    _card_shadow = "0px 12px 32px rgba(0,107,87,0.06)"
    _label_color = "#9CA3AF" if dark else "#a8a29e"
    _value_color = "#6fd9bc" if dark else "#1b1c1c"
    _sub_color = "#9CA3AF" if dark else "#78716c"
    _bar_bg = "rgba(111,217,188,0.15)" if dark else "rgba(0,138,113,0.08)"
    _bar_fg = "#6fd9bc" if dark else "#008A71"

    st.markdown(f"""
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:24px;margin-bottom:8px;">
        <div style="background:{_card_bg};padding:28px 24px;border-radius:20px;box-shadow:{_card_shadow};display:flex;flex-direction:column;gap:16px;">
            <span style="font-family:'Montserrat',sans-serif;font-size:0.6rem;font-weight:800;text-transform:uppercase;letter-spacing:0.12em;color:{_label_color};">Total Clusters</span>
            <div style="display:flex;align-items:baseline;gap:8px;">
                <span style="font-family:'Montserrat',sans-serif;font-size:2rem;font-weight:900;color:{_value_color};letter-spacing:-0.03em;">{len(filtered_df):,}</span>
                <span style="font-size:0.75rem;font-weight:700;color:#22c55e;display:flex;align-items:center;">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>&nbsp;12%
                </span>
            </div>
            <div style="display:flex;align-items:flex-end;height:28px;gap:3px;">
                <div style="background:{_bar_bg};flex:1;height:50%;border-radius:2px 2px 0 0;"></div>
                <div style="background:{_bar_bg};flex:1;height:75%;border-radius:2px 2px 0 0;"></div>
                <div style="background:{_bar_bg};flex:1;height:60%;border-radius:2px 2px 0 0;"></div>
                <div style="background:{_bar_fg}40;flex:1;height:85%;border-radius:2px 2px 0 0;"></div>
                <div style="background:{_bar_fg};flex:1;height:100%;border-radius:2px 2px 0 0;"></div>
            </div>
        </div>
        <div style="background:{_card_bg};padding:28px 24px;border-radius:20px;box-shadow:{_card_shadow};display:flex;flex-direction:column;gap:16px;">
            <span style="font-family:'Montserrat',sans-serif;font-size:0.6rem;font-weight:800;text-transform:uppercase;letter-spacing:0.12em;color:{_label_color};">Active Hubs</span>
            <div style="display:flex;align-items:baseline;gap:8px;">
                <span style="font-family:'Montserrat',sans-serif;font-size:2rem;font-weight:900;color:{_value_color};letter-spacing:-0.03em;">{distinct_hubs:,}</span>
                <span style="font-size:0.75rem;color:{_sub_color};font-weight:500;">Nationwide</span>
            </div>
            <div style="display:flex;gap:4px;">
                <div style="height:4px;flex:1;background:{_bar_fg};border-radius:9999px;"></div>
                <div style="height:4px;flex:1;background:{_bar_fg};border-radius:9999px;"></div>
                <div style="height:4px;flex:1;background:{_bar_fg};border-radius:9999px;"></div>
                <div style="height:4px;flex:1;background:{_bar_bg};border-radius:9999px;"></div>
            </div>
        </div>
        <div style="background:{_card_bg};padding:28px 24px;border-radius:20px;box-shadow:{_card_shadow};display:flex;flex-direction:column;gap:16px;">
            <span style="font-family:'Montserrat',sans-serif;font-size:0.6rem;font-weight:800;text-transform:uppercase;letter-spacing:0.12em;color:{_label_color};">Surge Pincodes</span>
            <div style="display:flex;align-items:baseline;gap:8px;">
                <span style="font-family:'Montserrat',sans-serif;font-size:2rem;font-weight:900;color:{_value_color};letter-spacing:-0.03em;">{surge_pincodes:,}</span>
                <span style="color:#ef4444;font-size:0.75rem;font-weight:700;display:flex;align-items:center;">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2L1 21h22L12 2zm0 3.99L19.53 19H4.47L12 5.99zM11 16h2v2h-2zm0-6h2v4h-2z"/></svg>
                </span>
            </div>
            <p style="font-family:'Inter',sans-serif;font-size:0.68rem;color:{_sub_color};margin:0;">Requires immediate cluster re-allocation.</p>
        </div>
        <div style="background:linear-gradient(135deg,#008A71,#00846c);padding:28px 24px;border-radius:20px;box-shadow:0 8px 32px rgba(0,107,87,0.25);display:flex;flex-direction:column;justify-content:space-between;gap:16px;">
            <div>
                <span style="font-family:'Montserrat',sans-serif;font-size:0.6rem;font-weight:800;text-transform:uppercase;letter-spacing:0.12em;color:rgba(255,255,255,0.6);">Recommendation</span>
                <div style="font-family:'Montserrat',sans-serif;font-size:0.9rem;font-weight:700;color:#fff;margin-top:8px;">Active Cluster Balance</div>
            </div>
            <div style="background:#fff;color:#008A71;padding:10px;border-radius:10px;
                font-family:'Montserrat',sans-serif;font-size:0.75rem;font-weight:700;
                text-align:center;cursor:pointer;">Apply All Optimizations</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Hub Efficiency Rankings table
    if st.session_state.data_loaded:
        st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
        _tbl_bg = "#1A1C24" if dark else "#ffffff"
        _tbl_text = "#fbf9f8" if dark else "#1b1c1c"
        _tbl_accent = "#6fd9bc" if dark else "#008A71"
        st.markdown(f"""
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;
            padding:20px 24px 12px 24px;background:{_tbl_bg};border-radius:20px 20px 0 0;
            box-shadow:{_card_shadow};">
            <h3 style="font-family:'Montserrat',sans-serif;font-size:1rem;font-weight:700;
                color:{_tbl_text};margin:0;">Hub Efficiency Rankings</h3>
            <span style="font-family:'Montserrat',sans-serif;font-size:0.75rem;font-weight:700;
                color:{_tbl_accent};display:flex;align-items:center;gap:4px;cursor:pointer;">
                View Detailed Report
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
            </span>
        </div>
        """, unsafe_allow_html=True)

        from utils import aggregate_by_hub
        hub_summary = aggregate_by_hub(filtered_df)
        if len(hub_summary) > 0:
            hub_summary = hub_summary.sort_values('cluster_count', ascending=False).head(20)
            hub_summary['avg_rate'] = hub_summary['avg_rate'].round(2)
            display_cols = {
                'hub_name': 'Hub Name',
                'cluster_count': 'Clusters',
                'avg_rate': 'Avg Rate',
                'unique_pincodes': 'Pincodes'
            }
            display_df = hub_summary[list(display_cols.keys())].rename(columns=display_cols)
            st.dataframe(display_df, use_container_width=True, hide_index=True)


# ── TAB 2: CPO DASHBOARD (Hub-Level Analytics) ──
with tab2:
    cpo_a: CPOAnalytics = st.session_state.get("cpo_analytics")

    # Hero banner
    st.markdown("""
    <div class="pn-hero" style="background:linear-gradient(135deg,#00473A 0%,#006C68 50%,#008A71 100%);">
        <div class="pn-hero-overlay"></div>
        <div class="pn-hero-content">
            <div class="pn-hero-eyebrow">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12V7H5a2 2 0 0 1 0-4h14v4"/><path d="M3 5v14a2 2 0 0 0 2 2h16v-5"/><path d="M18 12a2 2 0 0 0 0 4h4v-4z"/></svg>
                Shadowfax Intelligent Analytics
            </div>
            <h2>Hub CPO &amp; Cluster Cost Analysis</h2>
            <p>Data-driven hub-level cost optimization — identify high-cost hubs, compare clustered vs non-clustered, and generate savings recommendations.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if cpo_a and cpo_a.is_loaded:
        summary = cpo_a.get_summary()
        dark = st.session_state.get("dark_mode", False)
        _card_bg = "#1A1C24" if dark else "#ffffff"
        _card_shadow = "0px 12px 32px rgba(0,107,87,0.06)"
        _label_color = "#9CA3AF" if dark else "#a8a29e"
        _value_color = "#6fd9bc" if dark else "#1b1c1c"
        _accent = "#6fd9bc" if dark else "#008A71"

        # ── KPI Row ──
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        kc1, kc2, kc3, kc4, kc5 = st.columns(5)
        kc1.metric("Total Hubs", f"{summary['total_hubs']:,}")
        kc2.metric("Clustered Hubs", f"{summary['clustered_hubs']:,}")
        kc3.metric("Total Cluster Pay", f"₹{summary['total_cluster_pay']:,.0f}")
        kc4.metric("Avg Cluster CPO (Clustered)", f"₹{summary['avg_cluster_cpo_clustered']:.2f}")
        kc5.metric("Avg Cluster CPO (Non-Clust..)", f"₹{summary['avg_cluster_cpo_non_clustered']:.2f}")

        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

        # ── Clustered vs Non-Clustered Comparison ──
        comparison_df = cpo_a.get_cluster_comparison()
        st.markdown(f"""
        <div style="background:{_card_bg};padding:20px 24px;border-radius:16px;box-shadow:{_card_shadow};margin-bottom:24px;">
            <h3 style="font-size:1rem;font-weight:700;margin:0 0 12px 0;">Clustered vs Non-Clustered Comparison</h3>
        </div>
        """, unsafe_allow_html=True)
        st.dataframe(comparison_df, use_container_width=True, hide_index=True,
                      column_config={
                          "Avg Cluster CPO": st.column_config.NumberColumn(format="₹%.2f"),
                          "Avg LM CPO": st.column_config.NumberColumn(format="₹%.2f"),
                          "Total Cluster Pay": st.column_config.NumberColumn(format="₹%d"),
                          "Total Payout": st.column_config.NumberColumn(format="₹%d"),
                      })

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        # ── CPO Distribution ──
        cpo_dist = cpo_a.get_cpo_distribution()
        col_dist, col_scatter = st.columns([1, 1])

        with col_dist:
            st.markdown("##### Cluster CPO Distribution (Hubs ≥50 orders)")
            st.bar_chart(cpo_dist.set_index("cpo_bucket")["hub_count"], color="#008A71")

        with col_scatter:
            st.markdown("##### Cluster Pay vs Cluster CPO")
            scatter_df = cpo_a.get_scatter_data()
            if len(scatter_df) > 0:
                st.scatter_chart(
                    scatter_df,
                    x="cluster_cpo",
                    y="Cluster_Pay",
                    size="marker_size",
                    color="is_clustered",
                )

        st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

        # ── Sub-tabs for detailed views ──
        cpo_tab1, cpo_tab2, cpo_tab3, cpo_tab4, cpo_tab5, cpo_tab6 = st.tabs([
            "High Cluster Payout Hubs",
            "High Cluster CPO Hubs",
            "High Burn Hubs",
            "Optimization Candidates",
            "Recommendations",
            "Polygon Optimizer",
        ])

        with cpo_tab1:
            st.markdown("""
            <div style="margin-bottom:12px;">
                <p style="font-size:0.85rem; color:var(--sfx-text-muted); margin:0;">
                    Hubs ranked by total Cluster Payout — where the most money is being spent on clustering.
                </p>
            </div>
            """, unsafe_allow_html=True)
            high_pay = cpo_a.get_high_cluster_payout_hubs(top_n=30)
            st.dataframe(high_pay, use_container_width=True, hide_index=True,
                          column_config={
                              "Cluster_Pay": st.column_config.NumberColumn("Cluster Pay", format="₹%d"),
                              "cluster_cpo": st.column_config.NumberColumn("Cluster CPO", format="₹%.2f"),
                              "LM_CPO": st.column_config.NumberColumn("LM CPO", format="₹%.2f"),
                              "total_pay": st.column_config.NumberColumn("Total Pay", format="₹%d"),
                              "cluster_pct_of_total": st.column_config.NumberColumn("Cluster %", format="%.1f%%"),
                          })
            st.download_button(
                "Download High Cluster Payout Hubs",
                high_pay.to_csv(index=False), "high_cluster_payout_hubs.csv",
                "text/csv", use_container_width=True
            )

        with cpo_tab2:
            st.markdown("""
            <div style="margin-bottom:12px;">
                <p style="font-size:0.85rem; color:var(--sfx-text-muted); margin:0;">
                    Hubs with highest Cluster CPO (minimum 100 orders) — where cluster cost per order is most expensive.
                </p>
            </div>
            """, unsafe_allow_html=True)
            high_cpo = cpo_a.get_high_cpo_hubs(min_orders=100, top_n=30)
            st.dataframe(high_cpo, use_container_width=True, hide_index=True,
                          column_config={
                              "cluster_cpo": st.column_config.NumberColumn("Cluster CPO", format="₹%.2f"),
                              "Cluster_Pay": st.column_config.NumberColumn("Cluster Pay", format="₹%d"),
                              "LM_CPO": st.column_config.NumberColumn("LM CPO", format="₹%.2f"),
                              "total_pay": st.column_config.NumberColumn("Total Pay", format="₹%d"),
                          })
            st.download_button(
                "Download High CPO Hubs",
                high_cpo.to_csv(index=False), "high_cpo_hubs.csv",
                "text/csv", use_container_width=True
            )

        with cpo_tab3:
            st.markdown("""
            <div style="margin-bottom:12px;">
                <p style="font-size:0.85rem; color:var(--sfx-text-muted); margin:0;">
                    Hubs where cluster CPO exceeds the threshold — prime targets for polygon expansion and burn reduction.
                </p>
            </div>
            """, unsafe_allow_html=True)

            _burn_col1, _burn_col2 = st.columns([1, 3])
            with _burn_col1:
                _cpo_threshold = st.number_input(
                    "CPO Threshold (₹)",
                    min_value=0.1, max_value=20.0, value=1.0, step=0.5,
                    key="burn_cpo_threshold",
                    help="Show hubs where Cluster CPO exceeds this value"
                )
            with _burn_col2:
                _burn_min_orders = st.slider(
                    "Minimum Orders",
                    min_value=10, max_value=500, value=50, step=10,
                    key="burn_min_orders"
                )

            burn_hubs = cpo_a.get_high_burn_hubs(
                cpo_threshold=_cpo_threshold, min_orders=_burn_min_orders
            )
            if len(burn_hubs) > 0:
                burn_summary = cpo_a.get_burn_summary(
                    cpo_threshold=_cpo_threshold, min_orders=_burn_min_orders
                )
                bc1, bc2, bc3, bc4 = st.columns(4)
                bc1.metric("High Burn Hubs", f"{burn_summary['hub_count']}")
                bc2.metric("Monthly Burn", f"₹{burn_summary['total_monthly_burn']:,.0f}")
                bc3.metric("Annual Burn", f"₹{burn_summary['total_annual_burn']:,.0f}")
                bc4.metric("Avg Cluster CPO", f"₹{burn_summary['avg_cluster_cpo']:.2f}")

                st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
                st.dataframe(burn_hubs, use_container_width=True, hide_index=True,
                              column_config={
                                  "Cluster_Pay": st.column_config.NumberColumn("Cluster Pay", format="₹%d"),
                                  "cluster_cpo": st.column_config.NumberColumn("Cluster CPO", format="₹%.2f"),
                                  "excess_cpo": st.column_config.NumberColumn("Excess CPO", format="₹%.2f"),
                                  "LM_CPO": st.column_config.NumberColumn("LM CPO", format="₹%.2f"),
                                  "total_pay": st.column_config.NumberColumn("Total Pay", format="₹%d"),
                                  "monthly_burn": st.column_config.NumberColumn("Monthly Burn", format="₹%.0f"),
                                  "annual_burn": st.column_config.NumberColumn("Annual Burn", format="₹%.0f"),
                              })
                st.download_button(
                    "Download High Burn Hubs",
                    burn_hubs.to_csv(index=False), "high_burn_hubs.csv",
                    "text/csv", use_container_width=True
                )
            else:
                st.success(f"No hubs with Cluster CPO > ₹{_cpo_threshold:.2f} — network is efficient!")

        with cpo_tab4:
            st.markdown("""
            <div style="margin-bottom:12px;">
                <p style="font-size:0.85rem; color:var(--sfx-text-muted); margin:0;">
                    Clustered hubs where cluster cost per order exceeds the median — prime candidates for rate optimization.
                </p>
            </div>
            """, unsafe_allow_html=True)
            candidates = cpo_a.get_optimization_candidates(min_orders=100, top_n=30)
            if len(candidates) > 0:
                total_potential = candidates["potential_saving"].sum()
                annual_potential = candidates["potential_saving_annual"].sum()
                oc1, oc2, oc3 = st.columns(3)
                oc1.metric("Candidates", f"{len(candidates)}")
                oc2.metric("Monthly Saving Potential", f"₹{total_potential:,.0f}")
                oc3.metric("Annual Saving Potential", f"₹{annual_potential:,.0f}")
                st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
                st.dataframe(candidates, use_container_width=True, hide_index=True,
                              column_config={
                                  "Cluster_Pay": st.column_config.NumberColumn("Cluster Pay", format="₹%d"),
                                  "cluster_cpo": st.column_config.NumberColumn("Cluster CPO", format="₹%.2f"),
                                  "excess_cluster_cpo": st.column_config.NumberColumn("Excess CPO", format="₹%.2f"),
                                  "potential_saving": st.column_config.NumberColumn("Monthly Save", format="₹%.0f"),
                                  "potential_saving_annual": st.column_config.NumberColumn("Annual Save", format="₹%.0f"),
                                  "total_pay": st.column_config.NumberColumn("Total Pay", format="₹%d"),
                              })
            else:
                st.success("All clustered hubs are near optimal!")

        with cpo_tab5:
            st.markdown("""
            <div style="margin-bottom:12px;">
                <p style="font-size:0.85rem; color:var(--sfx-text-muted); margin:0;">
                    Actionable recommendations with estimated savings — reduce cluster rates at these hubs for maximum cost impact.
                </p>
            </div>
            """, unsafe_allow_html=True)
            recs = cpo_a.generate_recommendations(min_orders=100, top_n=20)
            if len(recs) > 0:
                total_monthly = recs["Monthly Saving"].sum()
                total_annual = recs["Annual Saving"].sum()
                rc1, rc2, rc3 = st.columns(3)
                rc1.metric("Recommendations", f"{len(recs)}")
                rc2.metric("Total Monthly Saving", f"₹{total_monthly:,.0f}")
                rc3.metric("Total Annual Saving", f"₹{total_annual:,.0f}")

                st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

                # Color-coded recommendation cards
                for _, rec in recs.iterrows():
                    priority_color = {"Critical": "#EF4444", "High": "#F59E0B", "Medium": "#3B82F6", "Low": "#10B981"}.get(str(rec["Priority"]), "#9CA3AF")
                    bg = "#1A1C24" if dark else "#ffffff"
                    st.markdown(f"""
                    <div style="padding:14px 18px;border-radius:12px;background:{bg};
                        margin-bottom:8px;box-shadow:{_card_shadow};
                        border-left:4px solid {priority_color};">
                        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
                            <div style="display:flex;align-items:center;gap:8px;">
                                <span style="width:8px;height:8px;border-radius:50%;background:{priority_color};"></span>
                                <span style="font-weight:700;font-size:0.9rem;">{rec['Hub']}</span>
                                <span style="font-size:0.7rem;padding:2px 8px;border-radius:10px;
                                    background:{priority_color}20;color:{priority_color};font-weight:600;">
                                    {rec['Priority']}</span>
                            </div>
                            <span style="font-weight:800;color:{_accent};font-size:0.9rem;">
                                ₹{rec['Monthly Saving']:,.0f}/mo</span>
                        </div>
                        <p style="font-size:0.78rem;color:var(--sfx-text-muted);margin:0 0 4px 0;">
                            {rec['Action']}</p>
                        <div style="font-size:0.7rem;color:var(--sfx-text-muted);display:flex;gap:16px;">
                            <span>Current: ₹{rec['Current Cluster CPO']:.2f}/order</span>
                            <span>Target: ₹{rec['Target Cluster CPO']:.2f}/order</span>
                            <span>Orders: {rec['Orders']:,}</span>
                            <span>Annual: ₹{rec['Annual Saving']:,.0f}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
                st.download_button(
                    "Download All Recommendations",
                    recs.to_csv(index=False), "cpo_optimization_recommendations.csv",
                    "text/csv", use_container_width=True
                )
            else:
                st.success("All hubs are optimally priced — no savings to capture.")

        with cpo_tab6:
            st.markdown("""
            <div style="margin-bottom:12px;">
                <p style="font-size:0.85rem; color:var(--sfx-text-muted); margin:0;">
                    Spatial polygon analysis — calculates actual hub-to-polygon distances, checks SOP compliance,
                    matches AWB shipments via point-in-polygon, and recommends rate decrease or radius expansion per polygon.
                </p>
            </div>
            """, unsafe_allow_html=True)

            # Initialize optimizer for this tab
            _opt_data = st.session_state.get("processed_data")
            _opt_hub = st.session_state.get("hub_data")
            _opt_awb = st.session_state.get("_hub_pin_counts_cache", {})

            if _opt_data is not None and len(_opt_data) > 0:
                _awb_parquet = _get_awb_cache_path().replace(".csv", ".parquet")
                _tab_optimizer = PolygonOptimizer(
                    cluster_df=_opt_data, hub_df=_opt_hub,
                    cpo_analytics=cpo_a, awb_counts=_opt_awb,
                    awb_parquet_path=_awb_parquet,
                )

                _opt_target = st.number_input(
                    "Monthly Savings Target (₹)",
                    min_value=100000, max_value=50000000, value=2000000, step=100000,
                    key="opt_savings_target",
                    help="Target monthly savings in rupees (default: 20,00,000 = 20L)"
                )

                if st.button("Run Spatial Polygon Analysis", key="run_poly_opt", use_container_width=True, type="primary"):
                    with st.spinner("Calculating distances, matching AWBs to polygons, checking SOP compliance..."):
                        _opt_summary = _tab_optimizer.get_optimization_summary(target_saving=_opt_target)
                        _opt_suggestions = _tab_optimizer.suggest_optimal_radius(target_saving=_opt_target)
                        _opt_before_after = _tab_optimizer.generate_before_after(_opt_suggestions)
                        _opt_warnings = _tab_optimizer.validate_no_hub_impact(_opt_suggestions)

                    # Store in session for persistence
                    st.session_state["_poly_opt_summary"] = _opt_summary
                    st.session_state["_poly_opt_suggestions"] = _opt_suggestions
                    st.session_state["_poly_opt_before_after"] = _opt_before_after
                    st.session_state["_poly_opt_warnings"] = _opt_warnings

                # Display results if available
                _opt_summary = st.session_state.get("_poly_opt_summary")
                _opt_suggestions = st.session_state.get("_poly_opt_suggestions")
                _opt_before_after = st.session_state.get("_poly_opt_before_after")
                _opt_warnings = st.session_state.get("_poly_opt_warnings")

                if _opt_summary is not None:
                    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

                    # Row 1: Core savings metrics
                    os1, os2, os3, os4 = st.columns(4)
                    os1.metric("Hubs Analyzed", f"{_opt_summary['total_hubs_analyzed']}")
                    os2.metric("Hubs to Optimize", f"{_opt_summary['hubs_with_changes']}")
                    os3.metric("Monthly Saving", f"₹{_opt_summary['total_monthly_saving']:,.0f}")
                    os4.metric("Annual Saving", f"₹{_opt_summary['total_annual_saving']:,.0f}")

                    # Row 2: Spatial metrics
                    ss1, ss2, ss3, ss4 = st.columns(4)
                    ss1.metric("Polygons Scanned", f"{_opt_summary.get('total_polygons_analyzed', 0)}")
                    ss2.metric("SOP Compliance", f"{_opt_summary.get('sop_compliance_pct', 0):.0f}%")
                    ss3.metric("Overcharged Polygons", f"{_opt_summary.get('overcharged_polygons', 0)}")
                    ss4.metric("Monthly Burn", f"₹{_opt_summary.get('total_monthly_burn', 0):,.0f}")

                    # Row 3: Exception & custom radius detection
                    _exc = _opt_summary.get("exception_rate_polygons", 0)
                    _cust = _opt_summary.get("custom_radius_polygons", 0)
                    if _exc > 0 or _cust > 0:
                        ex1, ex2, ex3, ex4 = st.columns(4)
                        ex1.metric("Exception Rates", f"{_exc}", help="Polygons with rates above SOP likely due to criticality")
                        ex2.metric("Custom Radii", f"{_cust}", help="Polygons using non-standard radius distances")
                        ex3.metric("Reviews Needed", f"{_opt_summary.get('review_exception_actions', 0)}", help="Exception polygons that need manual verification")
                        ex4.metric("Non-Standard", f"{_opt_summary.get('non_standard_polygons', 0)}", help="Polygons using intermediate SOP categories (C2/C4/C6/C8/C10)")

                    # Data source info
                    _ds = _opt_summary.get("data_source", "Unknown")
                    st.caption(f"Data source: {_ds} | Rate decreases: {_opt_summary.get('rate_decrease_actions', 0)} | Radius expansions: {_opt_summary.get('radius_expansion_actions', 0)} | Exception reviews: {_opt_summary.get('review_exception_actions', 0)}")

                    # Target progress
                    _tgt_pct = min(_opt_summary.get("target_pct", 0), 100)
                    _tgt_color = "#22c55e" if _opt_summary.get("target_met") else "#f59e0b"
                    st.markdown(f"""
                    <div style="margin:12px 0;">
                        <div style="display:flex;justify-content:space-between;font-size:0.8rem;margin-bottom:4px;">
                            <span>Target: ₹{_opt_target:,.0f}/month</span>
                            <span style="color:{_tgt_color};font-weight:700;">{_tgt_pct:.0f}%</span>
                        </div>
                        <div style="height:8px;background:#e5e7eb;border-radius:4px;overflow:hidden;">
                            <div style="height:100%;width:{_tgt_pct}%;background:{_tgt_color};border-radius:4px;"></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # Warnings
                    if _opt_warnings:
                        with st.expander(f"⚠️ {len(_opt_warnings)} Warnings", expanded=False):
                            for w in _opt_warnings:
                                st.caption(f"**{w['hub_name']}** [{w['severity']}]: {w['message']}")

                    # Suggestions table
                    if _opt_suggestions is not None and len(_opt_suggestions) > 0:
                        st.markdown("##### Hub-by-Hub Spatial Optimization")
                        _display_sug = _opt_suggestions.drop(columns=["changes"], errors="ignore")
                        st.dataframe(_display_sug, use_container_width=True, hide_index=True,
                                      column_config={
                                          "current_monthly_cost": st.column_config.NumberColumn("Current Cost", format="₹%.0f"),
                                          "suggested_monthly_cost": st.column_config.NumberColumn("New Cost", format="₹%.0f"),
                                          "monthly_saving": st.column_config.NumberColumn("Monthly Save", format="₹%.0f"),
                                          "annual_saving": st.column_config.NumberColumn("Annual Save", format="₹%.0f"),
                                          "current_avg_rate": st.column_config.NumberColumn("Curr Rate", format="₹%.2f"),
                                          "suggested_avg_rate": st.column_config.NumberColumn("New Rate", format="₹%.2f"),
                                          "current_cpo": st.column_config.NumberColumn("Curr CPO", format="₹%.2f"),
                                          "suggested_cpo": st.column_config.NumberColumn("New CPO", format="₹%.2f"),
                                          "impact_pct": st.column_config.NumberColumn("Impact %", format="%.1f%%"),
                                          "overcharged_polygons": st.column_config.NumberColumn("Overcharged", format="%d"),
                                          "avg_distance_km": st.column_config.NumberColumn("Avg Dist (km)", format="%.1f"),
                                          "sop_compliant_pct": st.column_config.NumberColumn("SOP %", format="%.0f%%"),
                                      })

                    # Before/After comparison
                    if _opt_before_after:
                        st.markdown("##### Before / After Comparison")
                        for comp in _opt_before_after[:20]:
                            _b = comp["before"]
                            _a = comp["after"]
                            _d = comp["delta"]
                            _pri = comp.get("priority", "Medium")
                            _pri_color = {"Critical": "#EF4444", "High": "#F59E0B", "Medium": "#3B82F6", "Low": "#10B981"}.get(_pri, "#9CA3AF")
                            _bg = "#1A1C24" if dark else "#ffffff"

                            with st.expander(
                                f"{'🔴' if _pri == 'Critical' else '🟡' if _pri == 'High' else '🔵' if _pri == 'Medium' else '🟢'} "
                                f"**{comp['hub_name']}** — Save ₹{_d['cost_reduction']:,.0f}/mo ({_d['pct_reduction']:.1f}%) "
                                f"| {comp.get('overcharged_polygons', 0)} overcharged | avg {comp.get('avg_distance_km', 0):.1f}km"
                            ):
                                _bc1, _bc2, _bc3 = st.columns(3)
                                _bc1.metric("Before (Monthly)", f"₹{_b['monthly_cost']:,.0f}")
                                _bc2.metric("After (Monthly)", f"₹{_a['monthly_cost']:,.0f}")
                                _bc3.metric("Annual Saving", f"₹{_d['annual_reduction']:,.0f}")

                                _cc1, _cc2, _cc3 = st.columns(3)
                                _cc1.metric("Before CPO", f"₹{_b['cpo']:.2f}")
                                _cc2.metric("After CPO", f"₹{_a['cpo']:.2f}")
                                _cc3.metric("SOP Compliance", f"{comp.get('sop_compliant_pct', 0):.0f}%")

                                if comp.get("changes"):
                                    st.caption("**Polygon-Level Actions:**")
                                    for chg in comp["changes"][:8]:
                                        st.caption(f"  - {chg['action']}")

                    # Download
                    if _opt_suggestions is not None and len(_opt_suggestions) > 0:
                        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
                        _dl_df = _opt_suggestions.drop(columns=["changes"], errors="ignore")
                        st.download_button(
                            "Download Spatial Optimization Report",
                            _dl_df.to_csv(index=False), "spatial_polygon_optimization_report.csv",
                            "text/csv", use_container_width=True
                        )
            else:
                st.info("Load cluster data first to run polygon analysis.")

    else:
        st.markdown("""
        <div style="text-align:center; padding:60px 0;">
            <p style="font-size:1rem; color:var(--sfx-text-muted);">
                CPO Excel file not found. Place <code>2026-02-19_cpo_with_base.xlsx</code> in the project root
                or upload via the sidebar.
            </p>
        </div>
        """, unsafe_allow_html=True)


# ── TAB 3: RECOMMENDATIONS ──
with tab3:
    cpo_a_r: CPOAnalytics = st.session_state.get("cpo_analytics")

    st.markdown("""
    <div style="margin-bottom:20px;">
        <h2 style="font-size:1.25rem; margin:0 0 4px 0;">Optimization Recommendations</h2>
        <p style="font-size:0.85rem; color:var(--sfx-text-muted); margin:0;">Prioritized cost-saving actions based on hub-level CPO analysis.</p>
    </div>
    """, unsafe_allow_html=True)

    if cpo_a_r and cpo_a_r.is_loaded:
        recs_full = cpo_a_r.generate_recommendations(min_orders=100, top_n=30)
        if len(recs_full) > 0:
            rc1, rc2, rc3, rc4 = st.columns(4)
            rc1.metric("Total Actions", f"{len(recs_full)}")
            critical_count = len(recs_full[recs_full["Priority"] == "Critical"])
            rc2.metric("Critical", f"{critical_count}")
            rc3.metric("Total Monthly Saving", f"₹{recs_full['Monthly Saving'].sum():,.0f}")
            rc4.metric("Total Annual Saving", f"₹{recs_full['Annual Saving'].sum():,.0f}")

            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

            st.dataframe(
                recs_full,
                use_container_width=True, hide_index=True,
                column_config={
                    "Current Cluster CPO": st.column_config.NumberColumn(format="₹%.2f"),
                    "Target Cluster CPO": st.column_config.NumberColumn(format="₹%.2f"),
                    "Excess (₹/order)": st.column_config.NumberColumn(format="₹%.2f"),
                    "Monthly Saving": st.column_config.NumberColumn(format="₹%.0f"),
                    "Annual Saving": st.column_config.NumberColumn(format="₹%.0f"),
                }
            )

            st.download_button(
                "Download All Recommendations",
                recs_full.to_csv(index=False), "all_recommendations.csv",
                "text/csv", use_container_width=True
            )
        else:
            st.success("All hubs are optimally priced — no actions required.")
    else:
        st.markdown("""
        <div style="text-align:center; padding:60px 0;">
            <p style="font-size:1rem; color:var(--sfx-text-muted);">
                Place <code>2026-02-19_cpo_with_base.xlsx</code> in the project root for recommendations.</p>
        </div>
        """, unsafe_allow_html=True)


# ── TAB 4: DATA ──
with tab4:
    if st.session_state.data_loaded:
        cluster_df = st.session_state.cluster_data
        hub_df = st.session_state.hub_data
        distinct_hubs = cluster_df['hub_id'].nunique() if 'hub_id' in cluster_df.columns else hub_df['id'].nunique()
        cache_d = st.session_state.get("cache_date", "")

        st.markdown("""
        <div style="margin-bottom:20px;">
            <h2 style="font-size:1.25rem; margin:0 0 4px 0;">Data Explorer</h2>
            <p style="font-size:0.85rem; color:var(--sfx-text-muted); margin:0;">Browse and download raw cluster, hub, and AWB datasets.</p>
        </div>
        """, unsafe_allow_html=True)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Clusters", f"{len(cluster_df):,}")
        c2.metric("Distinct Hubs", f"{distinct_hubs:,}")
        c3.metric("Unique Pincodes", f"{cluster_df['pincode'].nunique():,}" if 'pincode' in cluster_df.columns else "N/A")
        c4.metric("Data Date", cache_d.split(" ")[0] if cache_d else "Local CSV")

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        col_d1, col_d2, col_d3 = st.columns(3)
        date_str = datetime.now().strftime('%d%m%Y')
        with col_d1:
            st.download_button("Download Clusters CSV", cluster_df.to_csv(index=False),
                              f"clustering_live_{date_str}.csv", "text/csv", use_container_width=True)
        with col_d2:
            st.download_button("Download Hub Locations CSV", hub_df.to_csv(index=False),
                              f"hub_Lat_Long{date_str}.csv", "text/csv", use_container_width=True)
        with col_d3:
            kp = st.session_state.get('kepler_path')
            if kp and Path(kp).exists():
                st.download_button("Download Kepler CSV", pd.read_csv(kp).to_csv(index=False),
                                  f"kepler_gl_final_main_{date_str}_csv.csv", "text/csv", use_container_width=True)
            else:
                st.caption("Kepler CSV available after BigQuery fetch")

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        ptab1, ptab2, ptab3 = st.tabs(["Clusters Preview", "Hub Locations Preview", "AWB Data"])
        with ptab1:
            st.dataframe(cluster_df.head(100), use_container_width=True, hide_index=True)
        with ptab2:
            st.dataframe(hub_df.head(100), use_container_width=True, hide_index=True)

        # ── AWB Data Tab ──
        with ptab3:
            st.markdown("""
            <div style="margin-bottom:12px;">
                <p style="font-size:0.85rem; color:var(--sfx-text-muted); margin:0;">
                    AWB (Air Waybill) data with lat/long coordinates. Fetch from BigQuery
                    or upload a CSV. Data is stored as Parquet for fast loading (no CSV export needed).
                </p>
            </div>
            """, unsafe_allow_html=True)

            # ── Manual AWB CSV Upload ──
            st.markdown("##### Upload AWB CSV")
            _awb_file = st.file_uploader(
                "Upload AWB CSV file", type=["csv"],
                help="Upload any CSV with shipment coordinates. Columns are auto-detected (lat, long, hub, pincode, etc.)",
                key="awb_csv_upload"
            )
            if _awb_file is not None:
                try:
                    _uploaded_awb = pd.read_csv(_awb_file, low_memory=False)
                    _uploaded_awb, _norm_err = _normalize_awb_df(_uploaded_awb)
                    if _norm_err:
                        st.error(_norm_err)
                    else:
                        _detected_cols = [c for c in ["lat", "long", "hub", "pincode", "fwd_del_awb_number", "order_date", "payment_category"] if c in _uploaded_awb.columns]
                        st.success(f"Loaded **{len(_uploaded_awb):,}** records. Detected: {', '.join(_detected_cols)}")
                        _uc1, _uc2 = st.columns(2)
                        with _uc1:
                            if st.button("Save to Cache & Use", key="save_awb_upload", use_container_width=True, type="primary"):
                                with st.spinner(f"Saving {len(_uploaded_awb):,} records..."):
                                    _save_awb_cache(_uploaded_awb)
                                st.session_state["_awb_cached_df"] = _uploaded_awb
                                st.session_state["_awb_processed_id"] = f"dw_{len(_uploaded_awb)}"
                                _invalidate_pip_cache()
                                st.success(f"Saved {len(_uploaded_awb):,} AWB records. Maps Studio will recompute polygon matches.")
                                st.rerun()
                        with _uc2:
                            st.caption(f"Preview: {len(_uploaded_awb):,} rows, {len(_uploaded_awb.columns)} columns")
                        st.dataframe(_uploaded_awb.head(100), use_container_width=True, hide_index=True)
                except Exception as e:
                    st.error(f"Error reading CSV: {e}")

            st.markdown("---")
            st.markdown("##### BigQuery Fetch")
            awb_meta = get_awb_cache_info()
            _awb_preview = get_awb_preview(200)

            if awb_meta:
                ac1, ac2, ac3 = st.columns(3)
                ac1.metric("AWB Records", f"{awb_meta.get('record_count', 0):,}")
                ac2.metric("Cached Date", awb_meta.get("fetched_date", "N/A"))
                ac3.metric("Fetched At", awb_meta.get("fetched_time", "N/A").split(" ")[-1] if awb_meta.get("fetched_time") else "N/A")

            # ── Pincode source selection ──
            _pin_source = st.radio(
                "Pincode source for AWB query",
                ["Live Clusters (auto)", "Manual Entry"],
                horizontal=True, key="awb_pin_source",
                help="Choose whether to use pincodes from live cluster data or enter them manually"
            )

            _manual_pins = []
            if _pin_source == "Manual Entry":
                _pin_text = st.text_area(
                    "Enter pincodes (comma, space, or newline separated)",
                    placeholder="560001, 560002, 560003\n110001\n400001",
                    height=100, key="manual_pincodes_input"
                )
                if _pin_text.strip():
                    # Parse pincodes from any separator: comma, space, newline, semicolon
                    import re
                    _manual_pins = [p.strip() for p in re.split(r'[,\s;]+', _pin_text.strip()) if p.strip()]
                    _manual_pins = [p for p in _manual_pins if p.isdigit() and len(p) == 6]
                    if _manual_pins:
                        st.caption(f"{len(_manual_pins)} valid pincodes entered")
                    elif _pin_text.strip():
                        st.warning("No valid 6-digit pincodes found. Enter pincodes like: 560001, 560002")

            # ── Pincode preview before fetch ──
            _preview_pins = []
            _preview_source = ""
            if _pin_source == "Manual Entry" and _manual_pins:
                _preview_pins = _manual_pins
                _preview_source = "Manual Entry"
            elif _pin_source == "Live Clusters (auto)" and st.session_state.get("data_loaded") and st.session_state.get("cluster_data") is not None:
                _live_cd = st.session_state.cluster_data
                if "pincode" in _live_cd.columns:
                    _preview_pins = (
                        _live_cd["pincode"]
                        .astype(str).str.strip()
                        .str.replace(".0", "", regex=False)
                        .unique().tolist()
                    )
                    _preview_pins = [p for p in _preview_pins if p and p != 'nan' and p != '']
                    _preview_source = "Live Clusters"

            if _preview_pins:
                _sorted_pins = sorted(_preview_pins)
                with st.expander(f"📋 **{len(_preview_pins):,} pincodes** will be queried from {_preview_source} — click to preview", expanded=False):
                    st.caption(f"All {len(_preview_pins):,} unique pincodes that will be dynamically inserted into the BigQuery `WHERE sg.pincode IN (...)` clause:")
                    # Show in a compact grid
                    _pin_display = ", ".join(_sorted_pins[:200])
                    if len(_sorted_pins) > 200:
                        _pin_display += f" ... and {len(_sorted_pins) - 200:,} more"
                    st.code(_pin_display, language=None)
                    st.caption(f"First: `{_sorted_pins[0]}` — Last: `{_sorted_pins[-1]}`")
            elif _pin_source == "Live Clusters (auto)" and not st.session_state.get("data_loaded"):
                st.info("⚠️ Fetch live clusters first (sidebar) to see pincode preview", icon="ℹ️")

            awb_col1, awb_col2 = st.columns(2)
            with awb_col1:
                _fetch_label = f"Fetch AWB Data ({len(_preview_pins):,} pincodes)" if _preview_pins else "Fetch AWB Data"
                if _pin_source == "Manual Entry":
                    _fetch_label = f"Fetch AWB for {len(_manual_pins)} Pincodes"
                if st.button(_fetch_label, key="fetch_awb_btn", use_container_width=True,
                             disabled=(_pin_source == "Manual Entry" and len(_manual_pins) == 0)):
                    bq_client = st.session_state.get("bq_client")
                    if not bq_client:
                        st.error("Connect to BigQuery first (sidebar → Login with Google)")
                    else:
                        # Clear old AWB data immediately
                        st.session_state.pop("_awb_cached_df", None)
                        st.session_state.pop("_awb_processed_id", None)

                        progress = st.progress(0, text="Starting AWB fetch...")
                        status = st.empty()

                        def awb_progress(pct, msg):
                            progress.progress(min(int(pct * 100), 100), text=msg)
                            status.caption(msg)

                        if _pin_source == "Manual Entry" and _manual_pins:
                            status.caption(f"Building query with {len(_manual_pins)} manually entered pincodes...")
                            df, err = fetch_awb_data(
                                bq_client, force_refresh=True,
                                progress_cb=awb_progress, manual_pincodes=_manual_pins
                            )
                            _pin_count_label = len(_manual_pins)
                        else:
                            if not st.session_state.data_loaded:
                                progress.empty()
                                status.empty()
                                st.error("Fetch live clusters first (sidebar → Fetch from BigQuery)")
                                df, err = None, "skipped"
                            else:
                                _live_cluster_df = st.session_state.cluster_data
                                _pin_count_label = _live_cluster_df['pincode'].nunique() if 'pincode' in _live_cluster_df.columns else 0
                                status.caption(f"Building query with {_pin_count_label:,} pincodes from live clusters...")
                                df, err = fetch_awb_data(
                                    bq_client, _live_cluster_df,
                                    force_refresh=True, progress_cb=awb_progress
                                )

                        if err and err != "skipped":
                            progress.empty()
                            status.empty()
                            st.error(f"AWB fetch failed: {err}")
                        elif df is not None:
                            st.session_state["_awb_cached_df"] = df
                            st.session_state["_awb_processed_id"] = f"bq_{len(df)}"
                            _invalidate_pip_cache()
                            progress.empty()
                            status.empty()
                            st.success(f"✅ Replaced AWB data: **{len(df):,}** records for **{_pin_count_label:,}** pincodes")
                            st.rerun()

            with awb_col2:
                if _awb_preview is not None:
                    st.metric("Unique Hubs", f"{_awb_preview['unique_hubs']:,}")

            if _awb_preview is not None:
                st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
                st.caption(f"Preview: first 200 of {_awb_preview['total_rows']:,} records (stored as Parquet for fast loading)")
                st.dataframe(_awb_preview["preview_df"], use_container_width=True, hide_index=True)

# ── TAB 5: MAPS STUDIO ──
with tab5:
    from free_maps_renderer import get_free_maps_html

    _ms_cluster_geojson = None
    _ms_hub_list = None
    _ms_awb_data = None
    _ms_hexbin_data = None

    if st.session_state.get("data_loaded") and st.session_state.get("processed_data") is not None:
        try:
            from shapely.geometry import mapping as _shp_mapping, Point as _shp_Point

            _ms_proc = st.session_state.processed_data
            _ms_hub_df = st.session_state.hub_data
            _ms_renderer = MapRenderer()

            # ── Fast AWB stats via DuckDB (no full DataFrame load) ──
            _hub_pin_counts = st.session_state.get("_hub_pin_counts_cache")
            if _hub_pin_counts is None:
                _hub_pin_counts = get_hub_pincode_counts()
                if _hub_pin_counts:
                    st.session_state["_hub_pin_counts_cache"] = _hub_pin_counts

            _cluster_awb_stats = {}
            if _hub_pin_counts:
                # ── Build hub-name mapping via lat/long for renamed hubs ──
                # Use the full hub location file (11K+ hubs) instead of session hub_df
                # (which only has ~1K hubs from cluster data) so renamed hubs can be matched.
                _awb_hub_names = set(k[0] for k in _hub_pin_counts.keys())
                _hub_name_map = {}  # cluster_hub_name -> awb_hub_name
                _full_hub_csv = None
                _manifest = DataLoader().get_cache_manifest()
                if _manifest:
                    _full_hub_csv = _manifest.get("hub_csv")
                if _full_hub_csv and Path(_full_hub_csv).exists():
                    _loc_df = pd.read_csv(_full_hub_csv).dropna(subset=["latitude", "longitude"]).copy()
                    _loc_df["lat_r"] = _loc_df["latitude"].round(3)
                    _loc_df["lng_r"] = _loc_df["longitude"].round(3)
                    # Group all hub names by rounded location
                    _loc_to_names = {}
                    _name_col = "name" if "name" in _loc_df.columns else "hub_name"
                    for _, _r in _loc_df.iterrows():
                        _n = str(_r.get(_name_col, ""))
                        _lk = (_r["lat_r"], _r["lng_r"])
                        _loc_to_names.setdefault(_lk, []).append(_n)
                    # For each cluster hub_name not in AWB, find AWB name at same location
                    _cluster_hub_names = set(_ms_proc["hub_name"].dropna().unique())
                    for _ch in _cluster_hub_names - _awb_hub_names:
                        _ch_row = _loc_df[_loc_df[_name_col] == _ch]
                        if _ch_row.empty:
                            continue
                        _lk = (_ch_row.iloc[0]["lat_r"], _ch_row.iloc[0]["lng_r"])
                        for _candidate in _loc_to_names.get(_lk, []):
                            if _candidate in _awb_hub_names:
                                _hub_name_map[_ch] = _candidate
                                break

                # ── Build pincode-only fallback counts ──
                _pin_only_counts = {}
                for (_h, _p), _c in _hub_pin_counts.items():
                    _pin_only_counts[_p] = _pin_only_counts.get(_p, 0) + _c

                # Map each cluster polygon to its AWB count via hub_name+pincode
                for _t in _ms_proc.itertuples(index=False):
                    _cc = str(getattr(_t, 'cluster_code', ''))
                    _hname = str(getattr(_t, 'hub_name', ''))
                    _pin_raw = getattr(_t, 'pincode', '')
                    # Fix pincode format: strip '.0' from float-converted pincodes
                    try:
                        _pin = str(int(float(_pin_raw))) if _pin_raw not in (None, '', 'nan') else ''
                    except (ValueError, TypeError):
                        _pin = str(_pin_raw).replace('.0', '').strip()
                    _rate = float(getattr(_t, 'surge_amount', 0))
                    # 1) Exact hub_name + pincode match
                    _awb_n = _hub_pin_counts.get((_hname, _pin), 0)
                    # 2) Lat/long-mapped hub name fallback
                    if _awb_n == 0 and _hname in _hub_name_map:
                        _awb_n = _hub_pin_counts.get((_hub_name_map[_hname], _pin), 0)
                    # 3) Pincode-only fallback (all hubs serving this pincode)
                    if _awb_n == 0:
                        _awb_n = _pin_only_counts.get(_pin, 0)
                    _cluster_awb_stats[_cc] = {
                        "awb_count": _awb_n,
                        "total_cost": round(_awb_n * _rate, 1),
                        "rate": _rate,
                    }

            # ── Build cluster GeoJSON with AWB stats (vectorized) ──
            def _rp(coords):
                if isinstance(coords, (list, tuple)) and len(coords) > 0:
                    if isinstance(coords[0], (list, tuple)):
                        return [_rp(c) for c in coords]
                    return [round(float(v), 4) for v in coords]
                return coords

            _valid = _ms_proc[_ms_proc['geometry'].apply(
                lambda g: g is not None and not (hasattr(g, 'is_empty') and g.is_empty)
            )].copy()

            _ms_features = []
            # Use itertuples for ~10x speed over iterrows
            _col_list = list(_valid.columns)
            for _t in _valid.itertuples(index=False):
                _geom = _t[_col_list.index('geometry')]
                try:
                    _geo = _shp_mapping(_geom)
                    _geo["coordinates"] = _rp(_geo["coordinates"])
                except Exception:
                    continue

                _cc = str(getattr(_t, 'cluster_code', 'N/A'))
                _rate = float(getattr(_t, 'surge_amount', 0))
                _stats = _cluster_awb_stats.get(_cc, {})
                _awb_n = _stats.get("awb_count", 0)
                _total_cost = _stats.get("total_cost", round(_rate * _awb_n, 1))
                _centroid = _geom.centroid

                _ms_features.append({
                    "type": "Feature",
                    "geometry": _geo,
                    "properties": {
                        "hub_id": str(getattr(_t, 'hub_id', '')),
                        "hub_name": str(getattr(_t, 'hub_name', 'N/A')),
                        "cluster_code": _cc,
                        "pincode": str(getattr(_t, 'pincode', '')),
                        "surge_rate": str(getattr(_t, 'cluster_category', f'Rs.{_rate}')),
                        "rate_num": _rate,
                        "rate_category": str(getattr(_t, 'rate_category', 'N/A')),
                        "fillColor": _ms_renderer._get_rate_color(_rate),
                        "fillOpacity": "0.4",
                        "awb_count": _awb_n,
                        "total_cost": _total_cost,
                        "center_lat": round(_centroid.y, 5),
                        "center_lon": round(_centroid.x, 5),
                    },
                })
            _ms_cluster_geojson = {"type": "FeatureCollection", "features": _ms_features}

            # ── Build hub list (vectorized) ──
            if _ms_hub_df is not None and len(_ms_hub_df) > 0:
                _hub_valid = _ms_hub_df.dropna(subset=["latitude", "longitude"])
                _ms_hub_list = [{
                    "id": str(r.get("id", "")),
                    "name": str(r.get("name", "Unknown")),
                    "lat": round(float(r["latitude"]), 5),
                    "lng": round(float(r["longitude"]), 5),
                    "category": str(r.get("hub_category", "")),
                } for r in _hub_valid.to_dict("records")]

            # ── Load pre-computed hexbin cache (fast, no 22M row processing) ──
            _hex_cache = st.session_state.get("_ms_hex_cache")
            if _hex_cache:
                _ms_hexbin_data = _hex_cache.get("hexbin", [])
                _ms_awb_data = _hex_cache.get("awb_sample", [])
            else:
                _ms_hexbin_data = load_hexbin_cache()
                _ms_awb_data = load_awb_sample_cache()
                if _ms_hexbin_data:
                    st.session_state["_ms_hex_cache"] = {
                        "hexbin": _ms_hexbin_data,
                        "awb_sample": _ms_awb_data,
                    }
        except Exception as e:
            st.caption(f"Could not prepare map data: {e}")

    maps_html = get_free_maps_html(_ms_cluster_geojson, _ms_hub_list, _ms_awb_data, _ms_hexbin_data)

    # Full-height map studio — hide Streamlit chrome for immersive view
    st.markdown("""
    <style>
    iframe { min-height: calc(100vh - 80px) !important; }
    </style>
    """, unsafe_allow_html=True)
    components.html(maps_html, height=900, scrolling=False)

# ── TAB 6: GANDALF AI ──
with tab6:
  try:
    # Initialize GANDALF engine
    if "gandalf_engine" not in st.session_state:
        st.session_state["gandalf_engine"] = GandalfEngine()

    _gandalf = st.session_state["gandalf_engine"]

    # Initialize polygon optimizer if data available
    _poly_opt = None
    if st.session_state.get("processed_data") is not None:
        try:
            _poly_opt = PolygonOptimizer(
                cluster_df=st.session_state.get("processed_data"),
                hub_df=st.session_state.get("hub_data"),
                cpo_analytics=st.session_state.get("cpo_analytics"),
                awb_counts=st.session_state.get("_hub_pin_counts_cache", {}),
                awb_parquet_path=_get_awb_cache_path().replace(".csv", ".parquet"),
            )
        except Exception:
            pass

    _gandalf.update_data(
        cluster_df=st.session_state.get("cluster_data"),
        hub_df=st.session_state.get("hub_data"),
        processed_df=st.session_state.get("processed_data"),
        cpo_analytics=st.session_state.get("cpo_analytics"),
        awb_counts=st.session_state.get("_hub_pin_counts_cache", {}),
        polygon_optimizer=_poly_opt,
    )

    _briefing = _gandalf.generate_briefing()
    _health = _gandalf.analyze_health()
    _llm_status = get_llm_status()

    # ── LLM Status Badge ──
    if _llm_status["any_available"]:
        _llm_label = _llm_status["preferred"].title()
        if _llm_status["preferred"] == "ollama" and _llm_status["ollama_models"]:
            _llm_label += f" ({_llm_status['ollama_models'][0]})"
        _llm_html = f'<span style="background:#16a34a;color:#fff;padding:3px 12px;border-radius:12px;font-size:11px;font-weight:600">{_llm_label} Online</span>'
    else:
        _llm_html = '<span style="background:#92400e;color:#fde047;padding:3px 12px;border-radius:12px;font-size:11px;font-weight:600">Rule-Based Mode</span>'

    # ── Briefing Banner ──
    _s = _briefing.get("summary", {})
    _metrics_html = ""
    for _m in _briefing.get("key_metrics", []):
        _metrics_html += f"""
        <div style="text-align:center;min-width:140px">
            <div style="font-size:11px;color:#8b949e;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px">{_m['label']}</div>
            <div style="font-size:18px;font-weight:800;color:#e6edf3;font-family:'Montserrat',sans-serif">{_m['value']}</div>
        </div>"""

    _grade_color = {"A+": "#16a34a", "A": "#22c55e", "B": "#eab308", "C": "#f97316", "D": "#ef4444", "F": "#dc2626"}.get(_health["grade"], "#6b7280")

    st.markdown(f"""
    <div class="gandalf-briefing-banner">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;flex-wrap:wrap;gap:12px">
            <div>
                <div style="font-size:24px;font-weight:800;color:#e6edf3;font-family:'Montserrat',sans-serif;letter-spacing:-0.03em">
                    G.A.N.D.A.L.F.
                </div>
                <div style="font-size:11px;color:#6fd9bc;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;margin-top:2px">
                    Guided Analytics Network for Delivery & Logistics Facilitation
                </div>
            </div>
            <div style="display:flex;align-items:center;gap:12px">
                {_llm_html}
                <div style="background:{_grade_color};color:#fff;padding:4px 14px;border-radius:12px;font-size:12px;font-weight:700;font-family:'Montserrat',sans-serif">
                    Health: {_health['grade']} ({_health['score']}/{_health['max_score']})
                </div>
            </div>
        </div>
        <div style="font-size:14px;color:#c9d1d9;margin-bottom:18px;line-height:1.5">{_briefing.get('greeting', '')}</div>
        <div style="display:flex;gap:24px;flex-wrap:wrap;justify-content:flex-start">{_metrics_html}</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Alerts & Actions ──
    _gcol1, _gcol2 = st.columns(2)
    with _gcol1:
        st.markdown("##### Alerts")
        _alerts = _briefing.get("alerts", [])
        if _alerts:
            for _al in _alerts:
                _sev_cls = f"gandalf-alert-{_al['severity']}"
                st.markdown(f"""<div class="gandalf-alert-card {_sev_cls}">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
                        <span class="gandalf-priority-badge gandalf-priority-{_al['severity']}">{_al['severity'].upper()}</span>
                        <span style="font-size:13px;font-weight:600;color:#e6edf3">{_al['title']}</span>
                    </div>
                    <div style="font-size:12px;color:#8b949e">{_al.get('action', '')}</div>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div class="gandalf-insight-card">All systems nominal. No alerts at this time.</div>', unsafe_allow_html=True)

    with _gcol2:
        st.markdown("##### Priority Actions")
        _actions = _briefing.get("top_actions", [])
        if _actions:
            for _act in _actions:
                _conf_pct = f"{_act.get('confidence', 0) * 100:.0f}%" if _act.get('confidence') else ""
                st.markdown(f"""<div class="gandalf-alert-card gandalf-alert-{_act['priority']}">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
                        <span class="gandalf-priority-badge gandalf-priority-{_act['priority']}">{_act['priority'].upper()}</span>
                        <span style="font-size:13px;font-weight:600;color:#e6edf3">{_act['title']}</span>
                    </div>
                    <div style="font-size:12px;color:#8b949e">
                        {f'Savings: {_act["savings"]}' if _act.get('savings') else ''}
                        {f' &middot; Confidence: {_conf_pct}' if _conf_pct else ''}
                    </div>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div class="gandalf-insight-card">No immediate actions required.</div>', unsafe_allow_html=True)

    # ── Insights ──
    _insights = _briefing.get("insights", [])
    if _insights:
        st.markdown("##### Insights")
        for _ins in _insights:
            st.markdown(f'<div class="gandalf-insight-card">{_ins}</div>', unsafe_allow_html=True)

    # ── Chat Interface ──
    st.markdown("---")
    st.markdown("### Ask GANDALF")
    st.caption("Ask anything about your logistics network, costs, hubs, or optimization opportunities.")

    if "gandalf_chat_history" not in st.session_state:
        st.session_state["gandalf_chat_history"] = []

    for _msg in st.session_state["gandalf_chat_history"]:
        with st.chat_message(_msg["role"]):
            st.markdown(_msg["content"])

    if _user_q := st.chat_input("Ask GANDALF anything...", key="gandalf_chat_input"):
        st.session_state["gandalf_chat_history"].append({"role": "user", "content": _user_q})
        with st.chat_message("user"):
            st.markdown(_user_q)

        with st.chat_message("assistant"):
            with st.spinner("GANDALF is analyzing..."):
                _data_ctx = json.dumps({
                    "summary": _briefing.get("summary", {}),
                    "health_grade": _health.get("grade", "N/A"),
                    "alerts_count": len(_briefing.get("alerts", [])),
                    "actions_count": len(_briefing.get("top_actions", [])),
                }) if _briefing.get("summary") else ""

                _llm_resp = None
                if _llm_status["any_available"]:
                    try:
                        _llm_resp = gandalf_chat(
                            _user_q, data_context=_data_ctx,
                            history=[{"role": m["role"], "content": m["content"]}
                                     for m in st.session_state["gandalf_chat_history"][-6:]])
                    except Exception:
                        _llm_resp = None

                if _llm_resp:
                    _response = _llm_resp
                else:
                    _result = _gandalf.answer_query(_user_q)
                    _response = _result["text"]

                st.markdown(_response)
                st.session_state["gandalf_chat_history"].append({"role": "assistant", "content": _response})

    # ── Quick Action Buttons ──
    st.markdown("#### Quick Actions")
    _qa1, _qa2, _qa3, _qa4, _qa5, _qa6, _qa7, _qa8, _qa9, _qa10 = st.columns(10)
    with _qa1:
        if st.button("Expensive Hubs", key="gq1", use_container_width=True):
            _r = _gandalf.answer_query("expensive hubs")
            st.session_state["gandalf_chat_history"].append({"role": "user", "content": "Show expensive hubs"})
            st.session_state["gandalf_chat_history"].append({"role": "assistant", "content": _r["text"]})
            st.rerun()
    with _qa2:
        if st.button("Merge Candidates", key="gq2", use_container_width=True):
            _r = _gandalf.answer_query("merge clusters")
            st.session_state["gandalf_chat_history"].append({"role": "user", "content": "Which clusters should I merge?"})
            st.session_state["gandalf_chat_history"].append({"role": "assistant", "content": _r["text"]})
            st.rerun()
    with _qa3:
        if st.button("Reduce Payouts", key="gq3", use_container_width=True):
            _r = _gandalf.answer_query("reduce payout")
            st.session_state["gandalf_chat_history"].append({"role": "user", "content": "Where can I reduce payout?"})
            st.session_state["gandalf_chat_history"].append({"role": "assistant", "content": _r["text"]})
            st.rerun()
    with _qa4:
        if st.button("Run Diagnostics", key="gq4", use_container_width=True):
            _r = _gandalf.answer_query("health check")
            st.session_state["gandalf_chat_history"].append({"role": "user", "content": "Run health check"})
            st.session_state["gandalf_chat_history"].append({"role": "assistant", "content": _r["text"]})
            st.rerun()
    with _qa5:
        if st.button("High Burn Hubs", key="gq5", use_container_width=True):
            _r = _gandalf.answer_query("high burn cpo hubs")
            st.session_state["gandalf_chat_history"].append({"role": "user", "content": "Show high burn hubs (CPO > Rs.1)"})
            st.session_state["gandalf_chat_history"].append({"role": "assistant", "content": _r["text"]})
            st.rerun()
    with _qa6:
        if st.button("Optimize Polygons", key="gq6", use_container_width=True):
            _r = _gandalf.answer_query("optimize polygon clusters")
            st.session_state["gandalf_chat_history"].append({"role": "user", "content": "Analyze polygon optimization for all hubs"})
            st.session_state["gandalf_chat_history"].append({"role": "assistant", "content": _r["text"]})
            st.rerun()
    with _qa7:
        if st.button("Save 20L Plan", key="gq7", use_container_width=True):
            _r = _gandalf.answer_query("save 20 lakh plan")
            st.session_state["gandalf_chat_history"].append({"role": "user", "content": "How can I save 20 lakh monthly?"})
            st.session_state["gandalf_chat_history"].append({"role": "assistant", "content": _r["text"]})
            st.rerun()
    with _qa8:
        if st.button("SOP Compliance", key="gq8", use_container_width=True):
            _r = _gandalf.answer_query("check sop compliance")
            st.session_state["gandalf_chat_history"].append({"role": "user", "content": "Check SOP compliance for all polygons"})
            st.session_state["gandalf_chat_history"].append({"role": "assistant", "content": _r["text"]})
            st.rerun()
    with _qa9:
        if st.button("Exception Rates", key="gq9", use_container_width=True):
            _r = _gandalf.answer_query("analyze exception rate polygons")
            st.session_state["gandalf_chat_history"].append({"role": "user", "content": "Analyze exception rate polygons"})
            st.session_state["gandalf_chat_history"].append({"role": "assistant", "content": _r["text"]})
            st.rerun()
    with _qa10:
        if st.button("Custom Radii", key="gq10", use_container_width=True):
            _r = _gandalf.answer_query("analyze custom radius polygons")
            st.session_state["gandalf_chat_history"].append({"role": "user", "content": "Analyze custom radius polygons"})
            st.session_state["gandalf_chat_history"].append({"role": "assistant", "content": _r["text"]})
            st.rerun()
  except Exception as _gandalf_err:
    st.error(f"GANDALF AI initialization error: {_gandalf_err}")
    import traceback
    st.code(traceback.format_exc())
