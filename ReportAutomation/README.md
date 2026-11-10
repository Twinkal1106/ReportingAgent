# FedEx Non-Delivery Report Automation

An intelligent AutoGen-based agent system for generating customized PDF reports of non-delivered shipments, integrated with a centralized MCP Server for secure FedEx API access.

## Overview

This application provides a conversational interface powered by GPT-4o that:
- ✅ **Fetches non-delivery data** from FedEx API via centralized MCP Server
- ✅ **Generates customized PDF reports** with full layout control
- ✅ **Supports natural language requests** for complete customization
- ✅ **Centralized authentication** via MCP Server (no hardcoded tokens)
- ✅ **Multi-application support** - share API access with other apps

---

## Architecture

```
┌─────────────────┐
│  User Browser   │
│  Port: 8000     │
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────────┐
│  ReportAutomation   │
│  FastAPI + AutoGen  │
│  GPT-4o Agent       │
└────────┬────────────┘
         │ HTTP (MCP Protocol)
         ▼
┌─────────────────────┐
│   MCP HTTP Server   │
│   Port: 8001        │
│ (Bearer Token Auth) │
└────────┬────────────┘
         │ HTTPS + Bearer Token
         ▼
┌─────────────────────┐
│   FedEx API         │
│  (External)         │
└─────────────────────┘
```

**Key Change:** Migrated from direct FedEx API calls to **HTTP-based MCP Server** for centralized authentication and multi-application support.

---

## Quick Start

### Start Both Services

**Terminal 1 - MCP Server:**
```powershell
cd C:\Workspaces\Automation\ReportingMCPServer
.\start_server.ps1
```

**Terminal 2 - ReportAutomation Client:**
```powershell
cd C:\Workspaces\Automation\ReportAutomation
.\startupclient.ps1
```

### Access the Application
- **Web UI:** http://127.0.0.1:8000
- **API Docs:** http://127.0.0.1:8000/docs

### Generate Your First Report
Type in the chat interface:
```
"Generate PDF report for facility 88 on 2026-01-31"
```

Click the download button when it appears.

---

## Manual Setup

### Prerequisites
- Python 3.12
- MCP Server running on port 8001 (see ReportingMCPServer setup)

### Installation

1. **Navigate to project:**
   ```powershell
   cd C:\Workspaces\Automation\ReportAutomation
   ```

2. **Create virtual environment:**
   ```powershell
   python -m venv .venv
   ```

3. **Activate environment:**
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

4. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

5. **Run the application:**
   ```powershell
   uvicorn src.AutogenReports.main:app --host 127.0.0.1 --port 8000 --reload
   ```

---

## Configuration

### Environment Variables

The application automatically loads MCP server configuration from `ReportingMCPServer\.env`:

```env
# MCP Server Configuration (loaded automatically)
MCP_SERVER_PORT=8001
INTERNAL_API_BASE_URL=https://api-engine-release.app.clwdev4-az3.paas.fedex.com/v1/api-engine
INTERNAL_API_KEY=<Bearer Token>
VERIFY_SSL=false
```

**Note:** Bearer token is managed centrally in MCP Server's `.env` file - client never handles authentication directly.

### OpenAI Configuration

Requires OpenAI API key for GPT-4o agent:
```env
OPENAI_API_KEY=<your_openai_api_key>
```

Set via environment variable or system configuration.

---

## PDF Customization Guide

### Available Customizations

#### 1. **Column Selection**
Choose specific data fields to include.

**Available Columns:**
- `trackingId` - Tracking ID
- `deliveryRecordNumber` - Delivery Record Number
- `addressLine1` - Street Address
- `cityName` - City
- `stateCode` - State
- `postalCode` - Zip Code
- `reasonCode` - Reason Code
- `workAreaName` - Work Area

**Example Requests:**
- "Generate PDF with only tracking ID, city, and state"
- "Show just tracking number and address"
- "Include tracking ID, delivery record, city, state, and zip"

#### 2. **Record Limits**
Control the number of records in the PDF.

**Example Requests:**
- "Show only 10 records"
- "Generate PDF with first 20 entries"
- "Limit to 50 records"

#### 3. **Page Size**
Choose paper dimensions.

**Options:** `letter` (default), `A4`, `legal`

**Example Requests:**
- "Generate an A4 PDF"
- "Create report on legal paper"
- "Make a letter-size PDF"

#### 4. **Page Orientation**
Choose layout direction.

**Options:** `portrait` (default), `landscape`

**Example Requests:**
- "Generate a landscape PDF"
- "Create report in portrait mode"
- "Make a wide landscape report"

#### 5. **Summary Section**
Include or exclude executive summary.

**Options:** `true` (default), `false`

**Example Requests:**
- "Generate PDF without summary"
- "Create report with no executive summary"
- "Show only the data table"

---

## Usage Examples

### Example 1: Minimal Report (5 columns)
**Request:**
```
"Generate PDF for facility 88 on 2026-01-31 with only tracking ID, delivery record, address, city, and state"
```

**Result:**
- 5 columns: Tracking ID, Delivery Record, Address, City, State
- Portrait orientation
- Letter size
- With summary

### Example 2: Limited Records
**Request:**
```
"Show me only 10 records for facility 88 on 2026-01-31"
```

**Result:**
- First 10 records only
- All columns (default)
- Portrait orientation
- Letter size
- With summary

### Example 3: Landscape Report
**Request:**
```
"Create a landscape A4 PDF for facility 88 on 2026-01-31"
```

**Result:**
- All columns
- Landscape orientation
- A4 paper size
- With summary

### Example 4: Custom Columns + No Summary
**Request:**
```
"Generate PDF for facility 88 on 2026-01-31 with tracking ID, city, state, and zip code, no summary"
```

**Result:**
- 4 columns: Tracking ID, City, State, Zip
- Portrait orientation
- Letter size
- No summary section

### Example 5: Complete Customization
**Request:**
```
"Generate landscape A4 PDF for facility 88 on 2026-01-31 with only 20 records showing tracking ID, address, city, state, and reason code, without summary"
```

**Result:**
- 20 records maximum
- 5 custom columns
- Landscape orientation
- A4 paper size
- No summary section

---

## Project Structure

```
ReportAutomation/
├── .env                                # OpenAI API key (optional)
├── README.md                          # This file
├── requirements.txt                   # Python dependencies
├── startupclient.ps1                 # Startup script
└── src/
    └── AutogenReports/
        ├── main.py                    # FastAPI app + AutoGen agent
        ├── mcp_client.py             # MCP HTTP client
        ├── pdf_generator.py          # ReportLab PDF generation
        ├── static/
        │   ├── css/
        │   │   └── fedex_agent.css   # Web UI styles
        │   └── js/
        │       └── app.js            # Chat interface
        └── uitemplate/
            └── agent_console.html     # Web UI template
```

---

## Core Dependencies

### Runtime
- **autogen-agentchat** - AI agent framework (GPT-4o integration)
- **fastapi** - Web framework for API
- **uvicorn** - ASGI server
- **httpx** - Async HTTP client for MCP communication
- **reportlab** - PDF generation library
- **pillow** - Image processing for PDF

### Development
- **python-dotenv** - Environment variable loading

---

## API Endpoints

### Web Interface
- **GET /** - Chat-based web UI

### Chat API
- **POST /chat** - Process natural language requests
  ```json
  {
    "message": "Generate PDF for facility 88 on 2026-01-31"
  }
  ```

### PDF Generation
- **POST /generate-pdf-report**
  ```json
  {
    "facilityId": 88,
    "scanDate": "2026-01-31",
    "columns": "trackingId,cityName,stateCode",
    "page_size": "A4",
    "orientation": "landscape",
    "include_summary": false,
    "max_records": 50
  }
  ```

---

## MCP Server Integration

### How It Works
1. User makes request in chat
2. Agent extracts parameters (facility, date, customizations)
3. **mcp_client.py** calls MCP Server at `http://127.0.0.1:8001/api/get`
4. MCP Server authenticates with Bearer token and proxies to FedEx API
5. Data returned to agent
6. PDF generated with ReportLab
7. Download link returned in chat

### Benefits of Centralized MCP
- ✅ **No hardcoded tokens** - Authentication managed centrally
- ✅ **Easy token updates** - Edit MCP Server `.env`, restart server only
- ✅ **Multi-app support** - Other applications can use same MCP server
- ✅ **Centralized logging** - All API requests logged in one place
- ✅ **Security** - API credentials isolated from client code

### Connecting to MCP Server
The client automatically connects to MCP Server via HTTP:

```python
# mcp_client.py
MCP_SERVER_URL = f"http://127.0.0.1:{MCP_SERVER_PORT}"

async def fetch_non_delivered_tracking_ids(facility_id, scan_date):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{MCP_SERVER_URL}/api/get",
            params={
                "endpoint": "/getNonDeliveredTrackingIDs",
                "facilityId": facility_id,
                "scanDate": scan_date
            }
        )
```

---

## Troubleshooting

### "Cannot connect to MCP Server"
**Cause:** MCP Server not running

**Solution:**
```powershell
cd C:\Workspaces\Automation\ReportingMCPServer
.\start_server.ps1
```

Check health: http://127.0.0.1:8001/health

### "401 Unauthorized" from FedEx API
**Cause:** Bearer token expired (expires hourly)

**Solution:**
1. Get new token from FedEx Okta
2. Edit `ReportingMCPServer\.env`
3. Update `INTERNAL_API_KEY=<new_token>`
4. Restart MCP Server only (client restart not needed)

### Agent not responding
**Cause:** OpenAI API key missing or invalid

**Solution:**
Set environment variable:
```powershell
$env:OPENAI_API_KEY = "sk-..."
```

### PDF generation fails
**Cause:** Invalid facility ID or date format

**Solution:**
- Use facility ID as integer (e.g., 88)
- Use date format: YYYY-MM-DD (e.g., 2026-01-31)

### Port 8000 already in use
**Cause:** Another process using port 8000

**Solution:**
```powershell
# Find process
Get-Process python | Where-Object {$_.Path -like "*ReportAutomation*"}

# Stop process
Stop-Process -Id <pid> -Force

# Restart
.\startupclient.ps1
```

---

## Development

### Running in Development Mode
```powershell
uvicorn src.AutogenReports.main:app --host 127.0.0.1 --port 8000 --reload
```

The `--reload` flag enables hot reloading on code changes.

### Testing PDF Generation
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run test script
python test_agent_report.py
```

### Adding New Customizations
Edit `src/AutogenReports/pdf_generator.py` to add new PDF customization options.

Update tool description in `src/AutogenReports/main.py`:
```python
generate_pdf_tool = FunctionTool(
    generate_pdf_for_agent,
    description="""Your updated description with new parameters"""
)
```

---

## Adding Additional Applications

To connect other applications to the same MCP Server:

1. **Install httpx:**
   ```powershell
   pip install httpx
   ```

2. **Import HTTP client:**
   ```python
   import httpx
   ```

3. **Call MCP Server:**
   ```python
   async with httpx.AsyncClient() as client:
       response = await client.get(
           "http://127.0.0.1:8001/api/get",
           params={
               "endpoint": "/yourEndpoint",
               "param1": "value1"
           }
       )
       data = response.json()
   ```

**That's it!** No Bearer token needed - MCP Server handles authentication.

---

## Security Considerations

### Token Management
- Bearer token stored in MCP Server's `.env` file only
- Client code never contains authentication credentials
- `.gitignore` protects `.env` from version control

### Network Security
- Application runs on localhost (127.0.0.1) by default
- MCP Server enforces Bearer token authentication
- SSL verification configurable via `VERIFY_SSL` setting

### API Access
- All FedEx API requests routed through MCP Server
- Centralized logging for audit trails
- Token expiration enforced (hourly refresh required)

---

## Updating Bearer Token

When the FedEx token expires:

1. **Get new Bearer token from Okta**

2. **Update MCP Server:**
   ```powershell
   notepad C:\Workspaces\Automation\ReportingMCPServer\.env
   ```
   Update: `INTERNAL_API_KEY=<new_token>`

3. **Restart MCP Server only:**
   ```powershell
   cd C:\Workspaces\Automation\ReportingMCPServer
   .\start_server.ps1
   ```

**Client restart not needed** - Client automatically uses updated token via MCP Server.

---

## Column Mapping Reference

| Field Name | Display Name | Description |
|------------|--------------|-------------|
| `trackingId` | Tracking ID | Package tracking number |
| `deliveryRecordNumber` | Delivery Record | Internal delivery record |
| `addressLine1` | Address | Street address |
| `cityName` | City | City name |
| `stateCode` | State | State abbreviation |
| `postalCode` | Zip | Postal/ZIP code |
| `reasonCode` | Reason Code | Non-delivery reason code |
| `workAreaName` | Work Area | Work area designation |

---

## Tips for Best Results

1. **Be specific about columns:** List exactly which columns you want
2. **Combine options:** Request multiple customizations in one sentence
3. **Use natural language:** Agent understands conversational requests
4. **Specify record limits:** Use phrases like "only 10 records" or "first 20"
5. **Default behavior:** Without specifications, you get all columns, letter size, portrait, with summary, all records

---

## Architecture Benefits Recap

| Feature | Direct API (Old) | Centralized MCP (New) |
|---------|------------------|----------------------|
| Token Location | Hardcoded in client | MCP Server .env file |
| Token Updates | Restart all apps | Restart MCP Server only |
| Multiple Apps | Duplicate configuration | Shared MCP Server |
| Security | Token in source code | Token isolated in server |
| Logging | Per-application logs | Centralized MCP logs |
| SSL Configuration | Per-application | Centralized (VERIFY_SSL) |
| Maintenance Effort | High (N apps) | Low (1 server) |
| Scalability | Poor | Excellent |

---

## License

Internal FedEx project - proprietary and confidential.

---

## Support

For issues or questions:
1. Check MCP Server health: http://127.0.0.1:8001/health
2. Review MCP Server logs for API errors
3. Verify Bearer token hasn't expired (hourly refresh)
4. Check OpenAI API key is valid

---

## Conclusion

Your ReportAutomation system provides:

✅ **Intelligent Agent** - Natural language PDF generation  
✅ **Full Customization** - Columns, layout, size, records, summary  
✅ **Centralized Security** - Bearer token managed by MCP Server  
✅ **Multi-App Support** - Share API access across applications  
✅ **Easy Maintenance** - Update token once for all apps  
✅ **Production Ready** - Scalable architecture for enterprise use  

**Start generating customized reports with simple conversational requests!** 🚀
