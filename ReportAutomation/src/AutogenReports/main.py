from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
import httpx
import json

from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.tools import FunctionTool

from .mcp_client import (
    fetch_non_delivered_tracking_ids,
    connect_cassandra,
    disconnect_cassandra,
    cassandra_execute_query,
    cassandra_list_tables,
    cassandra_select_table,
    generate_cassandra_pdf,
)
from .pdf_generator import generate_pdf_report, PDFReportConfig
from pathlib import Path

# load the key from environment
load_dotenv()
_mcp_env = Path(__file__).resolve().parents[3] / "ReportingMCPServer" / ".env"
if _mcp_env.exists():
    load_dotenv(_mcp_env)

api_key = os.getenv("OPENAI_API_KEY")

# Create async httpx client with SSL verification disabled (for corporate proxies/firewalls)
http_client = httpx.AsyncClient(verify=False)

# Function to generate PDF and return file info
async def generate_pdf_for_agent(
    facilityId: Optional[int] = 88,
    scanDate: Optional[str] = None,
    stationCode: Optional[str] = None,
    limit: Optional[int] = None,
    columns: Optional[str] = None,
    page_size: str = "letter",
    orientation: str = "portrait",
    include_summary: bool = True,
    max_records: Optional[int] = None
) -> str:
    """
    Generate PDF report and save it, returning download information for the agent.

    Args:
        facilityId: Facility ID (e.g. 88, defaults to 88 if not specified)
        scanDate: Scan date (YYYY-MM-DD). Defaults to today if not provided.
        stationCode: Station code filter (optional, e.g. 'PITG')
        limit: Record limit for API call (optional)
        columns: Comma-separated column names (optional). If not specified, ALL available columns
                 from the API response are automatically included in the PDF.
        page_size: letter, A4, or legal
        orientation: portrait or landscape
        include_summary: Include summary section
        max_records: Maximum number of records to include in PDF (optional)
    """
    try:
        from datetime import date
        if not scanDate or scanDate.strip().lower() in ("today", "current", "now"):
            scanDate = date.today().isoformat()

        effective_facility_id = facilityId if facilityId is not None else 88

        # Fetch data
        tracking_data_json = await fetch_non_delivered_tracking_ids(
            facilityId=effective_facility_id,
            scanDate=scanDate,
            stationCode=stationCode,
            limit=limit
        )

        tracking_data = json.loads(tracking_data_json)

        if tracking_data.get('status') == 'error':
            return json.dumps({
                "success": False,
                "error": tracking_data.get('message', 'Failed to fetch data')
            })

        # Parse columns if provided
        column_list = None
        if columns:
            column_list = [col.strip() for col in columns.split(',')]

        # Auto-detect column count to decide orientation when user hasn't specified
        if orientation == "portrait" and column_list is None:
            api_data = tracking_data.get('data', {})
            if isinstance(api_data, dict):
                sample_records = api_data.get('nonDeliveredTrackingDetails', [])
                if not sample_records:
                    # Walk one level deeper (data may be nested)
                    inner = api_data.get('data', {})
                    sample_records = inner.get('nonDeliveredTrackingDetails', []) if isinstance(inner, dict) else []
            else:
                sample_records = []
            if sample_records and isinstance(sample_records[0], dict):
                if len(sample_records[0].keys()) > 5:
                    orientation = "landscape"

        # Generate PDF with customization
        pdf_config = PDFReportConfig(
            page_size=page_size,
            orientation=orientation,
            title=f"FedEx Non-Delivered Report - {scanDate}",
            include_summary=include_summary,
            columns=column_list,
            max_records=max_records
        )

        metadata = {
            "Facility_ID": facilityId,
            "Scan_Date": scanDate,
            "Station_Code": stationCode or "All",
            "Record_Limit": limit or "No Limit"
        }

        pdf_bytes = generate_pdf_report(data=tracking_data, metadata=metadata, config=pdf_config)

        # Save PDF
        filename = f"FedEx_Report_{scanDate}_{facilityId}.pdf"
        filepath = os.path.join(os.getcwd(), filename)

        with open(filepath, 'wb') as f:
            f.write(pdf_bytes)

        file_size = len(pdf_bytes) / 1024

        # Get record count
        api_data = tracking_data.get('data', {})
        tracking_details = api_data.get('nonDeliveredTrackingDetails', []) if isinstance(api_data, dict) else []

        return json.dumps({
            "success": True,
            "message": "PDF report generated successfully!",
            "filename": filename,
            "filepath": filepath,
            "file_size_kb": round(file_size, 2),
            "record_count": len(tracking_details),
            "download_url": f"http://127.0.0.1:8000/download/{filename}",
            "instructions": "PDF file has been saved. You can download it using the provided URL or find it in the application directory."
        }, indent=2)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Failed to generate PDF: {str(e)}"
        })

# Create tools for the agent
fetch_report_tool = FunctionTool(
    fetch_non_delivered_tracking_ids,
    description="""Fetch non-delivered tracking IDs report from FedEx API. Use this to retrieve shipment tracking numbers that have not been delivered.
    Use this when the user has provided or confirmed the input parameters.
    Parameters:
    - facilityId: Facility ID (e.g. 88).
    - scanDate: Scan date (YYYY-MM-DD). If omitted or 'today', defaults to today.
    - stationCode: Station code filter (optional, e.g. 'PITG').
    - limit: Maximum number of records (optional)."""
)

generate_pdf_tool = FunctionTool(
    generate_pdf_for_agent,
    description="""Generate a PDF report for non-delivered tracking IDs with full customization options.
    IMPORTANT: Use this tool ONLY AFTER the user has provided or confirmed the input parameters (facilityId, scanDate, stationCode, etc.). Do not call this tool before asking for or confirming parameters with the user.

    Parameters:
    - facilityId: Facility ID (e.g. 88).
    - scanDate: Scan date (YYYY-MM-DD).
    - stationCode: Station code filter (optional, e.g. 'PITG').
    - columns: Select specific columns (optional).
    - page_size: letter (default), A4, or legal.
    - orientation: portrait (default) or landscape.
    - include_summary: true (default) or false.
    - max_records: Limit number of records in PDF (optional).

    Returns file information and download link."""
)

model_client = OpenAIChatCompletionClient(
    model='gpt-4o',
    api_key=api_key,
    http_client=http_client
)

_base_tools = [fetch_report_tool, generate_pdf_tool]

SYSTEM_PROMPT = (
    "You are an expert AI assistant that helps users analyze FedEx operations, fetch tracking data, and generate PDF reports.\n\n"
    f"CRITICAL DATE RULES:\n"
    f"- Today's real-world date is {datetime.now().strftime('%Y-%m-%d')} (Current Year: {datetime.now().year}).\n"
    f"- NEVER use dates from 2023 or earlier cutoff dates.\n"
    f"- When user says 'today', use {datetime.now().strftime('%Y-%m-%d')}.\n"
    f"- When user asks for 'last 7 days' or 'past 1 week', the date range is {(datetime.now().date() - timedelta(days=6)).isoformat()} to {datetime.now().date().isoformat()}.\n\n"
    "CRITICAL MANDATORY WORKFLOW FOR GENERATING REPORTS:\n"
    "Whenever a user asks to generate a report, create a PDF report, or run a summary report:\n"
    "1. DO NOT call report generation tools immediately without first asking for or confirming the input parameters.\n"
    "2. FIRST ask the user to provide or confirm the required input parameters in a polite, clearly formatted list:\n"
    "   - **Facility ID**: (e.g., `88`)\n"
    f"   - **Scan Date or Date Range**: (e.g., `Today ({datetime.now().strftime('%Y-%m-%d')})`, a specific date `YYYY-MM-DD`, or `Last 7 Days`)\n"
    "   - **Station Code**: (Optional, e.g., `PITG` or `All Stations`)\n"
    "   - **Report Preferences**: (Optional: record limits, orientation like portrait/landscape, or specific columns)\n"
    "3. If the user's initial message already specified some parameters (for example, 'Facility 88' and 'Last 7 Days'), "
    "summarize what you have gathered, ask for any remaining optional filters (such as Station Code or record limit), "
    "and ask for their final confirmation before generating.\n"
    "4. Once the user provides the parameters or confirms, proceed to call the tool and generate the report."
)

assistant_agent = AssistantAgent(
    name="ReportingAssistant",
    model_client=model_client,
    system_message=SYSTEM_PROMPT,
    description=(
        "An assistant that helps fetch and analyze FedEx non-delivered tracking reports and generate PDFs. "
        f"Today's real date is {datetime.now().strftime('%Y-%m-%d')}."
    ),
    tools=_base_tools
)

class LLMRequest(BaseModel):
    question: str = Field(..., description="Question to ask the AI")

class ApiResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

app = FastAPI(title="Pnd AutoGen Agent",
              description="A FastAPI application that integrates with an AutoGen Agent to generate responses based on user questions.",
             version="1.0.0")

@app.on_event("startup")
async def load_cassandra_tools():
    """Connect to Cassandra via mcp_client and register query tools with the agent."""
    global assistant_agent

    connected = connect_cassandra()
    if not connected:
        return

    cassandra_tools = [
        FunctionTool(cassandra_execute_query, description="Execute a CQL SELECT query against Cassandra DB. Use this when the user asks to query or retrieve data from Cassandra."),
        FunctionTool(cassandra_list_tables,   description="List all tables in the Cassandra keyspace. The keyspace is already configured — call this tool immediately with no arguments, do NOT ask the user for a keyspace name."),
        FunctionTool(cassandra_select_table,  description="Fetch all rows from a Cassandra table (SELECT *). Use when the user wants to see contents of a specific table. The keyspace is pre-configured — just pass the table name, do NOT ask the user for a keyspace."),
        FunctionTool(generate_cassandra_pdf,  description="""Generate a PDF report from a Cassandra table or CQL query and save it.
        Use this when the user asks to generate/download/export a PDF of Cassandra data.
        - query_or_table: table name (e.g. 'delivery_packages') or full CQL SELECT statement
        - title: optional PDF title
        - columns: optional comma-separated column names to include
        - max_records: optional row limit in the PDF
        - orientation: landscape (default) or portrait
        Returns a download link."""),
    ]

    assistant_agent = AssistantAgent(
        name="ReportingAssistant",
        model_client=model_client,
        system_message=SYSTEM_PROMPT,
        description=(
            "An assistant that fetches FedEx reports, generates PDFs, and queries Cassandra DB. "
            f"Today's real date is {datetime.now().strftime('%Y-%m-%d')}."
        ),
        tools=[*_base_tools, *cassandra_tools],
    )
    logging.info("AssistantAgent ready with %d tools (including 3 Cassandra tools)", len(_base_tools) + len(cassandra_tools))


@app.on_event("shutdown")
async def shutdown_cassandra():
    """Clean up Cassandra connection on app shutdown."""
    disconnect_cassandra()

_static_dir = Path(__file__).resolve().parent / "static"
_templates_dir = Path(__file__).resolve().parent / "uitemplate"

app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")
uitemplates = Jinja2Templates(directory=str(_templates_dir))

@app.get("/")
async def home(request: Request):
    # 1. Query parameter (?user=... or ?name=...) takes priority
    user_name = request.query_params.get("user") or request.query_params.get("name")
    
    # 2. Browser cookie set by user
    if not user_name:
        user_name = request.cookies.get("fedex_user_name")
    
    # 3. Environment override (USER_DISPLAY_NAME in .env)
    if not user_name:
        user_name = os.getenv("USER_DISPLAY_NAME") or os.getenv("FEDEX_USER_NAME")
    
    # 4. Token or cookie inspection
    token = os.getenv("INTERNAL_API_KEY", "")
    cookie = os.getenv("INTERNAL_API_COOKIE", "")
    if not user_name and token:
        try:
            from .okta_auth import extract_user_info
            info = extract_user_info(token)
            display = info.get("display_name")
            if display and not display.lower().startswith("fedex user"):
                user_name = display
        except Exception:
            pass
    if not user_name and cookie:
        try:
            from .okta_auth import extract_info_from_cookie
            info = extract_info_from_cookie(cookie)
            display = info.get("display_name")
            if display and not display.lower().startswith("fedex user"):
                user_name = display
        except Exception:
            pass
    if not user_name:
        user_name = "Twinkal"

    user_initial = user_name[0].upper() if user_name else "T"
    return uitemplates.TemplateResponse("agent_console.html", {
        "request": request,
        "user_name": user_name,
        "user_initial": user_initial,
    })


@app.get("/download/{filename}")
async def download_pdf(filename: str):
    """Download generated PDF files"""
    try:
        filepath = os.path.join(os.getcwd(), filename)

        if not os.path.exists(filepath):
            return JSONResponse(
                status_code=404,
                content={"error": "File not found"}
            )

        # Read file and return as response
        with open(filepath, 'rb') as f:
            pdf_content = f.read()

        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.post("/generate", response_model=ApiResponse)
async def generate_report(request: LLMRequest):
    try:
        # basic validation
        if not request.question or not request.question.strip():
            return JSONResponse(status_code=400, content={"error": "Question is required"})

        if not api_key:
            return JSONResponse(status_code=500, content={"error": "OPENAI_API_KEY not found in environment variables"})

        if assistant_agent is None:
            return JSONResponse(status_code=500, content={"error": "AssistantAgent is not initialized"})

        result_obj = await assistant_agent.run(task=request.question)

        # extract text from autogen response object
        if getattr(result_obj, "messages", None):
            try:
                result = result_obj.messages[-1].content
            except Exception:
                last_msg = result_obj.messages[-1]
                result = last_msg.get("content") if isinstance(last_msg, dict) else str(last_msg)
        else:
            result = getattr(result_obj, "content", None) or str(result_obj)

        logging.info("Generated Response via AssistantAgent: %s", result)

        if not result:
            result = "I apologize, but I couldn't generate a response. Please try rephrasing your question."

        return ApiResponse(success=True, data={"response": result})

    except Exception as e:
        error_message = str(e)
        logging.exception("ERROR in /generate")
        return JSONResponse(status_code=500, content={"error": error_message})
