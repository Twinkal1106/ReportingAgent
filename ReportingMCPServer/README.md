# FedEx API MCP Server

An HTTP-based MCP (Model Context Protocol) Server that provides centralized access to FedEx API endpoints with Bearer token authentication.

## Overview

This server acts as a proxy between client applications and the FedEx API, centralizing authentication and API access management. It exposes HTTP endpoints that can be called by any application needing to interact with FedEx services.

## Features

- **HTTP-based API Proxy**: FastAPI server exposing `/api/get` and `/api/post` endpoints
- **Centralized Authentication**: Bearer token management in one place (.env file)
- **Health Check**: `/health` endpoint for monitoring
- **Auto Documentation**: Swagger UI at `/docs` endpoint
- **Async Operations**: Built with async/await for high performance
- **SSL Configuration**: Configurable SSL verification
- **Comprehensive Logging**: Structured logging for all requests

## Architecture

```
Client Application (port 8000)
    ↓ HTTP Request
MCP HTTP Server (port 8001)
    ↓ Bearer Token + Request
FedEx API
```

## Installation

### Prerequisites

- Python 3.10 or higher
- Access to FedEx API endpoints
- Valid Bearer token from FedEx Okta authentication

### Quick Start

1. **Clone or navigate to the directory:**
```powershell
cd c:\Workspaces\Automation\ReportingMCPServer
```

2. **Run the startup script** (handles everything automatically):
```powershell
.\start_server.ps1
```

The script will:
- Create virtual environment if needed
- Install all dependencies
- Validate .env file exists
- Load environment variables
- Start the HTTP server on port 8001

### Manual Setup

If you prefer manual setup:

1. **Create virtual environment:**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. **Install dependencies:**
```powershell
pip install -r requirements.txt
```

3. **Configure environment** (see Configuration section below)

4. **Run the server:**
```powershell
python server.py
```

## Configuration

### Environment Variables

Create a `.env` file with the following configuration:

```env
# FedEx API Configuration
INTERNAL_API_BASE_URL=https://api-engine-release.app.clwdev4-az3.paas.fedex.com/v1/api-engine
INTERNAL_API_KEY=eyJraWQiOiJ...  # Your Bearer token from Okta
API_TIMEOUT=30
MCP_SERVER_PORT=8001
VERIFY_SSL=false
LOG_LEVEL=INFO
```

### Configuration Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `INTERNAL_API_BASE_URL` | Base URL for FedEx API | Required |
| `INTERNAL_API_KEY` | Bearer token (JWT from Okta) | Required |
| `API_TIMEOUT` | Request timeout in seconds | 30 |
| `MCP_SERVER_PORT` | Port for HTTP server | 8001 |
| `VERIFY_SSL` | SSL certificate verification | false |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, etc.) | INFO |

**Note:** Bearer tokens expire hourly and must be refreshed. Update the `INTERNAL_API_KEY` in `.env` and restart the server.

## API Endpoints

### Health Check
```http
GET /health
```
Returns server health status.

**Response:**
```json
{
  "status": "healthy",
  "service": "MCP HTTP Server"
}
```

### GET Proxy
```http
GET /api/get?endpoint={endpoint}&{query_params}
```

**Parameters:**
- `endpoint` (required): FedEx API endpoint path (e.g., `/getNonDeliveredTrackingIDs`)
- Additional query parameters are forwarded to the FedEx API

**Example:**
```http
GET /api/get?endpoint=/getNonDeliveredTrackingIDs&facilityId=88&scanDate=2026-01-31
```

**Response:**
```json
{
  "status": "success",
  "status_code": 200,
  "data": { /* FedEx API response */ }
}
```

### POST Proxy
```http
POST /api/post
Content-Type: application/json

{
  "endpoint": "/someEndpoint",
  "data": { /* request body */ }
}
```

**Request Body:**
- `endpoint` (required): FedEx API endpoint path
- `data` (optional): JSON object to send as request body

**Response:**
```json
{
  "status": "success",
  "status_code": 200,
  "data": { /* FedEx API response */ }
}
```

### API Documentation
```http
GET /docs
```
Access interactive Swagger UI for API testing and documentation.

## Usage Examples

### Using httpx (Python)
```python
import httpx

# Configure MCP server URL
MCP_SERVER_URL = "http://127.0.0.1:8001"

# GET request
async with httpx.AsyncClient() as client:
    response = await client.get(
        f"{MCP_SERVER_URL}/api/get",
        params={
            "endpoint": "/getNonDeliveredTrackingIDs",
            "facilityId": 88,
            "scanDate": "2026-01-31"
        }
    )
    data = response.json()
```

### Using curl
```bash
# GET request
curl "http://127.0.0.1:8001/api/get?endpoint=/getNonDeliveredTrackingIDs&facilityId=88&scanDate=2026-01-31"

# POST request
curl -X POST "http://127.0.0.1:8001/api/post" \
  -H "Content-Type: application/json" \
  -d '{"endpoint": "/someEndpoint", "data": {"key": "value"}}'

# Health check
curl "http://127.0.0.1:8001/health"
```

## Project Structure

```
ReportingMCPServer/
├── .env                    # Environment configuration (create this)
├── .gitignore             # Git ignore rules
├── README.md              # This file
├── requirements.txt       # Python dependencies
├── server.py              # Main HTTP server
├── start_server.ps1       # Startup script
└── .venv/                 # Virtual environment (auto-created)
```

## Dependencies

Core dependencies (see `requirements.txt`):
- **fastapi>=0.104.0**: Web framework for HTTP server
- **uvicorn>=0.24.0**: ASGI server
- **httpx**: Async HTTP client for API proxy
- **python-dotenv**: Environment variable management
- **pydantic>=2.0.0**: Data validation

## Troubleshooting

### Port Already in Use
If port 8001 is already in use:
1. Stop any existing server: `Get-Process python | Stop-Process -Force`
2. Or change `MCP_SERVER_PORT` in `.env`

### Bearer Token Expired
Symptoms: HTTP 401 errors
Solution:
1. Get new token from FedEx Okta
2. Update `INTERNAL_API_KEY` in `.env`
3. Restart server: `.\start_server.ps1`

### SSL Certificate Errors
If you encounter SSL errors:
1. Set `VERIFY_SSL=false` in `.env`
2. Restart server

### Dependencies Not Installing
```powershell
# Manually install dependencies
.\.venv\Scripts\pip.exe install -r requirements.txt
```

## Logging

Server logs include:
- Request/response details
- HTTP status codes
- Error messages
- Performance metrics

Logs are output to console with timestamps and log levels.

## Security Considerations

1. **Bearer Token**: Store securely in `.env`, never commit to git
2. **SSL Verification**: Enable in production (`VERIFY_SSL=true`)
3. **Network Access**: Restrict server access to trusted networks
4. **Token Rotation**: Update bearer token regularly (expires hourly)

## Development

### Running in Development Mode
```powershell
.\start_server.ps1
```
Server runs on http://127.0.0.1:8001 with auto-reload disabled by default.

### Testing the Server
```powershell
# Test health endpoint
Invoke-WebRequest -Uri "http://127.0.0.1:8001/health"

# Test API docs
Start-Process "http://127.0.0.1:8001/docs"
```

## Integration with ReportAutomation Client

This server is designed to work with the ReportAutomation client application:

1. **Start MCP Server** (port 8001): `.\start_server.ps1`
2. **Start Client** (port 8000): `cd ..\ReportAutomation ; .\startupclient.ps1`
3. **Access UI**: http://127.0.0.1:8000

The client application makes requests to the MCP server, which proxies them to FedEx API with proper authentication.

## License

Internal FedEx use only.

## Support

For issues or questions, contact the development team.

JAVA_SERVICE_TIMEOUT=30
JAVA_SERVICE_API_KEY=your_api_key_here
JAVA_SERVICE_VERIFY_SSL=true
```

### MCP Configuration

Add to your MCP client configuration (e.g., Claude Desktop's `config.json`):

```json
{
  "mcpServers": {
    "java-microservice": {
      "command": "python",
      "args": ["c:\\Project Management\\Automation\\ReportingMCPServer\\server.py"],
      "env": {
        "JAVA_SERVICE_BASE_URL": "http://localhost:8080"
      }
    }
  }
}
```

## Usage

### Running the Server

```powershell
python server.py
```

### Available Tools

#### 1. get_request
Send GET request to Java microservice endpoint.

**Parameters:**
- `endpoint` (required): API endpoint path (e.g., `/api/reports`)
- `params` (optional): Query parameters as key-value pairs
- `headers` (optional): Additional HTTP headers

**Example:**
```json
{
  "endpoint": "/api/reports",
  "params": {"status": "active", "limit": 10},
  "headers": {"X-Custom-Header": "value"}
}
```

#### 2. post_request
Send POST request to Java microservice endpoint.

**Parameters:**
- `endpoint` (required): API endpoint path
- `body` (required): Request body as JSON object
- `headers` (optional): Additional HTTP headers

**Example:**
```json
{
  "endpoint": "/api/reports",
  "body": {
    "title": "Monthly Report",
    "type": "summary",
    "data": {"month": "January"}
  }
}
```

#### 3. put_request
Send PUT request to update a resource.

**Parameters:**
- `endpoint` (required): API endpoint path
- `body` (required): Request body as JSON object
- `headers` (optional): Additional HTTP headers

#### 4. delete_request
Send DELETE request to remove a resource.

**Parameters:**
- `endpoint` (required): API endpoint path
- `headers` (optional): Additional HTTP headers

#### 5. health_check
Check health status of Java microservice (Spring Boot Actuator).

**Parameters:**
- `endpoint` (optional): Health check endpoint (default: `/actuator/health`)

#### 6. get_metrics
Get metrics from Java microservice.

**Parameters:**
- `endpoint` (optional): Metrics endpoint (default: `/actuator/metrics`)
- `metric_name` (optional): Specific metric name to retrieve

## Common Endpoints

### Spring Boot Applications

- Health: `/actuator/health`
- Info: `/actuator/info`
- Metrics: `/actuator/metrics`
- Environment: `/actuator/env`

### REST API Examples

- List resources: `/api/reports`
- Get resource: `/api/reports/123`
- Create resource: `POST /api/reports`
- Update resource: `PUT /api/reports/123`
- Delete resource: `DELETE /api/reports/123`

## Error Handling

The server returns structured error responses:

```json
{
  "error": "Connection refused",
  "type": "ConnectionError"
}
```

Common error types:
- `ConnectionError`: Cannot connect to service
- `TimeoutError`: Request exceeded timeout
- `HTTPStatusError`: HTTP error status code
- `ValueError`: Invalid parameters

## Development

### Project Structure

```
ReportingMCPServer/
├── server.py           # Main MCP server implementation
├── requirements.txt    # Python dependencies
├── config.json        # MCP and endpoint configuration
├── .env.example       # Environment variables template
└── README.md          # This file
```

### Testing

Test the server with a simple health check:

```python
# Test health check
{
  "tool": "health_check",
  "arguments": {
    "endpoint": "/actuator/health"
  }
}
```

## Integration with Java Microservices

### Spring Boot Configuration

Ensure your Spring Boot application exposes the required endpoints:

```yaml
# application.yml
management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics
  endpoint:
    health:
      show-details: always
```

### CORS Configuration

If accessing from a web application, configure CORS:

```java
@Configuration
public class CorsConfig {
    @Bean
    public WebMvcConfigurer corsConfigurer() {
        return new WebMvcConfigurer() {
            @Override
            public void addCorsMappings(CorsRegistry registry) {
                registry.addMapping("/api/**")
                    .allowedOrigins("*")
                    .allowedMethods("GET", "POST", "PUT", "DELETE");
            }
        };
    }
}
```

## Troubleshooting

### Connection Refused
- Verify the Java service is running
- Check the `JAVA_SERVICE_BASE_URL` in `.env`
- Ensure firewall allows the connection

### Authentication Errors
- Verify `JAVA_SERVICE_API_KEY` is correct
- Check if the Java service requires authentication
- Review API key format (Bearer token, API key header, etc.)

### Timeout Errors
- Increase `JAVA_SERVICE_TIMEOUT` value
- Check network connectivity
- Verify Java service performance

## Security Considerations

- Never commit `.env` file with real credentials
- Use environment variables for sensitive data
- Enable SSL/TLS verification in production
- Implement proper authentication and authorization
- Use HTTPS for production endpoints

## License

This project is part of the Report Automation system.

## Support

For issues or questions, please contact the development team.
