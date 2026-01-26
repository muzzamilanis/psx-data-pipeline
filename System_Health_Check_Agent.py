import asyncio
from typing import TypedDict, Annotated, Literal
from datetime import datetime
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from dotenv import load_dotenv
import os
import sys
import io
import msal
import requests
import subprocess
import threading
import time

load_dotenv()

# Force UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ============================================================================
# TOOLS
# ============================================================================

@tool
def upload_report_to_onedrive(html_file_path: str) -> dict:
    """
    Upload health check report to OneDrive.
    Use this when:
    - Health check found failures (important to document)
    - Report is from production branch
    - Stakeholders need to review
    
    Args:
        html_file_path: Path to the HTML report file
        
    Returns:
        dict with 'success' and 'url' or 'error'
    """
    try:
        client_id = os.getenv("ONEDRIVE_CLIENT_ID")
        client_secret = os.getenv("ONEDRIVE_CLIENT_SECRET")
        tenant_id = os.getenv("ONEDRIVE_TENANT_ID")
        
        if not all([client_id, client_secret, tenant_id]):
            return {"success": False, "error": "OneDrive credentials not configured"}
        
        # Authenticate
        authority = f"https://login.microsoftonline.com/{tenant_id}"
        app = msal.ConfidentialClientApplication(
            client_id,
            authority=authority,
            client_credential=client_secret
        )
        
        result = app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        
        if "access_token" not in result:
            return {"success": False, "error": result.get('error_description')}
        
        # Upload file
        with open(html_file_path, 'rb') as f:
            file_content = f.read()
        
        filename = os.path.basename(html_file_path)
        folder = os.getenv("ONEDRIVE_FOLDER_PATH", "/HealthCheckReports")
        
        upload_url = f"https://graph.microsoft.com/v1.0/me/drive/root:{folder}/{filename}:/content"
        
        headers = {
            "Authorization": f"Bearer {result['access_token']}",
            "Content-Type": "text/html"
        }
        
        response = requests.put(upload_url, headers=headers, data=file_content)
        response.raise_for_status()
        
        file_data = response.json()
        return {
            "success": True,
            "url": file_data.get("webUrl", ""),
            "name": filename
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
def check_onedrive_quota() -> dict:
    """
    Check OneDrive storage quota.
    Use this before uploading to avoid failures.
    
    Returns:
        dict with 'available_gb' and 'total_gb'
    """
    return {"available_gb": 50, "total_gb": 100}


@tool
def get_pr_metadata(pr_id: int = 0) -> dict:
    """
    Get metadata about the PR that triggered this check.
    Use this to determine report importance.
    
    Returns:
        dict with PR details (branch, author, labels, etc.)
    """
    # In real implementation, get from env or API
    return {
        "branch": os.getenv("CURRENT_PR_BRANCH", "development"),
        "is_hotfix": "hotfix" in os.getenv("CURRENT_PR_BRANCH", "").lower(),
        "author": os.getenv("CURRENT_PR_AUTHOR", "unknown"),
        "labels": []
    }


@tool
def send_email(to: str, subject: str, body: str, cc: str = None) -> dict:
    """
    Send email using Gmail API.
    Use this for critical alerts and notifications.
    
    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body (can be HTML)
        cc: Optional CC recipients (comma-separated)
        
    Returns:
        dict with 'success' and 'message_id' or 'error'
    """
    try:
        import base64
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        
        # Get OAuth credentials from env
        creds = Credentials(
            token=None,
            refresh_token=os.getenv("GOOGLE_OAUTH_REFRESH_TOKEN"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_OAUTH_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET"),
            scopes=['https://www.googleapis.com/auth/gmail.send']
        )
        
        service = build('gmail', 'v1', credentials=creds)
        
        # Create message
        message = MIMEMultipart('alternative')
        message['To'] = to
        message['Subject'] = subject
        if cc:
            message['Cc'] = cc
        
        # Add HTML body
        html_part = MIMEText(body, 'html')
        message.attach(html_part)
        
        # Encode and send
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        send_message = service.users().messages().send(
            userId='me',
            body={'raw': raw_message}
        ).execute()
        
        return {
            "success": True,
            "message_id": send_message['id'],
            "to": to
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool
def send_critical_alert_email(
    report_path: str,
    failed_count: int,
    total_count: int,
    max_response_time: float
) -> dict:
    """
    Send a critical alert email about health check failures.
    Use this when health check finds failures.
    
    Args:
        report_path: Path to the HTML report
        failed_count: Number of failed endpoints
        total_count: Total number of endpoints checked
        max_response_time: Maximum response time observed
        
    Returns:
        dict with 'success' and details
    """
    try:
        team_email = os.getenv("TEAM_LEAD_EMAIL", "mehroz.alam@thinkenabled.com")
        devops_email = os.getenv("DEVOPS_TEAM_EMAIL", "muzzammil@neuro-spinal.com")
        
        subject = f"🚨 CRITICAL: Health Check Failed - {failed_count}/{total_count} Endpoints Down"
        
        # Read the HTML report
        with open(report_path, 'r', encoding='utf-8') as f:
            report_html = f.read()
        
        # Create email body with inline report
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <div style="background: #fee2e2; border-left: 4px solid #ef4444; padding: 20px; margin-bottom: 20px;">
                <h2 style="color: #991b1b; margin: 0;">🚨 Critical Alert: System Health Check Failed</h2>
            </div>
            
            <div style="padding: 20px; background: #f8f9fa; border-radius: 8px; margin-bottom: 20px;">
                <h3>Summary</h3>
                <ul style="line-height: 1.8;">
                    <li><strong>Failed Endpoints:</strong> {failed_count} out of {total_count}</li>
                    <li><strong>Max Response Time:</strong> {max_response_time:.3f}s</li>
                    <li><strong>Report:</strong> {report_path}</li>
                    <li><strong>Timestamp:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</li>
                </ul>
            </div>
            
            <div style="margin-top: 20px;">
                <h3>Action Required</h3>
                <p>Please review the detailed report below and take necessary action.</p>
            </div>
            
            <hr style="margin: 30px 0;">
            
            {report_html}
        </body>
        </html>
        """
        
        # Send to team lead with DevOps in CC
        result = send_email.invoke({
            "to": team_email,
            "subject": subject,
            "body": body,
            "cc": devops_email
        })
        
        return result
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
def upload_to_google_drive(file_path: str, folder_name: str = "HealthCheckReports") -> dict:
    """
    Upload file to Google Drive.
    Use this to archive important reports.
    
    Args:
        file_path: Path to the file to upload
        folder_name: Google Drive folder name (default: HealthCheckReports)
        
    Returns:
        dict with 'success', 'file_id', and 'web_url' or 'error'
    """
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        
        # Get OAuth credentials
        creds = Credentials(
            token=None,
            refresh_token=os.getenv("GOOGLE_OAUTH_REFRESH_TOKEN"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_OAUTH_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET"),
            scopes=['https://www.googleapis.com/auth/drive.file']
        )
        
        service = build('drive', 'v3', credentials=creds)
        
        # Find or create folder
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        folders = results.get('files', [])
        
        if folders:
            folder_id = folders[0]['id']
        else:
            # Create folder
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = service.files().create(body=folder_metadata, fields='id').execute()
            folder_id = folder['id']
        
        # Upload file
        file_metadata = {
            'name': os.path.basename(file_path),
            'parents': [folder_id]
        }
        
        media = MediaFileUpload(file_path, mimetype='text/html', resumable=True)
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        
        return {
            "success": True,
            "file_id": file['id'],
            "web_url": file.get('webViewLink', ''),
            "folder": folder_name
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool
def list_drive_files(folder_name: str = "HealthCheckReports", max_results: int = 10) -> dict:
    """
    List recent files in Google Drive folder.
    Use this to check existing reports.
    
    Args:
        folder_name: Folder name to list files from
        max_results: Maximum number of files to return
        
    Returns:
        dict with 'success' and 'files' list or 'error'
    """
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        
        creds = Credentials(
            token=None,
            refresh_token=os.getenv("GOOGLE_OAUTH_REFRESH_TOKEN"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_OAUTH_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET"),
            scopes=['https://www.googleapis.com/auth/drive.readonly']
        )
        
        service = build('drive', 'v3', credentials=creds)
        
        # Find folder
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = service.files().list(q=query, spaces='drive', fields='files(id)').execute()
        folders = results.get('files', [])
        
        if not folders:
            return {"success": True, "files": [], "message": "Folder not found"}
        
        folder_id = folders[0]['id']
        
        # List files in folder
        query = f"'{folder_id}' in parents and trashed=false"
        results = service.files().list(
            q=query,
            pageSize=max_results,
            orderBy='createdTime desc',
            fields='files(id, name, createdTime, webViewLink)'
        ).execute()
        
        files = results.get('files', [])
        
        return {
            "success": True,
            "files": [
                {
                    "name": f['name'],
                    "created": f.get('createdTime'),
                    "url": f.get('webViewLink')
                }
                for f in files
            ]
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

# ============================================================================
# STATE
# ============================================================================

class HealthCheckState(TypedDict):
    """State for intelligent health check agent"""
    endpoints: list[str]
    current_index: int
    results: dict[str, dict]
    messages: Annotated[list, add_messages]
    final_report: list[str]
    html_report_path: str
    
    # Intelligence layer
    has_failures: bool
    failure_count: int
    max_response_time: float
    agent_decision: str  # Agent's reasoning


# ============================================================================
# NODES
# ============================================================================

def check_endpoint_node(state: HealthCheckState) -> HealthCheckState:
    """Check a single endpoint"""
    current_index = state["current_index"]
    endpoint = state["endpoints"][current_index]
    
    print(f"\nChecking endpoint {current_index + 1}/{len(state['endpoints'])}: {endpoint}")
    
    try:
        response = requests.get(endpoint, timeout=30)
        response_time = response.elapsed.total_seconds()
        
        result = {
            "status": "healthy" if response.status_code == 200 else "unhealthy",
            "status_code": response.status_code,
            "response_time": response_time,
            "timestamp": datetime.now().isoformat()
        }
        
        # Track failures
        if response.status_code != 200:
            state["has_failures"] = True
            state["failure_count"] = state.get("failure_count", 0) + 1
        
        # Track max response time
        if response_time > state.get("max_response_time", 0):
            state["max_response_time"] = response_time
        
        print(f"  Status: {response.status_code}")
        print(f"  Response Time: {response_time:.3f}s")
        
    except Exception as e:
        result = {
            "status": "unhealthy",
            "status_code": 0,
            "response_time": 0,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
        state["has_failures"] = True
        state["failure_count"] = state.get("failure_count", 0) + 1
        print(f"  Error: {e}")
    
    state["results"][endpoint] = result
    state["current_index"] = current_index + 1
    
    return state


def generate_console_report_node(state: HealthCheckState) -> HealthCheckState:
    """Generate console report"""
    print("\n" + "="*70)
    print("=== System Health Check Report ===")
    print("="*70)
    
    report_lines = []
    successful_checks = 0
    
    for endpoint, result in state["results"].items():
        # Use ASCII-safe symbols instead of Unicode
        status_symbol = "[OK]" if result["status"] == "healthy" else "[FAIL]"
        
        print(f"\nEndpoint: {endpoint}")
        print(f"  Status: {status_symbol} {result['status']}")
        print(f"  Status Code: {result['status_code']}")
        print(f"  Response Time: {result['response_time']:.3f}s")
        
        if result["status"] == "healthy":
            successful_checks += 1
        
        if "error" in result:
            print(f"  Error: {result['error']}")
        
        report_lines.append(f"Endpoint: {endpoint}")
        report_lines.append(f"  Status: {result['status']}")
        report_lines.append(f"  Status Code: {result['status_code']}")
        report_lines.append(f"  Response Time: {result['response_time']:.3f}s")
        if "error" in result:
            report_lines.append(f"  Error: {result['error']}")
    
    print("\n" + "="*70)
    print("=== Summary ===")
    print("="*70)
    print(f"Total Endpoints: {len(state['results'])}")
    print(f"Successful (200): {successful_checks}")
    print(f"Failed: {len(state['results']) - successful_checks}")
    print("="*70)
    
    report_lines.append("\n=== Summary ===")
    report_lines.append(f"Total Endpoints: {len(state['results'])}")
    report_lines.append(f"Successful (200): {successful_checks}")
    report_lines.append(f"Failed: {len(state['results']) - successful_checks}")
    
    state["final_report"] = report_lines
    return state


def generate_html_report_node(state: HealthCheckState) -> HealthCheckState:
    """Generate HTML report"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pr_id = os.getenv("CURRENT_PR_ID", "manual")
    filename = f"health_check_report_{timestamp}.html"
    
    successful_checks = sum(1 for r in state["results"].values() if r["status"] == "healthy")
    failed_checks = len(state["results"]) - successful_checks
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>System Health Check Report - {timestamp}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }}
        
        .header .timestamp {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 40px;
            background: #f8f9fa;
        }}
        
        .summary-card {{
            background: white;
            padding: 25px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: transform 0.3s ease;
        }}
        
        .summary-card:hover {{
            transform: translateY(-5px);
        }}
        
        .summary-card .number {{
            font-size: 3em;
            font-weight: bold;
            margin: 10px 0;
        }}
        
        .summary-card .label {{
            color: #666;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .summary-card.total .number {{ color: #667eea; }}
        .summary-card.success .number {{ color: #10b981; }}
        .summary-card.failed .number {{ color: #ef4444; }}
        
        .results {{
            padding: 40px;
        }}
        
        .results h2 {{
            color: #333;
            margin-bottom: 30px;
            font-size: 2em;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }}
        
        .endpoint {{
            background: white;
            border: 2px solid #e5e7eb;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            transition: all 0.3s ease;
        }}
        
        .endpoint:hover {{
            box-shadow: 0 8px 16px rgba(0,0,0,0.1);
            transform: translateX(5px);
        }}
        
        .endpoint.healthy {{
            border-left: 6px solid #10b981;
        }}
        
        .endpoint.unhealthy {{
            border-left: 6px solid #ef4444;
            background: #fef2f2;
        }}
        
        .endpoint-url {{
            font-size: 1.1em;
            color: #667eea;
            font-weight: 600;
            margin-bottom: 15px;
            word-break: break-all;
        }}
        
        .endpoint-details {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }}
        
        .detail {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .detail-label {{
            font-weight: 600;
            color: #666;
        }}
        
        .detail-value {{
            color: #333;
        }}
        
        .status-badge {{
            display: inline-block;
            padding: 6px 16px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.9em;
        }}
        
        .status-badge.healthy {{
            background: #d1fae5;
            color: #065f46;
        }}
        
        .status-badge.unhealthy {{
            background: #fee2e2;
            color: #991b1b;
        }}
        
        .error-message {{
            background: #fef2f2;
            border-left: 4px solid #ef4444;
            padding: 15px;
            margin-top: 15px;
            border-radius: 8px;
            color: #991b1b;
        }}
        
        .footer {{
            background: #f8f9fa;
            padding: 30px;
            text-align: center;
            color: #666;
            border-top: 2px solid #e5e7eb;
        }}
        
        @media (max-width: 768px) {{
            .summary {{
                grid-template-columns: 1fr;
            }}
            
            .endpoint-details {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏥 System Health Check Report</h1>
            <div class="timestamp">Generated: {datetime.now().strftime("%B %d, %Y at %I:%M:%S %p")}</div>
            <div class="timestamp">PR ID: {pr_id}</div>
        </div>
        
        <div class="summary">
            <div class="summary-card total">
                <div class="label">Total Endpoints</div>
                <div class="number">{len(state["results"])}</div>
            </div>
            <div class="summary-card success">
                <div class="label">Successful</div>
                <div class="number">{successful_checks}</div>
            </div>
            <div class="summary-card failed">
                <div class="label">Failed</div>
                <div class="number">{failed_checks}</div>
            </div>
        </div>
        
        <div class="results">
            <h2>📊 Detailed Results</h2>
"""
    
    for endpoint, result in state["results"].items():
        status_class = "healthy" if result["status"] == "healthy" else "unhealthy"
        status_code = result.get("status_code", 0)
        response_time = result.get("response_time", 0)
        
        html_content += f"""
            <div class="endpoint {status_class}">
                <div class="endpoint-url">{endpoint}</div>
                <div class="endpoint-details">
                    <div class="detail">
                        <span class="detail-label">Status:</span>
                        <span class="status-badge {status_class}">{result["status"].upper()}</span>
                    </div>
                    <div class="detail">
                        <span class="detail-label">Status Code:</span>
                        <span class="detail-value">{status_code}</span>
                    </div>
                    <div class="detail">
                        <span class="detail-label">Response Time:</span>
                        <span class="detail-value">{response_time:.3f}s</span>
                    </div>
                    <div class="detail">
                        <span class="detail-label">Timestamp:</span>
                        <span class="detail-value">{result.get("timestamp", "N/A")}</span>
                    </div>
                </div>
"""
        
        if "error" in result:
            html_content += f"""
                <div class="error-message">
                    <strong>Error:</strong> {result["error"]}
                </div>
"""
        
        html_content += """
            </div>
"""
    
    html_content += f"""
        </div>
        
        <div class="footer">
            <p>Automated Health Check System | Generated by LangGraph Agent</p>
            <p>Branch: {os.getenv("CURRENT_PR_BRANCH", "N/A")} | Author: {os.getenv("CURRENT_PR_AUTHOR", "N/A")}</p>
        </div>
    </div>
</body>
</html>
"""
    
    # Write HTML file
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"\n✓ HTML report generated: {filename}")
    state["html_report_path"] = filename
    
    return state


def agent_decision_node(state: HealthCheckState) -> HealthCheckState:
    """Agent decision with MCP tools"""
    
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    
    # Combine all tools
    tools = [
        upload_report_to_onedrive,
        check_onedrive_quota,
        get_pr_metadata,
        send_email,
        send_critical_alert_email,
        upload_to_google_drive,
        list_drive_files
    ]
    
    llm_with_tools = llm.bind_tools(tools)
    
    context = f"""
You are a DevOps automation agent. Health check completed:

**Results:**
- Total Endpoints: {len(state['endpoints'])}
- Failed: {state.get('failure_count', 0)}
- Max Response Time: {state.get('max_response_time', 0):.3f}s
- Report: {state['html_report_path']}

**Available Actions:**
1. upload_report_to_onedrive - Upload to OneDrive
2. upload_to_google_drive - Upload to Google Drive
3. send_critical_alert_email - Send email alert
4. send_email - Send custom email
5. list_drive_files - Check existing reports
6. get_pr_metadata - Get PR info

**Recipients:**
- Team: {os.getenv("TEAM_LEAD_EMAIL", "mehroz.alam@thinkenabled.com")}
- DevOps: {os.getenv("DEVOPS_TEAM_EMAIL", "muzzammil@neuro-spinal.com")}

**Criteria:**
- If failures → Upload report + Send critical email
- If all healthy → Just send summary email
- Prefer OneDrive over Google Drive if both available

**Task:** Execute appropriate actions based on results.
"""
    
    messages = [
        SystemMessage(content="You are a DevOps automation agent."),
        HumanMessage(content=context)
    ]
    
    print("\n" + "="*70)
    print("🤖 Agent analyzing...")
    print("="*70)
    
    for iteration in range(5):
        response = llm_with_tools.invoke(messages)
        messages.append(response)
        
        if not response.tool_calls:
            print(f"\n✅ Decision: {response.content}")
            state["agent_decision"] = response.content
            break
        
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            print(f"\n🔧 {tool_name}")
            print(f"   {tool_args}")
            
            selected_tool = next((t for t in tools if t.name == tool_name), None)
            if selected_tool:
                try:
                    tool_result = selected_tool.invoke(tool_args)
                    print(f"   ✓ {tool_result}")
                    messages.append(ToolMessage(content=str(tool_result), tool_call_id=tool_call["id"]))
                except Exception as e:
                    print(f"   ✗ {e}")
                    messages.append(ToolMessage(content=f"Error: {e}", tool_call_id=tool_call["id"]))
    
    return state

def should_continue(state: HealthCheckState) -> Literal["continue", "generate_console_report"]:
    """Determine if we should check more endpoints"""
    if state["current_index"] < len(state["endpoints"]):
        return "continue"
    return "generate_console_report"

def initialize_google_tools():
    """Check if Google API credentials are configured"""
    google_creds = all([
        os.getenv("GOOGLE_OAUTH_CLIENT_ID"),
        os.getenv("GOOGLE_OAUTH_CLIENT_SECRET"),
        os.getenv("GOOGLE_OAUTH_REFRESH_TOKEN")
    ])
    
    if google_creds:
        print("✓ Google APIs configured (Gmail + Drive)")
        return True
    else:
        print("⚠ Google APIs not configured")
        print("  → Add GOOGLE_OAUTH_* variables to .env")
        return False

# ============================================================================
# GRAPH
# ============================================================================

def build_intelligent_graph() -> StateGraph:
    """Build graph with intelligent agent decision-making"""
    workflow = StateGraph(HealthCheckState)
    
    # Add nodes
    workflow.add_node("check_endpoint", check_endpoint_node)
    workflow.add_node("generate_console_report", generate_console_report_node)
    workflow.add_node("generate_html_report", generate_html_report_node)
    workflow.add_node("agent_decision", agent_decision_node)
    
    # Set entry point
    workflow.set_entry_point("check_endpoint")
    
    # Define edges
    workflow.add_conditional_edges(
        "check_endpoint",
        should_continue,
        {
            "continue": "check_endpoint",
            "generate_console_report": "generate_console_report"
        }
    )
    
    workflow.add_edge("generate_console_report", "generate_html_report")
    workflow.add_edge("generate_html_report", "agent_decision")
    workflow.add_edge("agent_decision", END)
    
    return workflow.compile()


def main():
    """Main entry point with MCP initialization"""
    
    print("\n" + "="*70)
    print("🏥 System Health Check Agent")
    print("="*70)
    
    # Check Google API availability
    google_available = initialize_google_tools()
    
    print("\n🔧 Available Tools:")
    print(f"  • OneDrive: ✓")
    print(f"  • Google Drive: {'✓' if google_available else '✗'}")
    print(f"  • Gmail: {'✓' if google_available else '✗'}")
    print("="*70)
    
    endpoints = [
        "https://services-dev.sonik.health/aapi/health/ping",
        "https://services-dev.sonik.health/aapi/health/trace",
        "https://services-dev.sonik.health/tapi/health/ping",
        "https://services-dev.sonik.health/tapi/health/trace",
        "https://services-dev.sonik.health/aapi/health/Email/ping"
    ]
    
    initial_state = {
        "endpoints": endpoints,
        "current_index": 0,
        "results": {},
        "messages": [],
        "final_report": [],
        "html_report_path": "",
        "has_failures": False,
        "failure_count": 0,
        "max_response_time": 0.0,
        "agent_decision": ""
    }
    
    try:
        graph = build_intelligent_graph()
        final_state = graph.invoke(initial_state)
        
        print("\n" + "="*70)
        print("✅ Completed")
        print("="*70)
        print(f"Failed: {final_state.get('failure_count', 0)}")
        print(f"Report: {final_state.get('html_report_path')}")
        print(f"Decision: {final_state.get('agent_decision')}")
        print("="*70)
        
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()