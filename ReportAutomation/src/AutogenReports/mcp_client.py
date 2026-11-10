"""
MCP Client for FedEx API and Cassandra DB Integration
- fetch_non_delivered_tracking_ids: calls the MCP HTTP Server for FedEx data
- connect_cassandra / disconnect_cassandra: manage the Cassandra connection lifecycle
- cassandra_execute_query / cassandra_list_tables / cassandra_select_table: query tools
"""
import json
import logging
import os
import ssl
import struct
import sys
from pathlib import Path
from typing import Optional

import httpx

# Ensure workspace and ReportingMCPServer are in sys.path
_CLIENT_DIR = Path(__file__).resolve().parent
_WORKSPACE_ROOT = _CLIENT_DIR.parent.parent.parent
if str(_WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_ROOT))
if str(_WORKSPACE_ROOT / "ReportingMCPServer") not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_ROOT / "ReportingMCPServer"))

# ── asyncore backport (required by cassandra-driver on Python 3.12) ──────────
try:
    import asyncore  # type: ignore[import-untyped]  # noqa: F401  – pyasyncore backport
except ImportError:
    pass

# ── Cassandra driver ──────────────────────────────────────────────────────────
try:
    from cassandra.cluster import Cluster  # type: ignore[import-untyped]
    from cassandra.auth import PlainTextAuthProvider  # type: ignore[import-untyped]
    from cassandra.policies import DCAwareRoundRobinPolicy  # type: ignore[import-untyped]
    from cassandra.query import SimpleStatement  # type: ignore[import-untyped]
    import cassandra.cqltypes as _cqltypes  # type: ignore[import-untyped]

    # Patch DateType to handle out-of-range timestamps that Python datetime cannot represent.
    _orig_date_deserialize = _cqltypes.DateType.deserialize

    @staticmethod  # type: ignore[misc]
    def _safe_date_deserialize(byts, protocol_version):
        try:
            return _orig_date_deserialize(byts, protocol_version)
        except Exception:
            ms = struct.unpack(">q", byts)[0]
            return f"<timestamp:{ms}ms>"

    _cqltypes.DateType.deserialize = _safe_date_deserialize  # type: ignore[method-assign]

    CASSANDRA_AVAILABLE = True
except Exception as _cass_err:
    logging.warning("cassandra-driver not available: %s", _cass_err)
    CASSANDRA_AVAILABLE = False

# ── Cassandra session globals ─────────────────────────────────────────────────
_cluster = None
_session = None
_keyspace = ""

# ── MCP HTTP Server ───────────────────────────────────────────────────────────
MCP_SERVER_URL = "http://127.0.0.1:8001"
http_client = httpx.AsyncClient(timeout=30.0)
_current_auth_token: Optional[str] = None
_current_cookie: Optional[str] = None

def set_auth_token(token: Optional[str]) -> None:
    """Set dynamic bearer token (e.g. from Okta login session) to forward to MCP Server."""
    global _current_auth_token
    _current_auth_token = token

def get_auth_token() -> Optional[str]:
    """Get currently active bearer token."""
    return _current_auth_token

def set_auth_cookie(cookie_str: Optional[str]) -> None:
    """Set dynamic cookie string to forward to MCP Server."""
    global _current_cookie
    _current_cookie = cookie_str

def get_auth_cookie() -> Optional[str]:
    """Get currently active cookie string."""
    return _current_cookie


# ─────────────────────────────────────────────────────────────────────────────
# Cassandra lifecycle
# ─────────────────────────────────────────────────────────────────────────────

def connect_cassandra(config_path: str = "cassandra_mcp_config.json") -> bool:
    """
    Connect to Cassandra using the JSON config file.
    Populates module-level _cluster, _session, _keyspace.
    Returns True on success, False on failure.
    """
    global _cluster, _session, _keyspace

    if not CASSANDRA_AVAILABLE:
        logging.warning("cassandra-driver unavailable — skipping Cassandra connection")
        return False

    path = Path(config_path)
    if not path.exists():
        logging.warning("%s not found — skipping Cassandra connection", config_path)
        return False

    with open(path) as f:
        cfg = json.load(f)

    host = cfg.get("host", "127.0.0.1")
    port = cfg.get("port", 9042)
    _keyspace = cfg.get("keyspace", "")
    username = cfg.get("username", "")
    password = cfg.get("password", "")
    datacenter = cfg.get("datacenter", "datacenter1")

    try:
        auth = PlainTextAuthProvider(username=username, password=password) if username else None
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        _cluster = Cluster(
            contact_points=[host],
            port=port,
            auth_provider=auth,
            load_balancing_policy=DCAwareRoundRobinPolicy(local_dc=datacenter),
            ssl_context=ssl_ctx,
            connect_timeout=30,
            control_connection_timeout=30,
        )
        _session = _cluster.connect(_keyspace if _keyspace else None)
        logging.info("Cassandra connected: host=%s keyspace=%s", host, _keyspace)
        return True
    except Exception as exc:
        logging.warning("Cassandra connection failed: %s", exc)
        return False


def disconnect_cassandra() -> None:
    """Shut down the Cassandra cluster connection."""
    global _cluster, _session
    if _cluster:
        _cluster.shutdown()
        _cluster = None
        _session = None
        logging.info("Cassandra connection closed")


# ─────────────────────────────────────────────────────────────────────────────
# Cassandra query tools
# ─────────────────────────────────────────────────────────────────────────────

def cassandra_execute_query(cql: str, limit: int = 100) -> str:
    """
    Execute a CQL SELECT query against Cassandra.
    Args:
        cql:   CQL SELECT statement, e.g. 'SELECT * FROM orders LIMIT 10'
        limit: Max rows to return (default 100)
    Returns JSON string with row_count and data.
    """
    if _session is None:
        return json.dumps({"status": "error", "error": "Cassandra session not available"})
    try:
        if not cql.strip().upper().startswith("SELECT"):
            return json.dumps({"status": "error", "error": "Only SELECT queries are allowed"})
        rows = _session.execute(SimpleStatement(cql, fetch_size=limit))
        data = [dict(r._asdict()) for r in rows][:limit]
        return json.dumps({"status": "success", "row_count": len(data), "data": data}, default=str)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})


def cassandra_list_tables(keyspace_name: str = "") -> str:
    """
    List all tables in the configured Cassandra keyspace (fxg_pd_portal_l3_ks).
    Args:
        keyspace_name: Leave empty to use the pre-configured keyspace. Only set if
                       explicitly targeting a different keyspace.
    Returns JSON list of table names.
    """
    if _session is None:
        return json.dumps({"status": "error", "error": "Cassandra session not available"})
    try:
        ks = keyspace_name or _keyspace
        rows = _session.execute(
            "SELECT table_name FROM system_schema.tables WHERE keyspace_name = %s", [ks]
        )
        tables = [r.table_name for r in rows]
        return json.dumps({"status": "success", "keyspace": ks, "tables": tables})
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})


def cassandra_select_table(table: str, limit: int = 100) -> str:
    """
    Fetch rows from a Cassandra table using SELECT *.
    Args:
        table: Table name (optionally keyspace.table)
        limit: Max rows to return (default 100)
    Returns JSON with row_count and data.
    """
    if _session is None:
        return json.dumps({"status": "error", "error": "Cassandra session not available"})
    try:
        tbl = table if "." in table else f"{_keyspace}.{table}"
        rows = _session.execute(SimpleStatement(f"SELECT * FROM {tbl} LIMIT {limit}"))
        data = [dict(r._asdict()) for r in rows]
        return json.dumps({"status": "success", "table": tbl, "row_count": len(data), "data": data}, default=str)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})


# ─────────────────────────────────────────────────────────────────────────────
# Cassandra PDF export
# ─────────────────────────────────────────────────────────────────────────────

def generate_cassandra_pdf(
    query_or_table: str,
    title: str = "",
    page_size: str = "letter",
    orientation: str = "landscape",
    columns: Optional[str] = None,
    max_records: Optional[int] = None,
    limit: int = 500,
) -> str:
    """
    Generate a PDF from a Cassandra table or CQL SELECT query and save it.
    Args:
        query_or_table: A table name (e.g. 'delivery_packages') OR a full CQL SELECT statement.
        title:          PDF title. Auto-generated from the table/query if empty.
        page_size:      letter (default), A4, or legal.
        orientation:    landscape (default) or portrait.
        columns:        Comma-separated column names to include. All columns used if empty.
        max_records:    Maximum rows to include in the PDF.
        limit:          Max rows to fetch from Cassandra (default 500).
    Returns JSON with filename, filepath and download_url.
    """
    if _session is None:
        return json.dumps({"success": False, "error": "Cassandra session not available"})

    try:
        # Build CQL
        if query_or_table.strip().upper().startswith("SELECT"):
            cql = query_or_table.strip()
            table_label = "cassandra_query"
        else:
            tbl = query_or_table if "." in query_or_table else f"{_keyspace}.{query_or_table}"
            cql = f"SELECT * FROM {tbl} LIMIT {limit}"
            table_label = query_or_table.split(".")[-1]

        rows = _session.execute(SimpleStatement(cql, fetch_size=limit))
        records = [dict(r._asdict()) for r in rows][:limit]

        if not records:
            return json.dumps({"success": False, "error": f"No data returned for: {query_or_table}"})

        # Wrap in the format pdf_generator expects
        data = {"status": "success", "data": {"results": records}}

        # Lazy import to avoid circular deps at module load time
        from .pdf_generator import generate_pdf_report, PDFReportConfig  # type: ignore

        column_list = [c.strip() for c in columns.split(",")] if columns else None
        pdf_title = title or f"Cassandra Report — {table_label}"

        config = PDFReportConfig(
            page_size=page_size,
            orientation=orientation,
            title=pdf_title,
            columns=column_list,
            max_records=max_records,
        )

        pdf_bytes = generate_pdf_report(data=data, config=config)

        filename = f"Cassandra_{table_label}.pdf"
        filepath = os.path.join(os.getcwd(), filename)
        with open(filepath, "wb") as f:
            f.write(pdf_bytes)

        return json.dumps({
            "success": True,
            "message": "PDF generated successfully",
            "filename": filename,
            "filepath": filepath,
            "record_count": len(records),
            "file_size_kb": round(len(pdf_bytes) / 1024, 2),
            "download_url": f"http://127.0.0.1:8000/download/{filename}",
        }, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


# ─────────────────────────────────────────────────────────────────────────────
# FedEx API (via MCP HTTP Server)
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_non_delivered_tracking_ids(
    facilityId: Optional[int] = None,
    scanDate: Optional[str] = None,
    stationCode: Optional[str] = None,
    limit: Optional[int] = None
) -> str:
    """
    Fetch non-delivered tracking IDs via MCP HTTP Server.

    Args:
        facilityId: Facility ID (e.g. 88). Defaults to 88 if not specified.
        scanDate: Scan date for the report (YYYY-MM-DD). If omitted or 'today', uses current date YYYY-MM-DD automatically.
        stationCode: Station code filter (optional, e.g. 'PITG')
        limit: Maximum number of records (optional)

    Returns:
        JSON string with tracking IDs and report data
    """
    try:
        from datetime import date
        params = {"endpoint": "/getNonDeliveredTrackingIDs"}

        # Upstream FedEx API requires facilityId (defaults to 88 if omitted or not provided)
        effective_facility_id = facilityId if facilityId is not None else 88
        params["facilityId"] = str(effective_facility_id)
        
        # If scanDate is omitted or passed as 'today', default to today's date
        today_iso = date.today().isoformat()
        if not scanDate or scanDate.strip().lower() in ("today", "current", "now"):
            params["scanDate"] = today_iso
        else:
            cleaned_date = scanDate.strip()
            # Guard against LLM cutoff dates (e.g. 2023-XX-XX) which fail upstream DAO
            if cleaned_date.startswith("2023-") or cleaned_date.startswith("2024-") or cleaned_date.startswith("2025-"):
                params["scanDate"] = today_iso
            else:
                params["scanDate"] = cleaned_date

        if stationCode:
            params["stationCode"] = stationCode
        if limit:
            params["limit"] = str(limit)

        headers = {}
        if _current_auth_token:
            headers["Authorization"] = f"Bearer {_current_auth_token}"
        if _current_cookie:
            headers["Cookie"] = _current_cookie

        response = await http_client.get(f"{MCP_SERVER_URL}/api/get", params=params, headers=headers)
        response.raise_for_status()

        mcp_response = response.json()

        if mcp_response.get("status") == "success":
            return json.dumps({
                "status": "success",
                "data": mcp_response.get("data"),
                "message": "Successfully fetched tracking records via MCP Server"
            }, indent=2)
        else:
            return json.dumps({
                "status": "error",
                "error": mcp_response.get("error", "Unknown error from MCP server"),
                "message": "MCP Server returned an error"
            }, indent=2)

    except (httpx.ConnectError, httpx.ConnectTimeout):
        # Seamless in-process fallback when running in unified deployment without separate MCP process
        try:
            from ReportingMCPServer.server import make_api_request
            endpoint_path = params.pop("endpoint", "/api/v1/packages/non-delivered")
            direct_res = await make_api_request(
                endpoint=endpoint_path,
                method="GET",
                params=params,
                auth_token=_current_auth_token,
                cookies=_current_cookie
            )
            if direct_res.get("status") == "success":
                return json.dumps({
                    "status": "success",
                    "data": direct_res.get("data"),
                    "message": "Successfully fetched tracking records via in-process MCP Server"
                }, indent=2)
            else:
                return json.dumps({
                    "status": "error",
                    "error": direct_res.get("error", "Unknown error from in-process MCP server"),
                    "message": "In-process MCP Server returned an error"
                }, indent=2)
        except Exception as fallback_err:
            return json.dumps({
                "status": "error",
                "error": str(fallback_err),
                "message": f"MCP Server unreachable at {MCP_SERVER_URL} and in-process fallback encountered error."
            }, indent=2)
    except httpx.HTTPStatusError as e:
        return json.dumps({
            "status": "error",
            "error": f"HTTP {e.response.status_code}: {e.response.text}",
            "message": "MCP Server request failed"
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "message": "An unexpected error occurred while communicating with MCP Server"
        }, indent=2)
