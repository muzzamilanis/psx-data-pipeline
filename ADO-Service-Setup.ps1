# Install ADO Monitor as Windows Service

Write-Host "Installing Azure DevOps Monitor as Windows Service..."

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "❌ Please run as Administrator!" -ForegroundColor Red
    exit 1
}

# Install NSSM if not already installed
if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) {
    Write-Host "Installing NSSM (service manager)..."
    winget install nssm
}

$currentPath = Get-Location
$pythonPath = (Get-Command python).Source
$scriptPath = Join-Path $currentPath "ado_monitor.py"

# Remove existing service if it exists
$serviceName = "AzureDevOpsHealthMonitor"
$existingService = Get-Service -Name $serviceName -ErrorAction SilentlyContinue

if ($existingService) {
    Write-Host "Removing existing service..."
    nssm stop $serviceName
    nssm remove $serviceName confirm
}

# Install service
Write-Host "Installing service..."
nssm install $serviceName $pythonPath $scriptPath
nssm set $serviceName AppDirectory $currentPath
nssm set $serviceName DisplayName "Azure DevOps Health Monitor"
nssm set $serviceName Description "Monitors Azure DevOps for PR merges and triggers health checks"
nssm set $serviceName Start SERVICE_AUTO_START

# Start service
Write-Host "Starting service..."
nssm start $serviceName

Write-Host ""
Write-Host "✅ Service installed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Service Name: $serviceName"
Write-Host "Status: " -NoNewline
$service = Get-Service -Name $serviceName
Write-Host $service.Status -ForegroundColor Green
Write-Host ""
Write-Host "To check logs: Get-EventLog -LogName Application -Source $serviceName"
Write-Host "To stop: nssm stop $serviceName"
Write-Host "To restart: nssm restart $serviceName"
Write-Host "To remove: nssm remove $serviceName"