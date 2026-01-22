"""
Azure DevOps Monitor with Logging - Reads from .env file
"""

from dotenv import load_dotenv
import requests
import base64
import time
import subprocess
import os
from datetime import datetime
import json
import logging
import sys
from dateutil import parser as date_parser
from datetime import timezone

# Load environment variables from .env file
load_dotenv()

# Configure logging with UTF-8 encoding
import sys

# Force UTF-8 encoding for console output
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ado_monitor.log', encoding='utf-8'),  # Add encoding
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class AzureDevOpsMonitor:
    def __init__(self, organization, project, repository, pat_token, target_branch="main"):
        """Initialize Azure DevOps Monitor"""
        self.organization = organization
        self.project = project
        self.repository = repository
        self.target_branch = target_branch
        
        # Encode PAT for authentication
        auth_string = f":{pat_token}"
        auth_bytes = auth_string.encode('ascii')
        base64_bytes = base64.b64encode(auth_bytes)
        base64_auth = base64_bytes.decode('ascii')
        
        self.headers = {
            "Authorization": f"Basic {base64_auth}",
            "Content-Type": "application/json"
        }
        
        self.base_url = f"https://dev.azure.com/{organization}/{project}/_apis"
        
        # CHANGED: Track last merge time instead of PR ID
        self.last_checked_merge_time = self._load_last_checked_merge_time()
        
        # Path to your health check agent
        self.health_check_script = "System-Health-Check-Agent.py"
        
        logger.info("="*70)
        logger.info("Azure DevOps Monitor Initialized")
        logger.info(f"Organization: {organization}")
        logger.info(f"Project: {project}")
        logger.info(f"Repository: {repository}")
        logger.info(f"Target Branch: {target_branch}")
        logger.info(f"Last Checked Merge Time: {self.last_checked_merge_time}")
        logger.info("="*70)
    
    def _load_last_checked_merge_time(self):
        """Load the last checked merge timestamp from file"""
        checkpoint_file = "ado_monitor_checkpoint.json"
        if os.path.exists(checkpoint_file):
            try:
                with open(checkpoint_file, 'r') as f:
                    data = json.load(f)
                    # CHANGED: Load last_merge_time instead of last_pr_id
                    last_time_str = data.get('last_merge_time')
                    if last_time_str:
                        return date_parser.parse(last_time_str)
                    return None
            except Exception as e:
                logger.warning(f"Could not load checkpoint: {e}")
                return None
        return None
    
    def _save_last_checked_merge_time(self, merge_time, pr_id):
        """Save the last checked merge timestamp to file"""
        checkpoint_file = "ado_monitor_checkpoint.json"
        try:
            with open(checkpoint_file, 'w') as f:
                json.dump({
                    'last_merge_time': merge_time.isoformat(),
                    'last_pr_id': pr_id,  # Keep for reference
                    'last_check_time': datetime.now().isoformat()
                }, f, indent=2)
            logger.info(f"Checkpoint saved: PR #{pr_id} merged at {merge_time}")
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
    
    def get_merged_pull_requests(self):
        """Fetch recently completed/merged PRs from Azure DevOps"""
        url = f"{self.base_url}/git/repositories/{self.repository}/pullrequests"
        
        params = {
            "searchCriteria.status": "completed",
            "searchCriteria.targetRefName": f"refs/heads/{self.target_branch}",
            "$top": 50,  # Increased to catch more PRs
            "api-version": "7.0"
        }
        
        try:
            logger.debug(f"Fetching PRs from: {url}")
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            prs = data.get('value', [])
            logger.info(f"Found {len(prs)} completed PRs in target branch '{self.target_branch}'")
            return prs
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching PRs from Azure DevOps: {e}")
            return []
    
    def check_for_new_merges(self):
        """
        FIXED: Check for new merged PRs based on closedDate (merge time)
        instead of PR ID
        """
        all_prs = self.get_merged_pull_requests()
        new_merges = []
        
        latest_merge_time = self.last_checked_merge_time
        latest_pr_id = None
        
        for pr in all_prs:
            pr_id = pr.get('pullRequestId', 0)
            merge_status = pr.get('mergeStatus', '')
            closed_date_str = pr.get('closedDate')
            
            # Skip if not successfully merged
            if merge_status != 'succeeded':
                logger.debug(f"PR #{pr_id}: Skipping (merge status: {merge_status})")
                continue
            
            # Skip if no closed date
            if not closed_date_str:
                logger.debug(f"PR #{pr_id}: Skipping (no closed date)")
                continue
            
            # Parse the closed date
            try:
                closed_date = date_parser.parse(closed_date_str)
                
                # Make timezone-aware if not already
                if closed_date.tzinfo is None:
                    closed_date = closed_date.replace(tzinfo=timezone.utc)
                
            except Exception as e:
                logger.warning(f"PR #{pr_id}: Could not parse closed date '{closed_date_str}': {e}")
                continue
            
            # FIXED: Compare merge time instead of PR ID
            if self.last_checked_merge_time is None or closed_date > self.last_checked_merge_time:
                new_merges.append({
                    'pr': pr,
                    'merge_time': closed_date
                })
                
                # Track the latest merge time
                if latest_merge_time is None or closed_date > latest_merge_time:
                    latest_merge_time = closed_date
                    latest_pr_id = pr_id
                
                logger.info(f"New merge detected: PR #{pr_id} merged at {closed_date}")
            else:
                logger.debug(f"PR #{pr_id}: Already processed (merged at {closed_date})")
        
        # Sort by merge time (oldest first) to process in chronological order
        new_merges.sort(key=lambda x: x['merge_time'])
        
        # Update checkpoint if we found new PRs
        if latest_merge_time and latest_merge_time != self.last_checked_merge_time:
            self.last_checked_merge_time = latest_merge_time
            self._save_last_checked_merge_time(latest_merge_time, latest_pr_id)
        
        # Return just the PR objects
        return [merge['pr'] for merge in new_merges]
    
    def trigger_health_check(self, pr_info):
        """Execute health check for a merged PR"""
        pr_id = pr_info.get('pullRequestId', 'unknown')
        title = pr_info.get('title', 'N/A')
        source_branch = pr_info.get('sourceRefName', '').replace('refs/heads/', '')
        target_branch = pr_info.get('targetRefName', '').replace('refs/heads/', '')
        created_by = pr_info.get('createdBy', {}).get('displayName', 'Unknown')
        merged_date = pr_info.get('closedDate', datetime.now().isoformat())
        
        logger.info("="*70)
        logger.info("🎯 NEW MERGE DETECTED!")
        logger.info("="*70)
        logger.info(f"PR ID:          #{pr_id}")
        logger.info(f"Title:          {title}")
        logger.info(f"Source Branch:  {source_branch}")
        logger.info(f"Target Branch:  {target_branch}")
        logger.info(f"Merged By:      {created_by}")
        logger.info(f"Merged Date:    {merged_date}")
        logger.info("="*70)
        
        logger.info(f"🏥 Triggering Health Check Agent...")
        
        # Use sys.executable to get the current Python interpreter (from venv)
        python_executable = sys.executable
        logger.info(f"   Running: {python_executable} {self.health_check_script}")
        
        try:
            # Call your existing health check agent using the same Python interpreter
            result = subprocess.run(
                [python_executable, self.health_check_script],
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )
            
            # Log the output
            if result.stdout:
                logger.info("Health Check Output:")
                for line in result.stdout.split('\n'):
                    if line.strip():
                        logger.info(f"  {line}")
            
            if result.returncode == 0:
                logger.info("✅ Health check completed successfully!")
                logger.info(f"   Triggered by PR #{pr_id}: {title}")
            else:
                logger.error(f"❌ Health check failed with exit code {result.returncode}")
                if result.stderr:
                    logger.error(f"   Error: {result.stderr}")
            
            logger.info("="*70)
            
            return result.returncode == 0
            
        except subprocess.TimeoutExpired:
            logger.error("⏱️  Health check timed out (>10 minutes)")
            return False
        except Exception as e:
            logger.error(f"❌ Error running health check: {e}")
            return False
    
    def start_monitoring(self, poll_interval=60):
        """Start monitoring Azure DevOps for PR merges"""
        logger.info("="*70)
        logger.info("🔍 MONITORING STARTED")
        logger.info(f"Poll interval: {poll_interval} seconds")
        logger.info("⏳ Waiting for merge events... (Press Ctrl+C to stop)")
        logger.info("="*70)
        
        check_count = 0
        
        try:
            while True:
                check_count += 1
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                logger.debug(f"[Check #{check_count}] Polling at {current_time}")
                
                # Check for new merges
                new_merges = self.check_for_new_merges()
                
                if new_merges:
                    logger.info(f"🔔 Found {len(new_merges)} new merge(s)!")
                    self.trigger_health_check(new_merges[len(new_merges) - 1])  # Trigger for the latest merged PR
                else:
                    logger.debug(f"No new merges. Last checked PR: #{self.last_checked_merge_time}")
                
                # Wait before next check
                time.sleep(poll_interval)
                
        except KeyboardInterrupt:
            logger.info("="*70)
            logger.info("👋 Monitor stopped by user")
            logger.info(f"Total checks performed: {check_count}")
            logger.info(f"Last checked PR ID: #{self.last_checked_merge_time}")
            logger.info("="*70)


def validate_env_vars():
    """Validate required environment variables are set"""
    required_vars = {
        "AZURE_DEVOPS_ORGANIZATION": "Azure DevOps organization name",
        "AZURE_DEVOPS_PROJECT": "Azure DevOps project name",
        "AZURE_DEVOPS_REPOSITORY": "Azure DevOps repository name",
        "AZURE_DEVOPS_PAT_TOKEN": "Azure DevOps Personal Access Token"
    }
    
    missing_vars = []
    for var, description in required_vars.items():
        value = os.getenv(var)
        if not value or value.startswith("your-") or value.startswith("replace-"):
            missing_vars.append(f"{var} ({description})")
    
    if missing_vars:
        logger.error("="*70)
        logger.error("ERROR: Missing or invalid environment variables in .env file:")  # Changed emoji to text
        logger.error("="*70)
        for var in missing_vars:
            logger.error(f"  - {var}")  # Changed bullet to dash
        logger.error("="*70)
        logger.error("\nPlease update your .env file with correct values.")
        logger.error("\nExample .env file:")
        logger.error("  AZURE_DEVOPS_ORGANIZATION=myorg")
        logger.error("  AZURE_DEVOPS_PROJECT=MyProject")
        logger.error("  AZURE_DEVOPS_REPOSITORY=my-repo")
        logger.error("  AZURE_DEVOPS_PAT_TOKEN=abc123...")
        logger.error("  AZURE_DEVOPS_TARGET_BRANCH=main")
        logger.error("  AZURE_DEVOPS_POLL_INTERVAL=60")
        logger.error("="*70)
        return False
    
    return True


def main():
    """Main entry point - Reads from .env file"""
    
    logger.info("Starting Azure DevOps Monitor...")
    logger.info("Loading configuration from .env file...")
    
    # Check if .env exists
    if not os.path.exists('.env'):
        logger.error("="*70)
        logger.error("❌ .env file not found!")
        logger.error("="*70)
        logger.info("Creating template .env file...")
        
        template = """# Azure DevOps Configuration
AZURE_DEVOPS_ORGANIZATION=your-organization-name
AZURE_DEVOPS_PROJECT=your-project-name
AZURE_DEVOPS_REPOSITORY=your-repo-name
AZURE_DEVOPS_PAT_TOKEN=your-personal-access-token
AZURE_DEVOPS_TARGET_BRANCH=main
AZURE_DEVOPS_POLL_INTERVAL=60
"""
        with open('.env', 'w') as f:
            f.write(template)
        
        logger.info("✅ Created .env template file")
        logger.info("Please update .env with your Azure DevOps settings and restart.")
        logger.info("="*70)
        return
    
    # Validate environment variables
    if not validate_env_vars():
        return
    
    # Get configuration from environment variables
    organization = os.getenv("AZURE_DEVOPS_ORGANIZATION")
    project = os.getenv("AZURE_DEVOPS_PROJECT")
    repository = os.getenv("AZURE_DEVOPS_REPOSITORY")
    pat_token = os.getenv("AZURE_DEVOPS_PAT_TOKEN")
    target_branch = os.getenv("AZURE_DEVOPS_TARGET_BRANCH", "main")
    poll_interval = int(os.getenv("AZURE_DEVOPS_POLL_INTERVAL", "60"))
    
    logger.info("✅ Configuration loaded successfully from .env")
    
    # Create and start monitor
    monitor = AzureDevOpsMonitor(
        organization=organization,
        project=project,
        repository=repository,
        pat_token=pat_token,
        target_branch=target_branch
    )
    
    monitor.start_monitoring(poll_interval=poll_interval)


if __name__ == "__main__":
    main()