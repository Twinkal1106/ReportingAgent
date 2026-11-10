# FedEx Reporting Automation System

An enterprise reporting automation solution featuring a Model Context Protocol (MCP) server, an AutoGen multi-tool agent, and both a FastAPI web console and a Streamlit dashboard with FedEx PurpleID (Okta SSO) authentication.

---

## 🏗️ Architecture Overview

The system consists of two primary services:

1. **`ReportingMCPServer`** (Port `8001`):
   - Fast MCP / REST proxy server interfacing with the upstream FedEx API Engine.
   - Provides reporting endpoints, non-delivered package tracking, and summary aggregations.
   - Handles bearer token validation and proxying.

2. **`ReportAutomation`** (Ports `8000` & `8501`):
   - **AutoGen Agent**: AI-powered assistant with tools for querying Cassandra database, generating PDF reports, and invoking MCP endpoints.
   - **Streamlit Dashboard** (`streamlit_app.py` on Port `8501`): FedEx-branded reporting console with Okta PurpleID (PKCE) authentication, session cookie forwarding, quick action chips, and interactive PDF downloads.
   - **FastAPI Web Console** (`main.py` on Port `8000`): Full web UI featuring conversational agent workflow with FedEx corporate styling.

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.10+
- Git

### 1. Configure Environment Variables
Copy the `.env.example` files and populate with your credentials:

```bash
# Reporting MCP Server
cp ReportingMCPServer/.env.example ReportingMCPServer/.env

# Report Automation Client
cp ReportAutomation/.env.example ReportAutomation/.env
```

### 2. Start the Reporting MCP Server (Port 8001)
```powershell
cd ReportingMCPServer
.\start_server.ps1
```

### 3. Start the Report Automation Client (Streamlit & FastAPI)
```powershell
cd ReportAutomation

# To launch Streamlit dashboard (Port 8501):
.\start_streamlit.ps1

# Or to launch FastAPI web console (Port 8000):
.\startupclient.ps1
```

---

## 🔒 Security Notice
- Never commit `.env` files or tokens to version control.
- Sample configurations are provided in `.env.example`.
