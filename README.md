# PSX-Financial-Agent

Automated health monitoring system that integrates with Azure DevOps to trigger health checks when code is merged into specified branches.

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Components](#components)
- [Setup Guide](#setup-guide)
- [Configuration](#configuration)
- [Usage](#usage)
- [Monitoring & Validation](#monitoring--validation)
- [Troubleshooting](#troubleshooting)
- [API Documentation](#api-documentation)

---

## 🎯 Overview

This project provides an automated workflow that:

1. **Monitors Azure DevOps** for pull request merges into specific branches
2. **Automatically triggers** health check agents when merges are detected
3. **Generates comprehensive reports** in both console and HTML formats
4. **Runs as a Windows service** for continuous, unattended operation

### Key Features

✅ **Automated Monitoring** - Polls Azure DevOps every 60 seconds for new merges  
✅ **LangGraph-Based Agent** - Uses state machine pattern for health check workflow  
✅ **No Admin Permissions Required** - Only needs Personal Access Token (PAT)  
✅ **Persistent Checkpointing** - Never processes the same PR twice  
✅ **Comprehensive Logging** - Full audit trail of all operations  
✅ **HTML & Console Reports** - Detailed health check results  
✅ **Windows Service Support** - Runs in background automatically  

---

## 🏗️ Architecture

### System Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                      Azure DevOps Cloud                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Developer merges Branch A → Branch B (e.g., dev→main)   │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    [ADO Monitor polls via REST API]
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Local PC (Windows Service)                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              ado_monitor.py (Orchestrator)                │  │
│  │  • Polls Azure DevOps every 60 seconds                    │  │
│  │  • Detects new merged PRs                                 │  │
│  │  • Maintains checkpoint (last processed PR ID)            │  │
│  │  • Triggers health check agent                            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              ↓                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │       System-Health-Check-Agent.py (LangGraph Agent)     │  │
│  │  • Checks multiple API endpoints                          │  │
│  │  • Measures response times                                │  │
│  │  • Validates status codes                                 │  │
│  │  • Generates reports                                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              ↓                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   Generated Reports                       │  │
│  │  • health_check_PR{id}_{timestamp}.html                  │  │
│  │  • ado_monitor.log                                        │  │
│  │  • ado_monitor_checkpoint.json                            │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Component Interaction

```
ADO Monitor (Polling Loop)
    ↓
Check for new merged PRs → Azure DevOps API
    ↓
New PR detected? (ID > last_checked_pr_id)
    ↓ Yes
Trigger Health Check → subprocess.run(System-Health-Check-Agent.py)
    ↓
Health Check Agent (LangGraph Workflow)
    ├→ Node 1: Check Endpoint
    ├→ Node 2: Check Endpoint
    ├→ Node 3: Check Endpoint
    ├→ Node 4: Generate Console Report
    └→ Node 5: Generate HTML Report
    ↓
Save Report → health_check_PR{id}_{timestamp}.html
    ↓
Update Checkpoint → ado_monitor_checkpoint.json (last_pr_id)
    ↓
Continue Monitoring (wait 60 seconds, loop)
```

---

## 🧩 Components

### 1. **ADO Monitor** (`ado_monitor.py`)

**Purpose:** Orchestrator that monitors Azure DevOps and triggers health checks

**Key Responsibilities:**
- Poll Azure DevOps REST API for completed pull requests
- Track last processed PR ID to avoid duplicates
- Trigger health check agent when new merges are detected
- Log all activities for audit trail

**Technologies:**
- `requests` - HTTP client for Azure DevOps API
- `python-dotenv` - Environment variable management
- `logging` - Structured logging
- `subprocess` - Execute health check script

### 2. **Health Check Agent** (`System-Health-Check-Agent.py`)

**Purpose:** LangGraph-based agent that performs API health checks

**Key Responsibilities:**
- Check multiple API endpoints sequentially
- Measure response times and validate responses
- Generate detailed reports in multiple formats
- Handle errors gracefully

**Technologies:**
- `langgraph` - State graph workflow orchestration
- `requests` - HTTP client for health checks
- Built-in HTML generation

**State Machine:**
```python
HealthCheckState:
    - endpoints: list[str]           # URLs to check
    - current_index: int             # Current endpoint being checked
    - results: dict                  # Health check results
    - messages: list                 # Workflow messages
    - final_report: list[str]        # Console report
    - html_report_path: str          # Path to HTML report
```

### 3. **Windows Service Setup** (`ADO-Service-Setup.ps1`)

**Purpose:** Install and configure the monitor as a Windows service

**Key Features:**
- Uses NSSM (Non-Sucking Service Manager)
- Automatic restart on failure
- Configurable logging paths
- Easy management commands

### 4. **Configuration** (`.env` file)

**Purpose:** Store Azure DevOps credentials and settings

**Environment Variables:**
```bash
AZURE_DEVOPS_ORGANIZATION    # Organization name
AZURE_DEVOPS_PROJECT         # Project name
AZURE_DEVOPS_REPOSITORY      # Repository name/ID
AZURE_DEVOPS_PAT_TOKEN       # Personal Access Token
AZURE_DEVOPS_TARGET_BRANCH   # Branch to monitor (e.g., main, development)
AZURE_DEVOPS_POLL_INTERVAL   # Polling interval in seconds (default: 60)
```

---

## 🚀 Setup Guide

### Prerequisites

- **Windows PC** (Windows 10/11 or Windows Server)
- **Python 3.11+** installed
- **Azure DevOps** access (read permissions on code)
- **Internet connection** to reach Azure DevOps

### Step 1: Clone Repository

```powershell
git clone https://github.com/your-org/PSX-Financial-Agent.git
cd PSX-Financial-Agent
```

### Step 2: Create Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Step 3: Install Dependencies

```powershell
pip install -r requirements.txt
```

**Required packages:**
```
langgraph>=0.1.0
requests>=2.31.0
python-dotenv>=1.0.0
```

### Step 4: Get Azure DevOps Personal Access Token (PAT)

1. Go to **Azure DevOps** → Click your **profile picture** (top-right)
2. Select **Personal access tokens**
3. Click **+ New Token**
4. Configure:
   - **Name:** `Health Monitor`
   - **Organization:** Select your organization
   - **Expiration:** 90 days (or custom)
   - **Scopes:** Select **Code (Read)** ✅
5. Click **Create**
6. **⚠️ COPY THE TOKEN** (you won't see it again!)

### Step 5: Create `.env` Configuration File

```powershell
# Create .env file
New-Item -Path .env -ItemType File
```

Edit `.env` with your values:

```bash
# Azure DevOps Configuration
AZURE_DEVOPS_ORGANIZATION=your-org-name
AZURE_DEVOPS_PROJECT=YourProject
AZURE_DEVOPS_REPOSITORY=your-repo-name
AZURE_DEVOPS_PAT_TOKEN=your-pat-token-here
AZURE_DEVOPS_TARGET_BRANCH=development
AZURE_DEVOPS_POLL_INTERVAL=60
```

**How to find these values:**

| Variable | How to Find |
|----------|-------------|
| `ORGANIZATION` | From URL: `https://dev.azure.com/YOUR-ORG-HERE` |
| `PROJECT` | Project name in Azure DevOps |
| `REPOSITORY` | Go to Repos → Repository name at top |
| `PAT_TOKEN` | Copy from Step 4 |
| `TARGET_BRANCH` | Branch to monitor (e.g., `main`, `development`, `master`) |
| `POLL_INTERVAL` | How often to check (seconds, default: 60) |

### Step 6: Add `.env` to `.gitignore` (IMPORTANT!)

```bash
# .gitignore
.env
*.log
ado_monitor_checkpoint.json
health_check_*.html
```

### Step 7: Test Manually

```powershell
# Run monitor manually to test
python ado_monitor.py
```

Expected output:
```
2026-01-21 15:30:00 - INFO - Starting Azure DevOps Monitor...
2026-01-21 15:30:00 - INFO - Loading configuration from .env file...
2026-01-21 15:30:00 - INFO - ✅ Configuration loaded successfully from .env
2026-01-21 15:30:00 - INFO - ======================================================================
2026-01-21 15:30:00 - INFO - Azure DevOps Monitor Initialized
2026-01-21 15:30:00 - INFO - Organization: your-org
2026-01-21 15:30:00 - INFO - Project: YourProject
2026-01-21 15:30:00 - INFO - Repository: your-repo
2026-01-21 15:30:00 - INFO - Target Branch: development
2026-01-21 15:30:00 - INFO - Last Checked PR: #0
2026-01-21 15:30:00 - INFO - ======================================================================
2026-01-21 15:30:00 - INFO - 🔍 MONITORING STARTED
2026-01-21 15:30:00 - INFO - Poll interval: 60 seconds
2026-01-21 15:30:00 - INFO - ⏳ Waiting for merge events... (Press Ctrl+C to stop)
2026-01-21 15:30:02 - INFO - Found 20 completed PRs in target branch 'development'
```

### Step 8: Test Health Check Trigger

```powershell
# Test health check manually
python ado_monitor.py --test
```

This will trigger a test health check without waiting for a real PR merge.

### Step 9: Install as Windows Service

```powershell
# Run PowerShell as Administrator
.\ADO-Service-Setup.ps1
```

Expected output:
```
Installing Azure DevOps Monitor as Windows Service...
Installing service...
Service "AzureDevOpsHealthMonitor" installed successfully!
Starting service...

✅ Service installed successfully!

Service Name: AzureDevOpsHealthMonitor
Status: Running
```

---

## ⚙️ Configuration

### Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AZURE_DEVOPS_ORGANIZATION` | ✅ Yes | - | Azure DevOps organization name |
| `AZURE_DEVOPS_PROJECT` | ✅ Yes | - | Project name |
| `AZURE_DEVOPS_REPOSITORY` | ✅ Yes | - | Repository name or GUID |
| `AZURE_DEVOPS_PAT_TOKEN` | ✅ Yes | - | Personal Access Token with Code (Read) scope |
| `AZURE_DEVOPS_TARGET_BRANCH` | ❌ No | `main` | Branch to monitor for merges |
| `AZURE_DEVOPS_POLL_INTERVAL` | ❌ No | `60` | Polling interval in seconds |

### Health Check Endpoints Configuration

Edit endpoints in `System-Health-Check-Agent.py`:

```python
endpoints = [
    "https://services-dev.sonik.health/aapi/health/ping",
    "https://services-dev.sonik.health/aapi/health/trace",
    "https://services-dev.sonik.health/tapi/health/ping",
    "https://services-dev.sonik.health/tapi/health/trace",
    "https://services-dev.sonik.health/aapi/health/Email/ping"
]
```

---

## 📖 Usage

### Starting the Monitor

#### As Windows Service (Recommended)
```powershell
# Start service
nssm start AzureDevOpsHealthMonitor

# Check status
Get-Service AzureDevOpsHealthMonitor

# View logs
Get-Content .\ado_monitor.log -Tail 50 -Wait
```

#### Manually (For Testing)
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run monitor
python ado_monitor.py

# Test mode (triggers health check immediately)
python ado_monitor.py --test
```

### Stopping the Monitor

```powershell
# Stop service
nssm stop AzureDevOpsHealthMonitor

# Or press Ctrl+C if running manually
```

### Restarting the Monitor

```powershell
nssm restart AzureDevOpsHealthMonitor
```

### Viewing Logs

```powershell
# View last 50 lines
Get-Content .\ado_monitor.log -Tail 50

# Watch logs in real-time
Get-Content .\ado_monitor.log -Tail 50 -Wait

# View service-specific logs
Get-Content .\ado_monitor_service.log -Tail 50
```

---

## 🔍 Monitoring & Validation

### Validation Script

Run the validation script to check system health:

```powershell
.\validate_monitor.ps1
```

**Output includes:**
- ✅ Service status
- ✅ Configuration file validation
- ✅ Log file status
- ✅ Checkpoint information
- ✅ Python dependencies check

### What Happens When a PR is Merged

1. **Developer merges PR** in Azure DevOps (e.g., `feature/new-api` → `development`)

2. **Monitor detects merge** (within 60 seconds):
   ```log
   2026-01-21 16:45:12 - INFO - New merge detected: PR #2242
   2026-01-21 16:45:12 - INFO - ======================================================================
   2026-01-21 16:45:12 - INFO - 🎯 NEW MERGE DETECTED!
   2026-01-21 16:45:12 - INFO - PR ID:          #2242
   2026-01-21 16:45:12 - INFO - Title:          Add new API endpoint
   2026-01-21 16:45:12 - INFO - Source Branch:  feature/new-api
   2026-01-21 16:45:12 - INFO - Target Branch:  development
   2026-01-21 16:45:12 - INFO - Merged By:      John Doe
   ```

3. **Health check agent executes**:
   ```log
   2026-01-21 16:45:12 - INFO - 🏥 Triggering Health Check Agent...
   2026-01-21 16:45:12 - INFO -    Running: python System-Health-Check-Agent.py
   
   Checking endpoint 1/5: https://services-dev.sonik.health/aapi/health/ping
     Status: 200 - OK
     Response Time: 0.234s
   
   Checking endpoint 2/5: https://services-dev.sonik.health/aapi/health/trace
     Status: 200 - OK
     Response Time: 0.156s
   ...
   ```

4. **Report generated**:
   ```log
   === System Health Check Report ===
   
   Endpoint: https://services-dev.sonik.health/aapi/health/ping
     Status: healthy
     Status Code: 200
     Response Time: 0.234s
   
   === Summary ===
   Total Endpoints: 5
   Successful (200): 5
   Failed: 0
   
   ✓ HTML report generated: health_check_PR2242_20260121_164530.html
   ```

5. **Checkpoint updated**:
   ```json
   {
     "last_pr_id": 2242,
     "last_check_time": "2026-01-21T16:45:30"
   }
   ```

### File Outputs

| File | Purpose | Location |
|------|---------|----------|
| `ado_monitor.log` | Main monitor logs | Project root |
| `ado_monitor_service.log` | Windows service logs | Project root |
| `ado_monitor_checkpoint.json` | Last processed PR ID | Project root |
| `health_check_PR{id}_{timestamp}.html` | Health check report | Project root |

### Checkpoint System

The checkpoint file (`ado_monitor_checkpoint.json`) ensures PRs are never processed twice:

```json
{
  "last_pr_id": 2241,
  "last_check_time": "2026-01-21T15:30:00"
}
```

**Behavior:**
- Monitor only processes PRs with `ID > last_pr_id`
- Checkpoint updates after successful health check
- Persists across service restarts

**Reset checkpoint** (to reprocess PRs):
```powershell
# Stop service
nssm stop AzureDevOpsHealthMonitor

# Reset to earlier PR
@"
{
  "last_pr_id": 2200,
  "last_check_time": "2026-01-21T15:00:00"
}
"@ | Out-File -FilePath .\ado_monitor_checkpoint.json -Encoding UTF8

# Restart service
nssm start AzureDevOpsHealthMonitor
```

---

## 🔧 Troubleshooting

### Common Issues

#### Issue 1: Service Status is "Paused"

**Symptoms:**
```powershell
Get-Service AzureDevOpsHealthMonitor
# Status: Paused
```

**Solution:**
```powershell
# Check logs for errors
Get-Content .\ado_monitor_service.log -Tail 50

# Common causes:
# 1. Missing .env file
# 2. Invalid PAT token
# 3. Missing dependencies

# Restart service
nssm restart AzureDevOpsHealthMonitor
```

#### Issue 2: "Missing or invalid environment variables"

**Symptoms:**
```log
ERROR: Missing or invalid environment variables in .env file:
  - AZURE_DEVOPS_ORGANIZATION (Azure DevOps organization name)
```

**Solution:**
```powershell
# Check .env file exists
Test-Path .env

# Verify values don't contain "your-" or "replace-"
Get-Content .env

# Update .env with actual values
notepad .env
```

#### Issue 3: No New Merges Detected

**Symptoms:**
```log
Found 20 completed PRs in target branch 'development'
(no health checks trigger)
```

**Explanation:** All PRs have already been processed. The monitor only triggers on **NEW** merges (PR ID > last_checked_pr_id).

**Solution (for testing):**
```powershell
# Option 1: Use test mode
python ado_monitor.py --test

# Option 2: Reset checkpoint
@"
{
  "last_pr_id": 0,
  "last_check_time": "2026-01-21T00:00:00"
}
"@ | Out-File -FilePath .\ado_monitor_checkpoint.json -Encoding UTF8
```

#### Issue 4: "UnicodeEncodeError" in Logs

**Symptoms:**
```log
UnicodeEncodeError: 'charmap' codec can't encode character '\u274c'
```

**Solution:** Update `ado_monitor.py` with UTF-8 encoding:
```python
import sys
import codecs

if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
```

#### Issue 5: Health Check Script Not Found

**Symptoms:**
```log
FileNotFoundError: System-Health-Check-Agent.py
```

**Solution:**
```powershell
# Ensure both scripts are in same directory
ls System-Health-Check-Agent.py
ls ado_monitor.py

# Update working directory in service
nssm set AzureDevOpsHealthMonitor AppDirectory "D:\Projects\Muzzamil\Personal\Agent-Development\PSX-Financial-Agent"
nssm restart AzureDevOpsHealthMonitor
```

#### Issue 6: 401 Unauthorized from Azure DevOps

**Symptoms:**
```log
Error fetching PRs from Azure DevOps: 401 Client Error: Unauthorized
```

**Solution:**
```powershell
# PAT token is invalid or expired
# Generate new PAT token:
# 1. Azure DevOps → User Settings → Personal Access Tokens
# 2. Create new token with Code (Read) scope
# 3. Update .env file with new token

# Update .env
notepad .env
# Replace AZURE_DEVOPS_PAT_TOKEN with new token

# Restart service
nssm restart AzureDevOpsHealthMonitor
```

### Diagnostic Commands

```powershell
# Check service status
Get-Service AzureDevOpsHealthMonitor
nssm status AzureDevOpsHealthMonitor

# View service configuration
nssm get AzureDevOpsHealthMonitor AppDirectory
nssm get AzureDevOpsHealthMonitor Application
nssm get AzureDevOpsHealthMonitor AppParameters

# View recent logs
Get-Content .\ado_monitor.log -Tail 50
Get-Content .\ado_monitor_service.log -Tail 50

# Check Python environment
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\pip list

# Test Azure DevOps connectivity
python -c "import requests; import os; from dotenv import load_dotenv; load_dotenv(); print(requests.get(f\"https://dev.azure.com/{os.getenv('AZURE_DEVOPS_ORGANIZATION')}/{os.getenv('AZURE_DEVOPS_PROJECT')}/_apis/projects?api-version=7.0\", headers={'Authorization': f\"Basic {__import__('base64').b64encode(f\":{os.getenv('AZURE_DEVOPS_PAT_TOKEN')}\".encode()).decode()}\"}).status_code)"
```

### Getting Help

1. **Check logs first:**
   ```powershell
   Get-Content .\ado_monitor.log -Tail 100
   ```

2. **Run validation script:**
   ```powershell
   .\validate_monitor.ps1
   ```

3. **Test manually:**
   ```powershell
   python ado_monitor.py
   ```

4. **Enable debug logging:**
   Edit `ado_monitor.py`:
   ```python
   logging.basicConfig(
       level=logging.DEBUG,  # Changed from INFO
       ...
   )
   ```

---

## 📚 API Documentation

### Azure DevOps REST API

The monitor uses these endpoints:

#### Get Pull Requests
```http
GET https://dev.azure.com/{organization}/{project}/_apis/git/repositories/{repository}/pullrequests?api-version=7.0

Query Parameters:
  - searchCriteria.status=completed
  - searchCriteria.targetRefName=refs/heads/{branch}
  - $top=20

Headers:
  - Authorization: Basic {base64(:{pat_token})}
```

**Response:**
```json
{
  "value": [
    {
      "pullRequestId": 2241,
      "title": "Add new feature",
      "sourceRefName": "refs/heads/feature/new-feature",
      "targetRefName": "refs/heads/development",
      "status": "completed",
      "mergeStatus": "succeeded",
      "createdBy": {
        "displayName": "John Doe"
      },
      "closedDate": "2026-01-21T15:30:00Z"
    }
  ]
}
```

### Health Check Endpoints

The health check agent validates these endpoints:

| Endpoint | Expected Status | Timeout |
|----------|----------------|---------|
| `/aapi/health/ping` | 200 OK | 10s |
| `/aapi/health/trace` | 200 OK | 10s |
| `/tapi/health/ping` | 200 OK | 10s |
| `/tapi/health/trace` | 200 OK | 10s |
| `/aapi/health/Email/ping` | 200 OK | 10s |

**Success Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-21T15:30:00Z"
}
```

---

## 🔐 Security Best Practices

### 1. Protect PAT Token

✅ **DO:**
- Store PAT in `.env` file
- Add `.env` to `.gitignore`
- Set minimal scopes (Code: Read only)
- Set expiration date
- Rotate tokens regularly

❌ **DON'T:**
- Commit `.env` to Git
- Share PAT token
- Use admin-level tokens
- Set "never expire" tokens

### 2. Service Account

Consider using a dedicated service account:
```
1. Create dedicated Azure DevOps user
2. Grant minimal permissions (Code: Read)
3. Generate PAT for this account
4. Use in production
```

### 3. Log File Security

```powershell
# Restrict log file access (Windows)
icacls ado_monitor.log /grant:r "Users:(R)"
icacls .env /grant:r "Administrators:(F)"
```

### 4. Network Security

- Run monitor on secure network
- Consider VPN for remote access
- Firewall rules for Azure DevOps IPs only

---

## 📦 Project Structure

```
PSX-Financial-Agent/
│
├── .venv/                          # Virtual environment
├── .env                            # Configuration (NOT in Git)
├── .gitignore                      # Git ignore rules
│
├── ado_monitor.py                  # Main monitor script
├── System-Health-Check-Agent.py    # LangGraph health check agent
│
├── ADO-Service-Setup.ps1           # Windows service installer
├── validate_monitor.ps1            # Validation script
│
├── requirements.txt                # Python dependencies
├── README.md                       # This file
│
├── ado_monitor.log                 # Monitor logs
├── ado_monitor_service.log         # Service logs
├── ado_monitor_checkpoint.json     # Last processed PR
│
└── health_check_PR{id}_{timestamp}.html  # Generated reports
```

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

---

## 📝 License

[Your License Here]

---

## 👥 Authors

- **Your Name** - *Initial work*

---

## 🙏 Acknowledgments

- **LangGraph** - State machine framework
- **Azure DevOps** - Version control and CI/CD
- **NSSM** - Windows service manager
- **python-dotenv** - Environment management

---

## 📞 Support

For issues and questions:
- Create an issue on GitHub
- Email: your-email@example.com
- Documentation: [Link to docs]

---

## 🗺️ Roadmap

- [ ] Email notifications on health check failures
- [ ] Slack/Teams integration
- [ ] Multi-branch monitoring
- [ ] Dashboard UI
- [ ] Docker containerization
- [ ] Linux support
- [ ] Azure Function deployment option

---

**Last Updated:** January 21, 2026  
**Version:** 1.0.0