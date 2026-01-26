# PSX Financial Agent - Azure DevOps Health Monitoring System

An intelligent, autonomous health monitoring system that automatically detects Pull Request merges in Azure DevOps and executes comprehensive health checks on development/production endpoints. Built with LangGraph AI agents for intelligent decision-making.

---

## 📋 Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Features](#features)
- [Components](#components)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Service Deployment](#service-deployment)
- [Project Structure](#project-structure)
- [How It Works](#how-it-works)
- [Logging & Monitoring](#logging--monitoring)
- [Troubleshooting](#troubleshooting)
- [Requirements](#requirements)

---

## 🎯 Overview

This system provides **automated health monitoring** for your Azure DevOps repositories. When a Pull Request is merged to your target branch (e.g., `development` or `main`), the system:

1. **Detects** the merge event automatically
2. **Triggers** a comprehensive health check agent
3. **Tests** multiple API endpoints (ping, trace, email services)
4. **Analyzes** results using AI (GPT-4o via LangGraph)
5. **Makes intelligent decisions** about reporting and alerting
6. **Generates** beautiful HTML reports
7. **Uploads** reports to OneDrive (optional)
8. **Sends** email alerts for critical failures

**Use Cases:**
- Automated post-deployment health verification
- Continuous monitoring after PR merges
- Intelligent alerting for critical service failures
- Audit trail generation for compliance
- DevOps automation and CI/CD integration

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Azure DevOps                            │
│              (Pull Request Merged Event)                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  ado_monitor.py                             │
│  • Polls ADO API every 60s (configurable)                   │
│  • Detects new merged PRs by timestamp                      │
│  • Maintains checkpoint (ado_monitor_checkpoint.json)       │
│  • Triggers health check subprocess                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│          System-Health-Check-Agent.py                       │
│                 (LangGraph AI Agent)                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  1. Check Endpoints (Sequential)                    │   │
│  │     • aapi/health/ping                              │   │
│  │     • aapi/health/trace                             │   │
│  │     • tapi/health/ping                              │   │
│  │     • tapi/health/trace                             │   │
│  │     • aapi/health/Email/ping                        │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  2. Generate Console Report                         │   │
│  │     • ASCII-safe output (subprocess compatible)     │   │
│  │     • Summary statistics                            │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  3. Generate HTML Report                            │   │
│  │     • Beautiful responsive design                   │   │
│  │     • Visual status indicators                      │   │
│  │     • PR metadata embedded                          │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  4. AI Agent Decision (GPT-4o)                      │   │
│  │     • Analyzes health check results                 │   │
│  │     • Calls appropriate tools:                      │   │
│  │       - get_pr_metadata()                           │   │
│  │       - check_onedrive_quota()                      │   │
│  │       - upload_report_to_onedrive()                 │   │
│  │       - send_email_alert()                          │   │
│  │     • Makes intelligent decisions based on:         │   │
│  │       ✓ Failure count                               │   │
│  │       ✓ Response times                              │   │
│  │       ✓ Branch type (dev/main/hotfix)               │   │
│  │       ✓ Storage quota                               │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
        ┌──────────────┴──────────────┐
        │                             │
        ▼                             ▼
┌───────────────┐           ┌──────────────────┐
│   OneDrive    │           │  Email Alerts    │
│  HTML Reports │           │  (Critical/Warn) │
└───────────────┘           └──────────────────┘
```

---

## ✨ Features

### Automated Monitoring
- ✅ **Real-time PR merge detection** via Azure DevOps API
- ✅ **Timestamp-based tracking** (handles PR ID reuse, backdated merges)
- ✅ **Configurable polling interval** (default: 60 seconds)
- ✅ **Persistent checkpointing** (survives restarts)
- ✅ **Windows Service deployment** (runs 24/7 in background)

### Intelligent Health Checking
- ✅ **Multiple endpoint testing** (5 different health endpoints)
- ✅ **Response time tracking** (identifies performance degradation)
- ✅ **Error capturing** (network issues, timeouts, HTTP errors)
- ✅ **Sequential execution** with state management (LangGraph)

### AI-Powered Decision Making
- ✅ **GPT-4o integration** via LangChain/LangGraph
- ✅ **Context-aware reasoning** (branch type, failure severity)
- ✅ **Tool-based actions** (upload, email, quota check)
- ✅ **Smart storage management** (skip uploads for healthy dev builds)
- ✅ **Priority-based alerting** (critical for failures, warning for slowness)

### Comprehensive Reporting
- ✅ **Beautiful HTML reports** with responsive design
- ✅ **Visual status indicators** (green/red color coding)
- ✅ **Detailed metrics** (status codes, response times, timestamps)
- ✅ **PR metadata inclusion** (branch, author, merge date)
- ✅ **Error details** for failed endpoints

### Enterprise Integration
- ✅ **OneDrive upload** via Microsoft Graph API
- ✅ **Email alerts** with severity levels
- ✅ **Storage quota checking** before uploads
- ✅ **UTF-8 logging** for proper encoding

---

## 📦 Components

### 1. `ado_monitor.py`
**Azure DevOps Event Monitor**

- Continuously polls Azure DevOps API for merged PRs
- Detects new merges by comparing `closedDate` timestamps
- Saves checkpoint after each successful detection
- Spawns subprocess to run health check agent
- Logs all activity to `ado_monitor.log`

**Key Methods:**
```python
check_for_new_merges()      # Detects new PR merges
trigger_health_check(pr)    # Spawns health check subprocess
start_monitoring()          # Main polling loop
```

### 2. `System-Health-Check-Agent.py`
**LangGraph AI Health Check Agent**

- Built on LangGraph's StateGraph framework
- Executes health checks as a state machine workflow
- Uses GPT-4o for intelligent decision-making
- Generates both console and HTML reports
- Calls external tools based on AI analysis

**Workflow Nodes:**
```python
check_endpoint_node          # Tests one endpoint
generate_console_report_node # Creates ASCII report
generate_html_report_node    # Creates HTML report
agent_decision_node          # AI analyzes and acts
```

**AI Tools (Agent can call these):**
```python
@tool upload_report_to_onedrive()  # Microsoft Graph API
@tool send_email_alert()           # Email notifications
@tool check_onedrive_quota()       # Storage management
@tool get_pr_metadata()            # PR context retrieval
```

### 3. `ADO-Service-Setup.ps1`
**Windows Service Installer**

- Installs NSSM (Non-Sucking Service Manager)
- Configures monitor as Windows Service
- Sets auto-start on boot
- Provides management commands

---

## 🚀 Installation

### Prerequisites
- Python 3.11+ (tested with 3.13)
- Windows OS (for service deployment)
- Azure DevOps account with PAT token
- OpenAI API key (for GPT-4o)
- OneDrive (optional, for report uploads)

### Step 1: Clone Repository
```bash
git clone <your-repo-url>
cd PSX-Financial-Agent
```

### Step 2: Create Virtual Environment
```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

**Required Packages:**
```
langchain-openai
langgraph
requests
msal
python-dotenv
python-dateutil
```

### Step 4: Configure Environment Variables
Create a `.env` file in the project root:

```env
# Azure DevOps Configuration
AZURE_DEVOPS_ORGANIZATION=your-org-name
AZURE_DEVOPS_PROJECT=YourProject
AZURE_DEVOPS_REPOSITORY=your-repo-name
AZURE_DEVOPS_PAT_TOKEN=your-pat-token-here
AZURE_DEVOPS_TARGET_BRANCH=development
AZURE_DEVOPS_POLL_INTERVAL=60

# OpenAI Configuration
OPENAI_API_KEY=sk-your-openai-api-key

# OneDrive Configuration (Optional)
ONEDRIVE_CLIENT_ID=your-client-id
ONEDRIVE_CLIENT_SECRET=your-client-secret
ONEDRIVE_TENANT_ID=your-tenant-id
ONEDRIVE_FOLDER_PATH=/HealthCheckReports

# PR Context (Set by monitor automatically)
CURRENT_PR_ID=
CURRENT_PR_BRANCH=
CURRENT_PR_AUTHOR=
```

---

## ⚙️ Configuration

### Azure DevOps PAT Token Setup
1. Go to Azure DevOps → User Settings → Personal Access Tokens
2. Create new token with permissions:
   - **Code:** Read
   - **Pull Request Threads:** Read
3. Copy token to `.env` file

### OpenAI API Key
1. Get API key from https://platform.openai.com/api-keys
2. Add to `.env` file

### OneDrive Setup (Optional)
1. Register app in Azure AD
2. Grant Microsoft Graph API permissions:
   - `Files.ReadWrite.All`
3. Create client secret
4. Add credentials to `.env`

---

## 💻 Usage

### Manual Run (Testing)

**Test Health Check Agent:**
```bash
# Activate virtual environment
.venv\Scripts\Activate.ps1

# Run health check manually
python System-Health-Check-Agent.py
```

**Test ADO Monitor:**
```bash
# Run monitor (will check for new merges)
python ado_monitor.py
```

**Output:**
```
=======================================================================
Azure DevOps Monitor Initialized
Organization: yourorg
Project: YourProject
Repository: your-repo
Target Branch: development
=======================================================================
🔍 MONITORING STARTED
Poll interval: 60 seconds
⏳ Waiting for merge events... (Press Ctrl+C to stop)
=======================================================================
```

### Automated Run (Production)

Deploy as Windows Service for 24/7 monitoring:

```powershell
# Run PowerShell as Administrator
cd PSX-Financial-Agent
.\ADO-Service-Setup.ps1
```

**Service Management:**
```powershell
# Check status
Get-Service AzureDevOpsHealthMonitor

# Stop service
nssm stop AzureDevOpsHealthMonitor

# Start service
nssm start AzureDevOpsHealthMonitor

# Restart service
nssm restart AzureDevOpsHealthMonitor

# Remove service
nssm remove AzureDevOpsHealthMonitor confirm
```

---

## 📁 Project Structure

```
PSX-Financial-Agent/
│
├── .venv/                          # Virtual environment
├── logs/                           # Health check logs
│   └── health_check_YYYYMMDD_HHMMSS.log
│
├── ado_monitor.py                  # Main monitor script
├── System-Health-Check-Agent.py    # LangGraph health agent
├── ADO-Service-Setup.ps1           # Windows service installer
│
├── .env                            # Environment configuration
├── ado_monitor_checkpoint.json     # Persistent state
├── ado_monitor.log                 # Monitor activity log
│
├── health_check_PR####_TIMESTAMP.html  # Generated reports
│
├── requirements.txt                # Python dependencies
└── README.md                       # This file
```

---

## 🔄 How It Works

### Detection Flow
1. **Monitor starts** → Loads last checkpoint (`ado_monitor_checkpoint.json`)
2. **Polls ADO API** every 60s for completed PRs
3. **Compares timestamps** of PR `closedDate` with last checkpoint
4. **Detects new merge** if `closedDate > last_checked_merge_time`
5. **Spawns subprocess** to run health check agent
6. **Updates checkpoint** with latest merge timestamp

### Health Check Flow
1. **Initialize state** with endpoint list
2. **Node: check_endpoint** → Test one endpoint
   - Send HTTP GET request
   - Record status code, response time, errors
   - Update state (failures, max response time)
   - Loop until all endpoints checked
3. **Node: generate_console_report** → ASCII output for subprocess
4. **Node: generate_html_report** → Create beautiful HTML file
5. **Node: agent_decision** → AI analyzes results
   - Send context to GPT-4o with available tools
   - Agent decides which tools to call:
     - `get_pr_metadata()` → Check branch type
     - `check_onedrive_quota()` → Verify storage
     - `upload_report_to_onedrive()` → Upload if needed
     - `send_email_alert()` → Notify team if critical
   - Agent provides reasoning for decisions

### Decision Logic (AI-Driven)
The GPT-4o agent makes intelligent decisions:

| Scenario | Agent Decision |
|----------|----------------|
| **Any endpoint failed** | Upload report + Send critical email |
| **Response time > 2s** | Upload report + Send warning email |
| **All healthy + dev branch** | Skip upload (save storage) |
| **All healthy + main/production** | Upload (audit trail) |
| **Hotfix PR** | Always upload + email |

---

## 📊 Logging & Monitoring

### Monitor Logs (`ado_monitor.log`)
```
2026-01-22 13:02:30,624 - INFO - 🎯 NEW MERGE DETECTED!
2026-01-22 13:02:30,624 - INFO - PR ID:          #2233
2026-01-22 13:02:30,624 - INFO - Title:          [SI] - Add computer TH mapping
2026-01-22 13:02:30,624 - INFO - Source Branch:  feature/13600
2026-01-22 13:02:30,624 - INFO - Target Branch:  development
2026-01-22 13:02:30,624 - INFO - 🏥 Triggering Health Check Agent...
```

### Health Check Logs (`logs/health_check_*.log`)
```
2026-01-22 13:02:43,123 | INFO     | endpoint_checker     | Checking endpoint 1/5
2026-01-22 13:02:44,567 | INFO     | endpoint_checker     | ✅ Endpoint healthy - Response time: 1.942s
2026-01-22 13:02:45,890 | WARNING  | endpoint_checker     | ❌ Endpoint unhealthy - Status: 500
2026-01-22 13:02:50,234 | INFO     | agent_decision       | Agent calling tool: upload_report_to_onedrive
2026-01-22 13:02:51,456 | INFO     | tool                 | ✅ File uploaded successfully
```

### Checkpoint File (`ado_monitor_checkpoint.json`)
```json
{
  "last_merge_time": "2026-01-21T11:53:52.672637+00:00",
  "last_pr_id": 2233,
  "last_check_time": "2026-01-22T13:02:30.623193"
}
```

---

## 🛠️ Troubleshooting

### Issue: Monitor not detecting new PRs
**Solution:**
- Delete `ado_monitor_checkpoint.json` to reset
- Verify PAT token has correct permissions
- Check target branch matches in `.env`

### Issue: Health check fails with Unicode error
**Solution:**
- Already fixed with ASCII-safe symbols `[OK]` / `[FAIL]`
- UTF-8 encoding forced in script headers

### Issue: OneDrive upload fails
**Solution:**
- Verify `ONEDRIVE_TENANT_ID` is correct (not `your-tenant-id`)
- Check client secret hasn't expired
- Ensure app has Graph API permissions

### Issue: Service won't start
**Solution:**
```powershell
# Check service status
nssm status AzureDevOpsHealthMonitor

# View detailed error
nssm get AzureDevOpsHealthMonitor AppStdout
nssm get AzureDevOpsHealthMonitor AppStderr

# Verify Python path
nssm get AzureDevOpsHealthMonitor Application
```

---

## 📋 Requirements

### System Requirements
- Windows 10/11 or Windows Server 2016+
- 4GB RAM minimum
- Internet connectivity for API calls

### Python Requirements
```
python>=3.11
langchain-openai>=0.1.0
langgraph>=0.0.1
requests>=2.31.0
msal>=1.24.0
python-dotenv>=1.0.0
python-dateutil>=2.8.2
```

### API Requirements
- Azure DevOps PAT token (Code: Read, Pull Requests: Read)
- OpenAI API key (GPT-4o access)
- Microsoft Graph API credentials (optional, for OneDrive)

---

## 📝 Example Health Check Report

When a health check completes, you'll get:

**Console Output:**
```
======================================================================
=== System Health Check Report ===
======================================================================

Endpoint: https://services-dev.sonik.health/aapi/health/ping
  Status: [OK] healthy
  Status Code: 200
  Response Time: 1.942s

Endpoint: https://services-dev.sonik.health/aapi/health/Email/ping
  Status: [FAIL] unhealthy
  Status Code: 500
  Response Time: 1.674s

======================================================================
=== Summary ===
======================================================================
Total Endpoints: 5
Successful (200): 4
Failed: 1
======================================================================

🤖 Agent is analyzing results and deciding actions...
🔧 Agent is calling tool: get_pr_metadata
🔧 Agent is calling tool: upload_report_to_onedrive
🔧 Agent is calling tool: send_email_alert

✅ Agent Decision: Email alert sent with critical severity. 
Report uploaded to OneDrive for audit trail.
```

**HTML Report:**
- Visual dashboard with color-coded status
- Response time graphs
- Error details
- PR metadata (branch, author, merge date)

---

## 🔐 Security Considerations

- **PAT tokens** stored in `.env` (add to `.gitignore`)
- **API keys** never logged or committed
- **Checkpoint file** contains only timestamps and PR IDs
- **Service runs** with local system privileges (consider dedicated user)
- **HTTPS only** for all API communications

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/improvement`)
3. Commit changes (`git commit -am 'Add new feature'`)
4. Push to branch (`git push origin feature/improvement`)
5. Create Pull Request

---

## 📄 License

[Your License Here]

---

## 👤 Author

**Your Name**
- GitHub: [@yourusername](https://github.com/yourusername)
- Email: your.email@example.com

---

## 🙏 Acknowledgments

- **LangChain/LangGraph** - AI agent framework
- **OpenAI** - GPT-4o model
- **Microsoft** - Azure DevOps & Graph APIs
- **NSSM** - Windows service manager

---

## 📞 Support

For issues or questions:
1. Check [Troubleshooting](#troubleshooting) section
2. Review logs in `ado_monitor.log` and `logs/`
3. Open GitHub issue with:
   - Error message
   - Log excerpts
   - Steps to reproduce

---

**Last Updated:** January 22, 2026
**Version:** 1.0.0