#Requires -Version 5.1

[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [switch]$HealthCheck
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"
$venvDir = Join-Path $repoRoot ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$requirementsFile = Join-Path $backendDir "requirements.txt"
$packageFile = Join-Path $frontendDir "package.json"
$packageLockFile = Join-Path $frontendDir "package-lock.json"
$alembicConfig = Join-Path $repoRoot "alembic.ini"
$utf8NoBom = New-Object Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom
Set-Location -LiteralPath $repoRoot

function Write-Step {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host ""
    Write-Host "[00SWIFT] $Message" -ForegroundColor Cyan
}

function Get-Sha256 {
    param([Parameter(Mandatory = $true)][string]$Path)

    $stream = [IO.File]::OpenRead($Path)
    $sha256 = [Security.Cryptography.SHA256]::Create()
    try {
        $hashBytes = $sha256.ComputeHash($stream)
        return ([BitConverter]::ToString($hashBytes)).Replace("-", "")
    }
    finally {
        $sha256.Dispose()
        $stream.Dispose()
    }
}

function Test-SupportedPython {
    param(
        [Parameter(Mandatory = $true)][string]$File,
        [string[]]$PrefixArguments = @()
    )

    try {
        & $File @PrefixArguments -c "import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] < (3, 13) else 1)" *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Find-BootstrapPython {
    if (-not [string]::IsNullOrWhiteSpace($env:SWIFT_PYTHON)) {
        $configuredPython = [IO.Path]::GetFullPath($env:SWIFT_PYTHON)
        if (Test-SupportedPython -File $configuredPython) {
            return [PSCustomObject]@{
                File = $configuredPython
                PrefixArguments = @()
            }
        }
        throw "SWIFT_PYTHON does not point to a supported Python 3.11/3.12 runtime."
    }

    $launcher = Get-Command "py.exe" -ErrorAction SilentlyContinue
    if ($null -ne $launcher) {
        foreach ($selector in @("-3.12", "-3.11")) {
            if (Test-SupportedPython -File $launcher.Source -PrefixArguments @($selector)) {
                return [PSCustomObject]@{
                    File = $launcher.Source
                    PrefixArguments = @($selector)
                }
            }
        }
    }

    # Keep compatibility with the environment used by the previous launcher,
    # while isolating this project in its own .venv.
    $legacyCondaPython = Join-Path $env:USERPROFILE ".conda\envs\yz\python.exe"
    if ((Test-Path -LiteralPath $legacyCondaPython) -and
        (Test-SupportedPython -File $legacyCondaPython)) {
        return [PSCustomObject]@{
            File = $legacyCondaPython
            PrefixArguments = @()
        }
    }

    foreach ($commandName in @("python.exe", "python3.exe")) {
        $command = Get-Command $commandName -ErrorAction SilentlyContinue
        if (($null -ne $command) -and (Test-SupportedPython -File $command.Source)) {
            return [PSCustomObject]@{
                File = $command.Source
                PrefixArguments = @()
            }
        }
    }

    throw "Python 3.11 or 3.12 was not found. Install it, then run start.bat again."
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$File,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$FailureMessage
    )

    & $File @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$FailureMessage (exit code $LASTEXITCODE)."
    }
}

function Get-DescendantProcessIds {
    param([Parameter(Mandatory = $true)][int]$ParentProcessId)

    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $ParentProcessId" -ErrorAction SilentlyContinue
    foreach ($child in $children) {
        Get-DescendantProcessIds -ParentProcessId ([int]$child.ProcessId)
        [int]$child.ProcessId
    }
}

function Stop-ProcessTree {
    param([Parameter(Mandatory = $true)][int]$RootProcessId)

    $processIds = @(Get-DescendantProcessIds -ParentProcessId $RootProcessId)
    $processIds += $RootProcessId

    foreach ($processId in $processIds) {
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
}

function Test-TcpPortAvailable {
    param([Parameter(Mandatory = $true)][int]$Port)

    $listener = New-Object Net.Sockets.TcpListener -ArgumentList ([Net.IPAddress]::Any, $Port)
    try {
        $listener.Server.ExclusiveAddressUse = $true
        $listener.Start()
        return $true
    }
    catch {
        return $false
    }
    finally {
        $listener.Stop()
    }
}

function Initialize-PythonEnvironment {
    if (Test-Path -LiteralPath $venvPython) {
        if (-not (Test-SupportedPython -File $venvPython)) {
            throw "The existing .venv is not Python 3.11/3.12. Rename or remove '$venvDir' and retry."
        }
    }
    else {
        Write-Step "Creating the isolated Python environment"
        $bootstrap = Find-BootstrapPython
        $bootstrapArguments = @($bootstrap.PrefixArguments)
        $bootstrapArguments += @("-m", "venv", $venvDir)
        Invoke-Checked -File $bootstrap.File -Arguments $bootstrapArguments `
            -FailureMessage "Unable to create .venv"
    }

    $requirementsHash = Get-Sha256 -Path $requirementsFile
    $requirementsStamp = Join-Path $venvDir ".00swift-requirements.sha256"
    $needsInstall = -not (Test-Path -LiteralPath $requirementsStamp)

    if (-not $needsInstall) {
        $needsInstall = ((Get-Content -Raw -LiteralPath $requirementsStamp).Trim() -ne $requirementsHash)
    }

    if (-not $needsInstall) {
        & $venvPython -c "import alembic, cryptography, fastapi, httpx, jwt, lxml, pacs008, psycopg, pydantic_settings, sqlalchemy, uvicorn, xsdata" *> $null
        $needsInstall = $LASTEXITCODE -ne 0
    }

    if ($needsInstall) {
        Write-Step "Synchronizing backend dependencies"
        Invoke-Checked -File $venvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip") `
            -FailureMessage "Unable to upgrade pip"
        Invoke-Checked -File $venvPython -Arguments @("-m", "pip", "install", "-r", $requirementsFile) `
            -FailureMessage "Unable to install backend dependencies"
        [IO.File]::WriteAllText($requirementsStamp, $requirementsHash, $utf8NoBom)
    }
    else {
        Write-Step "Backend dependencies are up to date"
    }

    Invoke-Checked -File $venvPython -Arguments @("-m", "pip", "check") `
        -FailureMessage "The isolated Python environment has dependency conflicts"
}

function Initialize-Frontend {
    $nodeCommand = Get-Command "node.exe" -ErrorAction SilentlyContinue
    $npmCommand = Get-Command "npm.cmd" -ErrorAction SilentlyContinue
    if (($null -eq $nodeCommand) -or ($null -eq $npmCommand)) {
        throw "Node.js 22.12 or newer (including npm) was not found."
    }

    $nodeVersion = (& $nodeCommand.Source "--version").Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to read the Node.js version."
    }

    if ($nodeVersion -notmatch '^v?(\d+)\.(\d+)\.(\d+)') {
        throw "Unable to parse the Node.js version '$nodeVersion'."
    }

    $parsedNodeVersion = New-Object Version ([int]$Matches[1]), ([int]$Matches[2]), ([int]$Matches[3])
    if ($parsedNodeVersion -lt [Version]"22.12.0") {
        throw "Node.js 22.12 or newer is required; found $nodeVersion."
    }

    $nodeModulesDir = Join-Path $frontendDir "node_modules"
    $packageHash = Get-Sha256 -Path $packageFile
    $packageStamp = Join-Path $nodeModulesDir ".00swift-package.sha256"
    $needsInstall = -not (Test-Path -LiteralPath $packageStamp)

    if (-not $needsInstall) {
        $needsInstall = ((Get-Content -Raw -LiteralPath $packageStamp).Trim() -ne $packageHash)
    }

    if (-not $needsInstall) {
        & $npmCommand.Source "ls" "--prefix" $frontendDir "--depth=0" *> $null
        $needsInstall = $LASTEXITCODE -ne 0
    }

    if ($needsInstall) {
        Write-Step "Synchronizing frontend dependencies"
        if (Test-Path -LiteralPath $packageLockFile) {
            Invoke-Checked -File $npmCommand.Source `
                -Arguments @("ci", "--prefix", $frontendDir, "--no-audit", "--no-fund") `
                -FailureMessage "Unable to install locked frontend dependencies"
        }
        else {
            Invoke-Checked -File $npmCommand.Source `
                -Arguments @("install", "--prefix", $frontendDir, "--no-audit", "--no-fund") `
                -FailureMessage "Unable to install frontend dependencies"
        }
        [IO.File]::WriteAllText($packageStamp, $packageHash, $utf8NoBom)
    }
    else {
        Write-Step "Frontend dependencies are up to date"
    }

    Write-Step "Building the institutional frontend"
    Invoke-Checked -File $npmCommand.Source -Arguments @("run", "build", "--prefix", $frontendDir) `
        -FailureMessage "Frontend build failed"
}

function Get-LaunchConfiguration {
    $environmentFile = Join-Path $backendDir ".env"
    if (-not (Test-Path -LiteralPath $environmentFile)) {
        Copy-Item -LiteralPath (Join-Path $backendDir ".env.example") -Destination $environmentFile
        Write-Host "[00SWIFT] Created backend\.env from the sandbox example."
    }

    $configurationProbe = @'
import json
from pathlib import Path

from sqlalchemy.engine import make_url

from config import get_settings

settings = get_settings()
url = make_url(settings.db_url)
if url.drivername.startswith("sqlite") and url.database not in (None, "", ":memory:"):
    database_path = Path(url.database)
    if not database_path.is_absolute():
        database_path = (Path.cwd() / database_path).resolve()
    url = url.set(database=database_path.as_posix())

print(json.dumps({
    "db_url": url.render_as_string(hide_password=False),
    "host": settings.host,
    "port": settings.port,
    "swift_env": settings.swift_env,
}))
'@
    $probePayload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($configurationProbe))
    $probeWrapper = "import base64;exec(base64.b64decode('$probePayload'))"

    Push-Location $backendDir
    try {
        $configurationJson = & $venvPython -c $probeWrapper
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to load backend configuration."
        }
    }
    finally {
        Pop-Location
    }

    $configuration = (($configurationJson -join [Environment]::NewLine) | ConvertFrom-Json)
    if ($configuration.swift_env -ne "sandbox") {
        throw "The one-click launcher only supports SWIFT_ENV=sandbox. Use the documented manual launch for pilot/live."
    }

    return $configuration
}

function Start-Application {
    $configuration = Get-LaunchConfiguration
    $env:DB_URL = [string]$configuration.db_url
    $env:SWIFT_ENV = [string]$configuration.swift_env
    $serverHost = [string]$configuration.host
    $serverPort = [int]$configuration.port

    if (-not (Test-TcpPortAvailable -Port $serverPort)) {
        throw "Port $serverPort is already in use. Stop the existing service or change PORT in backend\.env."
    }

    Write-Step "Applying database migrations"
    Invoke-Checked -File $venvPython `
        -Arguments @("-m", "alembic", "-c", $alembicConfig, "upgrade", "head") `
        -FailureMessage "Database migration failed"

    $browserHost = $serverHost
    if ($browserHost -in @("0.0.0.0", "::", "[::]")) {
        $browserHost = "127.0.0.1"
    }
    $urlHost = $browserHost
    if ($urlHost.Contains(":") -and -not $urlHost.StartsWith("[")) {
        $urlHost = "[$urlHost]"
    }
    $appUrl = "http://${urlHost}:$serverPort/"
    $livenessUrl = "${appUrl}health"

    Write-Step "Starting 00SWIFT at $appUrl"
    $serverProcess = $null
    try {
        $serverProcess = Start-Process -FilePath $venvPython `
            -ArgumentList @("-m", "uvicorn", "main:app", "--host", $serverHost, "--port", [string]$serverPort) `
            -WorkingDirectory $backendDir -NoNewWindow -PassThru

        $ready = $false
        for ($attempt = 0; $attempt -lt 60; $attempt++) {
            $serverProcess.Refresh()
            if ($serverProcess.HasExited) {
                break
            }

            try {
                $response = Invoke-WebRequest -Uri $livenessUrl -UseBasicParsing -TimeoutSec 1
                if ($response.StatusCode -eq 200) {
                    $ready = $true
                    break
                }
            }
            catch {
                # The server is still booting.
            }
            Start-Sleep -Milliseconds 500
        }

        if (-not $ready) {
            $serverProcess.Refresh()
            if ($serverProcess.HasExited) {
                throw "The server exited before becoming ready (exit code $($serverProcess.ExitCode))."
            }
            throw "The server did not become ready within 30 seconds."
        }

        Write-Host "[00SWIFT] Ready: $appUrl" -ForegroundColor Green
        if ($HealthCheck) {
            $productionHealth = Invoke-RestMethod -Uri "${appUrl}production/v1/health" `
                -Headers @{ "X-Participant-ID" = "SANDBOX-ORIGIN" } -TimeoutSec 3
            if (($productionHealth.status -ne "ok") -or
                ($productionHealth.domain -ne "production") -or
                (-not $productionHealth.connectors.simulation)) {
                throw "Sandbox production-domain health verification failed."
            }
            if ($productionHealth.ready) {
                throw "Sandbox must not report production readiness."
            }
            Write-Host `
                "[00SWIFT] Sandbox health check passed; production readiness remains fail-closed." `
                -ForegroundColor Green
            return
        }

        Write-Host "[00SWIFT] Press Ctrl+C or close this window to stop the server."
        if (-not $NoBrowser) {
            try {
                Start-Process $appUrl
            }
            catch {
                Write-Warning "The browser could not be opened automatically. Open $appUrl manually."
            }
        }

        Wait-Process -Id $serverProcess.Id
        $serverProcess.Refresh()
        if ($serverProcess.ExitCode -ne 0) {
            throw "The server stopped with exit code $($serverProcess.ExitCode)."
        }
    }
    finally {
        if ($null -ne $serverProcess) {
            $serverProcess.Refresh()
            if (-not $serverProcess.HasExited) {
                Stop-ProcessTree -RootProcessId $serverProcess.Id
            }
        }
    }
}

try {
    if ($env:SWIFT_OPEN_BROWSER -eq "0") {
        $NoBrowser = $true
    }

    Write-Host "00SWIFT one-click launcher" -ForegroundColor White
    Write-Host "Repository: $repoRoot"
    Initialize-PythonEnvironment
    Initialize-Frontend
    Start-Application
    exit 0
}
catch {
    Write-Host ""
    Write-Host "[00SWIFT] ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
