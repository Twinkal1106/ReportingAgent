"""
Okta / PurpleID OAuth2 Authentication Helper for Streamlit
Supports:
- Authorization Code Flow with PKCE (Proof Key for Code Exchange)
- Token decoding & validation (expiration, claims, user profile)
- Seamless token propagation to MCP Server and AutoGen Agent
"""

import os
import json
import base64
import hashlib
import secrets
import time
from datetime import datetime
from typing import Optional, Dict, Any
import httpx
from dotenv import load_dotenv

load_dotenv()

# Okta configuration from env with defaults from PurpleID config
OKTA_ISSUER = os.getenv("OKTA_ISSUER", "https://purpleid-test.oktapreview.com/oauth2/aus14v9gf4ibMdMwb0h8").rstrip("/")
OKTA_CLIENT_ID = os.getenv("OKTA_CLIENT_ID", "0oa151mc6jbCh3Ffo0h8")
OKTA_CLIENT_SECRET = os.getenv("OKTA_CLIENT_SECRET", "")
OKTA_AUDIENCE = os.getenv("OKTA_AUDIENCE", "APP3536703")
OKTA_SCOPES = os.getenv("OKTA_SCOPES", "openid profile email groups")
OKTA_REDIRECT_URI = os.getenv("OKTA_REDIRECT_URI", "http://localhost:8501")

AUTH_ENDPOINT = f"{OKTA_ISSUER}/v1/authorize"
TOKEN_ENDPOINT = f"{OKTA_ISSUER}/v1/token"
USERINFO_ENDPOINT = f"{OKTA_ISSUER}/v1/userinfo"


def generate_pkce_pair() -> tuple[str, str]:
    """
    Generate PKCE code_verifier and code_challenge (S256).
    """
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return code_verifier, code_challenge


def get_authorization_url(redirect_uri: Optional[str] = None, state: Optional[str] = None, code_challenge: Optional[str] = None) -> str:
    """
    Build Okta PurpleID authorization URL.
    """
    from urllib.parse import urlencode

    redir = redirect_uri or OKTA_REDIRECT_URI
    st = state or secrets.token_urlsafe(16)

    params = {
        "client_id": OKTA_CLIENT_ID,
        "response_type": "code",
        "scope": OKTA_SCOPES,
        "redirect_uri": redir,
        "state": st,
    }
    if OKTA_AUDIENCE:
        params["audience"] = OKTA_AUDIENCE
    if code_challenge:
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"

    return f"{AUTH_ENDPOINT}?{urlencode(params)}"


def decode_jwt_payload(jwt_token: str) -> Dict[str, Any]:
    """
    Extract and decode the payload of a JWT without external network validation.
    """
    if not jwt_token or "." not in jwt_token:
        return {}
    try:
        parts = jwt_token.strip().split(".")
        if len(parts) < 2:
            return {}
        payload_b64 = parts[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        return json.loads(payload_bytes)
    except Exception:
        return {}


def is_token_valid(jwt_token: str, skew_seconds: int = 60) -> bool:
    """
    Check if a JWT token has not expired.
    """
    payload = decode_jwt_payload(jwt_token)
    if not payload:
        return False
    exp = payload.get("exp")
    if not exp:
        return False
    return time.time() < (exp - skew_seconds)


def get_token_expiration_str(jwt_token: str) -> str:
    """
    Return human-readable expiration time for a token.
    """
    payload = decode_jwt_payload(jwt_token)
    exp = payload.get("exp")
    if not exp:
        return "Unknown"
    dt = datetime.fromtimestamp(exp)
    remaining_mins = int((exp - time.time()) / 60)
    if remaining_mins > 0:
        return f"{dt.strftime('%H:%M:%S')} (in {remaining_mins} mins)"
    return f"Expired at {dt.strftime('%H:%M:%S')}"


def fetch_user_info_from_okta(access_token: str) -> Optional[Dict[str, Any]]:
    """
    Call the Okta /v1/userinfo endpoint using the access token.
    This dynamically retrieves the full user profile (name, given_name, family_name, email).
    """
    if not access_token:
        return None
    try:
        url = f"{OKTA_ISSUER}/v1/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        with httpx.Client(verify=False, timeout=5) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return None


def extract_user_info(jwt_token: str, id_token: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract user details (name, email, employeeNumber, station) dynamically from JWT claims.
    """
    payload = decode_jwt_payload(jwt_token) if jwt_token else {}

    # If id_token provided, merge profile claims
    if id_token:
        id_payload = decode_jwt_payload(id_token)
        for k in ("name", "displayName", "given_name", "firstName", "family_name", "preferred_username", "email", "sub"):
            if id_payload.get(k):
                payload[k] = id_payload[k]

    sub = payload.get("sub", "")
    email = payload.get("email", sub)
    emp_num = payload.get("employeeNumber", "N/A")

    # 1. Check explicit name claims from Okta / PurpleID token
    display_name = (
        payload.get("name")
        or payload.get("displayName")
        or payload.get("given_name")
        or payload.get("firstName")
    )
    if not display_name and payload.get("family_name"):
        display_name = payload.get("family_name")

    # If not in token claims, query Okta /v1/userinfo endpoint dynamically
    if not display_name and jwt_token:
        okta_profile = fetch_user_info_from_okta(jwt_token)
        if okta_profile:
            display_name = (
                okta_profile.get("name")
                or okta_profile.get("displayName")
                or okta_profile.get("given_name")
            )
            if not display_name and okta_profile.get("given_name"):
                gn = okta_profile.get("given_name", "")
                fn = okta_profile.get("family_name", "")
                display_name = f"{gn} {fn}".strip()
            if okta_profile.get("email"):
                email = okta_profile.get("email")

    # 2. Derive from preferred_username, email prefix, or sub if not purely numeric
    if not display_name:
        candidate = payload.get("preferred_username") or email or sub
        prefix = candidate.split("@")[0] if "@" in candidate else candidate
        if prefix and not prefix.isdigit():
            # Format "first.last" or "john_doe" -> "First Last"
            cleaned = prefix.replace("_", " ").replace(".", " ").strip()
            display_name = " ".join(part.capitalize() for part in cleaned.split() if part)

    # 3. Check environment or configuration override (e.g. USER_DISPLAY_NAME in .env)
    if not display_name or display_name.lower().startswith("fedex user"):
        env_name = os.getenv("USER_DISPLAY_NAME") or os.getenv("FEDEX_USER_NAME")
        if env_name and env_name.strip():
            display_name = env_name.strip()

    # 4. Fallback if still unknown
    if not display_name:
        display_name = f"FedEx User ({emp_num})" if emp_num != "N/A" else "FedEx User"

    return {
        "display_name": display_name,
        "email": email,
        "sub": sub,
        "employee_number": emp_num,
        "station": payload.get("comatStation") or payload.get("globalLocationId", "N/A"),
        "location": payload.get("globalLocationName", "N/A"),
        "groups": payload.get("groups", []),
        "exp": payload.get("exp"),
        "is_valid": is_token_valid(jwt_token) if jwt_token else False,
    }


def extract_info_from_cookie(cookie_str: str) -> Dict[str, Any]:
    """
    Parse a cookie header string to dynamically find any embedded JWT tokens
    or user identity attributes (purpleid_token, id_token, access_token, user, etc.).
    """
    if not cookie_str:
        return {}

    # Look for embedded JWT tokens inside the cookie string
    import re
    jwt_pattern = re.compile(r'eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]+')
    jwt_matches = jwt_pattern.findall(cookie_str)
    for jwt_candidate in jwt_matches:
        try:
            info = extract_user_info(jwt_candidate)
            if info and info.get("display_name") and not info.get("display_name").startswith("FedEx User"):
                return info
        except Exception:
            continue

    env_name = os.getenv("USER_DISPLAY_NAME") or os.getenv("FEDEX_USER_NAME")
    result: Dict[str, Any] = {
        "display_name": env_name or None,
        "email": "FedEx Session (Cookie)",
        "station": "PITCO",
        "employee_number": "Cookie-Auth",
    }

    pairs = [item.strip() for item in cookie_str.split(";") if "=" in item]
    for pair in pairs:
        k, _, v = pair.partition("=")
        k_clean = k.strip().lower()
        v_clean = v.strip()
        if k_clean in ("user", "username", "displayname", "name", "fedexuser") and v_clean:
            import urllib.parse
            unquoted = urllib.parse.unquote(v_clean).strip('"\'')
            if unquoted and not unquoted.isdigit():
                parts = unquoted.replace(".", " ").replace("_", " ").split()
                result["display_name"] = " ".join(p.capitalize() for p in parts)
            elif unquoted:
                result["display_name"] = f"FedEx User ({unquoted})"
        elif k_clean in ("employeenumber", "emp_id", "empid", "uid") and v_clean:
            result["employee_number"] = v_clean
        elif k_clean in ("station", "location", "comatstation") and v_clean:
            result["station"] = v_clean.upper()
        elif k_clean == "email" and "@" in v_clean:
            result["email"] = v_clean

    return result


def exchange_code_for_token(code: str, redirect_uri: Optional[str] = None, code_verifier: Optional[str] = None) -> Dict[str, Any]:
    """
    Exchange authorization code for access token.
    """
    data = {
        "grant_type": "authorization_code",
        "client_id": OKTA_CLIENT_ID,
        "code": code,
        "redirect_uri": redirect_uri or OKTA_REDIRECT_URI,
    }
    if OKTA_CLIENT_SECRET:
        data["client_secret"] = OKTA_CLIENT_SECRET
    if code_verifier:
        data["code_verifier"] = code_verifier

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    try:
        with httpx.Client(verify=False, timeout=15) as client:
            resp = client.post(TOKEN_ENDPOINT, data=data, headers=headers)
            if resp.status_code == 200:
                return {"success": True, "data": resp.json()}
            return {
                "success": False,
                "error": f"Token exchange failed (HTTP {resp.status_code}): {resp.text}",
            }
    except Exception as e:
        return {"success": False, "error": str(e)}
