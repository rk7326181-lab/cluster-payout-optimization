"""
Precision Navigator — Authentication Page
Login page matching the Shadowfax "Precision Navigator" design system.
Uses components.html() for the visual left panel to avoid Streamlit
HTML rendering limitations with large/complex markup.
"""

import streamlit as st
import streamlit.components.v1 as components


# ── Demo credentials ──
_VALID_USERS = {
    "admin@shadowfax.in": "shadowfax2026",
    "admin": "shadowfax2026",
    "demo@shadowfax.in": "demo2026",
    "demo": "demo2026",
}


def check_credentials(email: str, password: str) -> bool:
    return _VALID_USERS.get(email.strip().lower()) == password


def _get_logo_b64() -> str:
    """Return base64-encoded logo or empty string."""
    try:
        import base64
        from pathlib import Path
        logo = Path(__file__).parent.parent / "brand_assets" / "logo.jpeg"
        if logo.exists():
            return base64.b64encode(logo.read_bytes()).decode()
    except Exception:
        pass
    return ""


def _build_left_panel_html(logo_b64: str) -> str:
    """Build a self-contained HTML page for the left branding panel."""
    if logo_b64:
        logo_el = f'<img src="data:image/jpeg;base64,{logo_b64}" style="width:30px;height:30px;object-fit:contain;border-radius:6px;" />'
    else:
        logo_el = '<span style="color:#fff;font-size:20px;line-height:1;">&#9654;</span>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html, body {{ height:100%; overflow:hidden; }}
  body {{ font-family:'Inter',sans-serif; background:#f5f3f3; }}
</style>
</head>
<body>
<div style="
    height:100vh; background:#f5f3f3;
    display:flex; flex-direction:column;
    justify-content:space-between;
    padding:2.5rem; position:relative; overflow:hidden;
">
    <div style="position:absolute;top:-80px;right:-80px;width:320px;height:320px;
        background:radial-gradient(circle,rgba(0,138,113,0.08) 0%,transparent 70%);
        border-radius:50%;pointer-events:none;"></div>
    <div style="position:absolute;bottom:-60px;left:-60px;width:240px;height:240px;
        background:radial-gradient(circle,rgba(0,138,113,0.06) 0%,transparent 70%);
        border-radius:50%;pointer-events:none;"></div>

    <div style="position:relative;z-index:1;">
        <div style="display:flex;align-items:center;gap:12px;">
            <div style="width:44px;height:44px;
                background:linear-gradient(135deg,#008A71 0%,#00846c 100%);
                border-radius:12px;display:flex;align-items:center;justify-content:center;
                box-shadow:0px 8px 24px rgba(0,107,87,0.25);">
                {logo_el}
            </div>
            <div>
                <div style="font-family:'Montserrat',sans-serif;font-weight:800;
                    font-size:1.25rem;color:#006955;letter-spacing:-0.03em;line-height:1.1;">
                    Shadowfax</div>
                <div style="font-family:'Montserrat',sans-serif;font-size:0.6rem;
                    font-weight:600;color:#6d7a75;text-transform:uppercase;
                    letter-spacing:0.12em;">Precision Navigator</div>
            </div>
        </div>
    </div>

    <div style="position:relative;z-index:1;max-width:380px;">
        <h2 style="font-family:'Montserrat',sans-serif;font-weight:800;
            font-size:2.2rem;color:#1b1c1c;letter-spacing:-0.04em;
            line-height:1.15;margin-bottom:14px;">
            Optimizing the world's
            <span style="color:#008A71;">last mile</span>,
            one shipment at a time.
        </h2>
        <p style="font-family:'Inter',sans-serif;font-size:0.92rem;
            color:#6d7a75;line-height:1.6;margin:0;">
            Access the industry-leading logistics dashboard to track fleet
            metrics, optimize routes, and manage your precision delivery ecosystem.
        </p>
    </div>

    <div style="position:relative;z-index:1;">
        <div style="background:rgba(255,255,255,0.85);backdrop-filter:blur(20px);
            -webkit-backdrop-filter:blur(20px);padding:18px 22px;border-radius:18px;
            box-shadow:0px 12px 32px rgba(0,107,87,0.08);
            display:flex;align-items:center;gap:16px;max-width:260px;
            border:1px solid rgba(189,201,195,0.15);">
            <div style="width:44px;height:44px;background:rgba(0,138,113,0.1);
                border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0;">
                <span style="font-size:20px;line-height:1;">&#9889;</span>
            </div>
            <div>
                <div style="font-family:'Montserrat',sans-serif;font-size:0.58rem;
                    font-weight:700;color:#6d7a75;text-transform:uppercase;
                    letter-spacing:0.1em;margin-bottom:2px;">Real-time Efficiency</div>
                <div style="font-family:'Montserrat',sans-serif;font-size:1.25rem;
                    font-weight:800;color:#1b1c1c;letter-spacing:-0.02em;">
                    99.4%&nbsp;<span style="font-size:0.68rem;color:#008A71;font-weight:600;">+1.2%</span>
                </div>
            </div>
        </div>
        <div style="display:flex;align-items:center;justify-content:space-between;
            margin-top:20px;padding-top:16px;border-top:1px solid rgba(189,201,195,0.2);">
            <div>
                <div style="font-family:'Montserrat',sans-serif;font-size:0.58rem;
                    font-weight:700;color:#6d7a75;text-transform:uppercase;
                    letter-spacing:0.1em;">System Status</div>
                <div style="display:flex;align-items:center;gap:6px;margin-top:3px;">
                    <div style="width:7px;height:7px;border-radius:50%;background:#22c55e;"></div>
                    <span style="font-family:'Inter',sans-serif;font-size:0.73rem;color:#3d4945;">All Systems Operational</span>
                </div>
            </div>
            <div style="width:30px;height:30px;border-radius:50%;
                border:2px solid #f5f3f3;background:#e4e2e2;
                display:flex;align-items:center;justify-content:center;
                font-family:'Montserrat',sans-serif;font-size:0.58rem;
                font-weight:700;color:#6d7a75;">+4k</div>
        </div>
    </div>
</div>
</body>
</html>"""


def inject_login_css():
    """Inject CSS to style the right-side login form and hide Streamlit chrome."""
    st.markdown("""
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
    """, unsafe_allow_html=True)

    st.markdown("""
    <style>
    /* ── Hide all Streamlit chrome ── */
    #MainMenu, footer, .stDeployButton { display: none !important; visibility: hidden !important; }
    [data-testid="stHeader"]         { display: none !important; }
    [data-testid="stSidebar"]        { display: none !important; }
    [data-testid="stToolbar"]        { display: none !important; }
    [data-testid="stStatusWidget"]   { display: none !important; }
    [data-testid="manage-app-button"]{ display: none !important; }
    [data-testid="stDecoration"]     { display: none !important; }

    /* ── Full-page background ── */
    html, body { margin: 0 !important; padding: 0 !important; height: 100% !important; }
    .stApp, [data-testid="stAppViewContainer"] {
        background: #fbf9f8 !important;
        font-family: 'Inter', sans-serif !important;
        min-height: 100vh !important;
    }

    /* ── Remove block-container padding ── */
    .main .block-container {
        padding: 0 !important;
        max-width: 100% !important;
        margin: 0 !important;
        min-height: 100vh !important;
    }
    .main { padding: 0 !important; margin: 0 !important; min-height: 100vh !important; }

    /* ── Column row: fill viewport ── */
    [data-testid="stHorizontalBlock"],
    .stHorizontalBlock {
        gap: 0 !important;
        min-height: 100vh !important;
        align-items: stretch !important;
        flex-wrap: nowrap !important;
        padding: 0 !important;
    }

    /* ── Left panel (iframe visual) ── */
    [data-testid="stColumn"]:first-child {
        background: #f5f3f3 !important;
        min-height: 100vh !important;
        padding: 0 !important;
        flex: 1 !important;
        overflow: hidden !important;
    }
    [data-testid="stColumn"]:first-child > div,
    [data-testid="stColumn"]:first-child [data-testid="column"] {
        min-height: 100vh !important;
        padding: 0 !important;
        height: 100% !important;
    }
    [data-testid="stColumn"]:first-child iframe {
        min-height: 100vh !important;
        border: none !important;
    }

    /* ── Right panel (white, centered) ── */
    [data-testid="stColumn"]:last-child,
    [data-testid="stColumn"]:nth-child(2) {
        background: #ffffff !important;
        min-height: 100vh !important;
        flex: 1 !important;
    }
    [data-testid="stColumn"]:last-child > div,
    [data-testid="stColumn"]:last-child [data-testid="column"],
    [data-testid="stColumn"]:nth-child(2) > div,
    [data-testid="stColumn"]:nth-child(2) [data-testid="column"] {
        min-height: 100vh !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        padding: 3rem 3.5rem !important;
    }

    /* ── Login header text ── */
    .pn-login-header h2 {
        font-family: 'Montserrat', sans-serif !important;
        font-weight: 800 !important; font-size: 2rem !important;
        color: #1b1c1c !important; letter-spacing: -0.03em !important;
        margin: 0 0 6px 0 !important; line-height: 1.15 !important;
    }
    .pn-login-header p {
        color: #6d7a75 !important; font-size: 0.9rem !important;
        margin: 0 !important; font-family: 'Inter', sans-serif !important;
    }

    /* ── Input labels ── */
    .stTextInput label {
        font-family: 'Montserrat', sans-serif !important;
        font-size: 0.8rem !important; font-weight: 600 !important;
        color: #3d4945 !important; text-transform: none !important;
        letter-spacing: 0 !important; margin-bottom: 4px !important;
    }

    /* ── Input fields ── */
    .stTextInput > div > div > input {
        height: 52px !important;
        background: #f5f3f3 !important;
        border: none !important;
        border-bottom: 2px solid transparent !important;
        border-radius: 12px !important;
        color: #1b1c1c !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.9rem !important;
        padding: 0 16px !important;
        outline: none !important;
        box-shadow: none !important;
    }
    .stTextInput > div > div > input:focus {
        background: #efeded !important;
        border-bottom-color: #008A71 !important;
        box-shadow: none !important;
        outline: none !important;
    }
    .stTextInput > div > div > input::placeholder { color: #bdc9c3 !important; }
    .stTextInput > div > div { box-shadow: none !important; border: none !important; }
    .stTextInput > div { border: none !important; box-shadow: none !important; }

    /* ── Checkbox ── */
    .stCheckbox label {
        font-family: 'Inter', sans-serif !important;
        font-size: 0.85rem !important; color: #3d4945 !important;
    }

    /* ── Submit button ── */
    .stFormSubmitButton > button, .stButton > button {
        width: 100% !important; height: 52px !important;
        background: linear-gradient(135deg, #008A71 0%, #00846c 100%) !important;
        color: #ffffff !important; border: none !important;
        border-radius: 12px !important;
        font-family: 'Montserrat', sans-serif !important;
        font-size: 0.95rem !important; font-weight: 700 !important;
        letter-spacing: -0.01em !important;
        box-shadow: 0px 12px 32px rgba(0,107,87,0.25) !important;
        cursor: pointer !important;
    }
    .stFormSubmitButton > button:hover, .stButton > button:hover {
        transform: scale(1.015) !important;
        box-shadow: 0px 16px 40px rgba(0,107,87,0.35) !important;
    }

    /* ── Alert ── */
    [data-testid="stAlert"] {
        border-radius: 10px !important;
        font-family: 'Inter', sans-serif !important;
        border: none !important; margin-top: 8px !important;
    }

    /* ── Form container ── */
    [data-testid="stForm"] {
        background: transparent !important;
        border: none !important; padding: 0 !important;
    }
    </style>
    """, unsafe_allow_html=True)


def render_login_page():
    """Render the Precision Navigator login page."""
    inject_login_css()

    col_left, col_right = st.columns([1, 1])

    # ── LEFT — Visual branding panel (rendered via components.html for reliability) ──
    with col_left:
        logo_b64 = _get_logo_b64()
        left_html = _build_left_panel_html(logo_b64)
        components.html(left_html, height=900, scrolling=False)

    # ── RIGHT — Form Panel ──
    with col_right:
        st.markdown("""
        <div class="pn-login-header" style="margin-bottom:28px;">
            <h2>Welcome Back</h2>
            <p>Please enter your Precision Navigator credentials.</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("pn_login_form", clear_on_submit=False):
            st.text_input("Email Address", placeholder="name@shadowfax.in", key="login_email")
            st.text_input("Password", type="password", placeholder="••••••••", key="login_password")
            st.checkbox("Stay signed in for 30 days", key="login_remember")
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Sign In  →", use_container_width=True)

            if submitted:
                email = st.session_state.get("login_email", "")
                pwd = st.session_state.get("login_password", "")
                if check_credentials(email, pwd):
                    st.session_state["authenticated"] = True
                    st.session_state["current_user"] = email
                    st.rerun()
                else:
                    st.error("Invalid email or password. Please try again.")

        st.markdown("""
        <div style="margin-top:28px;padding-top:20px;
            border-top:1px solid rgba(189,201,195,0.2);
            text-align:center;font-family:'Inter',sans-serif;
            font-size:0.82rem;color:#6d7a75;">
            Don't have an account?&nbsp;
            <span style="color:#008A71;font-family:'Montserrat',sans-serif;
                font-weight:700;">Contact Admin</span>
        </div>
        """, unsafe_allow_html=True)
