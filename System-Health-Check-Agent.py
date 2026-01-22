import json
import sys
from typing import TypedDict, Annotated, Literal
from datetime import datetime
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
import requests
import os
import msal
from dotenv import load_dotenv

load_dotenv()

# Force UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
# ============================================================================
# TOOLS - Agent can choose to use these
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
def send_email_alert(recipients: list[str], report_path: str, severity: str) -> dict:
    """
    Send email alert about health check results.
    Use this when:
    - Health check failed
    - Critical services are down
    - Response times are abnormally high
    
    Args:
        recipients: List of email addresses
        report_path: Path to the HTML report
        severity: "critical", "warning", or "info"
    """
    # Implementation
    print(f"📧 Sending {severity} email to {recipients}")
    return {"success": True, "sent_to": recipients}


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
    filename = f"health_check_PR{pr_id}_{timestamp}.html"
    
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
    """
    INTELLIGENT NODE - Agent decides what actions to take
    based on health check results
    """
    
    # Initialize LLM
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    
    # Bind tools to LLM
    tools = [
        upload_report_to_onedrive,
        send_email_alert,
        check_onedrive_quota,
        get_pr_metadata
    ]
    llm_with_tools = llm.bind_tools(tools)
    
    # Create context for agent
    context = f"""
You are a DevOps automation agent. A health check just completed with these results:

**Health Check Summary:**
- Total Endpoints Checked: {len(state['endpoints'])}
- Failed Endpoints: {state.get('failure_count', 0)}
- All Healthy: {not state.get('has_failures', False)}
- Max Response Time: {state.get('max_response_time', 0):.3f}s
- Report Generated: {state['html_report_path']}

**Available Actions:**
1. upload_report_to_onedrive - Upload HTML report to OneDrive
2. send_email_alert - Send email to team
3. check_onedrive_quota - Check storage before uploading
4. get_pr_metadata - Get PR context (branch, author, etc.)

**Decision Criteria:**
- If ANY endpoint failed → Upload report + Send critical email
- If response times > 2s → Upload report + Send warning email
- If all healthy + dev branch → Skip upload (save storage)
- If all healthy + main/production → Upload (for audit trail)
- If hotfix PR → Always upload + email

**Your Task:**
Decide which actions to take and execute them. Be smart about storage and notifications.
"""
    
    messages = [
        SystemMessage(content="You are a DevOps automation agent. Make intelligent decisions based on health check results."),
        HumanMessage(content=context)
    ]
    
    print("\n" + "="*70)
    print("🤖 Agent is analyzing results and deciding actions...")
    print("="*70)
    
    # Agent reasoning loop
    for iteration in range(5):  # Max 5 iterations
        response = llm_with_tools.invoke(messages)
        messages.append(response)
        
        # If no tool calls, agent is done
        if not response.tool_calls:
            print(f"\n✅ Agent Decision: {response.content}")
            state["agent_decision"] = response.content
            break
        
        # Execute tool calls
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            print(f"\n🔧 Agent is calling tool: {tool_name}")
            print(f"   Arguments: {tool_args}")
            
            # Find and execute the tool
            selected_tool = next((t for t in tools if t.name == tool_name), None)
            if selected_tool:
                tool_result = selected_tool.invoke(tool_args)
                print(f"   Result: {tool_result}")
                
                # Add tool result to messages
                from langchain_core.messages import ToolMessage
                messages.append(
                    ToolMessage(
                        content=str(tool_result),
                        tool_call_id=tool_call["id"]
                    )
                )
    
    return state


def should_continue(state: HealthCheckState) -> Literal["continue", "generate_console_report"]:
    """Determine if we should check more endpoints"""
    if state["current_index"] < len(state["endpoints"]):
        return "continue"
    return "generate_console_report"


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
    """Run intelligent health check agent"""
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
    
    graph = build_intelligent_graph()
    final_state = graph.invoke(initial_state)
    
    print("\n" + "="*70)
    print("✅ Health Check Completed")
    print("="*70)
    print(f"Agent's Final Decision: {final_state['agent_decision']}")


if __name__ == "__main__":
    main()