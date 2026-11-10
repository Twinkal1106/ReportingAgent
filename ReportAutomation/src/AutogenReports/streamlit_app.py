"""
FedEx Reporting Agent - Streamlit Application with Okta / PurpleID Authentication
"""

import os
import sys
import json
import asyncio
import re
from pathlib import Path
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

# Ensure AutogenReports and parent directories are in sys.path
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
WORKSPACE_ROOT = PROJECT_ROOT.parent

for _p in [PROJECT_ROOT, CURRENT_DIR.parent, WORKSPACE_ROOT, WORKSPACE_ROOT / "ReportingMCPServer"]:
    _p_str = str(_p)
    if _p_str not in sys.path:
        sys.path.insert(0, _p_str)

load_dotenv(WORKSPACE_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(WORKSPACE_ROOT / "ReportingMCPServer" / ".env")

# Propagate Streamlit Cloud secrets into os.environ if deployed
try:
    for _sec_k, _sec_v in st.secrets.items():
        if isinstance(_sec_v, str) and _sec_k not in os.environ:
            os.environ[_sec_k] = _sec_v
except Exception:
    pass

# Ensure ReportingMCPServer is running on port 8001 in background daemon thread
_mcp_server_started = False
def ensure_mcp_server_running():
    global _mcp_server_started
    if _mcp_server_started:
        return
    import socket
    import threading
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as _sock:
        _sock.settimeout(0.3)
        if _sock.connect_ex(("127.0.0.1", 8001)) == 0:
            _mcp_server_started = True
            return
    try:
        import uvicorn
        from ReportingMCPServer.server import app as _mcp_app
        _cfg = uvicorn.Config(app=_mcp_app, host="127.0.0.1", port=8001, log_level="warning")
        _srv = uvicorn.Server(_cfg)
        _t = threading.Thread(target=_srv.run, daemon=True, name="ReportingMCPServer-Daemon")
        _t.start()
        _mcp_server_started = True
    except Exception as _start_err:
        pass

ensure_mcp_server_running()

import importlib
import AutogenReports.okta_auth as _okta_module
# Force reload to prevent stale module caching across hot-reloads
importlib.reload(_okta_module)

from AutogenReports.okta_auth import (
    get_authorization_url,
    generate_pkce_pair,
    exchange_code_for_token,
    decode_jwt_payload,
    is_token_valid,
    get_token_expiration_str,
    extract_user_info,
)

# Safe fallback for extract_info_from_cookie if cached module is in memory
try:
    from AutogenReports.okta_auth import extract_info_from_cookie
except ImportError:
    def extract_info_from_cookie(cookie_str: str) -> dict:
        return {
            "display_name": os.getenv("USER_DISPLAY_NAME") or "Twinkal",
            "email": "FedEx Session (Cookie)",
            "station": "PITCO",
            "employee_number": "Cookie-Auth",
        }
from AutogenReports.mcp_client import (
    set_auth_token,
    get_auth_token,
    set_auth_cookie,
    get_auth_cookie,
    fetch_non_delivered_tracking_ids,
    connect_cassandra,
    cassandra_execute_query,
    cassandra_list_tables,
    cassandra_select_table,
    generate_cassandra_pdf,
)
from AutogenReports.main import assistant_agent, model_client, SYSTEM_PROMPT, _base_tools
from autogen_agentchat.agents import AssistantAgent
from autogen_core.tools import FunctionTool

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="FedEx Reporting Agent",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom FedEx Branding CSS
st.markdown("""
<style>
    /* Global Background & Font */
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #f0f2f5 !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important;
    }

    /* Top Navigation Header Bar spanning full width */
    [data-testid="stHeader"] {
        background: transparent !important;
        height: 60px !important;
        z-index: 999995 !important;
        pointer-events: none !important;
    }

    /* Hide Streamlit default Deploy button, top decoration & hamburger menu to prevent overlap */
    #MainMenu,
    [data-testid="stToolbar"],
    [data-testid="stAppDeployButton"],
    button[data-testid="stHeaderDeployButton"],
    .stDeployButton,
    [data-testid="stDecoration"],
    [data-testid="stHeaderActionElements"],
    header [data-testid="stToolbar"],
    header [data-testid="stHeaderActionElements"],
    header .stAppToolbar {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
        width: 0 !important;
        height: 0 !important;
    }

    /* Make Streamlit's sidebar toggle (open/close) always visible & accessible */
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"],
    header [data-testid="stSidebarCollapsedControl"],
    button[data-testid="baseButton-headerNoPadding"],
    [data-testid="stSidebarCollapseButton"] {
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        pointer-events: auto !important;
        z-index: 1000001 !important;
        top: 12px !important;
        left: 16px !important;
        color: #ffffff !important;
        background: rgba(255, 255, 255, 0.22) !important;
        border: 1px solid rgba(255, 255, 255, 0.4) !important;
        border-radius: 8px !important;
        transition: all 0.2s ease !important;
    }
    [data-testid="collapsedControl"]:hover,
    [data-testid="stSidebarCollapsedControl"]:hover,
    header [data-testid="stSidebarCollapsedControl"]:hover,
    button[data-testid="baseButton-headerNoPadding"]:hover,
    [data-testid="stSidebarCollapseButton"]:hover {
        background: #FF6600 !important;
        border-color: #FF6600 !important;
        color: #ffffff !important;
        transform: scale(1.05);
    }
    [data-testid="collapsedControl"] svg,
    [data-testid="stSidebarCollapsedControl"] svg,
    header [data-testid="stSidebarCollapsedControl"] svg,
    button[data-testid="baseButton-headerNoPadding"] svg,
    [data-testid="stSidebarCollapseButton"] svg {
        fill: #ffffff !important;
        stroke: #ffffff !important;
        color: #ffffff !important;
    }

    /* Bring the open sidebar cleanly in front */
    [data-testid="stSidebar"] {
        z-index: 1000002 !important;
        top: 0 !important;
    }

    /* Adjust main content container padding */
    .block-container {
        max-width: 1100px !important;
        padding-top: 0.5rem !important;
        padding-bottom: 3.5rem !important;
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
    }

    /* Header Bar matching web console */
    .fedex-top-header {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 60px;
        background: #4D148C;
        color: white;
        padding: 0 28px 0 68px; /* Room for the sidebar reopen toggle button */
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.12);
        z-index: 999990;
    }

    .header-title-box {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 20px;
        font-weight: bold;
    }

    .brand-logo-txt {
        display: inline-flex;
        align-items: center;
        line-height: 1;
    }
    .brand-fed-txt {
        color: #ffffff;
        font-weight: 800;
        letter-spacing: -0.5px;
    }
    .brand-ex-txt {
        color: #FF6600;
        font-weight: 800;
        letter-spacing: -0.5px;
    }
    .brand-reporting-txt {
        color: #ffffff;
        margin-left: 4px;
        font-weight: 700;
    }
    .brand-agent-txt {
        color: #FF6600;
        font-weight: 600;
        margin-left: 4px;
    }

    .header-user-badge {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        font-size: 13.5px;
        font-weight: 500;
        color: #ffffff;
        background: rgba(255, 255, 255, 0.14);
        padding: 5px 6px 5px 14px;
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.2);
    }
    .header-user-circle {
        width: 26px;
        height: 26px;
        border-radius: 50%;
        background: linear-gradient(135deg, #FF6600, #ff8533);
        color: #ffffff;
        font-weight: 700;
        font-size: 12.5px;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
    }

    /* Fixed Corporate Footer */
    .fedex-bottom-footer {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        height: 38px;
        background: #4D148C;
        color: white;
        border-top: 2px solid #FF6600;
        display: flex;
        justify-content: center;
        align-items: center;
        font-size: 13px;
        letter-spacing: 0.3px;
        z-index: 999990;
    }

    /* Card Container Wrapper */
    .fedex-card-wrapper {
        background: #ffffff;
        border-radius: 14px;
        box-shadow: 0 6px 24px rgba(0, 0, 0, 0.08);
        padding: 24px 26px 20px 26px;
        margin-top: 48px;
        margin-bottom: 24px;
        border: 1px solid #eaeaea;
    }

    /* Welcome Banner */
    .fedex-welcome-card {
        display: flex;
        align-items: center;
        gap: 16px;
        background: #f7f4fb;
        border-left: 4px solid #4D148C;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 18px;
    }
    .fedex-welcome-avatar {
        font-size: 32px;
        line-height: 1;
    }
    .fedex-welcome-text h3 {
        margin: 0 0 6px 0;
        color: #4D148C;
        font-size: 16px;
        font-weight: 700;
    }
    .fedex-welcome-text p {
        margin: 0;
        color: #555;
        font-size: 13.5px;
        line-height: 1.4;
    }

    /* Quick Action Buttons Matching Chips */
    .quick-action-bar {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-top: 14px;
        margin-bottom: 8px;
    }
    .quick-action-label {
        font-size: 11.5px;
        color: #4b5563;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        margin-right: 4px;
        white-space: nowrap;
    }

    div[data-testid="stHorizontalBlock"] button {
        background: #f4effa !important;
        color: #4D148C !important;
        border: 1px solid #dcd1ed !important;
        padding: 6px 16px !important;
        border-radius: 20px !important;
        font-size: 13.5px !important;
        font-weight: 600 !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04) !important;
        transition: all 0.2s ease !important;
        white-space: nowrap !important;
    }
    div[data-testid="stHorizontalBlock"] button:hover {
        background: #4D148C !important;
        color: #ffffff !important;
        border-color: #4D148C !important;
        box-shadow: 0 4px 10px rgba(77, 20, 140, 0.25) !important;
    }

    /* Input & Send Styling */
    div[data-testid="stChatInput"] {
        border-radius: 10px !important;
    }
    div[data-testid="stChatInput"] textarea {
        border-radius: 10px !important;
        font-size: 14.5px !important;
    }
    div[data-testid="stChatInput"] button {
        background: linear-gradient(135deg, #FF6600, #FF8533) !important;
        color: white !important;
        border-radius: 8px !important;
    }

    /* PDF Download Card */
    .pdf-download-card {
        background: #F8F6FD;
        border: 1px solid #D8C7F0;
        border-left: 5px solid #4D148C;
        border-radius: 8px;
        padding: 14px 18px;
        margin-top: 10px;
        margin-bottom: 10px;
    }
    .pdf-card-header {
        font-weight: 700;
        color: #4D148C;
        font-size: 15px;
        margin-bottom: 6px;
    }
</style>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Session State Initialization
# -----------------------------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "auth_cookie" not in st.session_state:
    st.session_state.auth_cookie = None
if "auth_type" not in st.session_state:
    st.session_state.auth_type = "token"  # "token" or "cookie"
if "user_info" not in st.session_state:
    st.session_state.user_info = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pkce_verifier" not in st.session_state:
    st.session_state.pkce_verifier = None
if "pkce_challenge" not in st.session_state:
    st.session_state.pkce_challenge = None
if "cassandra_initialized" not in st.session_state:
    st.session_state.cassandra_initialized = False
if "agent" not in st.session_state:
    st.session_state.agent = assistant_agent


# -----------------------------------------------------------------------------
# Auto-discover token or cookie from environment on first load
# -----------------------------------------------------------------------------
if not st.session_state.authenticated:
    env_token = os.getenv("INTERNAL_API_KEY")
    env_cookie = os.getenv("INTERNAL_API_COOKIE")
    if env_token and is_token_valid(env_token):
        st.session_state.access_token = env_token
        st.session_state.user_info = extract_user_info(env_token)
        st.session_state.auth_type = "token"
        st.session_state.authenticated = True
        set_auth_token(env_token)
    elif env_cookie:
        st.session_state.auth_cookie = env_cookie
        st.session_state.auth_type = "cookie"
        cookie_data = extract_info_from_cookie(env_cookie)
        resolved_name = (
            cookie_data.get("display_name")
            or os.getenv("USER_DISPLAY_NAME")
            or "Twinkal"
        )
        st.session_state.user_info = {
            "display_name": resolved_name,
            "email": cookie_data.get("email", "FedEx Session (Cookie)"),
            "station": cookie_data.get("station", "PITCO"),
            "employee_number": cookie_data.get("employee_number", "Cookie-Auth"),
        }
        st.session_state.authenticated = True
        set_auth_cookie(env_cookie)
        if env_token:
            set_auth_token(env_token)


# -----------------------------------------------------------------------------
# Handle Okta OAuth Redirect Callback (query params ?code=...)
# -----------------------------------------------------------------------------
query_params = st.query_params
if "code" in query_params and not st.session_state.authenticated:
    auth_code = query_params["code"]
    verifier = st.session_state.pkce_verifier
    with st.spinner("Authenticating with FedEx Okta (PurpleID)..."):
        token_res = exchange_code_for_token(code=auth_code, code_verifier=verifier)
        if token_res.get("success"):
            tokens = token_res.get("data", {})
            new_token = tokens.get("access_token") or tokens.get("id_token")
            id_tok = tokens.get("id_token")
            if new_token:
                st.session_state.access_token = new_token
                st.session_state.user_info = extract_user_info(new_token, id_token=id_tok)
                st.session_state.authenticated = True
                set_auth_token(new_token)
                st.query_params.clear()
                st.rerun()
            else:
                st.error("No access token returned from Okta.")
        else:
            st.error(f"Okta login failed: {token_res.get('error')}")


# -----------------------------------------------------------------------------
# Initialize Cassandra Tools if not done
# -----------------------------------------------------------------------------
if not st.session_state.cassandra_initialized:
    try:
        connected = connect_cassandra()
        if connected:
            cassandra_tools = [
                FunctionTool(cassandra_execute_query, description="Execute a CQL SELECT query against Cassandra DB."),
                FunctionTool(cassandra_list_tables, description="List all tables in the configured Cassandra keyspace."),
                FunctionTool(cassandra_select_table, description="Fetch all rows from a Cassandra table (SELECT *)."),
                FunctionTool(generate_cassandra_pdf, description="Generate a PDF report from a Cassandra table or CQL query."),
            ]
            st.session_state.agent = AssistantAgent(
                name="ReportingAssistant",
                model_client=model_client,
                system_message=SYSTEM_PROMPT,
                description=f"FedEx Reporting Agent. Today is {datetime.now().strftime('%Y-%m-%d')}.",
                tools=[*_base_tools, *cassandra_tools]
            )
            st.session_state.cassandra_initialized = True
    except Exception:
        pass


# -----------------------------------------------------------------------------
# Okta Login View (Displayed if Unauthenticated)
# -----------------------------------------------------------------------------
def render_okta_login():
    st.markdown("""
    <div style="text-align: center; margin-top: 40px; margin-bottom: 25px;">
        <span style="font-size: 42px; font-weight: 900; letter-spacing: -1px;">
            <span style="color: #4D148C;">Fed</span><span style="color: #FF6600;">Ex</span>
        </span>
        <h2 style="color: #4D148C; margin-top: 8px; font-weight: 700;">FedEx Reporting Agent</h2>
        <p style="color: #666; font-size: 16px;">Sign in with your FedEx PurpleID (Okta) account to access reporting automation.</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.container(border=True):
            st.markdown("#### 🔐 PurpleID Single Sign-On (SSO)")
            st.markdown("Authenticate using the corporate FedEx Okta Authorization Server.")

            if st.session_state.pkce_verifier is None:
                verifier, challenge = generate_pkce_pair()
                st.session_state.pkce_verifier = verifier
                st.session_state.pkce_challenge = challenge

            okta_login_url = get_authorization_url(code_challenge=st.session_state.pkce_challenge)

            st.link_button(
                label="🚀 Sign In with FedEx PurpleID (Okta)",
                url=okta_login_url,
                type="primary",
                use_container_width=True,
            )

            st.markdown("---")
            st.markdown("##### 🍪 Sign In with Browser Session Cookies")
            with st.expander("Paste Session Cookie Header", expanded=True):
                st.caption("Copy the `Cookie` header from your browser (DevTools → Network → request headers):")
                cookie_user_name = st.text_input("Your Name / Display Name (Optional)", placeholder="Enter your name or employee ID", key="cookie_name_input")
                manual_cookie = st.text_area("Cookie Header", placeholder="ObSSOCookie=...; JSESSIONID=...; purpleid_token=...", height=90, key="login_cookie_input")
                if st.button("Authenticate with Cookies", use_container_width=True, type="primary"):
                    if manual_cookie.strip():
                        cookie_clean = manual_cookie.strip()
                        st.session_state.auth_cookie = cookie_clean
                        st.session_state.auth_type = "cookie"
                        cookie_info = extract_info_from_cookie(cookie_clean)
                        resolved_name = (
                            cookie_user_name.strip()
                            or cookie_info.get("display_name")
                            or os.getenv("USER_DISPLAY_NAME")
                            or "Twinkal"
                        )
                        st.session_state.user_info = {
                            "display_name": resolved_name,
                            "email": cookie_info.get("email", "FedEx Session (Cookie)"),
                            "station": cookie_info.get("station", "PITCO"),
                            "employee_number": cookie_info.get("employee_number", "Cookie-Auth")
                        }
                        st.session_state.authenticated = True
                        set_auth_cookie(cookie_clean)
                        set_auth_token(None)
                        st.success(f"Authenticated as {resolved_name}!")
                        st.rerun()
                    else:
                        st.warning("Please paste cookie string.")

            st.markdown("---")
            st.markdown("##### 🔑 Or Sign In with Active Bearer Token")
            with st.expander("Paste Okta JWT Token", expanded=False):
                st.caption("If you have an active Bearer token from your browser or FedEx portal:")
                manual_token = st.text_area("Bearer Token", placeholder="eyJraWQi...", height=100)
                if st.button("Authenticate with Token", use_container_width=True):
                    if manual_token.strip():
                        token_clean = manual_token.strip()
                        if is_token_valid(token_clean):
                            st.session_state.access_token = token_clean
                            st.session_state.user_info = extract_user_info(token_clean)
                            st.session_state.auth_type = "token"
                            st.session_state.authenticated = True
                            set_auth_token(token_clean)
                            set_auth_cookie(None)
                            st.success("Authenticated successfully!")
                            st.rerun()
                        else:
                            st.error("Provided token is expired or invalid. Please provide an active token.")
                    else:
                        st.warning("Please paste a token.")

            # Check if there is an expired token in .env to give user context
            env_t = os.getenv("INTERNAL_API_KEY", "")
            if env_t:
                exp_info = get_token_expiration_str(env_t)
                st.caption(f"Environment Token Status: {exp_info}")


# -----------------------------------------------------------------------------
# Main Application View (Displayed When Authenticated)
# -----------------------------------------------------------------------------
def render_main_dashboard():
    user = st.session_state.user_info or {}
    user_name = user.get("display_name")
    if not user_name or user_name.lower().startswith("fedex user"):
        user_name = os.getenv("USER_DISPLAY_NAME") or "Twinkal"
    user_initial = user_name[0].upper() if user_name else "T"
    user_email = user.get("email", "")
    token_str = st.session_state.access_token or ""
    exp_info = get_token_expiration_str(token_str)

    # Sidebar: User Profile & Okta/Cookie Session Details (Left Side Toggle)
    with st.sidebar:
        if st.button("➕ New Chat / Refresh", key="btn_sidebar_new_chat", use_container_width=True, type="primary"):
            st.session_state.messages = []
            st.rerun()

        st.markdown("---")
        st.markdown("### 👤 User Profile")
        with st.expander("✏️ Edit Display Name", expanded=False):
            custom_name_input = st.text_input("Display Name", value=user_name, key="edit_name_input")
            if st.button("Save Name", key="btn_save_name", use_container_width=True):
                if custom_name_input.strip():
                    st.session_state.user_info["display_name"] = custom_name_input.strip()
                    st.rerun()

        st.markdown(f"**Name:** {user_name}")
        st.markdown(f"**Email:** `{user_email}`")
        st.markdown(f"**Employee #:** `{user.get('employee_number', 'N/A')}`")

        st.markdown("---")
        st.markdown("### 🔐 Authentication Session")
        auth_mode = st.session_state.get("auth_type", "token")
        if auth_mode == "cookie":
            st.markdown("**Method:** 🍪 Browser Session Cookie")
            st.markdown("**Status:** 🟢 Active")
            cookie_preview = (st.session_state.auth_cookie[:25] + "...") if st.session_state.auth_cookie else "Set"
            st.caption(f"Cookie: `{cookie_preview}`")
        else:
            st.markdown("**Method:** 🔑 Bearer Token")
            st.markdown(f"**Status:** 🟢 Active")
            st.markdown(f"**Token Expiry:** {exp_info}")

        if st.button("🔄 Update Cookie / Token", use_container_width=True):
            st.session_state.token_modal_open = True

        if st.session_state.get("token_modal_open", False):
            tab_c, tab_t = st.tabs(["🍪 Cookie", "🔑 Bearer Token"])
            with tab_c:
                new_c = st.text_area("Paste Cookie Header", height=70, key="update_cookie")
                new_name = st.text_input("Display Name (Optional)", key="update_cookie_name", placeholder=user_name)
                if st.button("Apply Cookie"):
                    if new_c.strip():
                        st.session_state.auth_cookie = new_c.strip()
                        st.session_state.auth_type = "cookie"
                        cookie_info = extract_info_from_cookie(new_c.strip())
                        resolved_name = new_name.strip() or cookie_info.get("display_name") or user_name
                        st.session_state.user_info["display_name"] = resolved_name
                        if cookie_info.get("station"):
                            st.session_state.user_info["station"] = cookie_info["station"]
                        if cookie_info.get("employee_number"):
                            st.session_state.user_info["employee_number"] = cookie_info["employee_number"]
                        set_auth_cookie(new_c.strip())
                        set_auth_token(None)
                        st.session_state.token_modal_open = False
                        st.success("Cookie updated!")
                        st.rerun()
            with tab_t:
                new_t = st.text_area("Paste Fresh Token", height=70, key="update_token")
                if st.button("Apply Token"):
                    if new_t.strip() and is_token_valid(new_t.strip()):
                        st.session_state.access_token = new_t.strip()
                        st.session_state.auth_type = "token"
                        st.session_state.user_info = extract_user_info(new_t.strip())
                        set_auth_token(new_t.strip())
                        set_auth_cookie(None)
                        st.session_state.token_modal_open = False
                        st.success("Token updated!")
                        st.rerun()
                    else:
                        st.error("Token is invalid or expired.")

        st.markdown("---")
        if st.button("🚪 Log Out", use_container_width=True, type="secondary"):
            st.session_state.authenticated = False
            st.session_state.access_token = None
            st.session_state.auth_cookie = None
            st.session_state.user_info = None
            set_auth_token(None)
            set_auth_cookie(None)
            st.rerun()

    # Fixed Top Navigation Header Bar
    st.markdown(f"""
    <div class="fedex-top-header">
        <div class="header-title-box">
            <span class="brand-logo-txt">
                <span class="brand-fed-txt">Fed</span><span class="brand-ex-txt">Ex</span>
            </span>
            <span class="brand-reporting-txt">Reporting</span>
            <span class="brand-agent-txt">Agent</span>
        </div>
        <div class="header-user-badge">
            <span>Hi, {user_name}</span>
            <span class="header-user-circle" title="{user_name}">{user_initial}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Fixed Corporate Footer Bar
    st.markdown("""
    <div class="fedex-bottom-footer">
        <span>&copy; 2026 FedEx Corporation. All rights reserved.</span>
    </div>
    """, unsafe_allow_html=True)

    # Main White Card Container
    st.markdown(f"""
    <div class="fedex-card-wrapper">
        <div class="fedex-welcome-card">
            <div class="fedex-welcome-avatar">🤖</div>
            <div class="fedex-welcome-text">
                <h3>Hi {user_name} 👋 Welcome to your FedEx Reporting Agent</h3>
                <p>How can I assist you today? Ask me to generate standard or consolidated reports, query Cassandra, or create customized PDF reports.</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Quick Action Chips & Controls
    qa_title_col, qa_btn_col = st.columns([3.5, 1.2])
    with qa_title_col:
        st.markdown("**Quick actions:**")
    with qa_btn_col:
        if st.button("🔄 New Chat", key="btn_main_new_chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    qcol1, qcol2, qcol3, qcol4 = st.columns([1, 1.2, 1.2, 1])

    prompt_to_send = None
    with qcol1:
        if st.button("📄 Generate Report", use_container_width=True):
            prompt_to_send = "I want to generate a report"
    with qcol2:
        if st.button("📋 Non-Delivered (Facility 88)", use_container_width=True):
            prompt_to_send = "Fetch non-delivered tracking IDs for Facility 88"
    with qcol3:
        if st.button("📊 Summary Report (Last 7 Days)", use_container_width=True):
            prompt_to_send = "Generate summary report for the last 7 days for Facility 88"
    with qcol4:
        if st.button("🗄️ Cassandra Tables", use_container_width=True):
            prompt_to_send = "List all tables in Cassandra database"

    # Display Chat History
    if st.session_state.messages:
        hist_title_col, hist_btn_col = st.columns([4, 1.2])
        with hist_title_col:
            st.caption(f"💬 Conversation History ({len(st.session_state.messages)} messages)")
        with hist_btn_col:
            if st.button("🗑️ Clear History", key="btn_clear_history", use_container_width=True):
                st.session_state.messages = []
                st.rerun()

    for msg in st.session_state.messages:
        role = msg["role"]
        content = msg["content"]
        avatar = "🧑" if role == "user" else "🤖"
        with st.chat_message(role, avatar=avatar):
            # Check if content is a PDF generation result
            pdf_data = None
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict) and parsed.get("success") and parsed.get("download_url"):
                    pdf_data = parsed
            except Exception:
                pass

            if pdf_data:
                filename = pdf_data.get("filename", "report.pdf")
                rec_count = pdf_data.get("record_count", "N/A")
                file_size = pdf_data.get("file_size_kb", "N/A")
                st.markdown(f"""
                <div class="pdf-download-card">
                    <div class="pdf-card-header">📄 PDF Report Generated Successfully!</div>
                    <div><strong>File:</strong> {filename}</div>
                    <div><strong>Records:</strong> {rec_count} | <strong>Size:</strong> {file_size} KB</div>
                </div>
                """, unsafe_allow_html=True)

                # Check if file exists on disk to provide instant Streamlit download
                filepath = pdf_data.get("filepath")
                if filepath and os.path.exists(filepath):
                    with open(filepath, "rb") as f:
                        file_bytes = f.read()
                    st.download_button(
                        label=f"📥 Download {filename}",
                        data=file_bytes,
                        file_name=filename,
                        mime="application/pdf",
                        key=f"dl_{filename}_{msg.get('id', '')}"
                    )
            else:
                st.markdown(content)

    # Chat Input
    user_input = st.chat_input("🤖 Ask to generate reports, query Cassandra, or create PDF reports...")
    active_prompt = prompt_to_send or user_input

    if active_prompt:
        # Append User Message
        st.session_state.messages.append({"role": "user", "content": active_prompt})
        with st.chat_message("user", avatar="🧑"):
            st.markdown(active_prompt)

        # Agent Processing
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("FedEx Agent thinking..."):
                try:
                    # Run AutoGen Agent
                    agent_to_run = st.session_state.agent
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result_obj = loop.run_until_complete(agent_to_run.run(task=active_prompt))

                    # Extract Response text
                    if getattr(result_obj, "messages", None):
                        try:
                            response_text = result_obj.messages[-1].content
                        except Exception:
                            last_msg = result_obj.messages[-1]
                            response_text = last_msg.get("content") if isinstance(last_msg, dict) else str(last_msg)
                    else:
                        response_text = getattr(result_obj, "content", None) or str(result_obj)

                    if not response_text:
                        response_text = "I apologize, but I couldn't generate a response. Please try rephrasing your request."

                    # Render and append
                    pdf_data = None
                    try:
                        parsed = json.loads(response_text)
                        if isinstance(parsed, dict) and parsed.get("success") and parsed.get("download_url"):
                            pdf_data = parsed
                    except Exception:
                        pass

                    if pdf_data:
                        filename = pdf_data.get("filename", "report.pdf")
                        rec_count = pdf_data.get("record_count", "N/A")
                        file_size = pdf_data.get("file_size_kb", "N/A")
                        st.markdown(f"""
                        <div class="pdf-download-card">
                            <div class="pdf-card-header">📄 PDF Report Generated Successfully!</div>
                            <div><strong>File:</strong> {filename}</div>
                            <div><strong>Records:</strong> {rec_count} | <strong>Size:</strong> {file_size} KB</div>
                        </div>
                        """, unsafe_allow_html=True)

                        filepath = pdf_data.get("filepath")
                        if filepath and os.path.exists(filepath):
                            with open(filepath, "rb") as f:
                                file_bytes = f.read()
                            st.download_button(
                                label=f"📥 Download {filename}",
                                data=file_bytes,
                                file_name=filename,
                                mime="application/pdf"
                            )
                    else:
                        st.markdown(response_text)

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response_text,
                        "id": str(len(st.session_state.messages))
                    })

                except Exception as e:
                    err_msg = f"❌ **Error running agent:** {str(e)}"
                    st.error(err_msg)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": err_msg,
                        "id": str(len(st.session_state.messages))
                    })


# -----------------------------------------------------------------------------
# Main Router
# -----------------------------------------------------------------------------
if not st.session_state.authenticated:
    render_okta_login()
else:
    render_main_dashboard()
