#!/usr/bin/env python3
"""
HTTP Wrapper for MCP Server
Provides HTTP endpoints that proxy to FedEx API
"""

import os
import logging
from typing import Any, Optional, Dict
from pathlib import Path
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import uvicorn

# Load environment variables from server directory, workspace root, and client directory
_SERVER_DIR = Path(__file__).resolve().parent
load_dotenv(_SERVER_DIR / ".env")
load_dotenv(_SERVER_DIR.parent / ".env")
load_dotenv(_SERVER_DIR.parent / "ReportAutomation" / ".env")

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
API_BASE_URL = os.getenv("INTERNAL_API_BASE_URL", "").rstrip("/")
API_KEY = os.getenv("INTERNAL_API_KEY")
API_COOKIE = os.getenv("INTERNAL_API_COOKIE", "")
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))
MCP_SERVER_PORT = int(os.getenv("MCP_SERVER_PORT", "8001"))
VERIFY_SSL = os.getenv("VERIFY_SSL", "true").lower() == "true"

if API_BASE_URL:
    logger.info(f"HTTP MCP Server proxy target: {API_BASE_URL}")
else:
    logger.warning("INTERNAL_API_BASE_URL not set. Configure via .env or Streamlit secrets.")

logger.info(f"HTTP MCP Server starting on port {MCP_SERVER_PORT}")
logger.info(f"SSL Verification: {VERIFY_SSL}")

# Create FastAPI app
app = FastAPI(title="MCP HTTP Server", version="1.0.0")

# HTTP client
http_client = httpx.AsyncClient(timeout=API_TIMEOUT, verify=VERIFY_SSL)


async def make_api_request(
    endpoint: str,
    method: str = "GET",
    data: Optional[dict] = None,
    params: Optional[dict] = None,
    auth_token: Optional[str] = None,
    cookies: Optional[str] = None
) -> Dict[str, Any]:
    """
    Make an HTTP request to the configured API
    
    Args:
        endpoint: API endpoint path
        method: HTTP method (GET, POST)
        data: Request body data
        params: Query parameters
        auth_token: Optional dynamic Bearer token (overrides env INTERNAL_API_KEY)
        cookies: Optional dynamic Cookie header string
        
    Returns:
        dict containing the API response
    """
    base_url = (os.getenv("INTERNAL_API_BASE_URL") or API_BASE_URL or "").rstrip("/")
    if not base_url:
        return {
            "status": "error",
            "error": "INTERNAL_API_BASE_URL is not configured. Please add it to your environment or Streamlit secrets.",
            "status_code": 500
        }
    clean_endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    url = f"{base_url}{clean_endpoint}"
    
    # Prepare headers
    request_headers = {"Content-Type": "application/json"}
    effective_key = auth_token or os.getenv("INTERNAL_API_KEY") or API_KEY
    if effective_key:
        request_headers["Authorization"] = f"Bearer {effective_key}"
    
    effective_cookie = cookies or os.getenv("INTERNAL_API_COOKIE") or API_COOKIE
    if effective_cookie:
        request_headers["Cookie"] = effective_cookie
    
    try:
        logger.debug(f"Making {method} request to {url}")
        response = await http_client.request(
            method=method.upper(),
            url=url,
            json=data,
            params=params,
            headers=request_headers
        )
        response.raise_for_status()
        logger.info(f"Request successful: {method} {url} - Status {response.status_code}")
        
        return {
            "status": "success",
            "status_code": response.status_code,
            "data": response.json() if response.text else {}
        }
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
        return {
            "status": "error",
            "status_code": e.response.status_code,
            "error": str(e),
            "response_text": e.response.text
        }
    except Exception as e:
        logger.exception(f"Request failed: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "MCP HTTP Server"}


@app.get("/api/get")
async def api_get(request: Request):
    """
    Proxy GET request to configured API
    Query params: endpoint, and any other params to forward
    """
    params = dict(request.query_params)
    endpoint = params.pop("endpoint", None)
    
    if not endpoint:
        raise HTTPException(status_code=400, detail="endpoint parameter is required")
    
    # Allow dynamic Bearer token from incoming Authorization header
    auth_header = request.headers.get("authorization", "")
    auth_token = auth_header.replace("Bearer ", "").strip() if auth_header.startswith("Bearer ") else (auth_header.strip() or None)
    
    # Allow dynamic Cookie header forwarding
    cookie_header = request.headers.get("cookie", "") or None
    
    result = await make_api_request(endpoint, method="GET", params=params, auth_token=auth_token, cookies=cookie_header)
    
    if result.get("status") == "error":
        status_code = result.get("status_code", 500)
        raise HTTPException(status_code=status_code, detail=result)
    
    return JSONResponse(content=result)


@app.post("/api/post")
async def api_post(request: Request):
    """
    Proxy POST request to configured API
    Body should contain: endpoint, data
    """
    try:
        body = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    
    endpoint = body.get("endpoint")
    data = body.get("data")
    
    if not endpoint:
        raise HTTPException(status_code=400, detail="endpoint is required in request body")
    
    # Allow dynamic Bearer token from incoming Authorization header
    auth_header = request.headers.get("authorization", "")
    auth_token = auth_header.replace("Bearer ", "").strip() if auth_header.startswith("Bearer ") else (auth_header.strip() or None)
    
    # Allow dynamic Cookie header forwarding
    cookie_header = request.headers.get("cookie", "") or None
    
    result = await make_api_request(endpoint, method="POST", data=data, auth_token=auth_token, cookies=cookie_header)
    
    if result.get("status") == "error":
        status_code = result.get("status_code", 500)
        raise HTTPException(status_code=status_code, detail=result)
    
    return JSONResponse(content=result)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await http_client.aclose()


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=MCP_SERVER_PORT,
        log_level=LOG_LEVEL.lower()
    )

